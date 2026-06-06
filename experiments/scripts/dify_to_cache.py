"""Batch-trigger Dify runs and directly import PosterTask JSON into planner_cache.

Why this replaces batch_dify_runs.py + import_dify_runs.py
---------------------------------------------------------

The old two-step flow:
  1. batch_dify_runs.py — trigger 30 Dify runs, record status/run_id
  2. import_dify_runs.py — match outputs/runs/*/input.json to PDFs by
     fuzzy title matching (first-page text similarity), copy matched
     ones to planner_cache/<stem>.json

Problems with the old flow:
  - Title matching is fragile: ambiguous/unmatched cases require manual
    resolution (especially for papers with short/similar titles).
  - Two separate commands: you must wait for all runs to finish before
    running the import step.
  - No built-in resume: if the batch crashes mid-run, you start over.

This script merges both steps:
  - Trigger Dify for paper N → wait for its input.json to be written
    → validate → strip image_source → save as planner_cache/<stem>.json
    → move to paper N+1.
  - No title matching: the script knows the PDF stem it uploaded, so
    the cache filename is deterministic.
  - Built-in --skip-cached: safely resume from where you left off.
  - Two modes: "early" (grab input.json ~30s after trigger, before
    render finishes) or "finish" (wait for workflow_finished, ~120s).

Modes
-----

--mode early (default)
    Poll for input.json to appear in outputs/runs/ as soon as the
    backend's /generate_ppt endpoint writes it (~30-40s after trigger,
    before the SVFP render loop completes). Faster but adds light
    filesystem polling. Backend render threads accumulate in the
    background; the script serializes planning and overlaps rendering.

--mode finish
    Wait for the Dify SSE stream's workflow_finished event before
    claiming the run folder (~120-180s per paper). Rock-solid, zero
    concurrency, but slower.

Both modes produce identical planner_cache/*.json files.

Prerequisites
-------------

1. FastAPI backend is running and reachable from Dify (same as before).
2. .env contains DIFY_API_KEY, DIFY_BASE_URL, etc. (same as before).
3. datasets/papers/*.pdf exists (post-migration layout).

Usage
-----

Dry-run to confirm selection::

    python -m experiments.scripts.dify_to_cache --limit 3 --skip-cached --dry-run

Validate on ONE paper first (after starting the backend + Docker/Dify)::

    python -m experiments.scripts.dify_to_cache --limit 1 --max-workers 1

Run for real — parallel stream-capture is the default::

    python -m experiments.scripts.dify_to_cache --limit 64 --skip-cached --max-workers 4

If the stream finder can't locate the task, fall back to reading input.json::

    python -m experiments.scripts.dify_to_cache --limit 64 --skip-cached --capture folder

Output
------

- datasets/planner_cache/<stem>.json per successful run (portable:
  image_source stripped, baselines re-hydrate at runtime)
- experiments/results/dify_to_cache_report.json (progress + validation
  warnings)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAPERS_DIR = REPO_ROOT / "datasets" / "papers"
DEFAULT_CACHE_DIR = REPO_ROOT / "datasets" / "planner_cache"
DEFAULT_OUTPUTS_DIR = REPO_ROOT / "outputs" / "runs"
DEFAULT_REPORT = REPO_ROOT / "experiments" / "results" / "dify_to_cache_report.json"


def _load_env() -> None:
    """Minimal .env loader. Tolerates an absent file."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _select_pdfs(
    papers_dir: Path,
    limit: Optional[int],
    papers_list: Optional[Path],
    skip_cached: bool,
    cache_dir: Path,
) -> List[Path]:
    """Pick which PDFs to run."""
    if papers_list:
        names = papers_list.read_text(encoding="utf-8").splitlines()
        names = [n.strip() for n in names if n.strip() and not n.startswith("#")]
        pdfs = [papers_dir / n for n in names]
    else:
        pdfs = sorted(papers_dir.glob("*.pdf"))

    missing = [p for p in pdfs if not p.exists()]
    if missing:
        print(f"[dify_to_cache] warning: {len(missing)} PDFs not found:")
        for m in missing[:5]:
            print(f"    {m}")
    pdfs = [p for p in pdfs if p.exists()]

    if skip_cached:
        cached_stems = {p.stem for p in cache_dir.glob("*.json")}
        before = len(pdfs)
        pdfs = [p for p in pdfs if p.stem not in cached_stems]
        print(f"[dify_to_cache] --skip-cached: pruned {before - len(pdfs)} already-cached PDFs")

    if limit is not None and len(pdfs) > limit:
        pdfs = pdfs[:limit]
    return pdfs


