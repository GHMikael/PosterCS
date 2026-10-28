# RuleDev-72 数据协议 v1

日期：2026-09-28  
状态：生成前冻结

## 目的

RuleDev-72 仅用于开发六类确定性规则的阈值和 abstention 区间，不用于报告最终测试性能。
Formal-88 不参与样本生成、参数选择或阈值调整。

## 规模

- 6 个目标缺陷；
- 每类 3 种布局 × 2 个难度，共 6 对；
- 每对包含一个 control 和一个只注入目标缺陷的 mutation；
- 合计 36 对、72 张。

布局为 `dashboard`、`columns`、`storyflow`；难度为 `moderate`、`severe`。

## 六类注入

1. `body_text_too_small`：只缩小一个实质正文板块的字号。
2. `figure_detail_unreadable`：保持图片区位置不变，只减小图内标签和数字。
3. `text_overload`：保持字号与板块几何不变，只增加一个板块的文本量。
4. `space_imbalance`：把正文板块集中到一侧，形成大块留白与局部拥挤。
5. `alignment_error`：只移动并收窄一个主板块，使其偏离重复网格。
6. `overlap_or_clipping`：在一个结论文本区制造可见遮挡和不完整省略号。

## 文件要求

每个样本对必须保存 control/mutation 的 PPTX、2400×1350 PNG、图表源图、注入参数、随机种子、
SHA-256 和人工验收状态。人工验收检查：目标缺陷可见、control 干净、没有额外 Primary 缺陷。

## 隔离规则

- 不能复制 Formal-88 图片或使用其单样本得分选择参数。
- RuleDev 的模板、文字和图表由固定生成器产生。
- 规则冻结后不得回到 RuleDev 增加候选阈值；后续只允许在独立 Hybrid-Test 上一次性评估。
