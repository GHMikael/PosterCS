# Verification Review Report — Round 2

## Decision

**Minor Revision**

修订稿已经解决第一轮评审中影响论文成立的核心问题。论文的中心贡献、证据边界、外部检查、Gold provenance、复现信息、稳定性诊断和统计口径已经形成一致证据链。当前没有残留的 Major methodology issue，也不需要再次扩充主数据集或重跑冻结实验。尚未完全解决的事项可以通过有限正文压缩和说明补充完成，不涉及核心论证重构。

## 审查范围与验证依据

本轮复用第一轮已经确认的专业期刊审稿尺度，采用 re-review verification 模式。作者没有单独提交 Response to Reviewers letter，因此将 `ROUND1_REVISION_TRACKER_v1_ZH.md` 和 `MANUSCRIPT_R1_V3_INTEGRATION_QA_ZH.md` 视为作者修订声明，并在 `MANUSCRIPT_R1_WORKING_v3.md` 与对应冻结附录中独立核验。

## Revision Response Checklist

### Priority 1 — Required Revisions

| # | 第一轮要求 | 作者声明 | 状态 | 核验位置 | Verified? | 质量判断 |
|---|---|---|---|---|---|---|
| R1 | 主线改为 counterfactual audit protocol + evidence allocation，弱化 Hybrid 性能突破 | 已统一标题、摘要、RQ、贡献、讨论和结论 | **FULLY_ADDRESSED** | Title；Abstract；§1；§6.2；§7 | ✅ Yes | 全文不再声称 Hybrid 普遍优于 source-aware rules；主结果被解释为 sensitivity-specificity trade-off。 |
| R2 | 增加 post-freeze external check，或将全稿严格降为内部 proof-of-concept | 已完成 External-Natural-20 并限定为 image-only VLM 的方向性证据 | **FULLY_ADDRESSED** | §3.3；§5.6；§6.4；§7 | ✅ Yes | 样本、标注、输入标准化、结果和不可验证 source-aware transfer 的边界均明确。 |
| R3 | 补 Gold provenance、独立标注、agreement、仲裁、冻结与 hash | 正文写入关键流程，完整记录进入 Appendix A | **FULLY_ADDRESSED** | §3.3；Appendix A | ✅ Yes | Formal-88、C48-Confirm、External-Natural-20 的 Gold 来源与冻结边界可追踪。 |
| R4 | 补模型、Prompt、schema、图像预处理、重试、恢复、日期与成本记录 | 正文引用完整复现附录和冻结运行记录 | **FULLY_ADDRESSED** | §4.1；Appendix B；`FORMAL_RUN_REPORT_v1.md` | ✅ Yes | Appendix B 给出 model ID、Prompt、schema 与恢复流程，运行报告保存日期、token、latency 和 cost estimate。最终投稿时应把本地路径换成补充材料编号，但不影响当前方法可信度。 |
| R5 | 对选定 VLM operating point 做有限重复稳定性检查 | 固定 12 张、每图三次调用并报告一致率 | **FULLY_ADDRESSED** | §4.6；§5.5；§6.1；§6.4；Appendix D | ✅ Yes | 明确区分 repeatability diagnostic 与冻结性能测试，没有用重复结果重选模型或调参。 |
| R6 | 明确 primary contrast、多重校正和 macro-F1 零支持规则 | Hybrid vs Source-aware Rule 为唯一 primary；其余三项 Holm 校正 | **FULLY_ADDRESSED** | §4.5；§5.3；Appendix D | ✅ Yes | 主次比较、discordant counts、raw/adjusted *p* 和 macro-F1 规则均清楚。 |
| R7 | 加 evidence-access matrix，避免把不等输入解释为公平能力竞赛 | 完整矩阵进入 Appendix C，正文多处限定 | **FULLY_ADDRESSED** | §3.1；§4.3；§5.3 图注；§6.2；Appendix C | ✅ Yes | 比较被正确解释为 source-retaining pipeline 的 end-to-end strategy comparison。 |
| R8 | Repair 降为 feasibility，并把完整结果移入附录；无 Tier-B 时不列为等权贡献 | 已从主贡献中降级，并明确无独立 effectiveness 证据 | **PARTIALLY_ADDRESSED** | Abstract；§1；§4.7；§5.7；§6.4；§7 | ⚠️ Partial | 主张边界已修正，但 §5.7 仍保留全部几何倍率、quality gate 和 transferred-human-judgment 细节。建议正文压缩成一段 feasibility summary，将完整数字移入 Repair appendix。 |

### Priority 2 — Suggested Revisions

