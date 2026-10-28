#!/usr/bin/env python3
"""Score frozen Controlled-48 systems and the pre-specified Hybrid-v1 router."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


from postercs_audit.evaluation.core import ISSUE_LABELS, controlled_pair_summary, multilabel_summary
from postercs_audit.paths import CONFIG_ROOT, DATA_ROOT, RESEARCH_ROOT, RESULTS_ROOT


HERE = Path(__file__).resolve().parent


TARGETS = (
    "body_text_too_small",
    "figure_detail_unreadable",
    "text_overload",
    "space_imbalance",
    "alignment_error",
    "overlap_or_clipping",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_vlm(run_dir: Path) -> tuple[dict[str, set[str]], dict[str, dict[str, float]]]:
    parsed = sorted(run_dir.glob("parsed/**/*.json"))
    labels: dict[str, set[str]] = {}
    confidence: dict[str, dict[str, float]] = {}
    for path in parsed:
        record = json.loads(path.read_text(encoding="utf-8"))
        sample_id = str(record["sample_id"])
        if sample_id in labels:
            raise ValueError(f"duplicate VLM prediction: {sample_id} in {run_dir}")
        selected: set[str] = set()
        conf: dict[str, float] = {}
        for issue in record["prediction"]["issues"]:
            label = str(issue["label"])
            if int(issue["severity"]) >= 2:
                selected.add(label)
                conf[label] = float(issue["confidence"])
        labels[sample_id] = selected
        confidence[sample_id] = conf
    return labels, confidence


def load_rules(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in read_csv(path):
        copied: dict[str, Any] = dict(row)
        copied["risk_score"] = float(row["risk_score"]) if row["risk_score"] else None
        grouped[row["sample_id"]][row["rule_id"]] = copied
    return dict(grouped)


def pick_rule(rules: dict[str, dict[str, Any]], primary: str, fallback: str | None = None) -> dict[str, Any]:
    first = rules[primary]
    if first["decision"] in {"positive", "negative"}:
        return first
    if fallback is not None:
        second = rules[fallback]
        if second["decision"] in {"positive", "negative"}:
            return second
    return first


def cascaded_rule_labels(rules: dict[str, dict[str, Any]]) -> set[str]:
    routes = {
        "body_text_too_small": ("R1S", "R1R"),
        "figure_detail_unreadable": ("R2S", None),
        "text_overload": ("R3S", "R3R"),
        "space_imbalance": ("R4S", "R4R"),
        "overlap_or_clipping": ("R6S", None),
    }
    found = {
        label for label, (primary, fallback) in routes.items()
        if pick_rule(rules, primary, fallback)["decision"] == "positive"
    }
    alignment = rules["R5S"]
    if alignment["decision"] == "not_applicable":
        alignment = rules["R5R"]
    if alignment["decision"] == "positive":
        found.add("alignment_error")
    return found


def raster_rule_labels(rules: dict[str, dict[str, Any]]) -> set[str]:
    return {
        row["label"] for rule_id, row in rules.items()
        if rule_id.endswith("R") and row["decision"] == "positive"
    }


def hybrid_labels(
    rules: dict[str, dict[str, Any]],
    gemini: set[str],
    qwen: set[str],
) -> set[str]:
    output: set[str] = set()

    def decide(label: str, primary: str, fallback: str | None, vlm: set[str]) -> None:
        rule = pick_rule(rules, primary, fallback)
        if rule["decision"] == "positive":
            output.add(label)
        elif rule["decision"] not in {"negative"} and label in vlm:
            output.add(label)

    decide("body_text_too_small", "R1S", "R1R", gemini)
    decide("text_overload", "R3S", "R3R", gemini)
    decide("space_imbalance", "R4S", "R4R", qwen)
    decide("overlap_or_clipping", "R6S", None, gemini)

    alignment = rules["R5S"]
    if alignment["decision"] == "not_applicable":
        alignment = rules["R5R"]
    if alignment["decision"] == "positive":
        output.add("alignment_error")
    elif alignment["decision"] != "negative" and "alignment_error" in gemini:
        output.add("alignment_error")

    figure = rules["R2S"]
    if figure["decision"] == "positive":
        # Frozen policy treats the rule as a scale gate and Gemini as the
        # semantic-importance confirmation, so both are required here.
        if "figure_detail_unreadable" in gemini:
            output.add("figure_detail_unreadable")
    elif figure["decision"] != "negative" and "figure_detail_unreadable" in gemini:
        output.add("figure_detail_unreadable")

    if "weak_hierarchy" in gemini:
        output.add("weak_hierarchy")
    return output


def confidence_for(system: str, label: str, sample_id: str, present: bool,
                   gemini_conf: dict[str, dict[str, float]],
                   qwen_conf: dict[str, dict[str, float]]) -> float:
    if system == "gemini_p2":
        return gemini_conf[sample_id].get(label, 0.0)
    if system == "qwen32b_p3":
        return qwen_conf[sample_id].get(label, 0.0)
    return 1.0 if present else 0.0


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denominator = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return (0.0 if abs(low) < 1e-12 else low), (1.0 if abs(1.0 - high) < 1e-12 else high)


def exact_mcnemar(a: list[int], b: list[int]) -> dict[str, float | int]:
    discordant_a = sum(x == 1 and y == 0 for x, y in zip(a, b, strict=True))
    discordant_b = sum(x == 0 and y == 1 for x, y in zip(a, b, strict=True))
    n = discordant_a + discordant_b
    if n == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(n, k) for k in range(0, min(discordant_a, discordant_b) + 1)) / (2 ** n)
        p_value = min(1.0, 2.0 * tail)
    return {"hybrid_only_correct": discordant_a, "comparator_only_correct": discordant_b, "p_value": p_value}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DATA_ROOT / "controlled" / "gold.csv")
    parser.add_argument("--rules", type=Path, default=RESULTS_ROOT / "controlled" / "rule-decisions.csv")
    parser.add_argument("--gemini-run", type=Path, default=RESULTS_ROOT / "predictions" / "controlled-gemini")
    parser.add_argument("--qwen-run", type=Path, default=RESULTS_ROOT / "predictions" / "controlled-qwen")
    parser.add_argument("--output", type=Path, default=RESULTS_ROOT / "controlled")
    args = parser.parse_args()

    gold_rows = read_csv(args.gold)
    gold = {row["sample_id"]: row for row in gold_rows}
    if len(gold) != 48:
        raise ValueError(f"expected 48 gold samples, got {len(gold)}")
    rules = load_rules(args.rules)
    gemini, gemini_conf = load_vlm(args.gemini_run)
    qwen, qwen_conf = load_vlm(args.qwen_run)
    for name, values in (("rules", rules), ("gemini", gemini), ("qwen", qwen)):
        missing = set(gold) - set(values)
        extra = set(values) - set(gold)
        if missing or extra:
            raise ValueError(f"{name} sample mismatch: missing={sorted(missing)}, extra={sorted(extra)}")

    systems: dict[str, dict[str, set[str]]] = {
        "gemini_p2": gemini,
        "qwen32b_p3": qwen,
        "rule_raster_v1": {sample: raster_rule_labels(rules[sample]) for sample in gold},
        "rule_cascade_v1": {sample: cascaded_rule_labels(rules[sample]) for sample in gold},
        "hybrid_v1": {
            sample: hybrid_labels(rules[sample], gemini[sample], qwen[sample])
            for sample in gold
        },
    }

    prediction_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    interval_rows: list[dict[str, Any]] = []
    ordered_samples = [row["sample_id"] for row in gold_rows]
    gold_sets = [set(json.loads(gold[sample]["labels_json"])) for sample in ordered_samples]

    for system, predicted in systems.items():
        predicted_sets = [predicted[sample] for sample in ordered_samples]
        multi = multilabel_summary(gold_sets, predicted_sets, labels=ISSUE_LABELS)
        pairs = []
        for pair_id in sorted({row["pair_id"] for row in gold_rows}):
            control_id = f"{pair_id}-control"
            mutation_id = f"{pair_id}-mutation"
            target = gold[mutation_id]["primary_label"]
            control_labels = predicted[control_id]
            mutation_labels = predicted[mutation_id]
            pair = {
                "pair_id": pair_id,
                "target_label": target,
                "control_labels": control_labels,
                "mutation_labels": mutation_labels,
                "control_target_confidence": confidence_for(
                    system, target, control_id, target in control_labels, gemini_conf, qwen_conf
                ),
                "mutation_target_confidence": confidence_for(
                    system, target, mutation_id, target in mutation_labels, gemini_conf, qwen_conf
                ),
            }
            pairs.append(pair)
            pair_rows.append({
                "system": system,
                "pair_id": pair_id,
                "target_label": target,
                "control_target_hit": int(target in control_labels),
                "mutation_target_hit": int(target in mutation_labels),
                "control_any_hit": int(bool(control_labels)),
                "paired_target_correct": int(target not in control_labels and target in mutation_labels),
                "control_labels_json": json.dumps(sorted(control_labels)),
                "mutation_labels_json": json.dumps(sorted(mutation_labels)),
            })
        controlled = controlled_pair_summary(pairs)
        overall_rows.append({
            "system": system,
            **{key: multi[key] for key in (
                "n", "macro_f1", "micro_precision", "micro_recall", "micro_f1", "mean_jaccard", "exact_match"
            )},
            **controlled,
        })
        proportion_specs = {
            "mutation_target_recall": sum(target in pair["mutation_labels"] for pair, target in ((p, p["target_label"]) for p in pairs)),
            "target_control_fpr": sum(target in pair["control_labels"] for pair, target in ((p, p["target_label"]) for p in pairs)),
            "any_defect_control_fpr": sum(bool(pair["control_labels"]) for pair in pairs),
            "paired_target_correctness": sum(
                target not in pair["control_labels"] and target in pair["mutation_labels"]
                for pair, target in ((p, p["target_label"]) for p in pairs)
            ),
        }
        for metric, successes in proportion_specs.items():
            low, high = wilson_interval(int(successes), len(pairs))
            interval_rows.append({
                "system": system,
                "metric": metric,
                "successes": int(successes),
                "n": len(pairs),
                "estimate": int(successes) / len(pairs),
                "ci95_low": low,
                "ci95_high": high,
            })
        for target in TARGETS:
            subset = [pair for pair in pairs if pair["target_label"] == target]
            target_rows.append({"system": system, "target_label": target, **controlled_pair_summary(subset)})
        for sample in ordered_samples:
            prediction_rows.append({
                "system": system,
                "sample_id": sample,
                "pair_id": gold[sample]["pair_id"],
                "variant": gold[sample]["variant"],
                "gold_labels_json": gold[sample]["labels_json"],
                "predicted_labels_json": json.dumps(sorted(predicted[sample])),
            })

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "predictions.csv", prediction_rows, list(prediction_rows[0]))
    write_csv(args.output / "overall-metrics.csv", overall_rows, list(overall_rows[0]))
    write_csv(args.output / "per-target-metrics.csv", target_rows, list(target_rows[0]))
    write_csv(args.output / "pair-outcomes.csv", pair_rows, list(pair_rows[0]))
    write_csv(args.output / "confidence-intervals.csv", interval_rows, list(interval_rows[0]))

    paired_correct = {
        system: [
            int(target not in systems[system][f"{pair_id}-control"] and target in systems[system][f"{pair_id}-mutation"])
            for pair_id, target in (
                (pair_id, gold[f"{pair_id}-mutation"]["primary_label"])
                for pair_id in sorted({row["pair_id"] for row in gold_rows})
            )
        ]
        for system in systems
    }
    comparison_rows = []
    for comparator in systems:
        if comparator == "hybrid_v1":
            continue
        test = exact_mcnemar(paired_correct["hybrid_v1"], paired_correct[comparator])
        comparison_rows.append({
            "primary_system": "hybrid_v1",
            "comparator": comparator,
            "paired_correctness_delta": (
                sum(paired_correct["hybrid_v1"]) - sum(paired_correct[comparator])
            ) / len(paired_correct["hybrid_v1"]),
            **test,
        })
    write_csv(args.output / "paired-comparisons.csv", comparison_rows, list(comparison_rows[0]))

    by_system = {row["system"]: row for row in overall_rows}
    lines = [
        "# Controlled-48 Confirmation Results",
        "",
        "Controlled-48 is the primary confirmatory benchmark. All routing rules and thresholds were frozen before these predictions were scored.",
        "",
        "| System | Pair correctness | Mutation recall | Target-control FPR | Any-defect control FPR | Micro-F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for system in systems:
        row = by_system[system]
        lines.append(
            f"| {system} | {row['paired_target_correctness']:.3f} | {row['mutation_target_recall']:.3f} | "
            f"{row['target_control_fpr']:.3f} | {row['any_defect_control_fpr']:.3f} | {row['micro_f1']:.3f} |"
        )
    lines.extend([
        "",
        "Natural-20 remains a deferred robustness extension and is not required for the primary Controlled-48 claim.",
        "",
    ])
    (args.output / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = {
        "version": "controlled48_confirmation_v1",
        "gold_loaded_only_at_scoring": True,
        "hybrid_policy": "hybrid_routing_policy_v1",
        "samples": 48,
        "pairs": 24,
        "systems": list(systems),
        "inputs": {
            "scoring_code": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256(Path(__file__).resolve()),
            },
            "confirmation_protocol": {
                "path": str((RESEARCH_ROOT / "protocols" / "controlled-evaluation.md").resolve()),
                "sha256": sha256(RESEARCH_ROOT / "protocols" / "controlled-evaluation.md"),
            },
            "rule_config": {
                "path": str((CONFIG_ROOT / "audit" / "rules.json").resolve()),
                "sha256": sha256(CONFIG_ROOT / "audit" / "rules.json"),
            },
            "routing_policy": {
                "path": str((CONFIG_ROOT / "audit" / "routing-policy.json").resolve()),
                "sha256": sha256(CONFIG_ROOT / "audit" / "routing-policy.json"),
            },
            "gold": {"path": str(args.gold.resolve()), "sha256": sha256(args.gold)},
            "rules": {"path": str(args.rules.resolve()), "sha256": sha256(args.rules)},
            "gemini_manifest": {
                "path": str((args.gemini_run / "run_manifest.json").resolve()),
                "sha256": sha256(args.gemini_run / "run_manifest.json"),
            },
            "qwen_manifest": {
                "path": str((args.qwen_run / "run_manifest.json").resolve()),
                "sha256": sha256(args.qwen_run / "run_manifest.json"),
            },
        },
    }
    (args.output / "scoring-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "systems": list(systems), "samples": 48}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
