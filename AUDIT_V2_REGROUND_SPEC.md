# 新海报重审计 Spec —— audit v2 / new60(S1 诊断接地)

> 状态:草案,2026-06-09。承接 `SVFP_ISSUE_TAXONOMY_v5.md`(分类/路由设计)、`项目现状与最终方向_v6.md`(roadmap P0/P1)。
> 由 Claude 在 brainstorming 流程中与用户多轮确认后落定。**这是一份测量 spec,不是实现 spec**——它只回答「VLM 能否检出新海报上的 issue」并据此决定方向;**不**在本轮建 v2 路由检测器。
>
> ⚠️ 本 spec 的存在理由:旧审计(`experiments/results/audit_v1_old48/`、`ablation_*`)及其人工标签**全部基于旧 pipeline 海报,一律作废**。生成质量已优化,缺陷分布已变,必须在新海报上重新接地。

---

## 0. 目的与决策

**主问题:** 在**新管线**海报上,整图 VLM 能否**可靠**地检出版面 issue(按下文 6 类)?

**产出:** 一个三选一的方向判定 **S1 / S2 / S3**(见 §6),作为后续(P1 路由方法 / 转向)的依据。

**论文 emphasis(已确认,锚定不变):**
> 不是「VLM 对 asset 这一类盲」(旧叙事,已被生成优化架空),而是
> **「整图 VLM 当版面 critic 整体『非判别 + 闭环修不动』→ 可靠修复必须按问题类型路由;几何问题归确定性规则,VLM 只留视觉层级」**。

---

## 1. 样本(已冻结)

- **60 篇不同论文 / 60 个 run**:`outputs/runs/20260609_*`,每篇 1 个(已去重 72→59 + 补 EduIllustrate = 60)。
- **被审图 = 各 run 的 `pptx/iter_1.png`**(真实 soffice 渲染、**初版未经 SVFP 闭环**)。审「生成器产出」的缺陷;闭环效果单独算(§5)。
- 🚫 **严禁用 `preview/*_preview.png`**:它是轻量示意图,会把图画成空占位框、截断标题,**有误导性**(本轮 A 阶段已被它骗过一次)。
- **冻结清单** → `datasets/gold/audit_v2_manifest.json`:每条含 `run_folder` + `poster_title` + `iter1_png_sha256`,保证可复现、防止图被悄悄替换。

---

## 2. Label set(6 类 + guards)+ 预注册分布

每张海报标 **1 个 primary issue**(最该先修的)+ 可选 secondary + guards。6 类相对 v5 的改动:**asset 拆成两类**、**text_overload 降级为负控制**。

| Label | 定义(新系统口径) | 主检测器(路由归属) |
|---|---|---|
| `space_imbalance` | 面板内/面板间留白过多(过空为主),或局部过挤 | 几何(留白连通域 / occupancy) |
| `asset_mismatch` | 图文语义不匹配 / 放错图(取决于 planner 选图准不准) | 脚本+caption+文本 LLM(绕开 VLM 读图) |
| `asset_too_small` | 图本身太小、信息不可读 | 几何(图面积比) |
| `structure_alignment` | 网格级布局出错(如右侧整块长方形空缺、列宽失衡、对齐乱) | 几何(panel bbox / 网格偏移) |
| `hierarchy_emphasis_error`(原 `visual_hierarchy_weak`,**已拓宽**) | 焦点/强调错配:**无主次**(panel 雷同、headline 没突出)**或过度强调错元素**(如 story 模板超大序号抢焦点) | 规则代理(headline/序号尺寸是否合理)+ VLM 窄提示词 |
| `text_overload` ⭐**负控制** | 文字超框/被裁切 | 几何(框 vs 容器边界) |

⭐ **text_overload 作负控制/幻觉探针**:用户已优化掉文本溢出,客观发生率 ≈ 0。因此 **VLM 若仍报 text_overload,即为可证伪的假阳** → 直接量化 VLM 的幻觉率。这是把「几乎不发生的类」变成「最干净的测量」。

**标注边界(必须分清,否则 κ 低):**
- `space_imbalance`(面板**内部**太松/没填满)vs `structure_alignment`(**网格级** panel 缺口/错位):口诀「panel 里面空 → space;整版格子缺一块/排歪 → structure」。
- `text_overload`(内容**超出**框、被裁/重叠)vs `space_imbalance`(内容**不满**框、留白):一超一欠,**互斥**,同一 panel 不可能两者都是。
- ⚠️ **`text_overload` 与 `space_imbalance` 都已被生成设计基本消除**(规则:有图 panel → 1–2 bullet、无图 → 5 bullet,既不溢出也不空)。两者**预期低频**;`text_overload` 维持负控制,`space_imbalance` 保留但预期少。

