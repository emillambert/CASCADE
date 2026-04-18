from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


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


def load_payload_optional(path: Path) -> dict | None:
    if not path.exists():
        return None
    return load_payload(path)


def _roc_by_fp(points: list[dict]) -> list[dict]:
    """Sort ROC-style points by mean FP rate so fill_between has non-decreasing x."""
    return sorted(points, key=lambda p: p["false_positive_rate_pct"])


def _clip_pct_series(values: list[float], *, lo: float = 0.0, hi: float = 100.0) -> list[float]:
    arr = np.asarray(values, dtype=float)
    arr = np.clip(arr, lo, hi)
    return [float(x) for x in arr.tolist()]


def _clip_point_recall(p: dict) -> dict:
    out = dict(p)
    if "science_retention_pct" in out:
        out["science_retention_pct"] = float(np.clip(out["science_retention_pct"], 0.0, 100.0))
    if "science_retention_ci95_low" in out:
        out["science_retention_ci95_low"] = float(np.clip(out["science_retention_ci95_low"], 0.0, 100.0))
    if "science_retention_ci95_high" in out:
        # Judges read recall as a percentage; CI must not exceed 100%.
        out["science_retention_ci95_high"] = float(np.minimum(out["science_retention_ci95_high"], 100.0))
    return out


def _recall_fill_arrays(points: list[dict]) -> tuple[list[float], list[float]]:
    lo = _clip_pct_series([p["science_retention_ci95_low"] for p in points])
    hi = [float(np.minimum(h, 100.0)) for h in [p["science_retention_ci95_high"] for p in points]]
    return lo, hi


