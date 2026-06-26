#!/usr/bin/env python3
"""Simple RAGE + Session Judge flowchart for documentation."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "Documentation" / "figures" / "rage_judge_flow.png"

BOX = "#ffffff"
EDGE = "#5b7fa6"
FILL_RAGE = "#e8f0f8"
FILL_JUDGE = "#fff4e6"
FILL_OK = "#e8f5e9"
FILL_STOP = "#fdecea"
ARROW = "#3b6ea8"
TEXT = "#1a1a1a"
SUB = "#4a5568"


def _rounded(ax, x, y, w, h, text, *, face=BOX, edge=EDGE, fs=9, bold=False):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1.5, edgecolor=edge, facecolor=face, zorder=2,
        )
    )
    weight = "bold" if bold else "normal"
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=TEXT, fontweight=weight, linespacing=1.25)


def _diamond(ax, cx, cy, text, *, w=2.2, h=1.0):
  # draw as rotated square approximation using polygon - simpler: use a box with "?"
    _rounded(ax, cx - w / 2, cy - h / 2, w, h, text, face="#f7f9fc", fs=8.5, bold=True)


def _arrow(ax, x1, y1, x2, y2, label: str = "") -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="-|>", mutation_scale=14, linewidth=1.5, color=ARROW, zorder=3,
        )
    )
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.15, my, label, fontsize=7.5, color=SUB, ha="left", va="center")


def main() -> None:
    fig, ax = plt.subplots(figsize=(7.5, 11))
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 14)
    ax.axis("off")

    cx = 4.0
    w, h = 4.8, 0.85

    # Top to bottom
    y = 12.8
    _rounded(ax, cx - w / 2, y, w, h, "User message", bold=True)

    y -= 1.35
    _arrow(ax, cx, y + h + 0.5, cx, y + 1.15)
    _rounded(ax, cx - w / 2, y, w, 1.1, "RAGE defense (L1→L2→L3→L4)\n+ session memory (drift, risk)",
             face=FILL_RAGE, fs=8.5, bold=True)

    y -= 1.55
    _arrow(ax, cx, y + 1.1 + 0.45, cx, y + 1.05)
    _diamond(ax, cx, y + 0.45, "Clean turn?\n(no risk flag)", w=2.6, h=1.0)

    # YES branch left
    y_clean = y - 0.35
    _arrow(ax, cx - 1.3, y + 0.45, 1.6, y_clean + 1.5, "YES")
    _rounded(ax, 0.35, y_clean + 0.9, 2.5, 1.2,
             "Assistant LLM\n(large model)\n→ normal reply", face=FILL_OK, fs=8)

    # NO branch down
    y -= 1.85
    _arrow(ax, cx, y + 1.05 + 0.5, cx, y + 1.35, "NO")
    _rounded(ax, cx - w / 2, y, w, 1.35,
             "Session Judge LLM (small / fast)\nInputs: bot profile + chat history + RAGE briefing",
             face=FILL_JUDGE, fs=8, bold=True)

    y -= 1.65
    _arrow(ax, cx, y + 1.35 + 0.45, cx, y + 1.05)
    _diamond(ax, cx, y + 0.45, "Judge verdict?", w=2.4, h=1.0)

    # ALLOW
    y_allow = y - 0.4
    _arrow(ax, cx - 1.1, y + 0.45, 1.6, y_allow + 1.35, "ALLOW")
    _rounded(ax, 0.35, y_allow + 0.75, 2.5, 1.15,
             "Assistant LLM\n→ reply (false alarm cleared)", face=FILL_OK, fs=8)

    # BLOCK / DENY
    y -= 1.9
    _arrow(ax, cx, y + 1.05 + 0.55, cx, y + 1.25, "BLOCK / DENY")
    _rounded(ax, cx - w / 2, y, w, 1.05,
             "Stop — security message to user\n(assistant is NOT called)",
             face=FILL_STOP, fs=8.5, bold=True)

    ax.text(4, 13.55, "RAGE + Session Judge — one turn (Track A)",
            ha="center", fontsize=12, fontweight="bold", color=TEXT)
    ax.text(4, 0.35,
            "Clean turns skip the judge → lower latency · Risky turns get human-like review with full context",
            ha="center", fontsize=8, color=SUB, style="italic")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
