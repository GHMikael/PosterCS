#!/bin/bash
# 快速启动 PosterCS 项目的便捷脚本

PROJECT_DIR="/Users/mikaelsnow/Documents/ECNU/Paper_Comment_Poster/PosterCS"

echo "🚀 PosterCS 快速启动"
echo "===================="
echo ""

# 进入项目目录
cd "$PROJECT_DIR" || exit 1

# 激活虚拟环境
echo "🐍 激活虚拟环境..."
source .venv/bin/activate

echo "✅ 环境已激活"
echo ""
echo "📍 当前目录: $(pwd)"
echo "🐍 Python 版本: $(python --version)"
echo ""
echo "💡 快速命令:"
echo ""
echo "  # 运行测试"
echo "  pytest experiments/tests/ -v"
echo ""
echo "  # 验证项目"
echo "  bash verify_project.sh"
echo ""
echo "  # 运行单篇实验"
echo "  python -m experiments.scripts.run_one_paper \\"
echo "    --paper experiments/datasets/papers/your_paper.pdf \\"
echo "    --baseline ours_svfp \\"
echo "    --out experiments/results/test_run"
echo ""
echo "  # 运行 E1 smoke（5 篇论文）"
echo "  python -m experiments.scripts.run_matrix \\"
echo "    --config experiments/configs/e1_smoke_baselines.yaml \\"
echo "    --out experiments/results/artifacts_e1_smoke"
echo ""
echo "  # 运行 n=30 实验"
echo "  python -m experiments.scripts.run_matrix \\"
echo "    --config experiments/configs/baselines.yaml \\"
echo "    --papers experiments/configs/papers_30.json \\"
echo "    --out experiments/results/artifacts_n30"
echo ""
echo "📚 文档:"
echo "  - README_FIRST.md - 快速开始"
echo "  - README_SETUP.md - 完整设置指南"
echo "  - MIGRATION_REPORT.md - 迁移报告"
echo ""
echo "🎯 准备就绪！开始你的实验吧！"
echo ""

# 保持在激活的环境中
exec $SHELL
