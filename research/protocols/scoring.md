# Formal-88 评分协议 v1

冻结日期：2026-09-25  
状态：**评分口径已冻结；正式模型成绩尚未计算。**

## 1. 目标与分析单位

本阶段评估四个 VLM 配置在三个 Prompt 条件下对学术海报可见缺陷的识别能力。
Natural-40 与 Controlled-48 分开报告，不用一个混合总分替代二者。

- Natural-40：40 张海报，来自 20 篇论文；bootstrap 与方法比较以 `pair_id` 为聚类单位。
- Controlled-48：24 个 control/mutation 对；统计重采样与比较以 `pair_id` 为单位。
- 每个模型 × Prompt 条件均应有 Natural 40 项与 Controlled 48 项。

## 2. 固定标签、阳性与匹配

固定九类标签：

1. `body_text_too_small`
2. `figure_detail_unreadable`
3. `text_overload`
4. `space_imbalance`
5. `alignment_error`
6. `weak_hierarchy`
7. `overlap_or_clipping`
8. `asset_missing_or_broken`
9. `other`

主分析只把 severity 2–3 计为阳性；severity 1 保留但只进入探索性敏感性分析。
不使用 confidence 阈值。`none` 不是缺陷标签。`other` 只按标签匹配，不根据自由文本进行
事后语义匹配。每张海报中同一标签最多计一次。

Primary 使用十分类：九类缺陷加 `none`。预测 Primary 已按推理阶段冻结规则保证只来自
severity 2–3 的问题，否则为 `none`。

## 3. Natural-40 指标

### 3.1 主要指标

- **Macro-F1**：在该 split 中 Gold support ≥ 1 的标签上等权平均。

Gold support 为 0 的标签没有可估计召回率和 F1，逐类表记为 `NA`，不进入 Macro-F1。
对 Gold support ≥ 1 的标签，若模型完全不预测该标签，则 Precision、Recall、F1 按 0
处理，避免因不预测而抬高宏平均。

### 3.2 次要指标

- Micro Precision、Recall、F1。
- 每图标签集合 Jaccard 的均值。
- Exact Match：severity 2–3 标签集合完全一致。
- Primary accuracy、Primary macro-F1、Primary Cohen's κ。
- 九类逐类 support、TP、FP、FN、TN、Precision、Recall、F1。
- 过报数、漏报数，以及每图预测标签数与 Gold 标签数。

### 3.3 严重度

仅在 Gold 与预测均命中同一标签的实例上计算 severity MAE、exact agreement 和线性加权
κ。该结果是“命中条件下的严重度一致性”，不能解释为端到端缺陷识别能力。

## 4. Controlled-48 指标

每个 pair 具有一个预先注入的 `target_label`。

### 4.1 主要指标

- **Paired target correctness**：mutation 对目标标签判断为阳性，同时 control 对同一目标
  标签判断为阴性。24 对中满足该条件的比例。

### 4.2 次要指标

- Mutation target recall：mutation 中识别出目标标签的比例。
- Target-specific control FPR：control 中错误报告目标标签的比例。
- Any-defect control FPR：control 中报告任意 severity 2–3 缺陷的比例。
- 六个注入标签各自的上述指标。
- 目标标签 confidence 的 mutation-control 差值；目标标签未以 severity 2–3 报告时记 0。
- mutation 与 control 的预测缺陷数差值。

Controlled-48 的 control 只用于衡量系统对预先设计的干净对照的误报，不把该结果外推为
任意真实海报上的 specificity。

## 5. 置信区间与统计比较

- 所有主要和次要比例/性能指标报告 95% percentile cluster bootstrap CI。
- bootstrap 次数固定 10,000，随机种子固定 20260925。
- Natural 按 20 个论文 `pair_id` 重采样；Controlled 按 24 个实验 `pair_id` 重采样。
- 两方法差异使用同一批 cluster 索引做 paired bootstrap，报告差值与 95% CI。
- 二元逐样本或逐 pair 成败比较可补充 exact McNemar 检验。
- 多重比较按分析族使用 Holm 校正；原始 p 值与校正值同时保存。
- 不仅报告显著性，还必须报告绝对差值和置信区间。

预定义比较族：

1. Prompt：每个模型内 P2−P1、P3−P1、P3−P2。
2. 模型：每个 Prompt 内四模型的六个两两比较。
3. Qwen 规模效应：Qwen-32B−Qwen-8B 单独作为预设同家族对照报告，但仍保留在对应
   模型比较族的 Holm 校正中。

Natural 主要比较 Macro-F1；Controlled 主要比较 paired target correctness。其他指标的
比较明确标为次要或探索性。

## 6. 失败、重试与成本

- 最终缺失预测不得按 `none` 计分；应从指标分母中剔除并单独报告 coverage。
- 本次正式运行经 missing-only 补跑后 coverage 为 1056/1056，但评分代码仍保留该规则。
- 同时报告最终任务失败率和 attempt 级 API/validation error 率。
- 延迟以最终合法请求为主；重试次数与全部可计费用量另表报告。

## 7. 探索性分析

以下结果不改变主要结论：

- 将 severity 1–3 全部视为阳性的敏感性分析。
- confidence 的 AUROC、AUPRC、Brier score 与校准误差；未报告标签的 confidence 记 0。
- Gold 来源分层、模板分层、original/renderer 变体分层。
- 区域证据和修复建议的定性分析。

探索性分析不用于选择主要模型、Prompt 或阈值。

## 8. 数据输入与不可变性

- Gold：`05_formal_experiment/formal88_gold.csv`
- 主预测：`06_inference/runs/formal_20260924_v1/parsed/`
- 补跑预测：`06_inference/runs/formal_20260924_v1_supplement01/parsed/`
- Natural pair key：`05_formal_experiment/natural40/blind_key.json`
- Controlled pair key：`05_formal_experiment/controlled48/injection_manifest.json`

输入 SHA-256 固定在 `configs/scoring_v1.json`。评分脚本不得改写 Gold、原始响应或 parsed
预测。若哈希或覆盖关系变化，必须停止并生成新协议版本，不能静默继续。

## 9. 本阶段输出边界

协议冻结阶段只运行 synthetic tests 和输入前置检查，不计算 Formal-88 模型成绩。
正式评分必须在下一阶段通过显式 `--allow-score` 门启动，并把输出写入新的只增不改目录。
