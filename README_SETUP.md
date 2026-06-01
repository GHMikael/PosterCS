# PosterCS 项目设置指南

## 📋 项目概述

PosterCS 是一个全新的、独立的论文生成海报研究项目，从 `poster_agent_backend` 完全迁移而来。

**重要**: 本项目完全独立，不依赖原项目，可以安全删除 `poster_agent_backend`。

## 🏗️ 项目结构

```
PosterCS/
├── app/                          # 核心应用代码
│   ├── main.py                   # FastAPI 主入口
│   ├── models.py                 # 数据模型
│   ├── pdf_assets.py             # PDF 资源提取
│   ├── layout_engine.py          # 布局引擎
│   ├── ppt_renderer.py           # PPT 渲染器 v5.3
│   ├── vlm_commenter.py          # VLM 视觉评论器
│   ├── feedback_loop.py          # SVFP 反馈循环
│   └── ...
│
├── experiments/                  # 实验框架
│   ├── baselines/                # 基线方法
│   │   ├── ours_svfp.py          # E1: 我们的方法 + SVFP
│   │   ├── ours_no_svfp.py       # E1: 我们的方法 - SVFP
│   │   ├── ours_freeform.py      # E1: 我们的方法 + 自由形式反馈
│   │   └── gpt4o_zeroshot_svfp.py # E2: GPT-4o zero-shot + SVFP
│   │
│   ├── metrics/                  # 评估指标
│   │   ├── visual_smoke_check.py # 视觉质量检测
│   │   ├── figure_reuse_rate.py  # 图片复用率
│   │   ├── a1_information_retention.py
│   │   ├── a2_figure_text_alignment.py
│   │   ├── a3_hallucination.py
│   │   ├── a4_section_coverage.py
│   │   ├── b1_layout_rationality.py
│   │   ├── b2_readability.py
│   │   ├── b3_academic_compliance.py
│   │   ├── protocol_metrics.py
│   │   └── ...
│   │
│   ├── scripts/                  # 实验脚本
│   │   ├── run_matrix.py         # 批量运行实验
│   │   ├── compute_metrics.py    # 计算指标
│   │   ├── aggregate_stats.py    # 聚合统计
│   │   ├── plot_figures.py       # 绘制图表
│   │   ├── print_paper_table.py  # 打印论文表格
│   │   ├── audit_figures.py      # 审计图片
│   │   ├── batch_dify_runs.py    # Dify 批量运行
│   │   └── ...
│   │
│   ├── tools/                    # 实验工具
│   │   ├── llm_client.py         # LLM 客户端
│   │   ├── experiment_logger.py  # 实验日志
│   │   ├── pricing.py            # 成本计算
│   │   └── ...
│   │
│   ├── tests/                    # 测试套件
│   │   ├── test_visual_smoke_check.py
│   │   ├── test_figure_reuse_rate.py
│   │   ├── test_a3_hallucination.py
│   │   ├── test_protocol_metrics.py
│   │   └── ...
│   │
│   ├── datasets/                 # 数据集
│   │   ├── papers/               # 论文 PDF（需要手动添加）
│   │   ├── gold/                 # 金标准数据
│   │   ├── planner_cache/        # 规划器缓存
│   │   └── prepare_dataset.py    # 数据集准备脚本
│   │
│   ├── configs/                  # 配置文件
│   │   ├── baselines.yaml        # 基线配置
│   │   ├── e1_smoke_baselines.yaml # E1 smoke 配置
│   │   ├── metrics.yaml          # 指标配置
│   │   ├── papers_30.json        # 30 篇论文清单
│   │   ├── papers_5.json         # 5 篇论文清单
│   │   └── prompts/              # 提示词模板
│   │
│   └── results/                  # 实验结果（空目录）
│       ├── artifacts/            # 生成的海报
│       ├── metrics/              # 指标结果
│       ├── aggregate/            # 聚合统计
│       └── figures/              # 图表
│
├── dify/                         # Dify 集成（预留）
├── datasets/                     # 数据集根目录（预留）
│
├── .env.example                  # 环境变量示例
├── .gitignore                    # Git 忽略规则
├── requirements.txt              # Python 依赖
├── README.md                     # 项目说明（英文）
├── README.zh-CN.md               # 项目说明（中文）
└── README_SETUP.md               # 本文件
```

## 🚀 快速开始

### 1. 环境设置

```bash
cd /Users/mikaelsnow/Documents/ECNU/Paper_Comment_Poster/PosterCS

# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 API keys
# - DASHSCOPE_API_KEY: 阿里云 DashScope API key（用于 Qwen VL）
# - DIFY_API_KEY: Dify API key（可选，用于批量运行）
```

### 3. 准备数据集

```bash
# 将论文 PDF 放入 experiments/datasets/papers/ 目录
# 例如：
# experiments/datasets/papers/多模态预训练.pdf
# experiments/datasets/papers/LLM记忆评估.pdf
# ...

# 运行数据集准备脚本（提取 PDF 元数据）
python -m experiments.datasets.prepare_dataset
```

### 4. 运行测试

```bash
# 运行所有测试
pytest experiments/tests/ -v

# 运行特定测试
pytest experiments/tests/test_visual_smoke_check.py -v
```

### 5. 运行第一个实验

