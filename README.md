**English** | [简体中文](README.zh-CN.md)

# PosterCS — Paper-to-Poster Backend + SVFP

> **Status: v6 — first usable release.** FastAPI backend + Dify Chatflow planner + a deterministic, content-adaptive renderer + the **SVFP** (Structured Visual Feedback Protocol) closed loop + a reproducible **CS-Poster-30** evaluation harness (16 metrics, baseline matrix).

Given a CS paper PDF, the system produces an editable A3 conference poster PPTX:
**docling asset extraction → Dify Chatflow planning (`PosterTask` JSON) → content-adaptive PPTX renderer → optional SVFP loop (VLM critique → deterministic repair → convergence trace).**

---

## Design principle (the spine)

> **Geometry-decidable things go to deterministic code; semantic/content things go to the LLM/VLM.**

This runs through the whole system and the paper:
- **Figure extraction** uses docling (a layout model) instead of raw raster grabbing, so vector figures + tables aren't lost.
- **Figure layout** (top-bottom vs left-right, box size) is derived from the figure's **true aspect ratio** in the renderer — the planner doesn't guess it.
- **The SVFP diagnosis** (below): a holistic VLM critic is unreliable for layout, so reliable repair must route each issue to the detector that actually has the signal.

---

## Pipeline

```
PDF ──/extract_pdf_assets──►  text + figures (docling; fitz fallback)
                                   │
        Dify Chatflow (planneragent_v2) ──► PosterTask JSON (panels, figures, headline)
                                   │
        content-adaptive renderer ──► editable PPTX
          · content_spans: panel sizes scale with content (no fixed 6-grid)
          · figure layout from aspect ratio; headline = per-panel visual focus
                                   │
        optional SVFP loop ──► VLM critique → deterministic FeedbackApplier → convergence
                                   │
                          final.pptx + run_report.json (+ svfp_trace for c3)
```

Experiments **replay frozen planner snapshots** (`datasets/planner_cache/*.json`) so baselines are compared on identical plans.

---

## What works in v6 (usable)

| Area | Capability |
|---|---|
| **Extraction** | docling semantic extraction (figures **and tables**, incl. vector); fitz fallback; `POSTER_USE_DOCLING=0` to disable |
| **Planning** | Dify Chatflow → `PosterTask`; `planneragent_v2.txt` adds per-panel `headline` + CS-structured extraction; layout direction left to the renderer |
| **Renderer** | content-adaptive `content_spans` (dashboard/classic/minimal); figure layout by aspect; `headline` focal line; 4 templates × 4 themes |
| **SVFP loop** | closed `{4 issues × 9 actions}` + deterministic applier + convergence detector (production = the 4-class baseline; see framing) |
| **Evaluation** | **16 metrics** (A content / B visual / C protocol / D efficiency / E external) + baseline matrix + `compute_metrics`/`aggregate_stats`/`print_paper_table` |
| **Async** | async jobs + long-polling for Dify; run archive under `outputs/runs/` |

---

## Research framing (honest)

**Primary finding — the VLM layout critic is systematically unreliable (not a small-model artifact):**
- Scale ablation (Qwen3-VL 8B/30B/32B, same 16 posters): every size is **prior-dominated** (8B → 100% one label; 32B → text_overload 11/16), and **none recovers the figure/asset problems a human flags** (≤1/12 at every scale). Narrowing the prompt only lifts asset recall to 4/12.
- **`c3_issue_resolution_rate = 0.0`** on a real run: SVFP detected 8 issues, applied actions, and resolved **0** across two iterations — quantifying "the VLM can see problems but shallow closed-set actions can't fix them."

**Therefore:** reliable repair must **route detection by issue type** — geometry for space/overflow/structure, a script + figure-caption + text-LLM check for figure–text mismatch, and the VLM only where it's reliable (saliency/hierarchy).

