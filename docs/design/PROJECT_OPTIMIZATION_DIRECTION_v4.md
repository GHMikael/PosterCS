### **这份项目优化文档的核心结论：PosterCS 不再定位为“全面打败 SOTA 的海报生成器”，而是定位为“用于验证 SVFP 的可控结构化版面基座”；论文主贡献仍然是 SVFP，重点优化 ISSUE taxonomy、协议指标、实验分层和 renderer 的可控性，而不是盲目追求海报生成质量第一。**

下面是一份可以直接交给 Claude 逐步实现的完整项目优化方向文档。你可以保存为：

`PROJECT_OPTIMIZATION_DIRECTION_v4.md`

---

# **PosterCS / SVFP 项目优化方向文档 v4**

## **0. 当前论文定位与总体方向**

### **0.1 论文主线保持不变**

本项目的论文方向仍然保持原来的“一主两从金字塔”结构，不改成“单纯追求最强 paper-to-poster 生成系统”的方向。

当前最稳的定位是：

> **PosterCS 不定位为单独的 SOTA 海报生成器，而是作为一个可控的结构化版面基座，用于验证 SVFP 这一通用视觉修复协议：SVFP 将 VLM 的视觉批评转化为可执行、可收敛、可审计的海报版面编辑。**

英文可写作：

> **PosterCS is not positioned as a standalone SOTA poster generator; it is a controllable structured layout substrate for evaluating SVFP, a general visual repair protocol that turns VLM critiques into executable and convergent poster layout edits.**

因此，论文主线不是：

> We build the best paper-to-poster generation system.

而是：

> We propose SVFP, a structured visual feedback protocol that makes VLM visual critiques executable, convergent, and transferable across poster planners.

---

## **0.2 一主两从贡献结构**

项目贡献仍然采用“一主两从”金字塔：

```text
        ┌────────────────────────────────────────────────────┐
  主    │  贡献① SVFP：结构化视觉反馈协议                       │
        │  将 VLM critique 约束为封闭 issue-action schema，     │
        │  并通过 deterministic applier 实现可执行、可收敛修复    │
        └────────────────────────────────────────────────────┘

        ┌──────────────────────────────┐  ┌────────────────────────────────┐
  从    │ 贡献② CS-Poster-30 benchmark  │  │ 贡献③ CS poster 垂直实例化        │
        │ frozen snapshots + baseline   │  │ 六模块 domain prior + renderer    │
        │ matrix + protocol/outcome eval│  │ 作为验证 SVFP 的真实高密度场景       │
        └──────────────────────────────┘  └────────────────────────────────┘
```

### **贡献①：SVFP 结构化视觉反馈协议**

SVFP 是全文方法论 spine。它解决的核心问题是：

> VLM 可以发现海报视觉问题，但自由文本反馈无法稳定、确定、可复现地转化为下游版面修复动作。

SVFP 的核心价值是把 VLM 的视觉反馈从自然语言建议转化为：

- closed issue taxonomy；
- deterministic repair action；
- executable layout edits；
- bounded feedback loop；
- auditable repair trace。

### **贡献②：CS-Poster-30 benchmark + 评测套件**

CS-Poster-30 是支撑贡献，作用是提供可复现、可对比、可审计的实验基座。它包括：

- 30 篇 CS 论文；
- frozen planner snapshots；
- 多 baseline 矩阵；
- 自动指标；
- 协议指标；
- 人评 / PaperQuiz；
- 统计分析流程。

CS-Poster-30 的角色不是单独作为一个大 benchmark 争主线，而是支撑 SVFP 机制验证。

### **贡献③：CS 垂直实例化**

CS poster 生成器是 SVFP 的真实高信息密度验证场景。它保留六模块 CS domain prior、PDF asset pipeline、PlanJSON、renderer、SVFP loop，但角色应明确为：

> 一个可控 structured layout substrate，而不是最终主贡献本身。

---

# **1. 顶层实验哲学：不要把所有指标都当作“打败 SOTA”的战场**

## **1.1 指标的三层角色**

后续论文与实验中，不能把 16 个指标平均用力，也不能把它们全部理解为“PosterCS 必须全面超过 SOTA”。指标应该分成三层使用。

| 层级 | 指标类型 | 回答的问题 | 论文角色 |
| --- | --- | --- | --- |
| 主层 | C 协议指标 | SVFP 是否比 free-form feedback 更可执行、更收敛？ | 主创新证据 |
| 第二层 | B 视觉质量 + D 效率 | SVFP 执行后是否改善海报视觉质量？代价多少？ | 修复有效性与 Pareto 权衡 |
| 第三层 | A 内容保真 + E 人评/Quiz | 修复是否破坏内容？人类/阅读效果是否接受？ | 安全约束与外部验证 |

## **1.2 与 SOTA 的正确关系**

不应主张：

> PosterCS 全面超过所有 SOTA poster generation systems.

更稳的主张是：

