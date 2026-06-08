#!/usr/bin/env python3
"""Figure for the text_overload validity argument (P0 audit).

Two panels:
  (a) local text density (chars/cm^2) by VLM primary class -> heavy overlap, BLIP starred,
      annotation that body font is constant 8.8pt across all 47.
  (b) scatter of LOCAL density (chars/cm^2) vs GLOBAL volume (# text blocks), colored by VLM
      primary, BLIP starred -> shows text_overload bundles two different constructs.

Zero API. Reuses extract_geom from analysis_text_overload_geometry.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root → runnable via path or -m

from experiments.scripts.analysis_text_overload_geometry import (
    chosen_label, extract_geom, OK_SOURCES,
)

BLIP = "44a0517194a2"
ORDER = ["text_overload", "visual_hierarchy_weak", "asset_utilization_error"]
SHORT = {"text_overload": "text_overload", "visual_hierarchy_weak": "visual_hierarchy_weak",
         "asset_utilization_error": "asset_util_error"}
COL = {"text_overload": "#d1495b", "visual_hierarchy_weak": "#2e86ab",
       "asset_utilization_error": "#8d99ae"}


def main() -> None:
    recs = []
    for fp in sorted(glob.glob("experiments/results/audit/labels/*.json")):
        rec = json.loads(Path(fp).read_text())
        lab = chosen_label(rec)
        if not lab or lab.get("source") not in OK_SOURCES or not lab.get("primary_issue"):
            continue
        rd = rec.get("run_dir") or ""
        p = Path(rd) / "pptx" / "iter_1.pptx"
        g = extract_geom(p) if p.exists() else None
        if not g or g.get("chars_per_cm2_median") is None:
            continue
        recs.append({
            "run_id": rec["run_id"],
            "primary": lab["primary_issue"],
            "dens": g["chars_per_cm2_median"],
            "nbox": g["n_content_boxes"],
        })
    b = next(r for r in recs if r["run_id"] == BLIP)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6))

    # ---- panel (a): density by class ----
    for gi, cls in enumerate(ORDER):
        ys = [r["dens"] for r in recs if r["primary"] == cls]
        xs = gi + (np.linspace(-0.18, 0.18, len(ys)) if len(ys) > 1 else np.array([0.0]))
        ax1.scatter(xs, ys, c=COL[cls], s=30, alpha=0.85, edgecolors="white",
                    linewidths=0.5, zorder=3)
        if ys:
            med = float(np.median(ys))
            ax1.plot([gi - 0.28, gi + 0.28], [med, med], color=COL[cls], lw=2.5, zorder=4)
    ax1.scatter([ORDER.index(b["primary"])], [b["dens"]], marker="*", s=340, c="gold",
                edgecolors="black", linewidths=1.0, zorder=5)
    ax1.set_xticks(range(len(ORDER)))
    ax1.set_xticklabels([SHORT[c] for c in ORDER], rotation=12, fontsize=8)
    ax1.set_ylabel("LOCAL text density  (chars / cm²)")
    ax1.set_title("(a) density does not separate the classes\n"
                  "AUC(text_overload > vhw) = 0.65   (0.50 = chance)", fontsize=9)
    ax1.text(0.03, 0.04, "rendered body font = 8.8 pt for ALL 47 posters (σ = 0)\n"
                         "→ font/local density are renderer constants",
             transform=ax1.transAxes, fontsize=7.3, style="italic", color="#444")

    # ---- panel (b): two constructs ----
    for cls in ORDER:
        pts = [r for r in recs if r["primary"] == cls]
        ax2.scatter([r["dens"] for r in pts], [r["nbox"] for r in pts], c=COL[cls], s=32,
                    alpha=0.85, edgecolors="white", linewidths=0.5, label=SHORT[cls], zorder=3)
    ax2.scatter([b["dens"]], [b["nbox"]], marker="*", s=340, c="gold", edgecolors="black",
                linewidths=1.0, zorder=5, label="BLIP (expert: 'just full')")
    ax2.set_xlabel("LOCAL density  (chars / cm²)   →  what the expert judged")
    ax2.set_ylabel("GLOBAL volume  (# text blocks)   →  what the VLM reacted to")
    ax2.set_title("(b) 'text_overload' bundles two constructs", fontsize=9)
    ax2.legend(fontsize=7, loc="lower right", framealpha=0.9)
    ax2.annotate("low local density (38th pct)\nbut high block count (79th pct)",
                 xy=(b["dens"], b["nbox"]), xytext=(b["dens"] + 0.4, b["nbox"] - 6),
                 fontsize=7.2, arrowprops=dict(arrowstyle="->", color="black", lw=0.8))

    fig.suptitle("Is 'text_overload' a real failure or a VLM prior?  "
                 "(47 posters, P0 audit)", fontsize=11, y=1.02)
    fig.tight_layout()
    out = Path("experiments/results/audit/figures/text_overload_validity.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"wrote {out}")
    print(f"BLIP: local_density={b['dens']}  n_blocks={b['nbox']}  class={b['primary']}")
    for cls in ORDER:
        n = sum(1 for r in recs if r["primary"] == cls)
        print(f"  {cls:<24} n={n}")


if __name__ == "__main__":
    main()
