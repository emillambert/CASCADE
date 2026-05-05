# SPDX-License-Identifier: MIT
"""Render SoftwareX Figure 1 as a software-module/data-flow diagram."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT_DIR = Path(__file__).resolve().parent / "figures"
OUT_PATH = OUT_DIR / "Figure_1_architecture.pdf"


def _box(ax, xy, wh, title, body, face, edge="#1f2937") -> None:
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.016,rounding_size=0.018",
        linewidth=1.4,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h * 0.70,
        title,
        ha="center",
        va="center",
        fontsize=10.5,
        weight="bold",
        color="#111827",
    )
    ax.text(
        x + w / 2,
        y + h * 0.38,
        body,
        ha="center",
        va="center",
        fontsize=8.2,
        color="#1f2937",
        linespacing=1.22,
    )


def _arrow(ax, start, end, color="#334155", rad=0.0) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.25,
            color=color,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=4,
            shrinkB=4,
        )
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.2, 4.7))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.955,
        "CASCADE software modules and data flow",
        ha="center",
        va="center",
        fontsize=13,
        weight="bold",
        color="#0f172a",
    )

    _box(
        ax,
        (0.035, 0.62),
        (0.19, 0.19),
        "src/cascade/core.py",
        "Config, action table\nCSC, Beta helpers\nCASCADEPolicy",
        "#e0f2fe",
    )
    _box(
        ax,
        (0.035, 0.33),
        (0.19, 0.19),
        "src/cascade/replay/",
        "AppEEARS/MODIS path\nartifact-backed replay\nCLI: python -m cascade.replay",
        "#dcfce7",
    )
    _box(
        ax,
        (0.305, 0.62),
        (0.19, 0.19),
        "src/cascade/simulation.py",
        "synthetic seasons\npolicy baselines\n100-seed benchmark",
        "#fef3c7",
    )
    _box(
        ax,
        (0.305, 0.33),
        (0.19, 0.19),
        "src/cascade/calibration.py",
        "CSC weights\nalert threshold sweep\naccepted parameters",
        "#fde68a",
    )
    _box(
        ax,
        (0.575, 0.62),
        (0.19, 0.19),
        "src/cascade/economics.py",
        "SWAP accounting\nenergy/downlink summaries\nscenario outputs",
        "#fce7f3",
    )
    _box(
        ax,
        (0.575, 0.33),
        (0.19, 0.19),
        "examples/",
        "westlands_replay.py\noffline review path\npolicy modification hook",
        "#ede9fe",
    )
    _box(
        ax,
        (0.805, 0.62),
        (0.16, 0.19),
        "build/",
        "regenerated outputs\ntransient downloads\nlocal experiments",
        "#f1f5f9",
    )
    _box(
        ax,
        (0.805, 0.33),
        (0.16, 0.19),
        "artifacts/",
        "accepted fixtures\nrelease evidence\npaper figures",
        "#fee2e2",
    )
    _box(
        ax,
        (0.345, 0.075),
        (0.31, 0.15),
        "tests/ + GitHub Actions",
        "pytest compares metrics and fixtures\ncoverage gate protects public behavior",
        "#e5e7eb",
    )

    _arrow(ax, (0.225, 0.715), (0.305, 0.715))
    _arrow(ax, (0.225, 0.425), (0.305, 0.425))
    _arrow(ax, (0.495, 0.715), (0.575, 0.715))
    _arrow(ax, (0.495, 0.425), (0.575, 0.425))
    _arrow(ax, (0.765, 0.715), (0.805, 0.715))
    _arrow(ax, (0.765, 0.425), (0.805, 0.425))
    _arrow(ax, (0.885, 0.62), (0.885, 0.52))
    _arrow(ax, (0.205, 0.33), (0.375, 0.225), rad=-0.15)
    _arrow(ax, (0.405, 0.33), (0.445, 0.225), rad=-0.08)
    _arrow(ax, (0.645, 0.33), (0.555, 0.225), rad=0.08)
    _arrow(ax, (0.805, 0.425), (0.655, 0.17), rad=0.12)

    ax.text(0.15, 0.575, "shared policy API", ha="center", fontsize=7.5, color="#475569")
    ax.text(0.40, 0.575, "benchmark + calibration", ha="center", fontsize=7.5, color="#475569")
    ax.text(0.69, 0.575, "release export", ha="center", fontsize=7.5, color="#475569")
    ax.text(0.935, 0.57, "promote", ha="center", fontsize=7.5, color="#475569")

    fig.savefig(OUT_PATH, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
