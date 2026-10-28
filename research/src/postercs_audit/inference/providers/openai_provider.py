from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseProvider, ProviderResult, image_data_url, jsonable


class OpenAIProvider(BaseProvider):
    provider_name = "openai"

    def generate(
        self,
        *,
        image_path: Path,
        prompt: str,
        schema: dict[str, Any],
        temperature: float | None,
        max_output_tokens: int,
    ) -> ProviderResult:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key())
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": image_data_url(image_path),
                        "detail": self.config.get("image_detail", "high"),
                    },
                ],
            }],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "postercs_visual_audit",
                    "strict": True,
                    "schema": schema,
                }
            },
            "max_output_tokens": max_output_tokens,
        }
        reasoning_effort = self.config.get("reasoning_effort")
        if reasoning_effort:
            kwargs["reasoning"] = {"effort": reasoning_effort}
        if temperature is not None:
            kwargs["temperature"] = temperature
        response = client.responses.create(**kwargs)
        raw = jsonable(response)
        usage = jsonable(getattr(response, "usage", None)) or {}
        return ProviderResult(
            provider=self.provider_name,
            model=str(getattr(response, "model", self.model)),
            text=response.output_text,
            request_id=getattr(response, "id", None),
            usage=usage,
            raw=raw,
        )

    def probe(self) -> dict[str, Any]:
        result = super().probe()
        if not result["api_key_present"]:
            return result
        try:
            from openai import OpenAI

            model = OpenAI(api_key=self.api_key()).models.retrieve(self.model)
            result.update(network_checked=True, available=True, resolved_model=getattr(model, "id", self.model))
        except Exception as exc:  # pragma: no cover - network/account dependent
            result.update(network_checked=True, available=False, error=f"{type(exc).__name__}: {exc}")
        return result
