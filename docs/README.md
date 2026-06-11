# PosterCS 文档索引

> 当前版本 **v7** (2026-06-12)。权威状态文档：[`docs/design/项目现状与最终方向_v7.md`](design/项目现状与最终方向_v7.md)

## audit/ — audit v2 (new60) 诊断重审计

- [AUDIT_V2_FINDINGS.md](audit/AUDIT_V2_FINDINGS.md) — **最权威的结果报告：S1 判决 + gold 分布 + VLM vs gold 全指标**（自动生成）
- [AUDIT_V2_REGROUND_SPEC.md](audit/AUDIT_V2_REGROUND_SPEC.md) — 审计设计 spec（6 类 taxonomy + 2 几何规则 + 判定阈值）
- [AUDIT_V2_IMPLEMENTATION_PLAN.md](audit/AUDIT_V2_IMPLEMENTATION_PLAN.md) — 实现计划（Phase 0–4）
- [AUDIT_V2_ANNOTATION_GUIDE.md](audit/AUDIT_V2_ANNOTATION_GUIDE.md) — 标注者守则

## design/ — 方向 / 分类 / 布局设计

- **[项目现状与最终方向_v7.md](design/项目现状与最终方向_v7.md) ← 当前状态（权威）**
- [SVFP_ISSUE_TAXONOMY_v5.md](design/SVFP_ISSUE_TAXONOMY_v5.md) — taxonomy 设计草案 + 路由检测（⚠️ 权威定义在 `experiments/audit/taxonomy.py`）
- [LAYOUT_DESIGN_v2.md](design/LAYOUT_DESIGN_v2.md) — 内容自适应布局设计
- [PROJECT_OPTIMIZATION_DIRECTION_v4.md](design/PROJECT_OPTIMIZATION_DIRECTION_v4.md) — 原始方向总纲（⚠️ pre-new60 历史文档）

## progress/ — 阶段进度 / 价值分析（⚠️ 历史文档）

- [项目优化进度与成果总结_2026-06-07.md](progress/项目优化进度与成果总结_2026-06-07.md) — ⚠️ pre-new60 历史
- [含金量分析评估.md](progress/含金量分析评估.md) — 🟡 战略定位仍有效，部分细节过时

### 历史版本
- [项目现状与最终方向_v6.md](design/项目现状与最终方向_v6.md) — 被 v7 替代，保留供参考

## 关键文件路径

| 功能 | 路径 |
|------|------|
| Taxonomy 权威定义 | `experiments/audit/taxonomy.py` |
| VLM 标注器 | `experiments/audit/vlm_labeler.py` |
| 几何规则检测 | `experiments/audit/geom_rules.py` |
| 审计指标 | `experiments/audit/metrics_v2.py` |
| 审计分析脚本 | `experiments/scripts/analyze_audit_v2.py` |
| P1 修复批量重渲染 | `experiments/scripts/render_fixed_batch.py` |
| 渲染器（P1 修复已落地） | `app/ppt_renderer.py` |
| 金标数据（已仲裁） | `datasets/gold/audit_v2_labels_annotatorA.csv` |
| 审计结果目录 | `experiments/results/audit_v2_new60/` |
| P1 修复后重渲染 | `outputs/runs_fixed/` |
| 开题报告 | `/Users/mikaelsnow/Documents/ECNU/开题/` |
