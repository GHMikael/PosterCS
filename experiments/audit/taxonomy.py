"""The new SVFP audit taxonomy — standalone spec for the P0 failure audit.

This module is the canonical home of the **new 5-class issue taxonomy**, the
**4 deterministic guards**, and the **~12 closed actions** proposed in
``PROJECT_OPTIMIZATION_DIRECTION_v4.md`` (§3-§5). It is intentionally
*independent* of :mod:`app.vlm_commenter` (which still freezes the old 4-class
``SVFPIssueType``): P0 validates the taxonomy on real data before any
production code is changed. P1 will promote whatever survives the audit into
``app/``.

The vocabulary mirrors the production SVFP pattern — ``str``-backed enums so
members serialise directly and compare against raw VLM strings — and exposes a
JSON-schema + lightweight validator for a single audit *label* record, the same
way :func:`app.vlm_commenter.get_svfp_schema` does for production feedback.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Issue taxonomy (v4 §3.2) — five root-cause design failures, MECE-oriented.
# ---------------------------------------------------------------------------


class AuditIssueType(str, Enum):
    """The six primary issue classes, plus two labeling sentinels.

    The six real classes cover the core dimensions of poster visual design
    (space / text / hierarchy-emphasis / asset-mismatch / asset-size /
    structure). ``OTHER`` and ``NONE`` are sentinels used only during
    *labeling* so we can measure the audit's ``other_rate`` and ``coverage``
    honestly — they are never proposed as taxonomy members.
    """

    SPACE_IMBALANCE = "space_imbalance"
    TEXT_OVERLOAD = "text_overload"
    HIERARCHY_EMPHASIS_ERROR = "hierarchy_emphasis_error"
    ASSET_MISMATCH = "asset_mismatch"
    ASSET_TOO_SMALL = "asset_too_small"
    STRUCTURE_ALIGNMENT_ERROR = "structure_alignment_error"

    # labeling sentinels (NOT taxonomy members)
    OTHER = "other"
    NONE = "none"


#: The five real issue classes (no sentinels). This is the taxonomy under test.
REAL_ISSUES: List[str] = [
    AuditIssueType.SPACE_IMBALANCE.value,
    AuditIssueType.TEXT_OVERLOAD.value,
    AuditIssueType.HIERARCHY_EMPHASIS_ERROR.value,
    AuditIssueType.ASSET_MISMATCH.value,
    AuditIssueType.ASSET_TOO_SMALL.value,
    AuditIssueType.STRUCTURE_ALIGNMENT_ERROR.value,
]

#: Sentinels usable as a *primary* label (for coverage / other_rate accounting).
SENTINELS: List[str] = [AuditIssueType.OTHER.value, AuditIssueType.NONE.value]

#: Valid values for a ``primary_issue`` field: the 5 real classes + sentinels.
PRIMARY_ISSUE_VALUES: List[str] = REAL_ISSUES + SENTINELS

#: Valid values for ``secondary_issues`` entries: the 5 real classes + ``other``
#: (a secondary issue is never ``none`` — absence is just an empty list).
SECONDARY_ISSUE_VALUES: List[str] = REAL_ISSUES + [AuditIssueType.OTHER.value]

#: Human-readable gloss for each class (used in prompts / charts / reports).
ISSUE_GLOSS: Dict[str, str] = {
    AuditIssueType.SPACE_IMBALANCE.value: (
        "Uneven use of space WITHIN panels: some panels nearly empty or bullets "
        "too loosely spaced while others are cramped; lopsided visual weight. "
        "(Panel-internal — contrast structure_alignment_error which is grid-level.)"
    ),
    AuditIssueType.TEXT_OVERLOAD.value: (
        "Too much text / text overflowing or clipped / font too small. NEGATIVE "
        "CONTROL: generation has largely eliminated this, so a VLM reporting it "
        "is most likely a false positive (hallucination probe)."
    ),
    AuditIssueType.HIERARCHY_EMPHASIS_ERROR.value: (
        "Wrong visual emphasis: EITHER no clear focal point (panels look "
        "identical, reader cannot tell what to read first) OR an element is "
        "OVER-emphasized (e.g. oversized decorative section numbers grabbing "
        "attention away from content)."
    ),
    AuditIssueType.ASSET_MISMATCH.value: (
        "Figure does not match its text / a wrong or irrelevant figure was "
        "placed (depends on the planner's figure-selection accuracy)."
    ),
    AuditIssueType.ASSET_TOO_SMALL.value: (
        "A relevant figure is rendered too small to read its content."
    ),
    AuditIssueType.STRUCTURE_ALIGNMENT_ERROR.value: (
        "Broken structure at the GRID level: a whole rectangular region left "
        "blank on one side, misaligned panels, unbalanced column widths, panels "
        "not filling the canvas, section headers off-baseline. (Grid-level — "
        "contrast space_imbalance which is panel-internal.)"
    ),
}


# ---------------------------------------------------------------------------
# Guards (v4 §3.4) — low-frequency hard-constraint violations, rule-detectable.
# Kept OUT of the primary taxonomy on purpose; reported as a separate track.
# ---------------------------------------------------------------------------


class AuditGuard(str, Enum):
    """Rare, rule-checkable hard-constraint violations handled by guards.

    These are deliberately *not* primary issues: ``overlap`` and ``contrast``
    were demoted from the old taxonomy because they are low-frequency and more
    appropriately caught by deterministic checks (bbox overlap ratio, WCAG
    contrast) than by a VLM design critique.
    """

    OVERLAP_GUARD = "overlap_guard"
    CONTRAST_GUARD = "contrast_guard"
    OVERFLOW_GUARD = "overflow_guard"
    CROP_GUARD = "crop_guard"


GUARD_VALUES: List[str] = [g.value for g in AuditGuard]

GUARD_GLOSS: Dict[str, str] = {
    AuditGuard.OVERLAP_GUARD.value: "Two elements physically overlap.",
    AuditGuard.CONTRAST_GUARD.value: "Text/background contrast below a legibility threshold.",
    AuditGuard.OVERFLOW_GUARD.value: "Text overflows its box / is clipped / shows an ellipsis.",
    AuditGuard.CROP_GUARD.value: "An image is cropped or has a distorted aspect ratio.",
}


# ---------------------------------------------------------------------------
# Actions (v4 §5.2) — the closed, compact action set the FeedbackApplier will
# eventually expose. Spec only here; the P0 labeler does not emit actions.
# ---------------------------------------------------------------------------


class AuditAction(str, Enum):
    """The ~12 deterministic repair actions targeted for P1."""

    REBALANCE_WHITESPACE = "rebalance_whitespace"
    RESIZE_PANEL = "resize_panel"
    REDUCE_BULLET_COUNT = "reduce_bullet_count"
    INCREASE_ABSTRACTION = "increase_abstraction"
    PROMOTE_KEY_CLAIM = "promote_key_claim"
    ADD_CALLOUT = "add_callout"
    SELECT_KEY_FIGURE = "select_key_figure"
    ENLARGE_FIGURE = "enlarge_figure"
    SWITCH_TO_IMAGE_FOCUS = "switch_to_image_focus"
    SNAP_TO_GRID = "snap_to_grid"
    NORMALIZE_MARGINS = "normalize_margins"
    ALIGN_SECTION_HEADERS = "align_section_headers"


ACTION_VALUES: List[str] = [a.value for a in AuditAction]

#: Reference issue → typical actions (v4 §5.2). Documentation for P1, and used
#: by the audit report to sanity-check that every issue has a remedy.
ISSUE_TO_ACTIONS: Dict[str, List[str]] = {
    AuditIssueType.SPACE_IMBALANCE.value: [
        AuditAction.REBALANCE_WHITESPACE.value,
        AuditAction.RESIZE_PANEL.value,
    ],
    AuditIssueType.TEXT_OVERLOAD.value: [
        AuditAction.REDUCE_BULLET_COUNT.value,
        AuditAction.INCREASE_ABSTRACTION.value,
    ],
    AuditIssueType.HIERARCHY_EMPHASIS_ERROR.value: [
        AuditAction.PROMOTE_KEY_CLAIM.value,
        AuditAction.ADD_CALLOUT.value,
    ],
    AuditIssueType.ASSET_MISMATCH.value: [
        AuditAction.SELECT_KEY_FIGURE.value,
    ],
    AuditIssueType.ASSET_TOO_SMALL.value: [
        AuditAction.ENLARGE_FIGURE.value,
        AuditAction.SWITCH_TO_IMAGE_FOCUS.value,
    ],
    AuditIssueType.STRUCTURE_ALIGNMENT_ERROR.value: [
        AuditAction.SNAP_TO_GRID.value,
        AuditAction.NORMALIZE_MARGINS.value,
        AuditAction.ALIGN_SECTION_HEADERS.value,
    ],
}


# ---------------------------------------------------------------------------
# Old → new cross-walk (v4 §3.3). Lets the audit translate the legacy 4-class
# critiques already stored in old run_reports into the new vocabulary, and is
# the evidence that overlap/contrast are correctly demoted to guards.
# ---------------------------------------------------------------------------

#: kind ∈ {"issue", "guard"}; ``maps_to`` is a value of AuditIssueType/AuditGuard.
OLD_TO_NEW: Dict[str, Dict[str, str]] = {
    "empty_space": {
        "maps_to": AuditIssueType.SPACE_IMBALANCE.value,
        "kind": "issue",
        "note": "Widened from 'blank space' to 'uneven space allocation'.",
    },
    "overlapping_elements": {
        "maps_to": AuditGuard.OVERLAP_GUARD.value,
        "kind": "guard",
        "note": "Low-frequency; demoted to a rule-based guard. Primary slot ceded to text_overload.",
    },
    "low_contrast": {
        "maps_to": AuditGuard.CONTRAST_GUARD.value,
        "kind": "guard",
        "note": "WCAG-checkable; demoted to a guard. Primary slot ceded to hierarchy_emphasis_error.",
    },
    "figure_too_small": {
        "maps_to": AuditIssueType.ASSET_TOO_SMALL.value,
        "kind": "issue",
        "note": "v6: split out as its own class (geometry-detectable figure-size error).",
    },
    # v6 legacy: previous 5-class strings a model may still emit.
    "asset_utilization_error": {
        "maps_to": AuditIssueType.ASSET_MISMATCH.value,
        "kind": "issue",
        "note": "v6: the broad asset class split into asset_mismatch + asset_too_small; semantic mismatch is the default.",
    },
    "visual_hierarchy_weak": {
        "maps_to": AuditIssueType.HIERARCHY_EMPHASIS_ERROR.value,
        "kind": "issue",
        "note": "v6: renamed + widened to cover over-emphasis as well as no-focus.",
    },
}

#: The legacy 4-class taxonomy strings (for mining old run_reports).
OLD_ISSUE_VALUES: List[str] = list(OLD_TO_NEW.keys())


def map_old_issue(old_value: str) -> Dict[str, str]:
    """Translate a legacy 4-class issue string into the new vocabulary.

    Returns the ``OLD_TO_NEW`` record, or an ``other``/``issue`` fallback for
    any unrecognised legacy label so callers never KeyError on stray strings.
    """

    return OLD_TO_NEW.get(
        str(old_value).strip().lower(),
        {"maps_to": AuditIssueType.OTHER.value, "kind": "issue", "note": "Unmapped legacy label."},
    )


# ---------------------------------------------------------------------------
# Audit *label* record: schema + validator.
# ---------------------------------------------------------------------------


def audit_label_schema() -> Dict[str, Any]:
    """JSON Schema (draft-07) for a single audit label record.

    One record = one labeler's read of one initial poster. Mirrors the spirit
    of :func:`app.vlm_commenter.get_svfp_schema` so any producer (Qwen-VL, a
    stronger VLM, or a human) emits an identical payload.
    """

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "SVFPAuditLabel",
        "description": "One labeler's failure-taxonomy read of one initial poster.",
        "type": "object",
        "additionalProperties": True,
        "required": ["primary_issue"],
        "properties": {
            "primary_issue": {
                "type": "string",
                "enum": PRIMARY_ISSUE_VALUES,
                "description": "Dominant failure (5 classes, or 'other'/'none').",
            },
            "secondary_issues": {
                "type": "array",
                "items": {"type": "string", "enum": SECONDARY_ISSUE_VALUES},
                "description": "Additional non-dominant failures (no 'none').",
            },
            "guard_violations": {
                "type": "array",
                "items": {"type": "string", "enum": GUARD_VALUES},
                "description": "Rare hard-constraint violations (separate track).",
            },
            "evidence": {
                "type": "object",
                "description": "Free-text justification keyed by 'primary'/issue.",
            },
            "confidence": {
                "type": ["number", "null"],
                "minimum": 0.0,
                "maximum": 1.0,
            },
        },
    }


def validate_label(label: Any) -> None:
    """Structural validator for one audit label dict. Raises ``ValueError``.

    Kept dependency-free (no jsonschema lib) and tolerant of extra keys
    (``run_id``, ``labeler``, ``source``, ``notes`` …) so the same record can
    carry provenance without failing validation.
    """

    if not isinstance(label, dict):
        raise ValueError("Label must be a dict.")

    primary = label.get("primary_issue")
    if not isinstance(primary, str) or primary not in PRIMARY_ISSUE_VALUES:
        raise ValueError(
            f"primary_issue must be one of {PRIMARY_ISSUE_VALUES}, got {primary!r}"
        )

    secondary = label.get("secondary_issues", [])
    if not isinstance(secondary, list):
        raise ValueError("secondary_issues must be a list.")
    for s in secondary:
        if s not in SECONDARY_ISSUE_VALUES:
            raise ValueError(
                f"secondary issue must be one of {SECONDARY_ISSUE_VALUES}, got {s!r}"
            )

    guards = label.get("guard_violations", [])
    if not isinstance(guards, list):
        raise ValueError("guard_violations must be a list.")
    for g in guards:
        if g not in GUARD_VALUES:
            raise ValueError(f"guard violation must be one of {GUARD_VALUES}, got {g!r}")

    conf = label.get("confidence")
    if conf is not None and not (isinstance(conf, (int, float)) and 0.0 <= float(conf) <= 1.0):
        raise ValueError("confidence must be null or a number in [0, 1].")
