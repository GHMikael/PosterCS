"""Offline unit tests for the P0 failure-taxonomy audit (no network).

Covers: taxonomy integrity + old→new cross-walk, label validation, VLM-output
coercion (including legacy-string mapping), Cohen's κ, the distribution
aggregation, and the MECE audit math + verdict. Also asserts the VLM labeler
returns a clean ``disabled`` stub when no API key is configured.
"""

from __future__ import annotations

import json

import pytest

from experiments.audit.taxonomy import (
    ACTION_VALUES,
    GUARD_VALUES,
    ISSUE_GLOSS,
    ISSUE_TO_ACTIONS,
    OLD_TO_NEW,
    PRIMARY_ISSUE_VALUES,
    REAL_ISSUES,
    AuditIssueType,
    map_old_issue,
    validate_label,
)
from experiments.audit.vlm_labeler import _normalize_vlm_label, label_poster
from experiments.scripts.analysis_issue_distribution import aggregate, load_labels
from experiments.scripts.analysis_issue_mece_audit import audit, cohen_kappa


# ---------------------------------------------------------------------------
# Taxonomy integrity
# ---------------------------------------------------------------------------


def test_taxonomy_shapes():
    assert len(REAL_ISSUES) == 5
    assert set(PRIMARY_ISSUE_VALUES) == set(REAL_ISSUES) | {"other", "none"}
    assert len(GUARD_VALUES) == 4
    assert 9 <= len(ACTION_VALUES) <= 12
    assert set(ISSUE_GLOSS.keys()) == set(REAL_ISSUES)


def test_old_to_new_crosswalk_total_and_valid():
    # All four legacy classes are mapped.
    assert set(OLD_TO_NEW.keys()) == {
        "empty_space", "overlapping_elements", "low_contrast", "figure_too_small",
    }
    for old, rec in OLD_TO_NEW.items():
        assert rec["kind"] in {"issue", "guard"}
        if rec["kind"] == "issue":
            assert rec["maps_to"] in REAL_ISSUES
        else:
            assert rec["maps_to"] in GUARD_VALUES
    # overlap & contrast are demoted to guards (the core claim of P0).
    assert OLD_TO_NEW["overlapping_elements"]["kind"] == "guard"
    assert OLD_TO_NEW["low_contrast"]["kind"] == "guard"
    # empty_space becomes space_imbalance.
    assert OLD_TO_NEW["empty_space"]["maps_to"] == "space_imbalance"


def test_issue_to_actions_consistency():
    assert set(ISSUE_TO_ACTIONS.keys()) == set(REAL_ISSUES)
    for issue, actions in ISSUE_TO_ACTIONS.items():
        assert actions, f"{issue} has no action"
        for a in actions:
            assert a in ACTION_VALUES


def test_map_old_issue_unknown_falls_back_to_other():
    assert map_old_issue("empty_space")["maps_to"] == "space_imbalance"
    assert map_old_issue("totally_unknown")["maps_to"] == "other"


# ---------------------------------------------------------------------------
# Label validation
# ---------------------------------------------------------------------------


def test_validate_label_accepts_good():
    validate_label({
        "primary_issue": "text_overload",
        "secondary_issues": ["space_imbalance", "other"],
        "guard_violations": ["overflow_guard"],
        "confidence": 0.8,
        "run_id": "abc",  # extra keys allowed
    })


@pytest.mark.parametrize("bad", [
    {"primary_issue": "made_up"},
    {"primary_issue": "text_overload", "secondary_issues": ["none"]},     # 'none' invalid as secondary
    {"primary_issue": "text_overload", "secondary_issues": ["bogus"]},
    {"primary_issue": "text_overload", "guard_violations": ["not_a_guard"]},
    {"primary_issue": "text_overload", "confidence": 2.0},
    "not a dict",
])
def test_validate_label_rejects_bad(bad):
    with pytest.raises(ValueError):
        validate_label(bad)


# ---------------------------------------------------------------------------
# VLM output coercion
# ---------------------------------------------------------------------------


def test_normalize_maps_legacy_primary_issue():
    out = _normalize_vlm_label({"primary_issue": "empty_space"})
    assert out["primary_issue"] == "space_imbalance"
    validate_label(out)


def test_normalize_guard_named_as_primary_moves_to_guard_track():
    out = _normalize_vlm_label({"primary_issue": "overlapping_elements"})
    # overlap is a guard, not an issue → primary becomes 'other', guard recorded.
    assert out["primary_issue"] == "other"
    assert "overlap_guard" in out["guard_violations"]
    validate_label(out)


def test_normalize_dedupes_and_drops_primary_from_secondary():
    out = _normalize_vlm_label({
        "primary_issue": "text_overload",
        "secondary_issues": ["text_overload", "space_imbalance", "space_imbalance", "low_contrast"],
        "guard_violations": ["contrast_guard"],
        "confidence": 5,  # clamps to 1.0
    })
    assert out["primary_issue"] == "text_overload"
    assert out["secondary_issues"] == ["space_imbalance"]   # primary removed, deduped, low_contrast→guard dropped from issues
    assert "contrast_guard" in out["guard_violations"]
    assert out["confidence"] == 1.0
    validate_label(out)


def test_normalize_unknown_issue_becomes_other():
    out = _normalize_vlm_label({"primary_issue": "purple_monster"})
    assert out["primary_issue"] == "other"
    validate_label(out)


