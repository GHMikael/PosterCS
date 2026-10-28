# Appendix B. Reproducibility record

## B.1 Frozen VLM interface

All VLM calls request a structured JSON audit with the same nine-label taxonomy, severity scale, localized evidence field, confidence field, and one primary issue. The runner validates each response against `06_inference/protocol/prediction_schema.json` before it can enter a scored result. Invalid responses and transport failures are preserved as attempts; only a later valid response for the same task can complete that task.

| Configuration key | Provider/model | Prompt | Temperature | Input condition |
|---|---|---|---:|---|
| `gemini_flash` | Gemini `gemini-3.8-flash` | P2 taxonomy | 0 | image-only |
| `qwen_vl_8b` | SiliconFlow `Qwen/Qwen3-VL-8B-Instruct` | P1/P2/P3 | 0 | image-only |
| `qwen_vl_32b` | SiliconFlow `Qwen/Qwen3-VL-32B-Instruct` | P1/P2/P3 | 0 | image-only |
| `glm_vl_flash` | Zhipu `glm-4.6v-flash` | P1/P2/P3 | 0 | image-only |

API credentials are supplied only through environment variables and are neither stored in manifests nor released. The model configuration is `06_inference/configs/models.yaml`; P1, P2, and P3 are kept under `06_inference/prompts/`.

## B.2 Formal-88 execution

Formal inference was frozen as `formal88_v1_20260924` and run after Gold freeze. The planned workload was 88 images × 4 models × 3 prompts = 1,056 tasks. The primary batch yielded 1,054 valid results; a missing-only supplementary batch recovered the two GLM tasks that initially encountered repeated 429 responses. The merged output contained 1,056 unique valid predictions, no missing tasks, no unexpected tasks, and no final schema/semantic validation failure.

The main frozen record is `06_inference/protocol/FORMAL_FREEZE_v1.json`. It hashes the formal configuration, model configuration, all prompts, prediction schema, label definitions, runner, providers, locked requirements, and the Formal-88 image manifest. `FORMAL_RUN_REPORT_v1.md` records attempted-call recovery, aggregate token counts, latency, and cost estimates.

## B.3 C48-Confirm execution

C48-Confirm uses frozen `rule_v1.json` and `hybrid_routing_policy_v1.json`, controlled Gold, and 24 accepted pairs. The controlled scoring manifest confirms that Gold is loaded only at scoring. It reports the exact frozen asset, source, rule, policy, and evaluation inputs. Source-aware systems receive PPTX-derived structural features, whereas image-only VLMs receive only the rendered poster; this is an intentional end-to-end systems comparison, not an equal-input capability claim.

## B.4 External-Natural-20 execution

Gold was frozen before external inference. A raw high-resolution transmission feasibility check was excluded from analysis before any prediction content was examined. The final external run uses an image-only derived manifest in which every source poster is resized with Lanczos interpolation to a maximum long side of 2400 px, preserving aspect ratio with no crop or stretch. Both Gemini-P2 and Qwen32B-P3 receive the same derived PNG pixels.

Gemini completed 20/20 predictions in one run. Qwen completed ten valid predictions before a manual process interruption and recovered the ten missing items in a missing-only continuation, with the same config, prompt, manifest, and code hashes. The combined result has one valid prediction for each of 20 unique samples and no failed final task. The two Qwen run manifests retain this recovery provenance. The external scorer uses the frozen Gold only after inference, records all per-sample predictions, and states its macro-F1 rule: average over labels with Gold support greater than zero.

## B.5 Reproduction procedure

1. Verify the applicable freeze manifest and all listed SHA-256 values.
2. Install the locked inference environment and expose credentials via the documented environment-variable names.
3. Run the image-only manifest with the frozen config and prompts.
4. Preserve every raw attempt and validate structured outputs before scoring.
5. Score only after Gold freeze, using the versioned scoring script and Gold CSV.
6. For interrupted runs, create a missing-only continuation rather than overwriting completed predictions.

The external scripts and records are under `08_rule_hybrid_repair/09_external_natural20/`; the formal runner is under `06_inference/`; controlled confirmation records are under `08_rule_hybrid_repair/06_hybrid_test68/controlled48/`.
