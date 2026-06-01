# 🎯 PosterCS - 从这里开始

**欢迎来到 PosterCS 项目！** 这是一个全新的、完全独立的论文生成海报研究项目。

---

## ⚡ 快速开始（5 分钟）

### 1. 激活环境
```bash
cd /Users/mikaelsnow/Documents/ECNU/Paper_Comment_Poster/PosterCS
source .venv/bin/activate
```

### 2. 配置 API Key
```bash
# 编辑 .env 文件
nano .env

# 填入你的 DASHSCOPE_API_KEY
DASHSCOPE_API_KEY=sk-xxxxx
```

### 3. 验证安装
```bash
# 运行测试（应该全部通过）
pytest experiments/tests/ -v

# 预期结果：27 passed
```

---

## 📚 文档导航

### 新手入门
- **[README_SETUP.md](README_SETUP.md)** - 完整的项目设置指南（必读）
- **[README.zh-CN.md](README.zh-CN.md)** - 项目概述（中文）
- **[MIGRATION_REPORT.md](MIGRATION_REPORT.md)** - 迁移报告

### 实验指南
- **[INTERNAL_EXPERIMENT_GUIDE.md](INTERNAL_EXPERIMENT_GUIDE.md)** - 实验操作指南
- **[RESEARCH_DIRECTION_v3.md](RESEARCH_DIRECTION_v3.md)** - 研究方向和优化计划

---

## 🎯 项目状态

✅ **已完成**
- 代码迁移完成（79 个 Python 文件）
- 环境设置完成（虚拟环境 + 依赖）
- 测试验证通过（27/27 测试通过）
- 文档完整（6 个核心文档）

⏳ **待完成**
- 添加论文 PDF 到 `experiments/datasets/papers/`
- 运行第一个实验
- 开始 n=30 正式实验

---

## 🚀 下一步

### 选项 1: 运行单篇论文测试（10 分钟）
```bash
# 将一篇论文 PDF 放入 experiments/datasets/papers/
cp ~/Downloads/your_paper.pdf experiments/datasets/papers/

# 运行单篇测试
python -m experiments.scripts.run_one_paper \
  --paper experiments/datasets/papers/your_paper.pdf \
  --baseline ours_svfp \
  --out experiments/results/test_run
```

### 选项 2: 运行 E1 smoke（5 篇论文，2-3 小时）
```bash
# 准备 5 篇论文（参考 experiments/configs/papers_5.json）
# 然后运行批量实验
python -m experiments.scripts.run_matrix \
  --config experiments/configs/e1_smoke_baselines.yaml \
  --out experiments/results/artifacts_e1_smoke
```

### 选项 3: 直接运行 n=30 实验（1-2 天）
```bash
# 准备 30 篇论文（参考 experiments/configs/papers_30.json）
# 然后运行完整实验
python -m experiments.scripts.run_matrix \
  --config experiments/configs/baselines.yaml \
  --papers experiments/configs/papers_30.json \
  --out experiments/results/artifacts_n30
```

---

## 📊 项目结构速览

```
PosterCS/
├── app/                          # 核心应用（13 个模块）
│   ├── main.py                   # FastAPI 入口
│   ├── ppt_renderer.py           # PPT 渲染器 v5.3
│   ├── feedback_loop.py          # SVFP 反馈循环
│   └── ...
│
├── experiments/                  # 实验框架
│   ├── baselines/                # 基线方法（8 个）
│   ├── metrics/                  # 评估指标（15 个）
│   ├── scripts/                  # 实验脚本（10 个）
│   ├── judges/                   # 评判模块（10 个）
│   ├── tools/                    # 工具模块（6 个）
│   ├── tests/                    # 测试套件（7 个）
│   ├── datasets/                 # 数据集（空，需添加）
│   ├── configs/                  # 配置文件（9 个）
│   └── results/                  # 结果目录（空）
│
├── .env                          # 环境变量（已配置）
├── requirements.txt              # Python 依赖
└── README_*.md                   # 文档
```

---

## ✅ 测试验证

```bash
# 所有测试已通过
$ pytest experiments/tests/ -v

============================== 27 passed in 4.11s ==============================

✅ test_a3_hallucination.py (3 个测试)
✅ test_baselines_smoke.py (2 个测试)
✅ test_experiment_logger.py (9 个测试)
✅ test_figure_reuse_rate.py (3 个测试)
✅ test_pdf_assets_filter.py (3 个测试)
✅ test_ppt_renderer_binding.py (3 个测试)
✅ test_protocol_metrics.py (3 个测试)
✅ test_visual_smoke_check.py (2 个测试)
```

---

## 🔑 关键特性

### 1. SVFP 协议
- 4 种问题类型 × 9 种确定性动作
- 闭合模式视觉批评
- 确定性修复引擎

### 2. CS-Poster-30 数据集
- 30 篇冻结的 PosterTask 快照
- 覆盖计算机科学多个子领域
- 可重现的实验基准

### 3. 完整的评估体系
- **A1-A4**: 内容质量（信息保留、图文对齐、幻觉检测、章节覆盖）
- **B1-B3**: 视觉质量（布局合理性、可读性、学术规范）
- **C1-C3**: 用户体验（PaperQuiz、SUS、时间节省）
- **D1-D3**: 工程指标（延迟、成本、失败率）
- **新增**: visual_smoke_check, figure_reuse_rate, protocol_metrics

### 4. 三臂实验设计
- **E1**: ours_svfp vs ours_no_svfp vs ours_freeform（消融研究）
- **E2**: ours_svfp vs gpt4o_zeroshot_svfp（跨规划器基线）
- **E3**: 用户研究（可选）

---

## ⚠️ 重要提示

1. **完全独立**: 本项目不依赖 `poster_agent_backend`，可以安全删除原项目
2. **数据集为空**: 需要手动添加论文 PDF 到 `experiments/datasets/papers/`
3. **API Key 必需**: 必须配置 `.env` 中的 `DASHSCOPE_API_KEY`
4. **虚拟环境**: 每次使用前需要激活 `source .venv/bin/activate`

---

## 🆘 遇到问题？

### 测试失败
```bash
# 重新安装依赖
pip install -r requirements.txt

# 重新运行测试
pytest experiments/tests/ -v
```

### 模块导入错误
```bash
# 确保在项目根目录
cd /Users/mikaelsnow/Documents/ECNU/Paper_Comment_Poster/PosterCS

# 确保虚拟环境已激活
source .venv/bin/activate
```

### API Key 错误
```bash
# 检查 .env 文件
cat .env | grep DASHSCOPE_API_KEY

# 确保 API key 有效
```

---

## 📞 联系方式

如有问题，请参考：
- [README_SETUP.md](README_SETUP.md) - 详细设置指南
- [INTERNAL_EXPERIMENT_GUIDE.md](INTERNAL_EXPERIMENT_GUIDE.md) - 实验操作指南
- [MIGRATION_REPORT.md](MIGRATION_REPORT.md) - 迁移报告

---

**祝你实验顺利！论文发表成功！** 🚀🎓✨
