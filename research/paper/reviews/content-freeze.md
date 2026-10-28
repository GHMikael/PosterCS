# 第二轮复审后 Minor Revision 完成说明

## 结论

`MANUSCRIPT_R1_WORKING_v4.md` 已完成第二轮针对性复审要求中不依赖目标期刊的剩余修改。核心实验和科学主张可以进入内容冻结，不需要继续扩大标注或重跑冻结实验。

## 本次完成内容

1. **RR2-1 / R8：Repair 主张收紧**
   - §5.7 已压缩为一段 developmental feasibility summary；
   - 完整动作、几何结果、人评转移边界和 Tier-B 要求移入 `APPENDIX_E_REPAIR_FEASIBILITY_v1.md`；
   - 正文不再让 Repair 与反事实审计贡献等权。

2. **RR2-2：Viewing-condition 状态说明**
   - §4.4 和 §6.4 已如实记录：早期 fit-to-window 标注没有前瞻保存显示器尺寸、浏览器 viewport 和 zoom；
   - 结论严格限定为 workstation-specific digital-screen judgment，不外推到会议观看距离或实体海报。

3. **正文图组扩充**
   - Figure 1：研究阶段、冻结顺序与证据分配；
   - Figure 2：C48-Confirm 总体 paired correctness 与 control FPR；
   - Figure 3：五个系统在六类缺陷上的 paired correctness 热图；
   - Figure 4：三次调用稳定性与 External-Natural-20 诊断。

所有定量图均由冻结 CSV/JSON 自动生成，同时提供 PNG、PDF 和生成脚本。新增图不是装饰性插图，而分别承担方法解释、总体结论、缺陷级机制和外部/稳定性边界四类论证任务。

## 尚待作者或目标期刊决定

- 作者、单位、通讯作者、基金和利益冲突信息；
- 数据/代码公开位置及版权边界；
- 目标期刊、中文摘要字数、模板和正式 appendix 交叉引用；
- 是否额外做 Tier-B repair。该实验可增强论文，但不是当前审计论文通过复审的必要条件；
- 是否在最终 citation pass 中补 1–2 篇已核验的 behavior testing / shortcut learning 文献。

## 推荐下一步

先由作者通读 v4，重点查看四张主图、§5.3–§5.7 和 §6.4。若主线无异议，即可把 v4 标记为内容冻结候选，然后开始候选期刊筛选与 LaTeX 模板转换。

