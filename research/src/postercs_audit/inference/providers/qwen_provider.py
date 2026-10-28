from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseProvider, ProviderResult, image_data_url, jsonable


class QwenProvider(BaseProvider):
    provider_name = "qwen"

    def _client(self):
        from openai import OpenAI

        # External natural posters can be substantially larger than the
        # 16:9 synthetic inputs.  A run-specific timeout prevents one remote
        # request from blocking the whole, otherwise resumable, runner.
        client_kwargs: dict[str, Any] = {
            "api_key": self.api_key(),
            "base_url": str(self.config["base_url"]),
        }
        if self.config.get("timeout_seconds") is not None:
            client_kwargs["timeout"] = float(self.config["timeout_seconds"])
        return OpenAI(**client_kwargs)

    def generate(
        self,
        *,
        image_path: Path,
        prompt: str,
        schema: dict[str, Any],
        temperature: float | None,
        max_output_tokens: int,
    ) -> ProviderResult:
        mode = str(self.config.get("structured_mode", "json_object"))
        response_format: dict[str, Any]
        if mode == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "postercs_visual_audit",
                    "strict": True,
                    "schema": schema,
                },
            }
        elif mode == "json_object":
            response_format = {"type": "json_object"}
        else:
            raise ValueError(f"unsupported Qwen structured_mode: {mode}")

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url(image_path)},
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
            "response_format": response_format,
            "max_tokens": max_output_tokens,
        }
        # Some OpenAI-compatible hosts reject enable_thinking even when it is
        # explicitly false (notably SiliconFlow's Qwen3-VL Instruct models).
        # Only send the vendor extension when the model configuration asks for it.
        if "enable_thinking" in self.config:
            kwargs["extra_body"] = {
                "enable_thinking": bool(self.config["enable_thinking"]),
            }
        if temperature is not None:
            kwargs["temperature"] = temperature
        response = self._client().chat.completions.create(**kwargs)
        raw = jsonable(response)
        choice = response.choices[0]
        usage = jsonable(getattr(response, "usage", None)) or {}
        return ProviderResult(
            provider=self.provider_name,
            model=str(getattr(response, "model", self.model)),
            text=choice.message.content or "",
            request_id=getattr(response, "id", None),
            usage=usage,
            raw=raw,
        )

    def probe(self) -> dict[str, Any]:
        result = super().probe()
        result["base_url"] = str(self.config["base_url"])
        if not result["api_key_present"]:
            return result
        try:
            models = self._client().models.list()
            ids = {str(getattr(model, "id", "")) for model in models.data}
            result.update(
                network_checked=True,
                available=self.model in ids,
                resolved_model=self.model if self.model in ids else None,
                visible_model_count=len(ids),
            )
        except Exception as exc:  # pragma: no cover - network/account dependent
            result.update(network_checked=True, available=False, error=f"{type(exc).__name__}: {exc}")
        return result
