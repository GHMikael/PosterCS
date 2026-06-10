[English](README.md) | **简体中文**

# PosterCS — 论文转海报后端 + SVFP

> **状态:v6 —— 第一个能用的版本。** FastAPI 后端 + Dify Chatflow 规划 + 确定性·内容自适应渲染器 + **SVFP**(结构化视觉反馈协议)闭环 + 可复现的 **CS-Poster-30** 评测套件(16 指标 + baseline 矩阵)。

输入一篇 CS 论文 PDF,产出可编辑的 A3 会议海报 PPTX:
**docling 抽取图文 → Dify Chatflow 规划(`PosterTask` JSON)→ 内容自适应 PPTX 渲染器 → 可选 SVFP 闭环(VLM 批评 → 确定性修复 → 收敛留痕)。**

---

## 设计原则(主线)

> **几何可判的交给确定性代码;语义/内容相关的交给 LLM/VLM。**

这条线贯穿整个系统和论文:
- **图表抽取**用 docling(版面理解模型)而非抓原始位图,矢量图 + 表格都不漏。
- **图的布局**(上下/左右、框多大)由渲染器按图的**真实长宽比**推导,不让 planner 猜。
- **SVFP 的诊断**(见下):整图 VLM critic 对版面不可靠,所以可靠修复必须按问题类型路由到真正有信号的检测器。

---

## 流程

```
PDF ──/extract_pdf_assets──►  文本 + 图(docling;fitz 兜底)
                                   │
        Dify Chatflow(planneragent_v2) ──► PosterTask JSON(panels、figures、headline)
                                   │
        内容自适应渲染器 ──► 可编辑 PPTX
          · content_spans:panel 尺寸随内容变(不再死六格)
          · 图布局按长宽比;headline = 每个 panel 的视觉焦点
                                   │
        可选 SVFP 闭环 ──► VLM 批评 → 确定性 FeedbackApplier → 收敛
                                   │
                          final.pptx + run_report.json(+ 供 c3 的 svfp_trace)
```

实验从**冻结的 planner 快照**(`datasets/planner_cache/*.json`)重放,保证各 baseline 在同一份 plan 上对比。

---

## v6 已能用的能力

| 模块 | 能力 |
|---|---|
| **抽取** | docling 语义抽取(图 **和表**,含矢量);fitz 兜底;`POSTER_USE_DOCLING=0` 可关 |
| **规划** | Dify Chatflow → `PosterTask`;`planneragent_v2.txt` 加每个 panel 的 `headline` + CS 结构化抽取;布局方向交渲染器 |
| **渲染器** | 内容自适应 `content_spans`(dashboard/classic/minimal);图按长宽比布局;`headline` 焦点行;4 模板 × 4 配色 |
| **SVFP 闭环** | 闭集 `{4 类 issue × 9 动作}` + 确定性 applier + 收敛检测(生产 = 旧 4 类 baseline,见下) |
| **评测** | **16 指标**(A 内容 / B 视觉 / C 协议 / D 效率 / E 外部)+ baseline 矩阵 + `compute_metrics`/`aggregate_stats`/`print_paper_table` |
| **异步** | 异步 job + 长轮询(适配 Dify);run 归档在 `outputs/runs/` |

---

## 研究定位(诚实)

**主发现 —— VLM 版面 critic 系统性不可靠(不是模型太小):**
- 规模消融(Qwen3-VL 8B/30B/32B,同 16 张):每个尺寸都**先验主导**(8B → 100% 单一标签;32B → text_overload 11/16),且**都找不到人工标注的图/asset 问题**(各尺寸 ≤1/12);窄提示词也只把 asset 召回提到 4/12。
- 真实 run 上 **`c3_issue_resolution_rate = 0.0`**:SVFP 检测到 8 个 issue、应用了动作,两轮**解决了 0 个**——量化了"VLM 能看见问题,但浅闭集动作修不动"。

**因此:** 可靠修复必须**按问题类型路由检测**——几何管空间/溢出/结构,脚本+图 caption+文本 LLM 管图文不匹配,VLM 只用在它可靠的地方(显著性/层级)。

**代码现状 vs 论文方向:**
- **生产 SVFP 闭环目前 = 旧 4 类、整图 VLM 的 baseline**(`overlapping_elements / empty_space / low_contrast / figure_too_small` × 9 动作)。`c3=0.0` 就是在它上面测的,即**基线 / 反例**。
- **5 类 MECE taxonomy + 路由检测 + 严重性门控**(论文的改进)已在 [`SVFP_ISSUE_TAXONOMY_v5.md`](docs/design/SVFP_ISSUE_TAXONOMY_v5.md) 里**设计好,但还没迁进生产闭环**。这是 v6 之后的首要任务。

完整状态 + 路线见 [`项目现状与最终方向_v6.md`](docs/design/项目现状与最终方向_v6.md)。

