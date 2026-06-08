"""Narrowed-prompt ablation: can concrete per-issue cues fix the VLM critique?

Tests the user's "idea 2": instead of asking the VLM abstractly to pick a
layout issue (the 5-class taxonomy prompt used in the scale ablation), give it
**5 concrete perceptual cues** (one per issue class) and ask it to check each.
We then compare to the scale-ablation baseline (same model, same 16 posters,
ORIGINAL prompt) to measure the DELTA -- in particular whether **asset
(figure-text mismatch) recall improves**, which directly tests the hypothesis
"the VLM simply cannot read the figures, so narrowing the prompt won't help".

Holds posters + model (Qwen3-VL-32B, the prior-heavy arm) constant; only the
PROMPT changes vs experiments/results/ablation_model_scale.json (32B).

Run (from PosterCS root):
    unset VIRTUAL_ENV
    POSTER_LLM_TIMEOUT_S=90 .venv/bin/python -m experiments.scripts.ablation_narrowed_prompt
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path

from openai import OpenAI
from PIL import Image

from app.config import DASHSCOPE_API_KEY
from app.vlm_commenter import _extract_json_block, image_to_base64

MODEL = "Qwen/Qwen3-VL-32B-Instruct"
GOLD_CSV = Path("experiments/results/audit_v1_old48/human_gold_subset.csv")
SCALE_JSON = Path("experiments/results/ablation_model_scale.json")
OUT = Path("experiments/results/ablation_narrowed_prompt.json")
TEMP = 0.1

# concrete cue key -> canonical issue
CUE_TO_ISSUE = {
    "overflow": "text_overload",
    "loose_spacing": "space_imbalance",
    "figure_text_mismatch": "asset_utilization_error",
    "large_blank": "structure_alignment_error",
    "no_focus": "visual_hierarchy_weak",
}

PROMPT = """你在审查一张学术海报的版面。请逐一检查下面 5 个【具体线索】,每个只回答存在与否 + 一句证据,然后选出最严重的一个作为 primary。

1. overflow —— 有没有文字超出它的框、和图片/其它文字重叠、或被裁切?
2. loose_spacing —— bullet 之间或模块内部有没有明显过大的空隙(间距太大、显得空)?
3. figure_text_mismatch —— 逐张看配图:图的【内容】和它所在模块的【文字主题】是否相关?有没有明显放错/不相关/纯装饰的图?(请先真正描述每张图画的是什么,再判断相不相关)
4. large_blank —— 整张海报有没有大片连续空白(例如某一侧/某个角整块空着,内容挤在另一边)?
5. no_focus —— 是否缺少一个明显突出的重点模块/视觉焦点?所有模块大小是否雷同、没有主次?