**guards 取消作为人工标注类别**(6 类已覆盖),改为 **3 条客观几何规则检测器(rule-based,非标注标签)**——双重身份:既当**负控制/幻觉探针**(自家干净海报上应 ≈0,VLM 若报即假阳=幻觉),又当**可迁移检测器**(接到外部 SOTA 的乱版海报上会真触发):
- **contrast 规则**:从 PPTX 已知文字/底色算 WCAG 对比度。自家全达标而 VLM 狂报 `low_contrast` → low_contrast 假阳 = 幻觉。
- **overflow 规则**:几何判文本框超容器/被裁。自家无溢出而 VLM 报 `text_overload` → text_overload 假阳 = 幻觉。
- **overlap 规则**:元素 bbox 相交判重叠。**自家新海报 ≈0(负控制);但 Paper2Poster(qwen3vl)海报已确认大量重叠+出血裁切 → 同一几何规则在外部 SOTA 上真触发**,正面演示「几何检测器可迁移、整图 VLM critic 才是失效环节」(支撑 Direction C 可迁移性)。
- 三者直接量化「整图 VLM 非判别/幻觉」。

**预注册分布假设(用户域知识,observed vs predicted 将作为论文一张表):**
- `text_overload` ≈ 0、`space_imbalance` 低频(均已被设计压掉);`structure_alignment` / `asset_too_small` 会有;`hierarchy_emphasis_error` 偶发(含 story 序号过大这类**过度强调**);`asset_mismatch` 取决于 planner 选图准确率;**外加 open-coding 捕捉的模板特有缺陷(预期非空)**。

---

## 3. 人工标注协议

- **标注单元:** 每张 `iter_1.png`,标 primary(6 选 1)+ secondary(可多选)+ guards + 一句话理由。
- **双标注者独立标:** 用户本人 + 第二标注者(已到位),互不可见。
- **校准 + 开放编码(关键):** 先共标 **10 张**——但**先自由写下每张的实际毛病(open coding),再映射到 6 类**,凡不属任何类的记 `other(描述)`。讨论对齐口径、固化守则,再独立标全 60。**`other` 若反复出现(如某模板特有缺陷)→ 提升为新类。** 这才是「在新系统上接地 taxonomy」,防止「6 类是给旧坏生成器设计的、现在的真缺陷反而没类可标」。
- **一致性:** 报 **Cohen's κ**(primary label)。κ 是 gold 可信度的前提;若 κ 偏低(<0.4),说明 taxonomy 本身边界模糊,这本身是一条发现(需回头收紧定义)。
- **gold:** 分歧条目由第三方(或两人讨论)裁决,产出单一 `human_gold` primary。
- **产物:** `datasets/gold/audit_v2_labels_{annotatorA,annotatorB,gold}.json`。

---

## 4. VLM 条件(只有 Qwen,如实设计)

- **必测:** `Qwen3-VL-32B`,两种 prompt——
  - (a) **6 类直接**:给定义,直接判 primary issue;
  - (b) **窄/cue 版**:逐 cue(overflow / loose_spacing / figure_text_mismatch / figure_too_small / large_blank / no_focus)取证再聚合(对齐旧 `ablation_narrowed_prompt` 口径,可纵向比较)。
- **可选:** `8B` / `30B-A3B` 规模复测(便宜,验证「非小模型问题」是否在新数据上仍成立)。
- **前沿模型:** 本轮无(GPT-4o/Gemini 后续可能有)。代码留接口;若拿不到,在 limitation 如实写明「仅 Qwen 家族」。

---

## 5. 指标

**A. VLM vs human-gold(主):**
- 每类 **recall / precision / F1**;整体 **accuracy + Cohen's κ**;**混淆矩阵**。
- **先验基线:** 永远预测 gold 最频标签的 accuracy。VLM 必须**显著超过**它才算「有信号」。
- **VLM 标签熵 / top-1 占比:** 量化「非判别」(熵越低、单标签占比越高 → 越像先验)。
- **text_overload 假阳率:** #(VLM 报 text_overload)/60(gold≈0)→ 幻觉率。

**B. 人工分布 + 分模板:** 60 张 gold 的 primary 分布(对照 §2 预注册预测);并**按模板**(dashboard / story / minimal / …)拆分——把「story 序号过大」这类**模板特有缺陷**显式暴露成模板级发现(每张记录其 `template`)。

