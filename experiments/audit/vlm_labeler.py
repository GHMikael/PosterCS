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

import json
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


__all__ = ["is_enabled", "build_prompt", "build_describe_prompt",
           "build_classify_from_description_prompt", "label_poster", "_normalize_vlm_label"]


# ---------------------------------------------------------------------------
# Prompt — built from the taxonomy gloss so it can never drift from the enums.
# ---------------------------------------------------------------------------


def build_prompt(variant: str = "direct") -> str:
    """Construct the audit critique prompt from the taxonomy definitions.

    ``variant="direct"``: pick the single dominant failure from the N classes.
    ``variant="narrowed"``: evaluate every class as an explicit cue first, then
    aggregate to a primary — tests whether per-class cueing reduces the VLM's
    prior-domination (its tendency to default to one or two labels).
    ``variant="grounded"`` (L2): like narrowed, but each cue judged true must
    also carry a spatial grounding (panel id + region + a measurable property).
    The grounding acts as a commitment cost — hallucinated defects should fail
    to ground. The grounding field is collected in raw output but not read by
    :func:`_normalize_vlm_label` (it is a reasoning scaffold, not a label).
    ``variant="describe_classify"`` (L3): two-stage. Stage 1 elicits a purely
    objective description (no judgment); stage 2 classifies from that
    description + image. Tests whether separating perception from judgment
    recovers reliability. See :func:`label_poster` for the two-call path.
    """

    n_issues = len(REAL_ISSUES)
    n_guards = len(GUARD_VALUES)
    issue_lines = "\n".join(f"- {k} —— {ISSUE_GLOSS[k]}" for k in REAL_ISSUES)
    guard_lines = "\n".join(f"- {k} —— {GUARD_GLOSS[k]}" for k in GUARD_VALUES)
    if variant == "narrowed":
        cue_lines = "\n".join(
            f"- {k}：是否出现「{ISSUE_GLOSS[k]}」？(true/false + 一句图像证据)"
            for k in REAL_ISSUES
        )
        return f"""
你是一个严格的学术海报"版面设计失败"审查助手。下面这张是初始海报。
请**逐项**判断下面 {n_issues} 个线索是否成立，每项给 true/false 和一句图像证据；再综合选出最主要的一项作为 primary_issue。

逐项线索（每条对应一类 issue）：
{cue_lines}

判定规则：
1. primary_issue：上面 {n_issues} 类中最成立、最主要的一类。
   - 若 {n_issues} 类都不成立，填 "none"。
   - 若出现体系没覆盖的新失败类型，填 "other"。
2. secondary_issues：其余成立但非最主要的（取值同 {n_issues} 类，可含 "other"，不要 "none"）。
3. guard_violations：检测到的 guard（仅从 {n_guards} 个 guard 取值）。
4. evidence：对 primary（及主要 secondary）给一句具体图像证据。
5. confidence：0 到 1。

只输出合法 JSON，不要 Markdown，不要解释：
{{
  "primary_issue": "{n_issues}类之一 / other / none",
  "secondary_issues": ["..."],
  "guard_violations": ["..."],
  "evidence": {{"primary": "一句话证据"}},
  "confidence": 0.0到1.0
}}
""".strip()
    if variant == "grounded":
        cue_lines = "\n".join(
            f"- {k}：是否出现「{ISSUE_GLOSS[k]}」？(true/false)"
            for k in REAL_ISSUES
        )
        return f"""
你是一个严格的学术海报"版面设计失败"审查助手。下面这张是初始海报。

【第一步·逐项定位】请**逐项**判断下面 {n_issues} 个线索是否成立。**每一个判 true 的项，必须给出空间定位 grounding**（判 false 的项不需要 grounding）。grounding 三要素缺一不可：
- panel_id：问题出在哪个面板（用面板标题或序号，如 "Results 面板" / "panel 3"）
- region：面板内的大致区域（如 "右侧" / "底部" / "整块"）
- measurable：一个可测量的客观属性（如 "右侧 ~3cm 空白矩形" / "图占面板高约 40%" / "标题与正文基线错位 0.5cm"）
**没有可定位、可测量证据的，一律判 false**——禁止凭印象判 true。

逐项线索（每条对应一类 issue）：
{cue_lines}

【第二步·综合】基于上一步的逐项判断，选出最主要的一项作为 primary_issue。

判定规则：
1. 每项先给 true/false；若 true，必填 grounding（panel_id + region + measurable）。
2. primary_issue：{n_issues} 类中 true 且最主要的一类。
   - 若 {n_issues} 类都判 false（都不成立），填 "none"。
   - 若出现体系没覆盖的新失败类型，填 "other"。
3. secondary_issues：其余 true 但非最主要的（取值同 {n_issues} 类，可含 "other"，不要 "none"）。
4. guard_violations：检测到的 guard（仅从 {n_guards} 个 guard 取值）。
5. evidence：对 primary 给一句具体图像证据（可与 grounding 的 measurable 一致）。
6. confidence：0 到 1。

只输出合法 JSON，不要 Markdown，不要解释：
{{
  "cues": [
    {{"issue": "类名", "present": true/false, "grounding": {{"panel_id": "...", "region": "...", "measurable": "..."}}}}
  ],
  "primary_issue": "{n_issues}类之一 / other / none",
  "secondary_issues": ["..."],
  "guard_violations": ["..."],
  "evidence": {{"primary": "一句话证据"}},
  "confidence": 0.0到1.0
}}
""".strip()
    return f"""
你是一个严格的学术海报"版面设计失败"审查助手。下面这张是 SVFP 修复*之前*的初始海报。
请判断它最主要的版面设计失败属于哪一类，用于验证一套新的失败分类体系。

【{n_issues} 类主问题 issue】（primary_issue 必须从这 {n_issues} 类里选最主要的一类）：
{issue_lines}

【{n_guards} 个 guard】（低频硬约束违规，单独报告，不算主问题）：
{guard_lines}

判定规则：
1. primary_issue：这张海报*最主要*的设计失败，从上面 {n_issues} 类中选一个。
   - 若 {n_issues} 类都明显不适用（出现了体系没覆盖的新失败类型），填 "other"。
   - 若海报版面确实没有明显问题，填 "none"。
2. secondary_issues：其余存在但非最主要的问题，0 个或多个，取值同样来自 {n_issues} 类（可含 "other"，但不要含 "none"）。
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
# L3 (describe_classify) — two-stage prompts. Stage 1 elicits a purely
# objective description (perception only, no judgment); stage 2 classifies
# from that description + image. label_poster() runs the two calls in sequence.
# ---------------------------------------------------------------------------


def build_describe_prompt() -> str:
    """Stage 1 of the describe_classify variant — pure perception, no judgment.

    The model must inventory the poster objectively (panels, density, figure
    sizes, blank rectangles, grid alignment) WITHOUT naming any defect class.
    Output is a JSON description, not a label.
    """

    return """
