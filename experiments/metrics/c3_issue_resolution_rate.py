"""C3 — Issue Resolution Rate (the load-bearing protocol metric).

c1 (action executability) is near-tautological for a closed schema; c3 asks the
harder, more meaningful question: **after the applier executes an action, does
the detected issue actually go away?**

Computed from ``metadata.config.svfp_trace`` — a per-iteration list of detected
``panel:issue`` keys persisted by the SVFP baselines (reshaped from the loop's
own history; no change to the frozen loop). For each consecutive pair of
iterations, an issue detected at iter *i* is *resolved* if it is absent at iter
*i+1*::

    resolution_rate = (# issues detected at iter i and absent at iter i+1)
                      / (# issues detected at iters 1..N-1)

Caveat (report in the paper): "absent at i+1" is judged by the **same VLM**, so
this metric inherits the critic's noise — a flaky critic that simply stops
mentioning an issue inflates resolution. Pair c3 with the geometry-based
b1/b2 deltas, and read it against the VLM-reliability finding.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from experiments.metrics.base import Metric, MetricContext, MetricResult, MetricRegistry


def _metadata_config(ctx: MetricContext) -> Dict[str, Any]:
    path = ctx.artifact_dir / "metadata.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    cfg = data.get("config") or {}
    return cfg if isinstance(cfg, dict) else {}


@MetricRegistry.register
class IssueResolutionRate(Metric):
    metric_id = "c3_issue_resolution_rate"
    description = "Fraction of detected issues that disappear after the action is applied (consecutive iters)."

    def compute(self, ctx: MetricContext) -> MetricResult:
        cfg = ctx.config or {}
        if not cfg.get("enabled", True):
            return self._skip("disabled in metrics.yaml")

        meta_cfg = _metadata_config(ctx)
        if meta_cfg.get("feedback_mode") in (None, "none"):
            return self._skip("no feedback arm (c3 N/A)")
        trace = meta_cfg.get("svfp_trace")
        if not isinstance(trace, list):
            return self._skip("no svfp_trace in metadata (re-run SVFP baseline to emit it)")
        if len(trace) < 2:
            return self._skip(f"need >=2 iterations to measure resolution (got {len(trace)})")

        detected = 0
        resolved = 0
        per_iter = []
        for a, b in zip(trace, trace[1:]):
            da = set(a.get("issues") or [])
            db = set(b.get("issues") or [])
            res = da - db
            detected += len(da)
            resolved += len(res)
            per_iter.append({"from_iter": a.get("iteration"), "detected": len(da), "resolved": len(res)})

        if detected == 0:
            return self._skip("no issues detected across iterations")

        return MetricResult(
            metric_id=self.metric_id,
            score=resolved / detected,
            extra={
                "detected_total": detected,
                "resolved_total": resolved,
                "n_iterations": len(trace),
                "per_iter": per_iter,
                "note": "resolution judged by the same VLM critic; read with the reliability caveat",
            },
        )
