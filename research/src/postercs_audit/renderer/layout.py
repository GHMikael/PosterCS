#!/usr/bin/env python3
"""R2 v0.3: adaptive 1-4 figure budget, conservative crop, and quality gate.

Research prototype only. Old runs and the production renderer are untouched.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from postercs_audit.paths import REPOSITORY_ROOT, RUNS_ROOT

ROOT = REPOSITORY_ROOT
SCRIPT_DIR = Path(__file__).resolve().parent
for import_root in (ROOT, SCRIPT_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app import ppt_renderer  # noqa: E402
from app.feedback_loop import render_pptx_to_png  # noqa: E402
from postercs_audit.renderer.selection import _classify_figure, _load_rows, select_representative
from postercs_audit.renderer.ranking import _family, _score
from postercs_audit.renderer.geometry import summarize


OUTPUT = RUNS_ROOT / "renderer"
FIGURE_BUDGET = 4.8
MAX_FIGURES = 4


def _space_cost(analysis: dict[str, Any]) -> float:
    """Convert predicted readable size into poster-space cost.

    Figure type must not force a dense class: a result chart with large labels
    can be cheaper than a small-font method diagram.
    """
    width = float(analysis.get("estimated_required_width_1080px", 9999))
    height = float(analysis.get("estimated_required_height_1080px", 9999))
    edge = float(analysis.get("edge_density", 0.0))
    if width <= 520 and height <= 360:
        cost = 1.0
    elif width <= 760 and height <= 520:
        cost = 1.4
    else:
        cost = 2.2
    if edge >= 0.16:
        cost += 0.2
    return round(min(cost, 2.4), 2)


def _content_bbox(image: np.ndarray) -> tuple[int, int, int, int] | None:
    """Find non-background bounds using corner-estimated background colour."""
    h, w = image.shape[:2]
    patch = max(2, min(h, w) // 40)
    corners = np.concatenate([
        image[:patch, :patch].reshape(-1, 3),
        image[:patch, -patch:].reshape(-1, 3),
        image[-patch:, :patch].reshape(-1, 3),
        image[-patch:, -patch:].reshape(-1, 3),
    ])
    background = np.median(corners, axis=0)
    distance = np.max(np.abs(image.astype(np.int16) - background.astype(np.int16)), axis=2)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = ((distance > 18) | (gray < 238)).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    points = cv2.findNonZero(mask)
    if points is None:
        return None
    x, y, bw, bh = cv2.boundingRect(points)
    pad_x, pad_y = max(4, round(w * 0.02)), max(4, round(h * 0.02))
    x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
    x1, y1 = min(w, x + bw + pad_x), min(h, y + bh + pad_y)
    return x0, y0, x1, y1


def _crop_asset(source: Path, target: Path) -> dict[str, Any]:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        return {"applied": False, "reason": "unreadable_source", "source": str(source)}
    h, w = image.shape[:2]
    bbox = _content_bbox(image)
    if bbox is None:
        return {"applied": False, "reason": "no_content_bbox", "source": str(source)}
    x0, y0, x1, y1 = bbox
    retained = ((x1 - x0) * (y1 - y0)) / max(w * h, 1)
    removed = 1.0 - retained
    # Conservative: only remove meaningful margins, never retain less than 55%.
    if removed < 0.06:
        return {"applied": False, "reason": "margin_below_6_percent", "source": str(source), "removed_ratio": round(removed, 4)}
    if retained < 0.55 or min(x1 - x0, y1 - y0) < 100:
        return {"applied": False, "reason": "unsafe_crop", "source": str(source), "retained_ratio": round(retained, 4)}
    target.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(target), image[y0:y1, x0:x1])
    return {
        "applied": bool(ok),
        "reason": "cropped" if ok else "write_failed",
        "source": str(source),
        "output": str(target) if ok else "",
        "bbox": [x0, y0, x1, y1],
        "removed_ratio": round(removed, 4),
    }


def _select(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedy knapsack with method/evidence diversity and a 1-4 image cap."""
    selected: list[dict[str, Any]] = []
    spent = 0.0
    for wanted_family in ("method", "evidence"):
        options = [c for c in candidates if c["family"] == wanted_family and c not in selected]
        options.sort(key=lambda c: (-c["utility_per_cost"], -c["score"], c["index"]))
        if options and spent + options[0]["cost"] <= FIGURE_BUDGET:
            selected.append(options[0])
            spent += options[0]["cost"]
    for candidate in sorted(candidates, key=lambda c: (-c["utility_per_cost"], -c["score"], c["index"])):
        if candidate in selected or len(selected) >= MAX_FIGURES:
            continue
        if spent + candidate["cost"] <= FIGURE_BUDGET:
            selected.append(candidate)
            spent += candidate["cost"]
    if not selected and candidates:
        selected = [max(candidates, key=lambda c: c["score"])]
    return selected


