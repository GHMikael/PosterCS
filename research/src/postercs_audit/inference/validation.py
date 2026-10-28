from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


INFERENCE_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA_PATH = INFERENCE_DIR / "protocol" / "prediction_schema.json"


class PredictionValidationError(ValueError):
    pass


def load_schema(path: Path = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def provider_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove annotation-only keys that some structured-output APIs reject."""
    return {key: value for key, value in schema.items() if key not in {"$schema"}}


def parse_json_response(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise PredictionValidationError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PredictionValidationError("top-level prediction must be a JSON object")
    return value


def _join_unique(values: list[str], limit: int) -> str:
    result = ""
    for value in values:
        value = value.strip()
        if not value or value in result:
            continue
        candidate = value if not result else f"; {value}"
        if len(result) + len(candidate) > limit:
            if not result:
                result = value[:limit]
            break
        result += candidate
    return result


def _truncate(value: Any, limit: int) -> Any:
    return value[:limit] if isinstance(value, str) and len(value) > limit else value


def normalize_prediction(prediction: dict[str, Any]) -> dict[str, Any]:
    """Apply representation-only normalization before strict validation.

    Models sometimes emit one issue per affected region even though evaluation
    is label-level. Duplicate labels are merged without adding or removing a
    label: severity and confidence use the maximum observation, while evidence
    and the recommended action come from that strongest observation.
    """
    normalized = json.loads(json.dumps(prediction, ensure_ascii=False))
    issues = normalized.get("issues")
    if isinstance(issues, list):
        grouped: dict[str, list[dict[str, Any]]] = {}
        order: list[str] = []
        passthrough: list[Any] = []
        for issue in issues:
            if not isinstance(issue, dict) or not isinstance(issue.get("label"), str):
                passthrough.append(issue)
                continue
            label = issue["label"]
            if label not in grouped:
                grouped[label] = []
                order.append(label)
            grouped[label].append(issue)

        merged: list[Any] = []
        for label in order:
            observations = grouped[label]
            strongest = max(
                observations,
                key=lambda item: (
                    item.get("severity", -1) if isinstance(item.get("severity"), (int, float)) else -1,
                    item.get("confidence", -1) if isinstance(item.get("confidence"), (int, float)) else -1,
                ),
            )
            combined = dict(strongest)
            combined["region"] = _join_unique(
                [str(item.get("region", "")) for item in observations],
                120,
            )
            merged.append(combined)
        normalized["issues"] = merged + passthrough
        for issue in normalized["issues"]:
            if not isinstance(issue, dict):
                continue
            issue["region"] = _truncate(issue.get("region"), 120)
            issue["evidence"] = _truncate(issue.get("evidence"), 600)
            issue["recommended_action"] = _truncate(issue.get("recommended_action"), 400)

    normalized["no_issue_reason"] = _truncate(normalized.get("no_issue_reason"), 400)
    normalized["audit_summary"] = _truncate(normalized.get("audit_summary"), 600)

    normalized_issues = normalized.get("issues")
    if isinstance(normalized_issues, list):
        moderate_or_severe = {
            issue.get("label")
            for issue in normalized_issues
            if isinstance(issue, dict)
            and isinstance(issue.get("severity"), (int, float))
            and issue["severity"] >= 2
        }
        if not moderate_or_severe and normalized.get("primary_issue") != "none":
            normalized["primary_issue"] = "none"

    if normalized.get("primary_issue") != "none" and isinstance(normalized.get("no_issue_reason"), str):
        normalized["no_issue_reason"] = ""
    if normalized.get("primary_issue") == "none" and normalized.get("no_issue_reason") == "":
        normalized["no_issue_reason"] = "The model reported no moderate or severe defect."
    if normalized.get("audit_summary") == "":
        if normalized.get("primary_issue") == "none":
            normalized["audit_summary"] = "No qualifying defect was reported."
        else:
            normalized["audit_summary"] = (
                f"The model selected {normalized.get('primary_issue')} as the primary defect."
            )
    return normalized


def validate_prediction(
    prediction: dict[str, Any],
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    schema = schema or load_schema()
    errors = sorted(Draft202012Validator(schema).iter_errors(prediction), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(f"{list(err.path)}: {err.message}" for err in errors[:8])
        raise PredictionValidationError(f"schema validation failed: {details}")

    issues = prediction["issues"]
    labels = [issue["label"] for issue in issues]
    if len(labels) != len(set(labels)):
        raise PredictionValidationError("each defect label may appear at most once")

    moderate_or_severe = {issue["label"] for issue in issues if issue["severity"] >= 2}
    primary = prediction["primary_issue"]
    no_issue_reason = prediction["no_issue_reason"].strip()

    if moderate_or_severe and primary == "none":
        raise PredictionValidationError("primary_issue cannot be none when a severity 2-3 issue exists")
    if primary != "none" and primary not in moderate_or_severe:
        raise PredictionValidationError("primary_issue must refer to a recorded severity 2-3 issue")
    if primary == "none" and not no_issue_reason:
        raise PredictionValidationError("no_issue_reason is required when primary_issue is none")
    if primary != "none" and no_issue_reason:
        raise PredictionValidationError("no_issue_reason must be empty when primary_issue is not none")
    return prediction


def parse_and_validate(text: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    return validate_prediction(normalize_prediction(parse_json_response(text)), schema)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate one PosterCS prediction JSON file.")
    parser.add_argument("prediction", type=Path)
    args = parser.parse_args()
    validate_prediction(json.loads(args.prediction.read_text(encoding="utf-8")))
    print("valid")