> SVFP consistently improves visual quality from a given initial poster while preserving content fidelity within an acceptable trade-off, and its structured feedback is more executable and convergent than free-form feedback.

SOTA 的角色应该是：

1. **外部质量参照**：说明 PosterCS + SVFP 处于可用质量范围；
2. **可选后处理对象**：如果能拿到 PPTX / HTML / JSON 等可编辑输出，可做 `SOTA + SVFP`；
3. **不强行套用协议指标**：没有 feedback loop 的 SOTA，C 类协议指标应标 N/A。

---

# **2. 为什么仍然需要自研 renderer**

## **2.1 renderer 不是主贡献，而是 SVFP 的可控执行基座**

自研 renderer 的必要性不在于“打败 SOTA”，而在于 SVFP 需要一个可控的结构化状态空间。

SVFP 的核心不是让 VLM 发现问题，而是：

> VLM 发现问题之后，能否被 deterministic applier 稳定执行。

这要求系统必须知道每个元素的：

- 类型；
- 位置；
- 尺寸；
- 所属 panel；
- 所属 section；
- 字号；
- 颜色；
- 图源 ID；
- bbox；
- caption；
- z-order；
- 模块关系。

外部 SOTA 如果只输出 PNG/PDF，很难确定性编辑；如果输出 PPTX/HTML/JSON，则可以作为后续 SVFP 外部验证对象。

## **2.2 renderer 的优化目标**

renderer 不需要追求“最强美工”，而需要追求：

| 目标 | 说明 |
| --- | --- |
| 可控 | 所有布局元素可追踪、可编辑 |
| 可复现 | 同一 PlanJSON 渲染结果稳定 |
| 可审计 | 每轮 SVFP action 有 before/after trace |
| 可用 | 初始 poster 不应太差，否则会被质疑“修自家 bug” |
| 可扩展 | 后续可接外部 planner 或 SOTA editable output |

## **2.3 renderer 最该补的能力**

后续实现中优先补：

1. `render_state.json` / `layout_trace.json`；
2. 每个元素的 bbox、type、panel、section、font、color、source_id；
3. panel occupancy；
4. text density；
5. figure area ratio；
6. grid alignment；
7. action before/after trace；
8. issue detection trace。

---

# **3. 新版 SVFP ISSUE taxonomy**

## **3.1 为什么要重构 ISSUE**

原有 ISSUE 为：

| Issue | 典型确定性修复 |
| --- | --- |
| `overlapping_elements` | 减少 bullet、缩小字号 |
| `empty_space` | 放大字号、重平衡留白 |
| `low_contrast` | 切换配色 |
| `figure_too_small` | 纵向面板 → image_focus |

原 schema 稳定、可执行率高，但存在问题：

1. `overlapping_elements` 低频，现代 renderer 基本不会出现；
2. `low_contrast` 低频，且更适合作为规则 guard；
3. `figure_too_small` 太窄，只覆盖图资产问题的一小部分；
4. `empty_space` 过宽，容易变成“垃圾桶”类别；
5. 四类不是严格 MECE，真实失败案例解释力不足。

因此，后续应把 ISSUE 从“表面错误”升级为“高频、可检测、可归因、可修复的设计失败根因”。

---

## **3.2 新版 5 类主 ISSUE**

最终建议采用 5 类主 ISSUE：

| Issue | 中文解释 | 核心问题 | 典型修复 |
| --- | --- | --- | --- |
| `space_imbalance` | 空间利用不均 | 局部过空、局部过挤、视觉重心失衡 | 重分配 panel、高宽调整、重平衡留白 |
| `text_overload` | 文本负载过重 | bullet 太多、字号太小、文本密度高、阅读压力大 | 减少 bullet、提升摘要粒度、增大字号、拆分文本 |
| `visual_hierarchy_weak` | 视觉层级弱 | 贡献、方法、结果不突出，读者不知道先看哪里 | 放大 key claim、添加 callout、强化标题层级 |
| `asset_utilization_error` | 图表资产使用不佳 | 未复用关键图、图太小、图文距离远、caption 弱 | 选择关键图、放大图、image_focus、移动 caption |
| `structure_alignment_error` | 结构/对齐错误 | panel 不齐、网格破坏、模块边界不清、间距不一致 | snap-to-grid、统一边距、对齐标题、修正模块布局 |

这 5 类对应 poster 视觉设计的五个核心维度：

1. 空间；
2. 文本；
3. 层级；
4. 图表；
5. 结构。

它们比旧的 4 类更 MECE，更符合真实失败分布，也更利于论文防御。

---

## **3.3 新旧 ISSUE 映射**

| 原 Issue | 新定位 | 说明 |
| --- | --- | --- |
| `empty_space` | `space_imbalance` | 从“空白多”升级为“空间分配不均” |
| `overlapping_elements` | 降级为 `overlap_guard`，主 issue 替换为 `text_overload` | overlap 低频，text overload 高频 |
| `low_contrast` | 降级为 `contrast_guard`，主 issue 替换为 `visual_hierarchy_weak` | low contrast 可规则检测，不应做主 issue |
| `figure_too_small` | `asset_utilization_error` | 图太小只是图资产错误的一种 |
| 无 | `structure_alignment_error` | 新增，覆盖网格、对齐、模块边界问题 |

