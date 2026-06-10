# Audit v2 (new60) — Findings

> Gold = annotatorA (user). Inter-annotator A/B κ = **0.723** (60 common, 11 disagreements).

## Gold distribution (human)

| class | n |
|---|---|
| space_imbalance | 2 |
| asset_too_small | 14 |
| structure_alignment_error | 14 |
| none | 28 |
| other | 2 |

**Per template (gold):**

- `template_dashboard`: {'space_imbalance': 1, 'asset_too_small': 2, 'none': 13, 'other': 2}
- `template_classic`: {'space_imbalance': 1, 'asset_too_small': 6, 'none': 15}
- `template_storyflow`: {'structure_alignment_error': 14, 'asset_too_small': 5}
- `template_minimal`: {'asset_too_small': 1}

## Objective geom rules

- contrast: all themes WCAG-AA = **True** → any VLM `low_contrast` is a false positive.
- overlap: 20/60 posters have ≥1 partial collision (rest clean).

## VLM vs gold

| metric | direct | narrowed |
|---|---|---|
| accuracy | 0.083 | 0.167 |
| prior baseline | 0.467 | 0.467 |
| κ(VLM,gold) | 0.016 | 0.089 |
| VLM top-1 share | 0.767 | 0.7 |
| VLM label entropy | 0.605 | 0.651 |
| recall(none) | 0.0 | 0.0 |
| FP rate space_imbalance | 0.793 | 0.707 |
| FP rate text_overload | 0.0 | 0.033 |

**Per-class recall (VLM vs gold):**

| class | gold_support | recall(direct) | recall(narrowed) |
|---|---|---|---|
| space_imbalance | 2 | 0.0 | 0.5 |
| asset_too_small | 14 | 0.0 | 0.0 |
| structure_alignment_error | 14 | 0.357 | 0.643 |
| none | 28 | 0.0 | 0.0 |
| other | 2 | 0.0 | 0.0 |

## Verdict

- **direct: S1** — S1=True S2=False S3=False; reliable=[] blind=['asset_too_small', 'none'] (support≥8)
- **narrowed: S1** — S1=True S2=False S3=False; reliable=[] blind=['asset_too_small', 'none'] (support≥8)

## A/B disagreements (for adjudication)

- `20260609_023510_Seeing,_Listening,_Remembering` A=asset_too_small B=none
- `20260609_024001_Generalist_Reward_Models_Found` A=asset_too_small B=space_imbalance
- `20260609_024834_Revisiting_Hallucination_Detec` A=none B=space_imbalance
- `20260609_024836_Know_Your_Limits_A_Survey_of_A` A=asset_too_small B=space_imbalance
- `20260609_025220_Is_Chain-of-Thought_Reasoning_` A=asset_too_small B=structure_alignment_error
- `20260609_031542_LeanRAG_Knowledge-Graph-Based_` A=asset_too_small B=none
- `20260609_031955_Multimodal_Retrieval-Reflectio` A=asset_too_small B=none
- `20260609_033644_AQA_Adaptive_Question_Answerin` A=asset_too_small B=none
- `20260609_034637_Building_Production-Ready_AI_A` A=other B=none
- `20260609_041103_InfiFusion_A_Unified_Framework` A=none B=asset_too_small
- `20260609_042935_A_Survey_of_Large_Language_Mod` A=asset_too_small B=none