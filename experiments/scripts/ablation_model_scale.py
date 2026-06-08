"""Model-scale ablation: is the ``text_overload`` prior a small-model artifact?

Research question (the one the user asked):

    "VLM 不可靠会不会是我选的 Qwen3 模型太小了呢?"

We hold the **16 human-gold posters constant** and vary **only the VLM size**
(Qwen3-VL 8B -> 30B-A3B -> 32B), re-labeling each poster with the *same* audit
prompt / taxonomy. Everything else (image, resolution, prompt, temperature) is
identical across sizes, so the only moving part is model scale.

Interpretation:

* If ``text_overload``-dominance and the human-mis-ranking are **flat** across
  sizes, the prior is **not** explained by model size within this family —
  picking a bigger Qwen would not fix it (the finding survives the obvious
  "use a bigger model" rebuttal, at least within this family).
* If they fall **monotonically** with size, model scale matters and we must
  test a frontier model (GPT-4o / Gemini) before claiming "VLMs are unreliable".

Run (from the PosterCS root, with the venv)::

    unset VIRTUAL_ENV
    .venv/bin/python -m experiments.scripts.ablation_model_scale

Outputs ``experiments/results/ablation_model_scale.json`` and prints a
comparison table + an automatic verdict.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

from experiments.audit import vlm_labeler

# (display tag, SiliconFlow model id) — all three confirmed in the user's
# SiliconFlow billing history.
MODELS = [
    ("8B", "Qwen/Qwen3-VL-8B-Instruct"),
    ("30B-A3B", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
    ("32B", "Qwen/Qwen3-VL-32B-Instruct"),
]

GOLD_CSV = Path("experiments/results/audit_v1_old48/human_gold_subset.csv")
OUT = Path("experiments/results/ablation_model_scale.json")
TEMP = 0.1  # low temperature: the "primary" deterministic read

TEXT_OVERLOAD = "text_overload"
ASSET_ERROR = "asset_utilization_error"


def load_gold() -> list[dict]:
    if not GOLD_CSV.exists():
        print(f"[ablation] missing gold csv: {GOLD_CSV}", file=sys.stderr)
        raise SystemExit(2)
    return list(csv.DictReader(GOLD_CSV.open(encoding="utf-8")))


def label_with_retry(png: Path, model: str, *, run_id: str, attempts: int = 3) -> dict:
    """Call the labeler, retrying transient transport failures.

    The SiliconFlow 30B-A3B (MoE) endpoint intermittently times out; a clean
    label usually arrives on a retry. We only retry when ``source != 'vlm'``
    (i.e. error/unparsed/disabled), so a successful read is never re-billed.
    """

    last = {}
    for k in range(attempts):
        lab = vlm_labeler.label_poster(png, model=model, temperature=TEMP, run_id=run_id, pass_idx=0)
        if lab.get("source") == "vlm":
            return lab
        last = lab
        print(f"      retry {k + 1}/{attempts} ({lab.get('source')}: {str(lab.get('notes',''))[:50]})")
    return last


def run() -> dict:
    rows = load_gold()
    n = len(rows)
    print(f"[ablation] {n} human-gold posters x {len(MODELS)} models (temp={TEMP})")

    per_model: dict[str, list[dict]] = {}
    for tag, model in MODELS:
        print(f"\n[ablation] === {tag}  ({model}) ===")
        results = []
        for i, r in enumerate(rows, 1):
            png = Path(r["png_path"])
            lab = label_with_retry(png, model, run_id=r["run_id"])
            prim = (lab.get("primary_issue") or "").strip()
            sec = lab.get("secondary_issues") or []
            src = lab.get("source") or ""
            note = lab.get("notes") or ""
            results.append({
                "run_id": r["run_id"],
                "human_primary": (r.get("human_primary") or "").strip(),
                "human_overload": (r.get("human_overload") or "").strip(),
                "orig_vlm_primary": (r.get("vlm_primary") or "").strip(),
                "density_pct": (r.get("density_pct") or "").strip(),
                "vlm_primary": prim,
                "vlm_secondary": sec,
                "source": src,
                "notes": note,
            })
            flag = "" if src == "vlm" else f"  <{src}>"
            print(f"  ({i:2d}/{n}) {r['run_id'][:12]:12} -> {prim:26}{flag}")
        per_model[tag] = results

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "models": {t: m for t, m in MODELS},
        "n_posters": n,
        "temp": TEMP,
        "per_model": per_model,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ablation] raw results -> {OUT}")
    analyze(per_model, n)
    return payload


def _stat(results: list[dict]) -> dict:
    n = len(results)
    valid = [r for r in results if r["source"] == "vlm"]
    n_err = n - len(valid)
    to_primary = sum(1 for r in results if r["vlm_primary"] == TEXT_OVERLOAD)
    to_present = sum(
        1 for r in results
        if r["vlm_primary"] == TEXT_OVERLOAD or TEXT_OVERLOAD in (r["vlm_secondary"] or [])
    )
    asset_primary = sum(1 for r in results if r["vlm_primary"] == ASSET_ERROR)
    # mis-ranking: human saw a figure/asset problem, VLM cried text_overload
    misrank = sum(
        1 for r in results
        if r["human_primary"] == ASSET_ERROR and r["vlm_primary"] == TEXT_OVERLOAD
    )
    exact = sum(1 for r in results if r["vlm_primary"] and r["vlm_primary"] == r["human_primary"])
    dist = Counter(r["vlm_primary"] for r in results)
    return {
        "n": n,
        "n_valid": len(valid),
        "n_error": n_err,
        "text_overload_primary": to_primary,
        "text_overload_present": to_present,
        "asset_primary": asset_primary,
        "misrank_human_asset_vlm_to": misrank,
        "exact_match_human": exact,
        "primary_dist": dict(dist.most_common()),
        "first_error_note": next((r["notes"] for r in results if r["source"] != "vlm"), ""),
    }


def analyze(per_model: dict[str, list[dict]], n: int) -> None:
    tags = [t for t, _ in MODELS if t in per_model]
    stats = {t: _stat(per_model[t]) for t in tags}

    # human baseline (constant across models — read from any model's rows)
    any_rows = per_model[tags[0]]
    human_to = sum(1 for r in any_rows if r["human_primary"] == TEXT_OVERLOAD)
    human_asset = sum(1 for r in any_rows if r["human_primary"] == ASSET_ERROR)

    print("\n" + "=" * 72)
    print(f" MODEL-SCALE ABLATION  (n={n} human-gold posters; all human_overload=no)")
    print("=" * 72)

    def row(label, key, human=None):
        cells = " | ".join(f"{stats[t][key]:>2}/{n}" for t in tags)
        h = f" | human {human}/{n}" if human is not None else ""
        print(f" {label:34} | {cells}{h}")

    print(f" {'metric':34} | " + " | ".join(f"{t:>6}" for t in tags))
    print(" " + "-" * 70)
    row("valid labels (source=vlm)", "n_valid")
    row("text_overload = PRIMARY", "text_overload_primary", human=human_to)
    row("text_overload PRESENT (pri|sec)", "text_overload_present")
    row("asset_util_error = PRIMARY", "asset_primary", human=human_asset)
    row("mis-rank (human=asset, vlm=TO)", "misrank_human_asset_vlm_to")
    row("exact match w/ human_primary", "exact_match_human")

    print("\n primary-issue distribution per model:")
    for t in tags:
        print(f"   {t:8}: {stats[t]['primary_dist']}")
        if stats[t]["n_error"]:
            print(f"            ({stats[t]['n_error']} errors; first: {stats[t]['first_error_note'][:80]})")

    # ---- automatic verdict on the size question ----
    print("\n" + "=" * 72)
    rates = [stats[t]["text_overload_primary"] / n for t in tags if stats[t]["n_valid"]]
    if len(rates) < 2:
        print(" VERDICT: insufficient valid labels to judge — check model ids / API.")
        print("=" * 72)
        return
    spread = max(rates) - min(rates)
    # monotonic decrease 8B -> 32B?
    ordered = [stats[t]["text_overload_primary"] / n for t in tags if stats[t]["n_valid"]]
    monotonic_down = all(ordered[i] >= ordered[i + 1] for i in range(len(ordered) - 1))

    print(" VERDICT (is the text_overload prior a small-model artifact?)")
    print(f"   text_overload-primary rate by size: " +
          ", ".join(f"{t}={stats[t]['text_overload_primary']}/{n}" for t in tags))
    print(f"   spread (max-min) = {spread:.2f}")
    if spread <= 0.15:
        print("   => FLAT across 8B->32B. The prior is NOT explained by model size")
        print("      within the Qwen3-VL family. 'Pick a bigger Qwen' would not fix it.")
        print("      Finding survives the size rebuttal here; still test a FRONTIER model.")
    elif monotonic_down and spread >= 0.25:
        print("   => MONOTONIC DECREASE with size, large spread. Model scale MATTERS.")
        print("      The prior is (partly) a small-model artifact — must test frontier")
        print("      models before claiming 'VLM critique is unreliable' in general.")
    else:
        print("   => PARTIAL / non-monotonic. Size has some effect but doesn't erase the")
        print("      prior. Most likely true picture; report graded, test a frontier model.")
    print("=" * 72)


if __name__ == "__main__":
    run()
