"""VLM auto-labeler for the new SVFP audit taxonomy (P0).

Given an *initial* poster PNG (pre-SVFP render), ask the configured VLM to
classify its dominant design failure into the new 5-class taxonomy + guards
defined in :mod:`experiments.audit.taxonomy`, and return a structured audit
*label* record.

This deliberately reuses the production VLM transport from
:mod:`app.vlm_commenter` — the same OpenAI→SiliconFlow client, the same
``image_to_base64`` encoder, and the same robust ``_extract_json_block``
recovery — so the audit talks to exactly the model the system uses. Only the
*prompt* and the *output vocabulary* differ. No production code is modified.

The raw VLM JSON is coerced into a valid audit label by
:func:`_normalize_vlm_label`, which is pure and offline-testable: it maps any
legacy 4-class strings the small model might still emit onto the new taxonomy
and drops anything unrecognised to ``other`` (so ``other_rate`` stays honest).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Reuse production transport + helpers (read-only; nothing here mutates app/).
from app.config import DASHSCOPE_API_KEY, QWEN_VL_MODEL
from app.vlm_commenter import _extract_json_block, image_to_base64

from experiments.audit.taxonomy import (
    GUARD_GLOSS,
    GUARD_VALUES,
    ISSUE_GLOSS,
    OLD_TO_NEW,
    PRIMARY_ISSUE_VALUES,
    REAL_ISSUES,
    SECONDARY_ISSUE_VALUES,
    AuditIssueType,
)


__all__ = ["is_enabled", "build_prompt", "label_poster", "_normalize_vlm_label"]


# ---------------------------------------------------------------------------
# Prompt — built from the taxonomy gloss so it can never drift from the enums.
# ---------------------------------------------------------------------------


def build_prompt() -> str:
    """Construct the audit critique prompt from the taxonomy definitions."""

    issue_lines = "\n".join(f"- {k} —— {ISSUE_GLOSS[k]}" for k in REAL_ISSUES)
    guard_lines = "\n".join(f"- {k} —— {GUARD_GLOSS[k]}" for k in GUARD_VALUES)
    return f"""
你是一个严格的学术海报"版面设计失败"审查助手。下面这张是 SVFP 修复*之前*的初始海报。
请判断它最主要的版面设计失败属于哪一类，用于验证一套新的失败分类体系。

【5 类主问题 issue】（primary_issue 必须从这 5 类里选最主要的一类）：
{issue_lines}

【4 个 guard】（低频硬约束违规，单独报告，不算主问题）：
{guard_lines}

判定规则：
1. primary_issue：这张海报*最主要*的设计失败，从上面 5 类中选一个。
   - 若 5 类都明显不适用（出现了体系没覆盖的新失败类型），填 "other"。
   - 若海报版面确实没有明显问题，填 "none"。
2. secondary_issues：其余存在但非最主要的问题，0 个或多个，取值同样来自 5 类（可含 "other"，但不要含 "none"）。
3. guard_violations：检测到的 guard 违规（0 个或多个），仅从 4 个 guard 取值。
4. evidence：对 primary（以及主要 secondary）给一句具体的图像观察证据。
5. confidence：你对 primary_issue 判断的置信度，0 到 1 的小数。

只输出合法 JSON，不要 Markdown，不要解释，不要在 JSON 之外写任何文字。
JSON schema:
{{
  "primary_issue": "5类之一 / other / none",
  "secondary_issues": ["..."],
  "guard_violations": ["..."],
  "evidence": {{"primary": "一句话证据", "...": "..."}},
  "confidence": 0.0到1.0
}}
""".strip()


# ---------------------------------------------------------------------------
# Coercion — turn whatever the model said into a valid audit label.
# ---------------------------------------------------------------------------


def _coerce_one_issue(value: Any) -> Optional[str]:
    """Map a single raw issue string onto a real new-taxonomy issue.

    Returns a value in :data:`REAL_ISSUES`, or ``"other"`` for unmappable
    labels, or ``None`` if the string named a *guard* (so the caller can move
    it to the guard track) or was empty.
    """

    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in REAL_ISSUES:
        return text
    if text == AuditIssueType.OTHER.value:
        return AuditIssueType.OTHER.value
    if text == AuditIssueType.NONE.value:
        return None
    # Legacy 4-class string the small model may still emit.
    mapped = OLD_TO_NEW.get(text)
    if mapped is not None:
        if mapped["kind"] == "guard":
            return None  # belongs on the guard track, not the issue track
        return mapped["maps_to"]
    if text in GUARD_VALUES:
        return None  # a guard named where an issue was expected
    return AuditIssueType.OTHER.value


def _coerce_guard(value: Any) -> Optional[str]:
    """Map a single raw guard string onto a known guard value, or None."""

    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in GUARD_VALUES:
        return text
    mapped = OLD_TO_NEW.get(text)
    if mapped is not None and mapped["kind"] == "guard":
        return mapped["maps_to"]
    return None


def _normalize_vlm_label(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce a raw VLM JSON dict into valid audit-label fields.

    Pure and offline-testable. Always returns a dict with keys
    ``primary_issue`` / ``secondary_issues`` / ``guard_violations`` /
    ``evidence`` / ``confidence``. Any legacy or invalid labels are mapped or
    dropped so the result passes :func:`experiments.audit.taxonomy.validate_label`.
    """

    if not isinstance(raw, dict):
        raw = {}

    guards: List[str] = []

    # --- guard track (collect first; issue coercion may feed into it) ---
    for g in raw.get("guard_violations", []) or []:
        cg = _coerce_guard(g)
        if cg:
            guards.append(cg)

    # --- primary ---
    raw_primary = str(raw.get("primary_issue", "") or "").strip().lower()
    primary: str
    if raw_primary == AuditIssueType.NONE.value:
        primary = AuditIssueType.NONE.value
    else:
        coerced = _coerce_one_issue(raw_primary)
        if coerced is None:
            # The model put a guard (or empty) in the primary slot.
            gg = _coerce_guard(raw_primary)
            if gg:
                guards.append(gg)
            primary = AuditIssueType.OTHER.value if raw_primary else AuditIssueType.NONE.value
        else:
            primary = coerced

    # --- secondary ---
    secondary: List[str] = []
    for s in raw.get("secondary_issues", []) or []:
        cs = _coerce_one_issue(s)
        if cs is None:
            gg = _coerce_guard(s)
            if gg:
                guards.append(gg)
            continue
        if cs in SECONDARY_ISSUE_VALUES and cs != primary and cs not in secondary:
            secondary.append(cs)

    # --- evidence / confidence ---
    evidence = raw.get("evidence")
    if isinstance(evidence, str):
        evidence = {"primary": evidence}
    elif not isinstance(evidence, dict):
        evidence = {}

    confidence = raw.get("confidence")
    try:
        confidence = max(0.0, min(1.0, float(confidence))) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None

    # dedupe guards, preserve order
    guards = list(dict.fromkeys(guards))

    return {
        "primary_issue": primary,
        "secondary_issues": secondary,
        "guard_violations": guards,
        "evidence": evidence,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# The labeling call.
# ---------------------------------------------------------------------------


def is_enabled() -> bool:
    """True when a VLM API key is configured (else the labeler is a stub)."""

    return bool(DASHSCOPE_API_KEY)


def _disabled_stub(run_id: str, model: str, pass_idx: int) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "labeler": f"vlm:{model}#pass{pass_idx}",
        "primary_issue": AuditIssueType.NONE.value,
        "secondary_issues": [],
        "guard_violations": [],
        "evidence": {},
        "confidence": None,
        "source": "disabled",
        "notes": "VLM labeler disabled because DASHSCOPE_API_KEY is empty.",
    }