def render(payload: dict, out_base: Path) -> None:
    roc_base = payload["ndwi_removed"]["roc_baseline"]["thresholds"]
    roc_no_ndwi = payload["ndwi_removed"]["roc_ndwi_removed"]["thresholds"]
    stride_points = sorted(payload["stage1_stride_sweep"], key=lambda p: p["stage1_stride"])
    cloud_points = sorted(payload["cloud_pass_prob_sweep"], key=lambda p: p["cloud_pass_prob"])

    blue = "#1f77b4"
    red = "#b00020"
    orange = "#d95f02"

    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.15))
    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#777777")
        ax.spines["bottom"].set_color("#777777")

    # Panel 1: threshold sweep (FP vs recall); x clipped to operating-relevant FP band
    ax = axes[0]
    rb = [_clip_point_recall(p) for p in _roc_by_fp(roc_base)]
    rn = [_clip_point_recall(p) for p in _roc_by_fp(roc_no_ndwi)]
    if rb and "science_retention_ci95_low" in rb[0]:
        rlo, rhi = _recall_fill_arrays(rb)
        ax.fill_between(
            [p["false_positive_rate_pct"] for p in rb],
            rlo,
            rhi,
            color=blue,
            alpha=0.15,
            linewidth=0,
            zorder=1,
        )
        rlo2, rhi2 = _recall_fill_arrays(rn)
        ax.fill_between(
            [p["false_positive_rate_pct"] for p in rn],
            rlo2,
            rhi2,
            color=red,
            alpha=0.15,
            linewidth=0,
            zorder=1,
        )
    ax.plot(
        [p["false_positive_rate_pct"] for p in rb],
        _clip_pct_series([p["science_retention_pct"] for p in rb]),
        marker="o",
        markersize=3,
        linewidth=1.6,
        color=blue,
        label="Baseline",
        zorder=2,
    )
    ax.plot(
        [p["false_positive_rate_pct"] for p in rn],
        _clip_pct_series([p["science_retention_pct"] for p in rn]),
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
    ax.set_ylim(96.0, 100.5)

    # Panel 2: stride — recall (left) capped 99–100.15; seasonal compute varies (right)
    ax = axes[1]
    stride_points = [_clip_point_recall(p) for p in stride_points]
    xstride = [p["stage1_stride"] for p in stride_points]
    if stride_points and "science_retention_ci95_low" in stride_points[0]:
        slo, shi = _recall_fill_arrays(stride_points)
        ax.fill_between(
            xstride,
            slo,
            shi,
            color=blue,
            alpha=0.15,
            linewidth=0,
            zorder=1,
        )
    ax.plot(
        xstride,
        _clip_pct_series([p["science_retention_pct"] for p in stride_points]),
        marker="o",
        markersize=3,
        linewidth=1.6,
        color=blue,
        label="Recall",
        zorder=2,
    )
    ax.set_title("Sparse screening cadence")
    ax.set_xlabel("Stage-1 stride (passes)")
    ax.set_ylabel("Recall (%)")
    ax.set_xticks(xstride)
    ax.set_ylim(99.0, 100.15)

    if stride_points and stride_points[0].get("seasonal_average_compute_utilisation_pct") is not None:
        ax2 = ax.twinx()
        ax2.plot(
            xstride,
            [p["seasonal_average_compute_utilisation_pct"] for p in stride_points],
            marker="s",
            markersize=3,
            linewidth=1.4,
            color=orange,
            linestyle="--",
            label="Seasonal compute",
            zorder=3,
        )
        ax2.set_ylabel("Seasonal compute (%)", color=orange)
        ax2.tick_params(axis="y", labelcolor=orange)
        ax2.spines["top"].set_visible(False)
        ax2.set_frame_on(True)
        lines1, lab1 = ax.get_legend_handles_labels()
        lines2, lab2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, lab1 + lab2, frameon=False, fontsize=7, loc="center right")
    else:
        ax.legend(frameon=False, fontsize=8, loc="lower right")

    # Panel 3: CSC sweep (preferred) or cloud fallback — recall left; FP% on twin (varies)
    ax = axes[2]
    repo_root = out_base.resolve().parents[1]
    csc_path = repo_root / "outputs/csc_sensitivity.json"
    csc = load_payload_optional(csc_path)
    csc_cases = (csc or {}).get("cases") if isinstance(csc, dict) else None
    has_csc_ci = bool(csc_cases and isinstance(csc_cases, list) and "science_retention_ci95_low" in csc_cases[0])

    if has_csc_ci:
        cases = [_clip_point_recall(p) for p in csc_cases]
        n = len(cases)
        x = np.arange(n, dtype=float)
        # Meaningful x: weight and saturation scale factors from sweep grid
        xlabs: list[str] = []
        for i, p in enumerate(cases):
            if "weight_sweep_scale" in p and "saturation_sweep_scale" in p:
                xlabs.append(f"w={p['weight_sweep_scale']:.2f}\ns={p['saturation_sweep_scale']:.2f}")
            else:
                xlabs.append(str(i))

        rlo, rhi = _recall_fill_arrays(cases)
        ax.fill_between(x, rlo, rhi, color=blue, alpha=0.15, linewidth=0, zorder=1)
        ax.plot(
            x,
            _clip_pct_series([p["science_retention_pct"] for p in cases]),
            marker="o",
            markersize=3,
            linewidth=1.6,
            color=blue,
            label="Recall",
            zorder=2,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(xlabs, fontsize=6, rotation=0)
        ax.set_title("CSC parameter sensitivity")
        ax.set_xlabel(r"$\pm30\%$ grid (weight $w$, saturation $s$)")
        ax.set_ylabel("Recall (%)")
        ax.set_ylim(99.0, 100.15)

        ax2 = ax.twinx()
        if "false_positive_rate_ci95_low" in cases[0]:
            ax2.fill_between(
                x,
                [p["false_positive_rate_ci95_low"] for p in cases],
                [p["false_positive_rate_ci95_high"] for p in cases],
                color=orange,
                alpha=0.12,
                linewidth=0,
                zorder=1,
            )
        ax2.plot(
            x,
            [p["false_positive_rate_pct"] for p in cases],
            marker="s",
            markersize=3,
            linewidth=1.4,
            color=orange,
            linestyle="--",
            label="FP rate",
            zorder=3,
        )
        ax2.set_ylabel("FP rate (%)", color=orange)
        ax2.tick_params(axis="y", labelcolor=orange)
        lines1, lab1 = ax.get_legend_handles_labels()
        lines2, lab2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, lab1 + lab2, frameon=False, fontsize=7, loc="upper right")
    else:
        cloud_points = [_clip_point_recall(p) for p in cloud_points]
        xc = [p["cloud_pass_prob"] for p in cloud_points]
        if cloud_points and "science_retention_ci95_low" in cloud_points[0]:
            clo, chi = _recall_fill_arrays(cloud_points)
            ax.fill_between(xc, clo, chi, color=blue, alpha=0.15, linewidth=0, zorder=1)
        ax.plot(
            xc,
            _clip_pct_series([p["science_retention_pct"] for p in cloud_points]),
            marker="o",
            markersize=3,
            linewidth=1.6,
            color=blue,
            label="Recall",
            zorder=2,
        )
        ax.set_title("Cloud mask strictness")
        ax.set_xlabel("Cloud-flag rate")
        ax.set_ylabel("Recall (%)")
        ax.set_ylim(99.0, 100.15)
        if cloud_points and cloud_points[0].get("false_positive_rate_pct") is not None:
            ax2 = ax.twinx()
            if "false_positive_rate_ci95_low" in cloud_points[0]:
                ax2.fill_between(
                    xc,
                    [p["false_positive_rate_ci95_low"] for p in cloud_points],
                    [p["false_positive_rate_ci95_high"] for p in cloud_points],
                    color=orange,
                    alpha=0.12,
                    linewidth=0,
                    zorder=1,
                )
            ax2.plot(
                xc,
                [p["false_positive_rate_pct"] for p in cloud_points],
                marker="s",
                markersize=3,
                linewidth=1.4,
                color=orange,
                linestyle="--",
                label="FP rate",
                zorder=3,
            )
            ax2.set_ylabel("FP rate (%)", color=orange)
            ax2.tick_params(axis="y", labelcolor=orange)
            lines1, lab1 = ax.get_legend_handles_labels()
            lines2, lab2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, lab1 + lab2, frameon=False, fontsize=7, loc="upper right")
        else:
            ax.legend(frameon=False, fontsize=8, loc="lower right")

    out_base.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.06, right=0.995, top=0.88, bottom=0.28, wspace=0.30)

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
