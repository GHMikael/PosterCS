# Controlled-48 Confirmation Results v1

Controlled-48 is the primary confirmatory benchmark. All routing rules and thresholds were frozen before these predictions were scored.

| System | Pair correctness | Mutation recall | Target-control FPR | Any-defect control FPR | Micro-F1 |
|---|---:|---:|---:|---:|---:|
| gemini_p2 | 0.375 | 0.458 | 0.125 | 1.000 | 0.224 |
| qwen32b_p3 | 0.458 | 0.625 | 0.167 | 1.000 | 0.385 |
| rule_raster_v1 | 0.167 | 0.167 | 0.000 | 0.000 | 0.286 |
| rule_cascade_v1 | 0.750 | 0.750 | 0.000 | 0.000 | 0.857 |
| hybrid_v1 | 0.792 | 0.792 | 0.000 | 0.167 | 0.760 |

Natural-20 remains a deferred robustness extension and is not required for the primary Controlled-48 claim.
