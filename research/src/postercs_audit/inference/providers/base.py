from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    model: str
    text: str
    request_id: str | None
    usage: dict[str, Any]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseProvider(ABC):
    provider_name = "base"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.model = str(config["model"])
        self.api_key_env = str(config["api_key_env"])

    def api_key(self) -> str:
        value = os.getenv(self.api_key_env, "").strip()
        if not value:
            raise RuntimeError(f"missing API key environment variable: {self.api_key_env}")
        return value

    @abstractmethod
    def generate(
        self,
        *,
        image_path: Path,
        prompt: str,
        schema: dict[str, Any],
        temperature: float | None,
        max_output_tokens: int,
    ) -> ProviderResult:
        raise NotImplementedError

    def probe(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "configured_model": self.model,
            "api_key_env": self.api_key_env,
            "api_key_present": bool(os.getenv(self.api_key_env, "").strip()),
            "network_checked": False,
        }


def image_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def image_mime_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "image/png"


def jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    try:
        json.dumps(value)
        return value
    except TypeError:
        return {"repr": repr(value)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

