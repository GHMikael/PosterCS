from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
from scipy.stats import binomtest

from postercs_audit.evaluation.core import ISSUE_LABELS, holm_adjust, issue_map, sha256_file
from postercs_audit.evaluation.preflight import preflight
from postercs_audit.evaluation.metrics import (
    build_controlled_pairs,
    controlled_summary_from_pairs,
    natural_summary,
)


EVALUATION_DIR = Path(__file__).resolve().parent
PREDICTION_FIELDS = ("predicted_labels", "predicted_primary", "predicted_severity", "predicted_confidence")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score frozen Formal-88 predictions against frozen Gold.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-score", action="store_true")
    return parser.parse_args()


def resolve(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def stable_seed(seed: int, *parts: str) -> int:
    payload = "::".join((str(seed), *parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gold(path: Path, min_severity: int) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            sample_id = raw["sample_id"]
            if sample_id in result:
                raise ValueError(f"duplicate Gold sample_id: {sample_id}")
            issues = json.loads(raw["issues_json"])
            mapped = issue_map(issues, min_severity=min_severity)
            result[sample_id] = {
                "sample_id": sample_id,
                "dataset": raw["dataset"],
                "gold_primary": raw["primary_issue"],
                "gold_labels": set(mapped),
                "gold_severity": {label: int(issue["severity"]) for label, issue in mapped.items()},
                "gold_source": raw["gold_source"],
            }
    return result


def load_predictions(run_dirs: Sequence[Path], min_severity: int) -> dict[tuple[str, str, str], dict[str, Any]]:
    predictions: dict[tuple[str, str, str], dict[str, Any]] = {}
    for run_dir in run_dirs:
        for path in sorted((run_dir / "parsed").rglob("*.json")):
            record = load_json(path)
            key = (record["sample_id"], record["model_key"], record["prompt_id"])
            if key in predictions:
                raise ValueError(f"duplicate prediction key across runs: {key}")
            prediction = record["prediction"]
            mapped = issue_map(prediction["issues"], min_severity=min_severity)
            predictions[key] = {
                "sample_id": record["sample_id"],
                "model_key": record["model_key"],
                "prompt_id": record["prompt_id"],
                "predicted_primary": prediction["primary_issue"],
                "predicted_labels": set(mapped),
                "predicted_severity": {label: int(issue["severity"]) for label, issue in mapped.items()},
                "predicted_confidence": {label: float(issue["confidence"]) for label, issue in mapped.items()},
                "prediction_path": str(path),
                "source_run": run_dir.name,
            }
    return predictions


def build_rows(config: dict[str, Any], config_path: Path) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    min_severity = int(config["positive_severity_min"])
    inputs = {key: resolve(config_path, value) for key, value in config["inputs"].items()}
    gold = load_gold(inputs["gold"], min_severity)
    predictions = load_predictions([inputs["main_run"], inputs["supplement_run"]], min_severity)
    main_manifest = load_json(inputs["main_run"] / "run_manifest.json")
    expected_keys = {
        (task["sample_id"], task["model_key"], task["prompt_id"])
        for task in main_manifest["selected_tasks"]
    }
    if set(predictions) != expected_keys:
        raise ValueError(
            f"prediction coverage mismatch: missing={len(expected_keys-set(predictions))}, "
            f"unexpected={len(set(predictions)-expected_keys)}"
        )
    natural_key = {row["sample_id"]: row for row in load_json(inputs["natural_pair_key"])}
    controlled_key = {row["pair_id"]: row for row in load_json(inputs["controlled_pair_key"])}
    rows: list[dict[str, Any]] = []
    for key, prediction in predictions.items():
        sample_id = key[0]
        if sample_id not in gold:
            raise ValueError(f"prediction missing Gold: {sample_id}")
        row = {**gold[sample_id], **prediction}
        if row["dataset"] == "natural40":
            pair_meta = natural_key[sample_id]
            row.update(pair_id=pair_meta["pair_id"], variant=pair_meta["variant"], target_label="")
        elif row["dataset"] == "controlled48":
            pair_id, variant = sample_id.rsplit("-", 1)
            row.update(pair_id=pair_id, variant=variant, target_label=controlled_key[pair_id]["target_label"])
        else:
            raise ValueError(f"unknown dataset: {row['dataset']}")
        rows.append(row)
    rows.sort(key=lambda row: (row["model_key"], row["prompt_id"], row["sample_id"]))
    return rows, list(main_manifest["model_keys"]), list(main_manifest["prompt_ids"])


def condition_rows(rows: Sequence[dict[str, Any]], model: str, prompt: str, dataset: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["model_key"] == model and row["prompt_id"] == prompt and row["dataset"] == dataset]


def finite(value: Any) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(float(value))


def percentile(values: Sequence[float], confidence_level: float) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    alpha = 1.0 - confidence_level
    low, high = np.quantile(np.asarray(values, dtype=float), [alpha / 2, 1 - alpha / 2])
    return float(low), float(high)


def bootstrap_rows(
    rows: Sequence[dict[str, Any]],
    metric_fn: Callable[[Sequence[dict[str, Any]]], dict[str, Any]],
    iterations: int,
    seed: int,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["pair_id"])].append(row)
    ids = sorted(groups)
    rng = np.random.default_rng(seed)
    reports: list[dict[str, Any]] = []
    for _ in range(iterations):
        sampled_ids = rng.choice(ids, size=len(ids), replace=True)
        sampled = [row for pair_id in sampled_ids for row in groups[str(pair_id)]]
        reports.append(metric_fn(sampled))
    return reports


def bootstrap_pairs(
    pairs: Sequence[dict[str, Any]],
    metric_fn: Callable[[Sequence[dict[str, Any]]], dict[str, Any]],
    iterations: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    reports: list[dict[str, Any]] = []
    for _ in range(iterations):
        indices = rng.integers(0, len(pairs), size=len(pairs))
        reports.append(metric_fn([pairs[int(index)] for index in indices]))
    return reports


def ci_record(
    *, dataset: str, model: str, prompt: str, metric: str, estimate: Any,
    bootstrap_values: Sequence[Any], confidence_level: float, label: str = "",
) -> dict[str, Any]:
    valid = [float(value) for value in bootstrap_values if finite(value)]
    low, high = percentile(valid, confidence_level)
    return {
        "dataset": dataset,
        "model_key": model,
        "prompt_id": prompt,
        "label": label,
        "metric": metric,
        "estimate": estimate,
        "ci_lower": low,
        "ci_upper": high,
        "bootstrap_valid_n": len(valid),
    }


def clone_with_prediction(row: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(row)
    for field in PREDICTION_FIELDS:
        cloned[field] = source[field]
    return cloned


def macro_f1(rows: Sequence[dict[str, Any]], labels: Sequence[str]) -> float:
    value = natural_summary(rows, labels)["macro_f1"]
    if value is None:
        raise ValueError("macro_f1 is not estimable")
    return float(value)


def natural_comparison(
    rows_a: Sequence[dict[str, Any]], rows_b: Sequence[dict[str, Any]], labels: Sequence[str],
    iterations: int, confidence_level: float, seed: int,
) -> dict[str, Any]:
    by_sample_a = {row["sample_id"]: row for row in rows_a}
    by_sample_b = {row["sample_id"]: row for row in rows_b}
    if set(by_sample_a) != set(by_sample_b):
        raise ValueError("paired natural samples differ")
    groups: dict[str, list[str]] = defaultdict(list)
    for sample_id, row in by_sample_a.items():
        groups[str(row["pair_id"])].append(sample_id)
    ids = sorted(groups)
    observed = macro_f1(rows_b, labels) - macro_f1(rows_a, labels)
    rng = np.random.default_rng(seed)
    bootstrap_diffs: list[float] = []
    for _ in range(iterations):
        sampled_ids = rng.choice(ids, size=len(ids), replace=True)
        sample_ids = [sample_id for pair_id in sampled_ids for sample_id in groups[str(pair_id)]]
        sample_a = [by_sample_a[sample_id] for sample_id in sample_ids]
        sample_b = [by_sample_b[sample_id] for sample_id in sample_ids]
        bootstrap_diffs.append(macro_f1(sample_b, labels) - macro_f1(sample_a, labels))
    low, high = percentile(bootstrap_diffs, confidence_level)
    extreme = 0
    for _ in range(iterations):
        swap = {pair_id: bool(rng.integers(0, 2)) for pair_id in ids}
        pseudo_a: list[dict[str, Any]] = []
        pseudo_b: list[dict[str, Any]] = []
        for sample_id in sorted(by_sample_a):
            a, b = by_sample_a[sample_id], by_sample_b[sample_id]
            if swap[str(a["pair_id"])]:
                pseudo_a.append(clone_with_prediction(a, b))
                pseudo_b.append(clone_with_prediction(b, a))
            else:
                pseudo_a.append(a)
                pseudo_b.append(b)
        permuted = macro_f1(pseudo_b, labels) - macro_f1(pseudo_a, labels)
        extreme += int(abs(permuted) >= abs(observed) - 1e-15)
    return {
        "metric": "macro_f1",
        "method": "paired_cluster_bootstrap_and_randomization",
        "estimate_a": macro_f1(rows_a, labels),
        "estimate_b": macro_f1(rows_b, labels),
        "difference_b_minus_a": observed,
        "ci_lower": low,
        "ci_upper": high,
        "p_value": (extreme + 1) / (iterations + 1),
    }


def pair_success(pair: dict[str, Any]) -> int:
    target = str(pair["target_label"])
    return int(target in pair["mutation_labels"] and target not in pair["control_labels"])


def controlled_comparison(
    pairs_a: Sequence[dict[str, Any]], pairs_b: Sequence[dict[str, Any]],
    iterations: int, confidence_level: float, seed: int,
) -> dict[str, Any]:
    by_id_a = {pair["pair_id"]: pair for pair in pairs_a}
    by_id_b = {pair["pair_id"]: pair for pair in pairs_b}
    if set(by_id_a) != set(by_id_b):
        raise ValueError("paired controlled IDs differ")
    ids = sorted(by_id_a)
    values_a = [pair_success(by_id_a[pair_id]) for pair_id in ids]
    values_b = [pair_success(by_id_b[pair_id]) for pair_id in ids]
    estimate_a = sum(values_a) / len(values_a)
    estimate_b = sum(values_b) / len(values_b)
    observed = estimate_b - estimate_a
    rng = np.random.default_rng(seed)
    differences: list[float] = []
    for _ in range(iterations):
        indices = rng.integers(0, len(ids), size=len(ids))
        differences.append(
            sum(values_b[int(i)] - values_a[int(i)] for i in indices) / len(indices)
        )
    low, high = percentile(differences, confidence_level)
    b_only = sum(a == 0 and b == 1 for a, b in zip(values_a, values_b, strict=True))
    a_only = sum(a == 1 and b == 0 for a, b in zip(values_a, values_b, strict=True))
    discordant = a_only + b_only
    p_value = float(binomtest(min(a_only, b_only), discordant, 0.5).pvalue) if discordant else 1.0
    return {
        "metric": "paired_target_correctness",
        "method": "paired_bootstrap_and_exact_mcnemar",
        "estimate_a": estimate_a,
        "estimate_b": estimate_b,
        "difference_b_minus_a": observed,
        "ci_lower": low,
        "ci_upper": high,
        "discordant_a_only": a_only,
        "discordant_b_only": b_only,
        "p_value": p_value,
    }


def serialize(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    if fieldnames is None:
        ordered_fields: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for field in row:
                if field not in seen:
                    seen.add(field)
                    ordered_fields.append(field)
        fieldnames = ordered_fields
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_scoring(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = load_json(config_path)
    check = preflight(config_path)
    if check["hash_mismatches"] or not check["labels_match"] or not check["gold_columns_present"]:
        raise RuntimeError(f"preflight failed: {check}")
    rows, models, prompts = build_rows(config, config_path)
    labels = list(config["labels"])
    iterations = int(config["bootstrap_iterations"])
    confidence_level = float(config["confidence_level"])
    base_seed = int(config["seed"])

    natural_overall: list[dict[str, Any]] = []
    natural_per_label: list[dict[str, Any]] = []
    controlled_overall: list[dict[str, Any]] = []
    controlled_per_target: list[dict[str, Any]] = []
    ci_rows: list[dict[str, Any]] = []
    natural_conditions: dict[tuple[str, str], list[dict[str, Any]]] = {}
    controlled_conditions: dict[tuple[str, str], list[dict[str, Any]]] = {}

    natural_ci_metrics = (
        "macro_f1", "micro_precision", "micro_recall", "micro_f1", "mean_jaccard", "exact_match",
        "primary_accuracy", "primary_macro_f1", "primary_kappa", "severity_mae", "severity_exact",
        "severity_linear_weighted_kappa", "mean_false_positives", "mean_false_negatives",
    )
    controlled_ci_metrics = (
        "mutation_target_recall", "target_control_fpr", "any_defect_control_fpr",
        "paired_target_correctness", "mean_target_confidence_delta", "mean_predicted_count_delta",
    )

    for model in models:
        for prompt in prompts:
            natural = condition_rows(rows, model, prompt, "natural40")
            controlled = condition_rows(rows, model, prompt, "controlled48")
            if len(natural) != 40 or len(controlled) != 48:
                raise ValueError(f"condition size mismatch: {model}/{prompt}")
            natural_conditions[(model, prompt)] = natural
            natural_report = natural_summary(natural, labels)
            natural_overall.append({
                "model_key": model,
                "prompt_id": prompt,
                **{key: value for key, value in natural_report.items() if key != "per_label"},
            })
            for label, values in natural_report["per_label"].items():
                natural_per_label.append({"model_key": model, "prompt_id": prompt, "label": label, **values})
            natural_bootstrap = bootstrap_rows(
                natural, lambda sample: natural_summary(sample, labels), iterations,
                stable_seed(base_seed, "natural", model, prompt),
            )
            for metric in natural_ci_metrics:
                ci_rows.append(ci_record(
                    dataset="natural40", model=model, prompt=prompt, metric=metric,
                    estimate=natural_report.get(metric),
                    bootstrap_values=[report.get(metric) for report in natural_bootstrap],
                    confidence_level=confidence_level,
                ))
            for label in labels:
                ci_rows.append(ci_record(
                    dataset="natural40", model=model, prompt=prompt, label=label, metric="per_label_f1",
                    estimate=natural_report["per_label"][label]["f1"],
                    bootstrap_values=[report["per_label"][label]["f1"] for report in natural_bootstrap],
                    confidence_level=confidence_level,
                ))

            pairs = build_controlled_pairs(controlled)
            controlled_conditions[(model, prompt)] = pairs
            controlled_report = controlled_summary_from_pairs(pairs)
            controlled_overall.append({"model_key": model, "prompt_id": prompt, **controlled_report})
            controlled_bootstrap = bootstrap_pairs(
                pairs, controlled_summary_from_pairs, iterations,
                stable_seed(base_seed, "controlled", model, prompt),
            )
            for metric in controlled_ci_metrics:
                ci_rows.append(ci_record(
                    dataset="controlled48", model=model, prompt=prompt, metric=metric,
                    estimate=controlled_report.get(metric),
                    bootstrap_values=[report.get(metric) for report in controlled_bootstrap],
                    confidence_level=confidence_level,
                ))
            targets = sorted({str(pair["target_label"]) for pair in pairs})
            for target in targets:
                subset = [pair for pair in pairs if pair["target_label"] == target]
                target_report = controlled_summary_from_pairs(subset)
                controlled_per_target.append({
                    "model_key": model, "prompt_id": prompt, "target_label": target, **target_report,
                })
                target_bootstrap = bootstrap_pairs(
                    subset, controlled_summary_from_pairs, iterations,
                    stable_seed(base_seed, "controlled_target", model, prompt, target),
                )
                for metric in ("mutation_target_recall", "target_control_fpr", "paired_target_correctness"):
                    ci_rows.append(ci_record(
                        dataset="controlled48", model=model, prompt=prompt, label=target,
                        metric=f"per_target_{metric}", estimate=target_report.get(metric),
                        bootstrap_values=[report.get(metric) for report in target_bootstrap],
                        confidence_level=confidence_level,
                    ))

    comparisons_rows: list[dict[str, Any]] = []
    comparison_specs: list[tuple[str, str, tuple[str, str], tuple[str, str]]] = []
    for model in models:
        for prompt_a, prompt_b in ((prompts[0], prompts[1]), (prompts[0], prompts[2]), (prompts[1], prompts[2])):
            comparison_specs.append(("prompt", model, (model, prompt_a), (model, prompt_b)))
    for prompt in prompts:
        for model_a, model_b in combinations(models, 2):
            comparison_specs.append(("model", prompt, (model_a, prompt), (model_b, prompt)))

    for family, stratum, condition_a, condition_b in comparison_specs:
        for dataset in ("natural40", "controlled48"):
            seed = stable_seed(base_seed, "comparison", dataset, *condition_a, *condition_b)
            if dataset == "natural40":
                result = natural_comparison(
                    natural_conditions[condition_a], natural_conditions[condition_b], labels,
                    iterations, confidence_level, seed,
                )
            else:
                result = controlled_comparison(
                    controlled_conditions[condition_a], controlled_conditions[condition_b],
                    iterations, confidence_level, seed,
                )
            comparisons_rows.append({
                "dataset": dataset,
                "comparison_family": family,
                "stratum": stratum,
                "method_a_model": condition_a[0],
                "method_a_prompt": condition_a[1],
                "method_b_model": condition_b[0],
                "method_b_prompt": condition_b[1],
                **result,
            })
    grouped_indices: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(comparisons_rows):
        grouped_indices[(row["dataset"], row["comparison_family"])].append(index)
    for indices in grouped_indices.values():
        adjusted = holm_adjust([float(comparisons_rows[index]["p_value"]) for index in indices])
        for index, value in zip(indices, adjusted, strict=True):
            comparisons_rows[index]["p_value_holm"] = value

    merged_csv_rows: list[dict[str, Any]] = []
    for row in rows:
        merged_csv_rows.append({
            "sample_id": row["sample_id"], "dataset": row["dataset"], "pair_id": row["pair_id"],
            "variant": row["variant"], "target_label": row["target_label"], "model_key": row["model_key"],
            "prompt_id": row["prompt_id"], "gold_primary": row["gold_primary"],
            "predicted_primary": row["predicted_primary"],
            "gold_labels_json": json.dumps(sorted(row["gold_labels"]), ensure_ascii=False),
            "predicted_labels_json": json.dumps(sorted(row["predicted_labels"]), ensure_ascii=False),
            "gold_severity_json": json.dumps(row["gold_severity"], ensure_ascii=False, sort_keys=True),
            "predicted_severity_json": json.dumps(row["predicted_severity"], ensure_ascii=False, sort_keys=True),
            "predicted_confidence_json": json.dumps(row["predicted_confidence"], ensure_ascii=False, sort_keys=True),
            "gold_source": row["gold_source"], "source_run": row["source_run"],
            "prediction_path": row["prediction_path"],
        })

    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    write_csv(output_dir / "predictions_merged.csv", merged_csv_rows)
    write_csv(output_dir / "natural_overall_metrics.csv", natural_overall)
    write_csv(output_dir / "natural_per_label_metrics.csv", natural_per_label)
    write_csv(output_dir / "controlled_overall_metrics.csv", controlled_overall)
    write_csv(output_dir / "controlled_per_target_metrics.csv", controlled_per_target)
    write_csv(output_dir / "confidence_intervals.csv", ci_rows)
    write_csv(output_dir / "primary_comparisons.csv", comparisons_rows)

    summary = {
        "version": config["version"],
        "scoring_protocol": "protocols/scoring.md",
        "formal_scores_computed": True,
        "records": len(rows),
        "conditions": len(models) * len(prompts),
        "models": models,
        "prompts": prompts,
        "positive_severity_min": config["positive_severity_min"],
        "bootstrap_iterations": iterations,
        "confidence_level": confidence_level,
        "preflight": check,
        "outputs": {},
    }
    for path in sorted(output_dir.glob("*.csv")):
        summary["outputs"][path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    (output_dir / "scoring_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    args = parse_args()
    if not args.allow_score:
        raise SystemExit("formal scoring blocked: pass --allow-score after explicit approval")
    summary = run_scoring(args.config.expanduser().resolve(), args.output.expanduser().resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
