# 指标重构执行计划(Wave 1)—— 早上和用户一起做

> 2026-06-08 夜间生成。**为什么没在夜里直接执行整套 rewire:** 重命名/删除会牵动
> `aggregate_stats.py / plot_figures.py / print_paper_table.py / test_baselines_smoke.py`
> 等下游脚本,它们**在 import 时不报错、只在运行时报错**——结构 smoke 抓不到,夜里
> 又无法用真实数据全量验证。为守住"保证不报错",把整套 rewire 留给你在场时机械执行。
> **a3_semantic_fidelity 已实现且 bert_score 后端已验证(F1=0.3173,roberta-large 已缓存)。**

---

## 1. 完整映射表

| 旧 文件 / metric_id | 动作 | 新 文件 / metric_id / class |
|---|---|---|
| `a1_information_retention` / A1InformationRetention | 改名 | `a1_key_info_recall` / `A1KeyInfoRecall` |
| `a3_hallucination` / A3Hallucination | 改名 | `a2_hallucination_rate` / `A2HallucinationRate` |
| —(新) | **已建** | `a3_semantic_fidelity` / `A3SemanticFidelity` ✅ |
| `b1_layout_rationality` / B1LayoutRationality | 改名(几何为主+独立 VLM) | `b1_layout_quality` / `B1LayoutQuality` |
| `b2_readability` | 保留 | `b2_readability`(id 不变) |
| `figure_reuse_rate` / FigureReuseRate | 改名 | `b3_figure_reuse_rate` / `B3FigureReuseRate` |
| `a2_figure_text_alignment` / A2FigureTextAlignment | 改名(A→B) | `b4_figure_text_align` / `B4FigureTextAlign` |
| `d1_latency` / `d2_cost` | 保留 | 不变 |
| `c1_paperquiz` / C1PaperQuiz | 改名(C→E) | `e1_paperquiz` / `E1PaperQuiz` |
| —(新) | 待建(架子) | `e2_human_preference` / `E2HumanPreference`(读人评 CSV,无则 skip) |
| —(新) | 待建(架子) | `e3_llm_judge` / `E3LLMJudge`(LLM rubric 打分,须报与 e2 相关性) |
| `a4_section_coverage` | **删** | 天花板指标(≈1) |
| `b3_academic_compliance` | **删** | 偏题 |
| `c2_sus_likert` | **删** | 缓做 |
| `c3_time_saving` | **删** | 缓做 |
| `d3_failure_rate` | **删** | 地板指标(≈0) |
| `visual_smoke_check` | 移出主表 | 保留文件,作内部预检,不进 16 指标 |
| `protocol_metrics`(action_executability/convergence_rate/mean_iters/per_iter_visual_gain) | **不动** | 归 Wave2 / 任务 #10(c1 诚实重测 + c3 新建) |

最省事的"改名"做法:`git mv 旧.py 新.py` → 改文件里的 `metric_id` 与 class 名(逻辑不动)。

## 2. 改 `experiments/scripts/compute_metrics.py:_import_all_metrics()`

把模块列表替换为(Wave1 后):
```python
"experiments.metrics.a1_key_info_recall",
"experiments.metrics.a2_hallucination_rate",
"experiments.metrics.a3_semantic_fidelity",
"experiments.metrics.b1_layout_quality",
"experiments.metrics.b2_readability",
"experiments.metrics.b3_figure_reuse_rate",
"experiments.metrics.b4_figure_text_align",
"experiments.metrics.d1_latency",
"experiments.metrics.d2_cost",
"experiments.metrics.e1_paperquiz",
"experiments.metrics.e2_human_preference",
"experiments.metrics.e3_llm_judge",
"experiments.metrics.protocol_metrics",   # Wave2 的 C 类,暂留
# 删除: a1_information_retention, a2_figure_text_alignment, a3_hallucination,
#       a4_section_coverage, b1_layout_rationality, b3_academic_compliance,
#       figure_reuse_rate, c1_paperquiz, c2_sus_likert, c3_time_saving, d3_failure_rate
# visual_smoke_check 视情况保留(内部预检)
```

## 3. 改 `experiments/configs/metrics.yaml`
把顶层键按映射表改名;删除 5 个废弃键;新增 `a3_semantic_fidelity` / `e2_human_preference` / `e3_llm_judge` 配置块(至少 `enabled: true`)。

## 4. 修下游引用(必须全改,否则运行时报错)
`grep -rn "information_retention\|figure_text_alignment\|a3_hallucination\|section_coverage\|layout_rationality\|academic_compliance\|figure_reuse_rate\|c1_paperquiz\|sus_likert\|time_saving\|failure_rate" experiments/scripts/ experiments/configs/ experiments/tests/`
逐处改成新 id。重点文件:`aggregate_stats.py`、`plot_figures.py`、`print_paper_table.py`、`test_baselines_smoke.py`。

## 5. smoke(两层)
```bash
# 结构层(import + 注册无错)
unset VIRTUAL_ENV && .venv/bin/python -c "from experiments.scripts.compute_metrics import _import_all_metrics; from experiments.metrics.base import MetricRegistry; _import_all_metrics(); print(sorted(MetricRegistry.all()))"
# 数值层(在一个已有 cell 上跑新指标,确认不抛错)
.venv/bin/python -m experiments.scripts.compute_metrics --metrics a3_semantic_fidelity,b2_readability --artifact experiments/results/hydrate_test/<cell>
```
两层都绿 → 再 `git mv` 删旧文件并提交。任何一层红 → 因为旧文件仍在,回退 `_import_all_metrics` 即恢复。
