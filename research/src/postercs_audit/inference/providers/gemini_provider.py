from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseProvider, ProviderResult, image_mime_type, jsonable


class GeminiProvider(BaseProvider):
    provider_name = "gemini"

    def generate(
        self,
        *,
        image_path: Path,
        prompt: str,
        schema: dict[str, Any],
        temperature: float | None,
        max_output_tokens: int,
    ) -> ProviderResult:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key())
        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max_output_tokens,
            "response_mime_type": "application/json",
            "response_json_schema": schema,
        }
        if "thinking_budget" in self.config:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=int(self.config["thinking_budget"]),
            )
        if temperature is not None:
            config_kwargs["temperature"] = temperature
        response = client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=image_path.read_bytes(), mime_type=image_mime_type(image_path)),
                prompt,
            ],
            config=types.GenerateContentConfig(**config_kwargs),
        )
        raw = jsonable(response)
        usage = jsonable(getattr(response, "usage_metadata", None)) or {}
        return ProviderResult(
            provider=self.provider_name,
            model=getattr(response, "model_version", None) or self.model,
            text=response.text or "",
            request_id=getattr(response, "response_id", None),
            usage=usage,
            raw=raw,
        )

    def probe(self) -> dict[str, Any]:
        result = super().probe()
        if not result["api_key_present"]:
            return result
        try:
            from google import genai

            client = genai.Client(api_key=self.api_key())
            wanted = self.model.removeprefix("models/")
            found = None
            for model in client.models.list():
                model_name = str(getattr(model, "name", ""))
                if model_name.removeprefix("models/") == wanted:
                    found = model_name
                    break
            result.update(network_checked=True, available=found is not None, resolved_model=found)
        except Exception as exc:  # pragma: no cover - network/account dependent
            result.update(network_checked=True, available=False, error=f"{type(exc).__name__}: {exc}")
        return result
