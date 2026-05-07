#!/usr/bin/env python3
"""
Render detection-latency diagnostics for the synthetic benchmark.

Metric: passes from injected-anomaly onset to the first FUSE_PRIORITY pass that
detects that patch (i.e., exported as a priority alert tile).

Outputs:
  papers/02_arxiv/figures/Figure_5_detection_latency.pdf
"""

from __future__ import annotations

from collections import defaultdict
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

    out_path = repo_root / "papers/02_arxiv/figures/Figure_5_detection_latency.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_seeds = 100
    cfg = Config()

    latencies: list[int] = []
    never_priority = 0
    total_patches = 0

    for seed in range(n_seeds):
        data = make_data(seed=seed)
        run = simulate("CASCADE_MDP", CASCADEPolicy(), data, cfg, outer_seed=seed, trace=True)
        tr = run["trace"]

        # Map patch -> earliest pass where it appears in a priority true-positive set.
        earliest: dict[int, int] = {}
        for ti, patches in enumerate(tr["priority_tp_patches"]):
            for p in patches:
                earliest.setdefault(int(p), int(ti))

        for patch, onset in data["dis_onset"].items():
            total_patches += 1
            first = earliest.get(int(patch))
            if first is None:
                never_priority += 1
                continue
            latencies.append(int(first) - int(onset))

    latencies = [l for l in latencies if l >= 0]
    latencies.sort()

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4))

    ax = axes[0]
    if latencies:
        bins = list(range(0, max(latencies) + 2))
        ax.hist(latencies, bins=bins, color="#1b5e8a", alpha=0.85)
    ax.set_title("Priority detection latency histogram")
    ax.set_xlabel("Passes from onset to first priority TP")
    ax.set_ylabel("Count")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)

    ax = axes[1]
    if latencies:
        xs = latencies
        ys = [(i + 1) / len(xs) for i in range(len(xs))]
        ax.plot(xs, ys, color="#b00020", linewidth=1.8)
    ax.set_title("Empirical CDF")
    ax.set_xlabel("Passes from onset to first priority TP")
    ax.set_ylabel("CDF")
    ax.set_ylim(0.0, 1.02)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)

    suppressed = never_priority / max(total_patches, 1) * 100.0
    fig.suptitle(
        f"Synthetic priority-alert latency (CASCADE, {n_seeds} seeds). "
        f"Never-promoted: {never_priority}/{total_patches} ({suppressed:.1f}%)."
    )
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out_path)
    plt.close(fig)


if __name__ == "__main__":
    main()