---

## **3.4 Guard 层设计**

低频但可规则检测的问题不作为主 ISSUE，而作为 guard。

| Guard | 检测方式 | 修复 |
| --- | --- | --- |
| `overlap_guard` | bbox overlap ratio 超阈值 | move element、shrink secondary text、rebalance panel |
| `contrast_guard` | WCAG contrast ratio 低于阈值 | switch palette、darken text、lighten background |
| `overflow_guard` | 文本框溢出、省略号、裁切 | reduce bullets、enlarge box、adjust font |
| `crop_guard` | 图像裁切、比例异常 | fit contain、restore aspect ratio |

论文中可写作：

> SVFP separates high-level design issues from deterministic safety guards. The former captures frequent poster design failures, while the latter handles rare hard-constraint violations using rule-based checks.

---

# **4. 新版 ISSUE 的可检测标准**

## **4.1 `space_imbalance`**

### **定义**

空间利用不均，表现为局部过空、局部过挤、视觉重心偏移或 panel 面积分配不合理。

### **可计算代理指标**

panel occupancy：

$$
occupancy_i = \frac{content\_area_i}{panel\_area_i}
$$

empty ratio：

$$
empty\_ratio_i = 1 - occupancy_i
$$

imbalance score：

$$
space\_imbalance = Var(occupancy_1, ..., occupancy_n)
$$

### **触发条件示例**

- 某 panel `occupancy < 0.25`；
- 另一个 panel `occupancy > 0.75`；
- 最大空白连通区域过大；
- 左右视觉重心偏差过大；
- panel occupancy 方差超过阈值。

### **典型 action**

- `rebalance_whitespace`
- `resize_panel`
- `redistribute_panel_area`
- `increase_content_scale`
- `adjust_module_ratio`

---

## **4.2 `text_overload`**

### **定义**

文本负载过高，即使没有物理 overlap，也会导致阅读困难。

### **可计算代理指标**

text density：

$$
text\_density_i = \frac{characters_i}{panel\_area_i}
$$

也可统计：

- bullet 数；
- 行数；
- 最小字号；
- 文本框面积占比；
- likely overflow 数量；
- ellipsis 数量。

### **触发条件示例**

- panel bullet 数超过阈值；
- text density 超阈值；
- 最小字号低于阈值；
- ellipsis / overflow 出现；
- VLM 判断 panel 过密。

### **典型 action**

- `reduce_bullet_count`
- `increase_abstraction`
- `summarize_secondary_text`
- `increase_font_size_if_space_allows`
- `split_dense_panel`

注意：如果文本已过载，不应盲目 `shrink_font`，因为缩小字号可能降低可读性。更合理的是减少内容、提升摘要层级。

---

## **4.3 `visual_hierarchy_weak`**

### **定义**

海报没有清晰视觉重点，读者无法快速识别贡献、方法主线或关键结果。

### **检测方式**

VLM rubric：

> Is the main contribution visually salient within 3 seconds?

规则代理：

- title / subtitle / body 字号层级是否明显；
- key contribution 是否有 callout；
- result number 是否突出；
- method pipeline 是否有视觉中心；
- section title 是否统一；
- 强调区域面积是否足够。

### **典型 action**

- `promote_key_claim`
- `add_callout`
- `increase_title_hierarchy`
- `highlight_result_number`
- `reorder_panels_by_storyline`

---

## **4.4 `asset_utilization_error`**

### **定义**

图表资产使用不佳，包括未复用关键图、图太小、图文弱关联、caption 缺失或图源错误。

### **可计算代理指标**

figure-poster ratio：

$$
figure\_poster\_ratio = \frac{figure\_area}{poster\_area}
$$

figure-panel ratio：

$$
figure\_panel\_ratio = \frac{figure\_area}{panel\_area}
$$

还可统计：

- 是否复用 valid figure；
- figure source ID 是否存在；
- caption 是否存在；
- 图与相关文本距离；
- 图文一致性分数；
- unresolved figure reference。

### **典型 action**

- `select_key_figure`
- `enlarge_figure`
- `switch_to_image_focus`
- `move_caption_near_figure`
- `replace_decorative_asset_with_paper_figure`

---

## **4.5 `structure_alignment_error`**

### **定义**

结构、网格、模块边界或对齐关系不清晰。

### **可计算代理指标**

- panel x/y 是否对齐；
- 列宽是否一致；
- section header baseline 是否一致；
- panel margin 方差；
- grid deviation；
- 模块顺序是否符合 CS 六模块先验。

### **典型 action**

- `snap_to_grid`
- `align_section_headers`
- `normalize_margins`
- `equalize_column_width`
- `repair_module_order`

