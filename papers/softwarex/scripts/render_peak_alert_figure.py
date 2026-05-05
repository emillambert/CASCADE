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


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.paths import ARTIFACTS_REPLAY_DIR, SOFTWAREX_FIGURES_DIR


REPLAY_DIR = ARTIFACTS_REPLAY_DIR / "westlands_ca_2014-06-01_2014-10-31"
RAW_MAP = REPLAY_DIR / "peak_alert_map.png"
METRICS_PATH = REPLAY_DIR / "replay_metrics.json"
OUT_BASE = SOFTWAREX_FIGURES_DIR / "Figure_3_peak_alert_map"

RED = "#b00020"
DARK = "#222222"
EDGE = "#777777"
GRID = "#e4e4e4"
MASKED_CELL = "#eeeeee"


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
    return image[y0 + 3 : y1 - 2, x0 + 3 : x1 - 2, :]


def trim_masked_perimeter(panel: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Remove fully masked perimeter rows/columns from a cropped diagnostic image."""
    rgb = panel[..., :3]
    masked = np.all(rgb > 0.96, axis=2)
    while masked.shape[0] > 1 and masked[0, :].mean() > 0.95:
        panel = panel[1:, :, :]
        masked = masked[1:, :]
    while masked.shape[0] > 1 and masked[-1, :].mean() > 0.95:
        panel = panel[:-1, :, :]
        masked = masked[:-1, :]
    while masked.shape[1] > 1 and masked[:, 0].mean() > 0.95:
        panel = panel[:, 1:, :]
        masked = masked[:, 1:]
    while masked.shape[1] > 1 and masked[:, -1].mean() > 0.95:
        panel = panel[:, :-1, :]
        masked = masked[:, :-1]
    return panel, masked


def infer_csc_grid(image: np.ndarray, *, vmax: float, n_cells: int = 12) -> np.ndarray:
    """Recover the replay CSC grid from the tracked diagnostic PNG.

    The release artifact stores the peak field as a rendered Matplotlib PNG,
    not as a NumPy array.  This routine samples the center of each displayed
    cell and maps the Inferno RGB value back to the nearest scalar value.
    """
    panel, _ = trim_masked_perimeter(crop_map_panel(image).copy())
    height, width = panel.shape[:2]
    cell_h = height / n_cells
    cell_w = width / n_cells
    cmap = mpl.colormaps["inferno"]
    lookup = cmap(np.linspace(0.0, 1.0, 4096))[:, :3]
    values = np.linspace(0.0, vmax, 4096)
    grid = np.full((n_cells, n_cells), np.nan, dtype=float)
    for row in range(n_cells):
        for col in range(n_cells):
            y0 = int((row + 0.35) * cell_h)
            y1 = int((row + 0.65) * cell_h)
            x0 = int((col + 0.35) * cell_w)
            x1 = int((col + 0.65) * cell_w)
            sample = panel[y0:y1, x0:x1, :3].reshape(-1, 3)
            rgb = np.median(sample, axis=0)
            if np.all(rgb > 0.96):
                continue
            idx = int(np.argmin(np.sum((lookup - rgb) ** 2, axis=1)))
            grid[row, col] = values[idx]
    return grid


def render() -> None:
    configure_style()
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    raw = mpimg.imread(RAW_MAP)

    peak_csc = float(metrics["peak_csc"])
    alert_thr = float(metrics["csc_alert_thr"])
    vmax = max(0.7, peak_csc)
    grid = infer_csc_grid(raw, vmax=vmax)
    peak_row, peak_col = np.unravel_index(np.nanargmax(grid), grid.shape)

    lon_min, lat_min, lon_max, lat_max = -120.55, 36.55, -120.45, 36.65
    fig = plt.figure(figsize=(7.1, 3.65), layout="constrained")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 0.82], wspace=0.12)
    ax_map = fig.add_subplot(gs[0, 0])
    ax_info = fig.add_subplot(gs[0, 1])

    cmap = mpl.colormaps["inferno"].copy()
    cmap.set_bad(MASKED_CELL)
    im = ax_map.imshow(
        grid,
        cmap=cmap,
        vmin=0.0,
        vmax=vmax,
        interpolation="nearest",
        origin="upper",
        extent=[lon_min, lon_max, lat_min, lat_max],
    )
    ax_map.contour(
        np.linspace(lon_min, lon_max, grid.shape[1]),
        np.linspace(lat_max, lat_min, grid.shape[0]),
        grid,
        levels=[alert_thr],
        colors=[RED],
        linewidths=0.75,
    )
    peak_lon = lon_min + (peak_col + 0.5) * (lon_max - lon_min) / grid.shape[1]
    peak_lat = lat_max - (peak_row + 0.5) * (lat_max - lat_min) / grid.shape[0]
    ax_map.plot(peak_lon, peak_lat, marker="x", markersize=5.5, markeredgewidth=1.1, color=RED)
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.set_title("(a) Peak CSC field, Westlands 2014", loc="left", pad=5, fontsize=10.0, weight="bold")
    ax_map.set_xticks([-120.55, -120.50, -120.45])
    ax_map.set_yticks([36.55, 36.60, 36.65])
    ax_map.tick_params(length=3, width=0.65)
    for spine in ax_map.spines.values():
        spine.set_linewidth(0.75)
        spine.set_color(EDGE)
    cbar = fig.colorbar(im, ax=ax_map, fraction=0.046, pad=0.035)
    cbar.set_label("CSC")
    cbar.ax.axhline(alert_thr, color=RED, linewidth=0.9)

    ax_info.set_axis_off()
    ax_info.set_xlim(0.0, 1.0)
    ax_info.set_ylim(0.0, 1.0)
    ax_info.text(0.0, 1.0, "(b) Replay summary", ha="left", va="top", fontsize=10.0, weight="bold", color=DARK)
    rows = [
        ("AOI", "Westlands / Firebaugh"),
        ("Peak window", "13 Aug 2014"),
        ("Peak CSC", f"{peak_csc:.3f}"),
        ("Alert threshold", f"{alert_thr:.3f}"),
        ("Priority windows", f"{metrics['alert_windows']} / {metrics['valid_windows']}"),
        ("Mean valid pixels", f"{100 * float(metrics['mean_valid_fraction']):.1f}%"),
    ]
    y_top = 0.83
    row_h = 0.105
    ax_info.hlines(y_top, 0.0, 1.0, color="#9e9e9e", linewidth=0.55)
    for idx, (label, value) in enumerate(rows):
        y = y_top - (idx + 0.5) * row_h
        ax_info.text(0.02, y, label, ha="left", va="center", fontsize=7.7, color="#555555")
        ax_info.text(0.56, y, value, ha="left", va="center", fontsize=7.7, color=DARK)
        ax_info.hlines(y_top - (idx + 1) * row_h, 0.0, 1.0, color="#c7c7c7", linewidth=0.45)
    ax_info.text(
        0.0,
        0.11,
        "Red contour marks CSC >= alert threshold;\nred cross marks the peak replay cell.",
        ha="left",
        va="bottom",
        fontsize=7.2,
        color="#555555",
    )

    OUT_BASE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_BASE.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=0.03)
    fig.savefig(OUT_BASE.with_suffix(".pdf"), format="pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print(f"Saved {OUT_BASE.with_suffix('.pdf')}")


if __name__ == "__main__":
    render()