def test_normalize_none_stays_none():
    out = _normalize_vlm_label({"primary_issue": "none", "secondary_issues": []})
    assert out["primary_issue"] == "none"
    validate_label(out)


# ---------------------------------------------------------------------------
# Cohen's kappa
# ---------------------------------------------------------------------------


def test_cohen_kappa_perfect_and_empty_and_negative():
    assert cohen_kappa([("a", "a"), ("b", "b")], ["a", "b", "c"]) == 1.0
    assert cohen_kappa([], ["a", "b"]) is None
    assert cohen_kappa([("a", "b"), ("b", "a")], ["a", "b"]) == -1.0


# ---------------------------------------------------------------------------
# Distribution + MECE on synthetic records
# ---------------------------------------------------------------------------


def _rec(run_id, primary, *, secondary=None, guards=None, source="vlm", old=None, template="t", labels=None):
    base_labels = labels if labels is not None else [{
        "primary_issue": primary,
        "secondary_issues": secondary or [],
        "guard_violations": guards or [],
        "source": source,
    }]
    return {
        "run_id": run_id,
        "paper_title": run_id,
        "template": template,
        "old_issues_initial": old or [],
        "labels": base_labels,
    }


def _synthetic_corpus():
    return [
        _rec("r1", "space_imbalance", old=["empty_space", "overlapping_elements"]),
        _rec("r2", "text_overload", secondary=["space_imbalance"], guards=["overflow_guard"], old=["empty_space"]),
        _rec("r3", "other", old=["figure_too_small"]),
        _rec("r4", "none"),
        _rec("r5", "space_imbalance", source="vlm_error"),  # failed label
    ]


def test_aggregate_counts():
    agg = aggregate(_synthetic_corpus())
    assert agg["n_posters"] == 5
    assert agg["n_labeled_ok"] == 4          # r5 failed
    assert agg["primary_distribution"]["space_imbalance"] == 1
    assert agg["primary_distribution"]["text_overload"] == 1
    assert agg["primary_distribution"]["other"] == 1
    assert agg["primary_distribution"]["none"] == 1
    assert agg["secondary_distribution"]["space_imbalance"] == 1
    assert agg["guard_trigger_counts"]["overflow_guard"] == 1
    # legacy mining is independent of label success (r5 had no old issues anyway)
    assert agg["legacy_issue_counts"]["empty_space"] == 2
    assert agg["legacy_issue_counts"]["overlapping_elements"] == 1
    # overlap+contrast share of legacy mentions = 1 / (2+1+1) = 0.25
    assert agg["legacy_low_freq_check"]["overlap_plus_contrast"] == 1
    assert agg["legacy_low_freq_check"]["low_freq_share"] == 0.25


def test_mece_audit_math_and_verdict():
    res = audit(_synthetic_corpus(), {}, coverage_min=0.80, other_rate_max=0.10, legacy_lowfreq_max=0.25)
    # failures = r1, r2, r3 (primary != none) = 3; covered = r1, r2 = 2
    assert res["n_failures"] == 3
    assert res["coverage"] == round(2 / 3, 3)
    assert res["other_rate"] == round(1 / 3, 3)
    assert res["multi_label_rate"] == 0.25       # r2 has a secondary; over n_ok=4
    # coverage 0.667 < 0.80 and other_rate 0.333 > 0.10 → both fail; legacy 0.25 <= 0.25 passes
    assert res["verdict"]["coverage_pass"] is False
    assert res["verdict"]["other_rate_pass"] is False
    assert res["verdict"]["legacy_lowfreq_pass"] is True
    assert res["verdict"]["overall_pass"] is False


def test_mece_audit_two_pass_kappa():
    recs = [
        _rec("a", "x", labels=[
            {"primary_issue": "space_imbalance", "secondary_issues": [], "guard_violations": [], "source": "vlm"},
            {"primary_issue": "space_imbalance", "secondary_issues": [], "guard_violations": [], "source": "vlm"},
        ]),
        _rec("b", "x", labels=[
            {"primary_issue": "text_overload", "secondary_issues": [], "guard_violations": [], "source": "vlm"},
            {"primary_issue": "text_overload", "secondary_issues": [], "guard_violations": [], "source": "vlm"},
        ]),
    ]
    res = audit(recs, {}, coverage_min=0.8, other_rate_max=0.1, legacy_lowfreq_max=0.25)
    track = res["agreement"]["vlm_pass0_vs_pass1"]
    assert track is not None and track["n"] == 2
    assert track["cohen_kappa"] == 1.0          # perfect agreement


def test_load_labels_roundtrip(tmp_path):
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()
    (labels_dir / "r1.json").write_text(json.dumps(_rec("r1", "text_overload"), ensure_ascii=False), encoding="utf-8")
    recs = load_labels(labels_dir)
    assert len(recs) == 1 and recs[0]["run_id"] == "r1"


# ---------------------------------------------------------------------------
# Labeler disabled stub (no network, no key)
# ---------------------------------------------------------------------------


def test_label_poster_disabled_stub(monkeypatch, tmp_path):
    import experiments.audit.vlm_labeler as vl
    monkeypatch.setattr(vl, "DASHSCOPE_API_KEY", "")
    out = vl.label_poster(tmp_path / "nonexistent.png", run_id="r1")
    assert out["source"] == "disabled"
    assert out["primary_issue"] == "none"
    validate_label(out)
