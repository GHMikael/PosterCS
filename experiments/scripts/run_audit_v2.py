"""Phase 3 driver: run the VLM labeler (direct + narrowed) + geom rules over the frozen new60.

Reads ``datasets/gold/audit_v2_manifest.json`` and, for each poster's real
``iter_1.png``:
  * runs the VLM labeler under each prompt variant (direct, narrowed);
  * runs the deterministic geom rules (overlap on the .pptx, contrast by theme).

Writes ``experiments/results/audit_v2_new60/{vlm_qwen32b_<variant>.json, geom_rules.json}``.
VLM results are saved incrementally (after every poster) so a crash mid-batch
does not lose progress. ``label_poster`` never raises (returns a stub with a
``source`` flag), so the batch always runs to completion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import QWEN_VL_MODEL
from experiments.audit.vlm_labeler import label_poster
from experiments.audit.geom_rules import overlap_violations, theme_contrast

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "datasets" / "gold" / "audit_v2_manifest.json"
OUTDIR = REPO / "experiments" / "results" / "audit_v2_new60"


def _color_theme(run_folder: str) -> str:
    rep = REPO / "outputs" / "runs" / run_folder / "run_report.json"
    try:
        return json.loads(rep.read_text(encoding="utf-8"))["input"].get("color_theme", "?")
    except Exception:
        return "?"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Audit v2 VLM batch + geom rules over new60.")
    p.add_argument("--model", default=QWEN_VL_MODEL)
    p.add_argument("--variants", default="direct,narrowed")
    p.add_argument("--limit", type=int, default=0, help="0 = all")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.limit:
        rows = rows[: args.limit]
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    print(f"[run_audit_v2] {len(rows)} posters × variants={variants} model={args.model}", flush=True)

    if args.dry_run:
        for r in rows:
            print("  would label:", r["run_folder"])
        print("[dry-run] no VLM calls made.", flush=True)
        return 0

    OUTDIR.mkdir(parents=True, exist_ok=True)

    # 1) deterministic geom rules (cheap) — once per poster.
    geom = []
    for r in rows:
        pptx = Path(r["iter1_png"].replace("iter_1.png", "iter_1.pptx"))
        theme = _color_theme(r["run_folder"])
        ov = overlap_violations(pptx) if pptx.exists() else None
        geom.append({
            "run_folder": r["run_folder"], "template": r["template"], "color_theme": theme,
            "overlap_count": (len(ov) if ov is not None else None),
            "contrast": theme_contrast(theme),
        })
    (OUTDIR / "geom_rules.json").write_text(json.dumps(geom, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[run_audit_v2] geom_rules.json written ({len(geom)} posters)", flush=True)

    # 2) VLM labeling per variant (incremental save).
    for v in variants:
        out = []
        for i, r in enumerate(rows, 1):
            lab = label_poster(Path(r["iter1_png"]), model=args.model, run_id=r["run_folder"], variant=v)
            lab["template"] = r["template"]
            out.append(lab)
            (OUTDIR / f"vlm_qwen32b_{v}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  [{v} {i}/{len(rows)}] {r['run_folder'][:36]:36s} -> "
                  f"{lab.get('primary_issue'):24s} ({lab.get('source')})", flush=True)
        print(f"[run_audit_v2] vlm_qwen32b_{v}.json done ({len(out)} labels)", flush=True)

    print("[run_audit_v2] DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
