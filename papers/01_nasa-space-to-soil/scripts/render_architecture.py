# SPDX-License-Identifier: MIT
"""Render the CASCADE paper architecture figure.

The figure is intentionally artifact-backed where possible: the action mix comes
from the checked-in Monte Carlo metrics, while the architecture annotations are
the paper's fixed engineering description.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.paths import ARTIFACTS_BENCHMARK_DIR, PAPER_FIGURES_DIR


BLUE = "#1f77b4"
RED = "#b00020"
GREEN = "#2ca02c"
ORANGE = "#d95f02"
GRAY = "#6e6e6e"
DARK = "#222222"
GRID = "#e4e4e4"
EDGE = "#777777"
LIGHT_BLUE = "#edf4fb"
LIGHT_GREEN = "#edf7ed"
PANEL_BG = "#fafafa"

ACTION_COLORS = {
    "SKIP": GRAY,
    "MOD13": GREEN,
    "FUSE": BLUE,
    "FUSE_PRIORITY": RED,
}


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 8.8,
            "ytick.labelsize": 8.8,
            "axes.edgecolor": "#666666",
            "axes.linewidth": 0.75,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.alpha": 1.0,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "legend.fontsize": 8.0,
        }
    )


def load_metrics() -> dict:
    path = ARTIFACTS_BENCHMARK_DIR / "simulation_metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))


def action_mix(metrics: dict) -> dict[str, float]:
    mix = (
        metrics.get("monte_carlo", {})
        .get("policy_summary", {})
        .get("CASCADE_MDP", {})
        .get("action_mix", {})
    )
    result = {"SKIP": 0.0, "MOD13": 0.0, "FUSE": 0.0, "FUSE_PRIORITY": 0.0}
    for action in result:
        result[action] = float(mix.get(action, {}).get("pct_mean", 0.0))
    return result


def rounded_box(ax, xy, width, height, text, face, edge, fontsize=8.9, weight="bold"):
    box = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.008,rounding_size=0.014",
        linewidth=0.95,
        facecolor=face,
        edgecolor=edge,
        zorder=2,
    )
    ax.add_patch(box)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=DARK,
        weight=weight,
        zorder=3,
    )
    return box


def arrow(ax, start, end, label="", label_offset=(0, 0.055)):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(arrowstyle="-|>", lw=1.05, color="#666666", shrinkA=4, shrinkB=4),
        zorder=1,
    )
    if label:
        ax.text(
            (start[0] + end[0]) / 2 + label_offset[0],
            (start[1] + end[1]) / 2 + label_offset[1],
            label,
            ha="center",
            va="center",
            fontsize=7.2,
            color="#555555",
        )


def render_action_mix(ax, mix: dict[str, float]) -> None:
    x0, y0, width, height = 0.065, 0.125, 0.87, 0.062
    ax.text(0.065, 0.215, "100-seed scheduler action mix", ha="left", va="bottom", fontsize=9.1, weight="bold")
    ax.add_patch(Rectangle((x0, y0), width, height, facecolor=PANEL_BG, edgecolor="#cfcfcf", linewidth=0.75))

    cursor = x0
    for action in ("SKIP", "MOD13", "FUSE", "FUSE_PRIORITY"):
        pct = mix[action]
        seg_w = width * pct / 100.0
        if seg_w > 0:
            ax.add_patch(
                Rectangle(
                    (cursor, y0),
                    seg_w,
                    height,
                    facecolor=ACTION_COLORS[action],
                    edgecolor="white",
                    linewidth=0.75,
                )
            )
            if seg_w > 0.045:
                label = action.replace("_", "\n")
                ax.text(cursor + seg_w / 2, y0 + height / 2, label, ha="center", va="center", fontsize=7.2, color="white")
        cursor += seg_w

    legend_x = x0
    for action in ("SKIP", "MOD13", "FUSE", "FUSE_PRIORITY"):
        pct = mix[action]
        ax.add_patch(Rectangle((legend_x, 0.045), 0.016, 0.016, facecolor=ACTION_COLORS[action], edgecolor="none"))
        ax.text(
            legend_x + 0.022,
            0.053,
            f"{action.replace('_', ' ')} {pct:.1f}%",
            ha="left",
            va="center",
            fontsize=7.4,
            color=DARK,
        )
        legend_x += 0.22 if action != "FUSE_PRIORITY" else 0.24


def render_degradation(ax) -> None:
    x0, y0, width, height = 0.405, 0.342, 0.185, 0.052
    bands = [
        (">=35% SOC", GREEN, 0.45),
        ("15-<35%", ORANGE, 0.35),
        ("<15%", RED, 0.20),
    ]
    ax.text(x0, y0 + 0.066, "Graceful degradation", ha="left", va="bottom", fontsize=7.5, color=DARK)
    cursor = x0
    for label, color, frac in bands:
        seg_w = width * frac
        ax.add_patch(Rectangle((cursor, y0), seg_w, height, facecolor=color, edgecolor="white", linewidth=0.65))
        ax.text(cursor + seg_w / 2, y0 + height / 2, label, ha="center", va="center", fontsize=6.2, color="white")
        cursor += seg_w
    ax.add_patch(Rectangle((x0, y0), width, height, fill=False, edgecolor=EDGE, linewidth=0.75))


def main() -> None:
    configure_style()
    metrics = load_metrics()
    mix = action_mix(metrics)

    fig, ax = plt.subplots(figsize=(8.35, 2.95))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.add_patch(
        FancyBboxPatch(
            (0.025, 0.325),
            0.68,
            0.585,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            linewidth=0.95,
            facecolor="#f8fbff",
            edgecolor=BLUE,
            linestyle="--",
            zorder=0,
        )
    )
    ax.text(0.045, 0.855, "Hosted payload module - Loft Orbital YAM", ha="left", va="center", fontsize=8.6, color=BLUE, style="italic")

    rounded_box(ax, (0.070, 0.610), 0.085, 0.105, "Sensors\nMS + TIR", LIGHT_BLUE, BLUE, fontsize=8.3)
    rounded_box(ax, (0.210, 0.610), 0.105, 0.105, "FPGA\nKintex RT", LIGHT_BLUE, BLUE, fontsize=8.3)
    rounded_box(
        ax,
        (0.365, 0.585),
        0.17,
        0.155,
        "LEON4FT\nMDP policy\n$\\tau_{max}$ / SOC / $k$",
        LIGHT_BLUE,
        BLUE,
        fontsize=8.1,
        weight="bold",
    )
    rounded_box(ax, (0.595, 0.610), 0.105, 0.105, "Priority\nX-band", LIGHT_BLUE, BLUE, fontsize=8.3)
    rounded_box(ax, (0.780, 0.610), 0.10, 0.105, "Loft\nground", LIGHT_GREEN, GREEN, fontsize=8.3)
    rounded_box(ax, (0.743, 0.389), 0.08, 0.095, "OpenET\nAPI", LIGHT_GREEN, GREEN, fontsize=8.0)
    rounded_box(ax, (0.865, 0.389), 0.105, 0.095, "Farmer\nplatform", LIGHT_GREEN, GREEN, fontsize=8.0)

    arrow(ax, (0.155, 0.663), (0.210, 0.663))
    arrow(ax, (0.315, 0.663), (0.365, 0.663))
    arrow(ax, (0.535, 0.663), (0.595, 0.663))
    arrow(ax, (0.700, 0.663), (0.780, 0.663))
    arrow(ax, (0.83, 0.610), (0.775, 0.484))
    arrow(ax, (0.823, 0.436), (0.865, 0.436))

    ax.text(0.709, 0.855, "SPACE", ha="right", va="center", fontsize=7.4, color="#777777")
    ax.text(0.735, 0.855, "GROUND", ha="left", va="center", fontsize=7.4, color="#777777")

    render_degradation(ax)
    ax.text(0.405, 0.488, "Promotion gate:\ncontact + CSC > 0.615", ha="left", va="center", fontsize=7.0, color=RED)

    render_action_mix(ax, mix)

    out_base = PAPER_FIGURES_DIR / "architecture"
    out_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_base.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(out_base.with_suffix(".pdf"), format="pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(out_base.with_suffix(".svg"), format="svg", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"Saved {out_base.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