def _prepare(run_dir: Path, asset_dir: Path) -> tuple[Any, dict[str, Any]]:
    report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8"))
    task = ppt_renderer.PosterTask.model_validate(report["input"])
    analyses = {fid: _classify_figure(fig) for fid, fig in task.figures.items()}
    candidates = []
    for index, panel in enumerate(task.panels):
        if panel.figure_id not in analyses:
            continue
        analysis = analyses[panel.figure_id]
        cost = _space_cost(analysis)
        score = _score(panel, task, analysis)
        candidates.append({
            "index": index,
            "panel": panel,
            "figure_id": panel.figure_id,
            "family": _family(panel.section),
            "score": score,
            "cost": cost,
            "utility_per_cost": round(score / cost, 3),
        })
    selected = _select(candidates)
    selected_ids = {item["figure_id"] for item in selected}
    crop_log: dict[str, Any] = {}
    selected_log, suppressed_log = [], []
    for panel in task.panels:
        if not panel.figure_id:
            continue
        fid = panel.figure_id
        if fid not in selected_ids:
            suppressed_log.append({"panel": panel.section, "figure_id": fid, "reason": "adaptive_budget"})
            panel.figure_id, panel.figure, panel.layout_hint = "", None, "text_only"
            continue
        item = next(candidate for candidate in selected if candidate["figure_id"] == fid)
        figure = task.figures[fid]
        source = Path(figure.image_source) if figure.image_source else Path()
        crop = _crop_asset(source, asset_dir / f"{fid}.png") if source.exists() else {
            "applied": False, "reason": "missing_source", "source": str(source)
        }
        crop_log[fid] = crop
        if crop["applied"]:
            figure.image_source = crop["output"]
        old_hint = panel.layout_hint
        panel.layout_hint = "image_only"
        selected_log.append({
            "panel": panel.section,
            "figure_id": fid,
            "family": item["family"],
            "score": item["score"],
            "budget_cost": item["cost"],
            "old_layout_hint": old_hint,
            "new_layout_hint": panel.layout_hint,
        })
    old_template = task.template
    if task.template == "template_storyflow":
        task.template = "template_dashboard"
    return task, {
        "prototype_version": "r2-v0.3",
        "figure_budget": FIGURE_BUDGET,
        "figure_count": len(selected_log),
        "budget_spent": round(sum(item["budget_cost"] for item in selected_log), 2),
        "original_template": old_template,
        "render_template": task.template,
        "selected_figures": selected_log,
        "suppressed_figures": suppressed_log,
        "crop_log": crop_log,
        "figure_analysis": analyses,
    }


def _adaptive_spans(original: Any, hero_ids: set[str]):
    def spans(grid: Any, panels: list[Any]) -> list[dict[str, int]]:
        heroes = [i for i, panel in enumerate(panels) if panel.figure_id in hero_ids]
        others = [i for i in range(len(panels)) if i not in heroes]
        if not heroes or len(panels) < 4:
            return original(grid, panels)
        boxes: list[dict[str, int] | None] = [None] * len(panels)
        top_rows = 3 if grid.rows >= 7 else max(2, grid.rows // 2)
        widths = ppt_renderer._alloc_units(grid.cols, [1.0] * len(others), min_each=2)
        col = 0
        for index, width in zip(others, widths):
            boxes[index] = grid.box(col, 0, width, top_rows)
            col += width
        hero_widths = ppt_renderer._alloc_units(grid.cols, [1.0] * len(heroes), min_each=2)
        col = 0
        for index, width in zip(heroes, hero_widths):
            boxes[index] = grid.box(col, top_rows, width, grid.rows - top_rows)
            col += width
        return [box for box in boxes if box is not None]
    return spans


def _gate(task: Any, geometry: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    min_detail = float(geometry.get("min_detail") or 0)
    median_detail = float(geometry.get("median_detail") or 0)
    selected_families = {item["family"] for item in decision["selected_figures"]}
    total_bullets = sum(len(panel.content or []) for panel in task.panels)
    checks = {
        "has_figure": geometry["picture_count"] >= 1,
        "figure_count_within_budget": 1 <= geometry["picture_count"] <= MAX_FIGURES,
        "minimum_detail_discernible": min_detail >= 4.0,
        "median_detail_near_comfortable": median_detail >= 8.0,
        "method_or_evidence_covered": bool(selected_families & {"method", "evidence"}),
        "text_load_provisional": total_bullets <= 30,
    }
    hard = ["has_figure", "figure_count_within_budget", "method_or_evidence_covered"]
    status = "fail" if any(not checks[key] for key in hard) else ("pass" if all(checks.values()) else "warn")
    return {
        "status": status,
        "checks": checks,
        "geometry": geometry,
        "total_source_bullets": total_bullets,
        "note": "4px/8px are provisional discernible/near-comfortable proxy thresholds.",
    }


def render_one(row: dict[str, str], output_root: Path) -> dict[str, Any]:
    run_dir = ROOT / "outputs" / "runs" / row["run_folder"]
    target = output_root / row["run_folder"]
    target.mkdir(parents=True, exist_ok=True)
    before = Path(row["iter1_png"])
    if before.exists():
        shutil.copy2(before, target / "before.png")
    task, decision = _prepare(run_dir, target / "prepared_assets")
    hero_ids = {item["figure_id"] for item in decision["selected_figures"]}
    original_spans = ppt_renderer.content_spans
    ppt_renderer.content_spans = _adaptive_spans(original_spans, hero_ids)
    try:
        result = ppt_renderer.generate_dashboard_pptx(task)
    finally:
        ppt_renderer.content_spans = original_spans
    pptx_path = target / "after.pptx"
    pptx_path.write_bytes(result.getvalue())
    rendered = render_pptx_to_png(pptx_path, target)
    geometry = summarize(pptx_path)
    decision["quality_gate"] = _gate(task, geometry, decision)
    decision.update({
        "run_folder": row["run_folder"],
        "selection_group": row.get("selection_group", "manual"),
        "human_primary": row["primary_issue"],
        "human_secondary": row.get("secondary_issues", ""),
        "after_png": str(rendered) if rendered else "",
    })
    (target / "decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--run-folder", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    rows = select_representative(max(args.limit, 1))
    if args.run_folder:
        wanted = set(args.run_folder)
        labels, _ = _load_rows()
        rows = [dict(row, selection_group="manual") for row in labels if row["run_folder"] in wanted]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    decisions = []
    for index, row in enumerate(rows, 1):
        print(f"[{index}/{len(rows)}] {row['run_folder']}", flush=True)
        decisions.append(render_one(row, args.output_dir))
    (args.output_dir / "manifest.json").write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"outputs: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
