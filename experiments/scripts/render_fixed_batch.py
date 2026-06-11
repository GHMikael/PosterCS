#!/usr/bin/env python3
"""Overnight batch: re-render all 60 posters with P1 fixes applied.
Saves to outputs/runs_fixed/{run_name}/ (separate from original outputs/runs/).

Usage:
    unset VIRTUAL_ENV && PYTHONPATH=. .venv/bin/python experiments/scripts/render_fixed_batch.py
    unset VIRTUAL_ENV && PYTHONPATH=. .venv/bin/python experiments/scripts/render_fixed_batch.py --limit 5  # smoke test
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "datasets" / "gold" / "audit_v2_manifest.json"
RUNS_DIR = REPO / "outputs" / "runs"
OUT_DIR = REPO / "outputs" / "runs_fixed"


def render_one(run_name: str) -> dict:
    """Re-render a single run with fixed ppt_renderer. Returns status dict."""
    run_dir = RUNS_DIR / run_name
    report_path = run_dir / "run_report.json"
    if not report_path.exists():
        return {"run_name": run_name, "ok": False, "error": "no run_report.json"}

    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        task_snap = data["iterations"][-1]["task_snapshot"]

        from app.models import PosterTask
        from app.ppt_renderer import generate_dashboard_pptx
        from app.feedback_loop import render_pptx_to_png

        task = PosterTask.model_validate(task_snap)

        buf = generate_dashboard_pptx(task)

        out_dir = OUT_DIR / run_name / "pptx"
        out_dir.mkdir(parents=True, exist_ok=True)

        pptx_path = out_dir / "iter_1.pptx"
        pptx_path.write_bytes(buf.getvalue())

        # Also generate PNG for visual check
        png_path = render_pptx_to_png(pptx_path, out_dir)

        return {
            "run_name": run_name,
            "ok": True,
            "template": task.template,
            "pptx_size": len(buf.getvalue()),
            "png": str(png_path) if png_path else None,
        }
    except Exception as exc:
        return {"run_name": run_name, "ok": False, "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description="Re-render all 60 posters with P1 fixes")
    parser.add_argument("--limit", type=int, default=0, help="Limit to N posters (0=all)")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between renders (seconds)")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    run_names = [e["run_folder"].split("/")[-1] for e in manifest]

    if args.limit:
        run_names = run_names[: args.limit]

    print(f"[render_fixed] Re-rendering {len(run_names)} posters → {OUT_DIR}")
    print(f"[render_fixed] Start: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    ok = fail = 0
    results = []

    for i, run_name in enumerate(run_names, start=1):
        print(f"  [{i}/{len(run_names)}] {run_name[:60]}...", end=" ", flush=True)
        result = render_one(run_name)
        results.append(result)
        if result["ok"]:
            ok += 1
            print(f"OK ({result.get('template', '?')})")
        else:
            fail += 1
            print(f"FAIL: {result.get('error', '?')}")

        if i < len(run_names):
            time.sleep(args.delay)

    # Write summary
    summary = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(run_names),
        "ok": ok,
        "fail": fail,
        "results": results,
    }
    summary_path = OUT_DIR / "render_fixed_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[render_fixed] Done: {ok} OK, {fail} FAIL")
    print(f"[render_fixed] Output: {OUT_DIR}")
    print(f"[render_fixed] Summary: {summary_path}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
