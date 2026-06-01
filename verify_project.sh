#!/bin/bash
# PosterCS 项目验证脚本
# 验证项目是否完整且可以独立运行

set -e

echo "🔍 PosterCS 项目验证"
echo "===================="
echo ""

# 1. 检查目录结构
echo "📁 检查目录结构..."
REQUIRED_DIRS=(
    "app"
    "experiments/baselines"
    "experiments/metrics"
    "experiments/scripts"
    "experiments/tools"
    "experiments/tests"
    "experiments/judges"
    "experiments/datasets"
    "experiments/configs"
    "experiments/results"
    "dify"
    "datasets"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "  ✅ $dir"
    else
        echo "  ❌ $dir (缺失)"
        exit 1
    fi
done

echo ""

# 2. 检查核心文件
echo "📄 检查核心文件..."
REQUIRED_FILES=(
    ".env"
    ".env.example"
    ".gitignore"
    "requirements.txt"
    "README.md"
    "README.zh-CN.md"
    "README_FIRST.md"
    "README_SETUP.md"
    "MIGRATION_REPORT.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (缺失)"
        exit 1
    fi
done

echo ""

# 3. 检查虚拟环境
echo "🐍 检查虚拟环境..."
if [ -d ".venv" ]; then
    echo "  ✅ .venv 存在"
    if [ -f ".venv/bin/activate" ]; then
        echo "  ✅ activate 脚本存在"
    else
        echo "  ❌ activate 脚本缺失"
        exit 1
    fi
else
    echo "  ❌ .venv 不存在"
    exit 1
fi

echo ""

# 4. 检查 Python 模块
echo "🔧 检查 Python 模块..."
source .venv/bin/activate

python -c "import app" 2>/dev/null && echo "  ✅ app 模块可导入" || (echo "  ❌ app 模块导入失败" && exit 1)
python -c "import experiments" 2>/dev/null && echo "  ✅ experiments 模块可导入" || (echo "  ❌ experiments 模块导入失败" && exit 1)
python -c "import experiments.baselines" 2>/dev/null && echo "  ✅ experiments.baselines 可导入" || (echo "  ❌ experiments.baselines 导入失败" && exit 1)
python -c "import experiments.metrics" 2>/dev/null && echo "  ✅ experiments.metrics 可导入" || (echo "  ❌ experiments.metrics 导入失败" && exit 1)
python -c "import experiments.judges" 2>/dev/null && echo "  ✅ experiments.judges 可导入" || (echo "  ❌ experiments.judges 导入失败" && exit 1)

echo ""

# 5. 统计文件
echo "📊 统计文件..."
PY_COUNT=$(find . -name "*.py" -not -path "./.venv/*" | wc -l | xargs)
YAML_COUNT=$(find experiments/configs -name "*.yaml" | wc -l | xargs)
JSON_COUNT=$(find experiments/configs -name "*.json" | wc -l | xargs)
TEST_COUNT=$(find experiments/tests -name "test_*.py" | wc -l | xargs)

echo "  📝 Python 文件: $PY_COUNT"
echo "  ⚙️  YAML 配置: $YAML_COUNT"
echo "  📋 JSON 配置: $JSON_COUNT"
echo "  🧪 测试文件: $TEST_COUNT"

echo ""

# 6. 运行测试
echo "🧪 运行测试套件..."
pytest experiments/tests/ -v --tb=short -q 2>&1 | tail -5

echo ""

# 7. 检查环境变量
echo "🔑 检查环境变量..."
if grep -q "DASHSCOPE_API_KEY=" .env; then
    if grep -q "DASHSCOPE_API_KEY=sk-" .env; then
        echo "  ✅ DASHSCOPE_API_KEY 已配置"
    else
        echo "  ⚠️  DASHSCOPE_API_KEY 未配置（需要手动填入）"
    fi
else
    echo "  ❌ DASHSCOPE_API_KEY 缺失"
fi

echo ""

# 8. 最终报告
echo "✅ 验证完成！"
echo ""
echo "📊 项目统计:"
echo "  - Python 文件: $PY_COUNT"
echo "  - 配置文件: $((YAML_COUNT + JSON_COUNT))"
echo "  - 测试文件: $TEST_COUNT"
echo "  - 项目大小: $(du -sh . | cut -f1)"
echo ""
echo "🎯 项目状态: 就绪"
echo ""
echo "📝 下一步:"
echo "  1. 配置 .env 文件中的 DASHSCOPE_API_KEY"
echo "  2. 添加论文 PDF 到 experiments/datasets/papers/"
echo "  3. 运行第一个实验"
echo ""
echo "🚀 开始实验:"
echo "  python -m experiments.scripts.run_one_paper \\"
echo "    --paper experiments/datasets/papers/your_paper.pdf \\"
echo "    --baseline ours_svfp \\"
echo "    --out experiments/results/test_run"
echo ""
