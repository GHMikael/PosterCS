# R6 Statistical clarification v1

## Plain-language decision

The question that matters most for the paper is not whether Hybrid beats a weak image-only baseline. It is whether adding selective VLM escalation improves the already strong Source-aware Rule cascade enough to justify its extra false allegations. Therefore, **Hybrid-v1 versus Source-aware Rule-v1 is the single primary C48 contrast**. The three comparisons against Gemini-P2, Qwen32B-P3, and Raster Rule-v1 are secondary contextual contrasts and receive Holm correction as one three-test family.

## C48 paired-correctness contrasts

| Role | Comparator | Hybrid minus comparator | Hybrid-only / comparator-only correct pairs | Exact McNemar raw *p* | Holm-adjusted *p* | Reading |
|---|---|---:|---:|---:|---:|---|
| Primary | Source-aware Rule-v1 | +4.2 pp (1/24) | 1 / 0 | 1.000000 | 1.000000 | No evidence that the one-pair Hybrid gain is reliable. |
| Secondary | Gemini-P2 | +41.7 pp (10/24) | 10 / 0 | .001953 | .003906 | Hybrid exceeds this image-only operating point. |
| Secondary | Qwen32B-P3 | +33.3 pp (8/24) | 8 / 0 | .007813 | .007813 | Hybrid exceeds this image-only operating point. |
| Secondary | Raster Rule-v1 | +62.5 pp (15/24) | 15 / 0 | .000061 | .000183 | Hybrid exceeds the raster-only baseline. |

The primary comparison is deliberately not folded into the secondary Holm family because it was selected to test the paper's central deployment question: whether VLM escalation adds reliable value beyond retained source structure. All four raw exact p-values and all secondary adjusted values are retained in `C48_PRIMARY_SECONDARY_COMPARISONS_v1.csv`.

## Macro-F1 rule

For every dataset split, macro-F1 is the unweighted mean of per-label F1 over labels with at least one Gold positive in that split. A label with Gold support zero has no estimable recall or F1; its per-label value is reported as `NA` and it is excluded from macro-F1. A supported label that a system never predicts receives F1 = 0.

This rule applies separately to each split:

| Split | Labels with Gold support | Zero-support labels excluded from macro-F1 |
|---|---|---|
| Natural-40 | `overlap_or_clipping`, `figure_detail_unreadable`, `space_imbalance` | six |
| C48-Confirm | six injected actionable labels | three |
| External-Natural-20 | `body_text_too_small`, `figure_detail_unreadable`, `text_overload`, `space_imbalance` | five |

Macro-F1 is therefore a summary of performance on the observed label mix of that split. It is not evidence of uniform coverage of the nine-label taxonomy.

## Replacement text for the manuscript

### Replace the final two sentences of §4.5

```text
For C48-Confirm, the primary statistical contrast is Hybrid-v1 versus Source-aware Rule-v1 on paired target correctness, because this comparison tests whether selective VLM escalation adds reliable value beyond retained source structure. Hybrid-v1 comparisons with Gemini-P2, Qwen32B-P3, and Raster Rule-v1 are secondary contextual contrasts; their exact McNemar p-values are Holm-corrected as one three-test family. All comparisons report absolute paired-correctness differences and discordant-pair counts. Macro-F1 is the unweighted mean over labels with Gold support of at least one in the relevant split; zero-support labels are reported as `NA` per label and excluded from that split's macro average.
```

### Replace the first paragraph of §5.3 beginning “Matched comparisons …”

```text
The primary C48 contrast asks whether Hybrid-v1 improves paired target correctness over the Source-aware Rule cascade. Hybrid-v1 was correct on one additional pair and lost none, a 4.2-point difference (1/24; exact McNemar p = 1.0). Thus, the observed gain does not provide evidence that VLM escalation reliably improves the source-aware cascade. Three secondary comparisons place the systems in context. Relative to Gemini-P2, Qwen32B-P3, and Raster Rule-v1, Hybrid-v1 gained 10, 8, and 15 pairs, respectively, with no losses; the corresponding raw exact p-values were .001953, .007813, and .000061, and Holm-adjusted values within this three-test family were .003906, .007813, and .000183. These secondary differences establish that the source-retaining pipeline outperforms the selected image-only and raster-only baselines on this controlled task, but they do not change the primary Hybrid-versus-Source-aware conclusion.
```
