"""Geometric objective rules for the audit (negative controls / hallucination probes).

These are deterministic, rule-based detectors that run on the real generated
artifacts (the ``pptx/iter_1.pptx``), NOT VLM judgements. On PosterCS's own
clean posters they should fire near-zero (so a VLM that reports the matching
issue is making a false positive); on messy external SOTA output (e.g.
Paper2Poster) the same rules genuinely fire — demonstrating that geometric
detectors transfer while the holistic VLM critic is the unreliable link.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict


# ---------------------------------------------------------------------------
# overlap rule — two element bounding boxes physically intersect.
# ---------------------------------------------------------------------------


def _overlap_ratio(a, b) -> float:
    """Intersection area over the smaller box's area, for boxes (l, t, w, h).

    Returns 0.0 when the boxes do not intersect or either has non-positive area.
    """
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0.0
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    return inter / min(aw * ah, bw * bh)


def _is_collision(a, b, thresh: float = 0.15, containment_max: float = 0.9) -> bool:
    """True iff a and b *partially* overlap (a genuine collision).

    PPTX posters are deeply nested (page bg ⊃ panel cards ⊃ sub-cards / text /
    pictures). Normal nesting gives ``inter/min_area ≈ 1.0`` and must NOT count
    as a defect. A real overlap defect is a *partial* intersection where neither
    box contains the other: ``thresh ≤ inter/min_area < containment_max``.
    """
    r = _overlap_ratio(a, b)
    return thresh <= r < containment_max


def overlap_violations(pptx_path, thresh: float = 0.15) -> List[Dict]:
    """Pairs of shapes on slide 1 that *partially* overlap (genuine collisions).

    Uses python-pptx shape geometry (EMU). Containment (normal nesting) is
    excluded by :func:`_is_collision`. Returns ``{"i", "j", "ratio"}`` records
    (empty = clean). On a well-formed poster this should be ~empty; on messy
    output (overlapping/clipped elements) it fires.
    """
    from pptx import Presentation

    prs = Presentation(str(Path(pptx_path)))
    slide = prs.slides[0]
    boxes = []
    for s in slide.shapes:
        if s.left is None or s.top is None or not s.width or not s.height:
            continue
        boxes.append((int(s.left), int(s.top), int(s.width), int(s.height)))
    out: List[Dict] = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if _is_collision(boxes[i], boxes[j], thresh=thresh):
                out.append({"i": i, "j": j, "ratio": round(_overlap_ratio(boxes[i], boxes[j]), 3)})
    return out
