"""A3 — Semantic Fidelity (BERTScore F1).

New metric in the v5 16-metric scheme (Tier-2, content-fidelity支撑). Measures
how semantically close the poster text is to the paper's reference text
(abstract/first page), as a complement to A1 recall and A2 hallucination.

Why BERTScore (not ROUGE): the poster is a heavy compression/paraphrase of the
paper; surface n-gram overlap (ROUGE) under-rewards valid paraphrase, while
contextual-embedding similarity (BERTScore) tracks meaning. Report rescaled F1.

Additive + not yet wired into compute_metrics._import_all_metrics(): wire it as
part of the Wave-1 refactor (see experiments/scripts/METRIC_REFACTOR_PLAN.md).
First run downloads the BERTScore encoder (roberta-large for en); if the model
is unavailable offline the metric skips cleanly rather than erroring.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from experiments.metrics.base import Metric, MetricContext, MetricResult, MetricRegistry


@MetricRegistry.register
class A3SemanticFidelity(Metric):
    metric_id = "a3_semantic_fidelity"
    description = "BERTScore F1 between poster text and the paper reference text (abstract/first page)."

    def compute(self, ctx: MetricContext) -> MetricResult:
        cfg = ctx.config or {}
        if not cfg.get("enabled", True):
            return self._skip("disabled in metrics.yaml")
        if ctx.panels_json is None:
            return self._skip("no panels_json (opaque baseline)")

        poster_text = _poster_text(ctx.panels_json)
        if not poster_text.strip():
            return self._skip("empty poster text")

        reference = _reference_text(ctx)
        if not reference.strip():
            return self._skip("no reference text (paper missing / unreadable)")

        lang = str((ctx.paper_meta or {}).get("language") or cfg.get("lang") or "en").lower()
        lang = "zh" if lang.startswith("zh") else "en"

        try:
            from bert_score import score as bert_score  # heavy; downloads encoder on first use
        except Exception as exc:  # pragma: no cover
            return self._skip(f"bert_score unavailable: {exc}")

        try:
            _p, _r, f1 = bert_score(
                [poster_text], [reference],
                lang=lang,
                rescale_with_baseline=(lang == "en"),
                verbose=False,
            )
            val = float(f1.mean())
        except Exception as exc:
            # most likely: encoder model could not be downloaded offline
            return self._skip(f"bert_score compute failed (model download?): {str(exc)[:120]}")

        return MetricResult(
            metric_id=self.metric_id,
            score=val,
            extra={"lang": lang, "poster_chars": len(poster_text), "ref_chars": len(reference)},
        )


def _poster_text(panels_json: Dict[str, Any]) -> str:
    parts: List[str] = []
    title = (panels_json or {}).get("poster_title")
    if title:
        parts.append(str(title))
    for p in (panels_json or {}).get("panels", []) or []:
        for b in p.get("content", []) or []:
            s = (b or "").strip()
            if s:
                parts.append(s)
    return " ".join(parts)


def _reference_text(ctx: MetricContext, max_chars: int = 4000) -> str:
    """Reference = paper abstract (heuristic) falling back to first-page text.

    paper_meta.abstract is used if present; otherwise the PDF's first page text
    is read via PyMuPDF and the Abstract→Introduction span is extracted.
    """
    meta = ctx.paper_meta or {}
    if meta.get("abstract"):
        return str(meta["abstract"])[:max_chars]

    if not ctx.paper_path.exists():
        return ""
    try:
        import fitz
        doc = fitz.open(ctx.paper_path)
        try:
            head = "\n".join(doc[i].get_text("text") or "" for i in range(min(2, len(doc))))
        finally:
            doc.close()
    except Exception:
        return ""

    m = re.search(r"abstract\b(.*?)(?:\n\s*1\s+introduction|\bintroduction\b)", head, flags=re.I | re.S)
    span = m.group(1) if m else head
    return re.sub(r"\s+", " ", span).strip()[:max_chars]