---

## 16 个指标

| 层 | 指标 |
|---|---|
| **A 内容保真** | `a1_key_info_recall` · `a2_hallucination_rate` · `a3_semantic_fidelity`(BERTScore) |
| **B 视觉质量** | `b1_layout_quality` · `b2_readability` · `b3_figure_reuse_rate` · `b4_figure_text_align` |
| **C 协议** | `action_executability`(c1,**真实测量**)· `convergence_rate`(c2)· `c3_issue_resolution_rate` · `per_iter_visual_gain`(c4) |
| **D 效率** | `d1_latency` · `d2_cost` |
| **E 外部** | `e1_paperquiz` · `e2_human_preference`(harness)· `e3_llm_judge`(默认关) |

C 类只适用于有反馈的臂(`ours_svfp` / `ours_freeform` / `gpt4o_zeroshot_svfp`),其余 N/A。`c1` 现在是 applier 数出来的 `executed/attempted`(不再写死),`c3` 读每轮的 `svfp_trace`。

---

## 快速开始

```bash
cd PosterCS
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # DASHSCOPE_API_KEY(批量跑加 DIFY_*)
python -m app.main
curl http://127.0.0.1:8000/health
```

---

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 服务状态 |
| `POST` | `/extract_pdf_assets` | PDF → `asset_token` + 图 |
| `POST` | `/generate_ppt` | 异步生成(202 + `job_id`) |
| `GET` | `/jobs/{job_id}?wait=20` | 长轮询 job 状态 |
| `POST` | `/generate_ppt_file` | 同步生成(调试) |
| `GET` | `/download/run/{run_folder}` | 下载 `final.pptx` |
| `GET` | `/assets/{asset_token}/{filename}` | 抽取的图 |

---

## 实验

| Baseline | 隔离什么 |
|---|---|
| `ours_svfp` | 完整 SVFP 闭环 |
| `ours_no_svfp` | 同渲染器,无反馈 |
| `ours_freeform` | 自由文本 VLM 批评 + LLM 应用(c1 对照臂) |
| `gpt4o_zeroshot` | 仅 LLM planner |
| `gpt4o_zeroshot_svfp` | zero-shot planner + SVFP(planner-agnostic 验证) |
| `paper2poster` / `posteragent` | 外部 SOTA 参照(待复现) |

```bash
python -m experiments.scripts.run_matrix --papers experiments/configs/papers_30.json \
  --baselines ours_no_svfp,ours_freeform,ours_svfp,gpt4o_zeroshot_svfp
python -m experiments.scripts.compute_metrics --all
python -m experiments.scripts.aggregate_stats --out experiments/results/aggregate/
python -m experiments.scripts.print_paper_table
```

失败 taxonomy 审计 + 诊断分析在 `experiments/audit/` 和 `experiments/scripts/analysis_*.py` / `ablation_*.py`。

---

## 主要环境变量

| 变量 | 用途 |
|---|---|
| `DASHSCOPE_API_KEY` | Qwen-VL critic + judges(SiliconFlow) |
| `QWEN_VL_MODEL` | VLM 模型 id(默认 `Qwen/Qwen3-VL-32B-Instruct`) |
| `POSTER_USE_DOCLING` | `0` 退回 fitz 抽取 |
| `POSTER_LLM_TIMEOUT_S` | 文本/VLM 调用超时 |
| `DIFY_API_KEY` / `DIFY_BASE_URL` | 批量 Chatflow 触发 |

完整见 [`.env.example`](.env.example)。

---

## 文档地图

| 文档 | 内容 |
|---|---|
| **README**(本文) | 概览、流程、诚实定位、快速开始 |
| [`项目现状与最终方向_v6.md`](docs/design/项目现状与最终方向_v6.md) | **当前状态、做到哪/没做、可用 v1 验收清单、路线** |
| [`SVFP_ISSUE_TAXONOMY_v5.md`](docs/design/SVFP_ISSUE_TAXONOMY_v5.md) | 5 类 taxonomy + 路由检测设计(下一迭代) |
| [`LAYOUT_DESIGN_v2.md`](docs/design/LAYOUT_DESIGN_v2.md) | 内容自适应布局设计 |
| [`PROJECT_OPTIMIZATION_DIRECTION_v4.md`](docs/design/PROJECT_OPTIMIZATION_DIRECTION_v4.md) | 原始方向 + P0–P7 路线 |
| `experiments/scripts/METRIC_REFACTOR_PLAN.md` | 16 指标重构记录 |

---

## 测试

```bash
python -m pytest experiments/tests/ -q
```

## 说明

`.env`、`outputs/`、`*.pptx`、`zcache/`、`experiments/results/` 的重产物已 gitignore。`datasets/planner_cache/*.json`(冻结快照)与审计/诊断的 JSON 证据已提交以便复现。
