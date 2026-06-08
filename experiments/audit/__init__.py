"""P0 failure-taxonomy audit package.

Standalone tooling that validates the **new 5-class SVFP issue taxonomy**
(``space_imbalance``, ``text_overload``, ``visual_hierarchy_weak``,
``asset_utilization_error``, ``structure_alignment_error``) plus the four
deterministic guards, *before* the production SVFP code in :mod:`app` is
touched.

Design rule (v4 §13 / P0): this package MUST NOT mutate the production
4-class taxonomy. It defines its own vocabulary in :mod:`experiments.audit.taxonomy`
and only *reads* production helpers (image encoding, JSON extraction) for the
VLM labeler. Promotion of the new taxonomy into ``app/`` is P1, a later step.
"""
