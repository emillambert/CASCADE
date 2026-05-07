# SPDX-License-Identifier: MIT
"""Render the additional ablation figure for the CASCADE paper.

The paper figure keeps the two clearest curves large and moves CSC saturation
sensitivity into a compact artifact-backed callout.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.paths import ARTIFACTS_BENCHMARK_DIR, PAPER_FIGURES_DIR


BLUE = "#1f77b4"
RED = "#b00020"
ORANGE = "#d95f02"
GRAY = "#888888"
DARK = "#222222"
GRID = "#e0e0e0"
EDGE = "#888888"
PANEL_BG = "#fafafa"


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
            "axes.titlesize": 11.0,
            "axes.labelsize": 10.0,
            "xtick.labelsize": 9.2,
            "ytick.labelsize": 9.2,
            "axes.edgecolor": "#666666",
            "axes.linewidth": 0.75,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.alpha": 1.0,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "legend.fontsize": 8.8,
        }
    )


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _clip(values, lo=0.0, hi=100.0):
    return [float(np.clip(v, lo, hi)) for v in values]


def _spine_clean(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(EDGE)
    ax.spines["bottom"].set_color(EDGE)


def _interp(points: list[dict], threshold: float, field: str) -> float:
    xs = np.array([float(p["threshold"]) for p in points])
    ys = np.array([float(p[field]) for p in points])
    return float(np.interp(threshold, xs, ys))


def panel_threshold(ax, roc_payload: dict, ablation_payload: dict):
    roc_points = sorted(roc_payload["thresholds"], key=lambda p: p["threshold"])
    xs = [p["threshold"] for p in roc_points]
    recall = _clip([p["science_retention_pct"] for p in roc_points])
    fp = [p["false_positive_rate_pct"] for p in roc_points]
    op_thr = float(roc_payload.get("operating_point_threshold", 0.615018))

    ax.plot(xs, recall, color=BLUE, linewidth=2.0, marker="o", markersize=3.8, label="Recall")
    ax.axvline(op_thr, color=DARK, linewidth=1.0, linestyle="--")
    ax.text(op_thr + 0.006, 89.2, "operating\n0.615", ha="left", va="bottom", fontsize=7.7, color=DARK)

    annotation_xytext = {
        0.40: (0.455, 89.4),
        0.65: (0.626, 93.2),
        0.70: (0.655, 88.1),
    }
    for threshold in (0.40, 0.65, 0.70):
        point = min(roc_points, key=lambda p: abs(float(p["threshold"]) - threshold))
        ax.scatter([point["threshold"]], [point["science_retention_pct"]], s=38, color=BLUE, edgecolors="white", linewidths=0.7, zorder=5)
        text_x, text_y = annotation_xytext[threshold]
        ax.annotate(
            f"{point['threshold']:.2f}: {point['science_retention_pct']:.1f}% recall",
            xy=(point["threshold"], point["science_retention_pct"]),
            xytext=(text_x, text_y),
            fontsize=7.3,
            color=DARK,
            arrowprops=dict(arrowstyle="->", color=DARK, lw=0.65),
            ha="center",
        )

    ax.set_xlim(0.38, 0.715)
    ax.set_ylim(82, 101.5)
    ax.set_xlabel("CSC alert threshold")
    ax.set_ylabel("Recall (%)", color=BLUE)
    ax.tick_params(axis="y", labelcolor=BLUE)
    ax.set_title("(a) Threshold sweep")
    ax.set_xticks([0.40, 0.50, 0.60, 0.65, 0.70])
    ax.set_yticks([85, 90, 95, 100])
    _spine_clean(ax)

    ax2 = ax.twinx()
    ax2.plot(xs, fp, color=ORANGE, linewidth=1.8, marker="s", markersize=3.2, linestyle="-", label="FP rate")
    ax2.set_ylabel("FP rate (%)", color=ORANGE, labelpad=4)
    ax2.tick_params(axis="y", labelcolor=ORANGE)
    ax2.set_ylim(0, 2.1)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(EDGE)

    base_dense = sorted(
        ablation_payload["ndwi_removed"]["roc_baseline"]["thresholds"],
        key=lambda p: p["threshold"],
    )
    no_ndwi_dense = sorted(
        ablation_payload["ndwi_removed"]["roc_ndwi_removed"]["thresholds"],
        key=lambda p: p["threshold"],
    )
    dense_x = [x for x in np.linspace(0.40, 0.70, 120)]
    headline_fp = [_interp(roc_points, x, "false_positive_rate_pct") for x in dense_x]
    base_fp = [_interp(base_dense, x, "false_positive_rate_pct") for x in dense_x]
    no_ndwi_fp = [_interp(no_ndwi_dense, x, "false_positive_rate_pct") for x in dense_x]
    penalty_fp = [h + max(n - b, 0.0) for h, b, n in zip(headline_fp, base_fp, no_ndwi_fp)]
    ax2.fill_between(dense_x, headline_fp, penalty_fp, color=RED, alpha=0.10, linewidth=0, label="NDWI removed FP penalty")

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, frameon=False, loc="lower left", fontsize=7.4, ncol=3)


def panel_stride(ax, payload: dict):
    pts = sorted(payload["stage1_stride_sweep"], key=lambda p: p["stage1_stride"])
    xs = [p["stage1_stride"] for p in pts]
    recalls = _clip([p["science_retention_pct"] for p in pts])
    computes = [p["seasonal_average_compute_utilisation_pct"] for p in pts]

    if pts and "science_retention_ci95_low" in pts[0]:
        lo = _clip([p["science_retention_ci95_low"] for p in pts])
        hi = _clip([min(p["science_retention_ci95_high"], 100.0) for p in pts])
        ax.fill_between(xs, lo, hi, color=BLUE, alpha=0.18, linewidth=0, zorder=1)

    ax.plot(xs, recalls, color=BLUE, linewidth=0.9, linestyle=":", zorder=2, alpha=0.5)
    ax.scatter(xs, recalls, s=28, color=BLUE, zorder=3, label="Recall")
    ax.axhline(99.0, color=BLUE, linewidth=0.7, linestyle="--", alpha=0.45)
    ax.text(7.08, 99.02, "99.0%", color=BLUE, fontsize=7.2, va="bottom", alpha=0.7)

    ax.set_ylabel("Recall (%)", color=BLUE)
    ax.tick_params(axis="y", labelcolor=BLUE)
    ax.set_ylim(98.0, 100.5)
    ax.set_yticks([98, 99, 99.5, 100])
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))

    ax2 = ax.twinx()
    ax2.plot(xs, computes, color=ORANGE, linewidth=2.0, marker="s", markersize=4, label="Seasonal compute")
    ax2.set_ylabel("Seasonal compute (%)", color=ORANGE, labelpad=4)
    ax2.tick_params(axis="y", labelcolor=ORANGE)
    ax2.set_ylim(10, 65)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(EDGE)

    ax.annotate(
        "Recall range:\n99.6-100.0%",
        xy=(4.0, 99.86),
        xytext=(5.1, 99.16),
        fontsize=7.5,
        color=BLUE,
        arrowprops=dict(arrowstyle="->", color=BLUE, lw=0.7),
    )

    ax.set_xlabel("Stage-1 stride (passes)")
    ax.set_title("(b) Sparse screening cadence")
    ax.set_xticks(xs)
    ax.set_xticklabels([str(int(x)) if x == int(x) else "" for x in xs], fontsize=8.2)
    _spine_clean(ax)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, frameon=False, fontsize=7.5, loc="lower left")


def callout_saturation(ax, payload_csc: dict):
    cases = payload_csc["cases"]
    sats = sorted({float(p["saturation_sweep_scale"]) for p in cases})

    def by_sat(sat: float, field: str) -> list[float]:
        return [float(p[field]) for p in cases if float(p["saturation_sweep_scale"]) == sat]

    rows = []
    for sat in sats:
        recalls = by_sat(sat, "science_retention_pct")
        fps = by_sat(sat, "false_positive_rate_pct")
        rows.append((sat, float(np.mean(recalls)), float(np.mean(fps)), min(recalls), max(recalls)))

    nominal = next(row for row in rows if abs(row[0] - 1.0) < 1e-9)
    loose = next(row for row in rows if row[0] < 1.0)
    tight = next(row for row in rows if row[0] > 1.0)

    ax.axis("off")
    ax.set_facecolor(PANEL_BG)
    ax.add_patch(
        plt.Rectangle((0.02, 0.05), 0.96, 0.88, facecolor=PANEL_BG, edgecolor="#d5d5d5", linewidth=0.8)
    )
    ax.text(0.08, 0.84, "Saturation check", ha="left", va="center", fontsize=10.4, weight="bold", color=DARK)
    ax.text(0.08, 0.70, "Scale: 0.7 / 1.0 / 1.3x", ha="left", va="center", fontsize=8.3, color="#555555")
    ax.text(0.08, 0.56, f"s=0.70: {loose[1]:.1f}% recall\n{loose[2]:.2f}% FP", ha="left", va="center", fontsize=8.6, color=DARK)
    ax.text(0.08, 0.37, f"s=1.00: {nominal[1]:.1f}% recall\n{nominal[2]:.2f}% FP", ha="left", va="center", fontsize=8.6, color=DARK)
    ax.text(0.08, 0.17, f"s=1.30: {tight[1]:.1f}% recall\n{tight[2]:.1f}% FP", ha="left", va="center", fontsize=8.5, color=RED)


def main() -> None:
    configure_style()

    ablation_payload = load(ARTIFACTS_BENCHMARK_DIR / "additional_ablations.json")
    roc_payload = load(ARTIFACTS_BENCHMARK_DIR / "roc_metrics.json")
    payload_csc = load(ARTIFACTS_BENCHMARK_DIR / "csc_sensitivity.json")
    out_base = PAPER_FIGURES_DIR / "additional_ablation_curves"

    fig = plt.figure(figsize=(7.45, 5.3))
    gs = fig.add_gridspec(
        2,
        3,
        width_ratios=[1.0, 1.0, 0.88],
        height_ratios=[1.0, 1.0],
        hspace=0.52,
        wspace=0.42,
    )
    ax_threshold = fig.add_subplot(gs[0, 0:2])
    ax_callout = fig.add_subplot(gs[0, 2])
    ax_stride = fig.add_subplot(gs[1, :])

    for ax in (ax_threshold, ax_stride):
        ax.set_axisbelow(True)
        ax.grid(True, alpha=0.55)

    panel_threshold(ax_threshold, roc_payload, ablation_payload)
    panel_stride(ax_stride, ablation_payload)
    callout_saturation(ax_callout, payload_csc)

    fig.subplots_adjust(left=0.08, right=0.92, top=0.96, bottom=0.10)

    out_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".pdf"), format="pdf", bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".svg"), format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_base.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
