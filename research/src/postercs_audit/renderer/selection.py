#!/usr/bin/env python3
"""Generate non-destructive before/after posters with content-aware figure allocation.

This is an R2 research prototype. It intentionally monkey-patches the panel
weight only while rendering and never edits app/ppt_renderer.py or old runs.
The thresholds are provisional engineering bands, not paper conclusions.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from postercs_audit.paths import DATA_ROOT, REPOSITORY_ROOT, RUNS_ROOT

ROOT = REPOSITORY_ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import ppt_renderer  # noqa: E402
from app.feedback_loop import render_pptx_to_png  # noqa: E402
from app.models import PosterTask  # noqa: E402


LABELS = DATA_ROOT / "renderer-development" / "posters.csv"
SUMMARY = DATA_ROOT / "renderer-development" / "readability.csv"
OUTPUT = RUNS_ROOT / "renderer"
DENSE_TYPES = {"comparison_table", "table", "architecture", "framework", "pipeline", "result_chart"}


def _source_metrics(path: Path) -> dict[str, Any]:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return {"available": False, "reason": "image_unreadable"}
    src_h, src_w = image.shape
    scale = min(1.0, 768.0 / max(src_w, src_h))
    edge_image = cv2.resize(image, (max(1, round(src_w * scale)), max(1, round(src_h * scale))))
    edge_density = float(np.count_nonzero(cv2.Canny(edge_image, 80, 180)) / edge_image.size)

    _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    heights: list[int] = []
    for _, _, width, height, area in stats[1:count]:
        if 2 <= height <= max(12, int(src_h * 0.12)) and 3 <= area <= max(12, int(src_w * src_h * 0.02)):
            if width <= src_w * 0.5 and 0.05 <= width / max(height, 1) <= 25:
                heights.append(int(height))
    median_component = float(np.median(heights)) if heights else 0.0
    target_scale = 10.0 / median_component if median_component else 1.0
    return {
        "available": True,
        "source_width_px": src_w,
        "source_height_px": src_h,
        "edge_density": round(edge_density, 4),
        "median_component_height_px": round(median_component, 2),
        "estimated_scale_for_10px_detail": round(target_scale, 3),
        "estimated_required_width_1080px": round(src_w * target_scale, 1),
        "estimated_required_height_1080px": round(src_h * target_scale, 1),
    }


def _classify_figure(figure: Any) -> dict[str, Any]:
    path = Path(figure.image_source) if figure.image_source else Path()
    metrics = _source_metrics(path) if figure.image_source and path.exists() else {
        "available": False,
        "reason": "missing_image_source",
    }
    figure_type = (figure.type or "other").lower()
    edge = float(metrics.get("edge_density", 0.0))
    required_w = float(metrics.get("estimated_required_width_1080px", 0.0))
    dense_type = figure_type in DENSE_TYPES
    if dense_type or edge >= 0.12 or required_w >= 900:
        tier = "complex"
        weight_bonus = 4.0
    elif edge >= 0.075 or required_w >= 650:
        tier = "medium"
        weight_bonus = 2.0
    else:
        tier = "simple"
        weight_bonus = 0.5
    return {
        "figure_type": figure_type,
        "complexity_tier": tier,
        "panel_weight_bonus": weight_bonus,
        **metrics,
    }


def _load_rows() -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    with LABELS.open(newline="", encoding="utf-8") as fh:
        labels = [row for row in csv.DictReader(fh) if row.get("primary_issue")]
    with SUMMARY.open(newline="", encoding="utf-8") as fh:
        summary = {row["run_folder"]: row for row in csv.DictReader(fh)}
    return labels, summary


def select_representative(limit: int) -> list[dict[str, str]]:
    labels, summary = _load_rows()
    selected: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(rows: list[dict[str, str]], count: int) -> None:
        for row in rows:
            if len([r for r in selected if r.get("selection_group") == row.get("selection_group")]) >= count:
                break
            if row["run_folder"] not in seen:
                selected.append(row)
                seen.add(row["run_folder"])

    story = [dict(r, selection_group="storyflow") for r in labels if r["template"] == "template_storyflow"]
    add(story, 3)
    overload = [dict(r, selection_group="text_overload") for r in labels if r["primary_issue"] == "text_overload"]
    add(overload, 2)
    remaining = [dict(r, selection_group="lowest_readability") for r in labels if r["run_folder"] not in seen]
    remaining.sort(key=lambda r: float(summary.get(r["run_folder"], {}).get("min_median_detail_height_1080px") or 999))
    for row in remaining:
        if len(selected) >= limit:
            break
        selected.append(row)
        seen.add(row["run_folder"])
    return selected[:limit]


def _prepare_task(run_dir: Path) -> tuple[PosterTask, dict[str, dict[str, Any]], dict[str, Any]]:
    report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8"))
    task = PosterTask.model_validate(report["input"])
    analyses = {fid: _classify_figure(fig) for fid, fig in task.figures.items()}
    changes: list[dict[str, Any]] = []
    complex_count = 0
    for panel in task.panels:
        result = analyses.get(panel.figure_id)
        if not result:
            continue
        old_hint = panel.layout_hint
        if result["complexity_tier"] == "complex":
            complex_count += 1
            panel.layout_hint = "image_focus"
        elif result["complexity_tier"] == "medium" and panel.layout_hint == "text_only":
            panel.layout_hint = "text_top_image_bottom"
        if old_hint != panel.layout_hint:
            changes.append({
                "panel": panel.section,
                "figure_id": panel.figure_id,
                "old_layout_hint": old_hint,
                "new_layout_hint": panel.layout_hint,
            })
    old_template = task.template
    if task.template == "template_storyflow" and complex_count:
        task.template = "template_dashboard"
    decision = {
        "prototype_version": "r2-v0.1",
        "warning": "Provisional thresholds; visual calibration only, not final paper evidence.",
        "original_template": old_template,
        "render_template": task.template,
        "storyflow_routed": old_template != task.template,
        "panel_changes": changes,
        "figure_analysis": analyses,
    }
    return task, analyses, decision


def render_one(row: dict[str, str], output_root: Path) -> dict[str, Any]:
    run_dir = ROOT / "outputs" / "runs" / row["run_folder"]
    target = output_root / row["run_folder"]
    target.mkdir(parents=True, exist_ok=True)
    before = Path(row["iter1_png"])
    if before.exists():
        shutil.copy2(before, target / "before.png")

    task, analyses, decision = _prepare_task(run_dir)
    original_weight = ppt_renderer._panel_weight

    def content_aware_weight(panel: Any) -> float:
        base = original_weight(panel)
        return base + float(analyses.get(panel.figure_id, {}).get("panel_weight_bonus", 0.0))

    ppt_renderer._panel_weight = content_aware_weight
    try:
        pptx_bytes = ppt_renderer.generate_dashboard_pptx(task)
    finally:
        ppt_renderer._panel_weight = original_weight

    pptx_path = target / "after.pptx"
    pptx_path.write_bytes(pptx_bytes.getvalue())
    rendered = render_pptx_to_png(pptx_path, target)
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
    (args.output_dir / "manifest.json").write_text(
        json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"outputs: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
