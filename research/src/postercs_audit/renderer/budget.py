#!/usr/bin/env python3
"""R2 v0.4: v0.3 plus bullet budget and portrait/feasibility fallback."""

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
from postercs_audit.renderer.geometry import summarize
from postercs_audit.renderer.selection import _load_rows, select_representative
from postercs_audit.renderer.layout import _adaptive_spans, _gate, _prepare as prepare_layout


OUTPUT = RUNS_ROOT / "renderer"
MAX_TEXT_BULLETS = 3
MAX_BULLET_CHARS = 105


def _feasibility(analysis: dict[str, Any], count: int) -> float:
    required_w = max(float(analysis.get("estimated_required_width_1080px", 9999)), 1)
    required_h = max(float(analysis.get("estimated_required_height_1080px", 9999)), 1)
    # Conservative usable image region after header, caption, panel padding.
    slot_w = 1740 if count == 1 else (850 if count == 2 else 550)
    slot_h = 610 if count == 1 else 500
    return round(min(slot_w / required_w, slot_h / required_h), 3)


def _apply_feasibility_fallback(task: Any, decision: dict[str, Any]) -> None:
    selected = decision["selected_figures"]
    analyses = decision["figure_analysis"]
    original_count = len(selected)
    for item in selected:
        item["predicted_slot_feasibility"] = _feasibility(analyses[item["figure_id"]], original_count)

    infeasible = [item for item in selected if item["predicted_slot_feasibility"] < 0.75]
    if not infeasible:
        decision["feasibility_fallback"] = {"applied": False, "reason": "all_selected_figures_feasible"}
        return

    # Give the highest-value difficult figure a full-width slot, but only if
    # it can become reasonably legible there. Otherwise retain the best already
    # feasible figure and reject impossible portrait assets.
    difficult_best = max(infeasible, key=lambda item: item["score"])
    full_width_score = _feasibility(analyses[difficult_best["figure_id"]], 1)
    feasible_existing = [item for item in selected if item not in infeasible]
    if full_width_score >= 0.75:
        keep = [difficult_best]
        reason = "promote_difficult_high_value_figure_to_full_width"
    elif feasible_existing:
        keep = [max(feasible_existing, key=lambda item: item["score"])]
        reason = "reject_impossible_figure_keep_best_feasible"
    else:
        keep = [max(selected, key=lambda item: (_feasibility(analyses[item["figure_id"]], 1), item["score"]))]
        reason = "no_feasible_candidate_keep_least_bad"

    keep_ids = {item["figure_id"] for item in keep}
    dropped = []
    for panel in task.panels:
        if panel.figure_id and panel.figure_id not in keep_ids:
            dropped.append({"panel": panel.section, "figure_id": panel.figure_id, "reason": reason})
            panel.figure_id, panel.figure, panel.layout_hint = "", None, "text_only"
    decision["suppressed_figures"].extend(dropped)
    decision["selected_figures"] = keep
    decision["figure_count"] = len(keep)
    decision["budget_spent"] = round(sum(item["budget_cost"] for item in keep), 2)
    decision["feasibility_fallback"] = {
        "applied": True,
        "reason": reason,
        "original_count": original_count,
        "final_count": len(keep),
        "full_width_feasibility": full_width_score,
        "dropped": dropped,
    }
    # A single difficult hero benefits from the dashboard's 8-row body grid.
    task.template = "template_dashboard"
    decision["render_template"] = task.template


def _apply_bullet_budget(task: Any) -> list[dict[str, Any]]:
    log = []
    for panel in task.panels:
        if panel.figure_id or panel.figure:
            continue
        old = list(panel.content or [])
        panel.content = [ppt_renderer.clean_text(item, MAX_BULLET_CHARS) for item in old[:MAX_TEXT_BULLETS]]
        if old != panel.content:
            log.append({
                "panel": panel.section,
                "before_count": len(old),
                "after_count": len(panel.content),
                "truncated_count": max(0, len(old) - len(panel.content)),
            })
    return log


def _apply_single_hero_panel_budget(task: Any, decision: dict[str, Any]) -> dict[str, Any]:
    if decision["figure_count"] != 1 or len(task.panels) <= 5:
        return {"applied": False, "removed": []}
    hero_id = decision["selected_figures"][0]["figure_id"]
    hero_panel = next(panel for panel in task.panels if panel.figure_id == hero_id)
    hero_family = decision["selected_figures"][0]["family"]
    if hero_family == "method":
        tokens = ["motivation", "problem", "result", "finding", "conclusion"]
    else:
        tokens = ["motivation", "problem", "method", "framework", "conclusion"]
    candidates = [panel for panel in task.panels if panel is not hero_panel]

    def rank(panel: Any) -> tuple[int, int]:
        section = (panel.section or "").lower()
        hit = next((i for i, token in enumerate(tokens) if token in section), len(tokens) + 1)
        return hit, task.panels.index(panel)

    keep_text = sorted(candidates, key=rank)[:4]
    keep_ids = {id(hero_panel), *(id(panel) for panel in keep_text)}
    removed = [panel.section for panel in task.panels if id(panel) not in keep_ids]
    task.panels = [panel for panel in task.panels if id(panel) in keep_ids]
    return {"applied": True, "max_total_panels": 5, "removed": removed}


def _v04_spans(original: Any, hero_ids: set[str]):
    adaptive = _adaptive_spans(original, hero_ids)

    def spans(grid: Any, panels: list[Any]) -> list[dict[str, int]]:
        heroes = [i for i, panel in enumerate(panels) if panel.figure_id in hero_ids]
        others = [i for i in range(len(panels)) if i not in heroes]
        if len(heroes) != 1 or len(panels) < 4 or grid.rows < 7:
            return adaptive(grid, panels)
        boxes: list[dict[str, int] | None] = [None] * len(panels)
        top_rows = 2
        widths = ppt_renderer._alloc_units(grid.cols, [1.0] * len(others), min_each=2)
        col = 0
        for index, width in zip(others, widths):
            boxes[index] = grid.box(col, 0, width, top_rows)
            col += width
        boxes[heroes[0]] = grid.box(0, top_rows, grid.cols, grid.rows - top_rows)
        return [box for box in boxes if box is not None]

    return spans


def _prepare(run_dir: Path, asset_dir: Path) -> tuple[Any, dict[str, Any]]:
    task, decision = prepare_layout(run_dir, asset_dir)
    decision["prototype_version"] = "r2-v0.4"
    _apply_feasibility_fallback(task, decision)
    decision["single_hero_panel_budget"] = _apply_single_hero_panel_budget(task, decision)
    decision["bullet_budget"] = {
        "max_text_panel_bullets": MAX_TEXT_BULLETS,
        "max_bullet_chars": MAX_BULLET_CHARS,
        "changes": _apply_bullet_budget(task),
    }
    return task, decision


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
    ppt_renderer.content_spans = _v04_spans(original_spans, hero_ids)
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
        rows = [row for row in labels if row["run_folder"] in wanted]
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
