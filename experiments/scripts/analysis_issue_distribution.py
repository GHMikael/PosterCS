"""P0 analysis: issue distribution across the audited initial posters.

Reads the per-poster label files written by ``audit_label_posters.py`` and
produces:

* ``analysis_issue_distribution.json`` — primary/secondary distribution over
  the new 5 classes (+ ``other``/``none``), guard trigger rates, and the legacy
  4-class frequencies mined from the old run reports (the evidence that
  ``overlapping_elements`` / ``low_contrast`` are low-frequency → guards);
* ``figures/issue_distribution.png`` — a bar chart of the above.

Pure analysis: no network, no API. The chart degrades gracefully if matplotlib
is unavailable (the JSON is the real deliverable).

Usage::

    .venv/bin/python -m experiments.scripts.analysis_issue_distribution
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from experiments.audit.taxonomy import (
    GUARD_VALUES,
    OLD_ISSUE_VALUES,
    PRIMARY_ISSUE_VALUES,
    REAL_ISSUES,
    SECONDARY_ISSUE_VALUES,
    map_old_issue,
)

#: VLM sources we trust as a real label (others are failures, counted apart).
_OK_SOURCES = {"vlm", "vlm_partial", "human"}


def load_labels(labels_dir: Path) -> List[Dict[str, Any]]:
    """Load every per-poster label record from ``labels_dir``."""

    labels_dir = Path(labels_dir)
    records: List[Dict[str, Any]] = []
    for fp in sorted(labels_dir.glob("*.json")):
        try:
            records.append(json.loads(fp.read_text(encoding="utf-8")))
        except Exception:
            continue
    return records


def chosen_label(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pick the preferred label track for a poster: pass-0 with an OK source."""

    for lab in record.get("labels", []) or []:
        if lab.get("source") in _OK_SOURCES:
            return lab
    return None


def _ordered(counter: Counter, order: List[str]) -> Dict[str, int]:
    """Counter → dict in a fixed key order, including zero entries."""

    return {k: int(counter.get(k, 0)) for k in order}


def aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute the full distribution payload from label records."""

    n_total = len(records)
    primary = Counter()
    secondary = Counter()
    presence = Counter()          # issue appears as primary OR secondary
    guards = Counter()
    by_template: Dict[str, Counter] = {}
    old_raw = Counter()           # legacy 4-class strings on initial posters
    old_mapped = Counter()        # mapped onto the new vocabulary
    n_ok = 0
    failed_sources = Counter()

    for rec in records:
        # Legacy issue mining is independent of VLM success.
        for oi in rec.get("old_issues_initial", []) or []:
            old_raw[oi] += 1
            old_mapped[map_old_issue(oi)["maps_to"]] += 1

        lab = chosen_label(rec)
        if lab is None:
            # record the failure reason from the first label, if any
            labs = rec.get("labels", []) or []
            failed_sources[(labs[0].get("source") if labs else "missing")] += 1
            continue

        n_ok += 1
        p = lab.get("primary_issue", "none")
        primary[p] += 1
        presence[p] += 1
        tmpl = rec.get("template", "") or "unknown"
        by_template.setdefault(tmpl, Counter())[p] += 1
        for s in lab.get("secondary_issues", []) or []:
            secondary[s] += 1
            presence[s] += 1
        for g in lab.get("guard_violations", []) or []:
            guards[g] += 1

    def share(counter: Counter, order: List[str]) -> Dict[str, float]:
        return {k: round(counter.get(k, 0) / n_ok, 3) if n_ok else 0.0 for k in order}

    # Low-frequency evidence: how much of the legacy mentions are overlap/contrast.
    old_total = sum(old_raw.values())
    low_freq_legacy = old_raw.get("overlapping_elements", 0) + old_raw.get("low_contrast", 0)

    return {
        "n_posters": n_total,
        "n_labeled_ok": n_ok,
        "n_failed": n_total - n_ok,
        "failed_sources": dict(failed_sources),
        "distinct_papers": len({(r.get("paper_title") or r.get("run_id")) for r in records}),
        "primary_distribution": _ordered(primary, PRIMARY_ISSUE_VALUES),
        "primary_share": share(primary, PRIMARY_ISSUE_VALUES),
        "secondary_distribution": _ordered(secondary, SECONDARY_ISSUE_VALUES),
        "presence_distribution": _ordered(presence, PRIMARY_ISSUE_VALUES),
        "guard_trigger_counts": _ordered(guards, GUARD_VALUES),
        "guard_trigger_rate": {k: (round(guards.get(k, 0) / n_ok, 3) if n_ok else 0.0) for k in GUARD_VALUES},
        "legacy_issue_counts": _ordered(old_raw, OLD_ISSUE_VALUES),
        "legacy_mapped_to_new": dict(old_mapped),
        "legacy_low_freq_check": {
            "overlap_plus_contrast": int(low_freq_legacy),
            "legacy_total_mentions": int(old_total),
            "low_freq_share": round(low_freq_legacy / old_total, 3) if old_total else 0.0,
            "reading": "Low share ⇒ overlap/contrast are rare ⇒ demoting them to guards is justified.",
        },
        "by_template_primary": {t: _ordered(c, PRIMARY_ISSUE_VALUES) for t, c in sorted(by_template.items())},
    }


def plot(agg: Dict[str, Any], out_png: Path) -> Optional[Path]:
    """Bar chart: new-taxonomy primary distribution + legacy issue counts."""

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # matplotlib missing → skip chart, keep JSON
        print(f"[analysis_issue_distribution] chart skipped (matplotlib unavailable: {exc})")
        return None

    try:
        from experiments.scripts.plot_figures import _style
        _style()
    except Exception:
        pass

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))

    # Left: new 5-class (+other/none) primary distribution.
    keys1 = PRIMARY_ISSUE_VALUES
    vals1 = [agg["primary_distribution"][k] for k in keys1]
    ax1.bar(range(len(keys1)), vals1, color="#0056b3")
    ax1.set_xticks(range(len(keys1)))
    ax1.set_xticklabels([k.replace("_", "\n") for k in keys1], rotation=0, fontsize=8)
    ax1.set_title(f"New taxonomy — primary issue (n={agg['n_labeled_ok']})")
    ax1.set_ylabel("posters")
    for i, v in enumerate(vals1):
        if v:
            ax1.text(i, v, str(v), ha="center", va="bottom", fontsize=8)

    # Right: legacy 4-class counts (overlap/contrast expected low).
    keys2 = OLD_ISSUE_VALUES
    vals2 = [agg["legacy_issue_counts"][k] for k in keys2]
    ax2.bar(range(len(keys2)), vals2, color="#ea580c")
    ax2.set_xticks(range(len(keys2)))
    ax2.set_xticklabels([k.replace("_", "\n") for k in keys2], rotation=0, fontsize=8)
    ax2.set_title("Legacy 4-class on initial posters")
    ax2.set_ylabel("mentions")
    for i, v in enumerate(vals2):
        if v:
            ax2.text(i, v, str(v), ha="center", va="bottom", fontsize=8)

    fig.tight_layout()
    fig.savefig(out_png)
    fig.savefig(out_png.with_suffix(".pdf"))
    plt.close(fig)
    return out_png


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="P0: aggregate audit issue distribution.")
    p.add_argument("--labels-dir", type=Path, default=Path("experiments/results/audit/labels"))
    p.add_argument("--out", type=Path, default=Path("experiments/results/audit"))
    args = p.parse_args(argv)

    records = load_labels(args.labels_dir)
    if not records:
        print(f"[analysis_issue_distribution] no label files in {args.labels_dir}; run audit_label_posters first.")
        return 2

    agg = aggregate(records)
    args.out.mkdir(parents=True, exist_ok=True)
    out_json = args.out / "analysis_issue_distribution.json"
    out_json.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analysis_issue_distribution] {agg['n_labeled_ok']}/{agg['n_posters']} posters labeled OK")
    print(f"[analysis_issue_distribution] primary share: "
          + ", ".join(f"{k}={agg['primary_share'][k]}" for k in REAL_ISSUES))
    print(f"[analysis_issue_distribution] legacy low-freq share (overlap+contrast): "
          f"{agg['legacy_low_freq_check']['low_freq_share']}")
    plot(agg, args.out / "figures" / "issue_distribution.png")
    print(f"[analysis_issue_distribution] wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
