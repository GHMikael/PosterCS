from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from postercs_audit.inference.utils import (
    PROJECT_ROOT,
    append_jsonl,
    canonical_hash,
    compose_prompt,
    load_models_config,
    load_yaml,
    resolve_from,
    resolve_image_path,
    sha256_file,
    utc_now,
    write_json_exclusive,
)
from postercs_audit.inference.providers import PROVIDERS
from postercs_audit.inference.validation import (
    PredictionValidationError,
    load_schema,
    parse_and_validate,
    provider_schema,
)
from postercs_audit.paths import CONFIG_ROOT, REPOSITORY_ROOT


INFERENCE_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen PosterCS VLM audit prompts.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--allow-formal", action="store_true")
    parser.add_argument(
        "--only-missing-from",
        type=Path,
        help="Run only tasks without a valid parsed prediction in an earlier run directory.",
    )
    return parser.parse_args()


def load_records(config: dict[str, Any], config_path: Path) -> tuple[Path, list[dict[str, Any]]]:
    manifest_path = resolve_from(config_path.parent, config["dataset_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records", [])
    wanted = set(config.get("sample_ids") or [])
    if wanted:
        records = [record for record in records if record["sample_id"] in wanted]
        missing = wanted - {record["sample_id"] for record in records}
        if missing:
            raise ValueError(f"sample IDs not found in manifest: {sorted(missing)}")
    if config.get("development_only") and "formal88" in manifest_path.name.lower():
        raise ValueError("development_only config may not point to Formal-88")
    return manifest_path, records


def verify_records(records: list[dict[str, Any]], verify_hashes: bool) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        sample_id = str(record["sample_id"])
        if sample_id in seen:
            raise ValueError(f"duplicate sample_id: {sample_id}")
        seen.add(sample_id)
        image_path = resolve_image_path(record["image_path"])
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        actual_hash = sha256_file(image_path)
        if verify_hashes and actual_hash != record["sha256"]:
            raise ValueError(f"image hash mismatch: {sample_id}")
        copied = dict(record)
        copied["resolved_image_path"] = str(image_path)
        copied["verified_sha256"] = actual_hash
        verified.append(copied)
    return verified


def build_tasks(
    records: list[dict[str, Any]],
    model_keys: list[str],
    prompt_ids: list[str],
    seed: int,
) -> list[dict[str, Any]]:
    tasks = [
        {"record": record, "model_key": model_key, "prompt_id": prompt_id}
        for record in records
        for model_key in model_keys
        for prompt_id in prompt_ids
    ]
    random.Random(seed).shuffle(tasks)
    return tasks


def filter_missing_tasks(
    tasks: list[dict[str, Any]],
    source_run: Path,
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        task
        for task in tasks
        if not completed_prediction(
            task_paths(
                source_run,
                task["model_key"],
                task["prompt_id"],
                task["record"]["sample_id"],
            )["parsed"],
            schema,
        )
    ]


def safe_run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise ValueError("run-id may contain only letters, digits, dot, underscore, and hyphen")
    return value


def task_paths(run_dir: Path, model_key: str, prompt_id: str, sample_id: str) -> dict[str, Path]:
    stem = Path(model_key) / prompt_id / sample_id
    return {
        "attempt_dir": run_dir / "raw" / stem,
        "parsed": run_dir / "parsed" / stem.with_suffix(".json"),
        "error": run_dir / "errors" / stem.with_suffix(".json"),
    }


def completed_prediction(path: Path, schema: dict[str, Any]) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        parse_and_validate(json.dumps(payload["prediction"]), schema)
        return True
    except Exception:
        return False


def next_attempt_path(attempt_dir: Path, max_attempts: int) -> tuple[int, Path] | None:
    for index in range(1, max_attempts + 1):
        path = attempt_dir / f"attempt_{index:02d}.json"
        if not path.exists():
            return index, path
    return None


def create_or_check_manifest(
    *,
    run_dir: Path,
    config: dict[str, Any],
    config_path: Path,
    manifest_path: Path,
    records: list[dict[str, Any]],
    models: dict[str, dict[str, Any]],
    prompts: dict[str, str],
    schema_path: Path,
    labels_path: Path,
    tasks: list[dict[str, Any]],
    only_missing_from: Path | None,
) -> None:
    path = run_dir / "run_manifest.json"
    frozen = {
        "run_id": run_dir.name,
        "created_at": utc_now(),
        "run_kind": config["run_kind"],
        "seed": config["seed"],
        "task_count": len(tasks),
        "selected_tasks": [
            {
                "sample_id": task["record"]["sample_id"],
                "model_key": task["model_key"],
                "prompt_id": task["prompt_id"],
            }
            for task in tasks
        ],
        "only_missing_from": str(only_missing_from) if only_missing_from else None,
        "sample_ids": [record["sample_id"] for record in records],
        "model_keys": config["model_keys"],
        "models": {key: models[key] for key in config["model_keys"]},
        "prompt_ids": config["prompt_ids"],
        "hashes": {
            "config": sha256_file(config_path),
            "models_config": sha256_file(CONFIG_ROOT / "models" / "models.yaml"),
            "dataset_manifest": sha256_file(manifest_path),
            "schema": sha256_file(schema_path),
            "label_definitions": sha256_file(labels_path),
            "prompts": {key: canonical_hash(value) for key, value in prompts.items()},
            "code": {
                str(path.relative_to(REPOSITORY_ROOT)): sha256_file(path)
                for path in [
                    INFERENCE_DIR / "runner.py",
                    INFERENCE_DIR / "validation.py",
                    INFERENCE_DIR / "utils.py",
                    INFERENCE_DIR / "providers" / "base.py",
                    INFERENCE_DIR / "providers" / "openai_provider.py",
                    INFERENCE_DIR / "providers" / "gemini_provider.py",
                    INFERENCE_DIR / "providers" / "glm_provider.py",
                    INFERENCE_DIR / "providers" / "qwen_provider.py",
                ]
            },
        },
        "runtime": {
            "python": platform.python_version(),
            "packages": {
                name: importlib.metadata.version(name)
                for name in ["openai", "google-genai", "PyYAML", "jsonschema", "Pillow", "python-dotenv"]
            },
        },
        "gold_loaded": False,
    }
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        for key in ("run_kind", "seed", "task_count", "sample_ids", "model_keys", "prompt_ids", "hashes"):
            if existing.get(key) != frozen.get(key):
                raise RuntimeError(f"run manifest mismatch for {key}; use a new run-id")
        return
    write_json_exclusive(path, frozen)


def main() -> int:
    args = parse_args()
    load_dotenv(REPOSITORY_ROOT / ".env")
    config_path = args.config.expanduser().resolve()
    config = load_yaml(config_path)
    if config["run_kind"] == "formal" and not args.allow_formal:
        raise SystemExit("formal run blocked: pass --allow-formal only after explicit approval")

    models = load_models_config()
    for model_key in config["model_keys"]:
        if model_key not in models:
            raise ValueError(f"unknown model key: {model_key}")
    manifest_path, records = load_records(config, config_path)
    records = verify_records(records, bool(config.get("verify_image_hashes", True)))

    schema_path = CONFIG_ROOT / "audit" / "prediction-schema.json"
    labels_path = CONFIG_ROOT / "audit" / "label-definitions.json"
    schema = load_schema(schema_path)
    api_schema = provider_schema(schema)
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    prompts = {
        prompt_id: compose_prompt(prompt_id, schema=api_schema, label_definitions=labels)
        for prompt_id in config["prompt_ids"]
    }
    tasks = build_tasks(records, config["model_keys"], config["prompt_ids"], int(config["seed"]))
    source_run = args.only_missing_from.expanduser().resolve() if args.only_missing_from else None
    if source_run is not None:
        if not source_run.is_dir():
            raise FileNotFoundError(source_run)
        tasks = filter_missing_tasks(tasks, source_run, schema)
    if args.limit is not None:
        tasks = tasks[: args.limit]

    summary = {
        "run_kind": config["run_kind"],
        "dataset_manifest": str(manifest_path),
        "samples": len(records),
        "models": config["model_keys"],
        "prompts": config["prompt_ids"],
        "planned_tasks": len(tasks),
        "disabled_models": [key for key in config["model_keys"] if not models[key].get("enabled", False)],
        "only_missing_from": str(source_run) if source_run else None,
        "gold_loaded": False,
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    disabled = summary["disabled_models"]
    if disabled:
        raise SystemExit(f"run blocked: enable model(s) in configs/models/models.yaml after probe: {disabled}")

    run_id = safe_run_id(args.run_id or f"{config['run_kind']}_{datetime.now():%Y%m%d_%H%M%S}")
    output_root = resolve_from(config_path.parent, config["output_root"])
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    create_or_check_manifest(
        run_dir=run_dir,
        config=config,
        config_path=config_path,
        manifest_path=manifest_path,
        records=records,
        models=models,
        prompts=prompts,
        schema_path=schema_path,
        labels_path=labels_path,
        tasks=tasks,
        only_missing_from=source_run,
    )

    max_attempts = int(config["max_attempts"])
    progress_path = run_dir / "progress.jsonl"
    counts = {"completed": 0, "skipped": 0, "failed": 0}
    for task in tasks:
        record = task["record"]
        model_key = task["model_key"]
        prompt_id = task["prompt_id"]
        sample_id = record["sample_id"]
        paths = task_paths(run_dir, model_key, prompt_id, sample_id)
        if completed_prediction(paths["parsed"], schema):
            counts["skipped"] += 1
            continue

        provider = PROVIDERS[models[model_key]["provider"]](models[model_key])
        success = False
        while True:
            next_attempt = next_attempt_path(paths["attempt_dir"], max_attempts)
            if next_attempt is None:
                break
            attempt_index, attempt_path = next_attempt
            started = time.perf_counter()
            envelope: dict[str, Any] = {
                "sample_id": sample_id,
                "model_key": model_key,
                "prompt_id": prompt_id,
                "attempt": attempt_index,
                "started_at": utc_now(),
                "image_sha256": record["verified_sha256"],
            }
            try:
                result = provider.generate(
                    image_path=Path(record["resolved_image_path"]),
                    prompt=prompts[prompt_id],
                    schema=api_schema,
                    temperature=models[model_key].get("temperature", config.get("temperature")),
                    max_output_tokens=int(config["max_output_tokens"]),
                )
                envelope["provider_result"] = result.to_dict()
                prediction = parse_and_validate(result.text, schema)
                envelope["status"] = "valid"
                envelope["elapsed_seconds"] = round(time.perf_counter() - started, 4)
                envelope["finished_at"] = utc_now()
                write_json_exclusive(attempt_path, envelope)
                parsed_record = {
                    "sample_id": sample_id,
                    "model_key": model_key,
                    "provider": result.provider,
                    "model": result.model,
                    "prompt_id": prompt_id,
                    "image_sha256": record["verified_sha256"],
                    "prediction": prediction,
                    "request_id": result.request_id,
                    "usage": result.usage,
                    "elapsed_seconds": envelope["elapsed_seconds"],
                    "completed_at": envelope["finished_at"],
                }
                write_json_exclusive(paths["parsed"], parsed_record)
                append_jsonl(progress_path, {"status": "completed", **{k: envelope[k] for k in ("sample_id", "model_key", "prompt_id", "attempt", "finished_at")}})
                counts["completed"] += 1
                success = True
                break
            except Exception as exc:
                envelope.update(
                    status=("validation_error" if isinstance(exc, PredictionValidationError) else "api_error"),
                    error_type=type(exc).__name__,
                    error=str(exc),
                    elapsed_seconds=round(time.perf_counter() - started, 4),
                    finished_at=utc_now(),
                )
                write_json_exclusive(attempt_path, envelope)
                append_jsonl(progress_path, {"status": envelope["status"], **{k: envelope[k] for k in ("sample_id", "model_key", "prompt_id", "attempt", "finished_at")}})
                if attempt_index < max_attempts:
                    time.sleep(float(config["retry_base_seconds"]) * (2 ** (attempt_index - 1)))

        if not success:
            error_record = {
                "sample_id": sample_id,
                "model_key": model_key,
                "prompt_id": prompt_id,
                "status": "failed_after_retries",
                "max_attempts": max_attempts,
                "recorded_at": utc_now(),
            }
            if not paths["error"].exists():
                write_json_exclusive(paths["error"], error_record)
            counts["failed"] += 1

    print(json.dumps({**summary, **counts, "run_dir": str(run_dir)}, ensure_ascii=False, indent=2))
    return 0 if counts["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
