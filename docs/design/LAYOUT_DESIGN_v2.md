# 布局 v2 设计规格 —— 内容比例自适应(替代写死六格)

> 2026-06-08 夜间生成。**为什么只给规格不直接改代码:** 改 `layout_engine.py` / 渲染器
> 需要反复 render→soffice 栅格化→看图迭代,无人值守易碎;留给你在场时实现 + 目检。

## 1. 问题(已用代码定位)
`app/layout_engine.py:dashboard_layout` 是写死的 **3 列 × 2 行六格**(`left_w`/`right_w`=3.28" 钉死、两行等高),panel 按固定优先级塞进 6 个固定坑 → **每张 dashboard 海报几何完全相同** = 你说的"每张都像、视觉层级弱"的机械根因。

## 2. 借鉴 Paper2Poster `tree_split_layout.py`(用确定性版,不要学习版回归)
它给每 panel 算 `tp`(文字占比)/`gp`(图面积占比)/`sp`(面积占比)/`rp`(宽高比),用回归从 (tp,gp) 预测 panel 大小 → 二叉树递归切分。**我们不需要训练回归,用确定性权重即可,且更可审计。**

## 3. 规格
**Step A — panel 权重(确定性):**
```
weight(panel) = w_text * norm(text_len) + w_fig * has_figure * fig_importance
# 建议 w_text=1.0, w_fig=1.5;fig_importance ∈ {0.5,1,1.5} 来自 planner 的 importance
```
**Step B — 二叉树切分**:把画布按权重递归二分(交替横/纵切,或按列优先),每个叶子面积 ∝ weight。保证:
- 阅读顺序 = CS 软先验(背景→方法→实验→结论)作为切分时的排列约束;
- 最小 panel 面积下限(避免过小);
- headline(来自 planneragent_v2)所在 panel 适度放大,作为视觉焦点。

**Step C — 保留"少量骨架"**:不是一个死模板,也不是全自由;允许 2–3 种骨架(如:焦点图主导 / 均衡网格 / 流程纵向),由内容特征(图多/步骤多/贡献集中)选骨架,骨架内部用 A+B 定尺寸。

## 4. 集成点
- 改 `app/layout_engine.py`:`dashboard_layout` → `content_proportional_layout(prs, panels)`,返回同样的 `{section: {x,y,w,h}}` 结构(渲染器接口不变,降低风险)。
- `app/ppt_renderer.py`:读取 panel 的 `headline` 字段,在 panel 内以更大字号/callout 渲染(让 v2 prompt 的 headline 真正生效)。
- 其它模板(classic/storyflow/minimal)可后续比照。

## 5. 与 SVFP 的连接(重要)
内容自适应后,`resize_panel` / `rebalance` 这些 SVFP 动作**才有真正可操作的状态空间**(写死六格时它们几乎无效)。这也呼应 v5 taxonomy:`space_imbalance`/`structure_alignment` 的几何检测在可变布局上才有意义。

## 6. 测试(早上)
渲染 ~10 篇缓存 plan → 确认:① 不同论文几何**确实不同**(panel 尺寸有方差);② soffice 栅格化无重叠/越界;③ headline 被放大。一轮目检即可。
