#!/usr/bin/env python3
"""Track A scoring: agreement between the human gold labels and the VLM, from the filled
human_gold_subset.csv. Answers the live question with hard numbers:
  - Cohen's kappa(human, VLM) on text_overload presence, text_overload primary, and the
    multiclass primary issue.
  - Where on the density axis the human's "overload" threshold sits (if it exists at all).
  - What the human calls the real problem instead (human_primary distribution).

Zero API. Reads only the (now filled) experiments/results/audit/human_gold_subset.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

TO = "text_overload"
YES = {"yes", "y", "1", "true"}
BORDER = {"borderline", "maybe", "b"}


def kappa(a: list, b: list) -> tuple[float | None, float, str]:
    """Cohen's kappa for paired categorical labels a,b. Returns (kappa, p_observed, note)."""
    assert len(a) == len(b)
    n = len(a)
    if n == 0:
        return None, 0.0, "empty"
    cats = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca.get(c, 0) / n) * (cb.get(c, 0) / n) for c in cats)
    if abs(1 - pe) < 1e-12:
        # One or both raters constant on a single shared category -> kappa undefined.
        return 0.0, po, "degenerate (a rater is constant); kappa set to 0"
    return round((po - pe) / (1 - pe), 3), round(po, 3), ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="experiments/results/audit/human_gold_subset.csv")
    ap.add_argument("--out", default="experiments/results/audit/analysis_human_gold_kappa.json")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv)))
    n = len(rows)

    def norm(s):
        return (s or "").strip().lower()

    human_overload = [norm(r["human_overload"]) for r in rows]
    human_primary = [norm(r["human_primary"]) for r in rows]
    vlm_primary = [norm(r["vlm_primary"]) for r in rows]
    vlm_secondary = [[norm(x) for x in (r["vlm_secondary"] or "").split(";") if x.strip()] for r in rows]
    dens_pct = [float(r["density_pct"]) for r in rows]
    mean_chars = [float(r["mean_chars_per_panel"]) for r in rows]

    # Binary tracks.
    human_TO = ["yes" if v in YES else ("border" if v in BORDER else "no") for v in human_overload]
    human_TO_bin = ["TO" if v == "yes" else "notTO" for v in human_TO]  # borderline -> notTO (strict)
    vlm_TO_primary = ["TO" if p == TO else "notTO" for p in vlm_primary]
    vlm_TO_present = ["TO" if (p == TO or TO in sec) else "notTO"
                      for p, sec in zip(vlm_primary, vlm_secondary)]

    k_present = kappa(human_TO_bin, vlm_TO_present)
    k_primary = kappa(human_TO_bin, vlm_TO_primary)
    k_multiclass = kappa(human_primary, vlm_primary)

    # Threshold locator: density percentiles where the human DID vs DID NOT call overload.
    yes_pcts = [dens_pct[i] for i in range(n) if human_TO[i] == "yes"]
    no_pcts = [dens_pct[i] for i in range(n) if human_TO[i] == "no"]
    border_pcts = [dens_pct[i] for i in range(n) if human_TO[i] == "border"]

    # Primary confusion (human -> what VLM said).
    confusion = Counter((human_primary[i] or "(blank)", vlm_primary[i]) for i in range(n))

    result = {
        "n": n,
        "human_overload_counts": dict(Counter(human_TO)),
        "human_primary_counts": dict(Counter(p or "(blank)" for p in human_primary)),
        "vlm_primary_counts": dict(Counter(vlm_primary)),
        "vlm_TO_present_count": sum(1 for v in vlm_TO_present if v == "TO"),
        "vlm_TO_primary_count": sum(1 for v in vlm_TO_primary if v == "TO"),
        "kappa_text_overload_PRESENCE": {"kappa": k_present[0], "p_observed_agreement": k_present[1], "note": k_present[2]},
        "kappa_text_overload_PRIMARY": {"kappa": k_primary[0], "p_observed_agreement": k_primary[1], "note": k_primary[2]},
        "kappa_PRIMARY_ISSUE_multiclass": {"kappa": k_multiclass[0], "p_observed_agreement": k_multiclass[1], "note": k_multiclass[2]},
        "threshold": {
            "human_overload_yes_density_pcts": sorted(yes_pcts),
            "human_overload_borderline_density_pcts": sorted(border_pcts),
            "human_overload_no_density_pct_range": [min(no_pcts), max(no_pcts)] if no_pcts else None,
            "interpretation": ("human never calls overload across the full 0-98 pct density range -> "
                               "no threshold exists in this corpus")
            if not yes_pcts and not border_pcts else "see lists",
        },
        "primary_confusion_human_to_vlm": {f"{h} -> {v}": c for (h, v), c in confusion.most_common()},
        "caveats": [
            f"n={n}; single annotator who is also the system author -> internal evidence, needs >=1 "
            "independent annotator to be reviewer-proof.",
            "human labels are near-constant (overload all 'no'; primary mostly space_imbalance), so "
            "kappa is descriptive of a near-total disagreement, not a calibrated coefficient.",
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    # ---- console ----
    print(f"[human-gold kappa] n={n}  wrote {out}")
    print()
    print(f"human_overload : {result['human_overload_counts']}")
    print(f"human_primary  : {result['human_primary_counts']}")
    print(f"vlm_primary    : {result['vlm_primary_counts']}")
    print(f"VLM text_overload present on {result['vlm_TO_present_count']}/{n}, "
          f"primary on {result['vlm_TO_primary_count']}/{n};  human overload 'yes' on "
          f"{result['human_overload_counts'].get('yes',0)}/{n}")
    print()
    print("== agreement (Cohen's kappa; 0 = chance, 1 = perfect, <0 = worse than chance) ==")
    for key in ["kappa_text_overload_PRESENCE", "kappa_text_overload_PRIMARY", "kappa_PRIMARY_ISSUE_multiclass"]:
        d = result[key]
        print(f"  {key:<34} kappa={d['kappa']}  observed_agree={d['p_observed_agreement']}  {d['note']}")
    print()
    print("== where is the human's overload threshold? ==")
    print(f"  human said 'overload=yes' at density pcts: {result['threshold']['human_overload_yes_density_pcts'] or 'NONE'}")
    print(f"  human said 'overload=no'  spanning pcts  : {result['threshold']['human_overload_no_density_pct_range']}")
    print(f"  -> {result['threshold']['interpretation']}")
    print()
    print("== what the human calls the real problem (human_primary -> vlm_primary) ==")
    for k, c in result["primary_confusion_human_to_vlm"].items():
        print(f"  {c:>2}x  {k}")


if __name__ == "__main__":
    main()
