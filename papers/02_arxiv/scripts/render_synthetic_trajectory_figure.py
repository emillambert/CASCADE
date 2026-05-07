#!/usr/bin/env python3
"""
Render a single-seed synthetic trajectory plot for the arXiv manuscript.

Outputs:
  papers/02_arxiv/figures/Figure_4_synthetic_trajectory.pdf
"""

from __future__ import annotations

from pathlib import Path
import sys


def _require_pyplot():
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    return plt


def main() -> None:
    plt = _require_pyplot()

    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root / "src"))

    from cascade.core import CASCADEPolicy, Config
    from cascade.simulation import make_data, simulate

    out_path = repo_root / "papers/02_arxiv/figures/Figure_4_synthetic_trajectory.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    seed = 0
    data = make_data(seed=seed)
    cfg = Config()
    run = simulate("CASCADE_MDP", CASCADEPolicy(), data, cfg, outer_seed=seed, trace=True)
    tr = run["trace"]

    t = tr["t"]
    soc = tr["soc"]
    max_csc = tr["max_csc"]
    tp = tr["tp"]
    fp = tr["fp"]
    actions = tr["action"]
    dl = tr["downlink_window"]
    thr = float(run["detection_threshold"])

    priority_ts = [ti for ti, a in zip(t, actions) if a == "FUSE_PRIORITY"]

    fig, axes = plt.subplots(3, 1, figsize=(7.2, 6.4), sharex=True)

    ax = axes[0]
    ax.plot(t, soc, color="#1b5e8a", linewidth=1.6, label="Battery SOC")
    ax.set_ylabel("SOC")
    ax.set_ylim(0.0, 1.02)
    for ti, has_dl in zip(t, dl):
        if has_dl:
            ax.axvspan(ti - 0.5, ti + 0.5, color="#e0e0e0", alpha=0.25, linewidth=0)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.legend(frameon=False, fontsize=9, loc="lower right")

    ax = axes[1]
    ax.plot(t, max_csc, color="#b00020", linewidth=1.6, label="Max fused CSC")
    ax.axhline(thr, color="black", linewidth=1.0, alpha=0.7, linestyle="--", label=r"$\tau_{CSC}$")
    if priority_ts:
        ax.scatter(priority_ts, [max_csc[ti] for ti in priority_ts], s=18, color="#1b5e8a", label="Priority downlink")
    ax.set_ylabel("Max CSC")
    ax.set_ylim(0.0, 1.02)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.legend(frameon=False, fontsize=9, loc="lower right")

    ax = axes[2]
    ax.plot(t, tp, color="#1b5e8a", linewidth=1.6, label="Cumulative TP tiles")
    ax.plot(t, fp, color="#b00020", linewidth=1.6, label="Cumulative FP tiles")
    ax.set_ylabel("Tile count")
    ax.set_xlabel("Pass index")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.legend(frameon=False, fontsize=9, loc="upper left")

    fig.suptitle("Synthetic single-seed trajectory (seed 0)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path)
    plt.close(fig)


if __name__ == "__main__":
    main()

