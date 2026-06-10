# Audit v2 (new60) 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 `superpowers:subagent-driven-development`(推荐)或 `superpowers:executing-plans` 按任务逐条实现。步骤用 `- [ ]` 复选框跟踪。
> 配套 spec:`AUDIT_V2_REGROUND_SPEC.md`。**人工标注(Phase 0 产物给两位标注者)与代码(Phase 1-4)并行;代码侧不依赖标注完成。**

**Goal:** 在 60 张新海报上,用代码量化「整图 VLM 能否检出 6 类 issue」+ 2 条客观几何规则(contrast/overlap;负控制/幻觉探针),产出 S1/S2/S3 判定所需的全部指标。

**Architecture:** 复用现有 `experiments/audit/`(taxonomy + vlm_labeler + corpus)。把 taxonomy 从 5 类升 6 类;新增 `geom_rules.py`(contrast/overlap 两规则)、`manifest_v2.py`(冻结样本+标注 kit)、`metrics_v2.py`(手写 κ/混淆/熵/P-R-F1/先验基线/分模板/假阳率);两个 driver 脚本跑 VLM 批量与分析。无新依赖(κ 手写,不引 sklearn)。

**Tech Stack:** Python 3.12 · pytest · python-pptx 0.6.23(读 `pptx/iter_1.pptx` 几何+颜色)· Pillow · openai→SiliconFlow(复用 `vlm_labeler.label_poster`)。

---

## File Structure(先锁定边界)

| 文件 | 责任 | 新建/改 |
|---|---|---|
| `experiments/audit/taxonomy.py` | 6 类 issue 枚举 + gloss + schema + OLD→NEW | **改** |
| `experiments/audit/vlm_labeler.py` | VLM 打标(direct/narrowed 两 prompt) | **改**(加 variant) |
| `experiments/audit/corpus.py` | 找 run / iter_1.png(复用 `find_run_dirs`/`_first_png`) | 复用 |
| `experiments/audit/manifest_v2.py` | 冻结 60 张 manifest + 标注 CSV/guide | **新建** |
| `experiments/audit/geom_rules.py` | contrast / overlap 两客观规则(overflow 已取消) | **新建** |
| `experiments/audit/metrics_v2.py` | κ、混淆矩阵、P/R/F1、熵、先验基线、假阳率 | **新建** |
| `experiments/scripts/run_audit_v2.py` | 遍历 manifest 跑 VLM(direct+narrowed)+ 几何规则 | **新建** |
| `experiments/scripts/analyze_audit_v2.py` | 合 gold+VLM+rules → 表 + `AUDIT_V2_FINDINGS.md` | **新建** |
| `experiments/tests/test_audit_v2_*.py` | 各模块单测 | **新建** |
| 产物 | `datasets/gold/audit_v2_manifest.json`、`..._annotation_sheet.csv`、`AUDIT_V2_ANNOTATION_GUIDE.md`、`experiments/results/audit_v2_new60/*` | 生成 |

---

## Phase 0 — 冻结样本 + 标注 kit(备标注清单)

### Task 0.1：构建冻结 manifest

**Files:** Create `experiments/audit/manifest_v2.py`；Test `experiments/tests/test_audit_v2_manifest.py`

