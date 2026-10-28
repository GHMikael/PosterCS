#!/usr/bin/env python3
"""Extract T8-A continuous features for the frozen 30-sample development set."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import pytesseract

from postercs_audit.features.core import (
    BODY_BOTTOM_RATIO, BODY_TOP_RATIO, FEATURE_VERSION, GRID_BLANK_OCCUPANCY,
    extract_raster, extract_source,
)


HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def process(row: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    identity = {k: row[k] for k in ("dataset", "dataset_row", "sample_id", "pair_id", "variant", "image_path", "pptx_path")}
    raster, raster_regions = extract_raster(row["image_path"])
    source, source_regions = extract_source(row["pptx_path"] or None)
    feature_row = {**identity, "feature_version": FEATURE_VERSION, **raster, **source}
    for region in raster_regions:
        region.update({"dataset": row["dataset"], "sample_id": row["sample_id"], "image_path": row["image_path"]})
    for region in source_regions:
        region.update({"dataset": row["dataset"], "sample_id": row["sample_id"], "pptx_path": row["pptx_path"]})
    return feature_row, raster_regions, source_regions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not args.manifest.exists():
        raise FileNotFoundError(args.manifest)
    with args.manifest.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    feature_rows: list[dict[str, Any]] = []
    raster_regions: list[dict[str, Any]] = []
    source_regions: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(process, row): row for row in rows}
        for done, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            feature, rr, sr = future.result()
            feature_rows.append(feature)
            raster_regions.extend(rr)
            source_regions.extend(sr)
            print(f"[{done}/{len(rows)}] {row['dataset']} {row['sample_id']}", flush=True)
    order = {(r["dataset"], r["sample_id"]): i for i, r in enumerate(rows)}
    feature_rows.sort(key=lambda r: order[(r["dataset"], r["sample_id"])])
    raster_regions.sort(key=lambda r: (order[(r["dataset"], r["sample_id"])], r.get("y_norm", 0), r.get("x_norm", 0)))
    source_regions.sort(key=lambda r: (order[(r["dataset"], r["sample_id"])], r.get("shape_index", 0)))
    features_path = args.output_dir / "poster_features.csv"
    raster_path = args.output_dir / "raster_regions.csv"
    source_path = args.output_dir / "source_regions.csv"
    write_csv(features_path, feature_rows)
    write_csv(raster_path, raster_regions)
    write_csv(source_path, source_regions)
    outputs = [features_path, raster_path, source_path]
    run_manifest = {
        "feature_version": FEATURE_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "T8-A continuous feature extraction; no labels and no defect thresholds",
        "development_datasets": ["pilot20", "calibration10"],
        "formal88_used": False,
        "sample_count": len(rows),
        "settings": {"grid_rows": 4, "grid_cols": 8, "grid_blank_occupancy_preprocessing_cutoff": GRID_BLANK_OCCUPANCY,
                     "body_top_ratio": BODY_TOP_RATIO, "body_bottom_ratio": BODY_BOTTOM_RATIO,
                     "ocr_config": "tesseract --psm 11", "workers": args.workers},
        "runtime": {"python": platform.python_version(), "opencv": cv2.__version__,
                    "tesseract": str(pytesseract.get_tesseract_version()).splitlines()[0]},
        "input_manifest": {"path": str(args.manifest.resolve()), "sha256": sha256(args.manifest)},
        "implementation": {
            path.name: {"path": str(path.resolve()), "sha256": sha256(path)}
            for path in (HERE / "core.py", Path(__file__))
        },
        "outputs": {p.name: {"path": str(p.resolve()), "sha256": sha256(p)} for p in outputs},
    }
    manifest_path = args.output_dir / "feature_run_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {features_path} ({len(feature_rows)} posters)")


if __name__ == "__main__":
    main()
