from __future__ import annotations

from typing import Any

from .qwen_provider import QwenProvider


class GLMProvider(QwenProvider):
    """Zhipu OpenAI-compatible vision provider.

    GLM and Qwen share the same request envelope in this experiment, but they
    remain separate providers in logs and analysis.  Some free GLM vision
    models are callable even when the account's /models response omits them,
    so a successful image probe can be recorded explicitly in models.yaml.
    """

    provider_name = "glm"

    def probe(self) -> dict[str, Any]:
        result = super().probe()
        if not result.get("available") and self.config.get("image_probe_verified"):
            result.update(
                available=True,
                resolved_model=self.model,
                availability_basis="successful_image_probe",
            )
        return result
