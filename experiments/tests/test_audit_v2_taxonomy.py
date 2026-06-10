"""Audit v2 taxonomy: 6-class shape, glosses, validator, old→new crosswalk."""

from experiments.audit.taxonomy import (
    REAL_ISSUES,
    ISSUE_GLOSS,
    ISSUE_TO_ACTIONS,
    PRIMARY_ISSUE_VALUES,
    validate_label,
    map_old_issue,
)

SIX = {
    "space_imbalance",
    "text_overload",
    "hierarchy_emphasis_error",
    "asset_mismatch",
    "asset_too_small",
    "structure_alignment_error",
}


def test_real_issues_is_the_six_class_set():
    assert set(REAL_ISSUES) == SIX
    assert len(REAL_ISSUES) == 6


def test_every_class_has_gloss_and_actions():
    for c in REAL_ISSUES:
        assert ISSUE_GLOSS.get(c), f"missing gloss for {c}"
        assert ISSUE_TO_ACTIONS.get(c), f"missing actions for {c}"


def test_hierarchy_gloss_covers_over_emphasis():
    assert "over" in ISSUE_GLOSS["hierarchy_emphasis_error"].lower()


def test_text_overload_is_marked_negative_control():
    assert "negative control" in ISSUE_GLOSS["text_overload"].lower()


def test_primary_values_include_new_classes_and_sentinels():
    for v in SIX | {"other", "none"}:
        assert v in PRIMARY_ISSUE_VALUES


def test_validate_label_accepts_new_classes():
    validate_label({"primary_issue": "asset_mismatch"})
    validate_label({"primary_issue": "asset_too_small"})
    validate_label({"primary_issue": "hierarchy_emphasis_error"})


def test_old_to_new_crosswalk_remaps_asset_and_hierarchy():
    assert map_old_issue("figure_too_small")["maps_to"] == "asset_too_small"
    assert map_old_issue("asset_utilization_error")["maps_to"] == "asset_mismatch"
    assert map_old_issue("visual_hierarchy_weak")["maps_to"] == "hierarchy_emphasis_error"
    # guards unchanged
    assert map_old_issue("low_contrast")["maps_to"] == "contrast_guard"
    assert map_old_issue("overlapping_elements")["maps_to"] == "overlap_guard"


def test_build_prompt_variants():
    from experiments.audit.vlm_labeler import build_prompt

    direct = build_prompt()
    narrowed = build_prompt("narrowed")
    for c in SIX:                       # both list all 6 classes
        assert c in direct and c in narrowed
    assert "6 类" in direct and "6 类" in narrowed   # dynamic class count
    assert "逐项" in narrowed and "true/false" in narrowed  # per-cue framing
    assert "逐项" not in direct          # direct = dominant-pick, not a checklist
