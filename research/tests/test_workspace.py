import hashlib
import json
from pathlib import Path

import yaml

from postercs_audit.paths import CONFIG_ROOT, DATA_ROOT, RESEARCH_ROOT
from postercs_audit.rules.runtime import evaluate_row


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_portable_manifests_are_complete_and_hash_valid():
    expected = {"formal": 88, "controlled": 48, "external": 20}
    for dataset, count in expected.items():
        manifest = json.loads((DATA_ROOT / dataset / "manifest.json").read_text())
        assert len(manifest["records"]) == count
        assert len({row["sample_id"] for row in manifest["records"]}) == count
        for row in manifest["records"]:
            path = RESEARCH_ROOT / row["image_path"]
            assert path.is_file()
            assert sha256_file(path) == row["sha256"]


def test_run_configs_use_portable_manifests():
    for name in ("formal", "controlled-gemini", "controlled-qwen", "external-gemini", "external-qwen"):
        path = CONFIG_ROOT / f"{name}.yaml"
        config = yaml.safe_load(path.read_text())
        manifest = (path.parent / config["dataset_manifest"]).resolve()
        assert manifest.is_relative_to(RESEARCH_ROOT)
        assert manifest.is_file()


def test_frozen_rules_load_and_evaluate_without_historical_paths():
    config = json.loads((CONFIG_ROOT / "audit" / "rules.json").read_text())
    results = evaluate_row({}, config)
    assert results
    assert {row["label"] for row in results}