---

# **5. 新版 SVFP action 设计原则**

## **5.1 不要让 action 爆炸**

虽然 ISSUE 从 4 类升级为 5 类，但 action 不应无限增加。建议总 action 数控制在 10–12 个左右。

SVFP 仍然应该是：

> compact closed schema，而不是开放式视觉设计系统。

## **5.2 初始 action 集合建议**

| Action | 主要对应 Issue | 说明 |
| --- | --- | --- |
| `rebalance_whitespace` | `space_imbalance` | 重分配留白与 panel 尺寸 |
| `resize_panel` | `space_imbalance`, `structure_alignment_error` | 调整 panel 占比 |
| `reduce_bullet_count` | `text_overload` | 减少 bullet 数 |
| `increase_abstraction` | `text_overload` | 提升摘要粒度 |
| `promote_key_claim` | `visual_hierarchy_weak` | 提升关键贡献可见性 |
| `add_callout` | `visual_hierarchy_weak` | 添加关键结果/方法 callout |
| `select_key_figure` | `asset_utilization_error` | 选择更关键的原文图 |
| `enlarge_figure` | `asset_utilization_error` | 放大图表 |
| `switch_to_image_focus` | `asset_utilization_error` | 切换到 image-focused layout |
| `snap_to_grid` | `structure_alignment_error` | 网格吸附 |
| `normalize_margins` | `structure_alignment_error` | 统一边距 |
| `align_section_headers` | `structure_alignment_error` | 对齐标题 baseline |

如果需要保持更紧凑，可先实现 9–10 个，后续再补。

---

# **6. 新版指标体系：16 个正式指标**

## **6.1 指标体系总览**

当前正式指标保持 16 个，不继续扩充。它们分为五类：

- A：内容保真；
- B：视觉质量；
- C：协议性质；
- D：效率成本；
- E：人评 / Quiz / LLM judge。

注意：16 个指标是完整评测框架，但论文正文中不应平均展开。正文重点放 C 类协议指标、B 类视觉修复指标、D1 延迟、E1/E2 外部验证；A 类主要作为内容安全约束。

---

## **6.2 16 个指标表**

| 文件名 | 论文指标名 | 层级 | 设计原因 | 计算方案 |
| --- | --- | --- | --- | --- |
| `a1_key_info_recall.py` | Key Information Recall | Tier-1 | 内容保真核心。海报是信息压缩任务，必须衡量原文关键点被覆盖多少 | 从原文抽取 K 个关键信息点，用 NLI/LLM 判断每个点是否被海报 entail；Recall = 覆盖点数 / K |
| `a2_hallucination_rate.py` | Hallucination Rate | Tier-1 | 防止视觉修复通过乱写/删改内容换取美观，顶会重视事实性 | 将海报文本切成原子陈述，对原文做 NLI；contradicted + unsupported 计为幻觉，neutral/abstain 不计；Rate = 幻觉句 / 总句 |
| `a3_semantic_fidelity.py` | Semantic Fidelity (BERTScore) | Tier-2 | 语义相似度辅助指标，比 ROUGE 更适合压缩改写场景 | 海报全文与原文摘要/原文核心段落计算 BERTScore F1，报告 rescaled F1 |
| `b1_layout_quality.py` | Layout Quality | Tier-1 | SVFP 视觉修复主结果，验证 layout 是否更合理 | 渲染 PNG 后由独立 VLM 按 alignment/grid/whitespace/section clarity 打分，辅以几何检查 |
| `b2_readability.py` | Readability | Tier-1 | 与 b1 共同证明视觉质量提升，关注字号、密度、对比度、阅读负担 | 统计最小字号、文本密度、对比度、行宽、overflow、ellipsis；可与 VLM readability judge 结合 |
| `b3_figure_reuse_rate.py` | Figure Reuse Rate | Tier-1 | PDF asset pipeline 的结构性优势，证明原文图表被真实复用 | Reuse = 被复用的有效原文图数 / 原文有效图数；记录 unused/missing/unresolved |
| `b4_figure_text_align.py` | Figure-Text Alignment | Tier-2 | 验证图文一致性，支撑 AgentPrompt 与 asset utilization | 对每张入选图，用 VLM/CLIP/LLM 判断图与相邻正文/标题是否语义一致，取平均 |
| `c1_action_executability.py` | Action Executability | Tier-1 | SVFP 命门指标，证明 closed schema 比 free-form feedback 更可执行 | n_executed / n_attempts；分母包括 VLM 输出但无法解析/无法落地的反馈条目；free-form 同口径统计 |
| `c2_convergence_rate.py` | Convergence Rate | Tier-1 | 证明 SVFP 不是无限 agent loop，而能在有限预算内收敛 | 单 run 收敛=无有效 issue 或 gain 低于阈值；Rate = 收敛 run 数 / 总 run 数 |
| `c3_issue_resolution_rate.py` | Issue Resolution Rate | Tier-1 / Tier-2 | 建议替换原 per-iter gain 的主位置，证明 action 执行后 issue 是否真的被修好 | Resolution = 被解决 issue 数 / 检测到 issue 数；比较执行前后 issue 是否消失或降级 |
| `c4_per_iter_visual_gain.py` | Per-Iteration Visual Gain | Tier-2 | 解释闭环过程是否每轮平均改善，而非震荡 | 每轮后计算视觉分变化 ΔQ = Q_t - Q_{t-1}，报告平均正向增益和正向迭代占比 |
| `d1_latency.py` | Latency | Tier-1 | SVFP 会增加 VLM 调用，必须诚实报告质量-延迟权衡 | 端到端墙钟时间，拆 plan/render/SVFP loop；报告 median/P90 |
| `d2_cost.py` | Cost | Tier-2 | 报告多轮 VLM 成本，形成 quality-latency-cost Pareto | 累加 LLM/VLM token × 单价，拆文本规划与视觉批评成本 |
| `e1_paperquiz.py` | PaperQuiz Accuracy | Tier-1 | 升为 e1，对齐 SOTA 评测锚点；题目要难化以避免天花板 | 从原文生成困难选择题，让人或 VLM 只看海报答题；Accuracy = 答对数 / N |
| `e2_human_preference.py` | Human Preference | Tier-1 | 顶会刚需，打破自动指标循环论证 | 成对盲评同一论文不同方法海报，报告 win-rate 或 Bradley-Terry score，统计一致性 |
| `e3_llm_judge.py` | LLM-as-a-Judge | Tier-2 | 规模化补充评测，但必须与人评相关性绑定 | LLM 按 rubric 打分或成对判优；报告与 e2 的 Spearman/一致率 |

