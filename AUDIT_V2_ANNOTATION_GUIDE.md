# Audit v2 标注守则(给两位标注者)

> 目标:对 **60 张新海报**(SVFP 修复*之前*的初始渲染)各标一个「最主要的版面设计失败」,用于验证「整图 VLM 能否检出这些问题」。
> 你看的是真实渲染图(`iter1_png` 列指向的 `outputs/runs/.../pptx/iter_1.png`)。**两人独立标**,先共标前 10 行校准。

## 怎么填表

打开你的 `datasets/gold/audit_v2_labels_annotator{A,B}.csv`,逐行填这几列:

| 列 | 怎么填 |
|---|---|
| `primary_issue` | **最主要**的一个失败,从下面 6 类里选一个;6 类都不像就填 `other`;确实没毛病填 `none` |
| `secondary_issues` | 其余存在但非最主要的,0 个或多个,逗号分隔(取值同 6 类,可含 `other`,**不要** `none`) |
| `other_description` | **关键**:`primary` 或 `secondary` 里只要填了 `other`,在这写清到底是什么毛病(open-coding) |
| `guard_notes` | 看到明显的「文字压图/重叠/对比太低/被裁切」可随手记一句(非必填,这些主要交给规则自动算) |
| `confidence` | 你对 `primary` 判断的把握,0–1 小数 |
| `free_notes` | 任何想说的 |

## ⚠️ 先做 open-coding(重要)

每张**先用一句话自由写下你看到的实际毛病**(写在 `free_notes`),**再**去映射到下面 6 类。**凡是 6 类都套不进去的,填 `other` 并在 `other_description` 写清楚**(比如「story 模板左上角序号过大、抢焦点」)。我们要的就是这些「6 类没覆盖到的真实毛病」——别硬塞进 6 类。

## 6 类定义 + 边界口诀

1. **`space_imbalance`** — **某个 panel 内部**太松/没填满(bullet 间距大、这块内容稀),或局部过挤、左右上下视觉重量失衡。
2. **`text_overload`** — 文字**超出**框、被裁切、或密度过高读着累。*(注:生成已基本消除它;若你真看到再标。)*
3. **`hierarchy_emphasis_error`** — 焦点/强调**错配**:要么**没主次**(所有 panel 一样大、看不出先读哪)、要么**过度强调了错的元素**(如超大装饰序号抢焦点)。
4. **`asset_mismatch`** — 图**放错/与文不符**(配了不相关的图、图文主题对不上)。
5. **`asset_too_small`** — 图本身**太小**、看不清内容。
6. **`structure_alignment_error`** — **网格层面**出错:右侧整块长方形空白、列宽失衡、panel 没铺满画布、对齐乱、模块边界不清。

**最易混的边界,按口诀判:**
- **`space` vs `structure`**:「**某个 panel 里面**空」→ `space`;「**整版的格子**缺了一块 / 排歪了」→ `structure`。
- **`text_overload` vs `space_imbalance`**:字**超**框→overload;字**不满**框、留白→space(一超一欠,互斥)。
- **`asset_mismatch` vs `asset_too_small`**:放错图/图文无关→mismatch;图对但太小→too_small。
- **`hierarchy_emphasis_error`**:不是某一块错,而是**整体焦点**问题(没焦点 / 焦点给错了元素)。

## 不用你标的(规则自动算)

`overlap`(元素重叠)、`contrast`(对比度)、`overflow`(溢出)由代码用几何规则客观判定(同时当「VLM 幻觉探针」)。你**不必**专门标这些;只在特别明显时在 `guard_notes` 记一句即可。

## 填表示例(1 行)

```
primary_issue=structure_alignment_error
secondary_issues=space_imbalance
other_description=
guard_notes=
confidence=0.8
free_notes=右半边几乎空着,内容全挤在左侧三栏;整体像没排满
```

## 流程

1. 两人**共标前 10 行**,对完口径、讨论分歧、必要时回来补充本守则;
2. 各自**独立标完 60 行**;
3. 交回两份 CSV → 算 Cohen's κ、分歧第三方裁决出 `gold`。
