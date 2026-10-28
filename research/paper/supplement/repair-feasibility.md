# Appendix E. Developmental Repair Feasibility

## E.1 Scope and claim boundary

This appendix records the ten-poster repair pilot used to verify that audit concepts could be translated into deterministic renderer actions. The ten posters were involved in renderer development. They are therefore not an independent test set, and the results must not be interpreted as an estimate of end-to-end repair effectiveness, target-defect resolution, or generalization to unseen papers.

The confirmatory contribution of the study remains the frozen audit comparison on C48-Confirm. No repair-pilot result was used in C48 scoring, model selection, threshold calibration, or statistical testing.

## E.2 Deterministic action library

The developmental executor implemented four classes of renderer action:

1. reallocate panel area to increase the displayed size of method- and evidence-bearing figures;
2. select a limited number of semantically important figures instead of shrinking all available assets;
3. enforce panel-level text budgets and choose semantic content variants with different reading burdens; and
4. route portrait-oriented figures to a dedicated right-side region when the default horizontal allocation made internal detail too small.

These actions modify retained layout and content-selection state. They are not free-form image edits, and each action can be traced to a specific renderer decision.

## E.3 Objective geometry

Across the ten development posters, the median gain in the minimum displayed figure short side was 3.17× relative to the original renders. The median gain in minimum displayed figure area was 12.88×, and the median gain in the minimum internal-detail proxy was 3.50×. The automated quality gate classified seven outputs as `pass`, three as `warn`, and none as `fail`.

These measurements show that the executor changed the intended geometric bottleneck. They do not establish that every changed figure became readable to a user or that no unrelated defect was introduced.

## E.4 Human evidence transfer

Human judgments were transferred only when the evaluated image was pixel-identical to an image that had already been reviewed. Nine of the ten v0.6 outputs were pixel-identical to their v0.5 counterparts. Among those nine posters:

- 8/9 were judged to have readable figures;
- 9/9 had acceptable text burden;
- 8/9 had acceptable layout; and
- 0/9 were judged to omit important information.

The portrait-layout output changed after routing, so its earlier human judgment was not copied to the new image. This conservative rule prevents a judgment made on one artifact from being treated as evidence for a visually different artifact.

## E.5 Required independent evaluation

A future Tier-B evaluation should freeze the auditor, action registry, and renderer before applying them to unseen papers. At minimum, it should measure target-defect resolution, newly introduced defects, content preservation, action abstention, and blinded human preference. Until such a study is completed, the current repair executor supports only an implementation-feasibility claim.

## E.6 Reproducibility pointers

- Developmental summary: `../../08_rule_hybrid_repair/07_repair_utility/pilot10_v06/PILOT10_REPAIR_SUMMARY_v1.md`
- Per-poster results: `../../08_rule_hybrid_repair/07_repair_utility/pilot10_v06/pilot10_v06_results.csv`
- Repair-stage root: `../../08_rule_hybrid_repair/07_repair_utility/`

