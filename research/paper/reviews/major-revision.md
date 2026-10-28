# Editorial Decision Package — Round 1

## Part 1：Editorial Decision Letter

作者您好：

感谢提交题为 *Can Vision-Language Models Reliably Audit Scientific Posters? A Controlled Study of Source-Aware Rules and Selective Routing* 的稿件。本轮由 EIC、方法与统计、VLM/model-as-a-judge、文档工程与视觉可用性四位评审，以及一位 Devil's Advocate 独立审阅。

## Decision：Major Revision

这不是“项目方向不成立”的 Major Revision，而是“核心贡献已经形成，但投稿前必须重新定位并补齐证据链”的 Major Revision。四位评分评审均建议 Major Revision；Devil's Advocate 未发现 CRITICAL 基础崩塌，只提出五项可修复的 MAJOR 挑战。

### Reviewer Summary Matrix

| Reviewer | Recommendation | Confidence | Core judgment |
|---|---|---:|---|
| EIC | Major Revision | 4/5 | 贡献可发表，但主线应从 Hybrid 转为 counterfactual audit + evidence allocation |
| R1 Methodology | Major Revision | 5/5 | staged design 合理；gold、复现、多重比较和稳定性信息不足 |
| R2 VLM | Major Revision | 4/5 | VLM 先验驱动现象重要；只能解释选定 operating points |
| R3 Document/HCI | Major Revision | 4/5 | taxonomy 更合理；真实观看任务与跨生态效度不足 |
| Devil's Advocate | No CRITICAL; 5 MAJOR | — | 最强反方是“内部 validator 检测内部 mutation 痕迹” |

### Weakness Sub-Claim Inventory

| ID | Atomic sub-claim | Supporting reviewers | Disposition |
|---|---|---|---|
| SC-1 | 论文主贡献应从 Hybrid 优势改写为反事实审计协议与证据通道分工 | EIC, R2 | Corroborated 2/4 |
| SC-2 | 24 对、每类 4 对且同一 PosterCS 生态，不能支撑广泛通用性 | EIC, R1, R2, R3 | **CONSENSUS-4** |
| SC-3 | Gold/标注/仲裁流程缺少独立性、agreement 和 provenance 细节 | R1, R3 | Corroborated 2/4 |
| SC-4 | 托管模型精确版本、调用日期、Prompt、预处理和重试/成本不足 | R1, R2 | Corroborated 2/4 |
| SC-5 | 单次 temperature=0 调用不足以刻画 API operating-point 稳定性 | R1, R2 | Corroborated 2/4 |
| SC-6 | C48 四个 McNemar 对比未说明 primary contrast 或多重校正 | R1 | Single-reviewer, high confidence |
| SC-7 | fit-to-window 缺少具体显示条件和任务效度 | R3 | Single-reviewer, high confidence |
| SC-8 | visible evidence/location/abstention 被列为贡献但未直接评分 | R2 | Single-reviewer, high confidence |
| SC-9 | Hybrid 相对 Source-aware Rule 仅 +1/24 且新增 4 个误报，不宜作为性能突破 | EIC, R2 | Corroborated 2/4 |
| SC-10 | Repair pilot 非独立验证，主文权重过高会稀释审计主线 | EIC, R3 | Corroborated 2/4 |
| SC-11 | P1 是 Paper2Poster-style 本地 Prompt，不是原 commenter 复现 | R2 | Single-reviewer, high confidence |
| SC-12 | 需要 evidence-access matrix 直观说明不对称输入 | R3 | Single-reviewer, high confidence |

未出现 reviewer 对同一 atomic sub-claim 的存在性或修复方向冲突，因此本轮没有需要 EIC 仲裁的 SPLIT 项。

### Consensus Analysis

#### [CONSENSUS-4] 外部效度和样本规模

四位评审一致认为，C48-Confirm 能支持受控内部辨别结论，但不能支持自然海报、其他生成器或一般 VLM 的广泛结论。最优处理是补一个冻结后 Natural-20 或 cross-generator 小型测试；若客观上不能补，则必须把标题、摘要和结论统一改成 controlled proof-of-concept，并放弃强通用化语言。

#### Corroborated concerns

- **贡献定位**：Hybrid 是有信息量的负结果，不是主要性能贡献。
- **Gold provenance**：需要把已经完成的双人标注、仲裁和终审过程写进论文并量化。
- **复现与稳定性**：模型 API 实验需要精确配置与至少有限重复。
- **Repair 边界**：目前只能作为 feasibility，不能承担 effectiveness 结论。

#### Devil's Advocate assessment

DA 最强反方成立为“主要外部效度威胁”，但不足以判 Reject。论文已经主动承认 source access 和同生态问题，且 Raster Rule 与 Source-aware Rule 的对比确实回答了“保留源结构是否有用”这一端到端系统问题。作者需要用 external holdout 或更明确的 proof-of-concept 定位来回应，而不是声称公平同输入能力比较。

### Decision Rationale

本文已经具备明确研究问题、合理 staged design、冻结后的配对确认、完整负结果与克制结论，因此不是需要重新选题的稿件。它最值得发表的内容是：常规标签 F1 会掩盖 VLM 在干净控制上继续挑错；control/mutation pair 与 any-defect control FPR 能暴露这种风险；在保留 PPTX source 的生成系统中，确定性结构证据是主要 specificity anchor。

