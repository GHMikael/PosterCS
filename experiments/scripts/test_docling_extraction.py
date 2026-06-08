"""Compare fitz (current) vs docling (new) figure extraction on sample PDFs.

Shows the concrete win: docling should capture vector figures + tables that
fitz's raw-image extraction misses (especially on method/theory papers).

Run (from PosterCS root):
    unset VIRTUAL_ENV && .venv/bin/python -m experiments.scripts.test_docling_extraction
"""

import sys
import time
from pathlib import Path

from app.pdf_assets import extract_pdf_assets_from_bytes
from app.docling_assets import extract_pdf_assets_docling

DEFAULT_PDFS = [
    "datasets/papers/多智能体推理_4F96FB.pdf",
    "datasets/papers/LLM评估_FC7CBC.pdf",
    "datasets/papers/上下文工程_2F73CE.pdf",
]


def main():
    pdfs = sys.argv[1:] or DEFAULT_PDFS
    print(f"{'paper':40} | {'fitz':>14} | {'docling':>26}")
    print("-" * 88)
    for p in pdfs:
        path = Path(p)
        if not path.exists():
            print(f"{path.name:40} | MISSING")
            continue
        pb = path.read_bytes()

        t0 = time.time()
        try:
            _, ffigs = extract_pdf_assets_from_bytes(pb)
            fitz_s = f"{len(ffigs):2d} ({time.time()-t0:.1f}s)"
        except Exception as e:
            fitz_s = f"ERR {str(e)[:30]}"

        t0 = time.time()
        try:
            _, dfigs = extract_pdf_assets_docling(pdf_bytes=pb)
            n_tab = sum(1 for f in dfigs.values() if "table" in f.extraction_note)
            n_cap = sum(1 for f in dfigs.values() if f.caption)
            docling_s = f"{len(dfigs):2d} (tbl={n_tab} cap={n_cap}) ({time.time()-t0:.1f}s)"
        except Exception as e:
            docling_s = f"ERR {str(e)[:40]}"

        print(f"{path.name:40} | {fitz_s:>14} | {docling_s:>26}")

    print("\nInterpretation: docling > fitz (esp. tables + vector figures) ⇒ adopt docling")
    print("as primary in app/pdf_assets.py with fitz as fallback.")


if __name__ == "__main__":
    main()