你是一个客观的学术海报"版面测量员"。下面这张是初始海报。你的任务是**只描述、不评判**——把海报的版面事实 inventory 出来，禁止判断任何"好不好""有没有问题"。

请客观描述以下各项（能测量的给数字/估测，不能测量的给定性）：
1. 面板清单：海报有几个面板？每个面板的标题/位置（如左上/右下）。
2. 内容密度：每个面板的文字量（密/中/松）、bullet 条数。
3. 图：哪些面板有图？图相对所在面板的尺寸（图占面板宽约 X%、高约 Y%）？图是否清晰可读？
4. 空白区域：是否存在矩形空白区域？在哪个面板的哪个方位？大约多大（估测 cm 或占面板比例）？
5. 网格对齐：面板之间是否对齐？有没有某列/某行明显错位、宽窄不一、或一边留白？

只输出合法 JSON，不要 Markdown，不要解释，不要在 JSON 之外写任何文字：
{
  "n_panels": 数字,
  "panels": [
    {"id": "面板标题或序号", "position": "左上/右下/...", "density": "密/中/松", "n_bullets": 数字或null, "has_figure": true/false, "figure_size": "图占面板宽约X%高约Y%或null", "notes": "其它客观事实"}
  ],
  "blank_regions": [{"panel_id": "...", "where": "...", "approx_size": "..."}],
  "grid_alignment": "对齐良好 / 某列错位 / 右侧整块留白 / ...",
  "overall": "一句话客观总结，不含评判"
}
""".strip()


def build_classify_from_description_prompt() -> str:
    """Stage 2 of describe_classify — classify from the stage-1 description.

    Filled at call time with the stage-1 description JSON. The classifier is
    told to base its judgment on the description above (plus the image).
    """

    n_issues = len(REAL_ISSUES)
    n_guards = len(GUARD_VALUES)
    issue_lines = "\n".join(f"- {k} —— {ISSUE_GLOSS[k]}" for k in REAL_ISSUES)
    guard_lines = "\n".join(f"- {k} —— {GUARD_GLOSS[k]}" for k in GUARD_VALUES)
    return f"""
你是一个严格的学术海报"版面设计失败"审查助手。下面这张是初始海报。

【你上一步对该海报的客观描述（请基于此判断）】：
{{DESCRIPTION}}

【{n_issues} 类主问题 issue】（primary_issue 必须从这 {n_issues} 类里选最主要的一类）：
{issue_lines}

【{n_guards} 个 guard】（低频硬约束违规，单独报告，不算主问题）：
{guard_lines}

判定规则：
1. primary_issue：基于上面的客观描述，这张海报*最主要*的设计失败，从 {n_issues} 类中选一个。
   - 若描述里没有任何一类成立的事实，填 "none"。
   - 若出现了体系没覆盖的新失败类型，填 "other"。
2. secondary_issues：其余成立但非最主要的问题（取值同 {n_issues} 类，可含 "other"，不要 "none"）。
3. guard_violations：检测到的 guard 违规（0 个或多个），仅从 {n_guards} 个 guard 取值。
4. evidence：对 primary 给一句具体证据，优先引用上面描述里的客观事实。
5. confidence：0 到 1。