当前不宜直接投稿的原因是，贡献表达和证据强度尚未完全对齐。标题仍突出 selective routing，而 Hybrid 的增益为 1/24、*p*=1.0，并新增四个控制误报。唯一 CONSENSUS-4 问题是确认集规模与同生态来源；此外，gold provenance、模型复现、运行稳定性和统计 multiplicity 都需要补齐。上述问题可以在一个修订周期内解决，且不要求推翻现有全部实验。因此决定为 **Major Revision, re-review required**。

## Part 2：Revision Roadmap

### Required Revisions（Must Fix）

| # | Revision item | Sub-claims | Source | Priority | Estimated effort |
|---|---|---|---|---|---|
| R1 | 重写 title/abstract/contributions/discussion：主贡献改为 counterfactual audit protocol + evidence allocation；Hybrid 明确为有限扩展和负面 trade-off | SC-1, SC-9 | EIC, R2, DA | P1 | 1–2 天 |
| R2 | 处理外部效度：优先新增冻结后 Natural-20 或 cross-generator 小测试；若不补，则全稿降格为 controlled proof-of-concept，并删除广泛暗示 | SC-2 | All four, DA | P1 | 3–7 天（补实验）/ 1 天（只收缩） |
| R3 | 写出完整 gold provenance：标注者、独立轮次、盲化信息、初始 agreement、分歧、仲裁、终审、冻结版本与 hash | SC-3 | R1, R3 | P1 | 1 天 |
| R4 | 补模型复现附录：model ID、API/日期、Prompt 全文、schema、图像输入、tokens、thinking、重试、失败恢复和成本 | SC-4, SC-11 | R1, R2 | P1 | 1 天 |
| R5 | 处理稳定性：对 C48 的 Gemini-P2/Qwen-P3 至少做 3 次重复并报告一致率/范围；若不补跑，将一次 API realization 写成主要限制 | SC-5 | R1, R2 | P1 | 1–3 天 |
| R6 | 明确 primary statistical contrast，并对四个 McNemar 比较做 Holm correction 或区分 primary/secondary；补 macro-F1 零支持标签定义 | SC-6 | R1 | P1 | 0.5–1 天 |
| R7 | 加 evidence-access matrix，明确 raster/source/VLM 各自可见输入；避免公平能力竞赛表述 | SC-12 | R3, DA-M1 | P1 | 0.5 天 |
| R8 | Repair 主文降为 feasibility 摘要，完整结果移附录；除非新增独立 Tier-B，否则不列为与主审计等权贡献 | SC-10 | EIC, R3, DA | P1 | 0.5–1 天 |

### Suggested Revisions（Should Fix）

| # | Revision item | Sub-claims | Source | Priority | Estimated effort |
|---|---|---|---|---|---|
| S1 | 报告 fit-to-window 的屏幕/窗口/缩放条件；有余力可为 figure readability/text overload 做小规模 task-based check | SC-7 | R3 | P2 | 0.5–3 天 |
| S2 | 若保留“traceable evidence”贡献，抽样评估 location/evidence correctness；否则弱化该主张 | SC-8 | R2, DA-M4 | P2 | 1–2 天 |
| S3 | 增加 per-label 计数、2×2 discordance 表与整数分子/分母 | SC-6 | R1 | P2 | 0.5 天 |
| S4 | 补 behavior testing、shortcut learning 和 visual usability 桥接文献 | SC-1, SC-7 | R2, R3 | P2 | 0.5–1 天 |
| S5 | 在讨论中加入 rule+human escalation 作为更简单的部署基线 | SC-9 | DA | P2 | 0.5 天 |

### 可以暂缓到后续论文或补充材料

- 大规模跨生成器 benchmark；
- 完整会议现场观看距离实验；
- 独立 Tier-B repair study；
- PDF/HTML/image-only 全输入条件迁移。

这些方向有价值，但不应再次无限延长当前稿件。为了“能投稿且说得过去”，本轮最值得新增的是 **一个小型 post-freeze external set** 和 **有限 VLM 重复稳定性检查**，而不是再建一套大数据集。

### Revision Checklist

#### Priority 1 — 论文成立所必需

- [ ] R1：重写论文主线，弱化 Hybrid 性能突破叙事。
- [ ] R2：完成外部效度选择（补 Natural-20/cross-generator，或严格 proof-of-concept 降格）。
- [ ] R3：补 gold provenance 和 agreement。
- [ ] R4：补模型/Prompt/运行复现包。
- [ ] R5：完成有限重复，或明确 single-realization 限制。
- [ ] R6：修正 confirmatory multiplicity 与 macro-F1 定义。
- [ ] R7：加入 evidence-access matrix。
- [ ] R8：压缩 repair claim。

#### Priority 2 — 显著增强说服力

- [ ] S1：明确观看条件，考虑小型 task-based check。
- [ ] S2：评估 visible evidence/location，或弱化相关贡献。
- [ ] S3：补充逐类与 discordance 表。
- [ ] S4：补跨方法文献。
- [ ] S5：讨论 rule+human escalation。

### Recommended Revision Window

**3–5 周。** 若不补 Natural-20 和重复 API 实验，可在约 1–2 周内完成文字与复现层修订，但录用说服力会明显较弱。

## Part 3：给作者的最简结论

1. **论文已经开始写了，而且完整初稿已完成；当前是第一轮模拟审稿后的修订阶段。**
2. **不用推翻项目，也不用重新标几十轮数据。**
3. 当前最关键的新增工作只有两个：小型外部测试、VLM 重复稳定性；其余主要是把现有真实流程写清楚。
4. 修完后再做一次 targeted re-review，然后进入 LaTeX/Overleaf 模板与 PDF 投稿稿阶段。
