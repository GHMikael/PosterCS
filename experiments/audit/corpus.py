"""Locate and bundle the P0 audit corpus: initial-poster PNGs + their plans.

The corpus is the set of **pre-SVFP initial renders** (``iter_1.png``) produced
by the predecessor system ``poster_agent_backend`` — which is a 1:1 code copy
of the current PosterCS renderer (see ``MIGRATION_REPORT.md``), so these images
are representative of the renderer the paper evaluates.

For each run we collect:

* ``png_path``    — the initial render to feed the VLM labeler;
* ``plan``        — the ``input`` PosterTask, for cheap plan-derived proxies;
* ``old_issues_initial`` — the legacy 4-class issues the production VLM flagged
  on *this very initial poster* (iteration 1's feedback), mined for the
  "overlap/contrast are low-frequency" evidence — free, no API calls.

Nothing here calls a network or mutates state; it only reads run artifacts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import PROJECT_ROOT


__all__ = [
    "CorpusItem",
    "default_runs_dir",
    "find_run_dirs",
    "load_item",
    "load_corpus",
    "plan_proxies",
    "old_initial_issues",
]


def default_runs_dir() -> Path:
    """Default corpus location: PosterCS's own run archive.

    ``.../PosterCS/outputs/runs`` — where the *current* pipeline writes runs
    (see ``app.run_archive.RUNS_ROOT``). The predecessor system's archive
    (``../poster_agent_backend/outputs/runs``) is no longer the default; audit
    that older corpus explicitly with ``--runs-dir`` when needed.

    No silent fallback: if this dir is empty (e.g. the new batch hasn't been
    generated yet) the caller gets zero items rather than stale predecessor data.
    """

    return PROJECT_ROOT / "outputs" / "runs"


@dataclass
class CorpusItem:
    """One initial poster + everything the audit needs about it."""

    run_id: str
    paper_title: str
    template: str
    png_path: Path
    run_dir: Path
    plan: Optional[Dict[str, Any]] = None
    old_issues_initial: List[str] = field(default_factory=list)
    proxies: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "paper_title": self.paper_title,
            "template": self.template,
            "png_path": str(self.png_path),
            "run_dir": str(self.run_dir),
            "old_issues_initial": self.old_issues_initial,
            "proxies": self.proxies,
        }


def find_run_dirs(runs_dir: Path) -> List[Path]:
    """Return run subfolders that contain a usable initial poster.

    A folder qualifies if it has any ``iter_1.png`` (at any depth) or a
    ``run_report.json``. Sorted for deterministic ordering.
    """

    runs_dir = Path(runs_dir)
    if not runs_dir.exists():
        return []
    out: List[Path] = []
    for d in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        if any(d.glob("**/iter_1.png")) or (d / "run_report.json").exists():
            out.append(d)
    return out


def _first_png(run_dir: Path) -> Optional[Path]:
    """Locate the initial-poster PNG (prefer iter_1.png, then poster.png)."""

    for pat in ("**/iter_1.png", "**/poster.png", "**/iter_01.png"):
        hits = sorted(run_dir.glob(pat))
        if hits:
            return hits[0]
    return None


def _read_report(run_dir: Path) -> Optional[Dict[str, Any]]:
    rp = run_dir / "run_report.json"
    if not rp.exists():
        return None
    try:
        return json.loads(rp.read_text(encoding="utf-8"))
    except Exception:
        return None


def old_initial_issues(report: Optional[Dict[str, Any]]) -> List[str]:
    """Legacy 4-class issues flagged on the *initial* poster (iteration 1).

    Pulls ``global_issues`` and every panel's ``issues`` from the first
    iteration's feedback. Returns a flat list (with multiplicity) of legacy
    issue strings; empty when no report / no first-iteration feedback.
    """

    if not report:
        return []
    iterations = report.get("iterations") or []
    if not iterations:
        return []
    fb = iterations[0].get("feedback") or {}
    issues: List[str] = list(fb.get("global_issues") or [])
    for panel in fb.get("panel_feedback") or []:
        issues.extend(panel.get("issues") or [])
    return [str(i).strip().lower() for i in issues if str(i).strip()]


def plan_proxies(plan: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Cheap, API-free signals derived from the PosterTask plan.

    These corroborate (or contradict) the VLM's visual labels — e.g. a high
    ``mean_bullets_per_panel`` next to a "no text_overload" label is surfaced
    in the MECE audit as a disagreement worth checking.
    """

    if not isinstance(plan, dict):
        return {}
    panels = plan.get("panels") or []
    n_panels = len(panels)
    if n_panels == 0:
        return {"n_panels": 0}

    bullets_per_panel = [len(p.get("content") or []) for p in panels]
    chars_per_panel = [
        sum(len(str(b)) for b in (p.get("content") or [])) for p in panels
    ]
    figures = plan.get("figures") or {}
    n_panels_with_fig = sum(
        1 for p in panels if (p.get("figure_id") or p.get("figure"))
    )
    n_text_only = sum(1 for p in panels if (p.get("layout_hint") == "text_only"))

    total_bullets = sum(bullets_per_panel)
    return {
        "n_panels": float(n_panels),
        "total_bullets": float(total_bullets),
        "mean_bullets_per_panel": round(total_bullets / n_panels, 3),
        "max_bullets_per_panel": float(max(bullets_per_panel)),
        "mean_chars_per_panel": round(sum(chars_per_panel) / n_panels, 1),
        "max_chars_per_panel": float(max(chars_per_panel)),
        "n_figures_available": float(len(figures)),
        "n_panels_with_figure": float(n_panels_with_fig),
        "figure_usage_ratio": round(n_panels_with_fig / n_panels, 3),
        "text_only_panel_ratio": round(n_text_only / n_panels, 3),
    }


def load_item(run_dir: Path) -> Optional[CorpusItem]:
    """Build a :class:`CorpusItem` for one run folder, or None if no PNG."""

    run_dir = Path(run_dir)
    png = _first_png(run_dir)
    if png is None:
        return None
    report = _read_report(run_dir)
    plan = (report or {}).get("input") if report else None

    run_id = ""
    paper_title = ""
    template = ""
    if report:
        run_id = str(report.get("run_id") or "")
        plan = report.get("input") or None
    if plan:
        paper_title = str(plan.get("poster_title") or "")
        template = str(plan.get("template") or "")
    if not run_id:
        run_id = run_dir.name

    return CorpusItem(
        run_id=run_id,
        paper_title=paper_title,
        template=template,
        png_path=png,
        run_dir=run_dir,
        plan=plan,
        old_issues_initial=old_initial_issues(report),
        proxies=plan_proxies(plan),
    )


def load_corpus(runs_dir: Optional[Path] = None, *, limit: Optional[int] = None) -> List[CorpusItem]:
    """Load all usable corpus items from ``runs_dir`` (default: PosterCS ``outputs/runs``)."""

    runs_dir = Path(runs_dir) if runs_dir else default_runs_dir()
    items: List[CorpusItem] = []
    for d in find_run_dirs(runs_dir):
        item = load_item(d)
        if item is not None:
            items.append(item)
        if limit and len(items) >= limit:
            break
    return items