只输出合法 JSON，不要 Markdown，不要解释，不要在 JSON 之外写任何文字：
{{
  "primary_issue": "{n_issues}类之一 / other / none",
  "secondary_issues": ["..."],
  "guard_violations": ["..."],
  "evidence": {{"primary": "一句话证据"}},
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


def _error_stub(run_id: str, model: str, pass_idx: int, source: str, notes: str, content: str = "") -> Dict[str, Any]:
    """Neutral stub returned on transport/parse failure so the batch keeps going."""
    stub: Dict[str, Any] = {
        "run_id": run_id,
        "labeler": f"vlm:{model}#pass{pass_idx}",
        "primary_issue": AuditIssueType.NONE.value,
        "secondary_issues": [],
        "guard_violations": [],
        "evidence": {},
        "confidence": None,
        "source": source,
        "notes": notes,
    }
    if content:
        stub["raw_content"] = content[:2000]
    return stub


def _call_vlm(client: Any, model: str, text: str, image_b64: str, *, temperature: float) -> str:
    """One VLM call with JSON mode + fallback. Returns raw content text.

    Raises on transport failure so callers can catch and produce an error stub.
    """
    kwargs: Dict[str, Any] = dict(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
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
    return (resp.choices[0].message.content or "").strip()


def label_poster(
    png_path: Path,
    *,
    model: Optional[str] = None,
    temperature: float = 0.1,
    run_id: str = "",
    pass_idx: int = 0,
    variant: str = "direct",
    experiment_logger: Optional[Any] = None,
) -> Dict[str, Any]:
    """Label one initial-poster PNG with the new audit taxonomy.

    Returns an audit label record (see module docstring). Never raises on
    transport failure: a neutral stub with ``source`` in
    ``{"disabled", "vlm_error", "vlm_unparsed"}`` is returned instead, so the
    batch driver can keep going and the analysis can filter by ``source``.

    ``variant="describe_classify"`` runs two sequential VLM calls: stage 1
    elicits a pure objective description, stage 2 classifies from that
    description + image.
    """

    model = model or QWEN_VL_MODEL
    if not DASHSCOPE_API_KEY:
        return _disabled_stub(run_id, model, pass_idx)

    png_path = Path(png_path)
    try:
        from openai import OpenAI
        from PIL import Image

        image = Image.open(png_path).convert("RGB")
        image_b64 = image_to_base64(image)
        # describe_classify does 2 sequential calls (~85s observed on 32B);
        # give it a wider per-call timeout than the single-call variants.
        default_timeout = "180" if variant == "describe_classify" else "60"
        timeout_s = float(os.getenv("POSTER_LLM_TIMEOUT_S", default_timeout))
        client = OpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url="https://api.siliconflow.cn/v1",
            timeout=timeout_s,
            max_retries=0,
        )

        if variant == "describe_classify":
            # Stage 1 — objective description (perception only).
            desc_text = _call_vlm(client, model, build_describe_prompt(), image_b64, temperature=temperature)
            desc_data = _extract_json_block(desc_text)
            description_str = desc_text if desc_data is None else json.dumps(desc_data, ensure_ascii=False)

            # Stage 2 — classify from the description + image.
            classify_prompt = build_classify_from_description_prompt().replace("{DESCRIPTION}", description_str)
            content = _call_vlm(client, model, classify_prompt, image_b64, temperature=temperature)
            data = _extract_json_block(content)

            if experiment_logger is not None:
                try:
                    experiment_logger.log_llm_call(
                        stage="audit_taxonomy_label",
                        model=model,
                        prompt_tokens=0, completion_tokens=0, latency_ms=0.0,
                        raw_response={"content": content[:4000], "parsed": data,
                                      "stage1_description": description_str[:2000]},
                        retries=0,
                    )
                except Exception:
                    pass

            if data is None:
                return _error_stub(run_id, model, pass_idx, "vlm_unparsed",
                                   (content[:300] or "VLM returned empty content."), content)
            norm = _normalize_vlm_label(data)
            return {
                "run_id": run_id,
                "labeler": f"vlm:{model}#pass{pass_idx}",
                **norm,
                "source": "vlm",
                "notes": "",
                "raw_content": content[:2000],
                "stage1_description": description_str[:2000],
            }

        # Single-call variants: direct / narrowed / grounded.
        content = _call_vlm(client, model, build_prompt(variant), image_b64, temperature=temperature)
        data = _extract_json_block(content)

        if experiment_logger is not None:
            usage = getattr(client, "usage", None)  # placeholder; real usage lives on resp (kept simple for compat)
            try:
                experiment_logger.log_llm_call(
                    stage="audit_taxonomy_label",
                    model=model,
                    prompt_tokens=0, completion_tokens=0, latency_ms=0.0,
                    raw_response={"content": content[:4000], "parsed": data},
                    retries=0,
                )
            except Exception:
                pass

        if data is None:
            return _error_stub(run_id, model, pass_idx, "vlm_unparsed",
                               (content[:300] or "VLM returned empty content."), content)

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
        return _error_stub(run_id, model, pass_idx, "vlm_error", f"{type(exc).__name__}: {exc}")
