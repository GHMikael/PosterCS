# Appendix A. Gold provenance, annotation, and freeze record

## A.1 Purpose and scope

This appendix distinguishes (i) human Gold used to score naturally occurring defects from (ii) verified injected targets used in counterfactual control/mutation pairs. Candidate machine annotations, where present, were an interface aid only. They were never treated as an independent annotator or as Gold.

## A.2 Formal-88

Formal-88 contains 40 natural posters and 48 controlled posters. The natural component comprises 20 previously unseen papers, each rendered as an original and a renderer-v0.6 version. The controlled component comprises 24 base posters, each with a clean control and one single-defect mutation.

For Natural-40, annotator A reviewed all 40 posters. Annotator B independently blind-annotated a stratified 20-poster subset; B did not see candidate labels, A's labels, Rule outputs, or VLM outputs. Thirteen disagreements were adjudicated. Five apparent agreements were blind-spot-checked, and one additional difference discovered in that spot check was adjudicated. The remaining 20 non-double-coded posters retain A's reviewed labels as Gold. The independent subset had primary raw agreement 0.400, exact label-set agreement 0.400, mean label Jaccard 0.658, and severity exact agreement 0.818 over 22 common-label instances. These values describe a difficult operational labeling task rather than a claim of universal aesthetic agreement.

For Controlled-48, the intended label comes from an injection manifest, but every pair underwent human acceptance. A pair was retained only if the target defect was visible at the defined viewing condition, the control lacked that target defect, and the mutation did not add a primary confound. There are four accepted pairs for each of six actionable labels: `body_text_too_small`, `figure_detail_unreadable`, `text_overload`, `space_imbalance`, `alignment_error`, and `overlap_or_clipping`.

The frozen Formal-88 manifest reports 13 A/B-adjudicated natural rows, 6 A/B-agreement natural rows, 1 consensus-spot-check-adjudicated natural row, 20 A-reviewed natural rows, 24 verified controls, and 24 verified injections. The final Gold CSV SHA-256 is `b26afb930f0997f948b7a4fc7d6830c2111c0f7d543bb5d47a2b4e4c445c6750`.

## A.3 C48-Confirm

C48-Confirm is the frozen controlled confirmation set used for the five-system comparison. It contains 24 accepted control/mutation pairs (48 images), across four layouts (`magazine`, `sidebar_grid`, `horizontal_bands`, and `mosaic`) that were held out from RuleDev. Every actionable label has two moderate and two severe mutations. The controlled freeze was created on 2026-09-28 after automated QA passed and all 24 pairs completed human acceptance. Its freeze manifest records PNG and PPTX SHA-256 values per sample, along with hashes for the injection manifest, feature extraction outputs, acceptance file, controlled Gold, and QA report.

The controlled Gold file is `08_rule_hybrid_repair/06_hybrid_test68/controlled48/controlled_gold_v1.csv`; the governing freeze record is `controlled48_freeze_manifest_v1.json`. No Rule, VLM, or Hybrid prediction was used to select retained pairs.

## A.4 External-Natural-20

External-Natural-20 is a post-freeze external check using 20 author-created conference posters sampled deterministically from the Paper2Poster dataset at revision `1dd57d40186caa38b71b766ad9ac08f3e801e4cb`. It is not an evaluation of source-aware rules or Hybrid-v1, because those posters have no corresponding editable PPTX source structure.

Annotator A blind-labeled all 20 posters. Annotator B independently blind-labeled a stratified subset of 10. Label-set and primary-label agreement were both 9/10; two disagreements were adjudicated. Final Gold contains eight `body_text_too_small`, seven `figure_detail_unreadable`, six `text_overload`, and one `space_imbalance` moderate/severe labels; eight posters have no Gold issue. The frozen Gold file is `external_natural20_gold_v1.csv`; the Gold-freeze manifest is `external_natural20_gold_freeze_manifest_v1.json`.

## A.5 Leakage controls

1. Gold files, raw human records, and model predictions are stored separately.
2. VLM runners load an image-only manifest and record `gold_loaded: false`.
3. Human B and adjudication interfaces do not show candidate, Rule, Hybrid, or VLM outputs.
4. Gold is frozen before formal or external inference; no prompt, model, threshold, or routing choice is changed after inspecting scored results.
5. Every freeze record includes file hashes so that later scoring can identify its exact inputs.

## A.6 Source files

| Artifact | Location |
|---|---|
| Formal protocol | `05_formal_experiment/FORMAL_DATASET_PROTOCOL_v2.md` |
| Formal Gold freeze | `05_formal_experiment/formal88_freeze_manifest.json` |
| C48 protocol and freeze | `08_rule_hybrid_repair/06_hybrid_test68/HYBRID_TEST_PROTOCOL_v1.md`; `controlled48/controlled48_freeze_manifest_v1.json` |
| External protocol, agreement, Gold and results | `08_rule_hybrid_repair/09_external_natural20/` |
