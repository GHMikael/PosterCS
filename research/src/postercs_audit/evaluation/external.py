#!/usr/bin/env python3
"""Score the frozen External-Natural-20 Gold against frozen VLM predictions.

The script performs no inference and does not select operating points.  It
merges the intentionally interrupted Qwen batch with its missing-item resume
only after checking that every EN sample has exactly one valid prediction.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from postercs_audit.evaluation.core import ISSUE_LABELS, sha256_file
from postercs_audit.evaluation.metrics import natural_summary
from postercs_audit.paths import DATA_ROOT, RESULTS_ROOT


GOLD = DATA_ROOT / "external" / "gold.csv"
GOLD_FREEZE = DATA_ROOT / "external" / "freeze-manifest.json"
GEMINI_RUN = RESULTS_ROOT / "predictions" / "external-gemini"
QWEN_RUNS = (
    RESULTS_ROOT / "predictions" / "external-qwen",
    RESULTS_ROOT / "predictions" / "external-qwen-resume",
)
OUT_JSON = RESULTS_ROOT / "external" / "metrics.json"
OUT_CSV = RESULTS_ROOT / "external" / "scored-predictions.csv"
OUT_REPORT = RESULTS_ROOT / "external" / "summary.md"


def load_gold() -> dict[str, dict[str, Any]]:
    gold: dict[str, dict[str, Any]] = {}
    with GOLD.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            issues = json.loads(row["issues_json"])
            labels = sorted(issue["label"] for issue in issues if int(issue["severity"]) >= 2)
            gold[row["sample_id"]] = {
                "labels": labels,
                "primary": row["primary_issue"],
                "severity": {issue["label"]: int(issue["severity"]) for issue in issues},
            }
    return gold


def collect_predictions(run_dirs: tuple[Path, ...], model_key: str, prompt_id: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for run_dir in run_dirs:
        base = run_dir / "parsed" / model_key / prompt_id
        for path in sorted(base.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            sample_id = str(payload["sample_id"])
            if sample_id in records:
                raise RuntimeError(f"duplicate valid prediction for {model_key}/{sample_id}: {path}")
            records[sample_id] = payload
    return records


def make_rows(gold: dict[str, dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if set(gold) != set(predictions):
        raise RuntimeError(f"coverage mismatch; missing={sorted(set(gold)-set(predictions))}, extra={sorted(set(predictions)-set(gold))}")
    rows: list[dict[str, Any]] = []
    for sample_id in sorted(gold):
        prediction = predictions[sample_id]["prediction"]
        issues = prediction["issues"]
        predicted_labels = sorted(issue["label"] for issue in issues if int(issue["severity"]) >= 2)
        rows.append({
            "sample_id": sample_id,
            "gold_labels": gold[sample_id]["labels"],
            "predicted_labels": predicted_labels,
            "gold_primary": gold[sample_id]["primary"],
            "predicted_primary": prediction["primary_issue"],
            "gold_severity": gold[sample_id]["severity"],
            "predicted_severity": {issue["label"]: int(issue["severity"]) for issue in issues},
            "predicted_count": len(predicted_labels),
            "false_positive_labels": sorted(set(predicted_labels) - set(gold[sample_id]["labels"])),
            "false_negative_labels": sorted(set(gold[sample_id]["labels"]) - set(predicted_labels)),
            "elapsed_seconds": predictions[sample_id].get("elapsed_seconds"),
            "request_id": predictions[sample_id].get("request_id"),
        })
    return rows


def compact_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = natural_summary(rows, ISSUE_LABELS)
    none_rows = [row for row in rows if not row["gold_labels"]]
    summary["gold_none_n"] = len(none_rows)
    summary["gold_none_any_defect_fpr"] = (
        sum(bool(row["predicted_labels"]) for row in none_rows) / len(none_rows) if none_rows else None
    )
    summary["predicted_label_frequency"] = dict(Counter(
        label for row in rows for label in row["predicted_labels"]
    ))
    summary["mean_elapsed_seconds"] = sum(float(row["elapsed_seconds"] or 0) for row in rows) / len(rows)
    return summary


def write_csv(model_rows: dict[str, list[dict[str, Any]]]) -> None:
    columns = [
        "model_key", "sample_id", "gold_primary", "predicted_primary", "gold_labels",
        "predicted_labels", "false_positive_labels", "false_negative_labels", "predicted_count",
        "elapsed_seconds", "request_id",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for model_key, rows in model_rows.items():
            for row in rows:
                writer.writerow({
                    "model_key": model_key,
                    "sample_id": row["sample_id"],
                    "gold_primary": row["gold_primary"],
                    "predicted_primary": row["predicted_primary"],
                    "gold_labels": json.dumps(row["gold_labels"], ensure_ascii=False),
                    "predicted_labels": json.dumps(row["predicted_labels"], ensure_ascii=False),
                    "false_positive_labels": json.dumps(row["false_positive_labels"], ensure_ascii=False),
                    "false_negative_labels": json.dumps(row["false_negative_labels"], ensure_ascii=False),
                    "predicted_count": row["predicted_count"],
                    "elapsed_seconds": row["elapsed_seconds"],
                    "request_id": row["request_id"],
                })


def main() -> None:
    gold = load_gold()
    model_specs = {
        "gemini_flash_p2": ((GEMINI_RUN,), "gemini_flash", "p2_taxonomy"),
        "qwen32b_p3": (QWEN_RUNS, "qwen_vl_32b", "p3_evidence_grounded"),
    }
    model_rows: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for name, (runs, model_key, prompt_id) in model_specs.items():
        rows = make_rows(gold, collect_predictions(runs, model_key, prompt_id))
        model_rows[name] = rows
        summaries[name] = compact_summary(rows)

    payload = {
        "version": "external_natural20_results_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "gold_path": str(GOLD),
        "gold_sha256": sha256_file(GOLD),
        "gold_freeze_sha256": sha256_file(GOLD_FREEZE),
        "n": len(gold),
        "macro_f1_policy": "mean over labels with Gold support > 0; zero-support labels excluded",
        "input_protocol": "preprocessed long-side 2400px, aspect preserved, no crop/stretch",
        "runs": {name: [str(path) for path in spec[0]] for name, spec in model_specs.items()},
        "summaries": summaries,
        "rows": model_rows,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(model_rows)

    lines = [
        "# External-Natural-20 结果", "",
        "- 定位：Gold 冻结后的外部自然样本检查；n=20；仅比较两个预先固定的 image-only VLM operating point。",
        "- 输入：同一套保持原始纵横比、无裁切/拉伸、最长边 2400px 的 PNG 派生图。",
        "- Macro-F1：只对 Gold support > 0 的标签取平均；本集有正例的标签为 body_text_too_small、figure_detail_unreadable、text_overload、space_imbalance。",
        "- Qwen 由首批 10 条与中断后的 missing-only 续跑 10 条组成；两批使用相同配置、提示词和派生输入清单。", "",
        "| 模型 | micro-P | micro-R | micro-F1 | macro-F1 | exact match | mean Jaccard | primary acc. | Gold-none any-defect FPR | 平均指控数 |", 
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, summary in summaries.items():
        lines.append(
            f"| {name} | {summary['micro_precision']:.3f} | {summary['micro_recall']:.3f} | {summary['micro_f1']:.3f} | "
            f"{summary['macro_f1']:.3f} | {summary['exact_match']:.3f} | {summary['mean_jaccard']:.3f} | "
            f"{summary['primary_accuracy']:.3f} | {summary['gold_none_any_defect_fpr']:.3f} | {summary['mean_predicted_labels']:.2f} |"
        )
    lines += ["", "## 每标签结果", ""]
    for name, summary in summaries.items():
        lines += [f"### {name}", "", "| 标签 | support | TP | FP | FN | P | R | F1 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for label, values in summary["per_label"].items():
            if values["support"]:
                lines.append(
                    f"| {label} | {values['support']} | {values['tp']} | {values['fp']} | {values['fn']} | "
                    f"{values['precision']:.3f} | {values['recall']:.3f} | {values['f1']:.3f} |"
                )
        lines.append("")
        lines.append(f"预测标签频率：`{json.dumps(summary['predicted_label_frequency'], ensure_ascii=False, sort_keys=True)}`")
        lines.append("")
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"n": len(gold), "summaries": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
