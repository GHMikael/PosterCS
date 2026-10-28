#!/usr/bin/env python3
"""Select interpretable RuleDev thresholds and freeze rule_v1.

The candidate grids are intentionally finite and mirrored in
THRESHOLD_SELECTION_PROTOCOL_v1.md. Formal-88 is never read by this script.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from postercs_audit.paths import CONFIG_ROOT, DATA_ROOT, RESEARCH_ROOT, RESULTS_ROOT


HERE = Path(__file__).resolve().parent
RULEDEV = DATA_ROOT / "rule-development"
PAIRS_PATH = RULEDEV / "accepted-pairs.csv"
FEATURES_PATH = RULEDEV / "features" / "accepted-poster-features.csv"
PROTOCOL_PATH = RESEARCH_ROOT / "protocols" / "rule-calibration.md"
OUTPUT_DIR = RESULTS_ROOT / "rule-development"
MAX_CONTROL_FPR = 0.10


@dataclass(frozen=True)
class Detector:
    rule_id: str
    label: str
    track: str
    kind: str
    features: tuple[str, ...]
    candidates: tuple[dict[str, Any], ...]
    applicability: dict[str, Any] | None = None
    disabled_reason: str | None = None


def product_dict(**values: Iterable[Any]) -> tuple[dict[str, Any], ...]:
    keys = tuple(values)
    return tuple(dict(zip(keys, row)) for row in itertools.product(*(values[k] for k in keys)))


DETECTORS = (
    Detector("R1R", "body_text_too_small", "raster", "low",
             ("body_line_height_p25_px1080",),
             product_dict(positive_max=(8.0, 9.0, 10.0, 11.0, 12.0), negative_min=(14.0, 16.0, 18.0, 20.0))),
    Detector("R1S", "body_text_too_small", "source", "low",
             ("source_body_font_min_pt",),
             product_dict(positive_max=(7.0, 8.0, 9.0), negative_min=(10.0, 11.0, 12.0))),
    Detector("R2R", "figure_detail_unreadable", "raster", "disabled",
             ("ocr_line_count",), tuple(),
             disabled_reason="No validated raster figure localization; whole-poster OCR count is confounded by text volume."),
    Detector("R2S", "figure_detail_unreadable", "source", "low",
             ("source_picture_detail_p25_min_display_px",),
             product_dict(positive_max=(2.0, 2.5, 3.0, 3.5, 4.0), negative_min=(4.5, 5.0, 5.5)),
             applicability={"source_picture_count__min": 1}),
    Detector("R3R", "text_overload", "raster", "high",
             ("ocr_character_count",),
             product_dict(positive_min=(800, 850, 900, 950), negative_max=(700, 725, 750, 775))),
    Detector("R3S", "text_overload", "source", "high_all",
             ("source_character_count", "source_text_density_max"),
             product_dict(positive_min_0=(850, 900, 950), positive_min_1=(3500, 3750, 4000),
                          negative_max_0=(775, 800, 825), negative_max_1=(3250, 3350, 3450))),
    Detector("R4R", "space_imbalance", "raster", "high_all",
             ("foreground_left_right_abs_diff", "grid_occupancy_std"),
             product_dict(positive_min_0=(0.06, 0.07, 0.08, 0.09), positive_min_1=(0.20, 0.202, 0.204, 0.206),
                          negative_max_0=(0.03, 0.04, 0.05), negative_max_1=(0.20, 0.205, 0.21))),
    Detector("R4S", "space_imbalance", "source", "high_all",
             ("source_largest_empty_grid_rect_ratio", "source_content_left_right_abs_diff"),
             product_dict(positive_min_0=(0.06, 0.09, 0.12, 0.15), positive_min_1=(0.15, 0.20, 0.25, 0.30),
                          negative_max_0=(0.0, 0.03, 0.06), negative_max_1=(0.10, 0.12, 0.15))),
    Detector("R5R", "alignment_error", "raster", "high",
             ("large_panel_grid_alignment_max_residual_norm",),
             product_dict(positive_min=(0.018, 0.020, 0.022, 0.024), negative_max=(0.014, 0.016, 0.018)),
             applicability={"large_panel_candidate_count__min": 4, "large_panel_edges_in_clusters__min": 12}),
    Detector("R5S", "alignment_error", "source", "derived_named_panel_misalignment",
             ("source_named_panel_count", "source_named_panel_edges_in_clusters"),
             product_dict(positive_min=(0.04, 0.06, 0.08), negative_max=(0.0, 0.02, 0.04)),
             applicability={"source_named_panel_count__min": 4}),
    Detector("R6R", "overlap_or_clipping", "raster", "disabled",
             ("ellipsis_token_count", "edge_touching_ocr_word_count"), tuple(),
             disabled_reason="OCR ellipsis misses 5/6 mutations and fires once on a clean control; localized raster evidence is insufficient."),
    Detector("R6S", "overlap_or_clipping", "source", "binary_all",
             ("source_ellipsis_token_count", "source_content_overlap_pair_count"),
             ({"positive_min_0": 1, "positive_min_1": 1, "negative_max_0": 0, "negative_max_1": 0},)),
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def applicable(row: pd.Series, gate: dict[str, Any] | None) -> bool:
    if not gate:
        return True
    for key, threshold in gate.items():
        feature, op = key.rsplit("__", 1)
        value = row.get(feature)
        if not finite(value):
            return False
        if op == "min" and float(value) < float(threshold):
            return False
    return True


def decision(det: Detector, params: dict[str, Any] | None, row: pd.Series) -> tuple[str, float | None, dict[str, Any]]:
    evidence = {feature: None if not finite(row.get(feature)) else float(row[feature]) for feature in det.features}
    if det.kind == "disabled":
        return "abstain", None, evidence
    if not applicable(row, det.applicability):
        return "not_applicable", None, evidence
    if any(value is None for value in evidence.values()):
        return "abstain", None, evidence
    assert params is not None
    values = [evidence[f] for f in det.features]
    if det.kind == "derived_named_panel_misalignment":
        count, clustered = values
        risk_value = max(0.0, 1.0 - clustered / (4.0 * count))
        evidence["derived_unclustered_edge_ratio"] = risk_value
        values = [risk_value]
        kind = "high"
    else:
        kind = det.kind

    if kind == "low":
        value = values[0]
        pos, neg = float(params["positive_max"]), float(params["negative_min"])
        score = (neg - value) / max(neg - pos, 1e-9)
        verdict = "positive" if value <= pos else "negative" if value >= neg else "abstain"
    elif kind == "high":
        value = values[0]
        pos, neg = float(params["positive_min"]), float(params["negative_max"])
        score = (value - neg) / max(pos - neg, 1e-9)
        verdict = "positive" if value >= pos else "negative" if value <= neg else "abstain"
    elif kind in {"high_all", "binary_all"}:
        positive = all(value >= float(params[f"positive_min_{i}"]) for i, value in enumerate(values))
        negative = all(value <= float(params[f"negative_max_{i}"]) for i, value in enumerate(values))
        scores = [
            (value - float(params[f"negative_max_{i}"])) /
            max(float(params[f"positive_min_{i}"]) - float(params[f"negative_max_{i}"]), 1e-9)
            for i, value in enumerate(values)
        ]
        score = min(scores)
        verdict = "positive" if positive else "negative" if negative else "abstain"
    else:
        raise ValueError(f"Unknown detector kind: {kind}")
    return verdict, max(0.0, min(1.0, score)), evidence


def evaluate(det: Detector, params: dict[str, Any] | None, rows: pd.DataFrame) -> dict[str, Any]:
    decisions: dict[tuple[str, str], str] = {}
    for _, row in rows.iterrows():
        decisions[(row["pair_id"], row["variant"])] = decision(det, params, row)[0]
    pairs = sorted(rows["pair_id"].unique())
    controls = [decisions[(p, "control")] for p in pairs]
    mutations = [decisions[(p, "mutation")] for p in pairs]
    total = max(len(pairs), 1)
    non_abstain = {"positive", "negative"}
    return {
        "n_pairs": len(pairs),
        "pair_success_rate": sum(c == "negative" and m == "positive" for c, m in zip(controls, mutations)) / total,
        "mutation_positive_rate": sum(m == "positive" for m in mutations) / total,
        "mutation_negative_rate": sum(m == "negative" for m in mutations) / total,
        "control_negative_rate": sum(c == "negative" for c in controls) / total,
        "control_fpr": sum(c == "positive" for c in controls) / total,
        "coverage": sum(d in non_abstain for d in controls + mutations) / (2 * total),
        "abstention_rate": sum(d == "abstain" for d in controls + mutations) / (2 * total),
        "not_applicable_rate": sum(d == "not_applicable" for d in controls + mutations) / (2 * total),
    }


def conservative_key(det: Detector, params: dict[str, Any]) -> tuple[float, ...]:
    if det.kind == "low":
        return (-float(params["positive_max"]), float(params["negative_min"]))
    if det.kind in {"high", "derived_named_panel_misalignment"}:
        return (float(params["positive_min"]), -float(params["negative_max"]))
    if det.kind in {"high_all", "binary_all"}:
        pos = tuple(float(params[k]) for k in sorted(params) if k.startswith("positive_min"))
        neg = tuple(-float(params[k]) for k in sorted(params) if k.startswith("negative_max"))
        return pos + neg
    return tuple()


def choose(det: Detector, rows: pd.DataFrame) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if det.kind == "disabled":
        metrics = evaluate(det, None, rows)
        return None, metrics
    ranked = []
    for params in det.candidates:
        metrics = evaluate(det, params, rows)
        if metrics["control_fpr"] <= MAX_CONTROL_FPR:
            key = (
                metrics["pair_success_rate"],
                metrics["mutation_positive_rate"],
                metrics["control_negative_rate"],
                -metrics["mutation_negative_rate"],
                metrics["coverage"],
                conservative_key(det, params),
            )
            ranked.append((key, params, metrics))
    if not ranked:
        return None, evaluate(Detector(det.rule_id, det.label, det.track, "disabled", det.features, tuple()), None, rows)
    _, params, metrics = max(ranked, key=lambda item: item[0])
    return params, metrics


def main() -> None:
    pairs = pd.read_csv(PAIRS_PATH)
    features = pd.read_csv(FEATURES_PATH)
    expected_ids = set(pairs["pair_id"])
    actual_ids = set(features["pair_id"])
    if expected_ids != actual_ids or len(features) != 2 * len(pairs):
        raise RuntimeError("Frozen RuleDev pair/feature tables do not match.")

    candidate_log: dict[str, Any] = {
        "version": "candidate_thresholds_v1",
        "date": str(date.today()),
        "max_control_fpr": MAX_CONTROL_FPR,
        "formal88_used": False,
        "detectors": {},
    }
    cv_rows: list[dict[str, Any]] = []
    final_rules: dict[str, Any] = {}
    prediction_rows: list[dict[str, Any]] = []
    selected_by_rule: dict[str, dict[str, Any] | None] = {}

    for det in DETECTORS:
        pair_ids = list(pairs.loc[pairs["target_label"] == det.label, "pair_id"])
        rows = features.loc[features["pair_id"].isin(pair_ids)].copy()
        selected, full_metrics = choose(det, rows)
        selected_by_rule[det.rule_id] = selected

        candidate_entries = []
        for index, params in enumerate(det.candidates):
            metrics = evaluate(det, params, rows)
            candidate_entries.append({
                "candidate_id": f"{det.rule_id}-C{index + 1:03d}",
                "params": params,
                "metrics": metrics,
                "eligible": metrics["control_fpr"] <= MAX_CONTROL_FPR,
                "rejection_reason": None if metrics["control_fpr"] <= MAX_CONTROL_FPR else "control_fpr_above_0.10",
            })

        fold_metrics = []
        for held_out in pair_ids:
            train = rows.loc[rows["pair_id"] != held_out]
            test = rows.loc[rows["pair_id"] == held_out]
            fold_params, _ = choose(det, train)
            metrics = evaluate(det, fold_params, test)
            fold_metrics.append(metrics)
            cv_rows.append({
                "rule_id": det.rule_id,
                "label": det.label,
                "track": det.track,
                "fold": held_out,
                "selected_params": json.dumps(fold_params, sort_keys=True),
                **metrics,
            })
        lopo = {
            key: sum(float(m[key]) for m in fold_metrics) / len(fold_metrics)
            for key in ("pair_success_rate", "mutation_positive_rate", "mutation_negative_rate", "control_negative_rate",
                        "control_fpr", "coverage", "abstention_rate", "not_applicable_rate")
        }

        status = "disabled_abstain" if det.kind == "disabled" else "active"
        candidate_log["detectors"][det.rule_id] = {
            "label": det.label,
            "track": det.track,
            "status": status,
            "features": det.features,
            "candidate_count": len(det.candidates),
            "candidates": candidate_entries,
            "selected_params": selected,
            "disabled_reason": det.disabled_reason,
            "diagnostic_feature_ranges": {
                feature: {
                    variant: {
                        "min": float(rows.loc[rows["variant"] == variant, feature].min()),
                        "max": float(rows.loc[rows["variant"] == variant, feature].max()),
                    }
                    for variant in ("control", "mutation")
                }
                for feature in det.features
                if feature in rows and rows[feature].notna().any()
            },
            "full_metrics": full_metrics,
            "lopo_metrics": lopo,
        }
        final_rules[det.rule_id] = {
            "label": det.label,
            "track": det.track,
            "status": status,
            "kind": det.kind,
            "features": det.features,
            "applicability": det.applicability,
            "thresholds": selected,
            "disabled_reason": det.disabled_reason,
            "development_metrics": {"full": full_metrics, "lopo": lopo},
        }

        for _, row in rows.iterrows():
            verdict, risk, evidence = decision(det, selected, row)
            prediction_rows.append({
                "rule_id": det.rule_id,
                "label": det.label,
                "track": det.track,
                "pair_id": row["pair_id"],
                "sample_id": row["sample_id"],
                "variant": row["variant"],
                "decision": verdict,
                "risk_score": "" if risk is None else round(risk, 6),
                "severity": 2 if verdict == "positive" else "",
                "evidence": json.dumps(evidence, sort_keys=True),
            })

    rule_config = {
        "rule_version": "rule_v1",
        "date": str(date.today()),
        "input_resolution": {"width": 2400, "height": 1350, "normalized_height": 1080},
        "decision_schema": ["positive", "negative", "abstain", "not_applicable"],
        "development_data": "RuleDev accepted-pairs v1 (33 pairs / 66 images)",
        "formal88_used_for_tuning": False,
        "rules": final_rules,
        "deferred_labels": {
            "weak_hierarchy": "always_abstain",
            "asset_missing_or_broken": "not_calibrated_in_rule_v1",
            "other": "always_human_review",
        },
    }
    routing = {
        "version": "hybrid_routing_policy_v1",
        "status": "frozen_candidate_for_independent_hybrid_test",
        "formal88_role": "Model choice informed by prior benchmark; routing effectiveness is not claimed until Hybrid-Test.",
        "global": {
            "rule_positive": "accept when detector has localized/structural evidence, except figure readability which also needs VLM importance confirmation",
            "rule_abstain": "send to assigned VLM; preserve abstention if VLM lacks localized evidence",
            "rule_negative": "suppress same-label VLM allegation only for active high-coverage source rule; otherwise retain review path",
            "not_applicable": "VLM or human review; never map to none",
        },
        "routes": {
            "body_text_too_small": {"primary": "R1S_then_R1R", "borderline_vlm": "Gemini-P2"},
            "figure_detail_unreadable": {"primary": "R2S_scale_gate", "semantic_importance_vlm": "Gemini-P2", "raster_rule": "abstain"},
            "text_overload": {"primary": "R3S_then_R3R", "borderline_vlm": "Gemini-P2"},
            "space_imbalance": {"primary": "R4S_then_R4R", "borderline_vlm": "Qwen32B-P3"},
            "alignment_error": {"primary": "R5S_when_named_grid_else_R5R", "borderline_vlm": "Gemini-P2"},
            "overlap_or_clipping": {"primary": "R6S", "raster_fallback": "VLM_with_localized_evidence", "raster_rule": "abstain"},
            "weak_hierarchy": {"primary": "Gemini-P2", "rule": "abstain"},
            "asset_missing_or_broken": {"primary": "future_source_hard_failure_rule", "current": "human_review"},
            "other": {"primary": "human_review"},
        },
    }

    label_by_pair = dict(zip(pairs["pair_id"], pairs["target_label"]))
    all_prediction_rows: list[dict[str, Any]] = []
    cross_qa_rows: list[dict[str, Any]] = []
    for det in DETECTORS:
        det_predictions = []
        for _, row in features.iterrows():
            verdict, risk, evidence = decision(det, selected_by_rule[det.rule_id], row)
            truth = row["variant"] == "mutation" and label_by_pair[row["pair_id"]] == det.label
            record = {
                "rule_id": det.rule_id,
                "label": det.label,
                "track": det.track,
                "pair_id": row["pair_id"],
                "sample_id": row["sample_id"],
                "variant": row["variant"],
                "target_label": label_by_pair[row["pair_id"]],
                "is_target_positive": truth,
                "decision": verdict,
                "risk_score": "" if risk is None else round(risk, 6),
                "evidence": json.dumps(evidence, sort_keys=True),
            }
            det_predictions.append(record)
            all_prediction_rows.append(record)
        negatives = [r for r in det_predictions if not r["is_target_positive"]]
        positives = [r for r in det_predictions if r["is_target_positive"]]
        false_positives = [r for r in negatives if r["decision"] == "positive"]
        true_positives = [r for r in positives if r["decision"] == "positive"]
        cross_qa_rows.append({
            "rule_id": det.rule_id,
            "label": det.label,
            "track": det.track,
            "status": final_rules[det.rule_id]["status"],
            "target_positive_count": len(positives),
            "true_positive_count": len(true_positives),
            "target_recall": len(true_positives) / max(len(positives), 1),
            "non_target_count": len(negatives),
            "false_positive_count": len(false_positives),
            "cross_label_fpr": len(false_positives) / max(len(negatives), 1),
            "false_positive_samples": ";".join(r["sample_id"] for r in false_positives),
        })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "candidate-thresholds.json").write_text(json.dumps(candidate_log, indent=2) + "\n", encoding="utf-8")
    (CONFIG_ROOT / "audit" / "rules.json").write_text(json.dumps(rule_config, indent=2) + "\n", encoding="utf-8")
    (CONFIG_ROOT / "audit" / "routing-policy.json").write_text(json.dumps(routing, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(cv_rows).to_csv(OUTPUT_DIR / "cross-validation.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    pd.DataFrame(prediction_rows).to_csv(OUTPUT_DIR / "predictions.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    pd.DataFrame(all_prediction_rows).to_csv(OUTPUT_DIR / "all-predictions.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    pd.DataFrame(cross_qa_rows).to_csv(OUTPUT_DIR / "cross-label-qa.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    report_lines = [
        "# T8-C 阈值选择与冻结报告 v1", "", f"日期：{date.today()}", "",
        "## 结论", "",
        "- Source-aware：六类规则全部进入 rule_v1。",
        "- Raster-only：正文过小、文字过载、空间失衡、对齐错误进入 rule_v1。",
        "- Raster-only 的图内细节不可读与遮挡/裁断因证据不可定位或 OCR 不稳定，冻结为 abstain。",
        "- Formal-88 未被读取或用于调参。", "", "## 开发集与 LOPO 结果", "",
        "| Rule | Track | Label | 状态 | Full pair success | LOPO pair success | LOPO control FPR | LOPO coverage |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for det in DETECTORS:
        info = candidate_log["detectors"][det.rule_id]
        report_lines.append(
            f"| {det.rule_id} | {det.track} | `{det.label}` | {info['status']} | "
            f"{info['full_metrics']['pair_success_rate']:.3f} | {info['lopo_metrics']['pair_success_rate']:.3f} | "
            f"{info['lopo_metrics']['control_fpr']:.3f} | {info['lopo_metrics']['coverage']:.3f} |"
        )
    report_lines += [
        "", "## 跨类别误触发 QA（不参与阈值选择）", "",
        "| Rule | Target recall | Non-target FP | Cross-label FPR |",
        "|---|---:|---:|---:|",
    ]
    for row in cross_qa_rows:
        report_lines.append(
            f"| {row['rule_id']} | {row['target_recall']:.3f} | {row['false_positive_count']}/{row['non_target_count']} | {row['cross_label_fpr']:.3f} |"
        )
    report_lines += [
        "", "## 解释边界", "",
        "这些结果只证明规则能在人工验收后的合成 RuleDev 中跨 pair 工作。由于样本仅 5–6 对/类，且生成器风格有限，不能把开发集高分写成泛化性能。下一步必须先锁定本目录哈希，再建立版式、内容和注入参数均不同的 Hybrid-Test。",
        "", "Raster R2/R6 的 abstain 是设计结果，不是漏做：rule_v1 不允许用整张海报 OCR 数量冒充图片尺度证据，也不允许把 OCR 未识别出省略号解释为没有裁断。",
    ]
    (OUTPUT_DIR / "summary.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    tracked = [
        PAIRS_PATH, FEATURES_PATH, PROTOCOL_PATH, Path(__file__).resolve(),
        HERE / "runtime.py", OUTPUT_DIR / "candidate-thresholds.json",
        CONFIG_ROOT / "audit" / "rules.json", CONFIG_ROOT / "audit" / "routing-policy.json",
        OUTPUT_DIR / "cross-validation.csv", OUTPUT_DIR / "predictions.csv",
        OUTPUT_DIR / "all-predictions.csv", OUTPUT_DIR / "cross-label-qa.csv",
        OUTPUT_DIR / "summary.md",
    ]
    manifest = {
        "version": "rule_freeze_manifest_v1",
        "date": str(date.today()),
        "stage": "T8-C",
        "formal88_used_for_tuning": False,
        "accepted_pairs": len(pairs),
        "accepted_images": len(features),
        "quality_gate": {
            "max_control_fpr": MAX_CONTROL_FPR,
            "all_active_lopo_control_fpr_pass": all(
                final_rules[d.rule_id]["development_metrics"]["lopo"]["control_fpr"] <= MAX_CONTROL_FPR
                for d in DETECTORS if d.kind != "disabled"
            ),
            "all_active_cross_label_fpr_pass": all(
                row["cross_label_fpr"] <= MAX_CONTROL_FPR
                for row in cross_qa_rows if row["status"] == "active"
            ),
        },
        "files": {str(path.relative_to(RESEARCH_ROOT)) if path.is_relative_to(RESEARCH_ROOT) else str(path): sha256(path) for path in tracked},
    }
    (OUTPUT_DIR / "freeze-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "rules": len(DETECTORS),
        "active": sum(d.kind != "disabled" for d in DETECTORS),
        "disabled_abstain": sum(d.kind == "disabled" for d in DETECTORS),
        "quality_gate": manifest["quality_gate"],
    }, indent=2))


if __name__ == "__main__":
    main()
