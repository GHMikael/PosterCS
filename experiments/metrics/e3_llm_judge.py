"""E3 — LLM-as-a-Judge (rubric scoring).

Tier-2 scalable external validation. An LLM scores the rendered poster on a
small rubric (content clarity / visual layout / information delivery), 1–5
each, normalised to [0,1]. **Must be reported alongside its correlation with
E2 human preference** (computed in an analysis script) to be trustworthy.

To avoid surprise API cost it is **gated**: it only calls the model when
``enabled: true`` AND a key is configured; otherwise it skips. Uses the same
OpenAI→SiliconFlow transport as the production VLM commenter.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from experiments.metrics.base import Metric, MetricContext, MetricResult, MetricRegistry

_RUBRIC = """你是严格的学术海报评审。请只看这张海报图,按以下 3 个维度各打 1-5 分(整数):
- content_clarity:核心内容是否清晰传达(贡献/方法/结果一眼能抓住)。
- visual_layout:版面是否整洁、对齐、留白均衡、有视觉重点。
- info_delivery:作为单页视觉摘要,信息密度与可读性是否平衡。
只输出合法 JSON:{"content_clarity":n,"visual_layout":n,"info_delivery":n,"comment":"一句话"}"""


@MetricRegistry.register
class E3LLMJudge(Metric):
    metric_id = "e3_llm_judge"
    description = "LLM-as-a-judge rubric score (normalised); report correlation with E2 separately."

    def compute(self, ctx: MetricContext) -> MetricResult:
        cfg = ctx.config or {}
        if not cfg.get("enabled", False):  # gated OFF by default (API cost)
            return self._skip("disabled (set e3_llm_judge.enabled=true in metrics.yaml to run)")
        if ctx.png_path is None or not ctx.png_path.exists():
            return self._skip("no poster png (soffice render missing)")

        from app.config import DASHSCOPE_API_KEY, QWEN_VL_MODEL
        if not DASHSCOPE_API_KEY:
            return self._skip("no DASHSCOPE_API_KEY")

        try:
            from openai import OpenAI
            from PIL import Image
            from app.vlm_commenter import _extract_json_block, image_to_base64

            model = cfg.get("model") or QWEN_VL_MODEL
            img = Image.open(ctx.png_path).convert("RGB")
            client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url="https://api.siliconflow.cn/v1",
                            timeout=float(os.getenv("POSTER_LLM_TIMEOUT_S", "90")), max_retries=0)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": _RUBRIC},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_to_base64(img)}"}},
                ]}],
                temperature=0.1, max_tokens=400,
                response_format={"type": "json_object"},
            )
            data = _extract_json_block((resp.choices[0].message.content or "").strip()) or {}
        except Exception as exc:
            return self._skip(f"llm judge call failed: {str(exc)[:120]}")

        dims = ["content_clarity", "visual_layout", "info_delivery"]
        vals = [_clamp(data.get(d)) for d in dims]
        if any(v is None for v in vals):
            return self._skip(f"judge returned incomplete rubric: {data}")
        norm = (sum(vals) / len(vals) - 1.0) / 4.0  # 1..5 -> 0..1
        return MetricResult(
            metric_id=self.metric_id,
            score=norm,
            extra={"model": model, **{d: v for d, v in zip(dims, vals)}, "comment": str(data.get("comment", ""))[:200]},
        )


def _clamp(v: Any):
    try:
        return max(1.0, min(5.0, float(v)))
    except (TypeError, ValueError):
        return None