- [ ] **Step 1 写失败测试**
```python
# test_audit_v2_manifest.py
from experiments.audit.manifest_v2 import build_manifest
def test_manifest_has_60_unique_with_required_fields(tmp_path):
    rows = build_manifest()  # reads outputs/runs by default
    assert len(rows) == 60
    titles = {r["title_norm"] for r in rows}
    assert len(titles) == 60                      # 去重后每篇唯一
    r = rows[0]
    for k in ("run_folder","title","title_norm","template","iter1_png","iter1_sha256"):
        assert k in r and r[k]
```
- [ ] **Step 2 跑测试确认失败** — `pytest experiments/tests/test_audit_v2_manifest.py -v`(ImportError)
- [ ] **Step 3 实现**(复用 `corpus.find_run_dirs`/`_first_png`)
```python
# manifest_v2.py
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from experiments.audit.corpus import find_run_dirs, _first_png, default_runs_dir, _read_report

def _norm(t: str) -> str: return re.sub(r"\s+"," ",(t or "").strip().upper())
def _sha(p: Path) -> str: return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

def build_manifest(runs_dir: Path | None = None) -> list[dict]:
    runs_dir = runs_dir or default_runs_dir()
    seen, rows = {}, []
    for d in sorted(find_run_dirs(runs_dir)):
        rep = _read_report(d) or {}
        inp = rep.get("input", {})
        png = d / "pptx" / "iter_1.png"
        if not png.exists():
            png = _first_png(d)            # fallback
        if not png: continue
        title = inp.get("poster_title","")
        key = _norm(title)
        if key in seen: continue           # 去重:每篇留第一个(manifest 已在去重后的 60 上跑)
        seen[key] = True
        rows.append({
            "run_folder": d.name, "title": title, "title_norm": key,
            "template": inp.get("template","?"),
            "iter1_png": str(png), "iter1_sha256": _sha(png),
        })
    return rows

def write_manifest(out: Path = Path("datasets/gold/audit_v2_manifest.json")) -> Path:
    rows = build_manifest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
```
- [ ] **Step 4 跑测试确认通过** — `pytest experiments/tests/test_audit_v2_manifest.py -v`
- [ ] **Step 5 生成 manifest** — `python -c "from experiments.audit.manifest_v2 import write_manifest; print(write_manifest())"`；确认 60 行
- [ ] **Step 6 提交** — `git add experiments/audit/manifest_v2.py experiments/tests/test_audit_v2_manifest.py datasets/gold/audit_v2_manifest.json && git commit -m "feat(audit): freeze new60 manifest"`

### Task 0.2：生成标注 CSV + 标注守则

**Files:** Modify `experiments/audit/manifest_v2.py`(加 `write_annotation_kit`);Create `AUDIT_V2_ANNOTATION_GUIDE.md`

- [ ] **Step 1** 在 `manifest_v2.py` 加:
```python
import csv
def write_annotation_kit(out_csv: Path = Path("datasets/gold/audit_v2_annotation_sheet.csv")) -> Path:
    rows = json.loads(Path("datasets/gold/audit_v2_manifest.json").read_text(encoding="utf-8"))
    cols = ["run_folder","title","template","iter1_png",
            "primary_issue","secondary_issues","other_description","guard_notes","confidence","free_notes"]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows:
            w.writerow({"run_folder":r["run_folder"],"title":r["title"],
                        "template":r["template"],"iter1_png":r["iter1_png"]})
    return out_csv
```
- [ ] **Step 2** 生成两份(A/B 各一份副本):`python -c "from experiments.audit.manifest_v2 import write_annotation_kit as w; w(); import shutil; [shutil.copy('datasets/gold/audit_v2_annotation_sheet.csv', f'datasets/gold/audit_v2_labels_{x}.csv') for x in ('annotatorA','annotatorB')]"`
- [ ] **Step 3** 手写 `AUDIT_V2_ANNOTATION_GUIDE.md`:6 类定义 + 边界口诀(直接抄 spec §2:space↔structure、overload↔space 互斥;asset_mismatch↔too_small;hierarchy_emphasis 含过度强调)+ open-coding 说明(先自由写毛病→映射→`other_description` 记不属任何类的)+ 填表示例 1 行。
- [ ] **Step 4 提交** — `git add experiments/audit/manifest_v2.py AUDIT_V2_ANNOTATION_GUIDE.md datasets/gold/audit_v2_annotation_sheet.csv && git commit -m "feat(audit): annotation kit + guide for new60"`

> **交付给标注者:** `AUDIT_V2_ANNOTATION_GUIDE.md` + 各自的 `audit_v2_labels_annotator{A,B}.csv` + 图在 `iter1_png` 列路径(都在 `outputs/runs/*/pptx/iter_1.png`)。两人先共标前 10 行校准,再独立标完。

---

## Phase 1 — taxonomy 升 6 类

### Task 1.1：改 `experiments/audit/taxonomy.py`

**Files:** Modify `experiments/audit/taxonomy.py`;Test `experiments/tests/test_audit_v2_taxonomy.py`

