#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import shutil
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = PROJECT_ROOT / "datasets/gold/audit_v2_labels_annotatorB.csv"

FIELDNAMES = [
    "run_folder",
    "title",
    "template",
    "iter1_png",
    "primary_issue",
    "secondary_issues",
    "other_description",
    "guard_notes",
    "confidence",
    "free_notes",
]

CORE_ISSUES = [
    "space_imbalance",
    "text_overload",
    "hierarchy_emphasis_error",
    "asset_mismatch",
    "asset_too_small",
    "structure_alignment_error",
]
PRIMARY_ISSUES = CORE_ISSUES + ["other", "none"]
SECONDARY_ISSUES = CORE_ISSUES + ["other"]

ISSUE_HELP = {
    "space_imbalance": "panel 内部太松、太挤，或局部视觉重量失衡",
    "text_overload": "文字超框、被裁切，或密度过高读起来累",
    "hierarchy_emphasis_error": "整体焦点或强调错配，看不出先读哪或强调了错误元素",
    "asset_mismatch": "图放错、图文不符，或主题对不上",
    "asset_too_small": "图本身太小，看不清内容",
    "structure_alignment_error": "整版网格、列宽、对齐、模块边界或画布填充出错",
    "other": "六类都套不进去的真实毛病，需要写 other_description",
    "none": "确实没看到明显版面问题",
}

BACKED_UP: set[Path] = set()


class ValidationError(ValueError):
    pass


def read_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        missing_columns = [name for name in FIELDNAMES if name not in fieldnames]
        if missing_columns:
            joined = ", ".join(missing_columns)
            raise ValidationError(f"CSV missing required columns: {joined}")
        rows = list(reader)
    return fieldnames, rows


def is_completed(row: dict[str, str]) -> bool:
    return bool((row.get("primary_issue") or "").strip())


def load_state(csv_path: Path) -> dict:
    _, rows = read_rows(csv_path)
    missing_images = []
    first_unlabeled_index = None
    client_rows = []

    for index, row in enumerate(rows):
        if first_unlabeled_index is None and not is_completed(row):
            first_unlabeled_index = index
        image_path = Path(row.get("iter1_png", ""))
        if not image_path.exists():
            missing_images.append({"index": index, "path": str(image_path)})
        client_row = {name: row.get(name, "") for name in FIELDNAMES}
        client_row["index"] = index
        client_row["completed"] = is_completed(row)
        client_rows.append(client_row)

    return {
        "csv_path": str(csv_path),
        "total": len(rows),
        "completed": sum(1 for row in rows if is_completed(row)),
        "first_unlabeled_index": first_unlabeled_index,
        "missing_images": missing_images,
        "rows": client_rows,
        "primary_issues": PRIMARY_ISSUES,
        "secondary_issues": SECONDARY_ISSUES,
        "issue_help": ISSUE_HELP,
    }


def _parse_secondary(value) -> list[str]:
    if isinstance(value, list):
        parts = value
    else:
        parts = str(value or "").split(",")
    return [str(part).strip() for part in parts if str(part).strip()]


def validate_annotation(payload: dict) -> dict[str, str]:
    primary = str(payload.get("primary_issue", "")).strip()
    if primary not in PRIMARY_ISSUES:
        raise ValidationError("primary_issue must be one of the allowed labels")

    secondary = _parse_secondary(payload.get("secondary_issues", []))
    invalid_secondary = [item for item in secondary if item not in SECONDARY_ISSUES]
    if invalid_secondary:
        raise ValidationError("secondary_issues contains invalid labels")
    if "none" in secondary:
        raise ValidationError("secondary_issues must not contain none")
    if primary == "none" and secondary:
        raise ValidationError("secondary_issues must be empty when primary_issue is none")
    if primary != "none" and primary in secondary:
        raise ValidationError("secondary_issues should not repeat primary_issue")

    free_notes = str(payload.get("free_notes", "")).strip()
    if not free_notes:
        raise ValidationError("free_notes is required before mapping to labels")

    try:
        confidence_value = float(str(payload.get("confidence", "")).strip())
    except ValueError as exc:
        raise ValidationError("confidence must be a number between 0 and 1") from exc
    if not 0 <= confidence_value <= 1:
        raise ValidationError("confidence must be between 0 and 1")

    other_description = str(payload.get("other_description", "")).strip()
    if (primary == "other" or "other" in secondary) and not other_description:
        raise ValidationError("other_description is required when other is selected")

    return {
        "primary_issue": primary,
        "secondary_issues": ",".join(secondary),
        "other_description": other_description,
        "guard_notes": str(payload.get("guard_notes", "")).strip(),
        "confidence": str(confidence_value),
        "free_notes": free_notes,
    }


