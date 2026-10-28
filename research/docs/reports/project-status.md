# PosterCS 论文项目状态

更新日期：2026-10-10

## 已完成且无需重做

- 缺陷 taxonomy 与标注规则已经过多轮修订并冻结。
- Formal-88 金标准、模型梯度和三种 Prompt 的探索性实验已经完成。
- RuleDev 数据、连续特征、阈值选择和 source-aware rule 已经完成。
- Controlled-48 的配对确认实验已经完成。
- External-Natural-20 的双人标注、仲裁和外部检查已经完成。
- Gemini 与 Qwen 的重复运行稳定性分析已经完成。
- 初稿、补充材料、论文图表以及两轮模拟审稿已经形成。
- 旧研究目录已完整归档，新工作区已建立并通过数据清单预检。

## 当前阶段

当前不是继续扩数据或继续人工标注，而是进入 **IJDAR Journal Track 投稿准备阶段**。目标截止时间为 **2026-11-15（AoE）**。核心实验、金标准和两轮模拟审稿均已结束；现在只处理定向写作、引用核验、投稿格式和作者声明。

## 本轮已经完成

- 核验 IJDAR scope，确认本文对应 Performance Evaluation、Physical and Logical Analysis、Document Models 和 Implementations/Applications/Systems。
- 核验 ICDAR 2027 — IJDAR Journal Track 截止时间及审稿流程。
- 核验并加入最近邻 IJDAR 论文 Kim et al. (2026)，明确其 VLM-OCR hallucination/routing 与本文 poster-audit counterfactual protocol 的区别。
- 英文摘要已改为 IJDAR 要求的 Purpose / Methods / Results / Conclusion 结构，共 229 词。
- 英文关键词已收缩为 6 个，满足 IJDAR 的 4–6 个要求。
- 图、补充材料和 BibTeX 路径已切换到当前 `research/paper/` 目录，路径检查全部通过。
- 当前 23 个文内引用均能在 `references.bib` 中找到对应条目。

## 下一阶段任务

1. 完成全稿 citation audit，逐条核验 DOI、出处和正文支持关系。
2. 检查现有四张主图在 IJDAR 双栏 84 mm / 174 mm 宽度下是否仍可读；只补真正承担论证任务的案例图。
3. 转换为 Springer Nature LaTeX `iicol`，生成 20 页以内的投稿 PDF。
4. 由作者补齐作者单位、通讯作者、ORCID、基金、利益冲突、数据可用性和 AI 使用声明。
5. 进行一次 IJDAR 定向模拟审稿，只修投稿阻断项，不再次扩展研究范围。

完整安排见 [`paper/reviews/ijdar-revision-roadmap.md`](../../paper/reviews/ijdar-revision-roadmap.md)。

## 暂不做

- 不重新标注已经终审的数据。
- 不重新调 Controlled-48 上的阈值。
- 不把 Hybrid 写成已经证明全面优于所有单一 VLM；目前应强调证据通道互补和可控路由。
- 不为整理目录而重跑昂贵 API 实验。
