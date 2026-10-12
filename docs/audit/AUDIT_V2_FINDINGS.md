# Audit v2 (new60) — Findings

> Gold = annotatorA (user). Inter-annotator A/B κ = **0.864** (60 common, 5 disagreements).

## Gold distribution (human)

| class | n |
|---|---|
| space_imbalance | 2 |
| asset_too_small | 8 |
| structure_alignment_error | 14 |
| none | 35 |
| other | 1 |

**Per template (gold):**

- `template_dashboard`: {'space_imbalance': 1, 'none': 16, 'other': 1}
- `template_classic`: {'space_imbalance': 1, 'none': 19, 'asset_too_small': 2}
- `template_storyflow`: {'structure_alignment_error': 14, 'asset_too_small': 5}
- `template_minimal`: {'asset_too_small': 1}

## Objective geom rules

- contrast: all themes WCAG-AA = **True** → any VLM `low_contrast` is a false positive.
- overlap: 20/60 posters have ≥1 partial collision (rest clean).

## VLM vs gold (prompt-gradient)

| metric | direct | narrowed | grounded | describe_classify |
|---|---|---|---|---|
| accuracy | 0.133 | 0.167 | 0.267 | 0.133 |
| prior baseline | 0.583 | 0.583 | 0.583 | 0.583 |
| κ(VLM,gold) | 0.06 | 0.082 | 0.138 | 0.078 |
| VLM top-1 share | 0.7 | 0.667 | 0.5 | 0.867 |
| VLM label entropy | 0.701 | 0.678 | 0.79 | 0.567 |
| recall(none) | 0.0 | 0.0 | 0.0 | 0.0 |
| FP rate space_imbalance | 0.724 | 0.672 | 0.138 | 0.862 |
| FP rate text_overload | 0.0 | 0.033 | 0.0 | 0.0 |

**Per-class recall (VLM vs gold):**

| class | gold_support | recall(direct) | recall(narrowed) | recall(grounded) | recall(describe_classify) |
|---|---|---|---|---|---|
| space_imbalance | 2 | 0.0 | 0.5 | 0.0 | 1.0 |
| asset_too_small | 8 | 0.0 | 0.0 | 0.375 | 0.0 |
| structure_alignment_error | 14 | 0.571 | 0.643 | 0.929 | 0.429 |
| none | 35 | 0.0 | 0.0 | 0.0 | 0.0 |
| other | 1 | 0.0 | 0.0 | 0.0 | 0.0 |

## Verdict

- **direct: S1** — S1=True S2=False S3=False; reliable=[] blind=['asset_too_small', 'none'] (support≥8)
- **narrowed: S1** — S1=True S2=False S3=False; reliable=[] blind=['asset_too_small', 'none'] (support≥8)
- **grounded: S1** — S1=True S2=False S3=True; reliable=['structure_alignment_error'] blind=['none'] (support≥8)
- **describe_classify: S1** — S1=True S2=False S3=False; reliable=[] blind=['asset_too_small', 'none'] (support≥8)

## Prompt-gradient curve (constraint → reliability)

| variant | accuracy | κ | top1_share | none_recall | FP_text_overload | FP_space_imbalance | verdict |
|---|---|---|---|---|---|---|---|
| direct | 0.133 | 0.06 | 0.7 | 0.0 | 0.0 | 0.724 | S1 |
| narrowed | 0.167 | 0.082 | 0.667 | 0.0 | 0.033 | 0.672 | S1 |
| grounded | 0.267 | 0.138 | 0.5 | 0.0 | 0.0 | 0.138 | S1 |
| describe_classify | 0.133 | 0.078 | 0.867 | 0.0 | 0.0 | 0.862 | S1 |

## A/B disagreements (for adjudication)

- `20260609_024001_Generalist_Reward_Models_Found` A=asset_too_small B=space_imbalance
- `20260609_024834_Revisiting_Hallucination_Detec` A=none B=space_imbalance
- `20260609_024836_Know_Your_Limits_A_Survey_of_A` A=none B=space_imbalance
- `20260609_025220_Is_Chain-of-Thought_Reasoning_` A=asset_too_small B=structure_alignment_error
- `20260609_041103_InfiFusion_A_Unified_Framework` A=none B=asset_too_small