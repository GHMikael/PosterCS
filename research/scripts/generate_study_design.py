#!/usr/bin/env python3
"""Generate the manuscript study-design figure in vector and raster formats."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "paper" / "figures"

INK = "#172033"
MUTED = "#596579"
LINE = "#C9D2DE"
PANEL = "#F7F9FC"
WHITE = "#FFFFFF"
NAVY = "#254E77"
BLUE = "#2F80C3"
BLUE_PALE = "#EAF4FC"
TEAL = "#178A7A"
TEAL_PALE = "#E8F6F2"
ORANGE = "#D96B2B"
ORANGE_PALE = "#FFF1E7"
PURPLE = "#8064A2"
PURPLE_PALE = "#F3EFF8"


def configure() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 8.5,
            "figure.dpi": 220,
            "savefig.dpi": 320,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.04,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def rounded_box(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    face: str = WHITE,
    edge: str = LINE,
    linewidth: float = 1.0,
    radius: float = 1.2,
    zorder: int = 2,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0.02,rounding_size={radius}",
        facecolor=face,
        edgecolor=edge,
        linewidth=linewidth,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = "#7D8999",
    dashed: bool = False,
    width: float = 1.25,
    zorder: int = 4,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=width,
            linestyle=(0, (3, 2)) if dashed else "-",
            color=color,
            shrinkA=2,
            shrinkB=2,
            zorder=zorder,
        )
    )


def section_label(ax: plt.Axes, x: float, text: str, color: str) -> None:
    ax.text(
        x,
        56.1,
        text,
        ha="left",
        va="center",
        fontsize=8.0,
        fontweight="bold",
        color=color,
        zorder=5,
    )


def stage_card(
    ax: plt.Axes,
    x: float,
    y: float,
    title: str,
    body: str,
    *,
    accent: str,
    fill: str,
    number: str,
) -> None:
    rounded_box(ax, x, y, 20.0, 11.7, face=fill, edge=accent, linewidth=1.2)
    ax.add_patch(Circle((x + 2.2, y + 8.8), 1.15, facecolor=accent, edgecolor="none", zorder=4))
    ax.text(
        x + 2.2,
        y + 8.8,
        number,
        ha="center",
        va="center",
        color=WHITE,
        fontsize=7.1,
        fontweight="bold",
        zorder=5,
    )
    ax.text(
        x + 4.1,
        y + 8.8,
        title,
        ha="left",
        va="center",
        fontsize=9.6,
        fontweight="bold",
        color=INK,
        zorder=5,
    )
    ax.text(
        x + 2.0,
        y + 4.1,
        body,
        ha="left",
        va="center",
        fontsize=7.7,
        color=MUTED,
        linespacing=1.2,
        zorder=5,
    )


def evidence_lane(
    ax: plt.Axes,
    y: float,
    source: str,
    route: str,
    detail: str,
    *,
    accent: str,
    fill: str,
) -> None:
    rounded_box(ax, 31.0, y, 33.7, 8.0, face=WHITE, edge=LINE, linewidth=0.8, radius=0.9)
    rounded_box(ax, 32.0, y + 1.0, 10.2, 6.0, face=fill, edge="none", linewidth=0, radius=0.7)
    ax.text(37.1, y + 4.0, source, ha="center", va="center", fontsize=7.1, fontweight="bold", color=accent)
    arrow(ax, (43.1, y + 4.0), (46.4, y + 4.0), color=accent, width=1.0)
    ax.text(47.3, y + 4.8, route, ha="left", va="center", fontsize=7.1, fontweight="bold", color=INK)
    ax.text(47.3, y + 2.7, detail, ha="left", va="center", fontsize=6.0, color=MUTED, linespacing=1.05)


def evaluation_card(
    ax: plt.Axes,
    x: float,
    y: float,
    title: str,
    body: str,
    badge: str,
    *,
    accent: str,
    fill: str,
    title_size: float = 9.0,
) -> None:
    rounded_box(ax, x, y, 25.5, 14.2, face=fill, edge=accent, linewidth=1.15)
    ax.text(x + 2.0, y + 10.7, title, ha="left", va="center", fontsize=title_size, fontweight="bold", color=INK)
    ax.text(x + 2.0, y + 6.4, body, ha="left", va="center", fontsize=6.8, color=MUTED, linespacing=1.18)
    rounded_box(ax, x + 2.0, y + 1.3, 12.4, 2.6, face=WHITE, edge="none", linewidth=0, radius=0.7)
    ax.text(x + 8.2, y + 2.6, badge, ha="center", va="center", fontsize=6.0, fontweight="bold", color=accent)


def build() -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7.35, 4.35))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE)

    # Subtle column backgrounds create hierarchy without large colored blocks.
    rounded_box(ax, 1.5, 12.0, 24.2, 42.0, face=PANEL, edge="none", linewidth=0, radius=1.4, zorder=0)
    rounded_box(ax, 28.0, 12.0, 39.5, 42.0, face="#F9FBFD", edge=LINE, linewidth=0.8, radius=1.4, zorder=0)
    rounded_box(ax, 70.0, 12.0, 28.5, 42.0, face=PANEL, edge="none", linewidth=0, radius=1.4, zorder=0)

    section_label(ax, 2.0, "DEVELOPMENT", NAVY)
    section_label(ax, 28.6, "FROZEN AUDIT SYSTEM", TEAL)
    section_label(ax, 70.6, "POST-FREEZE EVALUATION", ORANGE)

    stage_card(
        ax,
        3.5,
        37.0,
        "Formal-88",
        "Explore model × prompt\nsettings",
        accent=BLUE,
        fill=BLUE_PALE,
        number="1",
    )
    stage_card(
        ax,
        3.5,
        20.3,
        "RuleDev-66",
        "Select features;\ncalibrate thresholds",
        accent=TEAL,
        fill=TEAL_PALE,
        number="2",
    )

    ax.text(47.7, 50.4, "Protocol freeze", ha="center", va="center", fontsize=10.3, fontweight="bold", color=INK)
    ax.text(
        47.7,
        46.8,
        "Rules, prompts, routes, and operating points fixed\nbefore confirmatory evaluation",
        ha="center",
        va="center",
        fontsize=6.1,
        color=MUTED,
        linespacing=1.12,
    )
    ax.plot([31.0, 64.5], [43.9, 43.9], color=LINE, linewidth=0.8, zorder=2)

    evidence_lane(
        ax,
        35.8,
        "PPTX source",
        "Source-aware rules",
        "fonts · bounds · clipping",
        accent=TEAL,
        fill=TEAL_PALE,
    )
    evidence_lane(
        ax,
        26.3,
        "Raster image",
        "Deterministic rules",
        "OCR · occupancy · geometry",
        accent=BLUE,
        fill=BLUE_PALE,
    )
    evidence_lane(
        ax,
        16.8,
        "Poster image",
        "Gated VLM judgement",
        "semantic priority · unresolved cases",
        accent=ORANGE,
        fill=ORANGE_PALE,
    )

    evaluation_card(
        ax,
        71.5,
        35.1,
        "C48-Confirm",
        "24 verified control–mutation pairs\nSensitivity + restraint",
        "ALL ROUTES",
        accent=ORANGE,
        fill=ORANGE_PALE,
    )
    evaluation_card(
        ax,
        71.5,
        17.4,
        "External-Natural-20",
        "20 natural posters\nDirectional external check",
        "IMAGE-ONLY VLM",
        accent=PURPLE,
        fill=PURPLE_PALE,
        title_size=8.0,
    )

    # Development data feeds the protocol; the frozen routes feed evaluation.
    arrow(ax, (23.7, 42.9), (28.0, 42.9), color=BLUE)
    arrow(ax, (23.7, 26.2), (28.0, 26.2), color=TEAL)
    arrow(ax, (67.5, 42.2), (71.5, 42.2), color=ORANGE)
    arrow(ax, (67.5, 22.9), (71.5, 24.5), color=PURPLE, dashed=True)

    # Gold labels are visually separated because they never enter inference.
    rounded_box(ax, 28.0, 2.6, 70.5, 6.0, face="#F2F4F7", edge="#929CAB", linewidth=0.9, radius=1.0)
    ax.text(31.0, 5.6, "HUMAN GOLD & ADJUDICATION", ha="left", va="center", fontsize=7.6, fontweight="bold", color=INK)
    ax.text(
        96.0,
        5.6,
        "evaluation only · never visible to auditors",
        ha="right",
        va="center",
        fontsize=7.0,
        color=MUTED,
    )
    ax.plot([97.0, 98.0], [42.2, 42.2], color="#929CAB", linewidth=1.0, linestyle=(0, (3, 2)), zorder=1)
    ax.plot([97.0, 98.0], [24.5, 24.5], color="#929CAB", linewidth=1.0, linestyle=(0, (3, 2)), zorder=1)
    ax.plot([98.0, 98.0], [42.2, 8.6], color="#929CAB", linewidth=1.0, linestyle=(0, (3, 2)), zorder=1)

    return fig


def main() -> None:
    configure()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = build()
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(OUTPUT_DIR / f"study-design.{suffix}", facecolor=WHITE)
    plt.close(fig)
    print(f"Wrote study-design.png/pdf/svg to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
