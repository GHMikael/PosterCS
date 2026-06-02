# PosterCS 工作流程详解

## 你的问题解答

### 问题 1: 是否使用了 Dify？

**答案：没有使用 Dify，但这是设计好的！**

---

## 📋 完整工作流程说明

### 方案 A: 使用 Dify（生产环境）

```
PDF → Dify Workflow → PosterTask JSON → 保存到 planner_cache/ → 实验使用缓存
```

**步骤：**
1. 在 Dify 中运行 workflow，输入 PDF
2. Dify 生成 PosterTask JSON（包含标题、面板、内容等）
3. 将 JSON 保存到 `experiments/datasets/planner_cache/<arxiv_id>.json`
4. 实验时，系统会**优先读取缓存**，重放 Dify 的输出
5. 然后运行 SVFP 反馈循环生成海报

**优点：**
- 实验可重现（使用相同的 Dify 输出）
- 不需要每次都调用 Dify
- 节省成本和时间

---

### 方案 B: 不使用 Dify（实验环境，当前使用）

```
PDF → heuristic_plan() → PosterTask → SVFP 反馈循环 → 海报
```

**步骤：**
1. 系统检查 `planner_cache/` 是否有缓存 → **没有**
2. 回退到 `heuristic_plan()`（启发式规划器）
3. 直接从 PDF 提取内容，生成 PosterTask
4. 运行 SVFP 反馈循环（2 次迭代）
5. 生成最终海报

**优点：**
- 完全独立，不依赖 Dify
- 可以快速测试和验证
- 适合实验和开发

---

## 🔍 代码逻辑（ours_svfp.py）

```python
# 第 41-47 行：规划器优先级
task = cached_plan(paper_path)  # 1. 尝试从 planner_cache/ 读取
planner_source = "dify_cache"

if task is None:  # 2. 如果没有缓存
    assets = extract_assets(paper_path)  # 提取 PDF 资源
    task = heuristic_plan(assets)  # 使用启发式规划器
    planner_source = "heuristic"  # 标记为 heuristic
```

**你的实验使用了 `heuristic` 规划器**，因为 `planner_cache/` 是空的。

---

## 📁 迭代图片在哪里？

### 位置：`outputs/runs/<run_id>/`

```
outputs/runs/20260601_182144_LLM记忆评估_C9177E_0340dec84261/
├── pptx/
│   ├── iter_1.png          # 第 1 次迭代的海报图片（得分 4.9）
│   ├── iter_2.png          # 第 2 次迭代的海报图片（得分 8.5）
│   ├── iter_1.pptx         # 第 1 次迭代的 PPT
│   └── iter_2.pptx         # 第 2 次迭代的 PPT
├── preview/
│   ├── iter_1_preview.png  # 第 1 次迭代的预览图（快速渲染）
│   └── iter_2_preview.png  # 第 2 次迭代的预览图
├── final.pptx              # 最终 PPT（= iter_2.pptx）
├── input.json              # 输入的 PosterTask JSON
└── run_report.json         # 运行报告（包含所有迭代信息）
```

### 查看迭代图片

```bash
# 打开第 1 次迭代（得分 4.9）
open outputs/runs/20260601_182144_LLM记忆评估_C9177E_0340dec84261/pptx/iter_1.png

# 打开第 2 次迭代（得分 8.5）
open outputs/runs/20260601_182144_LLM记忆评估_C9177E_0340dec84261/pptx/iter_2.png

# 查看完整运行报告
cat outputs/runs/20260601_182144_LLM记忆评估_C9177E_0340dec84261/run_report.json
```

---

## 🎯 SVFP 反馈循环工作流程

```
迭代 1:
  1. 生成 PPT (iter_1.pptx)
  2. 转换为 PNG (iter_1.png)
  3. VLM 评分 → 4.9/10
  4. 发现问题：overlapping_elements, empty_space 等
  5. 生成修复动作：reduce_bullet_count, shrink_text 等

迭代 2:
  1. 应用修复动作
  2. 生成新 PPT (iter_2.pptx)
  3. 转换为 PNG (iter_2.png)
  4. VLM 评分 → 8.5/10
  5. 没有问题 → 收敛成功！

最终:
  - 复制 iter_2.pptx 到 final.pptx
  - 复制 iter_2.png 到 experiments/results/test_run/.../poster.png
```

---

## 🔄 如何使用 Dify？

### 步骤 1: 在 Dify 中运行 workflow

1. 打开你的 Dify workflow
2. 上传 PDF（例如：LLM记忆评估_C9177E.pdf）
3. Dify 生成 PosterTask JSON

### 步骤 2: 保存 JSON 到 planner_cache

```bash
# 假设 Dify 输出的 JSON 保存为 dify_output.json
cp dify_output.json experiments/datasets/planner_cache/LLM记忆评估_C9177E.json
```

### 步骤 3: 重新运行实验

```bash
python -m experiments.scripts.run_one_paper \
  --paper experiments/datasets/papers/LLM记忆评估_C9177E.pdf \
  --baseline ours_svfp \
  --out experiments/results/test_run_with_dify
```

**这次会使用 Dify 的输出！**

---

## 📊 三种规划器对比

| 规划器 | 优先级 | 使用场景 | 优点 | 缺点 |
|--------|--------|----------|------|------|
| **cached_plan** (Dify) | 1 | 正式实验 | 可重现、真实生产输出 | 需要预先运行 Dify |
| **heuristic_plan** | 2 | 快速测试 | 完全独立、确定性 | 质量可能不如 LLM |
| **gpt4o_plan** | 3 | 无 Dify 环境 | 质量好、无需 Dify | 需要 OpenAI API |

---

## 💡 总结

1. **你的实验没有用 Dify，但这是正常的！**
   - 系统设计了 3 层回退机制
   - 当前使用 heuristic_plan，完全正常

2. **迭代图片在 `outputs/runs/<run_id>/pptx/` 目录**
   - iter_1.png（得分 4.9）
   - iter_2.png（得分 8.5）

3. **如果想用 Dify：**
   - 在 Dify 中运行 workflow
   - 保存 JSON 到 planner_cache/
   - 重新运行实验

4. **当前状态完全正常，可以继续实验！**
