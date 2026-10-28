# C48 stability results v1

Three independent calls were compared on 12 preselected C48 images. The first call is the frozen confirmation run; calls two and three are post-freeze repeat calls with unchanged image, model, prompt, schema, and temperature.

| Configuration | Images | Three-way exact label-set agreement | Mean pairwise Jaccard | Three-way primary agreement | Mean latency (s) |
|---|---:|---:|---:|---:|---:|
| gemini_flash_p2 | 12 | 0.083 | 0.569 | 0.500 | 6.18 |
| qwen32b_p3 | 12 | 0.917 | 0.944 | 0.833 | 38.14 |

This diagnostic reports repeatability only. It does not replace the frozen C48 performance evaluation or alter any selected operating point.
