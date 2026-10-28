# PosterCS Research Workspace

这是 PosterCS 论文研究的**当前唯一有效工作区**。从 2026-10-10 起，后续实验、论文修改和投稿材料都以本目录为准；旧的 `audit_v2_rewrite` 已整体冻结到历史快照，不再继续修改。

## 当前研究主线

论文研究科学海报审计中的证据分工：VLM 擅长较主观的视觉与语义判断，source-aware rule 擅长可测量的几何与渲染缺陷，Hybrid 通过冻结的路由策略组合二者。当前证据包括 Formal-88 探索实验、RuleDev 阈值开发、Controlled-48 确认实验、External-20 外部检查与重复运行稳定性分析。

## 从哪里开始

- 读论文：[`paper/manuscript.md`](paper/manuscript.md)
- 看当前状态：[`docs/reports/project-status.md`](docs/reports/project-status.md)
- 看 IJDAR 投稿路线：[`paper/reviews/ijdar-revision-roadmap.md`](paper/reviews/ijdar-revision-roadmap.md)
- 看实验设计：[`protocols/`](protocols/)
- 看冻结配置：[`configs/`](configs/)
- 看金标准与清单：[`data/`](data/)
- 看最终结果：[`results/`](results/)
- 改研究代码：[`src/postercs_audit/`](src/postercs_audit/)

## 目录约定

```text
research/
├── paper/       # 稿件、图表、补充材料、模拟审稿记录
├── protocols/   # 冻结的实验与评分协议
├── configs/     # 模型、Prompt、规则和运行配置
├── data/        # 金标准、开发集、确认集与外部集
├── src/         # 可复用 Python 包
├── results/     # 已确认的统计结果与正式预测
├── scripts/     # 数据物化和维护脚本
├── tests/       # 结构、清单和核心逻辑检查
└── docs/        # 决策记录与阶段报告
```

文件名不再使用 `v1/v2/v3` 表示当前版本。当前内容由 Git 管理；实验内部保留的 `rule_version`、taxonomy version 等字段属于可复现性元数据，不是并列文件版本。

## 常用检查

在项目根目录执行：

```bash
PYTHONPATH=research/src .venv/bin/python -m pytest research/tests
PYTHONPATH=research/src .venv/bin/python -m postercs_audit.inference.runner \
  --config research/configs/controlled-gemini.yaml --dry-run
```

正式调用模型前，应先运行 `--dry-run`；Formal-88 运行还必须显式添加 `--allow-formal`。新运行写入 `research/runs/`，不会覆盖论文采用的冻结结果。

## 历史恢复

完整历史快照位于：

```text
archive/research-history-2026-10-10/
```

它只用于追溯旧标注页面、旧脚本、旧版本输出和迁移来源，不应被新代码 import，也不应作为新配置的数据路径。
