"""P0 driver: label every initial poster with the new audit taxonomy.

Separates *labeling* (this script, may hit the VLM API) from *analysis*
(``analysis_issue_distribution.py`` / ``analysis_issue_mece_audit.py``, pure),
mirroring the run_matrix → compute_metrics split.

Usage::

    .venv/bin/python -m experiments.scripts.audit_label_posters --limit 3      # smoke
    .venv/bin/python -m experiments.scripts.audit_label_posters                # all
    .venv/bin/python -m experiments.scripts.audit_label_posters --passes 2     # auto-κ track
    .venv/bin/python -m experiments.scripts.audit_label_posters --dry-run      # no API

Outputs (under ``--out``, default ``experiments/results/audit``):

* ``labels/<run_id>.json`` — one file per poster: corpus meta + a list of
  per-pass VLM label records;
* ``human_label_template.csv`` — prefilled with the pass-0 VLM guess, for
  optional human adjudication (gold track → real Cohen's κ).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

from experiments.audit import corpus as corpus_mod
from experiments.audit import vlm_labeler

#: Per-pass sampling temperatures (pass 0 is the deterministic primary read).
_PASS_TEMPS = [0.1, 0.6, 0.9, 0.4]


def _safe_stem(item: "corpus_mod.CorpusItem") -> str:
    """Filesystem-safe, unique stem for a per-poster label file."""

    base = item.run_id or item.run_dir.name
    stem = re.sub(r"[^0-9A-Za-z._-]+", "_", base).strip("_")
    return stem or "run"


def _write_human_template(path: Path, rows: List[dict]) -> None:
    cols = [
        "run_id", "paper_title", "template", "png_path",
        "vlm_primary", "vlm_secondary", "vlm_guards",
        "human_primary", "human_secondary", "human_guards", "human_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="P0: label initial posters with the new audit taxonomy.")
    p.add_argument("--runs-dir", type=Path, default=None,
                   help="Run archive to audit (default: PosterCS outputs/runs; pass the predecessor "
                        "poster_agent_backend/outputs/runs to re-audit the old corpus).")
    p.add_argument("--out", type=Path, default=Path("experiments/results/audit"))
    p.add_argument("--limit", type=int, default=0, help="Label only the first N posters (smoke).")
    p.add_argument("--passes", type=int, default=1, help="Independent VLM passes per poster (>=2 enables auto-κ).")
    p.add_argument("--model", default=None, help="Override the VLM model id.")
    p.add_argument("--dry-run", action="store_true", help="Load corpus only; no VLM calls.")
    args = p.parse_args(argv)

    runs_dir = args.runs_dir or corpus_mod.default_runs_dir()
    items = corpus_mod.load_corpus(runs_dir, limit=(args.limit or None))
    print(f"[audit_label_posters] runs_dir={runs_dir}")
    print(f"[audit_label_posters] found {len(items)} initial poster(s)")
    if not items:
        print(f"[audit_label_posters] no posters found under {runs_dir}", file=sys.stderr)
        return 2

    distinct_papers = len({it.paper_title or it.run_id for it in items})
    print(f"[audit_label_posters] distinct papers (by title): {distinct_papers}")

    if not args.dry_run and not vlm_labeler.is_enabled():
        print("[audit_label_posters] WARNING: DASHSCOPE_API_KEY empty — labels will be 'disabled' stubs. "
              "Use --dry-run to skip the VLM entirely.", file=sys.stderr)

    labels_dir = args.out / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    source_counts: dict = {}
    template_rows: List[dict] = []

    for idx, item in enumerate(items, 1):
        labels = []
        if not args.dry_run:
            for pi in range(max(1, args.passes)):
                temp = _PASS_TEMPS[pi % len(_PASS_TEMPS)]
                lab = vlm_labeler.label_poster(
                    item.png_path, model=args.model, temperature=temp,
                    run_id=item.run_id, pass_idx=pi,
                )
                labels.append(lab)
                source_counts[lab.get("source", "?")] = source_counts.get(lab.get("source", "?"), 0) + 1

        record = {
            **item.to_dict(),
            "labels": labels,
        }
        (labels_dir / f"{_safe_stem(item)}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        pass0 = labels[0] if labels else {}
        template_rows.append({
            "run_id": item.run_id,
            "paper_title": item.paper_title,
            "template": item.template,
            "png_path": str(item.png_path),
            "vlm_primary": pass0.get("primary_issue", ""),
            "vlm_secondary": ";".join(pass0.get("secondary_issues", []) or []),
            "vlm_guards": ";".join(pass0.get("guard_violations", []) or []),
        })

        tag = (labels[0].get("primary_issue", "?") if labels else "dry_run")
        print(f"[audit_label_posters] ({idx}/{len(items)}) {item.run_id[:12]:12} -> {tag}")

    _write_human_template(args.out / "human_label_template.csv", template_rows)

    print(f"[audit_label_posters] wrote {len(items)} label file(s) to {labels_dir}")
    print(f"[audit_label_posters] human template: {args.out / 'human_label_template.csv'}")
    if source_counts:
        print(f"[audit_label_posters] label sources: {source_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
