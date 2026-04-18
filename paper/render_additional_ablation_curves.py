from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


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


def render(payload: dict, out_base: Path) -> None:
    roc_base = payload["ndwi_removed"]["roc_baseline"]["thresholds"]
    roc_no_ndwi = payload["ndwi_removed"]["roc_ndwi_removed"]["thresholds"]
    stride_points = payload["stage1_stride_sweep"]
    cloud_points = payload["cloud_pass_prob_sweep"]

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

    # Panel 1: threshold sweep
    ax = axes[0]
    # 2D CI rectangles (FP CI × Recall CI)
    for p in roc_base:
        if "false_positive_rate_ci95_low" not in p:
            break
        ax.add_patch(
            Rectangle(
                (p["false_positive_rate_ci95_low"], p["science_retention_ci95_low"]),
                p["false_positive_rate_ci95_high"] - p["false_positive_rate_ci95_low"],
                p["science_retention_ci95_high"] - p["science_retention_ci95_low"],
                facecolor=blue,
                edgecolor="none",
                alpha=0.12,
                zorder=1,
            )
        )
    for p in roc_no_ndwi:
        if "false_positive_rate_ci95_low" not in p:
            break
        ax.add_patch(
            Rectangle(
                (p["false_positive_rate_ci95_low"], p["science_retention_ci95_low"]),
                p["false_positive_rate_ci95_high"] - p["false_positive_rate_ci95_low"],
                p["science_retention_ci95_high"] - p["science_retention_ci95_low"],
                facecolor=red,
                edgecolor="none",
                alpha=0.12,
                zorder=1,
            )
        )
    ax.plot(
        [p["false_positive_rate_pct"] for p in roc_base],
        [p["science_retention_pct"] for p in roc_base],
        marker="o",
        linewidth=1.6,
        color=blue,
        label="Baseline",
    )
    ax.plot(
        [p["false_positive_rate_pct"] for p in roc_no_ndwi],
        [p["science_retention_pct"] for p in roc_no_ndwi],
        marker="o",
        linewidth=1.6,
        color=red,
        label="NDWI removed",
    )
    ax.set_title("CSC threshold sweep")
    ax.set_xlabel("FP rate (%)")
    ax.set_ylabel("Recall (%)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_ylim(98.2, 100.2)

    # Panel 2: stride sweep
    ax = axes[1]
    for p in stride_points:
        if "science_retention_ci95_low" not in p:
            break
        ax.add_patch(
            Rectangle(
                (p["stage1_stride"] - 0.12, p["science_retention_ci95_low"]),
                0.24,
                p["science_retention_ci95_high"] - p["science_retention_ci95_low"],
                facecolor=blue,
                edgecolor="none",
                alpha=0.12,
                zorder=1,
            )
        )
    ax.plot(
        [p["stage1_stride"] for p in stride_points],
        [p["science_retention_pct"] for p in stride_points],
        marker="o",
        linewidth=1.6,
        color=blue,
    )
    ax.set_title("Sparse screening cadence")
    ax.set_xlabel("Stage-1 stride (passes)")
    ax.set_ylabel("Recall (%)")
    ax.set_xticks([p["stage1_stride"] for p in stride_points])
    ax.set_ylim(98.2, 100.2)

    # Panel 3: cloud strictness sweep
    ax = axes[2]
    for p in cloud_points:
        if "science_retention_ci95_low" not in p:
            break
        ax.add_patch(
            Rectangle(
                (p["cloud_pass_prob"] - 0.01, p["science_retention_ci95_low"]),
                0.02,
                p["science_retention_ci95_high"] - p["science_retention_ci95_low"],
                facecolor=blue,
                edgecolor="none",
                alpha=0.12,
                zorder=1,
            )
        )
    ax.plot(
        [p["cloud_pass_prob"] for p in cloud_points],
        [p["science_retention_pct"] for p in cloud_points],
        marker="o",
        linewidth=1.6,
        color=blue,
    )
    ax.set_title("Cloud mask strictness")
    ax.set_xlabel("Cloud-flag rate")
    ax.set_ylabel("Recall (%)")
    ax.set_ylim(98.2, 100.2)

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

