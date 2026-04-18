from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.edgecolor": "#666666",
            "axes.linewidth": 0.8,
            "grid.color": "#d9d9d9",
            "grid.linewidth": 0.8,
            "grid.alpha": 0.8,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _roc_by_fp(points: list[dict]) -> list[dict]:
    """Sort ROC-style points by mean FP rate so fill_between has non-decreasing x."""
    return sorted(points, key=lambda p: p["false_positive_rate_pct"])


def _ylim_recall(stride_points: list[dict], cloud_points: list[dict], pad: float = 0.35) -> tuple[float, float]:
    """Per-panel y range from recall mean + 95% CI; avoids flat 98–100% when variation is tiny."""
    lows: list[float] = []
    highs: list[float] = []
    for seq in (stride_points, cloud_points):
        for p in seq:
            lows.append(p["science_retention_pct"])
            highs.append(p["science_retention_pct"])
            if "science_retention_ci95_low" in p:
                lows.append(p["science_retention_ci95_low"])
                highs.append(p["science_retention_ci95_high"])
    if not lows:
        return 98.0, 100.5
    return min(lows) - pad, max(highs) + pad


def _ylim_roc(roc_base: list[dict], roc_no_ndwi: list[dict], pad: float = 0.35) -> tuple[float, float]:
    lows: list[float] = []
    highs: list[float] = []
    for seq in (roc_base, roc_no_ndwi):
        for p in seq:
            if "science_retention_ci95_low" in p:
                lows.append(p["science_retention_ci95_low"])
                highs.append(p["science_retention_ci95_high"])
            lows.append(p["science_retention_pct"])
            highs.append(p["science_retention_pct"])
    if not lows:
        return 98.0, 100.5
    return min(lows) - pad, max(highs) + pad


def render(payload: dict, out_base: Path) -> None:
    roc_base = payload["ndwi_removed"]["roc_baseline"]["thresholds"]
    roc_no_ndwi = payload["ndwi_removed"]["roc_ndwi_removed"]["thresholds"]
    stride_points = sorted(payload["stage1_stride_sweep"], key=lambda p: p["stage1_stride"])
    cloud_points = sorted(payload["cloud_pass_prob_sweep"], key=lambda p: p["cloud_pass_prob"])

    blue = "#1f77b4"
    red = "#b00020"

    fig, axes = plt.subplots(1, 3, figsize=(10.6, 3.1))
    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#777777")
        ax.spines["bottom"].set_color("#777777")

    # Panel 1: threshold sweep (FP vs recall); x clipped to operating-relevant FP band
    ax = axes[0]
    rb = _roc_by_fp(roc_base)
    rn = _roc_by_fp(roc_no_ndwi)
    if rb and "science_retention_ci95_low" in rb[0]:
        ax.fill_between(
            [p["false_positive_rate_pct"] for p in rb],
            [p["science_retention_ci95_low"] for p in rb],
            [p["science_retention_ci95_high"] for p in rb],
            color=blue,
            alpha=0.15,
            linewidth=0,
            zorder=1,
        )
        ax.fill_between(
            [p["false_positive_rate_pct"] for p in rn],
            [p["science_retention_ci95_low"] for p in rn],
            [p["science_retention_ci95_high"] for p in rn],
            color=red,
            alpha=0.15,
            linewidth=0,
            zorder=1,
        )
    ax.plot(
        [p["false_positive_rate_pct"] for p in rb],
        [p["science_retention_pct"] for p in rb],
        marker="o",
        markersize=3,
        linewidth=1.6,
        color=blue,
        label="Baseline",
        zorder=2,
    )
    ax.plot(
        [p["false_positive_rate_pct"] for p in rn],
        [p["science_retention_pct"] for p in rn],
        marker="o",
        markersize=3,
        linewidth=1.6,
        color=red,
        label="NDWI removed",
        zorder=2,
    )
    ax.set_title("CSC threshold sweep")
    ax.set_xlabel("FP rate (%)")
    ax.set_ylabel("Recall (%)")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    ax.set_xlim(0.0, 5.0)
    y0, y1 = _ylim_roc(rb, rn)
    ax.set_ylim(y0, y1)

    # Panel 2: stride sweep
    ax = axes[1]
    if stride_points and "science_retention_ci95_low" in stride_points[0]:
        ax.fill_between(
            [p["stage1_stride"] for p in stride_points],
            [p["science_retention_ci95_low"] for p in stride_points],
            [p["science_retention_ci95_high"] for p in stride_points],
            color=blue,
            alpha=0.15,
            linewidth=0,
            zorder=1,
        )
    ax.plot(
        [p["stage1_stride"] for p in stride_points],
        [p["science_retention_pct"] for p in stride_points],
        marker="o",
        markersize=3,
        linewidth=1.6,
        color=blue,
        zorder=2,
    )
    ax.set_title("Sparse screening cadence")
    ax.set_xlabel("Stage-1 stride (passes)")
    ax.set_ylabel("Recall (%)")
    ax.set_xticks([p["stage1_stride"] for p in stride_points])
    sy0, sy1 = _ylim_recall(stride_points, [])
    ax.set_ylim(sy0, sy1)

    # Panel 3: cloud strictness sweep
    ax = axes[2]
    if cloud_points and "science_retention_ci95_low" in cloud_points[0]:
        ax.fill_between(
            [p["cloud_pass_prob"] for p in cloud_points],
            [p["science_retention_ci95_low"] for p in cloud_points],
            [p["science_retention_ci95_high"] for p in cloud_points],
            color=blue,
            alpha=0.15,
            linewidth=0,
            zorder=1,
        )
    ax.plot(
        [p["cloud_pass_prob"] for p in cloud_points],
        [p["science_retention_pct"] for p in cloud_points],
        marker="o",
        markersize=3,
        linewidth=1.6,
        color=blue,
        zorder=2,
    )
    ax.set_title("Cloud mask strictness")
    ax.set_xlabel("Cloud-flag rate")
    ax.set_ylabel("Recall (%)")
    cy0, cy1 = _ylim_recall([], cloud_points)
    ax.set_ylim(cy0, cy1)

    out_base.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.06, right=0.995, top=0.88, bottom=0.22, wspace=0.28)

    fig.savefig(out_base.with_suffix(".png"), dpi=300)
    fig.savefig(out_base.with_suffix(".pdf"), format="pdf")
    fig.savefig(out_base.with_suffix(".svg"), format="svg")
    plt.close(fig)


def main() -> None:
    configure_style()
    repo_root = Path(__file__).resolve().parents[1]
    payload_path = repo_root / "outputs/additional_ablations.json"
    out_base = repo_root / "outputs/additional_ablation_curves"
    payload = load_payload(payload_path)
    render(payload, out_base)


if __name__ == "__main__":
    main()
