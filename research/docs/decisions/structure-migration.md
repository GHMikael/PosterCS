# Research workspace migration

日期：2026-10-10

## 决策

将原 `audit_v2_rewrite/` 整体冻结为 `archive/research-history-2026-10-10/`，建立 `research/` 作为论文研究的唯一活动目录。

## 原因

旧目录按时间阶段累积，包含大量 `v1/v2/v3`、临时网页、失败重跑、缓存和同义文件，适合保存研究过程，但不适合作为投稿前的可复现代码库。新目录按职责划分，并只保留每项材料的当前有效版本。

## 迁移规则

| 旧内容 | 新位置 | 处理方式 |
|---|---|---|
| 当前英文稿、参考文献 | `paper/` | 采用内容冻结后的稿件 |
| 正式实验协议 | `protocols/` | 去掉文件名版本号，内容不改写 |
| Prompt、模型与规则 | `configs/` | 统一小写、语义化命名 |
| Formal-88 | `data/formal/` | 金标准与 88 张输入自包含 |
| RuleDev | `data/rule-development/` | 仅保留验收后的 pair 与特征 |
| Controlled-48 | `data/controlled/` | 作为主要确认集 |
| External-20 | `data/external/` | 作为外部自然样本检查 |
| 正式预测与统计结果 | `results/` | 去掉路径中的日期和文件版本号 |
| 推理、规则、评分代码 | `src/postercs_audit/` | 改为 Python package 和相对路径 |
| 旧页面、失败轮次、备份 | `archive/` | 只读保留，不进入活动代码 |

## 不变量

- 不删除旧研究证据；历史快照保持完整。
- 不修改原项目中用户已有的其他 Git 改动。
- 论文已采用的 CSV/JSON 结果只迁移和改名，不重新计算。
- 新清单使用 `research/` 相对路径，并校验图片 SHA-256。
- 后续版本历史由 Git 记录，不再复制 `*_v2`、`*_v3` 文件。