**Where the code is vs. where the paper is going:**
- **Production SVFP loop today = the old 4-class, holistic-VLM baseline** (`overlapping_elements / empty_space / low_contrast / figure_too_small` × 9 actions). This is what `c3=0.0` was measured on — i.e., the **baseline / counter-example**.
- **The 5-class MECE taxonomy + routed detection + severity-gating** (the paper's improvement) is **designed** in [`SVFP_ISSUE_TAXONOMY_v5.md`](SVFP_ISSUE_TAXONOMY_v5.md) but **not yet migrated into the production loop**. That migration is the top post-v6 task.

See [`项目现状与最终方向_v6.md`](项目现状与最终方向_v6.md) for the full status + roadmap.

---

## The 16 metrics

| Tier | Metrics |
|---|---|
| **A — content fidelity** | `a1_key_info_recall` · `a2_hallucination_rate` · `a3_semantic_fidelity` (BERTScore) |
| **B — visual quality** | `b1_layout_quality` · `b2_readability` · `b3_figure_reuse_rate` · `b4_figure_text_align` |
| **C — protocol** | `action_executability` (c1, **honestly measured**) · `convergence_rate` (c2) · `c3_issue_resolution_rate` · `per_iter_visual_gain` (c4) |
| **D — efficiency** | `d1_latency` · `d2_cost` |
| **E — external** | `e1_paperquiz` · `e2_human_preference` (harness) · `e3_llm_judge` (gated) |

C-class only applies to feedback arms (`ours_svfp`, `ours_freeform`, `gpt4o_zeroshot_svfp`); N/A elsewhere. `c1` is now `executed/attempted` measured by the applier (no longer hardcoded), `c3` reads the per-iteration `svfp_trace`.

---

## Quick start

```bash
cd PosterCS
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # DASHSCOPE_API_KEY (+ DIFY_* for batch runs)
python -m app.main
curl http://127.0.0.1:8000/health
```

---

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service status |
| `POST` | `/extract_pdf_assets` | PDF → `asset_token` + figures |
| `POST` | `/generate_ppt` | Async generation (202 + `job_id`) |
| `GET` | `/jobs/{job_id}?wait=20` | Long-poll job status |
| `POST` | `/generate_ppt_file` | Sync generation (debug) |
| `GET` | `/download/run/{run_folder}` | Download `final.pptx` |
| `GET` | `/assets/{asset_token}/{filename}` | Extracted figures |

---

## Experiments

| Baseline | Isolates |
|---|---|
| `ours_svfp` | full SVFP closed loop |
| `ours_no_svfp` | same renderer, no feedback |
| `ours_freeform` | free-text VLM critique + LLM apply (c1 comparison arm) |
| `gpt4o_zeroshot` | LLM planner only |
| `gpt4o_zeroshot_svfp` | zero-shot planner + SVFP (planner-agnostic test) |
| `paper2poster` / `posteragent` | external SOTA reference (repro pending) |

```bash
python -m experiments.scripts.run_matrix --papers experiments/configs/papers_30.json \
  --baselines ours_no_svfp,ours_freeform,ours_svfp,gpt4o_zeroshot_svfp
python -m experiments.scripts.compute_metrics --all
python -m experiments.scripts.aggregate_stats --out experiments/results/aggregate/
python -m experiments.scripts.print_paper_table
```

The failure-taxonomy audit + diagnosis analyses live in `experiments/audit/` and `experiments/scripts/analysis_*.py` / `ablation_*.py`.

---

## Key environment variables

| Variable | Purpose |
|---|---|
| `DASHSCOPE_API_KEY` | Qwen-VL critic + judges (SiliconFlow) |
| `QWEN_VL_MODEL` | VLM model id (default `Qwen/Qwen3-VL-32B-Instruct`) |
| `POSTER_USE_DOCLING` | `0` to fall back to fitz extraction |
| `POSTER_LLM_TIMEOUT_S` | request timeout for text/VLM calls |
| `DIFY_API_KEY` / `DIFY_BASE_URL` | batch Chatflow trigger |

See [`.env.example`](.env.example) for the full list.

---

## Documentation map

| Doc | Content |
|---|---|
| **README** (this file) | Overview, pipeline, honest framing, quick start |
| [`项目现状与最终方向_v6.md`](项目现状与最终方向_v6.md) | **Current status, done/not-done, usable-v1 checklist, roadmap** |
| [`SVFP_ISSUE_TAXONOMY_v5.md`](SVFP_ISSUE_TAXONOMY_v5.md) | 5-class taxonomy + routed-detection design (next iteration) |
| [`LAYOUT_DESIGN_v2.md`](LAYOUT_DESIGN_v2.md) | content-adaptive layout design |
| [`PROJECT_OPTIMIZATION_DIRECTION_v4.md`](PROJECT_OPTIMIZATION_DIRECTION_v4.md) | original direction + P0–P7 roadmap |
| `experiments/scripts/METRIC_REFACTOR_PLAN.md` | 16-metric refactor record |

---

## Tests

```bash
python -m pytest experiments/tests/ -q
```

## Notes

`.env`, `outputs/`, `*.pptx`, `zcache/`, heavy `experiments/results/` artifacts are gitignored. `datasets/planner_cache/*.json` (frozen snapshots) and the audit/diagnosis JSON evidence are committed for reproducibility.
