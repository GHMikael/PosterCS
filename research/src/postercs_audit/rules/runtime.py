#!/usr/bin/env python3
"""Runtime evaluator for the frozen rule_v1 configuration."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from postercs_audit.paths import CONFIG_ROOT


HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = CONFIG_ROOT / "audit" / "rules.json"


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _applicable(row: Mapping[str, Any], gate: Mapping[str, Any] | None) -> bool:
    if not gate:
        return True
    for key, threshold in gate.items():
        feature, op = key.rsplit("__", 1)
        value = _number(row.get(feature))
        if value is None:
            return False
        if op == "min" and value < float(threshold):
            return False
    return True


def evaluate_rule(rule_id: str, rule: Mapping[str, Any], row: Mapping[str, Any], version: str = "rule_v1") -> dict[str, Any]:
    features = tuple(rule["features"])
    evidence = {name: _number(row.get(name)) for name in features}
    base = {
        "label": rule["label"],
        "decision": "abstain",
        "severity": None,
        "risk_score": None,
        "region": None,
        "evidence_source": rule["track"],
        "evidence": evidence,
        "rule_id": rule_id,
        "rule_version": version,
    }
    if rule["status"] != "active":
        base["evidence"]["abstain_reason"] = rule.get("disabled_reason")
        return base
    if not _applicable(row, rule.get("applicability")):
        base["decision"] = "not_applicable"
        base["evidence"]["not_applicable_reason"] = "applicability_gate_failed"
        return base
    if any(value is None for value in evidence.values()):
        base["evidence"]["abstain_reason"] = "missing_required_feature"
        return base

    params = rule["thresholds"]
    values = [evidence[name] for name in features]
    kind = rule["kind"]
    if kind == "derived_named_panel_misalignment":
        count, clustered = values
        derived = max(0.0, 1.0 - clustered / (4.0 * count))
        evidence["derived_unclustered_edge_ratio"] = derived
        values = [derived]
        kind = "high"

    if kind == "low":
        value = values[0]
        positive, negative = float(params["positive_max"]), float(params["negative_min"])
        raw_score = (negative - value) / max(negative - positive, 1e-9)
        verdict = "positive" if value <= positive else "negative" if value >= negative else "abstain"
    elif kind == "high":
        value = values[0]
        positive, negative = float(params["positive_min"]), float(params["negative_max"])
        raw_score = (value - negative) / max(positive - negative, 1e-9)
        verdict = "positive" if value >= positive else "negative" if value <= negative else "abstain"
    elif kind in {"high_all", "binary_all"}:
        positive_hit = all(value >= float(params[f"positive_min_{i}"]) for i, value in enumerate(values))
        negative_hit = all(value <= float(params[f"negative_max_{i}"]) for i, value in enumerate(values))
        component_scores = [
            (value - float(params[f"negative_max_{i}"])) /
            max(float(params[f"positive_min_{i}"]) - float(params[f"negative_max_{i}"]), 1e-9)
            for i, value in enumerate(values)
        ]
        raw_score = min(component_scores)
        verdict = "positive" if positive_hit else "negative" if negative_hit else "abstain"
    else:
        raise ValueError(f"Unsupported frozen rule kind: {kind}")

    base["decision"] = verdict
    base["risk_score"] = round(max(0.0, min(1.0, raw_score)), 6)
    base["severity"] = 2 if verdict == "positive" else None
    return base


def evaluate_row(row: Mapping[str, Any], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        evaluate_rule(rule_id, rule, row, config["rule_version"])
        for rule_id, rule in config["rules"].items()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply frozen rule_v1 to a T8-A poster feature CSV.")
    parser.add_argument("features_csv", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rows = pd.read_csv(args.features_csv)
    output = []
    for _, row in rows.iterrows():
        for result in evaluate_row(row, config):
            output.append({
                "sample_id": row.get("sample_id"),
                "pair_id": row.get("pair_id"),
                "variant": row.get("variant"),
                **result,
                "evidence": json.dumps(result["evidence"], sort_keys=True),
            })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(output).to_csv(args.output, index=False)
    print(f"Wrote {len(output)} rule decisions to {args.output}")


if __name__ == "__main__":
    main()
