#!/usr/bin/env python3
"""Build portable manifests and materialize the frozen poster images.

The source manifests record the original experiment paths. This script keeps
them as provenance, then creates canonical manifests whose image paths are
relative to ``research/`` and therefore independent of the historical layout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any


RESEARCH_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = RESEARCH_ROOT.parent
DEFAULT_LEGACY_ROOT = REPOSITORY_ROOT / "archive" / "research-history-2026-10-10"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    return path.resolve().relative_to(RESEARCH_ROOT).as_posix()


def index_pngs(roots: list[Path]) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = defaultdict(list)
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.png"):
            result[sha256_file(path)].append(path)
    return result


def materialize_formal(legacy_root: Path) -> None:
    data_dir = RESEARCH_ROOT / "data" / "formal"
    source = read_json(data_dir / "source-manifest.json")
    output_dir = data_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = index_pngs([
        data_dir / "natural",
        data_dir / "controlled",
        legacy_root / "05_formal_experiment",
        REPOSITORY_ROOT / "outputs" / "runs",
    ])

    records = []
    by_sample: dict[str, str] = {}
    for record in source["records"]:
        expected = record["sha256"]
        matches = candidates.get(expected, [])
        if not matches:
            raise FileNotFoundError(f"no frozen image matches {record['sample_id']} ({expected})")
        target = output_dir / f"{record['sample_id']}.png"
        if not target.exists() or sha256_file(target) != expected:
            shutil.copy2(matches[0], target)
        copied = dict(record)
        copied["image_path"] = relative(target)
        records.append(copied)
        by_sample[record["sample_id"]] = copied["image_path"]

    manifest = {key: value for key, value in source.items() if key != "records"}
    manifest.update(status="portable_frozen", records=records)
    write_json(data_dir / "manifest.json", manifest)

    gold_path = data_dir / "gold.csv"
    with gold_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames or []
    for row in rows:
        row["image_path"] = by_sample[row["sample_id"]]
    with gold_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def rewrite_manifest(dataset: str, image_for_record) -> None:
    data_dir = RESEARCH_ROOT / "data" / dataset
    source = read_json(data_dir / "source-manifest.json")
    records = []
    for record in source["records"]:
        target = image_for_record(data_dir, record)
        if not target.is_file():
            raise FileNotFoundError(target)
        actual = sha256_file(target)
        if actual != record["sha256"]:
            raise ValueError(f"hash mismatch for {record['sample_id']}: {target}")
        copied = dict(record)
        copied["image_path"] = relative(target)
        records.append(copied)
    manifest = {key: value for key, value in source.items() if key != "records"}
    manifest["records"] = records
    write_json(data_dir / "manifest.json", manifest)


def rewrite_embedded_paths(path: Path, replacements: dict[str, str]) -> None:
    """Replace only path strings while preserving all measured values."""
    text = path.read_text(encoding="utf-8")
    updated = text
    for old, new in replacements.items():
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def make_operational_tables_portable() -> None:
    old_root = "/Users/mikaelsnow/Documents/ECNU/Paper_Comment_Poster/PosterCS/audit_v2_rewrite"
    rule_root = RESEARCH_ROOT / "data" / "rule-development"
    controlled_root = RESEARCH_ROOT / "data" / "controlled"
    replacements = {
        f"{old_root}/08_rule_hybrid_repair/04_ruledev72/assets": "data/rule-development/pairs",
        f"{old_root}/08_rule_hybrid_repair/06_hybrid_test68/controlled48/assets": "data/controlled/pairs",
    }
    paths = [
        *(rule_root.glob("*.csv")),
        *(rule_root.glob("*.json")),
        *(rule_root.joinpath("features").glob("*.csv")),
        *(controlled_root.glob("*.csv")),
        *(controlled_root.glob("*.json")),
        *(controlled_root.joinpath("features").glob("*.csv")),
    ]
    for path in paths:
        # Source/freeze manifests intentionally preserve original provenance.
        if path.name in {"source-manifest.json", "freeze-manifest.json"}:
            continue
        rewrite_embedded_paths(path, replacements)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", type=Path, default=DEFAULT_LEGACY_ROOT)
    args = parser.parse_args()

    materialize_formal(args.legacy_root.expanduser().resolve())
    rewrite_manifest(
        "controlled",
        lambda root, row: root / "pairs" / row["pair_id"] / f"{row['variant']}.png",
    )
    rewrite_manifest(
        "external",
        lambda root, row: root / "images" / f"{row['sample_id']}.png",
    )
    make_operational_tables_portable()
    print("materialized: formal=88, controlled=48, external=20")


if __name__ == "__main__":
    main()
