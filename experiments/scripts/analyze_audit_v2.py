"""Phase 4: analyze audit v2.

Combine human gold (annotatorA, with annotatorB for reliability), the VLM labels
(direct + narrowed), and the geom rules, then compute the full metric panel and
emit the S1/S2/S3 verdict + AUDIT_V2_FINDINGS.md.

Gold = annotatorA's primary label (the user's design-informed labels). A/B
Cohen's kappa is reported as inter-annotator reliability and disagreements are
listed for adjudication. Verdict thresholds follow AUDIT_V2_REGROUND_SPEC.md §6;
classes with gold support < MIN_SUPPORT are reported but excluded from the
reliable/blind verdict logic (small-sample guard).
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from experiments.audit.taxonomy import REAL_ISSUES
from experiments.audit.metrics_v2 import (
    cohen_kappa, confusion_matrix, per_class_prf, macro_recall,
    label_entropy, top1_share, prior_baseline_acc, false_positive_rate,
)

REPO = Path(__file__).resolve().parents[2]
GOLD_DIR = REPO / "datasets" / "gold"
OUT = REPO / "experiments" / "results" / "audit_v2_new60"
LABELS = REAL_ISSUES + ["none", "other"]
MIN_SUPPORT = 8


def _load_csv(p: Path) -> dict:
    return {
        r["run_folder"]: (r.get("primary_issue") or "").strip()
        for r in csv.DictReader(p.open(encoding="utf-8"))
        if (r.get("primary_issue") or "").strip()
    }


def _load_vlm(p: Path) -> dict:
    # label_poster stores the run folder under "run_id"
    return {x["run_id"]: x["primary_issue"] for x in json.loads(p.read_text(encoding="utf-8"))}


def _acc(gold, pred) -> float:
    return round(sum(1 for g, p in zip(gold, pred) if g == p) / len(gold), 3) if gold else 0.0


def _verdict(prf, kappa_vg, acc_vlm, acc_prior, t1):
    supported = {c: m for c, m in prf.items() if m["support"] >= MIN_SUPPORT}
    rmac = macro_recall(supported, only_supported=False) if supported else 0.0
    reliable = [c for c, m in supported.items() if m["recall"] >= 0.70]
    blind = [c for c, m in supported.items() if m["recall"] <= 0.30]
    kvg = kappa_vg or 0.0
    s2 = rmac >= 0.70 and kvg >= 0.60 and (acc_vlm - acc_prior) >= 0.15
    s1 = (acc_vlm <= acc_prior + 0.05 or kvg < 0.20) and t1 >= 0.5
    s3 = bool(reliable) and bool(blind)
    verdict = "S2" if s2 else ("S1" if s1 else ("S3" if s3 else "inconclusive"))
    # S1 and S3 can co-hold; report both, lead with S1 if VLM is at/below prior.
    return {
        "verdict": verdict, "S1_unreliable": s1, "S2_reliable": s2, "S3_routed": s3,
        "macro_recall_supported": rmac, "reliable_classes": reliable, "blind_classes": blind,
        "supported_classes": list(supported),
    }


def _variant(name, gold_map, vlm_map):
    runs = [r for r in gold_map if r in vlm_map]
    gold = [gold_map[r] for r in runs]
    pred = [vlm_map[r] for r in runs]
    prf = per_class_prf(gold, pred, LABELS)
    acc_vlm = _acc(gold, pred)
    acc_prior = prior_baseline_acc(gold)
    kvg = cohen_kappa(gold, pred)
    res = {
        "variant": name, "n": len(runs),
        "vlm_distribution": dict(Counter(pred)),
        "accuracy": acc_vlm, "prior_baseline_acc": acc_prior,
        "kappa_vlm_gold": (round(kvg, 3) if kvg is not None else None),
        "vlm_label_entropy": label_entropy(pred), "vlm_top1_share": top1_share(pred),
        "none_recall": prf["none"]["recall"],
        "fp_rate_space_imbalance": false_positive_rate(gold, pred, "space_imbalance"),
        "fp_rate_text_overload": false_positive_rate(gold, pred, "text_overload"),
        "per_class": prf,
        "confusion": confusion_matrix(gold, pred, LABELS),
    }
    res["verdict"] = _verdict(prf, kvg, acc_vlm, acc_prior, res["vlm_top1_share"])
    return res


def main() -> int:
    A = _load_csv(GOLD_DIR / "audit_v2_labels_annotatorA.csv")
    B = _load_csv(GOLD_DIR / "audit_v2_labels_annotatorB.csv")
    direct = _load_vlm(OUT / "vlm_qwen32b_direct.json")
    narrowed = _load_vlm(OUT / "vlm_qwen32b_narrowed.json")
    geom = {g["run_folder"]: g for g in json.loads((OUT / "geom_rules.json").read_text(encoding="utf-8"))}

    runs = sorted(A)
    gold = [A[r] for r in runs]

    # inter-annotator
    common = [r for r in runs if r in B]
    ab_kappa = cohen_kappa([A[r] for r in common], [B[r] for r in common])
    disagreements = [(r, A[r], B[r]) for r in common if A[r] != B[r]]

    # per-template gold
    tmpl = {g["run_folder"]: g["template"] for g in geom.values()}
    by_tmpl = {}
    for r in runs:
        t = tmpl.get(r, "?")
        by_tmpl.setdefault(t, Counter())[A[r]] += 1

    dv = _variant("direct", A, direct)
    nv = _variant("narrowed", A, narrowed)

    kappa_out = {"annotatorA_vs_B": (round(ab_kappa, 3) if ab_kappa is not None else None),
                 "n_common": len(common), "n_disagreements": len(disagreements),
                 "disagreements": [{"run": r, "A": a, "B": b} for r, a, b in disagreements]}
    (OUT / "kappa.json").write_text(json.dumps(kappa_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "confusion_matrix.json").write_text(
        json.dumps({"direct": dv["confusion"], "narrowed": nv["confusion"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "per_issue_table.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["variant", "class", "precision", "recall", "f1", "gold_support"])
        for res in (dv, nv):
            for c in LABELS:
                m = res["per_class"][c]
                w.writerow([res["variant"], c, m["precision"], m["recall"], m["f1"], m["support"]])

    _write_findings(gold, by_tmpl, kappa_out, dv, nv, geom)
    print(f"[analyze] verdict: direct={dv['verdict']['verdict']}  narrowed={nv['verdict']['verdict']}")
    print(f"[analyze] wrote AUDIT_V2_FINDINGS.md + 3 artifacts to {OUT}")
    return 0


def _write_findings(gold, by_tmpl, kappa_out, dv, nv, geom):
    gdist = Counter(gold)
    overlap_nz = sum(1 for g in geom.values() if (g["overlap_count"] or 0) > 0)
    contrast_ok = all(g["contrast"]["ok"] for g in geom.values() if g["contrast"])
    lines = []
    L = lines.append
    L("# Audit v2 (new60) — Findings\n")
    L(f"> Gold = annotatorA (user). Inter-annotator A/B κ = **{kappa_out['annotatorA_vs_B']}** "
      f"({kappa_out['n_common']} common, {kappa_out['n_disagreements']} disagreements).\n")
    L("## Gold distribution (human)\n")
    L("| class | n |\n|---|---|")
    for c in LABELS:
        if gdist.get(c):
            L(f"| {c} | {gdist[c]} |")
    L("\n**Per template (gold):**\n")
    for t, cnt in by_tmpl.items():
        L(f"- `{t}`: {dict(cnt)}")
    L("\n## Objective geom rules\n")
    L(f"- contrast: all themes WCAG-AA = **{contrast_ok}** → any VLM `low_contrast` is a false positive.")
    L(f"- overlap: {overlap_nz}/60 posters have ≥1 partial collision (rest clean).\n")
    L("## VLM vs gold\n")
    L("| metric | direct | narrowed |\n|---|---|---|")
    for k, lab in [("accuracy", "accuracy"), ("prior_baseline_acc", "prior baseline"),
                   ("kappa_vlm_gold", "κ(VLM,gold)"), ("vlm_top1_share", "VLM top-1 share"),
                   ("vlm_label_entropy", "VLM label entropy"), ("none_recall", "recall(none)"),
                   ("fp_rate_space_imbalance", "FP rate space_imbalance"),
                   ("fp_rate_text_overload", "FP rate text_overload")]:
        L(f"| {lab} | {dv[k]} | {nv[k]} |")
    L("\n**Per-class recall (VLM vs gold):**\n")
    L("| class | gold_support | recall(direct) | recall(narrowed) |\n|---|---|---|---|")
    for c in LABELS:
        s = dv["per_class"][c]["support"]
        if s:
            L(f"| {c} | {s} | {dv['per_class'][c]['recall']} | {nv['per_class'][c]['recall']} |")
    L("\n## Verdict\n")
    for res in (dv, nv):
        v = res["verdict"]
        L(f"- **{res['variant']}: {v['verdict']}** — S1={v['S1_unreliable']} S2={v['S2_reliable']} S3={v['S3_routed']}; "
          f"reliable={v['reliable_classes']} blind={v['blind_classes']} (support≥{MIN_SUPPORT})")
    if kappa_out["disagreements"]:
        L("\n## A/B disagreements (for adjudication)\n")
        for d in kappa_out["disagreements"]:
            L(f"- `{d['run'][:46]}` A={d['A']} B={d['B']}")
    (OUT.parent.parent.parent / "AUDIT_V2_FINDINGS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
