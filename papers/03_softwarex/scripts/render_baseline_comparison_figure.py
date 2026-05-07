# SPDX-License-Identifier: MIT
"""Render SoftwareX Figure 4 as a baseline-comparison figure."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.paths import ARTIFACTS_BENCHMARK_DIR, SOFTWAREX_FIGURES_DIR


OUT_BASE = SOFTWAREX_FIGURES_DIR / "Figure_4_baseline_comparison"
BASELINE_TABLE = ARTIFACTS_BENCHMARK_DIR / "baselines_comparison_table.tex"
HEADLINE_METRICS = ARTIFACTS_BENCHMARK_DIR / "simulation_metrics.json"

DARK = "#222222"
EDGE = "#777777"
GRID = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#1f4e79"
CASCADE = "#0f766e"


@dataclass(frozen=True)
class BaselineRow:
    label: str
    downlink_reduction_pct: float
    data_mb: float
    recall_pct: float
    false_positive_pct: float
    compute_pct: float | None


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
            "axes.titlesize": 10.0,
            "axes.labelsize": 8.8,
            "xtick.labelsize": 7.7,
            "ytick.labelsize": 7.7,
            "axes.edgecolor": EDGE,
            "axes.linewidth": 0.75,
            "grid.color": GRID,
            "grid.linewidth": 0.65,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def _clean_label(label: str) -> str:
    label = re.sub(r"\\rowcolor\{[^}]+\}", "", label)
    label = label.replace(r"\rowcolor{green!8}", "")
    return label.strip()


def load_rows() -> list[BaselineRow]:
    pattern = re.compile(
        r"^(?P<label>(?:\\rowcolor\{[^}]+\})?\s*[^&]+?)\s*&\s*"
        r"(?P<downlink>[\d.]+)\\%\s*&\s*"
        r"(?P<data>[\d.]+)\s*&\s*"
        r"(?P<recall>[\d.]+)\\%\s*&\s*"
        r"(?P<fp>[\d.]+)\\%\s*&\s*"
        r"(?P<compute>N/A|[\d.]+\\%)\s*\\\\"
    )
    rows: list[BaselineRow] = []
    for line in BASELINE_TABLE.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        compute = match.group("compute")
        rows.append(
            BaselineRow(
                label=_clean_label(match.group("label")),
                downlink_reduction_pct=float(match.group("downlink")),
                data_mb=float(match.group("data")),
                recall_pct=float(match.group("recall")),
                false_positive_pct=float(match.group("fp")),
                compute_pct=None if compute == "N/A" else float(compute.replace(r"\%", "")),
            )
        )
    if len(rows) != 5:
        raise RuntimeError(f"Expected 5 baseline rows in {BASELINE_TABLE}, found {len(rows)}")
    return rows


def render() -> None:
    configure_style()
    rows = load_rows()
    metrics = json.loads(HEADLINE_METRICS.read_text(encoding="utf-8"))
    ci = metrics["monte_carlo"]["per_metric_ci95"]

    labels = ["Raw downlink", "Fixed onboard", "EVI only", "No belief", "Full CASCADE"]
    y = np.arange(len(rows))
    data = np.array([row.data_mb for row in rows])
    colors = [CASCADE if row.label == "Full CASCADE" else MUTED for row in rows]

    fig = plt.figure(figsize=(7.1, 3.6))
    ax_bar = fig.add_axes((0.18, 0.17, 0.38, 0.72))
    ax_table = fig.add_axes((0.63, 0.13, 0.35, 0.78))

    ax_bar.barh(y, data, color=colors, edgecolor="white", linewidth=0.6)
    ax_bar.set_xscale("log")
    ax_bar.set_xlim(80, 30000)
    ax_bar.set_yticks(y, labels)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Downlink volume per season (MB, log scale)")
    ax_bar.set_title("(a) Downlink by policy", loc="left", weight="bold")
    ax_bar.grid(axis="x", which="major")
    ax_bar.set_axisbelow(True)
    for spine in ("top", "right"):
        ax_bar.spines[spine].set_visible(False)
    for row_index, row in enumerate(rows):
        ax_bar.text(
            row.data_mb * 1.08,
            row_index,
            f"{row.data_mb:.1f} MB",
            va="center",
            ha="left",
            fontsize=7.2,
            color=DARK,
        )

    ax_table.set_axis_off()
    ax_table.set_xlim(0.0, 1.0)
    ax_table.set_ylim(0.0, 1.0)
    ax_table.text(0.0, 1.0, "(b) Operating metrics", ha="left", va="top", fontsize=10.0, weight="bold", color=DARK)
    headers = ["Policy", "Recall", "FP", "Compute"]
    x_cols = [0.0, 0.47, 0.66, 0.82]
    y_top = 0.85
    row_h = 0.103
    ax_table.hlines(y_top, 0.0, 1.0, color="#9e9e9e", linewidth=0.55)
    for x, header in zip(x_cols, headers):
        ax_table.text(x, y_top + 0.035, header, ha="left", va="bottom", fontsize=7.2, weight="bold", color=DARK)
    for idx, row in enumerate(rows):
        y_mid = y_top - (idx + 0.5) * row_h
        color = CASCADE if row.label == "Full CASCADE" else DARK
        weight = "bold" if row.label == "Full CASCADE" else "normal"
        compute = "N/A" if row.compute_pct is None else f"{row.compute_pct:.1f}%"
        ax_table.text(x_cols[0], y_mid, row.label, ha="left", va="center", fontsize=7.0, color=color, weight=weight)
        ax_table.text(x_cols[1], y_mid, f"{row.recall_pct:.1f}%", ha="left", va="center", fontsize=7.0, color=color, weight=weight)
        ax_table.text(x_cols[2], y_mid, f"{row.false_positive_pct:.1f}%", ha="left", va="center", fontsize=7.0, color=color, weight=weight)
        ax_table.text(x_cols[3], y_mid, compute, ha="left", va="center", fontsize=7.0, color=color, weight=weight)
        ax_table.hlines(y_top - (idx + 1) * row_h, 0.0, 1.0, color="#c7c7c7", linewidth=0.45)

    ax_table.text(
        0.0,
        0.12,
        "Full CASCADE: 99.05% downlink reduction vs raw\n"
        f"(95% CI {ci['downlink_reduction_vs_raw_pct']['ci95_low']:.2f}-"
        f"{ci['downlink_reduction_vs_raw_pct']['ci95_high']:.2f}%).",
        ha="left",
        va="bottom",
        fontsize=7.0,
        color=ACCENT,
    )
    ax_table.text(
        0.0,
        0.025,
        f"Versus fixed onboard: {metrics['downlink_reduction_vs_fixed_pct']:.1f}% less downlink; "
        f"{metrics['energy_saving_vs_fixed_pct']:.1f}% less energy.",
        ha="left",
        va="bottom",
        fontsize=7.0,
        color=ACCENT,
    )

    OUT_BASE.parent.mkdir(parents=True, exist_ok=True)
    png_path = OUT_BASE.with_suffix(".png")
    pdf_path = OUT_BASE.with_suffix(".pdf")
    fig.savefig(png_path, dpi=300)
    plt.close(fig)
    Image.open(png_path).convert("RGB").save(pdf_path, "PDF", resolution=300.0)
    print(f"Saved {pdf_path}")


if __name__ == "__main__":
    render()
