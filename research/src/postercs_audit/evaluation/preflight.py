from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from postercs_audit.evaluation.core import ISSUE_LABELS, sha256_file


EVALUATION_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight the frozen Formal-88 scoring inputs.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parsed_count(run_dir: Path) -> int:
    return sum(1 for _ in (run_dir / "parsed").rglob("*.json"))


def preflight(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    paths = {key: resolve(config_path, value) for key, value in config["inputs"].items()}
    hashes = {
        "gold": sha256_file(paths["gold"]),
        "natural_pair_key": sha256_file(paths["natural_pair_key"]),
        "controlled_pair_key": sha256_file(paths["controlled_pair_key"]),
        "prediction_schema": sha256_file(paths["prediction_schema"]),
        "main_run_manifest": sha256_file(paths["main_run"] / "run_manifest.json"),
        "supplement_run_manifest": sha256_file(paths["supplement_run"] / "run_manifest.json"),
    }
    mismatches = {
        key: {"expected": config["sha256"][key], "actual": value}
        for key, value in hashes.items()
        if config["sha256"].get(key) != value
    }
    with paths["gold"].open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        gold_rows = list(reader)
        gold_columns = reader.fieldnames or []
    required_columns = {"sample_id", "dataset", "primary_issue", "issues_json", "gold_source"}
    main_manifest = json.loads((paths["main_run"] / "run_manifest.json").read_text(encoding="utf-8"))
    supplement_manifest = json.loads((paths["supplement_run"] / "run_manifest.json").read_text(encoding="utf-8"))
    return {
        "mode": "preflight_only_no_scores",
        "config_version": config["version"],
        "labels_match": tuple(config["labels"]) == ISSUE_LABELS,
        "hash_mismatches": mismatches,
        "gold_rows": len(gold_rows),
        "gold_columns_present": required_columns.issubset(gold_columns),
        "main_parsed_files": parsed_count(paths["main_run"]),
        "supplement_parsed_files": parsed_count(paths["supplement_run"]),
        "main_gold_loaded": main_manifest.get("gold_loaded"),
        "supplement_gold_loaded": supplement_manifest.get("gold_loaded"),
        "planned_tasks": config["expected"]["tasks"],
        "formal_scores_computed": False,
    }


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        raise SystemExit("formal scoring is gated: this phase only supports --dry-run")
    report = preflight(args.config.expanduser().resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    failures = bool(report["hash_mismatches"]) or not report["labels_match"] or not report["gold_columns_present"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
