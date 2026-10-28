# Controlled-48 Confirmation Protocol v1

## Status

- Benchmark: frozen `Controlled-48` (24 control/mutation pairs, 48 posters).
- Gold source: controlled injection plus blind human verification.
- Gold visibility: unavailable to VLM inference and rule execution; loaded only by the scoring script.
- Rule thresholds: frozen as `rule_v1` before confirmation scoring.
- Routing policy: frozen as `hybrid_routing_policy_v1` before confirmation scoring.
- Primary scope: controlled sensitivity and false-positive resistance for six operational defect labels.
- Deferred extension: `Natural-20` robustness evaluation; it is not required for the primary Controlled-48 claim.

## Systems compared

1. `gemini_p2`: Gemini Flash with the frozen P2 taxonomy prompt.
2. `qwen32b_p3`: Qwen3-VL-32B-Instruct with the frozen P3 evidence-grounded prompt.
3. `rule_raster_v1`: positive outputs from frozen raster rules only.
4. `rule_cascade_v1`: frozen source-first rules with their specified raster fallbacks.
5. `hybrid_v1`: frozen rule/VLM routing described below.

All VLM labels require predicted severity >= 2. Severity-1 observations do not count as detected defects.

## Hybrid-v1 operational routing

| Label | Rule path | Borderline/fallback VLM | Final decision |
|---|---|---|---|
| `body_text_too_small` | R1S, then R1R | Gemini-P2 | Rule positive/negative is decisive; unresolved cases use Gemini. |
| `figure_detail_unreadable` | R2S scale gate | Gemini-P2 | A positive scale gate requires Gemini semantic-importance confirmation; negative suppresses; unresolved cases use Gemini. |
| `text_overload` | R3S, then R3R | Gemini-P2 | Rule positive/negative is decisive; unresolved cases use Gemini. |
| `space_imbalance` | R4S, then R4R | Qwen32B-P3 | Rule positive/negative is decisive; unresolved cases use Qwen. |
| `alignment_error` | R5S for named grids, otherwise R5R | Gemini-P2 | Rule positive/negative is decisive; unresolved cases use Gemini. |
| `overlap_or_clipping` | R6S | Gemini-P2 | Rule positive/negative is decisive; unresolved cases use Gemini. |
| `weak_hierarchy` | none | Gemini-P2 | Gemini decides. |
| `asset_missing_or_broken`, `other` | not calibrated | human/deferred | Not emitted automatically by Hybrid-v1. |

`not_applicable` is never converted directly to a clean (`none`) judgment. It follows the specified fallback or VLM route.

## Primary metrics

- Mutation target recall.
- Target-label false-positive rate on paired controls.
- Paired target correctness: mutation detects the target while its control does not.
- Any-defect false-positive rate on controls.

Secondary metrics are multilabel micro/macro F1, exact match, and mean Jaccard. Per-target results are reported because each target has four independent pairs.

## Interpretation boundary

Controlled-48 supports causal sensitivity claims for the six injected defect types under the included layouts and severities. It does not by itself establish performance on naturally occurring posters. Any broader robustness claim requires the deferred Natural-20 experiment or another independently sampled natural benchmark.