- [ ] **Step 1 写失败测试**
```python
from experiments.audit.taxonomy import REAL_ISSUES, ISSUE_GLOSS, validate_label
def test_six_classes_with_asset_split_and_emphasis_rename():
    assert set(REAL_ISSUES) == {
      "space_imbalance","text_overload","hierarchy_emphasis_error",
      "asset_mismatch","asset_too_small","structure_alignment_error"}
    assert "over" in ISSUE_GLOSS["hierarchy_emphasis_error"].lower()  # 含 over-emphasis
    validate_label({"primary_issue":"asset_mismatch"})               # 不抛错
```
- [ ] **Step 2 跑测试确认失败**
- [ ] **Step 3 实现**:在 `AuditIssueType` 用 `ASSET_MISMATCH="asset_mismatch"` / `ASSET_TOO_SMALL="asset_too_small"` 替换 `ASSET_UTILIZATION_ERROR`;`VISUAL_HIERARCHY_WEAK`→`HIERARCHY_EMPHASIS_ERROR="hierarchy_emphasis_error"`。同步更新 `REAL_ISSUES`、`ISSUE_GLOSS`(hierarchy gloss 加「or an element is **over**-emphasized e.g. oversized decorative numbers」;asset 拆两条;space/structure 用 spec 口诀措辞)、`ISSUE_TO_ACTIONS`、`OLD_TO_NEW`(`figure_too_small`→`asset_too_small`;新增 `empty_space`→`space_imbalance` 已有)。`text_overload` gloss 末尾加「**(negative control: generation 已基本消除,VLM 仍报即假阳)**」。
- [ ] **Step 4 跑测试确认通过**;并跑既有 `pytest experiments/tests/test_audit_taxonomy.py -v` 确认旧测试已更新/不回归(旧测试若 hardcode 5 类需同步改)。
- [ ] **Step 5 验证 prompt 自动更新** — `python -c "from experiments.audit.vlm_labeler import build_prompt; print(build_prompt())"`,确认列出 6 类、含 hierarchy 的 over-emphasis。
- [ ] **Step 6 提交** — `git commit -m "feat(audit): taxonomy v6 (asset split + hierarchy/emphasis rename + text_overload as neg-control)"`

---

## Phase 2 — 2 条客观几何规则(geom_rules.py;overflow 已取消)

### Task 2.1：overlap 规则(最干净,先做)

**Files:** Create `experiments/audit/geom_rules.py`;Test `experiments/tests/test_audit_v2_geom.py`

- [ ] **Step 1 写失败测试**(用合成 bbox)
```python
from experiments.audit.geom_rules import _overlap_ratio
def test_overlap_ratio_basic():
    assert _overlap_ratio((0,0,100,100),(50,50,100,100)) > 0.0   # 相交
    assert _overlap_ratio((0,0,100,100),(200,200,50,50)) == 0.0  # 不交
```
- [ ] **Step 2 跑测试确认失败**
- [ ] **Step 3 实现**(python-pptx 读 `pptx/iter_1.pptx` 的 shape EMU 几何)
```python
# geom_rules.py
from __future__ import annotations
from pathlib import Path
from pptx import Presentation

def _overlap_ratio(a, b):  # a,b = (l,t,w,h)
    ax,ay,aw,ah=a; bx,by,bw,bh=b
    ix=max(0,min(ax+aw,bx+bw)-max(ax,bx)); iy=max(0,min(ay+ah,by+bh)-max(ay,by))
    inter=ix*iy
    if inter<=0: return 0.0
    return inter/min(aw*ah, bw*bh)

def overlap_violations(pptx_path: Path, thresh: float = 0.10) -> list[dict]:
    prs=Presentation(str(pptx_path)); out=[]
    shapes=[s for s in prs.slides[0].shapes if s.width and s.height]
    boxes=[(s.left,s.top,s.width,s.height) for s in shapes]
    for i in range(len(boxes)):
        for j in range(i+1,len(boxes)):
            r=_overlap_ratio(boxes[i],boxes[j])
            if r>=thresh: out.append({"i":i,"j":j,"ratio":round(r,3)})
    return out
```
- [ ] **Step 4 跑测试通过**;**Step 5** 真跑一张自家 + 一张 Paper2Poster:`python -c "from experiments.audit.geom_rules import overlap_violations as ov; print('ours',len(ov('outputs/runs/<任一>/pptx/iter_1.pptx'))); print('p2p',len(ov('../Paper2Poster-latest/<qwen3vl_qwen3vl>_generated_posters/data/2604.05005v2/poster.pptx')))"` —— 期望自家≈0、P2P>0(若 P2P 无 .pptx 只有 png,记为 limitation)。**Step 6 提交**。