```bash
# 单篇论文测试
python -m experiments.scripts.run_one_paper \
  --paper experiments/datasets/papers/多模态预训练.pdf \
  --baseline ours_svfp \
  --out experiments/results/test_run

# 批量运行 E1 smoke（5 篇论文 × 3 个基线）
python -m experiments.scripts.run_matrix \
  --config experiments/configs/e1_smoke_baselines.yaml \
  --out experiments/results/artifacts_e1_smoke

# 计算指标
python -m experiments.scripts.compute_metrics \
  --artifact experiments/results/artifacts_e1_smoke \
  --metrics visual_smoke_check,figure_reuse_rate,protocol_metrics \
  --out experiments/results/metrics_e1_smoke

# 聚合统计
python -m experiments.scripts.aggregate_stats \
  --metrics experiments/results/metrics_e1_smoke \
  --out experiments/results/aggregate_e1_smoke
```

## 📊 实验流程

### E1: 三臂实验（消融研究）

```bash
# 1. 运行 E1 smoke（5 篇论文）
python -m experiments.scripts.run_matrix \
  --config experiments/configs/e1_smoke_baselines.yaml \
  --out experiments/results/artifacts_e1_smoke

# 2. 计算所有指标
python -m experiments.scripts.compute_metrics \
  --artifact experiments/results/artifacts_e1_smoke \
  --metrics visual_smoke_check,figure_reuse_rate,protocol_metrics,a1_information_retention,a3_hallucination \
  --out experiments/results/metrics_e1_smoke

# 3. 聚合统计
python -m experiments.scripts.aggregate_stats \
  --metrics experiments/results/metrics_e1_smoke \
  --out experiments/results/aggregate_e1_smoke

# 4. 打印论文表格
python -m experiments.scripts.print_paper_table \
  --aggregate experiments/results/aggregate_e1_smoke
```

### E2: 跨规划器基线

```bash
# 运行 GPT-4o zero-shot baseline
python -m experiments.scripts.run_matrix \
  --config experiments/configs/baselines.yaml \
  --baselines gpt4o_zeroshot_svfp \
  --out experiments/results/artifacts_e2
```

### 正式 n=30 实验

```bash
# 使用 papers_30.json 运行完整实验
python -m experiments.scripts.run_matrix \
  --config experiments/configs/baselines.yaml \
  --papers experiments/configs/papers_30.json \
  --out experiments/results/artifacts_n30
```

## 🧪 测试套件

```bash
# 运行所有测试
pytest experiments/tests/ -v

# 测试覆盖：
# - test_visual_smoke_check.py: 视觉质量检测
# - test_figure_reuse_rate.py: 图片复用率
# - test_a3_hallucination.py: 幻觉检测
# - test_protocol_metrics.py: 协议指标
# - test_pdf_assets_filter.py: PDF 资源过滤
# - test_ppt_renderer_binding.py: PPT 渲染器绑定
```

## 📝 关键文件说明

### 配置文件

- **experiments/configs/baselines.yaml**: 所有基线方法的配置
- **experiments/configs/e1_smoke_baselines.yaml**: E1 smoke 实验配置（5 篇论文）
- **experiments/configs/metrics.yaml**: 所有指标的配置
- **experiments/configs/papers_30.json**: CS-Poster-30 数据集清单
- **experiments/configs/papers_5.json**: E1 smoke 数据集清单

### 核心模块

- **app/ppt_renderer.py**: PPT 渲染器 v5.3（修复了标题截断和 Method 卡片文本问题）
- **app/feedback_loop.py**: SVFP 反馈循环（4 种问题类型 × 9 种确定性动作）
- **app/vlm_commenter.py**: VLM 视觉评论器（闭合模式视觉批评）
- **experiments/baselines/ours_svfp.py**: 我们的方法 + SVFP（E1 主臂）

### 新增指标

- **experiments/metrics/visual_smoke_check.py**: 检测文本溢出、省略号、微小字体
- **experiments/metrics/figure_reuse_rate.py**: 诚实报告图片复用率
- **experiments/metrics/protocol_metrics.py**: SVFP 协议指标（问题分布、动作分布）

## 🔧 依赖项

```
fastapi==0.116.1
uvicorn==0.35.0
python-multipart==0.0.20
pydantic==2.8.2
python-pptx==0.6.23
Pillow==10.4.0
PyMuPDF==1.24.9
requests==2.32.3
python-dotenv==1.0.1
openai==1.101.0
```

## ⚠️ 重要提示

1. **完全独立**: 本项目不依赖 `poster_agent_backend`，可以安全删除原项目
2. **数据集为空**: `experiments/datasets/papers/` 目录为空，需要手动添加论文 PDF
3. **实验结果为空**: `experiments/results/` 目录为空，需要运行实验生成
4. **环境变量**: 必须配置 `.env` 文件中的 API keys 才能运行
5. **虚拟环境**: 强烈建议使用虚拟环境，避免依赖冲突

## 📚 文档

- **README.md**: 项目概述（英文）
- **README.zh-CN.md**: 项目概述（中文）
- **INTERNAL_EXPERIMENT_GUIDE.md**: 内部实验指南
- **RESEARCH_DIRECTION_v3.md**: 研究方向 v3

## 🎯 下一步

1. **立即可做**（1 小时）
   - 阅读 README.zh-CN.md
   - 配置环境变量
   - 运行测试套件

2. **稍后可做**（2-3 小时）
   - 准备数据集（添加论文 PDF）
   - 运行 E1 smoke（5 篇论文）
   - 验证新 renderer 质量

3. **最终目标**（3-5 周）
   - 运行正式 n=30 实验
   - 独立视觉验证
   - 用户研究

---

**祝你实验顺利！** 🚀