---

## **6.3 删除或降级的指标**

以下指标不进入正式 16 个主指标：

| 指标 | 处理方式 | 原因 |
| --- | --- | --- |
| ROUGE-L | 删除或仅附录 | 海报高度压缩改写场景下区分度弱，容易被审稿人质疑 |
| Section Coverage | 删除正文 | 之前基本全是 1，天花板指标，无区分度 |
| Failure Rate | 删除正文，仅一句话报告 | 之前基本全是 0，地板指标；可附录说明系统稳定 |
| Academic Compliance | 降级或删除 | 与主线弱相关，容易稀释核心 |
| Visual Smoke Check | 内部预检，不进主表 | 工程 smoke test，不适合作为论文主指标 |
| SUS / Time Saving | 暂缓 | 人评资源有限时优先做 PaperQuiz 和 Human Preference |

---

# **7. C 类协议指标的特殊定位**

## **7.1 C 类不是普通质量指标**

A/B/D/E 评估的是最终输出 poster：

- 内容是否保真；
- 视觉是否更好；
- 成本是否可接受；
- 人是否喜欢。

C 类评估的是 SVFP 协议机制：

- 反馈是否可执行；
- 闭环是否收敛；
- issue 是否被修复；
- 每轮是否改善。

因此 C 类应在论文中单独命名为：

> Protocol-level Metrics  
> Mechanism Metrics

不要把它与普通 outcome metrics 混在一起。

## **7.2 C 类指标适用的 baseline**

C 类不适用于所有方法。没有 feedback loop 的方法应标 N/A。

| Baseline | C 类是否适用 | 说明 |
| --- | --- | --- |
| `ours_svfp` | 适用 | 主方法 |
| `ours_freeform` | 适用 | E1 对比，自由文本 feedback + LLM apply |
| `gpt4o_zeroshot_svfp` | 适用 | E2，验证 planner-agnostic |
| `ours_no_svfp` | N/A | 无反馈过程 |
| `gpt4o_zeroshot` | N/A | 无反馈过程 |
| external SOTA | 通常 N/A | 除非接上 SVFP 后处理 |

## **7.3 C 类指标如何证明“好”**

| 指标 | 好的结果 | 证明 |
| --- | --- | --- |
| c1 Action Executability | SVFP 接近 100%，free-form 明显更低 | closed schema 让 VLM feedback 可执行 |
| c2 Convergence Rate | 大多数 run 在预算内收敛 | 闭环稳定可控 |
| c3 Issue Resolution Rate | 多数 issue 执行后消失或降级 | action 不只是执行了，而且真的修好了 |
| c4 Per-Iter Gain | 前 1–2 轮有正向提升，后续趋稳 | 修复有效且 bounded |

---

# **8. 分析项：不作为正式指标，但必须支撑论文**

以下分析不放入 16 个正式指标，但对论文很重要。

## **8.1 Issue Distribution**

文件建议：

`analysis_issue_distribution.py`

作用：

- 统计新版 5 类 issue 在真实失败案例中的 primary / secondary 分布；
- 证明 taxonomy 覆盖真实失败；
- 支撑 MECE 性。

输出示例：

