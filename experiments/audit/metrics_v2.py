"""Pure metric functions for the audit v2 analysis (no sklearn, no I/O).

All functions take parallel label lists / simple sequences so they are trivially
unit-testable offline. Used by experiments/scripts/analyze_audit_v2.py.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Optional, Sequence


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> Optional[float]:
    """Cohen's kappa between two equal-length label sequences.

    Returns None for empty input. 1.0 = perfect, 0 = chance, <0 = worse than chance.
    """
    if len(a) != len(b):
        raise ValueError("label sequences must be equal length")
    n = len(a)
    if n == 0:
        return None
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    if pe == 1.0:
        return 1.0  # both constant & identical → perfect agreement
    return (po - pe) / (1 - pe)


def confusion_matrix(gold: Sequence[str], pred: Sequence[str], classes: List[str]) -> Dict[str, Dict[str, int]]:
    """gold→pred counts. Rows=gold class, cols=pred class. Unlisted labels ignored row-wise but counted if in classes."""
    cm = {g: {p: 0 for p in classes} for g in classes}
    for g, p in zip(gold, pred):
        if g in cm and p in cm[g]:
            cm[g][p] += 1
    return cm


def per_class_prf(gold: Sequence[str], pred: Sequence[str], classes: List[str]) -> Dict[str, Dict[str, float]]:
    """precision/recall/f1/support per class (one-vs-rest)."""
    out: Dict[str, Dict[str, float]] = {}
    for c in classes:
        tp = sum(1 for g, p in zip(gold, pred) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold, pred) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold, pred) if g == c and p != c)
        support = sum(1 for g in gold if g == c)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        out[c] = {"precision": round(precision, 3), "recall": round(recall, 3),
                  "f1": round(f1, 3), "support": support}
    return out


def macro_recall(prf: Dict[str, Dict[str, float]], only_supported: bool = True) -> float:
    """Macro-average recall across classes (default: only classes with support>0)."""
    vals = [m["recall"] for m in prf.values() if (m["support"] > 0 or not only_supported)]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def label_entropy(labels: Sequence[str]) -> float:
    """Shannon entropy of the label distribution, normalized to [0,1] by log2(#distinct).

    0.0 = a single label dominates entirely; 1.0 = uniform over the observed labels.
    """
    n = len(labels)
    if n == 0:
        return 0.0
    counts = Counter(labels)
    k = len(counts)
    if k <= 1:
        return 0.0
    h = -sum((c / n) * math.log2(c / n) for c in counts.values())
    return round(h / math.log2(k), 3)


def top1_share(labels: Sequence[str]) -> float:
    """Fraction taken by the single most frequent label (non-discriminativeness)."""
    n = len(labels)
    if n == 0:
        return 0.0
    return round(Counter(labels).most_common(1)[0][1] / n, 3)


def prior_baseline_acc(gold: Sequence[str]) -> float:
    """Accuracy of always predicting gold's most frequent label."""
    n = len(gold)
    if n == 0:
        return 0.0
    return round(Counter(gold).most_common(1)[0][1] / n, 3)


def false_positive_rate(gold: Sequence[str], pred: Sequence[str], cls: str) -> float:
    """Of all items whose gold != cls, the fraction the predictor labelled cls.

    For a class humans (near-)never assign, this is the hallucination rate.
    """
    neg = [(g, p) for g, p in zip(gold, pred) if g != cls]
    if not neg:
        return 0.0
    return round(sum(1 for g, p in neg if p == cls) / len(neg), 3)