def label_poster(
    png_path: Path,
    *,
    model: Optional[str] = None,
    temperature: float = 0.1,
    run_id: str = "",
    pass_idx: int = 0,
    experiment_logger: Optional[Any] = None,
) -> Dict[str, Any]:
    """Label one initial-poster PNG with the new audit taxonomy.

    Returns an audit label record (see module docstring). Never raises on
    transport failure: a neutral stub with ``source`` in
    ``{"disabled", "vlm_error", "vlm_unparsed"}`` is returned instead, so the
    batch driver can keep going and the analysis can filter by ``source``.
    """

    model = model or QWEN_VL_MODEL
    if not DASHSCOPE_API_KEY:
        return _disabled_stub(run_id, model, pass_idx)

    png_path = Path(png_path)
    try:
        from openai import OpenAI
        from PIL import Image

        image = Image.open(png_path).convert("RGB")
        timeout_s = float(os.getenv("POSTER_LLM_TIMEOUT_S", "60"))
        client = OpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url="https://api.siliconflow.cn/v1",
            timeout=timeout_s,
            max_retries=0,
        )
        kwargs: Dict[str, Any] = dict(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": build_prompt()},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_to_base64(image)}"},
                        },
                    ],
                }
            ],
            temperature=temperature,
            max_tokens=800,
        )
        strict_json = os.getenv("POSTER_VLM_JSON_MODE", "1") != "0"
        allow_fallback = os.getenv("POSTER_VLM_ALLOW_FALLBACK", "0") == "1"
        try:
            if strict_json:
                resp = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
            else:
                resp = client.chat.completions.create(**kwargs)
        except Exception:
            if not allow_fallback or not strict_json:
                raise
            resp = client.chat.completions.create(**kwargs)

        content = (resp.choices[0].message.content or "").strip()
        data = _extract_json_block(content)

        if experiment_logger is not None:
            usage = getattr(resp, "usage", None)
            try:
                experiment_logger.log_llm_call(
                    stage="audit_taxonomy_label",
                    model=model,
                    prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                    completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                    latency_ms=0.0,
                    raw_response={"content": content[:4000], "parsed": data},
                    retries=0,
                )
            except Exception:
                pass

        if data is None:
            return {
                "run_id": run_id,
                "labeler": f"vlm:{model}#pass{pass_idx}",
                "primary_issue": AuditIssueType.NONE.value,
                "secondary_issues": [],
                "guard_violations": [],
                "evidence": {},
                "confidence": None,
                "source": "vlm_unparsed",
                "notes": (content[:300] or "VLM returned empty content."),
                "raw_content": content[:2000],
            }

        norm = _normalize_vlm_label(data)
        return {
            "run_id": run_id,
            "labeler": f"vlm:{model}#pass{pass_idx}",
            **norm,
            "source": "vlm",
            "notes": "",
            "raw_content": content[:2000],
        }
    except Exception as exc:  # transport/parse failure → neutral stub, keep going
        return {
            "run_id": run_id,
            "labeler": f"vlm:{model}#pass{pass_idx}",
            "primary_issue": AuditIssueType.NONE.value,
            "secondary_issues": [],
            "guard_violations": [],
            "evidence": {},
            "confidence": None,
            "source": "vlm_error",
            "notes": f"{type(exc).__name__}: {exc}",
        }