| Issue | Primary Count | Secondary Count | Share |
| --- | ---: | ---: | ---: |
| `space_imbalance` | 18 | 7 | 40% |
| `text_overload` | 12 | 10 | 31% |
| `visual_hierarchy_weak` | 9 | 8 | 24% |
| `asset_utilization_error` | 6 | 6 | 17% |
| `structure_alignment_error` | 3 | 5 | 9% |

## **8.2 Action Distribution**

文件建议：

`analysis_action_distribution.py`

作用：

- 统计 10–12 个 deterministic actions 的触发频次；
- 证明 action schema 不是拍脑袋；
- 发现零触发/低触发 action 是否需要删减或解释。

## **8.3 Guard Trigger Rate**

文件建议：

`analysis_guard_trigger_rate.py`

作用：

- 统计 overlap、contrast、overflow、crop 等 guard 的触发频次；
- 支撑“overlap/contrast 低频，降级为 guard 是合理的”。

## **8.4 MECE Audit**

文件建议：

`analysis_issue_mece_audit.py`

建议统计：

| 统计 | 定义 | 作用 |
| --- | --- | --- |
| Coverage | 至少被一个 issue 覆盖的失败案例 / 全部失败案例 | 证明穷尽性 |
| Other Rate | 标成 unknown/other 的比例 | 证明没有大类缺失 |
| Primary Agreement | 标注者对 primary issue 的一致率或 Cohen’s κ | 证明类别边界清晰 |
| Multi-label Rate | 同时出现多个 issue 的比例 | 说明主/次 issue 标注必要性 |

目标：

- Other Rate 尽量 < 10%；
- Primary agreement 尽量达到中等以上；
- 主要 issue 都有真实触发案例。

---

# **9. 实验表设计**

不要把所有 baseline 和所有指标塞进一张大表。建议拆成三张表。

## **9.1 Table 1：Protocol Evaluation**

只比较有反馈机制的方法。

| Method | C1 Executability ↑ | C2 Convergence ↑ | C3 Issue Resolution ↑ | C4 Iter Gain ↑ |
| --- | ---: | ---: | ---: | ---: |
| Free-form feedback | low | medium/low | medium/low | unstable |
| SVFP | high | high | high | stable |
| Zero-shot + SVFP | high | high | high | stable |

目的：

证明 SVFP 比自由文本 feedback 更可执行、更稳定、更可收敛。

## **9.2 Table 2：Same-initial Poster Repair**

比较同一初始 poster 修复前后。

| Method | A1 Recall ↑ | A2 Hallucination ↓ | B1 Layout ↑ | B2 Readability ↑ | D1 Latency ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| ours_no_svfp | baseline | baseline | baseline | baseline | low |
| ours_freeform | maybe fluctuates | maybe fluctuates | small gain | small gain | medium |
| ours_svfp | acceptable | acceptable | higher | higher | higher |

目的：

证明 SVFP 在同一初始条件下改善视觉质量，同时不严重破坏内容。

## **9.3 Table 3：External SOTA Reference**

SOTA 作为质量参照，不强行套用 C 类协议指标。

| Method | A1 Recall ↑ | B1 Layout ↑ | B2 Readability ↑ | E1 PaperQuiz ↑ | E2 Human Pref ↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| SOTA-1 | - | - | - | - | - |
| SOTA-2 | - | - | - | - | - |
| PosterCS + SVFP | - | - | - | - | - |

如果能接外部 editable output，则增加：

| Method | B1 Layout ↑ | B2 Readability ↑ | E2 Human Pref ↑ |
| --- | ---: | ---: | ---: |
| SOTA | baseline | baseline | baseline |
| SOTA + SVFP | higher | higher | higher |

目的：

证明 SVFP 不是 PosterCS renderer 的内部 trick，而可作为通用 post-hoc visual repair protocol。

---

# **10. Baseline 设计建议**

## **10.1 必保 baseline**

| Baseline | 作用 |
| --- | --- |
| `ours_no_svfp` | 同 renderer 无反馈，验证 SVFP 视觉修复增益 |
| `ours_svfp` | 主方法 |
| `ours_freeform` | E1，对比 free-form feedback 的不可执行性 |
| `gpt4o_zeroshot` | zero-shot planner 基线 |
| `gpt4o_zeroshot_svfp` | E2，验证 SVFP planner-agnostic |

## **10.2 后续强加分 baseline**

| Baseline | 作用 |
| --- | --- |
| external SOTA-1 | 外部质量参照 |
| external SOTA-2 | 外部质量参照 |
| `sota_svfp` | 若有可编辑输出，验证 SVFP 通用后处理能力 |

---

# **11. 后续实现路线图**

## **11.1 P0：先做 failure taxonomy audit**

目标：不改主代码，先验证新版 5 issue 是否合理。

输入：

- n=30 或至少 10 个 pilot poster；
- 最好使用 SVFP 修复前的初始 PNG；
- 包括 `ours_no_svfp`、`gpt4o_zeroshot` 或初始 render。

步骤：

