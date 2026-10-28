# IJDAR Journal Track 定向修订路线图

## 目标与截止时间

- **首投目标：** ICDAR 2027 — IJDAR Journal Track
- **投稿截止：** 2026-11-15（AoE）
- **当前日期：** 2026-10-10
- **剩余时间：** 36 天
- **当前稿件状态：** 核心实验已结束；两轮模拟审稿后为 Minor Revision / 内容冻结候选；本轮不默认增加新实验。

## 当前论文最准确的定位

本文是一篇面向 scientific poster auditing 的 evaluation-and-systems empirical study。主贡献不是提出一个新的 VLM，也不是证明 Hybrid 普遍优于单一方法，而是：

1. 用 control/mutation counterfactual pairs 同时测量缺陷敏感性与对干净海报的克制性；
2. 证明常规 recall/F1 可能掩盖 VLM 的 unsupported allegations；
3. 比较 raster、retained source structure 与 gated VLM judgment 三类证据通道的适用边界；
4. 给出一个可复现的 selective-routing 实例，并诚实报告其 sensitivity-specificity trade-off。

这与 IJDAR 的 Performance Evaluation、Physical and Logical Analysis、Document Models、Implementations/Applications/Systems 范围直接对应。

## 与最近邻 IJDAR 论文的关系

最近邻工作：Kim, Han, and Yang, “Hallucination-aware evaluation and confidence-guided selective routing for hybrid VLM-OCR: an empirical study on scene text and receipt documents,” IJDAR, 2026, DOI: 10.1007/s10032-026-00620-7。

| 维度 | Kim et al. 2026 | PosterCS 本文 |
|---|---|---|
| 文档任务 | OCR transcription | scientific-poster defect auditing |
| 主要风险 | visually unsupported text completion | unsupported visual defect allegation |
| 反事实/参照 | visible transcript vs full transcript | clean control vs single-defect mutation |
| 安全行为 | abstention / empty output | restraint / no allegation on clean control |
| 确定性通道 | PaddleOCR confidence | raster measures + retained PPTX structure |
| VLM 路由目的 | cost–accuracy control | semantic escalation under measurable gates |
| 主要结论 | routing 不是直接的 hallucination mitigation | Hybrid 不是普遍性能突破；source structure 是 specificity anchor |

因此，该论文应作为直接相关工作和写作范例引用。我们的差异必须在 Introduction、Related Work 和 Discussion 中明确写出，避免审稿人认为只是把 OCR routing 换成 poster routing。

## 本轮修订项目

| ID | 项目 | 动作 | 是否需要新实验 |
|---|---|---|---|
| IR-1 | IJDAR 摘要规范 | 改为 Purpose / Methods / Results / Conclusion，控制在 150–250 英文词 | 否 |
| IR-2 | 最近邻定位 | 引用 Kim et al. 2026，并明确 OCR unsupported completion 与 poster unsupported allegation 的差别 | 否 |
| IR-3 | 贡献边界 | 保留 counterfactual protocol + evidence allocation 主线，不把 Hybrid 写成普遍优越 | 否 |
| IR-4 | 活跃目录一致性 | 修复图、附录和 BibTeX 的新目录路径，清除旧版本号路径 | 否 |
| IR-5 | 投稿格式准备 | 后续转换到 Springer Nature LaTeX `iicol`，检查 20 页上限 | 否 |
| IR-6 | 投稿材料 | 完成作者、单位、通讯作者、ORCID、基金、利益冲突、数据可用性和 AI 使用说明 | 需要作者信息，不需要实验 |
| IR-7 | 最后质量门 | citation audit、图中文字可读性、20 页双栏 PDF、一次 IJDAR 定向模拟审稿 | 否 |

## 36 天执行安排

1. **10 月 10–14 日：** 完成 IR-1 至 IR-4，形成 IJDAR 定向内容稿。
2. **10 月 15–24 日：** 核验全部引用与 DOI，补齐图表、附录和复现入口。
3. **10 月 25–11 月 2 日：** 转 Springer Nature LaTeX `iicol`，压缩到 20 页以内并生成可读 PDF。
4. **11 月 3–7 日：** 由作者确认元数据、数据公开策略、声明和作者贡献。
5. **11 月 8–11 日：** 做一次 IJDAR 定向模拟审稿，只修投稿阻断项。
6. **11 月 12–14 日：** 最终编译、上传前检查和 cover letter。

## 明确不再做的事情

- 不重新开启大规模人工标注；
- 不为了让 Hybrid “赢”而重调冻结阈值；
- 不新增一套大 benchmark；
- 不把 renderer repair pilot 升格成独立 effectiveness claim；
- 不在内容冻结前反复切换投稿方向。

只有在 IJDAR 定向模拟审稿发现明确的致命证据缺口时，才讨论最小补充实验。否则从现在起主线是“修稿、核引、排版、投稿”。
