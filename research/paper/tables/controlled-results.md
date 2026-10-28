# Table 1. C48-Confirm audit performance

| System | Paired correctness | Mutation recall | Target-control FPR | Any-defect control FPR | Micro-F1 |
|---|---:|---:|---:|---:|---:|
| Gemini-P2 | 37.5% [21.2%, 57.3%] | 45.8% | 12.5% | 100.0% | 0.224 |
| Qwen32B-P3 | 45.8% [27.9%, 64.9%] | 62.5% | 16.7% | 100.0% | 0.385 |
| Raster Rule | 16.7% [6.7%, 35.9%] | 16.7% | 0.0% | 0.0% | 0.286 |
| Source-aware Rule | 75.0% [55.1%, 88.0%] | 75.0% | 0.0% | 0.0% | 0.857 |
| Hybrid-v1 | 79.2% [59.5%, 90.8%] | 79.2% | 0.0% | 16.7% | 0.760 |

*Note.* Brackets show 95% Wilson confidence intervals for paired target correctness. Source-aware systems receive PPTX-derived structure unavailable to image-only VLM baselines.
