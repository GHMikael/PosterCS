#!/usr/bin/env python3
"""Build a single labeled contact sheet of the 16 human-gold posters, so the user can re-mark
human_primary against [idx] without hunting for files one by one.

Each cell is labeled [pick_idx] + short title + density pct. VLM's guess is intentionally OMITTED
to keep the human's primary judgment independent. Zero API. Reads human_gold_subset.csv + the PNGs.
"""
from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CSV = "experiments/results/audit/human_gold_subset.csv"
OUT = Path("experiments/results/audit/figures/human_gold_contact_sheet.png")

COLS = 4
TW, TH = 470, 300           # thumbnail bounding box
LABEL_H, PAD, MARGIN = 26, 16, 18
HEADER_H = 34


def load_font(size):
    for p in [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def main() -> None:
    rows = list(csv.DictReader(open(CSV)))
    n = len(rows)
    cols = COLS
    nrows = (n + cols - 1) // cols

    cell_w = TW + PAD
    cell_h = TH + LABEL_H + PAD
    W = MARGIN * 2 + cols * cell_w
    H = MARGIN * 2 + HEADER_H + nrows * cell_h

    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)
    flabel = load_font(17)
    fhead = load_font(20)

    draw.text((MARGIN, MARGIN), "human-gold contact sheet — re-mark human_primary by [idx] "
              "(figures=asset_utilization_error, title overlap=overlap_guard, truncation=overflow_guard, …)",
              fill="black", font=fhead)

    missing = []
    for i, r in enumerate(rows):
        col, row = i % cols, i // cols
        x0 = MARGIN + col * cell_w
        y0 = MARGIN + HEADER_H + row * cell_h
        idx = r["pick_idx"]
        title = (r["paper_title"] or "")[:34]
        dens = r["density_pct"]
        draw.text((x0, y0), f"[{idx}] {title}  ({dens}%)", fill="black", font=flabel)
        p = r["png_path"]
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((TW, TH))
            px = x0 + (TW - im.width) // 2
            py = y0 + LABEL_H + (TH - im.height) // 2
            canvas.paste(im, (px, py))
            draw.rectangle([px - 1, py - 1, px + im.width, py + im.height], outline="#bbbbbb")
        except Exception as e:
            missing.append((idx, str(e)))
            draw.rectangle([x0, y0 + LABEL_H, x0 + TW, y0 + LABEL_H + TH], outline="red")
            draw.text((x0 + 8, y0 + LABEL_H + 8), f"MISSING\n{p}", fill="red", font=flabel)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT)
    print(f"wrote {OUT}  ({W}x{H}, {n} posters)")
    if missing:
        print("MISSING:", missing)


if __name__ == "__main__":
    main()
