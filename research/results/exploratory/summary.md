# Formal-88 正式评分结果摘要 v1

生成日期：2026-09-25  
状态：**正式评分已完成并通过独立一致性核验。**

## 1. 评分范围与完整性

- 数据：Natural-40 + Controlled-48，共 88 张图像。
- 条件：4 个 VLM × 3 个 Prompt，共 12 个条件。
- 预测：每个条件 88 条，共 1056/1056 条，coverage 为 100%。
- 阳性阈值：severity 2–3；不使用 confidence 阈值。
- 置信区间：按 `pair_id` 聚类的 10,000 次 percentile bootstrap，95% CI。
- 方法比较：paired bootstrap；Natural 辅以配对随机化检验，Controlled 使用 exact McNemar；同一比较族使用 Holm 校正。
- 输入哈希均与冻结配置一致；评分过程未改写 Gold、原始响应或 parsed 预测。

## 2. 主要结果

### 2.1 Natural-40：真实系统缺陷识别

主要指标为 Gold support ≥ 1 标签上的 Macro-F1。

| 排名 | 模型 | Prompt | Macro-F1 | 95% CI |
|---:|---|---|---:|---:|
| 1 | Gemini Flash | P3 Evidence-grounded | 0.634 | [0.520, 0.747] |
| 2 | Gemini Flash | P2 Taxonomy | 0.610 | [0.512, 0.745] |
| 3 | Qwen VL 32B | P2 Taxonomy | 0.530 | [0.480, 0.577] |
| 4 | Gemini Flash | P1 Paper2Poster-style | 0.514 | [0.459, 0.570] |
| 5 | Qwen VL 32B | P3 Evidence-grounded | 0.496 | [0.436, 0.551] |

其余条件：GLM 的最佳结果为 P2 的 0.252；Qwen VL 8B 三个 Prompt 均为 0。

Natural-40 中，Gemini P3 的逐类 F1 为：

- `figure_detail_unreadable`：0.724；
- `overlap_or_clipping`：0.870；
- `space_imbalance`：0.308。

### 2.2 Controlled-48：受控缺陷辨别

主要指标为 paired target correctness，即 mutation 检出目标缺陷且对应 control 不误报该目标缺陷。

| 排名 | 模型 | Prompt | Paired correctness | 95% CI |
|---:|---|---|---:|---:|
| 1 | Gemini Flash | P2 Taxonomy | 0.625 | [0.417, 0.792] |
| 2 | Qwen VL 32B | P3 Evidence-grounded | 0.542 | [0.333, 0.750] |
| 3 | Gemini Flash | P1 Paper2Poster-style | 0.500 | [0.292, 0.708] |
| 3 | Gemini Flash | P3 Evidence-grounded | 0.500 | [0.292, 0.708] |
| 5 | GLM VL Flash | P2 Taxonomy | 0.250 | [0.083, 0.417] |

Gemini P2 的 mutation target recall 为 0.750，但 any-defect control FPR 为 0.500；它较敏感，仍有过报。
Qwen 32B P3 的 mutation target recall 为 0.542，any-defect control FPR 为 0；它更保守，目标辨别与控制误报之间更均衡。

## 3. Prompt 与模型效应

Holm 校正后显著的主要 Prompt 差异：

- Qwen 32B / Natural：P2−P1 = +0.334，校正后 p=0.0012；P3−P1 = +0.300，校正后 p=0.0012。
- Qwen 32B / Controlled：P3−P1 = +0.417，校正后 p=0.0234；P3−P2 = +0.375，校正后 p=0.0430。
- GLM / Natural：P2−P1 = +0.137，校正后 p=0.0230。
- Gemini 的三个 Prompt 在 Holm 校正后均无显著差异。

因此，“结构化 taxonomy 或证据约束能改善弱提示词”在 Qwen 32B 和 GLM 上有支持，但不能概括为对所有模型都显著有效。

Gemini 与 Qwen 32B 的核心比较：

- Natural / P1：Gemini 明显优于 Qwen 32B，差值 0.318，校正后 p=0.0018。
- Natural / P2、P3：两者差异在 Holm 校正后不显著。
- Controlled / P2：Gemini 优于 Qwen 32B，差值 0.458，校正后 p=0.0137。
- Controlled / P3：两者几乎持平，差值为 Qwen 32B +0.042，校正后 p=1.0。