1. 渲染初始 poster PNG；
2. 用人工或 VLM 标注 primary issue；
3. 可选标注 secondary issue；
4. guard violation 单独统计；
5. 计算 issue distribution、other rate、coverage、agreement。

输出：

- `analysis_issue_distribution.json`
- `analysis_issue_mece_audit.json`
- 可视化柱状图。

通过标准：

- 五类 issue 覆盖绝大多数失败；
- old `overlap` / `contrast` 确实低频；
- `empty_space` 可被合理拆成 `space_imbalance` 等更具体类型；
- other rate 不高。

---

## **11.2 P1：升级 SVFP schema prompt**

目标：把 VLM critique 从旧 4 issue 改为新 5 issue。

建议输出格式：

```json
{
  "issues": [
    {
      "issue_type": "space_imbalance",
      "severity": "medium",
      "target": "results_panel",
      "evidence": "The right column has large unused whitespace while the method panel is dense.",
      "recommended_action": "rebalance_whitespace"
    }
  ]
}
```

字段建议：

| 字段 | 说明 |
| --- | --- |
| `issue_type` | 五类之一 |
| `severity` | low / medium / high |
| `target` | 具体 panel/element |
| `evidence` | VLM 观察证据 |
| `recommended_action` | 封闭 action 集合之一 |
| `confidence` | 可选 |
| `guard_violation` | 可选，低频硬约束 |

---

## **11.3 P2：先复用旧 action，不要大爆炸**

先把新 issue 映射到已有 action，降低实现风险。

| 新 Issue | 初期可复用 action |
| --- | --- |
| `space_imbalance` | `rebalance_whitespace`, `enlarge_font`, `resize_panel` |
| `text_overload` | `reduce_bullet_count`, `shrink_font` 慎用 |
| `visual_hierarchy_weak` | `enlarge_font`, `promote_title`, `add_highlight` |
| `asset_utilization_error` | `image_focus`, `enlarge_figure` |
| `structure_alignment_error` | `snap_to_grid`, `normalize_margins` |

如果某类 issue 修不好，再补新 action。

---

## **11.4 P3：补 renderer telemetry**

需要新增或强化：

`render_state.json`：

```json
{
  "poster_size": {"width": 1920, "height": 1080},
  "panels": [
    {
      "id": "method_panel",
      "bbox": [100, 200, 500, 700],
      "section": "Method",
      "occupancy": 0.82,
      "text_density": 0.76,
      "n_bullets": 7
    }
  ],
  "elements": [
    {
      "id": "fig1",
      "type": "figure",
      "source_id": "Fig1",
      "bbox": [600, 300, 900, 600],
      "panel": "results_panel"
    }
  ]
}
```

`svfp_trace.json`：

```json
{
  "iteration": 1,
  "detected_issue": {
    "issue_type": "text_overload",
    "target": "method_panel",
    "severity": "high"
  },
  "action": {
    "name": "reduce_bullet_count",
    "target": "method_panel"
  },
  "before": {
    "n_bullets": 8,
    "font_size": 12,
    "text_density": 0.86
  },
  "after": {
    "n_bullets": 5,
    "font_size": 14,
    "text_density": 0.61
  }
}
```

---

## **11.5 P4：更新 C 类指标**

建议正式 C 类更新为：

| 编号 | 文件名 | 说明 |
| --- | --- | --- |
| c1 | `c1_action_executability.py` | 保留 |
| c2 | `c2_convergence_rate.py` | 保留 |
| c3 | `c3_issue_resolution_rate.py` | 新增/替换原主位置 |
| c4 | `c4_per_iter_visual_gain.py` | 保留解释性指标 |

`action_distribution` 移入 analysis，不作为正式 16 指标。

---

## **11.6 P5：跑 same-initial repair experiment**

最小实验矩阵：

| Method | 目的 |
| --- | --- |
| `ours_no_svfp` | 无反馈 baseline |
| `ours_freeform` | 自由文本反馈 |
| `ours_svfp_v1` | 旧 schema，可选 |
| `ours_svfp_v2` | 新 5 issue schema |

如果 v2 比 v1 更好，可将 schema 大改作为论文增强点。

---

## **11.7 P6：跑 n=30 正式实验**

必须完成：

1. v5.3 后内容指标重算；
2. n=30 全量实验；
3. BH-FDR；
4. 效应量；
5. 置信区间；
6. pilot 不作为正式 claim；
7. 正文避免 n=5 结论。

---

## **11.8 P7：外部 SOTA 复现与可选 SVFP 后处理**

优先复现两个 SOTA 作为质量参照。

如果外部 SOTA 可输出 PPTX/HTML/JSON，则尝试：

- `sota`
- `sota_svfp`

如果只输出 PNG/PDF，不强行做 deterministic repair，可只作为 external quality reference。

---

# **12. 论文写作建议**

## **12.1 Intro 主问题**

不要写成：

> Existing systems generate low-quality posters.

建议写成：

