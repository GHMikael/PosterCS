"""P0 analysis: MECE audit of the new issue taxonomy.

Answers the questions v4 §8.4 needs before any code is rewritten:

* **coverage** — of the posters that have a real failure, how many are covered
  by one of the 5 classes (vs ``other``)?
* **other_rate** — share of failures the taxonomy could not classify;
* **multi_label_rate** — share of posters with more than one issue;
* **inter-annotator agreement** — Cohen's κ between two label tracks, when
  available (VLM pass-0 vs pass-1, and/or VLM vs a filled human gold CSV);
* a printed **PASS/FAIL verdict** against v4's criteria (coverage high,
  ``other_rate < 10%``, legacy overlap/contrast low-frequency).

Pure analysis (reuses the loaders from ``analysis_issue_distribution``); no API.

Usage::

    .venv/bin/python -m experiments.scripts.analysis_issue_mece_audit
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from experiments.audit.taxonomy import PRIMARY_ISSUE_VALUES, REAL_ISSUES, AuditIssueType
from experiments.scripts.analysis_issue_distribution import aggregate, chosen_label, load_labels

_NONE = AuditIssueType.NONE.value
_OTHER = AuditIssueType.OTHER.value


def cohen_kappa(pairs: List[Tuple[str, str]], categories: List[str]) -> Optional[float]:
    """Cohen's κ for two raters over a fixed category set (pure Python)."""

    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    pe = sum((ca.get(c, 0) / n) * (cb.get(c, 0) / n) for c in categories)
    if math.isclose(pe, 1.0):
        return 1.0
    return round((po - pe) / (1.0 - pe), 3)


def _read_human_gold(csv_path: Path) -> Dict[str, str]:
    """run_id → human_primary, for rows where a human filled in a primary."""

    gold: Dict[str, str] = {}
    if not csv_path.exists():
        return gold
    try:
        with csv_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                hp = (row.get("human_primary") or "").strip().lower()
                rid = (row.get("run_id") or "").strip()
                if rid and hp in PRIMARY_ISSUE_VALUES:
                    gold[rid] = hp
    except Exception:
        pass
    return gold


def _agreement_tracks(records: List[Dict[str, Any]], gold: Dict[str, str]) -> Dict[str, Any]:
    """Build κ for VLM-pass0-vs-pass1 and VLM-vs-human, when each is available."""

    pass_pairs: List[Tuple[str, str]] = []
    human_pairs: List[Tuple[str, str]] = []

    for rec in records:
        labs = rec.get("labels", []) or []
        ok = [l for l in labs if l.get("source") in {"vlm", "vlm_partial", "human"}]
        if ok:
            p0 = ok[0].get("primary_issue", _NONE)
            if len(ok) >= 2:
                pass_pairs.append((p0, ok[1].get("primary_issue", _NONE)))
            rid = rec.get("run_id", "")
            if rid in gold:
                human_pairs.append((p0, gold[rid]))

    def track(pairs: List[Tuple[str, str]]) -> Optional[Dict[str, Any]]:
        if not pairs:
            return None
        n = len(pairs)
        raw = round(sum(1 for a, b in pairs if a == b) / n, 3)
        return {"n": n, "raw_agreement": raw, "cohen_kappa": cohen_kappa(pairs, PRIMARY_ISSUE_VALUES)}

    return {
        "vlm_pass0_vs_pass1": track(pass_pairs),
        "vlm_vs_human": track(human_pairs),
    }