### Task 2.2：contrast 规则(主题级,负控制)

**Files:** Modify `experiments/audit/geom_rules.py`;同测试文件

- [ ] **Step 1 先读源**:`app/ppt_renderer.py` 找主题→颜色映射(symbol 名,如 `THEMES`/`COLOR_THEMES`),记下 body-text 与 panel-fill 的 RGB。
- [ ] **Step 2 写失败测试**
```python
from experiments.audit.geom_rules import wcag_ratio, contrast_ok
def test_wcag_known():
    assert round(wcag_ratio((255,255,255),(0,0,0)),1)==21.0   # 黑白=21
def test_theme_contrast_pass():
    assert contrast_ok("academic_blue") is True               # 自家主题应达标
```
- [ ] **Step 3 实现** `wcag_ratio(rgb1,rgb2)`(标准相对亮度公式)+ `contrast_ok(color_theme)`:从 ppt_renderer 主题表查 (text,fill),算比值,`>=4.5` 为 True。主题表用 `from app.ppt_renderer import <THEMES symbol>`(Step1 确认的名)。
- [ ] **Step 4-6** 测试通过 → 对全部主题打印比值(确认都 ≥4.5,坐实「low_contrast 全是 VLM 幻觉」)→ 提交。

### Task 2.3：overflow 规则 —— ❌ 已取消(用户 2026-06-11 选 c)

**Files:** ~~Modify `experiments/audit/geom_rules.py`~~ —— 不做。真实 pptx 经 soffice autofit 缩字,字面溢出基本不显现;contrast 已是干净幻觉探针。`text_overload` 假阳率改用**人工 gold(预注册 gold≈0)**衡量(Phase 4)。下面步骤作废,仅作记录。

---

## Phase 3 — VLM 批量打标(direct + narrowed)

### Task 3.1：vlm_labeler 支持 narrowed 变体

**Files:** Modify `experiments/audit/vlm_labeler.py`

- [ ] **Step 1 写失败测试**:`build_prompt(variant="narrowed")` 含 6 个 cue 词(overflow/loose_spacing/figure_text_mismatch/figure_too_small/large_blank/no_focus);`build_prompt()` 默认 direct 不变。
- [ ] **Step 2 失败** → **Step 3** 给 `build_prompt(variant="direct")` 加分支;narrowed 版逐 cue 取证再聚合(措辞参考既有 `experiments/scripts/ablation_narrowed_prompt.py`);`label_poster(..., variant=)` 透传。
- [ ] **Step 4 通过** → **Step 5 提交**。

### Task 3.2：批量 driver `run_audit_v2.py`

**Files:** Create `experiments/scripts/run_audit_v2.py`

- [ ] **Step 1 写失败测试**(`--dry-run` 只打印将处理的 60 张、不调 VLM)。
- [ ] **Step 2 失败** → **Step 3 实现**:读 manifest → 对每张 `iter1_png` 调 `label_poster(png, model=QWEN_VL_MODEL, variant=v)` for v in (direct,narrowed) → 同时跑 `geom_rules` 两规则(overlap/contrast)→ 落
  `experiments/results/audit_v2_new60/vlm_qwen32b_{direct,narrowed}.json` 和 `geom_rules.json`。`--models` 可选 8B/30B;`--limit` 调试。每张 crash 不中断(label_poster 本就返回 stub)。
- [ ] **Step 4 dry-run 通过** → **Step 5 真跑** `python -m experiments.scripts.run_audit_v2`(60 张 × 2 prompt,留意限流;失败条目 source 字段标记)→ **Step 6 提交脚本**(结果 JSON 视体积决定是否 gitignore)。

---

## Phase 4 — 指标 + findings

### Task 4.1：metrics_v2.py(手写 κ / 混淆 / P-R-F1 / 熵 / 先验 / 假阳)

**Files:** Create `experiments/audit/metrics_v2.py`;Test `experiments/tests/test_audit_v2_metrics.py`

