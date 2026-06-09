"""Audit v2 (new60) — freeze the annotation sample and emit the annotation kit.

Self-contained on purpose: it reads the frozen ``20260609_*`` run batch under
``outputs/runs/`` directly (the deduped 60-paper sample) and records, per paper,
the **real PPTX render** ``pptx/iter_1.png`` (never the misleading PIL preview).

Outputs
-------
* ``datasets/gold/audit_v2_manifest.json`` — one row per paper (run_folder,
  title, title_norm, template, iter1_png, iter1_sha256).
* ``datasets/gold/audit_v2_annotation_sheet.csv`` — blank annotation sheet
  (one row per paper, empty label columns) used to derive per-annotator copies.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

REPO = Path(__file__).resolve().parents[2]  # .../PosterCS
DEFAULT_RUNS_DIR = REPO / "outputs" / "runs"
BATCH_GLOB = "20260609_*"  # the frozen new-pipeline batch (audit v2 sample)


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().upper())


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def build_manifest(runs_dir: Optional[Path] = None) -> List[Dict]:
    """Return one deduped row per paper for the frozen batch (sorted, stable)."""
    runs_dir = Path(runs_dir or DEFAULT_RUNS_DIR)
    seen: Dict[str, bool] = {}
    rows: List[Dict] = []
    for d in sorted(runs_dir.glob(BATCH_GLOB)):
        report = d / "run_report.json"
        png = d / "pptx" / "iter_1.png"
        if not report.exists() or not png.exists():
            continue
        try:
            inp = json.loads(report.read_text(encoding="utf-8")).get("input", {})
        except Exception:
            continue
        title = inp.get("poster_title", "")
        key = _norm(title)
        if key in seen:  # belt-and-suspenders dedupe (sample is already deduped)
            continue
        seen[key] = True
        rows.append({
            "run_folder": d.name,
            "title": title,
            "title_norm": key,
            "template": inp.get("template", "?"),
            "iter1_png": str(png),
            "iter1_sha256": _sha(png),
        })
    return rows


def write_manifest(out: Optional[Path] = None) -> Path:
    out = Path(out or REPO / "datasets" / "gold" / "audit_v2_manifest.json")
    rows = build_manifest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


ANNOTATION_COLS = [
    "run_folder", "title", "template", "iter1_png",
    "primary_issue", "secondary_issues", "other_description",
    "guard_notes", "confidence", "free_notes",
]


def write_annotation_kit(out_csv: Optional[Path] = None) -> Path:
    out_csv = Path(out_csv or REPO / "datasets" / "gold" / "audit_v2_annotation_sheet.csv")
    manifest = REPO / "datasets" / "gold" / "audit_v2_manifest.json"
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ANNOTATION_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({
                "run_folder": r["run_folder"], "title": r["title"],
                "template": r["template"], "iter1_png": r["iter1_png"],
            })
    return out_csv


if __name__ == "__main__":  # pragma: no cover
    print("manifest:", write_manifest())
    print("sheet:", write_annotation_kit())