> Modern VLMs can identify visual problems in generated posters, but their free-form critiques are difficult to execute reliably. This creates a critique-to-action gap in visual generation agents.

## **12.2 Method 主句**

> SVFP constrains VLM critiques into a closed issue-action schema and applies them through a deterministic FeedbackApplier, making visual feedback executable, convergent, and auditable.

## **12.3 Renderer 定位**

> PosterCS serves as a controllable structured layout substrate for evaluating SVFP, rather than being positioned as a standalone SOTA poster generator.

## **12.4 实验主 claim**

建议三个 claim：

### **Claim 1：Protocol Claim**

SVFP makes VLM feedback more executable and convergent than free-form feedback.

对应：

- c1；
- c2；
- c3；
- E1 free-form baseline。

### **Claim 2：Repair Claim**

Given the same initial poster, SVFP improves layout quality and readability with bounded latency.

对应：

- b1；
- b2；
- d1；
- same-initial repair comparison。

### **Claim 3：Generalization Claim**

SVFP is planner-agnostic and can improve outputs from different poster planners.

对应：

- `ours_svfp`；
- `gpt4o_zeroshot_svfp`；
- optional `sota_svfp`。

---

# **13. 当前最重要的实现优先级**

## **P0：不要立刻大改所有代码，先做 taxonomy audit**

原因：

- 证明新 5 issue 是数据驱动的；
- 避免主观重构；
- 为论文 MECE 性提供证据；
- 低风险。

## **P1：升级 ISSUE schema 和 prompt**

先只改 VLM 输出类别和 action mapping，不大改 renderer。

## **P2：补 render_state / svfp_trace**

这是后续 C 类指标、issue resolution、MECE audit 的基础。

## **P3：实现 c3_issue_resolution_rate**

这是新版 C 类里最值得加入的硬指标。

## **P4：跑 old schema vs new schema 小规模 ablation**

证明新 5 issue 不只是改名，而是真的更有效。

## **P5：跑 n=30 正式实验**

作为投稿主结果。

---

# **14. 最终确定内容清单**

## **14.1 论文方向**

保留原方向：

- 主：SVFP；
- 从：CS-Poster-30；
- 从：CS 垂直实例化。

## **14.2 新 ISSUE**

正式采用 5 类：

1. `space_imbalance`
2. `text_overload`
3. `visual_hierarchy_weak`
4. `asset_utilization_error`
5. `structure_alignment_error`

## **14.3 Guard**

低频硬约束降级为 guard：

1. `overlap_guard`
2. `contrast_guard`
3. `overflow_guard`
4. `crop_guard`

## **14.4 正式指标保持 16 个**

A：

1. `a1_key_info_recall.py`
2. `a2_hallucination_rate.py`
3. `a3_semantic_fidelity.py`

B：

4. `b1_layout_quality.py`
5. `b2_readability.py`
6. `b3_figure_reuse_rate.py`
7. `b4_figure_text_align.py`

C：

8. `c1_action_executability.py`
9. `c2_convergence_rate.py`
10. `c3_issue_resolution_rate.py`
11. `c4_per_iter_visual_gain.py`

D：

12. `d1_latency.py`
13. `d2_cost.py`

E：

14. `e1_paperquiz.py`
15. `e2_human_preference.py`
16. `e3_llm_judge.py`

## **14.5 Analysis 项**

不进正式 16 指标，但建议实现：

1. `analysis_issue_distribution.py`
2. `analysis_action_distribution.py`
3. `analysis_guard_trigger_rate.py`
4. `analysis_issue_mece_audit.py`

---

# **15. 给实现助手的工作提示**

后续让 Claude 实现时，建议按以下顺序拆任务：

1. 读取当前 SVFP issue/action schema；
2. 新建新版 issue enum；
3. 新增 guard enum；
4. 修改 VLM critique prompt；
5. 修改 FeedbackApplier action mapping；
6. 增加 render_state 输出；
7. 增加 svfp_trace 输出；
8. 实现 `analysis_issue_distribution.py`；
9. 实现 `analysis_issue_mece_audit.py`;
10. 实现 `c3_issue_resolution_rate.py`;
11. 将 action distribution 移入 analysis；
12. 更新 metrics config；
13. 跑 5-paper smoke；
14. 跑 old-vs-new SVFP ablation；
15. 跑 n=30；
16. 生成论文表格与统计结果。

---

# **16. 一句话总结**

PosterCS 的优化方向不是把自研 renderer 做成全面 SOTA，而是把它打磨成一个**可控、可执行、可审计的结构化版面实验基座**；论文主贡献仍然是 SVFP。后续重点应放在新版 5 类 MECE ISSUE taxonomy、协议级 C 指标、failure audit、issue resolution、same-initial repair 实验，以及 n=30 正式统计上。这样即使最终海报质量不全面超过外部 SOTA，论文仍然可以通过“结构化视觉反馈协议”这一方法论贡献成立。

*内容由 AI 生成仅供参考*