def _upload_file(
    session: requests.Session,
    base_url: str,
    api_key: str,
    pdf_path: Path,
    user_id: str,
) -> str:
    """Upload PDF to Dify, return file_id."""
    url = f"{base_url.rstrip('/')}/files/upload"
    with pdf_path.open("rb") as fh:
        files = {"file": (pdf_path.name, fh, "application/pdf")}
        data = {"user": user_id}
        headers = {"Authorization": f"Bearer {api_key}"}
        r = session.post(url, headers=headers, files=files, data=data, timeout=120)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"file upload failed [{r.status_code}]: {r.text[:300]}")
    file_id = r.json().get("id")
    if not file_id:
        raise RuntimeError(f"file upload returned no id: {r.text[:300]}")
    return file_id


def _run_chatflow_streaming(
    session: requests.Session,
    base_url: str,
    api_key: str,
    file_id: str,
    *,
    input_name: str,
    user_id: str,
    query: str,
    max_wait_sec: int,
) -> Dict[str, Any]:
    """Trigger a CHATFLOW run in streaming mode; consume SSE until end-of-run.

    Returns workflow_run_id, status, timing. The backend render thread
    continues in the background even after this returns.
    """
    url = f"{base_url.rstrip('/')}/chat-messages"
    payload = {
        "inputs": {
            input_name: {
                "type": "custom",
                "transfer_method": "local_file",
                "upload_file_id": file_id,
            }
        },
        "query": query,
        "response_mode": "streaming",
        "conversation_id": "",
        "user": user_id,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    deadline = time.monotonic() + max_wait_sec
    started_at = time.time()
    run_id: Optional[str] = None
    status: Optional[str] = None
    finished_at: Optional[float] = None
    saw_message_end = False

    with session.post(
        url, headers=headers, json=payload, stream=True,
        timeout=(30, max_wait_sec + 60),
    ) as r:
        if r.status_code != 200:
            raise RuntimeError(f"chat-messages call failed [{r.status_code}]: {r.text[:300]}")
        for raw_line in r.iter_lines(decode_unicode=True):
            if time.monotonic() > deadline:
                raise TimeoutError(f"chatflow exceeded {max_wait_sec}s")
            if not raw_line or not raw_line.startswith("data:"):
                continue
            chunk = raw_line[5:].strip()
            if not chunk or chunk == "[DONE]":
                continue
            try:
                event = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            ev = event.get("event") or event.get("type")
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            if ev == "workflow_started":
                run_id = data.get("id") or run_id
            elif ev == "workflow_finished":
                run_id = data.get("id") or run_id
                status = data.get("status") or status
                finished_at = time.time()
                if status == "succeeded":
                    break
            elif ev == "message_end":
                saw_message_end = True
                finished_at = finished_at or time.time()
                break
            elif ev == "error":
                raise RuntimeError(f"dify error event: {json.dumps(event)[:300]}")

    if finished_at is None:
        raise RuntimeError("stream ended without message_end or workflow_finished")

    final_status = status or ("succeeded" if saw_message_end else "unknown")

    return {
        "workflow_run_id": run_id,
        "status": final_status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_s": round(finished_at - started_at, 2),
    }


def _claim_run_folder(
    outputs_dir: Path,
    trigger_time: float,
    *,
    poll_timeout_s: int = 60,
    poll_interval_s: float = 2.0,
) -> Optional[Path]:
    """Poll outputs/runs/ for the newest folder created after trigger_time.

    Returns the folder Path once input.json exists inside it, or None on
    timeout. Used in early mode to grab input.json without waiting for
    the full render to finish.
    """
    deadline = time.monotonic() + poll_timeout_s
    while time.monotonic() < deadline:
        if not outputs_dir.exists():
            time.sleep(poll_interval_s)
            continue
        candidates = [
            d for d in outputs_dir.iterdir()
            if d.is_dir() and d.stat().st_ctime > trigger_time
        ]
        for folder in sorted(candidates, key=lambda x: x.stat().st_ctime, reverse=True):
            input_json = folder / "input.json"
            if input_json.exists():
                return folder
        time.sleep(poll_interval_s)
    return None


def _validate_input_json(data: Dict[str, Any], pdf_stem: str) -> Dict[str, Any]:
    """Validate input.json and return a validation report.

    Returns::

        {
          "valid": bool,
          "errors": [str, ...],       # hard rejections
          "warnings": [str, ...],     # soft issues
        }
    """
    errors = []
    warnings = []

    asset_token = (data.get("asset_token") or "").strip()
    if asset_token.startswith("heuristic"):
        errors.append(f"asset_token '{asset_token}' indicates heuristic fallback (degraded run)")

    panels = data.get("panels") or []
    if not panels:
        errors.append("panels list is empty")

    poster_title = (data.get("poster_title") or "").strip()
    if poster_title == pdf_stem:
        warnings.append(f"poster_title == pdf_stem ('{pdf_stem}'); may indicate extraction failure")

    authors = (data.get("authors") or "").strip()
    paper_info = (data.get("paper_info") or "").strip()
    if not authors and not paper_info:
        warnings.append("authors and paper_info both empty")

    figures = data.get("figures") or {}
    if not figures:
        warnings.append("figures dict is empty (no images extracted)")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def _strip_image_sources(data: Dict[str, Any]) -> None:
    """Strip machine-specific image paths for portability.

    Baselines re-hydrate image_source at runtime via
    hydrate_task_image_sources().
    """
    for fig in data.get("figures", {}).values():
        fig.pop("image_source", None)
        fig.pop("image_url", None)
        fig.pop("thumbnail_url", None)


def _save_to_cache(
    data: Dict[str, Any],
    pdf_stem: str,
    cache_dir: Path,
) -> Path:
    """Strip image_source and write to planner_cache/<stem>.json."""
    _strip_image_sources(data)
    cache_path = cache_dir / f"{pdf_stem}.json"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache_path


# ---------------------------------------------------------------------------
# Stream-capture path (parallel-safe): grab the PosterTask straight from each
# paper's own Dify SSE connection. No run-folder claim, no title matching.
# ---------------------------------------------------------------------------


def _extract_json_object(s: str) -> Optional[Any]:
    """Best-effort: extract the first balanced ``{...}`` JSON object from a string."""
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start:i + 1])
                except Exception:
                    return None
    return None


