# Appendix C. Evidence-access matrix and decision boundaries

The systems do not receive identical evidence. This matrix makes that asymmetry explicit and prevents the controlled comparison from being misread as a pure contest of visual reasoning.

| System | Rendered poster pixels | Raster geometry/OCR-like measurements | PPTX structure (fonts, bounds, clipping, object groups) | Semantic visual judgment | Intended role |
|---|---:|---:|---:|---:|---|
| Gemini-P2 | Yes | No | No | Yes | image-only visual audit baseline |
| Qwen32B-P3 | Yes | No | No | Yes | image-only visual audit baseline |
| Raster Rule-v1 | Yes | Yes | No | No | conservative geometry-only baseline |
| Source-aware Rule-v1 | Yes | Yes | Yes | No | primary detector for measurable rendering facts |
| Hybrid-v1 | Yes | Yes | Yes | Selective only | gated semantic escalation after a measurable route |
| Human review | Yes | Optional | Optional | Yes | final route for uncalibrated or subjective cases |

## C.1 Label-level allocation

| Label | Primary evidence route | VLM role | Decision boundary |
|---|---|---|---|
| `body_text_too_small` | PPTX font/bounds and rendered-size feature | Borderline confirmation only | Source geometry suppresses conflicting generic VLM claim |
| `figure_detail_unreadable` | Rendered scale/complexity gate | Assess whether detail is semantically necessary | Require a measurable scale concern before semantic escalation |
| `text_overload` | Text-area density and panel budget | Secondary evidence only | Abstain if density and VLM disagree |
| `space_imbalance` | Regional occupancy/whitespace asymmetry | Raster-only confirmation when source is absent | Do not accept generic VLM allegation over measured balance |
| `alignment_error` | Grid, baseline, and edge-deviation features | Secondary perceptual cue | Only reading-disruptive, non-design deviations qualify; overlap/clipping is separate |
| `weak_hierarchy` | No calibrated deterministic route | VLM or human proposal | Review/abstain unless localized evidence supports the claim |
| `overlap_or_clipping` | PPTX text state, object intersection, and boundary checks | Raster-only fallback | Source-confirmed fact overrides VLM |
| `asset_missing_or_broken` | Source asset/path checks | Visible-placeholder fallback | Source evidence overrides VLM |
| `other` | No stable route | Free-text proposal only | Never automatically repair; route to review |

## C.2 Interpretation consequence

The Source-aware Rule and Hybrid systems can exploit retained source facts that image-only VLMs cannot observe reliably from pixels. Their higher specificity on C48-Confirm is therefore evidence for an end-to-end source-retaining audit pipeline, not evidence that deterministic rules are universally better visual reasoners. Conversely, VLM performance on External-Natural-20 cannot validate source-aware transfer because the external posters do not provide compatible source structure.

## C.3 Implementation sources

The label-level evidence plan is grounded in `08_rule_hybrid_repair/01_error_analysis/results_v1/ROUTING_EVIDENCE_MATRIX_v1.csv`; frozen thresholds and routing are stored in `08_rule_hybrid_repair/05_threshold_freeze/`.
