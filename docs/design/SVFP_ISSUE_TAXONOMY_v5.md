# SVFP Issue Taxonomy v5 —— 检测路由 + 修复动作(修订版)

> 状态:草案,2026-06-08。相对 `PROJECT_OPTIMIZATION_DIRECTION_v4.md` §3 的修订。
> 由 Claude 在与用户多轮讨论后整理,固化本次达成的两个关键转变 + 三处动作修正。
>
> ### ⚠️ 实际落地差异（2026-06-11 标注）
>
> **代码 canonical 定义在 `experiments/audit/taxonomy.py`。** 本文档是设计稿，与代码有以下差异：
> - 设计 5 类 → **代码 6 类**（`hierarchy_emphasis_error` 和 `asset_mismatch` 拆为独立类；`asset_too_small` 作为几何问题保留）
> - `visual_hierarchy_weak` → **`hierarchy_emphasis_error`**（强调"过度强调"而不只是"弱"）
> - `asset_utilization_error` → **`asset_mismatch`**（强调图文语义不匹配；图尺寸问题走 `asset_too_small`）
> - `text_overload` → **降级为负控制/hallucination probe**（new60 gold=0, VLM 标它就是 FP）
> - 本文 §6 两个未决项 **已闭合**：① 窄提示词消融 done（new60 narrowed acc=0.167 仍不可靠）；② 新系统重审计 done（audit v2 new60, 60 张, 双人标注 S1）
>
> **以 `experiments/audit/taxonomy.py` + `docs/audit/AUDIT_V2_FINDINGS.md` 为当前权威来源。**

---

## 0. 核心转变(v4 → v5)

**v4:** SVFP = 用 VLM 检测 5 类 issue → 确定性修复。

**v5:** **SVFP = 检测(用每类最可靠的手段)→ 确定性修复 → 收敛。检测器不必是 VLM。**

**依据:** 模型规模消融(8B / 30B-A3B / 32B,16 张 human-gold)证明 VLM 版面 critic **先验主导、对图文语义盲**(asset 召回 ≤ 1/12,且 8B 把 16 张全标成同一类),且**不是小模型问题**(换大模型只是换一个默认先验)。→ 因此把检测从「全靠 VLM」改为「按问题类型路由」。

---

## 1. 五类 issue:定义 / 检测路由 / 修复动作

| Issue | 核心问题(修订) | 检测器(路由) | 修复动作(修订) |
|---|---|---|---|
| **space_imbalance** | 主导是「过空」(bullet 间距大、panel 没填满);也含局部过挤 | **几何**(panel occupancy / 留白连通域 / 视觉重心) | 过空 → 放大字号 / 重平衡留白 / 适度减间距;过挤 → 反向。**不能只「减间距」**(只减间距会让过空更空) |
| **text_overload**(≈ overflow) | 文字超框 / 与图重叠 / 被裁切(内容留多后**真实出现**) | **几何**(文本框 vs 容器边界、autofit 溢出标志) | 减 bullet 数 / 减每条 bullet 字数。**禁用 shrink_font**(缩字号降可读性) |
| **visual_hierarchy_weak** | 模块大小雷同、无主次焦点 | **VLM(窄提示词)** 或 规则代理(标题/正文字号层级) | 放大关键模块(用 CS 六模块先验锁定 contribution/results)/ 加 callout / 强化标题层级 |
| **asset_utilization_error** | ① 图文语义不匹配 / 放错图  ② 图太小 | ① **脚本 + 文本 LLM**(图出处 + 原始 caption ↔ panel 文字相关性,**绕开让 VLM 读图**)  ② 几何(图面积比) | ① **优先「换成原文更相关的图」**(用 asset 图库 + 出处),**删除仅兜底**  ② 放大图 / image_focus |
| **structure_alignment_error** | 整体布局出错(如全挤左、右半空)、网格破坏、对齐乱 | **几何**(panel bbox / 列宽平衡 / 网格偏移) | **重平衡列 / snap-to-grid / re-plan**。**不用「整张重渲」** |

---

## 2. 检测路由原则(capability–criticality routing)

- **几何可测的**(overflow / spacing / blank / alignment)→ **规则**,比 VLM 准、且免费、可审计;
- **图文语义**(asset 不匹配)→ **脚本(出处+caption)+ 文本 LLM**,**绕开 VLM 读图**(规模消融证明 VLM 在这类上盲);
- **真正的整体视觉判断**(hierarchy / 粗粒度大片空白)→ **VLM(窄提示词)**,这是 VLM 的主场。

> 反转:VLM 在 asset(图语义)最差,但在 hierarchy(有没有焦点)反而最合适。论文可写成「我们只在 VLM 可靠处用它,在它不可靠处路由给别的检测器」。

---

## 3. Guards(低频硬约束,规则检测,不算主 issue)

`overlap_guard` / `contrast_guard` / `overflow_guard` / `crop_guard` —— 见 `experiments/audit/taxonomy.py`。

---

## 4. 三个被修正的动作(重点,别照搬 v4 / 初版直觉)

1. **space_imbalance:** 你的海报主导子情况是「过空」,所以动作集合必须含**放大 / 重平衡留白**,不能只「减间距」。
2. **asset 图文不匹配:** **换图 > 删图**。删图会压低 figure_reuse / 内容保真,可能搞出无图海报;你有 asset 图库 + 出处,应**替换为更相关的原文图**(同时正面秀 PDF asset pipeline)。
3. **structure_alignment:** **重平衡 / re-plan > 整张重渲**。确定性渲染器对同一 plan 重渲结果**不变**,修不了;且整张重置**破坏** per-action trace / same-initial repair / convergence 叙事。

---

## 5. 与 SVFP 协议指标的衔接(给 Wave2 / #10)

- **c1 可执行率:** 别再写死 `1.0`(`ours_svfp.py:67` 现在就是写死的)。SVFP 臂要诚实计入「VLM 吐出但 schema 校验失败 / applier 落不了地」的条目,和 freeform 同口径。且 c1 偏同义反复 —— **c3 issue-resolution 才是主指标**。
- **c3 issue_resolution_rate:** 需要 `svfp_trace` 遥测(每轮 issue → action → 是否解决/降级)。现 metadata 只有聚合计数,须先在 `feedback_loop.py` 补 `render_state.json` / `svfp_trace.json`(v4 P2/P3)。
- **质量度量(b1/b2):** 用独立几何 + 一个**不同于 critic 的 VLM**,避免「同一不可靠 VLM 既检测又评判」的循环论证。

---

## 6. 未决 / 下一步

- [x] **#4 窄提示词消融(2026-06-08 已完成)** → 结果:窄提示词把 asset 召回从 ~1/12 提到 **4/12**、text_overload 从 11/16 降到 9/16,但**仍不可靠**(漏 8/12,text_overload 仍霸 9/16,与人工一致仅 4/16)。**结论:VLM 即使用直接的图文相关性提示词也只能当 asset 的弱辅助;图文匹配主力仍走脚本+文本 LLM。** 原始数据 `experiments/results/ablation_narrowed_prompt.json`。
- [ ] base 改造(#6/#7/#8)后,在**新系统重跑审计**,用新分布接地 taxonomy。预注册假设:`text_overload`/`vhw` 下降,`asset`/`space`/`structure` 上升。
- [ ] **独立第二标注者**(现唯一标注者是系统作者本人,审稿人必质疑)。
