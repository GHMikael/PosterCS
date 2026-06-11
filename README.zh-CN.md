[English](README.md) | **简体中文**

# PosterCS — 论文转海报后端 + SVFP 审计协议

> **状态: v7 — S1 诊断完成，P1 布局修复落地。** 可控的 CS 海报生成基座 + 系统性评估 VLM 视觉批评可靠性的 **SVFP 审计协议**。

输入一篇 CS 论文 PDF，产出可编辑的会议海报 PPTX：
**docling 抽取图文 → Dify Chatflow 规划 → 内容自适应渲染（确定性几何规则驱动）。**

---

## 设计原则

> **几何可判的 → 确定性代码。语义/内容的 → LLM/VLM。**

这条原则贯穿整个系统，且有实证支撑：
- **audit v2 (new60)**：60 张海报、双人金标（κ=0.864）→ VLM 整图 critic 准确率 **0.083**（先验基线 0.583），对主导真实缺陷的 recall = **0.0**。
- **残余缺陷全为几何/代码可修**：`structure_alignment_error`、`asset_too_small`、`space_imbalance`。语义类缺陷（`text_overload`、`asset_mismatch`、`hierarchy_emphasis_error`）为 **零**——生成优化已消除。
- **P1 修复**：动态 spotlight grid（不对称 2.19"→0.00"）、宽高比感知 `fig_ratio`（图片面积最大 +500%）、稀疏 panel 字体缩放。
- **结论**：确定性几何规则直接嵌入渲染器 **优于 VLM 事后 critic 闭环**——更可靠、可审计、零 API 成本。

---

## 研究定位

**论文的核心贡献是 SVFP 审计协议**——一套标准化方法论，用于评估 VLM 视觉批评是否可靠。我们用它在 Qwen3-VL-32B 上验证并得出否定结论。该协议可迁移至任何 VLM critic（GPT-4o、Gemini、Paper2Poster 的 commenter）。

**关键证据：**

| 指标 | 数值 |
|---|---|
| 双人金标 κ (A/B) | **0.864** |
| VLM 准确率 (direct) | 0.083 |
| VLM 准确率 (narrowed) | 0.167 |
| 先验基线准确率 | 0.583 |
| recall(asset_too_small) | 0.0 |
| recall(none) — VLM 从不说"好" | 0.0 |
| 判决 | **S1 — VLM critic 不可靠** |

完整诊断报告：[`docs/audit/AUDIT_V2_FINDINGS.md`](docs/audit/AUDIT_V2_FINDINGS.md)

---

## 流程

```
PDF ──/extract_pdf_assets──►  文本 + 图 (docling; fitz 兜底)
                                   │
        Dify Chatflow (planneragent_v2) ──► PosterTask JSON (panels, figures, headline)
                                   │
        内容自适应渲染器 ──► 可编辑 PPTX
          · content_spans, 长宽比感知图布局, headline 焦点行
          · 4 模板 × 4 配色, storyflow 紧凑标题 (v7)
                                   │
                        final.pptx + run_report.json
```

实验从**冻结的 planner 快照**重放以保证可复现。

---

## 已有能力

| 模块 | 能力 |
|---|---|
| **抽取** | docling 语义抽取（图+表，含矢量）；fitz 兜底 |
| **规划** | Dify Chatflow → `PosterTask`，每 panel 带 `headline` |
| **渲染器** | 内容自适应 `content_spans`；图按长宽比布局；storyflow 紧凑标题栏；4 模板 × 4 配色 |
| **评测** | 16 指标 (A/B/C/D/E) + baseline 矩阵 |
| **审计** | SVFP 审计协议：6 类 taxonomy、双人金标、几何规则、VLM 标注、全指标体系、S1/S2/S3 判决 |
| **测试** | 81 测试通过 |

---

## 快速开始

```bash
cd PosterCS
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # DASHSCOPE_API_KEY
unset VIRTUAL_ENV             # macOS 必需
.venv/bin/python -m app.main
curl http://127.0.0.1:8000/health
```

---

## 实验

```bash
python -m experiments.scripts.run_matrix --papers experiments/configs/papers_30.json \
  --baselines ours_no_svfp,ours_svfp
```

审计流水线：`experiments/scripts/run_audit_v2.py` → `experiments/scripts/analyze_audit_v2.py` → `docs/audit/AUDIT_V2_FINDINGS.md`

P1 修复后批量重渲染：`experiments/scripts/render_fixed_batch.py` → `outputs/runs_fixed/`

---

## 测试

```bash
unset VIRTUAL_ENV && PYTHONPATH=. .venv/bin/python -m pytest experiments/tests/ -q
```

## 文档地图

| 文档 | 内容 |
|---|---|
| **README**（本文件） | 概览、设计原则、快速开始 |
| [`docs/design/项目现状与最终方向_v7.md`](docs/design/项目现状与最终方向_v7.md) | **当前状态 (v7)——权威来源** |
| [`docs/audit/AUDIT_V2_FINDINGS.md`](docs/audit/AUDIT_V2_FINDINGS.md) | **审计 v2 结果：S1 判决 + 全指标** |
| [`docs/audit/AUDIT_V2_REGROUND_SPEC.md`](docs/audit/AUDIT_V2_REGROUND_SPEC.md) | 审计设计 spec（taxonomy、阈值） |
| [`docs/design/SVFP_ISSUE_TAXONOMY_v5.md`](docs/design/SVFP_ISSUE_TAXONOMY_v5.md) | Taxonomy 设计 + 路由（⚠️ 与代码有差异，见内注） |
| [`docs/design/PROJECT_OPTIMIZATION_DIRECTION_v4.md`](docs/design/PROJECT_OPTIMIZATION_DIRECTION_v4.md) | 历史路线图 (pre-new60) |
| [`docs/progress/含金量分析评估.md`](docs/progress/含金量分析评估.md) | 战略价值分析 |

## 说明

`.env`、`outputs/`、`*.pptx`、`zcache/`、`experiments/results/` 产物已 gitignore。`datasets/planner_cache/*.json`（冻结快照）与审计金标/JSON 证据已提交以便复现。