## 4. 重要失败模式

### 4.1 Qwen VL 8B 的零分不是评分故障

Qwen VL 8B 在 3 个 Prompt × 88 张图像的 264 次合法响应中，全部输出 `primary_issue=none`，没有 severity 2–3 缺陷。原始响应状态均为 valid，因此这是模型在当前协议下的系统性漏检，而非解析失败。

### 4.2 难类仍未解决

Controlled-48 显示：

- `text_overload`：最佳 mutation recall 只有 0.25；
- `alignment_error`：只有 Gemini P2 达到 0.50，其余条件均为 0；
- `body_text_too_small` 与 `figure_detail_unreadable` 对模型和 Prompt 非常敏感；
- `overlap_or_clipping` 与 `space_imbalance` 相对容易，但容易被模型泛化过度而造成 control 误报。

这支持论文的核心问题：VLM 审计能力并非只由模型规模决定，还高度依赖缺陷类别、Prompt 约束和误报容忍度。

## 5. 数据覆盖边界

Natural-40 的 severity 2–3 Gold 只自然出现三类：

| 标签 | Gold support |
|---|---:|
| `overlap_or_clipping` | 38 |
| `figure_detail_unreadable` | 21 |
| `space_imbalance` | 4 |

其余六类在 Natural-40 中 support 为 0。Controlled-48 覆盖六种预设注入缺陷，每类 4 对，未覆盖 `weak_hierarchy`、`asset_missing_or_broken` 和 `other`。

因此当前 Formal-88 可以支持：

1. 四个模型和三种 Prompt 的受控比较；
2. 对本系统高频真实缺陷的识别评估；
3. 对六类可控视觉缺陷的因果式配对测试。

但不能支持“九类缺陷均已被充分验证”或“对任意学术海报均具有稳定审计能力”的强结论。Natural-40 中 `overlap_or_clipping` 的高占比也说明结果明显受当前 renderer 自动截断/省略号问题影响。

## 6. 当前推荐结论

- 论文主模型候选：**Gemini Flash + P2**。它不是每张表的第一名，但在 Natural 与 Controlled 两个任务上最稳定，且 P2 的结构明确、易复现。
- 低误报候选：**Qwen VL 32B + P3**。Controlled control 的 any-defect FPR 为 0，适合需要保守、可执行反馈的系统模式。
- GLM VL Flash：可保留为低能力梯度，结果有区分度，但不适合作为最终审计器。
- Qwen VL 8B：当前配置下不适合作为审计模型；它可以作为“弱模型/能力下限”对照。

正式测试集已经揭盲并完成评分，不应再根据这些结果修改 Prompt 或阈值。如果要优化 Prompt，必须使用新的开发集，再在独立扩展测试集上验证。

## 7. 下一阶段建议

优先进入 **Phase 3：错误分析与系统方案确定**，而不是立即重跑 Formal-88：

1. 对 Gemini P2 与 Qwen 32B P3 做逐样本 TP/FP/FN 归因，确定哪些问题交给 VLM、哪些交给确定性规则。
2. 构建 rule-only baseline，至少覆盖截断/省略号、几何重叠、图片显示尺寸和留白比例。
3. 构建 hybrid router：可测问题优先走规则，语义/层级问题交给 VLM，并设置 abstention。
4. 在独立的新扩展集上补 `weak_hierarchy`、`asset_missing_or_broken` 和更充分的 `text_overload` / `alignment_error`；不改动 Formal-88。
5. 最后评估修复闭环：修复前后缺陷减少、无副作用率以及人工偏好。

## 8. 文件索引

- `natural_overall_metrics.csv`：Natural 条件级总指标。
- `natural_per_label_metrics.csv`：Natural 逐标签混淆统计与 F1。
- `controlled_overall_metrics.csv`：Controlled 条件级总指标。
- `controlled_per_target_metrics.csv`：Controlled 逐注入标签指标。
- `confidence_intervals.csv`：全部 bootstrap 置信区间。
- `primary_comparisons.csv`：Prompt/模型配对比较与 Holm 校正。
- `predictions_merged.csv`：1056 条评分输入的统一追踪表。
- `scoring_manifest.json`：配置、输入、输出哈希与运行元数据。

