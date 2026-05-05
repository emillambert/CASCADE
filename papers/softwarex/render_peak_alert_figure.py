# SPDX-License-Identifier: MIT
"""Render the SoftwareX peak-alert map figure.

The tracked replay artifact is a diagnostic PNG. This script wraps the same
evidence in a paper-style panel for the SoftwareX manuscript.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.paths import ARTIFACTS_REPLAY_DIR, SOFTWAREX_FIGURES_DIR


REPLAY_DIR = ARTIFACTS_REPLAY_DIR / "westlands_ca_2014-06-01_2014-10-31"
RAW_MAP = REPLAY_DIR / "peak_alert_map.png"
METRICS_PATH = REPLAY_DIR / "replay_metrics.json"
OUT_BASE = SOFTWAREX_FIGURES_DIR / "Figure_3_peak_alert_map"

BLUE = "#1f77b4"
RED = "#b00020"
GREEN = "#2ca02c"
ORANGE = "#d95f02"
DARK = "#222222"
EDGE = "#777777"
GRID = "#e4e4e4"
PANEL_BG = "#fafafa"


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
        }
    )


def _runs(indices: np.ndarray) -> list[tuple[int, int]]:
    if indices.size == 0:
        return []
    breaks = np.where(np.diff(indices) > 1)[0] + 1
    groups = np.split(indices, breaks)
    return [(int(group[0]), int(group[-1])) for group in groups if group.size]


def crop_map_panel(image: np.ndarray) -> np.ndarray:
    """Crop the diagnostic title and colorbar away from the replay PNG."""
    rgb = image[..., :3]
    dark = np.all(rgb < 0.08, axis=2)
    height, width = dark.shape

    vertical = _runs(np.where(dark.sum(axis=0) > height * 0.45)[0])
    horizontal = _runs(np.where(dark.sum(axis=1) > width * 0.45)[0])
    if len(vertical) < 2 or len(horizontal) < 2:
        return image

    y0 = (horizontal[0][0] + horizontal[0][1]) // 2
    y1 = (horizontal[1][0] + horizontal[1][1]) // 2
    target_height = y1 - y0

    x_positions = [(start + end) // 2 for start, end in vertical]
    x0, x1 = min(
        (
            (left, right)
            for i, left in enumerate(x_positions)
            for right in x_positions[i + 1 :]
            if right - left > width * 0.35
        ),
        key=lambda pair: abs((pair[1] - pair[0]) - target_height),
    )
    return image[y0 + 1 : y1, x0 + 1 : x1, :]


def metric_box(ax, y: float, label: str, value: str, color: str) -> None:
    box = FancyBboxPatch(
        (0.0, y),
        1.0,
        0.135,
        boxstyle="round,pad=0.009,rounding_size=0.012",
        linewidth=0.8,
        facecolor=PANEL_BG,
        edgecolor="#cfcfcf",
    )
    ax.add_patch(box)
    ax.add_patch(Rectangle((0.0, y), 0.02, 0.135, facecolor=color, edgecolor="none"))
    ax.text(0.055, y + 0.087, label, ha="left", va="center", fontsize=7.5, color="#555555")
    ax.text(0.055, y + 0.039, value, ha="left", va="center", fontsize=10.0, weight="bold", color=DARK)


def render() -> None:
    configure_style()
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    raw = mpimg.imread(RAW_MAP)
    cropped = crop_map_panel(raw)

    peak_csc = float(metrics["peak_csc"])
    alert_thr = float(metrics["csc_alert_thr"])
    vmax = max(0.7, peak_csc)

    fig = plt.figure(figsize=(7.45, 4.05))
    ax_map = fig.add_axes((0.055, 0.135, 0.56, 0.76))
    cax = fig.add_axes((0.635, 0.20, 0.026, 0.62))
    ax_info = fig.add_axes((0.705, 0.135, 0.245, 0.76))

    ax_map.imshow(cropped, interpolation="nearest")
    ax_map.set_xticks([])
    ax_map.set_yticks([])
    for spine in ax_map.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.75)
        spine.set_color(EDGE)
    ax_map.set_title("(a) Peak CSC field, Westlands 2014", loc="left", pad=5, fontsize=10.5, weight="bold")
    ax_map.annotate(
        f"peak CSC {peak_csc:.3f}",
        xy=(0.73, 0.48),
        xycoords="axes fraction",
        xytext=(0.43, 0.88),
        textcoords="axes fraction",
        fontsize=8.0,
        color=DARK,
        arrowprops=dict(arrowstyle="->", lw=0.8, color=RED),
        bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="#d0d0d0", linewidth=0.6),
    )
    norm = mpl.colors.Normalize(vmin=0.0, vmax=vmax)
    sm = mpl.cm.ScalarMappable(norm=norm, cmap="inferno")
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cax)
    cbar.ax.set_title("CSC", fontsize=7.8, pad=4)
    cbar.ax.axhline(alert_thr, color=RED, linewidth=1.2)

    ax_info.set_axis_off()
    ax_info.text(0.0, 0.98, "(b) Replay values", ha="left", va="top", fontsize=10.5, weight="bold", color=DARK)
    ax_info.text(0.0, 0.885, "Peak alert window: 13 Aug 2014", ha="left", va="top", fontsize=8.0, color="#555555")
    metric_box(ax_info, 0.70, "Peak CSC", f"{peak_csc:.3f}", RED)
    metric_box(ax_info, 0.52, "Alert threshold", f"{alert_thr:.3f}", ORANGE)
    metric_box(ax_info, 0.34, "Priority windows", f"{metrics['alert_windows']} / {metrics['valid_windows']}", BLUE)
    metric_box(ax_info, 0.16, "Mean valid pixels", f"{100 * float(metrics['mean_valid_fraction']):.1f}%", GREEN)
    ax_info.text(
        0.0,
        0.025,
        "Rendered from the tracked offline replay artifact.",
        ha="left",
        va="bottom",
        fontsize=7.4,
        color="#555555",
    )

    OUT_BASE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_BASE.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=0.03)
    fig.savefig(OUT_BASE.with_suffix(".pdf"), format="pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print(f"Saved {OUT_BASE.with_suffix('.pdf')}")


if __name__ == "__main__":
    render()