**B2. open-coding 产物:** `other` 缺陷清单 + 频次,据此决定是否新增类(taxonomy 在新系统上的接地证据)。

**C. 闭环侧(已观测,旧 4 类生产环,作 baseline 反例,不需重跑):**
- (旧 4 类闭环,**72 个原始 run** 上观测)改善 **1/72**、持平 49、变差 22;`per_iter_visual_gain` 70/72=0;71/72 停滞收敛;`empty_space`/`low_contrast` 刷 ~90%;`enlarge_font` 481 次。**正式版在冻结的 60 张上重算。**
- (说明:`per_iter_visual_gain` 可能是未实装 stub;`c3 issue-resolution` 需 `svfp_trace` 遥测,本轮**不算**,列为后续。)

---

## 6. 判定阈值(预注册,避免事后找补)

设 5 个「真」类(排除负控制 text_overload)的宏平均 recall = `R_macro`,VLM-vs-gold primary 的 κ = `κ_vg`,先验基线 accuracy = `acc_prior`,VLM accuracy = `acc_vlm`。

- **S2 — VLM 可靠(诊断崩,需转向):** `R_macro ≥ 0.70` **且** `κ_vg ≥ 0.60` **且** `acc_vlm − acc_prior ≥ 0.15`(或 McNemar p<0.05)。
  → 转向:贡献落到生成管线或 measurement 角度(与 VLM 可靠性解耦)。
- **S1 — VLM 不可靠(诊断成立):** `acc_vlm ≤ acc_prior + 0.05` **或** `κ_vg < 0.20`,**且**标签熵低/被 ≤2 个标签主导。
  → 「整图 VLM 非判别」主张在新数据上接地。
- **S3 — 分项可靠(路由有据,最可能):** 存在 ≥1 类 `recall ≥ 0.70`(如 vhw / overflow)**且** ≥1 类 `recall ≤ 0.30`(如 asset_mismatch / structure)。
  → 「按问题路由」有逐类证据,Direction B 成主线。

---

## 7. 产物与目录

```
datasets/gold/audit_v2_manifest.json          # 冻结的 60 张样本清单 + sha
datasets/gold/audit_v2_labels_*.json          # A/B/gold 人工标签
experiments/results/audit_v2_new60/
    vlm_qwen32b_direct.json                    # VLM (a) 输出
    vlm_qwen32b_narrowed.json                  # VLM (b) 输出
    confusion_matrix.json / per_issue_table.csv
    kappa.json                                 # 人-人 κ + VLM-gold κ
AUDIT_V2_FINDINGS.md                           # 落到 S1/S2/S3 + 下一步方向
```

---

## 8. 不在本 spec 范围(YAGNI,由审计结果决定)

- ❌ 建 v2 路由检测器(几何/脚本+LLM/VLM 分工)、severity-gating —— P1,**审计判定 S1/S3 后**才做。
- ❌ `svfp_trace` 遥测实装、c3 真实计算 —— 后续 wave。
- ❌ 前沿模型对照 —— 待资源。
- ❌ 与 Paper2Poster 的 head-to-head —— 受「无 4o」约束,另议(但 overlap 规则可在其 qwen3vl 海报上跑,作可迁移性演示)。
- ❌ **模板去留决策**(minimal 仅 n=1、story 序号过大)—— **生成侧决策,由 per-template 分析结果决定;本轮保留全 4 模板**。理由:缺陷多样性是测 critic/路由的**资产**,不为美观而砍样本;cut 会让 critic 没毛病可测、且像挑好案例。story 序号=**修**(调小底纹数字)非砍;minimal=**待定**(要么修选择器让它被选到,要么砍,审计后定)。

---

## 9. 与论文假设的衔接

- **H1(本审计直接检验):** 整图 VLM 对 6 类 issue 的检测 ≈ 先验、随规模不改善 → 落 S1/S3 即支撑。
- **H2(后续 P1 检验):** 路由检测的 issue-resolution 显著 > 整图 VLM 闭环、质量不回退。
- 与 Paper2Poster 的对照点:P2P 的 Painter-Commentor 正是「整图 VLM 修 overflow/对齐」,本审计若落 S1/S3,即从经验上质疑该范式 + VLM-as-Judge 的版面效度。

*本文为 brainstorming 终态产物(测量 spec);经用户 review 后转 `writing-plans` 出实现计划。*
