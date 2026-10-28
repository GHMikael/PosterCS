from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from postercs_audit.evaluation.core import controlled_pair_summary, multilabel_summary


PRIMARY_CLASSES = (
    "body_text_too_small",
    "figure_detail_unreadable",
    "text_overload",
    "space_imbalance",
    "alignment_error",
    "weak_hierarchy",
    "overlap_or_clipping",
    "asset_missing_or_broken",
    "other",
    "none",
)


def cohen_kappa(gold: Sequence[str], predicted: Sequence[str]) -> float | None:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted lengths differ")
    if not gold:
        return None
    n = len(gold)
    observed = sum(a == b for a, b in zip(gold, predicted, strict=True)) / n
    gold_counts = Counter(gold)
    predicted_counts = Counter(predicted)
    classes = set(gold_counts) | set(predicted_counts)
    expected = sum((gold_counts[c] / n) * (predicted_counts[c] / n) for c in classes)
    if expected == 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def primary_summary(
    gold: Sequence[str],
    predicted: Sequence[str],
    classes: Sequence[str] = PRIMARY_CLASSES,
) -> dict[str, float | int | None]:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted lengths differ")
    n = len(gold)
    if not n:
        return {"primary_accuracy": None, "primary_macro_f1": None, "primary_kappa": None}
    per_class_f1: list[float] = []
    for label in classes:
        tp = sum(g == label and p == label for g, p in zip(gold, predicted, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, predicted, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, predicted, strict=True))
        support = tp + fn
        if support == 0:
            continue
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support
        per_class_f1.append(0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall))
    return {
        "primary_accuracy": sum(g == p for g, p in zip(gold, predicted, strict=True)) / n,
        "primary_macro_f1": sum(per_class_f1) / len(per_class_f1) if per_class_f1 else None,
        "primary_kappa": cohen_kappa(gold, predicted),
    }


def linear_weighted_kappa(gold: Sequence[int], predicted: Sequence[int]) -> float | None:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted lengths differ")
    if not gold:
        return None
    categories = (1, 2, 3)
    n = len(gold)
    max_distance = len(categories) - 1
    weights = {(a, b): abs(a - b) / max_distance for a in categories for b in categories}
    observed = sum(weights[(a, b)] for a, b in zip(gold, predicted, strict=True)) / n
    gold_counts = Counter(gold)
    predicted_counts = Counter(predicted)
    expected = sum(
        weights[(a, b)] * (gold_counts[a] / n) * (predicted_counts[b] / n)
        for a in categories
        for b in categories
    )
    if expected == 0:
        return None
    return 1.0 - observed / expected


def severity_summary(rows: Sequence[dict[str, Any]]) -> dict[str, float | int | None]:
    gold_values: list[int] = []
    predicted_values: list[int] = []
    for row in rows:
        gold_map = row["gold_severity"]
        predicted_map = row["predicted_severity"]
        for label in set(gold_map) & set(predicted_map):
            gold_values.append(int(gold_map[label]))
            predicted_values.append(int(predicted_map[label]))
    n = len(gold_values)
    return {
        "severity_matched_n": n,
        "severity_mae": sum(abs(a - b) for a, b in zip(gold_values, predicted_values, strict=True)) / n if n else None,
        "severity_exact": sum(a == b for a, b in zip(gold_values, predicted_values, strict=True)) / n if n else None,
        "severity_linear_weighted_kappa": linear_weighted_kappa(gold_values, predicted_values),
    }


def natural_summary(rows: Sequence[dict[str, Any]], labels: Sequence[str]) -> dict[str, Any]:
    gold_sets = [set(row["gold_labels"]) for row in rows]
    predicted_sets = [set(row["predicted_labels"]) for row in rows]
    report = multilabel_summary(gold_sets, predicted_sets, labels=labels)
    report.update(primary_summary(
        [str(row["gold_primary"]) for row in rows],
        [str(row["predicted_primary"]) for row in rows],
    ))
    report.update(severity_summary(rows))
    n = len(rows)
    report.update(
        mean_gold_labels=sum(len(value) for value in gold_sets) / n if n else None,
        mean_predicted_labels=sum(len(value) for value in predicted_sets) / n if n else None,
        mean_false_positives=sum(len(p - g) for g, p in zip(gold_sets, predicted_sets, strict=True)) / n if n else None,
        mean_false_negatives=sum(len(g - p) for g, p in zip(gold_sets, predicted_sets, strict=True)) / n if n else None,
    )
    return report


def build_controlled_pairs(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["pair_id"]), {})[str(row["variant"])] = row
    pairs: list[dict[str, Any]] = []
    for pair_id, variants in sorted(grouped.items()):
        if set(variants) != {"control", "mutation"}:
            raise ValueError(f"controlled pair incomplete: {pair_id}")
        control = variants["control"]
        mutation = variants["mutation"]
        target = str(control["target_label"])
        if target != str(mutation["target_label"]):
            raise ValueError(f"controlled pair target mismatch: {pair_id}")
        pairs.append({
            "pair_id": pair_id,
            "target_label": target,
            "control_labels": set(control["predicted_labels"]),
            "mutation_labels": set(mutation["predicted_labels"]),
            "control_target_confidence": float(control["predicted_confidence"].get(target, 0.0)),
            "mutation_target_confidence": float(mutation["predicted_confidence"].get(target, 0.0)),
            "control_predicted_count": len(control["predicted_labels"]),
            "mutation_predicted_count": len(mutation["predicted_labels"]),
        })
    return pairs


def controlled_summary_from_pairs(pairs: Sequence[dict[str, Any]]) -> dict[str, float | int | None]:
    report = controlled_pair_summary(pairs)
    n = len(pairs)
    report["mean_predicted_count_delta"] = (
        sum(int(pair["mutation_predicted_count"]) - int(pair["control_predicted_count"]) for pair in pairs) / n
        if n else None
    )
    return report
