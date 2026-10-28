#!/usr/bin/env python3
"""R2 v0.2 prototype: select at most two figures and give them dedicated space."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from postercs_audit.paths import REPOSITORY_ROOT, RUNS_ROOT

ROOT = REPOSITORY_ROOT
SCRIPT_DIR = Path(__file__).resolve().parent
for import_root in (ROOT, SCRIPT_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app import ppt_renderer  # noqa: E402
from app.feedback_loop import render_pptx_to_png  # noqa: E402

from postercs_audit.renderer.selection import _classify_figure, _load_rows, select_representative


OUTPUT = RUNS_ROOT / "renderer"
IMPORTANCE = {"high": 3.0, "medium": 1.5, "low": 0.0}
SECTION_FAMILY = {
    "method": "method",
    "approach": "method",
    "framework": "method",
    "experiment": "evidence",
    "result": "evidence",
    "evaluation": "evidence",
    "benchmark": "evidence",
}


def _family(section: str) -> str:
    value = (section or "").lower()
    return next((family for token, family in SECTION_FAMILY.items() if token in value), value)


def _score(panel: Any, task: Any, analysis: dict[str, Any]) -> float:
    figure = task.figures[panel.figure_id]
    tier = {"complex": 3.0, "medium": 1.5, "simple": 0.0}[analysis["complexity_tier"]]
    importance = IMPORTANCE.get((figure.importance or "medium").lower(), 1.5)
    dense = 1.5 if analysis["figure_type"] in {"comparison_table", "table", "architecture", "framework", "pipeline", "result_chart"} else 0.0
    required = min(float(analysis.get("estimated_required_width_1080px", 0.0)) / 600.0, 2.0)
    return round(tier + importance + dense + required, 3)


def _prepare(run_dir: Path) -> tuple[Any, dict[str, Any]]:
    report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8"))
    task = ppt_renderer.PosterTask.model_validate(report["input"])
    analyses = {fid: _classify_figure(fig) for fid, fig in task.figures.items()}
    candidates = []
    for index, panel in enumerate(task.panels):
        if panel.figure_id in analyses:
            candidates.append((_score(panel, task, analyses[panel.figure_id]), index, panel))
    candidates.sort(key=lambda item: (-item[0], item[1]))

    selected = []
    families: set[str] = set()
    # Prefer one method and one evidence figure when their scores are close.
    for score, index, panel in candidates:
        family = _family(panel.section)
        if len(selected) < 2 and (family not in families or not selected):
            selected.append((score, index, panel))
            families.add(family)
    for item in candidates:
        if len(selected) >= 2:
            break
        if item not in selected:
            selected.append(item)

    selected_ids = {panel.figure_id for _, _, panel in selected}
    selection = []
    suppressed = []
    for panel in task.panels:
        if not panel.figure_id:
            continue
        fid = panel.figure_id
        if fid in selected_ids:
            old_hint = panel.layout_hint
            panel.layout_hint = "image_only"
            selection.append({
                "panel": panel.section,
                "figure_id": fid,
                "score": next(score for score, _, p in selected if p is panel),
                "old_layout_hint": old_hint,
                "new_layout_hint": panel.layout_hint,
            })
        else:
            suppressed.append({"panel": panel.section, "figure_id": fid, "reason": "top_2_figure_budget"})
            panel.figure_id = ""
            panel.figure = None
            panel.layout_hint = "text_only"

    old_template = task.template
    if task.template == "template_storyflow":
        task.template = "template_dashboard"
    return task, {
        "prototype_version": "r2-v0.2",
        "warning": "Figure budget and thresholds are provisional.",
        "original_template": old_template,
        "render_template": task.template,
        "selected_figures": selection,
        "suppressed_figures": suppressed,
        "figure_analysis": analyses,
    }


def _dedicated_spans(original: Any, hero_ids: set[str]):
    def spans(grid: Any, panels: list[Any]) -> list[dict[str, int]]:
        heroes = [i for i, panel in enumerate(panels) if panel.figure_id in hero_ids]
        others = [i for i in range(len(panels)) if i not in heroes]
        if not heroes or len(panels) < 4:
            return original(grid, panels)
        boxes: list[dict[str, int] | None] = [None] * len(panels)
        top_rows = 3 if grid.rows >= 7 else max(2, grid.rows // 2)
        top_widths = ppt_renderer._alloc_units(grid.cols, [1.0] * len(others), min_each=2)
        col = 0
        for index, width in zip(others, top_widths):
            boxes[index] = grid.box(col, 0, width, top_rows)
            col += width
        hero_widths = ppt_renderer._alloc_units(grid.cols, [1.0] * len(heroes), min_each=4)
        col = 0
        for index, width in zip(heroes, hero_widths):
            boxes[index] = grid.box(col, top_rows, width, grid.rows - top_rows)
            col += width
        return [box for box in boxes if box is not None]
    return spans


def render_one(row: dict[str, str], output_root: Path) -> dict[str, Any]:
    run_dir = ROOT / "outputs" / "runs" / row["run_folder"]
    target = output_root / row["run_folder"]
    target.mkdir(parents=True, exist_ok=True)
    before = Path(row["iter1_png"])
    if before.exists():
        shutil.copy2(before, target / "before.png")
    task, decision = _prepare(run_dir)
    hero_ids = {item["figure_id"] for item in decision["selected_figures"]}
    original_spans = ppt_renderer.content_spans
    ppt_renderer.content_spans = _dedicated_spans(original_spans, hero_ids)
    try:
        result = ppt_renderer.generate_dashboard_pptx(task)
    finally:
        ppt_renderer.content_spans = original_spans
    pptx_path = target / "after.pptx"
    pptx_path.write_bytes(result.getvalue())
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
    (args.output_dir / "manifest.json").write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"outputs: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
