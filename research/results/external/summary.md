# External-Natural-20 结果 v1

- 定位：Gold 冻结后的外部自然样本检查；n=20；仅比较两个预先固定的 image-only VLM operating point。
- 输入：同一套保持原始纵横比、无裁切/拉伸、最长边 2400px 的 PNG 派生图。
- Macro-F1：只对 Gold support > 0 的标签取平均；本集有正例的标签为 body_text_too_small、figure_detail_unreadable、text_overload、space_imbalance。
- Qwen 由首批 10 条与中断后的 missing-only 续跑 10 条组成；两批使用相同配置、提示词和派生输入清单。

| 模型 | micro-P | micro-R | micro-F1 | macro-F1 | exact match | mean Jaccard | primary acc. | Gold-none any-defect FPR | 平均指控数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini_flash_p2 | 0.444 | 0.545 | 0.490 | 0.361 | 0.050 | 0.250 | 0.200 | 1.000 | 1.35 |
| qwen32b_p3 | 0.375 | 0.545 | 0.444 | 0.274 | 0.100 | 0.246 | 0.200 | 1.000 | 1.60 |

## 每标签结果

### gemini_flash_p2

| 标签 | support | TP | FP | FN | P | R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| body_text_too_small | 8 | 3 | 2 | 5 | 0.600 | 0.375 | 0.462 |
| figure_detail_unreadable | 7 | 7 | 12 | 0 | 0.368 | 1.000 | 0.538 |
| text_overload | 6 | 2 | 1 | 4 | 0.667 | 0.333 | 0.444 |
| space_imbalance | 1 | 0 | 0 | 1 | 0.000 | 0.000 | 0.000 |

预测标签频率：`{"body_text_too_small": 5, "figure_detail_unreadable": 19, "text_overload": 3}`

### qwen32b_p3

| 标签 | support | TP | FP | FN | P | R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| body_text_too_small | 8 | 0 | 0 | 8 | 0.000 | 0.000 | 0.000 |
| figure_detail_unreadable | 7 | 7 | 12 | 0 | 0.368 | 1.000 | 0.538 |
| text_overload | 6 | 5 | 7 | 1 | 0.417 | 0.833 | 0.556 |
| space_imbalance | 1 | 0 | 1 | 1 | 0.000 | 0.000 | 0.000 |

预测标签频率：`{"figure_detail_unreadable": 19, "space_imbalance": 1, "text_overload": 12}`