只输出合法 JSON,不要解释,不要 Markdown:
{
  "cues": {
    "overflow": {"present": true, "evidence": "..."},
    "loose_spacing": {"present": false, "evidence": "..."},
    "figure_text_mismatch": {"present": false, "evidence": "..."},
    "large_blank": {"present": false, "evidence": "..."},
    "no_focus": {"present": false, "evidence": "..."}
  },
  "primary_cue": "上面 5 个 key 之一",
  "primary_evidence": "一句话"
}"""


def label_one(png: Path):
    image = Image.open(png).convert("RGB")
    client = OpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url="https://api.siliconflow.cn/v1",
        timeout=float(os.getenv("POSTER_LLM_TIMEOUT_S", "90")),
        max_retries=0,
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_to_base64(image)}"}},
            ],
        }],
        temperature=TEMP,
        max_tokens=1000,
        response_format={"type": "json_object"},
    )
    content = (resp.choices[0].message.content or "").strip()
    return _extract_json_block(content)


def label_with_retry(png: Path, attempts: int = 3):
    for k in range(attempts):
        try:
            d = label_one(png)
            if d:
                return d, "vlm"
        except Exception as e:  # transient SiliconFlow timeout etc.
            print(f"      retry {k + 1}/{attempts}: {str(e)[:60]}")
    return None, "vlm_error"


def run():
    rows = list(csv.DictReader(GOLD_CSV.open(encoding="utf-8")))
    results = []
    for i, r in enumerate(rows, 1):
        d, src = label_with_retry(Path(r["png_path"]))
        cues = (d or {}).get("cues", {}) or {}
        primary_cue = (d or {}).get("primary_cue", "")
        primary_issue = CUE_TO_ISSUE.get(primary_cue, "")
        present = [
            CUE_TO_ISSUE[k] for k, v in cues.items()
            if k in CUE_TO_ISSUE and isinstance(v, dict) and v.get("present")
        ]
        fm = cues.get("figure_text_mismatch") or {}
        results.append({
            "run_id": r["run_id"],
            "human_primary": (r.get("human_primary") or "").strip(),
            "vlm_primary": primary_issue,
            "vlm_present": present,
            "figure_mismatch_flag": bool(isinstance(fm, dict) and fm.get("present")),
            "source": src,
            "raw": d,
        })
        print(f"  ({i:2d}/{len(rows)}) {r['run_id'][:12]:12} -> {primary_issue:26} [{src}]")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"model": MODEL, "prompt": "narrowed_5cue", "per_poster": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[narrowed] raw -> {OUT}")
    analyze(results)


def analyze(results):
    n = len(results)
    valid = [r for r in results if r["source"] == "vlm"]
    to_primary = sum(1 for r in results if r["vlm_primary"] == "text_overload")
    asset_primary = sum(1 for r in results if r["vlm_primary"] == "asset_utilization_error")
    asset_flag = sum(1 for r in results if r["figure_mismatch_flag"])
    human_asset = sum(1 for r in results if r["human_primary"] == "asset_utilization_error")
    asset_recall = sum(
        1 for r in results
        if r["human_primary"] == "asset_utilization_error" and r["figure_mismatch_flag"]
    )
    exact = sum(1 for r in results if r["vlm_primary"] and r["vlm_primary"] == r["human_primary"])
    dist = Counter(r["vlm_primary"] for r in results)

    base = {}
    if SCALE_JSON.exists():
        try:
            sj = json.loads(SCALE_JSON.read_text(encoding="utf-8"))
            rows32 = sj.get("per_model", {}).get("32B", [])
            base["to"] = sum(1 for x in rows32 if x.get("vlm_primary") == "text_overload")
            base["asset"] = sum(1 for x in rows32 if x.get("vlm_primary") == "asset_utilization_error")
        except Exception:
            pass

    print("\n" + "=" * 66)
    print(f" NARROWED-PROMPT ABLATION (32B, n={n}; human asset={human_asset}/{n})")
    print("=" * 66)
    print(f" valid labels: {len(valid)}/{n}")
    print(f" primary dist: {dict(dist.most_common())}")
    print(f" text_overload primary: {to_primary}/{n}   (orig-prompt 32B: {base.get('to','?')}/{n})")
    print(f" asset primary:         {asset_primary}/{n}   (orig-prompt 32B: {base.get('asset','?')}/{n})")
    print(f" figure_mismatch flagged present (any poster): {asset_flag}/{n}")
    print(f" ** asset RECALL (human=asset & VLM flagged mismatch): {asset_recall}/{human_asset} **")
    print(f" exact match w/ human_primary: {exact}/{n}")

    print("\n VERDICT (does a direct prompt fix the figure-blindness?):")
    if human_asset:
        rr = asset_recall / human_asset
        if rr >= 0.6:
            print(f"   asset recall {asset_recall}/{human_asset} HIGH -> narrowing HELPS. Earlier 1/12")
            print("   failure was prompt-dilution; asset IS salvageable with a direct figure-")
            print("   relevance prompt. VLM can be a (secondary) asset detector.")
        elif rr <= 0.25:
            print(f"   asset recall {asset_recall}/{human_asset} LOW -> CAPABILITY CEILING confirmed.")
            print("   Even a direct figure-relevance prompt can't make the VLM see the mismatch.")
            print("   Route asset to script+text-LLM (caption vs panel text), NOT pixel-VLM.")
        else:
            print(f"   asset recall {asset_recall}/{human_asset} PARTIAL -> narrowing helps a bit but")
            print("   unreliable; prefer script+text-LLM for asset, VLM as weak secondary.")
    print("=" * 66)


if __name__ == "__main__":
    run()