def ensure_backup(csv_path: Path) -> Path:
    resolved = csv_path.resolve()
    if resolved in BACKED_UP:
        return resolved

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = csv_path.with_name(f"{csv_path.name}.bak-{timestamp}")
    suffix = 1
    while backup_path.exists():
        backup_path = csv_path.with_name(f"{csv_path.name}.bak-{timestamp}-{suffix}")
        suffix += 1

    shutil.copy2(csv_path, backup_path)
    BACKED_UP.add(resolved)
    return backup_path


def write_rows(csv_path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp_path = csv_path.with_name(f".{csv_path.name}.tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    os.replace(tmp_path, csv_path)


def save_annotation(csv_path: Path, index: int, payload: dict) -> dict:
    fieldnames, rows = read_rows(csv_path)
    if index < 0 or index >= len(rows):
        raise ValidationError("index is out of range")

    values = validate_annotation(payload)
    ensure_backup(csv_path)
    rows[index].update(values)
    write_rows(csv_path, fieldnames, rows)
    return load_state(csv_path)


def html_page() -> bytes:
    return HTML.encode("utf-8")


def make_handler(csv_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_error_json(self, status: int, message: str) -> None:
            self._send_json(status, {"error": message})

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    body = html_page()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if parsed.path == "/api/state":
                    self._send_json(200, load_state(csv_path))
                    return
                if parsed.path == "/api/image":
                    self._serve_image(parsed.query)
                    return
                self._send_error_json(404, "not found")
            except ValidationError as exc:
                self._send_error_json(400, str(exc))
            except Exception as exc:  # pragma: no cover - keeps browser failures visible.
                self._send_error_json(500, str(exc))

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/save":
                self._send_error_json(404, "not found")
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                index = int(payload.pop("index"))
                self._send_json(200, save_annotation(csv_path, index, payload))
            except ValidationError as exc:
                self._send_error_json(400, str(exc))
            except Exception as exc:  # pragma: no cover - keeps browser failures visible.
                self._send_error_json(500, str(exc))

        def _serve_image(self, query: str) -> None:
            params = parse_qs(query)
            index = int(params.get("index", ["-1"])[0])
            _, rows = read_rows(csv_path)
            if index < 0 or index >= len(rows):
                raise ValidationError("index is out of range")

            image_path = Path(rows[index].get("iter1_png", ""))
            if not image_path.exists():
                raise ValidationError(f"image not found: {image_path}")

            body = image_path.read_bytes()
            content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:
            print(f"[annotation] {self.address_string()} - {fmt % args}")

    return Handler


def run_server(csv_path: Path, host: str, port: int, open_browser: bool) -> None:
    csv_path = csv_path.resolve()
    state = load_state(csv_path)
    if state["missing_images"]:
        raise SystemExit(f"{len(state['missing_images'])} images are missing; fix CSV paths first.")

    server = ThreadingHTTPServer((host, port), make_handler(csv_path))
    url = f"http://{host}:{server.server_port}"
    print(f"CSV: {csv_path}")
    print(f"Rows: {state['total']}, completed: {state['completed']}")
    print(f"Open: {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit v2 browser annotation workbench")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV file to annotate")
    parser.add_argument("--host", default="127.0.0.1", help="server host")
    parser.add_argument("--port", type=int, default=8765, help="server port")
    parser.add_argument("--open", action="store_true", help="open the browser automatically")
    return parser.parse_args()


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Audit v2 标注器</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d8dde6;
      --text: #18202f;
      --muted: #667085;
      --accent: #126b5a;
      --danger: #b42318;
      --soft: #eef6f4;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    header {
      min-height: 68px;
      display: flex;
      gap: 18px;
      align-items: center;
      justify-content: space-between;
      padding: 12px 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 {
      margin: 0 0 4px;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0;
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
      max-width: 900px;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .progressBox {
      min-width: 220px;
      text-align: right;
      color: var(--muted);
      font-size: 13px;
    }
    progress {
      width: 220px;
      height: 10px;
      accent-color: var(--accent);
    }
    main {
      height: calc(100vh - 69px);
      display: grid;
      grid-template-columns: minmax(520px, 1fr) 430px;
      gap: 0;
    }
    .imagePane {
      min-width: 0;
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--line);
    }
    .toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      flex-wrap: wrap;
    }
    button, select, input, textarea {
      font: inherit;
    }
    button, .linkButton {
      min-height: 34px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      padding: 6px 10px;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
    button:hover, .linkButton:hover { background: #f2f4f7; }
    button.primary {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    button.primary:hover { background: #0d5b4c; }
    button:disabled {
      opacity: .5;
      cursor: not-allowed;
    }
    .imageWrap {
      flex: 1;
      min-height: 0;
      overflow: auto;
      padding: 16px;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      background: #e9edf3;
    }
    .imageWrap.fit {
      align-items: center;
    }
    img {
      max-width: none;
      background: #fff;
      box-shadow: 0 12px 36px rgba(24, 32, 47, .18);
    }
    .imageWrap.fit img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
    aside {
      overflow: auto;
      padding: 14px;
      background: var(--panel);
    }
    .section {
      padding: 12px 0;
      border-bottom: 1px solid var(--line);
    }
    .section:first-child { padding-top: 0; }
    label.label {
      display: block;
      margin-bottom: 6px;
      font-weight: 650;
      font-size: 13px;
    }
    .hint {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    textarea, select, input[type="number"] {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      background: #fff;
      color: var(--text);
    }
    textarea {
      resize: vertical;
      min-height: 70px;
      line-height: 1.45;
    }
    .checks {
      display: grid;
      gap: 6px;
    }
    .checkItem {
      display: grid;
      grid-template-columns: 20px 1fr;
      gap: 8px;
      align-items: start;
      padding: 6px;
      border: 1px solid transparent;
      border-radius: 6px;
    }
    .checkItem:hover { background: #f8fafc; border-color: #edf1f5; }
    .checkText {
      font-size: 13px;
      line-height: 1.35;
    }
    .checkText code { font-size: 12px; }
    .actions {
      position: sticky;
      bottom: 0;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      padding: 12px 0 0;
      background: linear-gradient(to top, #fff 85%, rgba(255,255,255,0));
    }
    .actions .wide { grid-column: 1 / -1; }
    .status {
      margin-top: 10px;
      min-height: 20px;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.4;
    }
    .status.error { color: var(--danger); }
    details {
      background: var(--soft);
      border: 1px solid #d8ebe7;
      border-radius: 6px;
      padding: 8px 10px;
    }
    summary {
      cursor: pointer;
      font-weight: 650;
      font-size: 13px;
    }
    .guideList {
      margin: 8px 0 0;
      padding-left: 18px;
      color: #344054;
      font-size: 12px;
      line-height: 1.45;
    }
    @media (max-width: 980px) {
      main {
        height: auto;
        grid-template-columns: 1fr;
      }
      .imagePane {
        height: 62vh;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
      aside { min-height: 60vh; }
      header { align-items: flex-start; flex-direction: column; }
      .progressBox { text-align: left; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Audit v2 标注器</h1>
      <div id="meta" class="meta">加载中...</div>
    </div>
    <div class="progressBox">
      <div id="counter">0/0</div>
      <progress id="progress" value="0" max="1"></progress>
    </div>
  </header>
  <main>
    <section class="imagePane">
      <div class="toolbar">
        <button id="prevBtn" type="button">上一张</button>
        <button id="nextBtn" type="button">下一张</button>
        <button id="nextBlankBtn" type="button">下一张未标</button>
        <label><input id="fitToggle" type="checkbox" checked> 适应窗口</label>
        <a id="openImage" class="linkButton" href="#" target="_blank" rel="noreferrer">原图</a>
      </div>
      <div id="imageWrap" class="imageWrap fit">
        <img id="poster" alt="poster preview">
      </div>
    </section>
    <aside>
      <div class="section">
        <details open>
          <summary>标注口径速查</summary>
          <ol class="guideList" id="guideList"></ol>
        </details>
      </div>
      <div class="section">
        <label class="label" for="free_notes">free_notes</label>
        <textarea id="free_notes" placeholder="先用一句话自由写下你看到的实际毛病"></textarea>
        <div class="hint">按守则，先 open-coding 再映射到标签。</div>
      </div>
      <div class="section">
        <label class="label" for="primary_issue">primary_issue</label>
        <select id="primary_issue"></select>
        <div id="primaryHelp" class="hint"></div>
      </div>
      <div class="section">
        <label class="label">secondary_issues</label>
        <div id="secondaryBox" class="checks"></div>
        <div class="hint">可多选，但不要选 none，也不要重复 primary。</div>
      </div>
      <div class="section">
        <label class="label" for="other_description">other_description</label>
        <textarea id="other_description" placeholder="只有选 other 时必填"></textarea>
      </div>
      <div class="section">
        <label class="label" for="guard_notes">guard_notes</label>
        <textarea id="guard_notes" placeholder="明显文字压图/重叠/对比太低/裁切时可记一句"></textarea>
      </div>
      <div class="section">
        <label class="label" for="confidence">confidence</label>
        <input id="confidence" type="number" min="0" max="1" step="0.05" placeholder="0.8">
        <div class="hint">0 到 1；常用 0.6、0.8、0.9。</div>
      </div>
      <div class="actions">
        <button id="saveBtn" type="button">保存</button>
        <button id="saveNextBtn" class="primary" type="button">保存并下一张</button>
        <button id="reloadBtn" class="wide" type="button">重新读取 CSV</button>
      </div>
      <div id="status" class="status"></div>
    </aside>
  </main>
  <script>
    let state = null;
    let currentIndex = 0;
    let dirty = false;

    const el = (id) => document.getElementById(id);
    const fields = ["free_notes", "primary_issue", "other_description", "guard_notes", "confidence"];

    function setStatus(message, isError = false) {
      el("status").textContent = message;
      el("status").classList.toggle("error", isError);
    }

    function labelFor(issue) {
      return `${issue} - ${state.issue_help[issue] || ""}`;
    }

    function renderGuide() {
      const list = el("guideList");
      list.innerHTML = "";
      state.primary_issues.forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = labelFor(issue);
        list.appendChild(item);
      });
    }

    function renderControls() {
      const primary = el("primary_issue");
      primary.innerHTML = "";
      state.primary_issues.forEach((issue) => {
        const option = document.createElement("option");
        option.value = issue;
        option.textContent = labelFor(issue);
        primary.appendChild(option);
      });

      const secondaryBox = el("secondaryBox");
      secondaryBox.innerHTML = "";
      state.secondary_issues.forEach((issue) => {
        const label = document.createElement("label");
        label.className = "checkItem";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.name = "secondary";
        input.value = issue;
        const text = document.createElement("span");
        text.className = "checkText";
        text.innerHTML = `<code>${issue}</code><br>${state.issue_help[issue] || ""}`;
        label.appendChild(input);
        label.appendChild(text);
        secondaryBox.appendChild(label);
      });
    }

    function completedAfter(index) {
      for (let i = index + 1; i < state.rows.length; i += 1) {
        if (!state.rows[i].completed) return i;
      }
      for (let i = 0; i <= index; i += 1) {
        if (!state.rows[i].completed) return i;
      }
      return Math.min(index + 1, state.rows.length - 1);
    }

    function loadIndex(index) {
      currentIndex = Math.max(0, Math.min(index, state.rows.length - 1));
      const row = state.rows[currentIndex];
      el("meta").textContent = `${row.index + 1}. ${row.title} | ${row.template}`;
      el("counter").textContent = `${state.completed}/${state.total} 已完成 | 当前 ${row.index + 1}/${state.total}`;
      el("progress").max = state.total || 1;
      el("progress").value = state.completed;

      fields.forEach((id) => {
        el(id).value = row[id] || "";
      });
      if (!el("confidence").value) {
        el("confidence").value = "0.8";
      }
      el("primaryHelp").textContent = state.issue_help[el("primary_issue").value] || "";
      const selectedSecondary = new Set((row.secondary_issues || "").split(",").filter(Boolean));
      document.querySelectorAll("input[name='secondary']").forEach((input) => {
        input.checked = selectedSecondary.has(input.value);
      });

      const imageUrl = `/api/image?index=${currentIndex}`;
      el("poster").src = `${imageUrl}&t=${Date.now()}`;
      el("openImage").href = imageUrl;
      el("prevBtn").disabled = currentIndex === 0;
      el("nextBtn").disabled = currentIndex === state.rows.length - 1;
      dirty = false;
      setStatus(row.completed ? "这一张已有标注，可以修改后再次保存。" : "这一张还未标注。");
    }

    function collectPayload() {
      return {
        index: currentIndex,
        free_notes: el("free_notes").value,
        primary_issue: el("primary_issue").value,
        secondary_issues: Array.from(document.querySelectorAll("input[name='secondary']:checked")).map((input) => input.value),
        other_description: el("other_description").value,
        guard_notes: el("guard_notes").value,
        confidence: el("confidence").value,
      };
    }

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      return payload;
    }

    async function refresh(keepIndex = false) {
      state = await fetchJson("/api/state");
      renderGuide();
      renderControls();
      const index = keepIndex ? currentIndex : (state.first_unlabeled_index ?? 0);
      loadIndex(index);
    }

    async function save(stay) {
      setStatus("保存中...");
      try {
        state = await fetchJson("/api/save", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(collectPayload()),
        });
        renderControls();
        const target = stay ? currentIndex : completedAfter(currentIndex);
        loadIndex(target);
        setStatus(stay ? "已保存。" : "已保存，并跳到下一张。");
      } catch (err) {
        setStatus(err.message, true);
      }
    }

    fields.forEach((id) => {
      document.addEventListener("input", (event) => {
        if (event.target.id === id || event.target.name === "secondary") dirty = true;
      });
      document.addEventListener("change", (event) => {
        if (event.target.id === id || event.target.name === "secondary") dirty = true;
      });
    });

    el("primary_issue").addEventListener("change", () => {
      el("primaryHelp").textContent = state.issue_help[el("primary_issue").value] || "";
    });
    el("fitToggle").addEventListener("change", () => {
      el("imageWrap").classList.toggle("fit", el("fitToggle").checked);
    });
    el("prevBtn").addEventListener("click", () => loadIndex(currentIndex - 1));
    el("nextBtn").addEventListener("click", () => loadIndex(currentIndex + 1));
    el("nextBlankBtn").addEventListener("click", () => loadIndex(completedAfter(currentIndex)));
    el("saveBtn").addEventListener("click", () => save(true));
    el("saveNextBtn").addEventListener("click", () => save(false));
    el("reloadBtn").addEventListener("click", () => refresh(true));

    window.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        save(false);
      }
      if (event.altKey && event.key === "ArrowLeft") {
        event.preventDefault();
        loadIndex(currentIndex - 1);
      }
      if (event.altKey && event.key === "ArrowRight") {
        event.preventDefault();
        loadIndex(currentIndex + 1);
      }
    });

    window.addEventListener("beforeunload", (event) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    });

    refresh(false).catch((err) => setStatus(err.message, true));
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    run_server(args.csv, args.host, args.port, args.open)


if __name__ == "__main__":
    main()
