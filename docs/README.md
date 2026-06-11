# PosterCS 文档索引

根目录只保留 `README.md` / `README.zh-CN.md`;其余文档按主题归到这里。

## audit/ — audit v2(new60)诊断重审计
- [AUDIT_V2_REGROUND_SPEC.md](audit/AUDIT_V2_REGROUND_SPEC.md) — 重审计设计 spec(6 类 taxonomy + 2 几何规则 + 判定阈值)
- [AUDIT_V2_IMPLEMENTATION_PLAN.md](audit/AUDIT_V2_IMPLEMENTATION_PLAN.md) — 实现计划(Phase 0-4)
- [AUDIT_V2_ANNOTATION_GUIDE.md](audit/AUDIT_V2_ANNOTATION_GUIDE.md) — 给标注者的守则
- [AUDIT_V2_FINDINGS.md](audit/AUDIT_V2_FINDINGS.md) — **当前最权威的结果报告：S1 判决 + gold 分布 + VLM vs gold 全指标**(脚本生成)

## design/ — 方向 / 分类 / 布局设计
- **[项目现状与最终方向_v7.md](design/项目现状与最终方向_v7.md) ← 当前状态**(2026-06-11 更新，替代 v6)
- [SVFP_ISSUE_TAXONOMY_v5.md](design/SVFP_ISSUE_TAXONOMY_v5.md) — taxonomy 设计草案 + 路由检测（⚠️ 已加实际落地差异标注；权威定义在 `experiments/audit/taxonomy.py`）
- [LAYOUT_DESIGN_v2.md](design/LAYOUT_DESIGN_v2.md) — 内容自适应布局设计
- [PROJECT_OPTIMIZATION_DIRECTION_v4.md](design/PROJECT_OPTIMIZATION_DIRECTION_v4.md) — 原始方向总纲（⚠️ pre-new60，路线 P0-P7 未更新）

## progress/ — 阶段进度 / 价值分析（⚠️ pre-new60 历史文档）
- [项目优化进度与成果总结_2026-06-07.md](progress/项目优化进度与成果总结_2026-06-07.md) — ⚠️ 旧48张审计年代，待重审计/第二标注者等全部已做完
- [含金量分析评估.md](progress/含金量分析评估.md) — 🟡 战略定位仍有效，部分细节过时

### 历史版本
- [项目现状与最终方向_v6.md](design/项目现状与最终方向_v6.md) — 被 v7 替代，保留供参考
