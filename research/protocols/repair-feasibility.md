# Repair Utility Protocol v1

## Purpose

Evaluate whether audited defects can be converted into useful poster changes without introducing new defects. This stage is secondary to the audit benchmark: the paper's core claim concerns diagnosis reliability, while repair demonstrates downstream utility.

## Evidence tiers

### Tier A — existing renderer development pilot

- Ten original/v0.6 poster pairs already exist.
- These posters were used during renderer development and therefore provide developmental evidence only.
- Geometry and the existing blind review may be summarized, but the set cannot support an independent generalization claim.
- v0.5 and v0.6 are pixel-identical for nine posters; the single portrait-layout change is not assigned the old v0.5 human rating automatically.

### Tier B — frozen closed-loop confirmation

This is the future confirmatory repair experiment. It must use data not used to tune the renderer or audit thresholds.

1. Run frozen `hybrid_v1` on the original poster.
2. Map emitted labels through `REPAIR_ACTION_REGISTRY_v1.csv`.
3. Apply only supported, deterministic actions; unsupported labels abstain.
4. Re-run the frozen auditor and objective feature extractor.
5. Evaluate target resolution, new-defect introduction, content preservation, and visual preference.

Natural-20 is the preferred Tier-B set if the paper needs an external-validity claim. A smaller fresh repair set may be used for a scoped utility claim, but it must be disclosed as such.

## Pre-registered outcomes for Tier B

- `target_resolution_rate`: target label present before and absent after, conditional on a supported repair action.
- `new_defect_rate`: labels absent before but present after.
- `safe_success_rate`: target resolved with no new moderate/severe defect.
- `abstention_rate`: detected issues without a supported safe action.
- `content_preservation_rate`: no important-information-loss judgment in blind human review.
- Pairwise human preference on readability, text burden, layout, and information preservation.

## Safety rules

- Never use the paired clean control as the source of repair parameters.
- Never tune repair thresholds on the confirmatory set.
- A VLM suggestion is advisory text; only registry actions may mutate source files.
- `alignment_error` is repaired only when a stable grid/read path can be inferred.
- `figure_detail_unreadable` may abstain when enlargement would still not reach the readability gate.
- Every edit preserves the original source, produces a new PPTX/PNG, and records an action log and hashes.