def audit(records: List[Dict[str, Any]], gold: Dict[str, str],
          *, coverage_min: float, other_rate_max: float, legacy_lowfreq_max: float) -> Dict[str, Any]:
    agg = aggregate(records)
    n_ok = agg["n_labeled_ok"]

    primary = [chosen_label(r).get("primary_issue", _NONE) for r in records if chosen_label(r)]
    failures = [p for p in primary if p != _NONE]
    n_fail = len(failures)
    covered = sum(1 for p in failures if p in REAL_ISSUES)
    other = sum(1 for p in failures if p == _OTHER)

    multi = sum(
        1 for r in records
        if chosen_label(r) and (chosen_label(r).get("secondary_issues") or [])
    )

    coverage = round(covered / n_fail, 3) if n_fail else None
    other_rate = round(other / n_fail, 3) if n_fail else None
    multi_rate = round(multi / n_ok, 3) if n_ok else None

    legacy = agg["legacy_low_freq_check"]
    agreement = _agreement_tracks(records, gold)

    coverage_pass = coverage is not None and coverage >= coverage_min
    other_pass = other_rate is not None and other_rate <= other_rate_max
    legacy_pass = legacy["low_freq_share"] <= legacy_lowfreq_max
    # Soft check: space_imbalance (new home of empty_space) actually used.
    space_share = agg["primary_share"].get("space_imbalance", 0.0)

    return {
        "n_posters": agg["n_posters"],
        "n_labeled_ok": n_ok,
        "n_failures": n_fail,
        "coverage": coverage,
        "other_rate": other_rate,
        "multi_label_rate": multi_rate,
        "primary_distribution": agg["primary_distribution"],
        "primary_share": agg["primary_share"],
        "space_imbalance_share": space_share,
        "agreement": agreement,
        "legacy_low_freq_check": legacy,
        "criteria": {
            "coverage_min": coverage_min,
            "other_rate_max": other_rate_max,
            "legacy_lowfreq_max": legacy_lowfreq_max,
        },
        "verdict": {
            "coverage_pass": bool(coverage_pass),
            "other_rate_pass": bool(other_pass),
            "legacy_lowfreq_pass": bool(legacy_pass),
            "overall_pass": bool(coverage_pass and other_pass and legacy_pass),
        },
    }


def _print_verdict(res: Dict[str, Any]) -> None:
    v = res["verdict"]
    def mark(b: bool) -> str:
        return "PASS" if b else "FAIL"
    print(f"[analysis_issue_mece_audit] failures={res['n_failures']} / ok={res['n_labeled_ok']} / total={res['n_posters']}")
    print(f"  coverage          = {res['coverage']}  (>= {res['criteria']['coverage_min']}?)  -> {mark(v['coverage_pass'])}")
    print(f"  other_rate        = {res['other_rate']}  (<= {res['criteria']['other_rate_max']}?)  -> {mark(v['other_rate_pass'])}")
    print(f"  legacy low-freq   = {res['legacy_low_freq_check']['low_freq_share']}  (<= {res['criteria']['legacy_lowfreq_max']}?)  -> {mark(v['legacy_lowfreq_pass'])}")
    print(f"  multi_label_rate  = {res['multi_label_rate']}")
    print(f"  space_imbalance   = {res['space_imbalance_share']} (empty_space's new home)")
    ag = res["agreement"]
    if ag.get("vlm_pass0_vs_pass1"):
        t = ag["vlm_pass0_vs_pass1"]
        print(f"  κ(pass0,pass1)    = {t['cohen_kappa']} (n={t['n']}, raw={t['raw_agreement']})")
    if ag.get("vlm_vs_human"):
        t = ag["vlm_vs_human"]
        print(f"  κ(vlm,human)      = {t['cohen_kappa']} (n={t['n']}, raw={t['raw_agreement']})")
    if not ag.get("vlm_pass0_vs_pass1") and not ag.get("vlm_vs_human"):
        print("  agreement (κ)     = N/A (single track; rerun with --passes 2 or fill the human CSV)")
    print(f"  OVERALL           -> {mark(v['overall_pass'])}")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="P0: MECE audit of the new issue taxonomy.")
    p.add_argument("--labels-dir", type=Path, default=Path("experiments/results/audit/labels"))
    p.add_argument("--out", type=Path, default=Path("experiments/results/audit"))
    p.add_argument("--human-csv", type=Path, default=Path("experiments/results/audit/human_label_template.csv"))
    p.add_argument("--coverage-min", type=float, default=0.80)
    p.add_argument("--other-rate-max", type=float, default=0.10)
    p.add_argument("--legacy-lowfreq-max", type=float, default=0.25)
    args = p.parse_args(argv)

    records = load_labels(args.labels_dir)
    if not records:
        print(f"[analysis_issue_mece_audit] no label files in {args.labels_dir}; run audit_label_posters first.")
        return 2

    gold = _read_human_gold(args.human_csv)
    res = audit(
        records, gold,
        coverage_min=args.coverage_min,
        other_rate_max=args.other_rate_max,
        legacy_lowfreq_max=args.legacy_lowfreq_max,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    out_json = args.out / "analysis_issue_mece_audit.json"
    out_json.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_verdict(res)
    print(f"[analysis_issue_mece_audit] wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
