#!/usr/bin/env python3
"""Generate architecture figures for the Global South submission PDF."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "Documentation" / "figures"

BOX_FACE = "#ffffff"
BOX_EDGE = "#b0b8c4"
GROUP_FACE = "#f4f6f8"
GROUP_EDGE = "#8a9aad"
ARROW_COLOR = "#3b6ea8"
TEXT_COLOR = "#1a1a1a"
SUBTEXT = "#4a5568"


def _box(ax, x, y, w, h, title: str, lines: list[str], *, fontsize: float = 8) -> None:
    rect = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2,
        edgecolor=BOX_EDGE,
        facecolor=BOX_FACE,
        transform=ax.transData,
        zorder=2,
    )
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h - 0.22, title, ha="center", va="top", fontsize=fontsize + 1,
            fontweight="bold", color=TEXT_COLOR)
    yy = y + h - 0.55
    for line in lines:
        ax.text(x + w / 2, yy, line, ha="center", va="top", fontsize=fontsize, color=SUBTEXT)
        yy -= 0.28


def _group(ax, x, y, w, h, label: str) -> None:
    rect = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.03,rounding_size=0.1",
        linewidth=1.5,
        edgecolor=GROUP_EDGE,
        facecolor=GROUP_FACE,
        transform=ax.transData,
        zorder=1,
    )
    ax.add_patch(rect)
    ax.text(x + 0.12, y + h - 0.12, label, ha="left", va="top", fontsize=9,
            fontweight="bold", color=TEXT_COLOR)


def _arrow(ax, x1, y1, x2, y2) -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.4,
            color=ARROW_COLOR,
            zorder=3,
        )
    )


def figure_layers_modular(path: Path) -> None:
    """Figure 2 — L1–L4 modular architecture (parallel layers → decision)."""
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    # L1
    _group(ax, 0.3, 4.0, 3.2, 1.7, "L1 — Regex")
    _box(ax, 0.55, 4.35, 2.7, 1.0, "Fixed patterns", [
        "DROP TABLE, ignore instructions",
        "DAN, [SYSTEM], canary probes",
    ], fontsize=7.5)

    # L2
    _group(ax, 0.3, 2.1, 3.2, 1.7, "L2 — RAG KB")
    _box(ax, 0.55, 2.45, 2.7, 1.0, "threats.json", [
        "TF-IDF embeddings",
        "Cosine similarity vs message",
    ], fontsize=7.5)

    # L3
    _group(ax, 0.3, 0.2, 3.2, 1.7, "L3 — Semantic drift")
    _box(ax, 0.55, 0.55, 2.7, 1.0, "Turn context", [
        "δ vs previous turn; Δ vs T0",
        "Optional LLM judge if suspicious",
    ], fontsize=7.5)

    # L4
    _group(ax, 5.8, 1.5, 3.6, 3.2, "L4 — Decision")
    _box(ax, 6.05, 3.35, 3.1, 0.9, "Fuse signals", ["L1 + L2 + L3 scores"], fontsize=8)
    _box(ax, 6.05, 2.35, 3.1, 0.85, "Score 0–100", ["Weighted fusion + session EWMA"], fontsize=8)
    _box(ax, 6.05, 1.65, 3.1, 0.6, "Action band", ["allow / warn / block"], fontsize=8)

    _arrow(ax, 3.5, 4.85, 5.8, 3.8)
    _arrow(ax, 3.5, 2.95, 5.8, 3.2)
    _arrow(ax, 3.5, 1.05, 5.8, 2.6)

    ax.set_title("Figure 2 — RAGE layered defense (L1–L4)", fontsize=11, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def figure_end_to_end(path: Path) -> None:
    """Figure 1 — End-to-end pipeline with gateway and metrics."""
    fig, ax = plt.subplots(figsize=(10, 2.8))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 3)
    ax.axis("off")

    steps = [
        ("User", 0.2, 1.0, 1.1, 0.9),
        ("L1\nRegex", 1.5, 1.0, 1.0, 0.9),
        ("L2\nRAG/KB", 2.7, 1.0, 1.0, 0.9),
        ("L3\nDrift", 3.9, 1.0, 1.0, 0.9),
        ("L4\nDecision", 5.1, 1.0, 1.15, 0.9),
        ("SQL\nGateway", 6.5, 1.0, 1.15, 0.9),
        ("SQLite\nAgent", 7.9, 1.0, 1.15, 0.9),
        ("AUC-D /\nTRI", 9.3, 1.0, 1.15, 0.9),
    ]
    centers = []
    for label, x, y, w, h in steps:
        rect = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            linewidth=1.2,
            edgecolor=BOX_EDGE,
            facecolor=BOX_FACE,
            zorder=2,
        )
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=7.5,
                color=TEXT_COLOR, linespacing=1.15)
        centers.append((x + w, y + h / 2, x, y + h / 2))

    for i in range(len(centers) - 1):
        x1, y1, x2, _ = centers[i][0], centers[i][1], centers[i + 1][2], centers[i + 1][3]
        _arrow(ax, x1 + 0.05, y1, x2 - 0.05, y1)

    ax.text(8.0, 0.35, "Tool calls blocked before destructive SQL executes",
            ha="center", fontsize=8, color=SUBTEXT, style="italic")
    ax.set_title("Figure 1 — End-to-end RAGE pipeline", fontsize=11, fontweight="bold", pad=10)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p1 = OUT_DIR / "rage_pipeline.png"
    p2 = OUT_DIR / "rage_layers.png"
    figure_end_to_end(p1)
    figure_layers_modular(p2)
    print(f"Wrote {p1}")
    print(f"Wrote {p2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
