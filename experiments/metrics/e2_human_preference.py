"""E2 — Human Preference (pairwise win-rate harness).

Tier-1 external validation. Human preference cannot be computed without human
data, so this metric is a **harness**: it reads pairwise blind-comparison
verdicts from a CSV and reports this method's win-rate (a Bradley-Terry score
can be fit offline across methods). With no data file it skips cleanly.

Expected CSV (``human_preference.csv`` under the results root or a path set in
metrics.yaml ``e2_human_preference.csv_path``), one row per pairwise judgement::

    paper_id,method_a,method_b,winner,judge_id
    2505.21497,ours_svfp,gpt4o_zeroshot,ours_svfp,annot1

The metric for a given cell (method = its baseline) = wins / comparisons it
took part in. Inter-annotator agreement (κ) is computed in an analysis script,
not here.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from experiments.metrics.base import Metric, MetricContext, MetricResult, MetricRegistry


@MetricRegistry.register
class E2HumanPreference(Metric):
    metric_id = "e2_human_preference"
    description = "Pairwise blind-comparison win-rate for this method (from human verdict CSV)."

    def compute(self, ctx: MetricContext) -> MetricResult:
        cfg = ctx.config or {}
        if not cfg.get("enabled", True):
            return self._skip("disabled in metrics.yaml")

        method = str((ctx.paper_meta or {}).get("baseline") or _method_from_dir(ctx.artifact_dir))
        paper_id = str((ctx.paper_meta or {}).get("arxiv_id") or "")

        csv_path = _resolve_csv(ctx)
        if csv_path is None or not csv_path.exists():
            return self._skip("no human_preference.csv yet (data-collection harness; see module docstring)")

        wins = comps = 0
        try:
            for row in csv.DictReader(csv_path.open(encoding="utf-8")):
                if paper_id and str(row.get("paper_id") or "") != paper_id:
                    continue
                a, b = str(row.get("method_a") or ""), str(row.get("method_b") or "")
                if method not in (a, b):
                    continue
                comps += 1
                if str(row.get("winner") or "") == method:
                    wins += 1
        except Exception as exc:
            return self._skip(f"could not parse {csv_path.name}: {exc}")

        if comps == 0:
            return self._skip(f"no comparisons for method={method!r} paper={paper_id!r}")
        return MetricResult(
            metric_id=self.metric_id,
            score=wins / comps,
            extra={"method": method, "wins": wins, "comparisons": comps},
        )


def _method_from_dir(artifact_dir: Path) -> str:
    # results/artifacts/<baseline>_<arxiv_id>/  ->  <baseline>
    name = Path(artifact_dir).name
    return name.rsplit("_", 1)[0] if "_" in name else name


def _resolve_csv(ctx: MetricContext) -> Optional[Path]:
    p = (ctx.config or {}).get("csv_path")
    if p:
        return Path(p)
    # default: alongside the results tree (…/results/human_preference.csv)
    try:
        return ctx.artifact_dir.parent.parent / "human_preference.csv"
    except Exception:
        return None
