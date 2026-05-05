# SPDX-License-Identifier: MIT
"""Render SoftwareX Figure 1 as a software-module/data-flow diagram."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT_DIR = Path(__file__).resolve().parents[1] / "figures"
OUT_PATH = OUT_DIR / "Figure_1_architecture.pdf"


BOXES: list[tuple[float, float, float, float]] = []


def _box(
    ax,
    xy,
    wh,
    title,
    body,
    face,
    edge="#1f2937",
    *,
    title_size=8.5,
    body_size=6.9,
) -> None:
    x, y = xy
    w, h = wh
    BOXES.append((x, y, w, h))
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
        y + h * 0.71,
        title,
        ha="center",
        va="center",
        fontsize=title_size,
        weight="bold",
        color="#111827",
    )
    ax.text(
        x + w / 2,
        y + h * 0.38,
        body,
        ha="center",
        va="center",
        fontsize=body_size,
        color="#1f2937",
        linespacing=1.12,
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

    global BOXES
    BOXES = []

    fig, ax = plt.subplots(figsize=(8.8, 5.2))
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
        fontsize=13.5,
        weight="bold",
        color="#0f172a",
    )

    module_w = 0.18
    small_w = 0.14
    col1 = 0.035
    col2 = 0.295
    col3 = 0.555
    col4 = 0.82
    top = 0.62
    mid = 0.33
    _box(
        ax,
        (col1, top),
        (module_w, 0.19),
        "cascade.core",
        "Config + actions\nCSC + Beta\nCASCADEPolicy",
        "#e0f2fe",
        body_size=7.0,
    )
    _box(
        ax,
        (col1, mid),
        (module_w, 0.19),
        "cascade.replay",
        "MODIS path\nartifact replay\nreplay() API",
        "#dcfce7",
        body_size=7.0,
    )
    _box(
        ax,
        (col2, top),
        (module_w, 0.19),
        "cascade.simulation",
        "synthetic seasons\nbaselines\n100-seed MC",
        "#fef3c7",
        body_size=7.0,
    )
    _box(
        ax,
        (col2, mid),
        (module_w, 0.19),
        "cascade.calibration",
        "CSC weights\nthreshold sweep\naccepted params",
        "#fde68a",
        body_size=7.0,
    )
    _box(
        ax,
        (col3, top),
        (module_w, 0.19),
        "cascade.economics",
        "SWAP accounting\nenergy/downlink\nscenario outputs",
        "#fce7f3",
        body_size=7.0,
    )
    _box(
        ax,
        (col3, mid),
        (module_w, 0.19),
        "examples",
        "Westlands replay\noffline workflow\npolicy hook",
        "#ede9fe",
        body_size=7.0,
    )
    _box(
        ax,
        (col4, top),
        (small_w, 0.19),
        "build/",
        "regenerated\noutputs\nlocal runs",
        "#f1f5f9",
        body_size=7.2,
    )
    _box(
        ax,
        (col4, mid),
        (small_w, 0.19),
        "artifacts/",
        "accepted\nfixtures\npaper figures",
        "#fee2e2",
        body_size=7.2,
    )
    _box(
        ax,
        (0.335, 0.075),
        (0.33, 0.15),
        "tests + GitHub Actions",
        "pytest compares metrics + fixtures\ncoverage gate protects behavior",
        "#e5e7eb",
        body_size=7.0,
    )

    c1r = col1 + module_w
    c2r = col2 + module_w
    c3r = col3 + module_w
    c4m = col4 + small_w / 2
    top_center = top + 0.095
    mid_center = mid + 0.095
    lower_box_bottom = mid
    lower_box_top = mid + 0.19
    tests_top = 0.225

    _arrow(ax, (c1r, top_center), (col2, top_center))
    _arrow(ax, (c2r, top_center), (col3, top_center))
    _arrow(ax, (c3r, top_center), (col4, top_center))
    _arrow(ax, (c1r, mid_center), (col2, mid_center))
    _arrow(ax, (c2r, mid_center), (col3, mid_center))
    _arrow(ax, (c3r, mid_center), (col4, mid_center))
    _arrow(ax, (c4m, top), (c4m, lower_box_top))
    _arrow(ax, (col2 + module_w / 2, lower_box_bottom), (col2 + module_w / 2, tests_top), color="#64748b")
    _arrow(ax, (col3 + module_w / 2, lower_box_bottom), (col3 + module_w / 2, tests_top), color="#64748b")

    fig.savefig(OUT_PATH, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
