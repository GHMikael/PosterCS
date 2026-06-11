**English** | [简体中文](README.zh-CN.md)

# PosterCS — Paper-to-Poster Backend + SVFP Audit Protocol

> **Status: v7 — S1 diagnosis complete, P1 layout fixes landed.** A controllable CS-poster generation substrate + the **SVFP Audit Protocol** for systematically evaluating VLM visual critic reliability.

The system turns a CS paper PDF into an editable conference poster PPTX:
**docling asset extraction → Dify Chatflow planning → content-adaptive PPTX renderer with deterministic geometry rules.**

---

## Design principle

> **Geometry-decidable → deterministic code. Semantic/content → LLM/VLM.**

This principle runs through the whole system and is backed by empirical evidence:
- **audit v2 (new60)** on 60 posters with dual-human gold (κ=0.864) found: VLM holistic critic accuracy = **0.083** (prior baseline = 0.583), recall on the dominant real defect = **0.0**.
- **All residual defects are geometry/code-fixable**: `structure_alignment_error`, `asset_too_small`, `space_imbalance`. Semantic defects (`text_overload`, `asset_mismatch`, `hierarchy_emphasis_error`) are **zero** — eliminated by generation improvements.
- **P1 fixes** (dynamic spotlight grid, aspect-aware `fig_ratio`, sparse-panel font scaling) reduced asymmetry 2.19"→0.00", increased figure sizes +70–500%, and brought gold `none` toward 58/60.
- **Conclusion**: deterministic geometry rules baked into the renderer **outperform VLM post-hoc critic loops** — more reliable, auditable, and zero API cost.

---

## Research framing

**The paper's core contribution is the SVFP Audit Protocol** — a standardized methodology for evaluating whether VLM visual critics are reliable. We applied it to Qwen3-VL-32B and found it isn't. The protocol itself is transferable to any VLM critic (GPT-4o, Gemini, Paper2Poster's commenter).

**Key evidence:**
| Metric | Value |
|---|---|
| Gold: dual-human κ (A/B) | **0.864** |
| VLM accuracy (direct) | 0.083 |
| VLM accuracy (narrowed) | 0.167 |
| Prior baseline accuracy | 0.583 |
| recall(asset_too_small) | 0.0 |
| recall(none) — VLM never says "good" | 0.0 |
| Verdict | **S1 — VLM critic unreliable** |

**Where to read the full diagnosis:** [`docs/audit/AUDIT_V2_FINDINGS.md`](docs/audit/AUDIT_V2_FINDINGS.md)

---

## Pipeline

```
PDF ──/extract_pdf_assets──►  text + figures (docling; fitz fallback)
                                   │
        Dify Chatflow (planneragent_v2) ──► PosterTask JSON (panels, figures, headline)
                                   │
        content-adaptive renderer ──► editable PPTX
          · content_spans, aspect-aware figure layout, headline focal line
          · 4 templates × 4 themes, compact storyflow header (v7)
                                   │
                        final.pptx + run_report.json
```

Experiments replay **frozen planner snapshots** (`datasets/planner_cache/*.json`) for reproducibility.

---

## What works

| Area | Capability |
|---|---|
| **Extraction** | docling semantic extraction (figures + tables, incl. vector); fitz fallback |
| **Planning** | Dify Chatflow → `PosterTask` with per-panel `headline` |
| **Renderer** | content-adaptive `content_spans`; figure layout by aspect ratio; storyflow compact header; 4 templates × 4 themes |
| **Evaluation** | 16 metrics (A/B/C/D/E) + baseline matrix |
| **Audit** | SVFP Audit Protocol: 6-class taxonomy, dual-human gold, geometric rules, VLM labeling, full metric suite, S1/S2/S3 verdict |
| **Tests** | 81 tests passing |

---

## Quick start

```bash
cd PosterCS
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # DASHSCOPE_API_KEY
unset VIRTUAL_ENV             # required on macOS
.venv/bin/python -m app.main
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

---

## Experiments

| Baseline | Isolates |
|---|---|
| `ours_svfp` | full SVFP closed loop |
| `ours_no_svfp` | same renderer, no feedback |
| `paper2poster` / `posteragent` | external SOTA reference |

```bash
python -m experiments.scripts.run_matrix --papers experiments/configs/papers_30.json \
  --baselines ours_no_svfp,ours_svfp
```

The audit pipeline: `experiments/scripts/run_audit_v2.py` → `experiments/scripts/analyze_audit_v2.py` → `docs/audit/AUDIT_V2_FINDINGS.md`.

P1-fixed batch re-render: `experiments/scripts/render_fixed_batch.py` → `outputs/runs_fixed/`.

---

## Documentation map

| Doc | Content |
|---|---|
| **README** (this file) | Overview, design principle, quick start |
| [`docs/design/项目现状与最终方向_v7.md`](docs/design/项目现状与最终方向_v7.md) | **Current status (v7) — authoritative** |
| [`docs/audit/AUDIT_V2_FINDINGS.md`](docs/audit/AUDIT_V2_FINDINGS.md) | **Audit v2 results: S1 verdict + full metrics** |
| [`docs/audit/AUDIT_V2_REGROUND_SPEC.md`](docs/audit/AUDIT_V2_REGROUND_SPEC.md) | Audit design spec (taxonomy, thresholds) |
| [`docs/design/SVFP_ISSUE_TAXONOMY_v5.md`](docs/design/SVFP_ISSUE_TAXONOMY_v5.md) | Taxonomy design + routing (⚠️ code differs — see notes) |
| [`docs/design/PROJECT_OPTIMIZATION_DIRECTION_v4.md`](docs/design/PROJECT_OPTIMIZATION_DIRECTION_v4.md) | Historical roadmap (pre-new60) |
| [`docs/progress/含金量分析评估.md`](docs/progress/含金量分析评估.md) | Strategic value analysis |

---

## Key env vars

| Variable | Purpose |
|---|---|
| `DASHSCOPE_API_KEY` | Qwen-VL via SiliconFlow |
| `QWEN_VL_MODEL` | VLM model (default `Qwen/Qwen3-VL-32B-Instruct`) |
| `POSTER_USE_DOCLING` | `0` to fall back to fitz |

---

## Tests

```bash
unset VIRTUAL_ENV && PYTHONPATH=. .venv/bin/python -m pytest experiments/tests/ -q
```

## Notes

`.env`, `outputs/`, `*.pptx`, `zcache/`, `experiments/results/` artifacts are gitignored. `datasets/planner_cache/*.json` (frozen snapshots) and audit gold/JSON evidence are committed for reproducibility.
