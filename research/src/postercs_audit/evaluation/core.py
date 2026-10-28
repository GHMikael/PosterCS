from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


ISSUE_LABELS = (
    "body_text_too_small",
    "figure_detail_unreadable",
    "text_overload",
    "space_imbalance",
    "alignment_error",
    "weak_hierarchy",
    "overlap_or_clipping",
    "asset_missing_or_broken",
    "other",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def issue_map(issues: Iterable[dict[str, Any]], min_severity: int = 2) -> dict[str, dict[str, Any]]:
    """Return one qualifying issue per label and reject duplicate labels."""
    mapped: dict[str, dict[str, Any]] = {}
    for issue in issues:
        label = str(issue["label"])
        if label not in ISSUE_LABELS:
            raise ValueError(f"unknown issue label: {label}")
        if label in mapped:
            raise ValueError(f"duplicate issue label: {label}")
        if int(issue["severity"]) >= min_severity:
            mapped[label] = issue
    return mapped


def label_set(issues: Iterable[dict[str, Any]], min_severity: int = 2) -> set[str]:
    return set(issue_map(issues, min_severity))


def jaccard(gold: set[str], predicted: set[str]) -> float:
    if not gold and not predicted:
        return 1.0
    return len(gold & predicted) / len(gold | predicted)


def exact_match(gold: set[str], predicted: set[str]) -> int:
    return int(gold == predicted)


def binary_counts(gold: Sequence[set[str]], predicted: Sequence[set[str]], label: str) -> dict[str, int]:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted lengths differ")
    tp = fp = fn = tn = 0
    for gold_set, pred_set in zip(gold, predicted, strict=True):
        gold_positive = label in gold_set
        pred_positive = label in pred_set
        if gold_positive and pred_positive:
            tp += 1
        elif pred_positive:
            fp += 1
        elif gold_positive:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def prf_from_counts(tp: int, fp: int, fn: int, tn: int = 0) -> dict[str, float | int | None]:
    support = tp + fn
    predicted_positive = tp + fp
    if support == 0:
        precision = tp / predicted_positive if predicted_positive else None
        recall = None
        f1 = None
    else:
        precision = tp / predicted_positive if predicted_positive else 0.0
        recall = tp / support
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "support": support,
        "predicted_positive": predicted_positive,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def multilabel_summary(
    gold: Sequence[set[str]],
    predicted: Sequence[set[str]],
    labels: Sequence[str] = ISSUE_LABELS,
) -> dict[str, Any]:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted lengths differ")
    per_label = {
        label: prf_from_counts(**binary_counts(gold, predicted, label))
        for label in labels
    }
    estimable_f1 = [row["f1"] for row in per_label.values() if row["support"] > 0]
    tp = sum(int(row["tp"]) for row in per_label.values())
    fp = sum(int(row["fp"]) for row in per_label.values())
    fn = sum(int(row["fn"]) for row in per_label.values())
    micro = prf_from_counts(tp=tp, fp=fp, fn=fn)
    n = len(gold)
    return {
        "n": n,
        "macro_f1": sum(float(value) for value in estimable_f1) / len(estimable_f1) if estimable_f1 else None,
        "micro_precision": micro["precision"],
        "micro_recall": micro["recall"],
        "micro_f1": micro["f1"],
        "mean_jaccard": sum(jaccard(g, p) for g, p in zip(gold, predicted, strict=True)) / n if n else None,
        "exact_match": sum(exact_match(g, p) for g, p in zip(gold, predicted, strict=True)) / n if n else None,
        "per_label": per_label,
    }


def controlled_pair_summary(pairs: Sequence[dict[str, Any]]) -> dict[str, float | int | None]:
    """Score target detection on pre-matched control/mutation pairs."""
    if not pairs:
        return {
            "n_pairs": 0,
            "mutation_target_recall": None,
            "target_control_fpr": None,
            "any_defect_control_fpr": None,
            "paired_target_correctness": None,
            "mean_target_confidence_delta": None,
        }
    mutation_hits = control_target_hits = control_any_hits = paired_hits = 0
    confidence_deltas: list[float] = []
    for pair in pairs:
        target = str(pair["target_label"])
        control_labels = set(pair["control_labels"])
        mutation_labels = set(pair["mutation_labels"])
        mutation_hit = target in mutation_labels
        control_target_hit = target in control_labels
        mutation_hits += int(mutation_hit)
        control_target_hits += int(control_target_hit)
        control_any_hits += int(bool(control_labels))
        paired_hits += int(mutation_hit and not control_target_hit)
        confidence_deltas.append(
            float(pair.get("mutation_target_confidence", 0.0))
            - float(pair.get("control_target_confidence", 0.0))
        )
    n = len(pairs)
    return {
        "n_pairs": n,
        "mutation_target_recall": mutation_hits / n,
        "target_control_fpr": control_target_hits / n,
        "any_defect_control_fpr": control_any_hits / n,
        "paired_target_correctness": paired_hits / n,
        "mean_target_confidence_delta": sum(confidence_deltas) / n,
    }


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Return Holm-adjusted p-values in the original order."""
    n = len(p_values)
    order = sorted(range(n), key=lambda index: p_values[index])
    adjusted = [0.0] * n
    running = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (n - rank) * float(p_values[index]))
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted
