"""Tests for experiments.audit.metrics_v2 (pure metric functions)."""

from experiments.audit.metrics_v2 import (
    cohen_kappa, confusion_matrix, per_class_prf, macro_recall,
    label_entropy, top1_share, prior_baseline_acc, false_positive_rate,
)


def test_cohen_kappa_perfect_zero_negative():
    assert cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
    assert cohen_kappa([], []) is None
    assert cohen_kappa(["a", "b"], ["b", "a"]) == -1.0


def test_prior_baseline_acc():
    assert prior_baseline_acc(["a", "a", "b"]) == round(2 / 3, 3)


def test_label_entropy_bounds():
    assert label_entropy(["a", "a", "a"]) == 0.0       # single label
    assert label_entropy(["a", "b"]) == 1.0            # uniform over 2
    assert label_entropy([]) == 0.0


def test_top1_share():
    assert top1_share(["a", "a", "a", "b"]) == 0.75


def test_per_class_prf_known():
    gold = ["x", "x", "y", "z"]
    pred = ["x", "y", "y", "x"]
    prf = per_class_prf(gold, pred, ["x", "y", "z"])
    # x: tp=1 (item0), fp=1 (item3 gold z pred x), fn=1 (item1 gold x pred y)
    assert prf["x"]["recall"] == 0.5 and prf["x"]["precision"] == 0.5
    # y: tp=1 (item2), fp=1 (item1), fn=0 → recall 1.0
    assert prf["y"]["recall"] == 1.0
    # z: support 1, recall 0 (item3 gold z pred x)
    assert prf["z"]["recall"] == 0.0 and prf["z"]["support"] == 1


def test_macro_recall_only_supported():
    prf = {"a": {"recall": 1.0, "support": 2}, "b": {"recall": 0.0, "support": 1},
           "c": {"recall": 0.0, "support": 0}}
    assert macro_recall(prf) == 0.5   # c (support 0) excluded


def test_confusion_matrix():
    cm = confusion_matrix(["a", "a", "b"], ["a", "b", "b"], ["a", "b"])
    assert cm["a"]["a"] == 1 and cm["a"]["b"] == 1 and cm["b"]["b"] == 1


def test_false_positive_rate_is_hallucination_rate():
    # gold has zero 'space'; pred says 'space' on 3 of 4 → FP rate 0.75
    gold = ["none", "none", "none", "structure"]
    pred = ["space", "space", "space", "none"]
    assert false_positive_rate(gold, pred, "space") == 0.75
