from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from postercs_audit.paths import CONFIG_ROOT, RESEARCH_ROOT

INFERENCE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RESEARCH_ROOT


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return value


def resolve_from(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def resolve_image_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (RESEARCH_ROOT / path).resolve()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def load_models_config() -> dict[str, dict[str, Any]]:
    return load_yaml(CONFIG_ROOT / "models" / "models.yaml")["models"]


def load_prompt(prompt_id: str) -> str:
    path = CONFIG_ROOT / "prompts" / f"{prompt_id}.txt"
    if not path.exists():
        raise FileNotFoundError(f"unknown prompt: {prompt_id}")
    return path.read_text(encoding="utf-8").strip()


def compose_prompt(
    prompt_id: str,
    *,
    schema: dict[str, Any],
    label_definitions: dict[str, Any],
) -> str:
    sections = [load_prompt(prompt_id)]
    if prompt_id in {"taxonomy", "evidence-grounded"}:
        sections.append(
            "FROZEN LABEL DEFINITIONS:\n"
            + json.dumps(label_definitions["labels"], ensure_ascii=False, indent=2)
        )
    sections.append(
        "SEVERITY RULES:\n"
        "1 minor: visible but does not impede main reading or understanding.\n"
        "2 moderate: clearly reduces reading efficiency, accurate understanding, or professional presentation.\n"
        "3 severe: key content is unreadable, the reading path is broken, or a hard rendering failure is present."
    )
    sections.append("OUTPUT JSON SCHEMA:\n" + json.dumps(schema, ensure_ascii=False, separators=(",", ":")))
    sections.append(
        "FINAL OUTPUT INSTRUCTION:\n"
        "The schema above is a contract, not the answer. Do not repeat or describe the schema. "
        "Return one JSON instance whose top-level keys are exactly issues, primary_issue, "
        "no_issue_reason, and audit_summary. Never return schema-definition keys such as "
        "title, type, properties, required, or additionalProperties. Each defect label may "
        "appear at most once: if the same defect occurs in multiple regions, merge those "
        "observations into one issue and summarize all affected regions in its region and "
        "evidence fields. If primary_issue is not none, no_issue_reason must be the empty "
        "string. If primary_issue is none, no_issue_reason must briefly explain why no "
        "moderate or severe defect qualifies. Output JSON only."
    )
    return "\n\n".join(sections)
