#!/usr/bin/env python3
"""R2 v0.6: accepted v0.5 semantics with portrait figures routed right."""

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
from postercs_audit.renderer.budget import _apply_bullet_budget


OUTPUT = RUNS_ROOT / "renderer"


def _portrait_ids(decision: dict[str, Any]) -> set[str]:
    ids = set()
    for item in decision["selected_figures"]:
        metrics = decision["figure_analysis"][item["figure_id"]]
        aspect = float(metrics["source_width_px"]) / max(float(metrics["source_height_px"]), 1)
        if aspect < 0.85:
            ids.add(item["figure_id"])
    return ids


def _prepare(run_dir: Path, asset_dir: Path) -> tuple[Any, dict[str, Any]]:
    task, decision = prepare_layout(run_dir, asset_dir)
    decision["prototype_version"] = "r2-v0.6"
    portraits = _portrait_ids(decision)
    removed = []
    # The portrait layout has six slots. Remove only a redundant general/
    # overview panel when a seven-panel plan would otherwise overflow.
    if len(decision["selected_figures"]) == 2 and len(portraits) == 1 and len(task.panels) > 6:
        for panel in reversed(task.panels):
            if ppt_renderer.classify_panel(panel.section) == "general":
                removed.append(panel.section)
                task.panels.remove(panel)
                break
    decision["portrait_routing"] = {
        "applied": len(decision["selected_figures"]) == 2 and len(portraits) == 1 and len(task.panels) == 6,
        "portrait_figure_ids": sorted(portraits),
        "removed_redundant_panels": removed,
    }
    decision["bullet_budget"] = {
        "max_text_panel_bullets": 3,
        "max_bullet_chars": 105,
        "changes": _apply_bullet_budget(task),
    }
    return task, decision


