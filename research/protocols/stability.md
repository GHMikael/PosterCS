# R5 C48 stability protocol v1

## Goal

Estimate limited repeat-call stability for the two selected image-only VLM operating points without reopening model, prompt, threshold, or routing selection.

## Fixed subset

The subset contains one complete control/mutation pair for each of the six actionable labels (12 posters). For each label, the selected pair is the lowest SHA-256 ranking under:

```text
SHA256("postercs_c48_stability_v1|<label>|<pair_id>")
```

| Label | Pair | Mutation severity | Layout |
|---|---|---|---|
| body_text_too_small | HC03 | moderate | horizontal_bands |
| figure_detail_unreadable | HC07 | moderate | horizontal_bands |
| text_overload | HC09 | moderate | magazine |
| space_imbalance | HC16 | severe | mosaic |
| alignment_error | HC18 | severe | sidebar_grid |
| overlap_or_clipping | HC24 | severe | mosaic |

## Runs and analysis

For each configuration, three independent calls per image are compared: the original frozen C48 confirmation prediction plus two new runs. The repeated calls use the same image hash, model identifier, prompt, schema, severity threshold, and temperature-0 setting. Only the API call time differs.

Report:

1. exact label-set agreement across all three calls per image;
2. mean pairwise Jaccard across the three calls;
3. primary-label agreement;
4. severity agreement for labels emitted in both calls;
5. valid-response coverage, retries, latency, and any API/validation failures.

This is a repeatability diagnostic, not a new model-selection experiment and not a basis for changing any frozen result.
