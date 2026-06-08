#!/usr/bin/env python3
"""Discriminating analysis: is `text_overload` a density-grounded failure or a VLM prior?

The P0 audit found `text_overload` at 83% primary / 100% presence. A class that fires on
every poster has near-zero discriminative power UNLESS it tracks a measurable layout quantity.
This script tests exactly that, with zero API cost, by reading only the already-written
label files in experiments/results/audit/labels/*.json.

Core test: group posters by the VLM's PRIMARY issue and compare layout-density proxies.
  - If `text_overload`-primary posters are systematically DENSER than `visual_hierarchy_weak`-
    primary posters (high AUC on char/bullet density) -> the VLM elevates denser posters to
    text_overload; the construct is grounded.
  - If the density distributions OVERLAP (AUC ~ 0.5) -> the label is assigned regardless of how
    dense the poster is -> consistent with a VLM prior ("口头禅"); text_overload needs an
    operational threshold or human-gold recalibration.

Also reports: presence-vs-density ("does even the least-dense poster still get tagged?") and
where the BLIP poster the user flagged sits in the density ranking.
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

OK_SOURCES = {"vlm", "vlm_partial", "human"}

# Density / layout proxies, with the direction that means "more text-heavy".
DENSITY_KEYS = [
    "mean_chars_per_panel",
    "max_chars_per_panel",
    "mean_bullets_per_panel",
    "total_bullets",
    "text_only_panel_ratio",
    "figure_usage_ratio",
]
# The two proxies most directly meaning "text overload" if the construct is real.
HEADLINE_KEYS = ["mean_chars_per_panel", "max_chars_per_panel", "mean_bullets_per_panel"]

BLIP_RUN_ID = "44a0517194a2"


def chosen_label(rec: dict) -> dict | None:
    labels = rec.get("labels") or []
    if not labels:
        return None
    for lab in labels:  # prefer a human gold label if one exists
        if lab.get("source") == "human":
            return lab
    return labels[0]


def load(labels_dir: Path) -> list[dict]:
    items = []
    for fp in sorted(glob.glob(str(labels_dir / "*.json"))):
        rec = json.loads(Path(fp).read_text())
        lab = chosen_label(rec)
        if lab is None:
            continue
        items.append(
            {
                "run_id": rec.get("run_id"),
                "title": (rec.get("paper_title") or "")[:38],
                "template": rec.get("template"),
                "source": lab.get("source"),
                "primary": lab.get("primary_issue"),
                "secondary": list(lab.get("secondary_issues") or []),
                "proxies": rec.get("proxies") or {},
            }
        )
    return items


def describe(values: list[float]) -> dict | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    n = len(vals)
    return {
        "n": n,
        "mean": round(statistics.mean(vals), 1),
        "median": round(statistics.median(vals), 1),
        "std": round(statistics.pstdev(vals), 1) if n > 1 else 0.0,
        "min": round(min(vals), 1),
        "max": round(max(vals), 1),
    }


def auc(pos: list[float], neg: list[float]) -> float | None:
    """P(random pos > random neg); Mann-Whitney U / (n_pos*n_neg). Ties count 0.5."""
    pos = [v for v in pos if v is not None]
    neg = [v for v in neg if v is not None]
    if not pos or not neg:
        return None
    wins = 0.0
    for a in pos:
        for b in neg:
            wins += 1.0 if a > b else (0.5 if a == b else 0.0)
    return round(wins / (len(pos) * len(neg)), 3)


def pct_rank(value: float, pool: list[float]) -> float | None:
    pool = [v for v in pool if v is not None]
    if value is None or not pool:
        return None
    below = sum(1 for v in pool if v < value)
    return round(100.0 * below / len(pool), 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels-dir", default="experiments/results/audit/labels")
    ap.add_argument("--out", default="experiments/results/audit/analysis_text_overload_validity.json")
    args = ap.parse_args()

    labels_dir = Path(args.labels_dir)
    items = load(labels_dir)
    ok = [it for it in items if it["source"] in OK_SOURCES and it["primary"]]

    by_primary: dict[str, list[dict]] = defaultdict(list)
    for it in ok:
        by_primary[it["primary"]].append(it)

    primary_counts = {k: len(v) for k, v in sorted(by_primary.items(), key=lambda kv: -len(kv[1]))}

    def vals(group: list[dict], key: str) -> list[float]:
        return [g["proxies"].get(key) for g in group if g["proxies"].get(key) is not None]

    # Per-group density description table.
    group_stats: dict[str, dict] = {}
    for prim, group in by_primary.items():
        group_stats[prim] = {key: describe(vals(group, key)) for key in DENSITY_KEYS}

    TO = "text_overload"
    VHW = "visual_hierarchy_weak"
    to_group = by_primary.get(TO, [])
    vhw_group = by_primary.get(VHW, [])

    # Headline: does density separate text_overload-primary from vhw-primary?
    separation = {}
    for key in DENSITY_KEYS:
        separation[key] = {
            "auc_TO_vs_VHW": auc(vals(to_group, key), vals(vhw_group, key)),
            "TO_median": (describe(vals(to_group, key)) or {}).get("median"),
            "VHW_median": (describe(vals(vhw_group, key)) or {}).get("median"),
        }

    # Presence-vs-density: text_overload presence across ALL posters, and whether the
    # least-dense quartile still gets tagged with it (primary OR secondary).
    def has_to(it: dict) -> bool:
        return it["primary"] == TO or TO in it["secondary"]

    presence_count = sum(1 for it in ok if has_to(it))
    all_mean_chars = [(it, it["proxies"].get("mean_chars_per_panel")) for it in ok]
    ranked = sorted([t for t in all_mean_chars if t[1] is not None], key=lambda t: t[1])
    q = max(1, len(ranked) // 4)
    least_dense = ranked[:q]
    least_dense_to_present = sum(1 for it, _ in least_dense if has_to(it))
    least_dense_to_primary = sum(1 for it, _ in least_dense if it["primary"] == TO)

    # Among posters whose primary is NOT text_overload, how often is it still a secondary?
    non_to_primary = [it for it in ok if it["primary"] != TO]
    to_as_secondary = sum(1 for it in non_to_primary if TO in it["secondary"])

    # Where does the BLIP poster the user flagged sit?
    blip = next((it for it in ok if it["run_id"] == BLIP_RUN_ID), None)
    blip_locator = None
    if blip:
        bm = blip["proxies"].get("mean_chars_per_panel")
        blip_locator = {
            "run_id": BLIP_RUN_ID,
            "primary": blip["primary"],
            "mean_chars_per_panel": bm,
            "pct_rank_in_all": pct_rank(bm, [v for _, v in ranked]),
            "pct_rank_in_TO_group": pct_rank(bm, vals(to_group, "mean_chars_per_panel")),
        }

    # Heuristic verdict on the headline proxy.
    head_auc = separation["mean_chars_per_panel"]["auc_TO_vs_VHW"]
    if head_auc is None:
        verdict = "INDETERMINATE — not enough labels in one of the two groups."
    elif head_auc >= 0.70:
        verdict = ("GROUNDED — text_overload-primary posters are measurably denser than "
                   "visual_hierarchy_weak-primary ones; the label tracks a real layout quantity.")
    elif head_auc <= 0.60:
        verdict = ("PRIOR-LIKE — density does NOT separate the two; text_overload is assigned "
                   "largely independent of how dense the poster is. Operationalize via a density/"
                   "font-size threshold or recalibrate against human gold before headlining 83%.")
    else:
        verdict = ("AMBIGUOUS — weak density separation; small n_VHW. Add human gold or a 2nd "
                   "annotator to decide.")

    result = {
        "n_ok": len(ok),
        "n_vhw_caveat": (f"visual_hierarchy_weak n={len(vhw_group)} is small; AUC is descriptive, "
                         "not inferential."),
        "primary_counts": primary_counts,
        "group_density_stats": group_stats,
        "separation_TO_vs_VHW": separation,
        "presence_diagnostic": {
            "text_overload_presence": f"{presence_count}/{len(ok)}",
            "least_dense_quartile_n": len(least_dense),
            "least_dense_with_TO_present": least_dense_to_present,
            "least_dense_with_TO_primary": least_dense_to_primary,
            "non_TO_primary_n": len(non_to_primary),
            "of_those_TO_as_secondary": to_as_secondary,
        },
        "blip_locator": blip_locator,
        "headline_auc_mean_chars": head_auc,
        "verdict": verdict,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    # ---- console report ----
    print(f"[text_overload validity] n_ok={len(ok)}  primary={primary_counts}")
    print(f"[text_overload validity] wrote {out}")
    print()
    print("== density by PRIMARY group (median [min..max], n) ==")
    for prim in sorted(by_primary, key=lambda k: -len(by_primary[k])):
        line = [f"{prim:<26} n={len(by_primary[prim]):<2}"]
        for key in HEADLINE_KEYS:
            d = group_stats[prim][key]
            if d:
                line.append(f"{key.split('_')[1] if key!='mean_bullets_per_panel' else 'bullets'}={d['median']}[{d['min']}..{d['max']}]")
        print("  " + "  ".join(line))
    print()
    print("== does density separate text_overload vs visual_hierarchy_weak? (AUC) ==")
    for key in HEADLINE_KEYS:
        s = separation[key]
        print(f"  {key:<26} AUC(TO>VHW)={s['auc_TO_vs_VHW']}   TO_med={s['TO_median']}  VHW_med={s['VHW_median']}")
    print()
    pd = result["presence_diagnostic"]
    print("== presence vs density ('口头禅' test) ==")
    print(f"  text_overload present on {pd['text_overload_presence']} posters")
    print(f"  least-dense quartile (n={pd['least_dense_quartile_n']}): "
          f"TO present on {pd['least_dense_with_TO_present']}, TO PRIMARY on {pd['least_dense_with_TO_primary']}")
    print(f"  of {pd['non_TO_primary_n']} non-TO-primary posters, {pd['of_those_TO_as_secondary']} still list TO as secondary")
    print()
    if blip_locator:
        print("== BLIP poster the user flagged ==")
        print(f"  primary={blip_locator['primary']}  mean_chars/panel={blip_locator['mean_chars_per_panel']}  "
              f"percentile in all={blip_locator['pct_rank_in_all']}%  in TO-group={blip_locator['pct_rank_in_TO_group']}%")
    print()
    print("VERDICT:", verdict)


if __name__ == "__main__":
    main()
