"""docling-based PDF asset extraction (figures + tables) for PosterCS.

Why: ``app/pdf_assets.py`` extracts raw embedded raster images via PyMuPDF
(``fitz.get_images``), which **misses vector figures** (matplotlib/TikZ — very
common in CS papers) and **tables** (text + lines, not rasters), then
over-filters tiny fragments. docling segments each page semantically with a
layout model, so every figure/table is captured as one rendered region
regardless of how it is stored in the PDF — fixing both "vector figures lost"
and "tables never captured".

Mirrors Paper2Poster ``PosterAgent/parse_raw.py`` (local ModelScope model
path, OCR off, the torch.compiler patch) and returns the **same shape** as
``extract_pdf_assets_from_bytes``::

    (text_preview, Dict[figure_id -> ExtractedFigure])

so it is a drop-in primary path with the fitz extractor as fallback. The
converter (heavy) is built lazily and cached.
"""

from __future__ import annotations

import io
import os
import re
from typing import Dict, Optional, Tuple

from app.image_utils import pil_to_data_url
from app.models import ExtractedFigure

_CONVERTER = None  # lazy singleton (loading docling models is expensive)


def _clean_text(text: str, max_len: int = 12000) -> str:
    text = re.sub(r"<!--[\s\S]*?-->", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _build_converter():
    """Construct (once) a docling DocumentConverter pinned to local ModelScope
    artifacts with OCR disabled. Mirrors Paper2Poster parse_raw.py exactly."""
    global _CONVERTER
    if _CONVERTER is not None:
        return _CONVERTER

    import torch
    # torch 2.1.2 lacks torch.compiler.is_compiling, which transformers' RTDetr
    # layout model calls; patch a False stub (same as parse_raw.py).
    if not hasattr(torch.compiler, "is_compiling"):
        torch.compiler.is_compiling = lambda *a, **k: False

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    # docling-ibm-models 3.13 expects the *newer* layout model; the old ModelScope
    # cache (…/docling-models/model_artifacts/layout) is an incompatible format
    # ("Missing safe tensors file"). By default let docling fetch/cache its own
    # model from HF (reachable via the proxy — bert_score downloads work). Set
    # DOCLING_ARTIFACTS_PATH to a *new-format* artifacts dir to override.
    artifacts = os.getenv("DOCLING_ARTIFACTS_PATH")
    if artifacts and os.path.isdir(artifacts):
        opts.artifacts_path = artifacts
    opts.images_scale = float(os.getenv("DOCLING_IMAGE_SCALE", "2.0"))
    opts.generate_page_images = True       # tables crop from the page image
    opts.generate_picture_images = True
    opts.do_ocr = False                    # text PDFs; skip slow easyocr download

    _CONVERTER = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    return _CONVERTER


def _bbox_list(prov) -> list:
    try:
        bb = prov.bbox
        return [round(float(x), 2) for x in (bb.l, bb.t, bb.r, bb.b)]
    except Exception:
        return []


def extract_pdf_assets_docling(
    pdf_bytes: Optional[bytes] = None,
    *,
    pdf_path: Optional[str] = None,
    min_px: int = 40,
) -> Tuple[str, Dict[str, ExtractedFigure]]:
    """Extract figures + tables via docling. Pass either ``pdf_bytes`` or
    ``pdf_path``.

    Returns ``(text_preview, figures)`` matching
    :func:`app.pdf_assets.extract_pdf_assets_from_bytes`. Raises on
    docling/transport failure so callers can fall back to the fitz extractor.
    """
    from docling_core.types.doc import PictureItem, TableItem

    converter = _build_converter()

    if pdf_path:
        source = pdf_path
    elif pdf_bytes is not None:
        from docling.datamodel.base_models import DocumentStream
        source = DocumentStream(name="paper.pdf", stream=io.BytesIO(pdf_bytes))
    else:
        raise ValueError("provide pdf_bytes or pdf_path")

    conv = converter.convert(source)
    doc = conv.document

    figures: Dict[str, ExtractedFigure] = {}
    idx = 1
    for element, _level in doc.iterate_items():
        if not isinstance(element, (PictureItem, TableItem)):
            continue
        try:
            pil = element.get_image(doc)
        except Exception:
            pil = None
        if pil is None:
            continue
        pil = pil.convert("RGB")
        if pil.width < min_px or pil.height < min_px:
            continue
        prov = element.prov[0] if getattr(element, "prov", None) else None
        page_no = int(getattr(prov, "page_no", 0) or 0) if prov else 0
        try:
            caption = element.caption_text(doc) or ""
        except Exception:
            caption = ""
        kind = "table" if isinstance(element, TableItem) else "picture"
        fig_id = f"Fig{idx}"
        figures[fig_id] = ExtractedFigure(
            figure_id=fig_id,
            caption=_clean_text(caption, 300),
            page=page_no,
            width=pil.width,
            height=pil.height,
            image_source=pil_to_data_url(pil, fmt="PNG", max_width=1200),
            source_xref=0,
            bbox=_bbox_list(prov) if prov else [],
            extraction_note=f"docling_{kind}",
        )
        idx += 1

    text_preview = _clean_text(doc.export_to_markdown(), 12000)
    return text_preview, figures