| # | 第一轮建议 | 状态 | 核验与说明 |
|---|---|---|---|
| S1 | 报告 fit-to-window 的屏幕、窗口和缩放条件，或增加小型 task-based check | **PARTIALLY_ADDRESSED** | §6.4 已明确它只代表 digital review task，不能外推到会议观看距离；但正文仍未提供实际显示器、浏览器窗口和缩放记录。若当时未记录，应明确写为“not prospectively recorded”，不应事后猜测。无需为本轮新做 task-based experiment。 |
| S2 | 抽样评估 evidence/location correctness，或弱化相关贡献 | **FULLY_ADDRESSED** | 稿件没有把 evidence/location accuracy 作为已验证贡献；§3.1 明确 confirmatory analysis 只 operationalize detection 与 restraint。 |
| S3 | 增加 per-label 计数、2×2 discordance 与整数分子/分母 | **FULLY_ADDRESSED** | §5.3–§5.4 提供整数结果和 per-label patterns；Appendix D/CSV 保留 paired discordance。 |
| S4 | 增加 behavior testing、shortcut learning 与 visual usability 桥接文献 | **PARTIALLY_ADDRESSED** | multimodal judge bias 和 document intelligence 的桥接已经加强，但 behavior testing/shortcut learning 仍未形成独立文献线索。该项可在最后 citation pass 中补 1–2 个已核验来源，或保持现有更窄定位。 |
| S5 | 讨论 rule + human escalation 作为更简单的部署基线 | **FULLY_ADDRESSED** | §6.3 明确提出 rule-plus-human escalation 可能优于自动 VLM escalation。 |

## New Issues Discovered During Revision

| # | 类型 | 位置 | 说明 | 严重度 |
|---|---|---|---|---|
| NEW-1 | 正文与补充材料组织 | §5.7 | Repair 已在主张层降级，但正文长度和数值密度仍像一个完整结果模块，与“移入附录”的修订承诺不完全一致。 | Minor，和 R8 合并处理 |
| NEW-2 | 投稿格式 | Supplementary Appendices | 当前使用本地相对路径，不是最终期刊可接受的 appendix/cross-reference 形式。内容冻结后在 LaTeX 阶段统一转换即可。 | Minor formatting |
| NEW-3 | 摘要长度 | 中文摘要 | 中文摘要约 691 个非空白字符，可能超过部分期刊常见上限；目标期刊尚未确定，暂不构成内容问题。 | Minor formatting |

没有发现修订新增的统计错误、数据泄漏、结果数字冲突或新的过度概括。

## Editorial Assessment

### 已通过的核心质量门

1. **Contribution alignment**：标题、摘要、Introduction、Discussion 和 Conclusion 现在讲述同一个研究故事。
2. **Internal validity**：Formal-88、RuleDev、C48-Confirm 和 External-Natural-20 的职责及冻结顺序清晰。
3. **Statistical interpretation**：论文不再用 Hybrid 对弱基线的显著差异掩盖 Hybrid 与 Source-aware Rule 之间的非显著差异。
4. **External-validity honesty**：外部实验只支持 image-only VLM 行为的方向性复现，不被包装成完整系统跨生成器验证。
5. **Repair boundary**：稿件明确承认当前 Repair 不是独立 effectiveness study。

### 最强剩余反方

最强反方仍然是：Source-aware Rule 的高 specificity 可能依赖 PosterCS 保留的内部结构，无法直接迁移到没有 PPTX source 的海报生态。修订稿已经正面承认这一点，并将贡献限定为 source-retaining generation pipeline 的审计策略。因此该反方现在是外部效度限制，而不是推翻中心论点的致命漏洞。

## Decision Rationale

第一轮 Major Revision 的八项 Required Revisions 中，七项已经充分解决。唯一部分解决的 R8 不再影响论文的核心科学结论，因为摘要、贡献和结论已明确把 Repair 定位为 developmental feasibility；剩余问题只是正文和附录之间的篇幅分配。S1 的显示条件记录和 S4 的桥接文献也属于可通过说明或有限补充解决的问题，不要求新增数据。

因此，新决定从 **Major Revision 降为 Minor Revision**。完成以下三项后，稿件可以进入内容冻结与投稿格式阶段，不需要再进行第三轮完整模拟审稿：

1. 将 §5.7 压缩为一段，完整 Repair 数字移入单独 Appendix；
2. 在 §4.4 或 §6.4 明确 fit-to-window 的实际记录状态：若没有保存屏幕/缩放条件，就如实说明未前瞻记录；
3. 在确定目标期刊后压缩中文摘要，并把本地文件路径转换成正式交叉引用。

## Residual Issues

| ID | 必须程度 | 建议动作 | 是否需要新实验 |
|---|---|---|---|
| RR2-1 | 投稿前应完成 | 压缩 Repair 正文并建立 Repair appendix | 否 |
| RR2-2 | 投稿前应完成 | 补充 fit-to-window 记录状态和适用边界 | 否 |
| RR2-3 | 目标期刊确定后完成 | 调整摘要长度与 appendix 引用格式 | 否 |
| RR2-4 | 可选增强 | 补 1–2 篇 behavior testing/shortcut learning 桥接文献 | 否；但引用必须核验 |
| RR2-5 | 可选增强 | 独立 Tier-B repair study | **是，但不是当前审计论文通过复审的必要条件** |

## Final Re-Review Conclusion

当前论文已经从“需要补齐证据链的 Major Revision”进入“可以收尾的 Minor Revision”。审计论文的主要实验阶段可以视为结束。接下来应优先完成三项有限正文整理并确定投稿方向，而不是继续循环标注或重新设计 benchmark。
