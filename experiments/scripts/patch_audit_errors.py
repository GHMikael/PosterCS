"""Targeted re-run: patch missing/errored VLM labels back into each variant JSON.

Reads each vlm_qwen32b_<variant>.json, finds records with source != "vlm" (or
missing run_ids from the manifest), re-labels just those with label_poster,
and writes the patched JSON back (preserving all already-good labels).

Usage:
    python -m experiments.scripts.patch_audit_errors [--variants V1,V2]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.config import QWEN_VL_MODEL
from experiments.audit.vlm_labeler import label_poster

RETRIES = 3          # retry on transport errors (transient network)
RETRY_SLEEP = 5.0    # seconds between retries

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "datasets" / "gold" / "audit_v2_manifest.json"
OUTDIR = REPO / "experiments" / "results" / "audit_v2_new60"


def _load_manifest_index() -> list[dict]:
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    # index by run_folder for quick lookup of iter1_png + template
    return rows


def patch_variant(variant: str, rows: list[dict]) -> int:
    out_path = OUTDIR / f"vlm_qwen32b_{variant}.json"
    existing = {r["run_id"]: r for r in json.loads(out_path.read_text(encoding="utf-8"))}
    manifest_by_id = {r["run_folder"]: r for r in rows}

    # run_ids needing fix: in manifest but missing from existing, or present but source != vlm
    all_ids = [r["run_folder"] for r in rows]
    need = [rid for rid in all_ids if rid not in existing or existing[rid].get("source") != "vlm"]
    if not need:
        print(f"[patch:{variant}] nothing to do ({len(existing)} ok).", flush=True)
        return 0
    print(f"[patch:{variant}] re-running {len(need)} posters …", flush=True)

    fixed = 0
    for i, rid in enumerate(need, 1):
        m = manifest_by_id[rid]
        # Retry on transport errors — transient network flakiness should not
        # leave a poster permanently errored. Label semantics are unchanged.
        lab = None
        for attempt in range(1, RETRIES + 1):
            lab = label_poster(Path(m["iter1_png"]), model=QWEN_VL_MODEL, run_id=rid, variant=variant)
            if lab.get("source") == "vlm":
                break
            # vlm_error / vlm_unparsed → back off and retry (parse errors are rare)
            if attempt < RETRIES:
                time.sleep(RETRY_SLEEP)
        lab["template"] = m["template"]
        existing[rid] = lab
        # incremental save
        ordered = [existing[r["run_folder"]] for r in rows if r["run_folder"] in existing]
        out_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
        ok = lab.get("source") == "vlm"
        fixed += 1 if ok else 0
        print(f"  [{variant} {i}/{len(need)}] {rid[:36]:36s} -> {lab.get('primary_issue'):24s} "
              f"({'OK' if ok else lab.get('source')})", flush=True)
    print(f"[patch:{variant}] recovered {fixed}/{len(need)}", flush=True)
    return len(need) - fixed  # remaining errors


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Patch errored/missing VLM audit labels.")
    p.add_argument("--variants", default="describe_classify,grounded,narrowed")
    args = p.parse_args(argv)
    rows = _load_manifest_index()
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    remaining = 0
    for v in variants:
        remaining += patch_variant(v, rows)
    print(f"[patch] DONE. remaining errors across patched variants: {remaining}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