- [ ] **Step 1 写失败测试**(已知小例对拍)
```python
from experiments.audit.metrics_v2 import cohen_kappa, prior_baseline_acc, label_entropy
def test_kappa_perfect(): assert cohen_kappa(["a","b","a"],["a","b","a"])==1.0
def test_prior_baseline(): assert prior_baseline_acc(["a","a","b"])==2/3
def test_entropy_single_label_zero(): assert label_entropy(["a","a","a"])==0.0
```
- [ ] **Step 2 失败** → **Step 3 实现**:`cohen_kappa`(po/pe 公式)、`confusion_matrix`、`per_class_prf`(recall/precision/F1)、`label_entropy`(香农,归一化)、`prior_baseline_acc`(最频标签占比)、`false_positive_rate(vlm_labels, rule_ok, target)`(rule 说没问题而 VLM 报 target 的比例)。纯函数、无 sklearn。
- [ ] **Step 4 通过** → **Step 5 提交**。

### Task 4.2：分析脚本 `analyze_audit_v2.py` → AUDIT_V2_FINDINGS.md

**Files:** Create `experiments/scripts/analyze_audit_v2.py`

- [ ] **Step 1 写失败测试**(喂合成 gold+VLM,断言输出含 `verdict ∈ {S1,S2,S3}` 且 per-class 表行数=6)。
- [ ] **Step 2 失败** → **Step 3 实现**:
  - 载 `audit_v2_labels_gold.json`(裁决后的 gold;若标注未完成,支持 `--gold` 可缺省,先只出 VLM 自身分布+假阳+熵)、两个 VLM JSON、`geom_rules.json`。
  - 算:人-人 κ(A vs B)、VLM-gold κ(direct & narrowed)、混淆矩阵、6 类 P/R/F1、VLM 标签熵 + top1 占比、先验基线、`text_overload` 假阳率(VLM vs 人工 gold,gold≈0)、`low_contrast`/`overlap` 假阳率(VLM vs 几何规则)、**按 template 拆分分布**、`other` 清单。
  - 套 spec §6 阈值出 **verdict S1/S2/S3**(含小样本警告:某类 gold<8 不下判定)。
  - 写 `experiments/results/audit_v2_new60/{confusion_matrix.json,per_issue_table.csv,kappa.json}` + 顶层 `AUDIT_V2_FINDINGS.md`(verdict + 三表 + 下一步方向)。
- [ ] **Step 4 通过** → **Step 5 真跑**(标注好后)`python -m experiments.scripts.analyze_audit_v2` → **Step 6 提交**。

---

## Self-Review(已对 spec 逐节核对)

- **样本/iter_1/禁 preview**:Task 0.1 用 `pptx/iter_1.png`(real),manifest 记 sha ✓
- **6 类 + asset 拆 + hierarchy 改名 + text_overload 负控制**:Task 1.1 ✓
- **2 客观规则(contrast/overlap)双重身份**:Phase 2 ✓(overflow 按用户决定取消;overlap 在 P2P 上演示可迁移)
- **双标注 + κ + open-coding + 校准**:Task 0.2 kit + Guide,Task 4.2 算人-人 κ ✓
- **VLM:32B × direct/narrowed,8B/30B 可选**:Phase 3 ✓
- **指标:per-class R/P/F1、VLM-gold κ、混淆、熵、先验、假阳、分模板**:Phase 4 ✓
- **S1/S2/S3 阈值 + 小样本警告**:Task 4.2 ✓
- **前沿模型留接口**:`run_audit_v2 --models` 可加,本轮 Qwen-only ✓
- **范围外不做**(v2 路由器/severity/svfp_trace/模板去留):本计划不含 ✓
- 无占位符;后置任务引用的 `label_poster`/`build_prompt`/`corpus.find_run_dirs` 均为已存在或前置任务定义的符号。两处「先读源」(ppt_renderer 主题表、feedback_loop overflow)是读现有代码、非占位。

---

## Execution Handoff

Plan 已存 `PosterCS/AUDIT_V2_IMPLEMENTATION_PLAN.md`。两种执行方式:
1. **Subagent-Driven(推荐)** — 每个 Task 派新 subagent,任务间 review,迭代快(`superpowers:subagent-driven-development`)。
2. **Inline** — 本会话内分批执行 + 检查点(`superpowers:executing-plans`)。
