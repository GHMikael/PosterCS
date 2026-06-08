#!/usr/bin/env python3
"""Build a curated, density-spanning human-gold labeling table (track A).

The VLM tags `text_overload` on 100% of posters with near-coin-flip density separation
(see analysis_text_overload_validity.py). To decide whether that is a real failure or a VLM
prior, we need a human threshold. This selects ~15 posters that SPAN the char-density range
(so the user's accept/reject boundary is locatable), force-including the BLIP poster the user
already reacted to and several visual_hierarchy_weak-primary posters for contrast.

Output: experiments/results/audit/human_gold_subset.csv with blank columns for the user.
Zero API. Reads only experiments/results/audit/labels/*.json.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
from pathlib import Path

OK_SOURCES = {"vlm", "vlm_partial", "human"}
DENSITY_KEY = "mean_chars_per_panel"
BLIP_RUN_ID = "44a0517194a2"
VHW = "visual_hierarchy_weak"


def chosen_label(rec: dict) -> dict | None:
    labels = rec.get("labels") or []
    if not labels:
        return None
    for lab in labels:
        if lab.get("source") == "human":
            return lab
    return labels[0]


def load(labels_dir: Path) -> list[dict]:
    items = []
    for fp in sorted(glob.glob(str(labels_dir / "*.json"))):
        rec = json.loads(Path(fp).read_text())
        lab = chosen_label(rec)
        if lab is None or lab.get("source") not in OK_SOURCES or not lab.get("primary_issue"):
            continue
        px = rec.get("proxies") or {}
        if px.get(DENSITY_KEY) is None:
            continue
        run_dir = rec.get("run_dir") or ""
        png = rec.get("png_path") or (str(Path(run_dir) / "pptx" / "iter_1.png") if run_dir else "")
        items.append(
            {
                "run_id": rec.get("run_id"),
                "title": (rec.get("paper_title") or "")[:46],
                "template": rec.get("template"),
                "vlm_primary": lab.get("primary_issue"),
                "vlm_secondary": ";".join(lab.get("secondary_issues") or []),
                "mean_chars_per_panel": px.get("mean_chars_per_panel"),
                "max_chars_per_panel": px.get("max_chars_per_panel"),
                "mean_bullets_per_panel": px.get("mean_bullets_per_panel"),
                "figure_usage_ratio": px.get("figure_usage_ratio"),
                "png_path": png,
            }
        )
    return items


def density_pct(value: float, pool: list[float]) -> float:
    below = sum(1 for v in pool if v < value)
    return round(100.0 * below / len(pool), 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels-dir", default="experiments/results/audit/labels")
    ap.add_argument("--out", default="experiments/results/audit/human_gold_subset.csv")
    ap.add_argument("--n", type=int, default=12, help="evenly-spaced picks before force-includes")
    args = ap.parse_args()

    items = load(Path(args.labels_dir))
    ranked = sorted(items, key=lambda r: r["mean_chars_per_panel"])
    pool = [r["mean_chars_per_panel"] for r in ranked]
    N = len(ranked)

    # Evenly-spaced picks across the density range (deterministic, no RNG).
    k = min(args.n, N)
    base_idx = sorted({round(i * (N - 1) / (k - 1)) for i in range(k)})
    picked = {ranked[i]["run_id"]: ranked[i] for i in base_idx}

    by_id = {r["run_id"]: r for r in ranked}
    # Force-include the BLIP poster the user flagged.
    if BLIP_RUN_ID in by_id:
        picked.setdefault(BLIP_RUN_ID, by_id[BLIP_RUN_ID])
    # Force-include up to 3 visual_hierarchy_weak-primary posters for contrast.
    vhw = [r for r in ranked if r["vlm_primary"] == VHW]
    for r in vhw[:3]:
        picked.setdefault(r["run_id"], r)

    final = sorted(picked.values(), key=lambda r: r["mean_chars_per_panel"])

    cols = [
        "pick_idx", "run_id", "paper_title", "template",
        "vlm_primary", "vlm_secondary",
        "mean_chars_per_panel", "max_chars_per_panel", "mean_bullets_per_panel",
        "figure_usage_ratio", "density_pct",
        "human_overload", "human_primary", "human_notes",
        "png_path",
    ]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i, r in enumerate(final, 1):
            w.writerow([
                i, r["run_id"], r["title"], r["template"],
                r["vlm_primary"], r["vlm_secondary"],
                r["mean_chars_per_panel"], r["max_chars_per_panel"], r["mean_bullets_per_panel"],
                r["figure_usage_ratio"], density_pct(r["mean_chars_per_panel"], pool),
                "", "", "",          # <- USER FILLS these three
                r["png_path"],
            ])

    print(f"[human-gold] selected {len(final)} of {N} posters spanning "
          f"{DENSITY_KEY} {min(pool):.0f}..{max(pool):.0f}")
    print(f"[human-gold] wrote {out}")
    print()
    print("FILL THESE COLUMNS (open each png_path):")
    print("  human_overload : yes | borderline | no   (is text density a REAL problem at viewing distance?)")
    print("  human_primary  : optional — the ONE issue you'd call primary (any of the 5 classes / none)")
    print("  human_notes    : optional free text")
    print()
    print(f"{'idx':>3}  {'dens%':>5}  {'vlm_primary':<22}  {'mean_ch':>7}  png")
    for i, r in enumerate(final, 1):
        print(f"{i:>3}  {density_pct(r['mean_chars_per_panel'], pool):>5}  "
              f"{r['vlm_primary']:<22}  {r['mean_chars_per_panel']:>7}  {r['png_path']}")


if __name__ == "__main__":
    main()