def _find_poster_task(obj: Any, _depth: int = 0) -> Optional[Dict[str, Any]]:
    """Recursively search an SSE payload for a PosterTask.

    A PosterTask is identified as a dict carrying both ``asset_token`` and a
    ``panels`` list. Handles nested dicts/lists and JSON-string-encoded
    payloads (Dify End nodes often return the task as a stringified answer).
    This defensive search means we don't need to hard-code the exact Dify
    output key — it adapts to whatever shape the stream uses.
    """
    if obj is None or _depth > 6:
        return None
    if isinstance(obj, dict):
        if "asset_token" in obj and isinstance(obj.get("panels"), list):
            return obj
        for v in obj.values():
            found = _find_poster_task(v, _depth + 1)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_poster_task(v, _depth + 1)
            if found:
                return found
    elif isinstance(obj, str):
        if "asset_token" in obj and "panels" in obj:
            try:
                parsed = json.loads(obj)
            except Exception:
                parsed = _extract_json_object(obj)
            if parsed is not None:
                return _find_poster_task(parsed, _depth + 1)
    return None


def _capture_one(
    pdf: Path,
    *,
    base_url: str,
    api_key: str,
    input_name: str,
    user_id: str,
    query: str,
    max_wait_sec: int,
    stop_after_capture: bool,
) -> Dict[str, Any]:
    """Worker: upload one PDF, trigger the chatflow, capture the PosterTask
    JSON straight from the SSE stream. Thread-safe (own Session). Performs no
    disk writes — returns the raw task for the main thread to validate/cache.
    """
    rec: Dict[str, Any] = {
        "pdf": str(pdf), "stem": pdf.stem, "status": None,
        "workflow_run_id": None, "duration_s": None, "captured_at": None,
        "task": None, "event_types": [], "wf_outputs_keys": None, "error": "",
    }
    session = requests.Session()
    t0 = time.time()
    task: Optional[Dict[str, Any]] = None
    wf_status: Optional[str] = None
    seen = set()
    try:
        file_id = _upload_file(session, base_url, api_key, pdf, user_id)
        url = f"{base_url.rstrip('/')}/chat-messages"
        payload = {
            "inputs": {input_name: {"type": "custom", "transfer_method": "local_file",
                                    "upload_file_id": file_id}},
            "query": query, "response_mode": "streaming", "conversation_id": "", "user": user_id,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        deadline = time.monotonic() + max_wait_sec
        with session.post(url, headers=headers, json=payload, stream=True,
                          timeout=(30, max_wait_sec + 60)) as r:
            if r.status_code != 200:
                raise RuntimeError(f"chat-messages [{r.status_code}]: {r.text[:200]}")
            for line in r.iter_lines(decode_unicode=True):
                if time.monotonic() > deadline:
                    raise TimeoutError(f"exceeded {max_wait_sec}s")
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    event = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                ev = event.get("event") or event.get("type")
                seen.add(ev)
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                if ev == "workflow_started":
                    rec["workflow_run_id"] = data.get("id") or rec["workflow_run_id"]
                # Capture as early as possible (planner node) — protects the cache
                # even if the downstream render later fails.
                if task is None and ev in ("node_finished", "workflow_finished"):
                    payload_obj = data.get("outputs") if data.get("outputs") is not None else data
                    found = _find_poster_task(payload_obj)
                    if found:
                        task = found
                        rec["captured_at"] = round(time.time() - t0, 1)
                        if stop_after_capture:
                            break
                if ev == "workflow_finished":
                    rec["workflow_run_id"] = data.get("id") or rec["workflow_run_id"]
                    wf_status = data.get("status") or wf_status
                    outs = data.get("outputs")
                    rec["wf_outputs_keys"] = (list(outs.keys()) if isinstance(outs, dict)
                                              else type(outs).__name__)
                    if task is None:
                        task = _find_poster_task(data)
                        if task:
                            rec["captured_at"] = round(time.time() - t0, 1)
                    break
                if ev == "message_end" and task is not None:
                    break
                if ev == "error":
                    raise RuntimeError(f"dify error event: {json.dumps(event)[:200]}")
        rec["event_types"] = sorted(x for x in seen if x)
        rec["task"] = task
        rec["duration_s"] = round(time.time() - t0, 2)
        if task is not None:
            rec["status"] = "captured"
        else:
            rec["status"] = "no_task"
            rec["error"] = (f"PosterTask not found in stream "
                            f"(events={rec['event_types']}, wf_outputs_keys={rec['wf_outputs_keys']}, "
                            f"wf_status={wf_status})")
    except Exception as exc:
        rec["status"] = "errored"
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["duration_s"] = round(time.time() - t0, 2)
        rec["event_types"] = sorted(x for x in seen if x)
    finally:
        session.close()
    return rec


def _run_parallel_stream(
    pdfs: List[Path],
    *,
    base_url: str, api_key: str, input_name: str, user_id: str, query: str,
    max_wait_sec: int, max_workers: int, stop_after_capture: bool,
    cache_dir: Path, report_path: Path,
) -> int:
    """Run papers concurrently, capturing each PosterTask from its own Dify SSE
    stream. Parallel-safe: each result arrives on its own connection, so there
    is no run-folder claim or title matching. Validation + strip + cache write
    happen in the single main thread as each worker completes (no write races).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    counts = {"cached": 0, "validation_error": 0, "no_task": 0, "errored": 0}

    def _flush() -> None:
        report_path.write_text(
            json.dumps({"counts": counts, "records": records}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"\n[dify_to_cache] launching {max_workers} worker(s) over {len(pdfs)} paper(s) "
          f"(stop_after_capture={stop_after_capture})...\n")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(
                _capture_one, pdf,
                base_url=base_url, api_key=api_key, input_name=input_name,
                user_id=user_id, query=query, max_wait_sec=max_wait_sec,
                stop_after_capture=stop_after_capture,
            ): pdf
            for pdf in pdfs
        }
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            pdf = futures[fut]
            done += 1
            try:
                rec = fut.result()
            except Exception as exc:  # defensive; _capture_one catches its own
                rec = {"pdf": str(pdf), "stem": pdf.stem, "status": "errored",
                       "error": f"{type(exc).__name__}: {exc}", "task": None}
            task = rec.pop("task", None)
            tag = f"[{done}/{len(pdfs)}]"
            if rec.get("status") == "errored":
                counts["errored"] += 1
                print(f"{tag} ! {pdf.name}: {rec.get('error', '')[:140]}")
            elif task is None:
                counts["no_task"] += 1
                print(f"{tag} ✗ {pdf.name}: no PosterTask in stream "
                      f"(events={rec.get('event_types')}, wf_keys={rec.get('wf_outputs_keys')})")
            else:
                validation = _validate_input_json(task, pdf.stem)
                rec["validation"] = validation
                if not validation["valid"]:
                    counts["validation_error"] += 1
                    print(f"{tag} ✗ {pdf.name}: validation FAILED {validation['errors']}")
                else:
                    cache_path = _save_to_cache(task, pdf.stem, cache_dir)
                    rec["cache_path"] = str(cache_path)
                    counts["cached"] += 1
                    warn = f"  ⚠ {validation['warnings']}" if validation["warnings"] else ""
                    print(f"{tag} ✓ {pdf.name} → {cache_path.name} "
                          f"(captured @ {rec.get('captured_at')}s){warn}")
            records.append(rec)
            _flush()

    print()
    print(f"[dify_to_cache] summary: {counts}")
    print(f"[dify_to_cache] report:  {report_path}")
    if counts["no_task"]:
        print("\n⚠ Some papers returned no PosterTask. Check event_types / wf_outputs_keys "
              "in the report — the stream finder may need a tweak for your Dify End-node "
              "shape, or fall back to --capture folder.")
    if counts["cached"]:
        print(f"\n✓ {counts['cached']} cached to {cache_dir}")
    bad = counts["errored"] + counts["validation_error"] + counts["no_task"]
    return 0 if bad == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Batch-trigger Dify workflow and directly import into planner_cache.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--papers-dir", type=Path, default=DEFAULT_PAPERS_DIR,
                   help="Directory of PDFs (default: datasets/papers).")
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR,
                   help="Where to write planner_cache/<stem>.json.")
    p.add_argument("--outputs-dir", type=Path, default=DEFAULT_OUTPUTS_DIR,
                   help="Where backend writes outputs/runs/ folders.")
    p.add_argument("--report", type=Path, default=DEFAULT_REPORT,
                   help="Per-paper outcomes (written after each iteration).")
    p.add_argument("--limit", type=int, default=25,
                   help="Max papers to run (default 25).")
    p.add_argument("--papers-list", type=Path, default=None,
                   help="Optional: text file with one PDF filename per line.")
    p.add_argument("--skip-cached", action="store_true",
                   help="Skip PDFs whose <stem>.json already exists in planner_cache.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print selected PDFs and exit without calling Dify.")
    p.add_argument("--mode", choices=["early", "finish"], default="early",
                   help="early: poll for input.json ~30s after trigger (fast, light polling); "
                        "finish: wait for workflow_finished ~120s (rock-solid, slower).")
    p.add_argument("--max-wait-sec", type=int, default=600,
                   help="Per-paper max wait for workflow_finished (default 600s).")
    p.add_argument("--inter-run-sleep-sec", type=float, default=2.0,
                   help="Pause between Dify runs (default 2s; --capture folder only).")
    p.add_argument("--capture", choices=["stream", "folder"], default="stream",
                   help="stream (default): grab the PosterTask straight from each paper's "
                        "Dify SSE — parallel-safe, no run-folder claim, no title matching. "
                        "folder: read outputs/runs/<dir>/input.json (serial fallback).")
    p.add_argument("--max-workers", type=int, default=4,
                   help="Concurrent Dify runs for --capture stream (default 4). Each holds a "
                        "backend render, so this bounds concurrent backend load.")
    p.add_argument("--stop-after-capture", action="store_true",
                   help="Close the stream the instant the PosterTask is captured (~planner "
                        "done, before render finishes). Faster, but the backend may keep "
                        "rendering in the background — use only if it handles the load.")
    args = p.parse_args(argv)

    _load_env()
    api_key = os.environ.get("DIFY_API_KEY", "").strip()
    base_url = os.environ.get("DIFY_BASE_URL", "http://localhost/v1").strip()
    input_name = os.environ.get("DIFY_WORKFLOW_INPUT_NAME", "paper").strip()
    user_id = os.environ.get("DIFY_USER_ID", "experiment-batch").strip()
    query = os.environ.get(
        "DIFY_QUERY",
        "Generate a conference-style poster from this paper.",
    ).strip()

    pdfs = _select_pdfs(
        args.papers_dir, args.limit, args.papers_list,
        args.skip_cached, args.cache_dir,
    )
    print(f"[dify_to_cache] selected {len(pdfs)} PDF(s) from {args.papers_dir}")
    for i, pdf in enumerate(pdfs, 1):
        print(f"  {i:>3}. {pdf.name}")

    if args.dry_run:
        print("[dry-run] no Dify calls made.")
        return 0
    if not pdfs:
        print("[dify_to_cache] no PDFs to run, exiting.")
        return 0
    if not api_key:
        print("[dify_to_cache] DIFY_API_KEY missing in env or .env. Aborting.",
              file=sys.stderr)
        return 2

    print()
    print(f"[dify_to_cache] Dify base:      {base_url}")
    print(f"[dify_to_cache] input variable: {input_name}")
    print(f"[dify_to_cache] user id:        {user_id}")
    print(f"[dify_to_cache] query:          {query!r}")
    print(f"[dify_to_cache] capture:        {args.capture}"
          + (f"  workers={args.max_workers}" if args.capture == "stream" else f"  mode={args.mode}"))
    print(f"[dify_to_cache] max wait/paper: {args.max_wait_sec}s")

    if args.capture == "stream":
        return _run_parallel_stream(
            pdfs,
            base_url=base_url, api_key=api_key, input_name=input_name,
            user_id=user_id, query=query, max_wait_sec=args.max_wait_sec,
            max_workers=args.max_workers, stop_after_capture=args.stop_after_capture,
            cache_dir=args.cache_dir, report_path=args.report,
        )

    # ---- folder-claim path (serial fallback; reads outputs/runs/<dir>/input.json) ----
    session = requests.Session()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    counts = {"succeeded": 0, "failed": 0, "errored": 0, "validation_error": 0, "cached": 0}

    for i, pdf in enumerate(pdfs, 1):
        rec: Dict[str, Any] = {
            "pdf": str(pdf),
            "stem": pdf.stem,
            "status": None,
            "workflow_run_id": None,
            "duration_s": None,
            "cache_path": None,
            "validation": {"valid": None, "errors": [], "warnings": []},
            "error": "",
        }
        print(f"\n[{i}/{len(pdfs)}] {pdf.name}")
        try:
            trigger_time = time.time()
            print("  → upload to Dify...")
            file_id = _upload_file(session, base_url, api_key, pdf, user_id)
            print(f"    file_id = {file_id}")

            print("  → trigger chatflow (streaming)...")
            result = _run_chatflow_streaming(
                session, base_url, api_key, file_id,
                input_name=input_name, user_id=user_id, query=query,
                max_wait_sec=args.max_wait_sec,
            )
            rec.update({
                "status": result["status"],
                "workflow_run_id": result["workflow_run_id"],
                "duration_s": result["duration_s"],
            })

            if result["status"] != "succeeded":
                counts["failed"] += 1
                print(f"    ✗ workflow status={result['status']} "
                      f"(run_id={result['workflow_run_id']})")
                records.append(rec)
                args.report.write_text(
                    json.dumps({"counts": counts, "records": records},
                               ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                if i < len(pdfs):
                    time.sleep(args.inter_run_sleep_sec)
                continue

            # Mode: early → poll for input.json; finish → already waited
            if args.mode == "early":
                print("  → polling for input.json (early mode)...")
                folder = _claim_run_folder(
                    args.outputs_dir, trigger_time,
                    poll_timeout_s=60, poll_interval_s=2.0,
                )
                if folder is None:
                    raise TimeoutError("input.json did not appear within 60s")
                input_json_path = folder / "input.json"
            else:
                # finish mode: run_id is in the folder name suffix
                # We need to find it by matching the run_id or by creation time
                folder = _claim_run_folder(
                    args.outputs_dir, trigger_time,
                    poll_timeout_s=10, poll_interval_s=1.0,
                )
                if folder is None:
                    raise RuntimeError("could not locate run folder after workflow_finished")
                input_json_path = folder / "input.json"

            print(f"    folder: {folder.name}")
            data = json.loads(input_json_path.read_text(encoding="utf-8"))

            # Validate
            validation = _validate_input_json(data, pdf.stem)
            rec["validation"] = validation
            if validation["errors"]:
                counts["validation_error"] += 1
                print(f"    ✗ validation FAILED:")
                for err in validation["errors"]:
                    print(f"        - {err}")
                if validation["warnings"]:
                    print(f"    ⚠ warnings:")
                    for warn in validation["warnings"]:
                        print(f"        - {warn}")
                records.append(rec)
                args.report.write_text(
                    json.dumps({"counts": counts, "records": records},
                               ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                if i < len(pdfs):
                    time.sleep(args.inter_run_sleep_sec)
                continue

            if validation["warnings"]:
                print(f"    ⚠ warnings:")
                for warn in validation["warnings"]:
                    print(f"        - {warn}")

            # Save to cache
            cache_path = _save_to_cache(data, pdf.stem, args.cache_dir)
            rec["cache_path"] = str(cache_path)
            counts["cached"] += 1
            print(f"    ✓ cached → {cache_path.name}")

        except Exception as exc:
            rec["status"] = "errored"
            rec["error"] = f"{type(exc).__name__}: {exc}"
            counts["errored"] += 1
            print(f"    ! errored: {rec['error']}")

        records.append(rec)
        args.report.write_text(
            json.dumps({"counts": counts, "records": records},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if i < len(pdfs):
            time.sleep(args.inter_run_sleep_sec)

    print()
    print(f"[dify_to_cache] summary: {counts}")
    print(f"[dify_to_cache] report:  {args.report}")
    print()
    if counts["cached"] > 0:
        print(f"✓ {counts['cached']} paper(s) cached to {args.cache_dir}")
        print()
        print("Next steps:")
        print("  1. Verify planner_cache count:")
        print(f"       ls {args.cache_dir} | wc -l")
        print("  2. Run the experiment matrix:")
        print("       python -m experiments.scripts.run_matrix \\")
        print("           --papers experiments/configs/papers_30.json \\")
        print("           --baselines ours_svfp,ours_no_svfp,gpt4o_zeroshot \\")
        print("           --workers 2")

    return 0 if counts["errored"] == 0 and counts["validation_error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
