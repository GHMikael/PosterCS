# T8-C 阈值选择协议 v1

日期：2026-09-28  
状态：候选阈值表在首次运行前冻结。跨类别 QA 条款在首次结果复核时追加，仅用于验收，未参与阈值选择或修改。

## 1. 数据隔离

- 只使用 `04_ruledev72/accepted_pairs_v1.csv` 中冻结的 33 个 pair（66 张图）。
- 只使用 `features_v1/accepted_poster_features_v1.csv` 中对应的冻结特征。
- Formal-88 不参与候选特征、阈值、abstention 区间或路由规则的选择。
- 每次交叉验证以 pair 为组，同时留出 control 与 mutation，禁止图像级拆分。

## 2. 选择目标

候选规则先满足开发集 control false-positive rate ≤ 10%，再按以下顺序选择：

1. control 为 negative 且 mutation 为 positive 的完整 pair 比例；
2. mutation positive rate；
3. control negative rate；
4. non-abstain coverage；
5. 同分时选择更保守的 positive 边界。

同时报告 leave-one-pair-out（LOPO）结果。开发集样本量较小，LOPO 只衡量规则在 RuleDev
布局/难度间的稳定性，不替代独立 Hybrid-Test。

阈值冻结后另做一项不参与候选选择的跨类别 QA：目标 mutation 以外的 61–62 张图均视为
“非目标样本”，检查规则是否被其他缺陷误触发。该 QA 的 FPR 也必须 ≤ 10%，但不据此反向改阈值。

## 3. 预定义候选

候选值来自 1080p 归一化尺寸、PPT 字号、网格比例和可解释的对象计数；每个 detector 只允许
下列有限候选，脚本不得从样本唯一值无限搜索。

| ID | 轨道 | 特征与方向 | positive 候选 | negative 候选 |
|---|---|---|---|---|
| R1R | Raster | 正文行高 p25，越小风险越高 | ≤ 8/9/10/11/12 px | ≥ 14/16/18/20 px |
| R1S | Source | 正文最小字号，越小风险越高 | ≤ 7/8/9 pt | ≥ 10/11/12 pt |
| R2R | Raster | 图区无法可靠定位 | 仅做候选诊断 | 固定 abstain |
| R2S | Source | 图内细节显示高度 p25，越小风险越高 | ≤ 2/2.5/3/3.5/4 px | ≥ 4.5/5/5.5 px |
| R3R | Raster | OCR 字符数，越大风险越高 | ≥ 800/850/900/950 | ≤ 700/725/750/775 |
| R3S | Source | 字符数与最大文本密度同时过高 | chars ≥ 850/900/950；density ≥ 3500/3750/4000 | chars ≤ 775/800/825；density ≤ 3250/3350/3450 |
| R4R | Raster | 左右质量差与局部网格方差同时过高 | asym ≥ .06/.07/.08/.09；std ≥ .20/.202/.204/.206 | asym ≤ .03/.04/.05；std ≤ .20/.205/.21 |
| R4S | Source | 大块空白与左右质量差同时存在 | blank ≥ .06/.09/.12/.15；asym ≥ .15/.20/.25/.30 | blank ≤ 0/.03/.06；asym ≤ .10/.12/.15 |
| R5R | Raster | 稳定主 panel 网格的最大偏移 | ≥ .018/.020/.022/.024 | ≤ .014/.016/.018 |
| R5S | Source | 命名主 panel 未聚类边比例 | ≥ .04/.06/.08 | ≤ 0/.02/.04 |
| R6R | Raster | OCR 省略号/边界证据 | 仅做候选诊断 | 固定 abstain |
| R6S | Source | source 省略号且存在内容对象重叠 | 两项均 ≥ 1 | 两项均为 0 |

多信号规则只有在所有 positive 条件同时满足时才报 positive；所有 negative 条件同时满足时才报
negative；其余为 abstain。无稳定网格、无图片、缺失 OCR 或缺失 source 时输出
`not_applicable`/`abstain`，不得转成 negative。

## 4. 两项预先限定的 Raster 弃用条件

- `figure_detail_unreadable`：若只能依靠整张海报 OCR 数量、无法定位图区并给出图内尺度证据，R2R
  冻结为 always-abstain。
- `overlap_or_clipping`：若 OCR 省略号不能在至少 5/6 mutation 上触发，或 control 出现误触发，R6R
  冻结为 always-abstain。

这两项仍保留候选诊断结果，避免只汇报成功规则。

## 5. 冻结产物

- `candidate_thresholds_v1.json`：全部候选和被拒绝原因；
- `threshold_cv_results_v1.csv`：全量拟合与 LOPO 指标；
- `ruledev_predictions_v1.csv`：每图决策和证据；
- `all_ruledev_predictions_v1.csv` 与 `cross_label_qa_v1.csv`：冻结后的跨类别误触发检查；
- `rule_v1.json`：最终 Raster/Source 规则；
- `hybrid_routing_policy_v1.json`：后续 Hybrid-Test 使用的候选路由；
- `rule_freeze_manifest_v1.json`：输入、代码、配置哈希；
- `THRESHOLD_SELECTION_REPORT_v1.md`：结果、限制和下一步。