def _portrait_spans(original: Any, hero_ids: set[str], portrait_ids: set[str]):
    adaptive = _adaptive_spans(original, hero_ids)

    def spans(grid: Any, panels: list[Any]) -> list[dict[str, int]]:
        portrait = [i for i, panel in enumerate(panels) if panel.figure_id in portrait_ids]
        landscape = [i for i, panel in enumerate(panels) if panel.figure_id in hero_ids and panel.figure_id not in portrait_ids]
        others = [i for i in range(len(panels)) if i not in portrait and i not in landscape]
        if len(panels) != 6 or len(portrait) != 1 or len(landscape) != 1 or len(others) != 4:
            return adaptive(grid, panels)
        boxes: list[dict[str, int] | None] = [None] * len(panels)
        # Keep the tall supporting figure on the right so the reading path
        # starts with text and the portrait asset does not dominate the lead.
        boxes[portrait[0]] = grid.box(8, 0, 4, grid.rows)
        # Four concise semantic panels in a 2x2 block on the upper left.
        split = max(2, grid.rows // 2)
        for pos, index in enumerate(others):
            col = (pos % 2) * 4
            row = (pos // 2) * (split // 2)
            boxes[index] = grid.box(col, row, 4, split // 2)
        boxes[landscape[0]] = grid.box(0, split, 8, grid.rows - split)
        return [box for box in boxes if box is not None]

    return spans


def _semantic_panel_renderer(original: Any):
    def render(slide: Any, x: Any, y: Any, w: Any, h: Any, panel: Any, task: Any, palette: Any, idx: int):
        figure_source, _ = ppt_renderer.get_panel_figure(panel, task)
        kind = ppt_renderer.classify_panel(panel.section)
        if figure_source or kind not in {"method", "benchmark", "results", "takeaway"}:
            return original(slide, x, y, w, h, panel, task, palette, idx)

        accent = ppt_renderer.panel_accent(panel.section, palette)
        ppt_renderer.add_rect(slide, x, y, w, h, palette.panel_bg, palette.border, radius=True, line_width=0.8)
        ppt_renderer.add_panel_header(slide, x, y, w, panel.section, idx, palette, accent)
        cx, cy = x + ppt_renderer.Inches(0.13), y + ppt_renderer.Inches(0.44)
        cw, ch = w - ppt_renderer.Inches(0.26), h - ppt_renderer.Inches(0.56)
        if panel.headline:
            ppt_renderer._add_headline(slide, cx, cy, cw, ppt_renderer.Inches(0.28), panel.headline, palette, accent)
            cy += ppt_renderer.Inches(0.31)
            ch -= ppt_renderer.Inches(0.31)
        items = list(panel.content or [])[:3]
        if not items:
            items = ["Key information"]

        if kind == "method":
            # Process cards replace numbered prose bullets.
            gap = ppt_renderer.Inches(0.06)
            horizontal = w >= ppt_renderer.Inches(4.6)
            for pos, text in enumerate(items):
                if horizontal:
                    card_w = (cw - gap * (len(items) - 1)) / len(items)
                    bx, by, bw, bh = cx + pos * (card_w + gap), cy, card_w, ch
                else:
                    card_h = (ch - gap * (len(items) - 1)) / len(items)
                    bx, by, bw, bh = cx, cy + pos * (card_h + gap), cw, card_h
                ppt_renderer.add_rect(slide, bx, by, bw, bh, palette.soft, palette.border, radius=True, line_width=0.6)
                ppt_renderer.add_textbox(slide, bx + ppt_renderer.Inches(0.05), by + ppt_renderer.Inches(0.04), ppt_renderer.Inches(0.22), ppt_renderer.Inches(0.18), f"{pos + 1}", 8.5, accent, True, ppt_renderer.PP_ALIGN.CENTER)
                ppt_renderer.add_textbox(slide, bx + ppt_renderer.Inches(0.08), by + ppt_renderer.Inches(0.25), bw - ppt_renderer.Inches(0.16), bh - ppt_renderer.Inches(0.30), ppt_renderer.clean_text(text, 82), 8.4, palette.text, pos == 0, fit=True, min_font_size=6.8)
        elif kind in {"benchmark", "results"} and ppt_renderer.extract_metrics(panel):
            metrics = ppt_renderer.extract_metrics(panel)
            ppt_renderer.add_metric_pills(slide, cx, metrics=metrics, y=cy, w=cw, palette=palette, accent=accent)
            summary_y = cy + ppt_renderer.Inches(0.38)
            ppt_renderer.add_textbox(slide, cx, summary_y, cw, max(ppt_renderer.Inches(0.28), ch - ppt_renderer.Inches(0.38)), ppt_renderer.clean_text(items[0], 105), 9.2, palette.text, True, fit=True, min_font_size=7.0)
        else:
            # Evidence/takeaway cards remove repeated numbered dots while
            # preserving two or three distinct claims.
            gap = ppt_renderer.Inches(0.06)
            card_h = (ch - gap * (len(items) - 1)) / len(items)
            fills = [palette.soft, palette.panel_bg, palette.soft]
            for pos, text in enumerate(items):
                by = cy + pos * (card_h + gap)
                ppt_renderer.add_rect(slide, cx, by, cw, card_h, fills[pos % len(fills)], palette.border, radius=True, line_width=0.6)
                ppt_renderer.add_rect(slide, cx, by, ppt_renderer.Inches(0.05), card_h, accent, radius=False)
                ppt_renderer.add_textbox(slide, cx + ppt_renderer.Inches(0.12), by + ppt_renderer.Inches(0.05), cw - ppt_renderer.Inches(0.18), card_h - ppt_renderer.Inches(0.10), ppt_renderer.clean_text(text, 100), 8.8, palette.text, pos == 0, fit=True, min_font_size=6.8)
    return render


def render_one(row: dict[str, str], output_root: Path) -> dict[str, Any]:
    run_dir = ROOT / "outputs" / "runs" / row["run_folder"]
    target = output_root / row["run_folder"]
    target.mkdir(parents=True, exist_ok=True)
    before = Path(row["iter1_png"])
    if before.exists():
        shutil.copy2(before, target / "before.png")
    task, decision = _prepare(run_dir, target / "prepared_assets")
    hero_ids = {item["figure_id"] for item in decision["selected_figures"]}
    portrait_ids = set(decision["portrait_routing"]["portrait_figure_ids"])
    original_spans = ppt_renderer.content_spans
    original_panel = ppt_renderer.add_panel_content
    ppt_renderer.content_spans = _portrait_spans(original_spans, hero_ids, portrait_ids)
    ppt_renderer.add_panel_content = _semantic_panel_renderer(original_panel)
    try:
        result = ppt_renderer.generate_dashboard_pptx(task)
    finally:
        ppt_renderer.content_spans = original_spans
        ppt_renderer.add_panel_content = original_panel
    pptx_path = target / "after.pptx"
    pptx_path.write_bytes(result.getvalue())
    rendered = render_pptx_to_png(pptx_path, target)
    geometry = summarize(pptx_path)
    decision["quality_gate"] = _gate(task, geometry, decision)
    decision["semantic_panel_types"] = ["method_process", "result_metrics", "evidence_cards", "takeaway_cards"]
    decision.update({"run_folder": row["run_folder"], "after_png": str(rendered) if rendered else ""})
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
