#!/usr/bin/env python3
"""
Render CSC sensitivity heatmaps from build/benchmark/csc_sensitivity.json.

Outputs:
  papers/02_arxiv/figures/Figure_6_csc_sensitivity.pdf
"""

from __future__ import annotations

import json
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
    in_path = repo_root / "build/benchmark/csc_sensitivity.json"
    out_path = repo_root / "papers/02_arxiv/figures/Figure_6_csc_sensitivity.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        raise SystemExit(
            f"Missing {in_path}. Generate it first with `python -m cascade.simulate` "
            "or `python -m cascade.simulate --additional-ablations-only`."
        )

    payload = json.loads(in_path.read_text(encoding="utf-8"))
    w_scales = payload["weight_sweep_scale"]
    s_scales = payload["saturation_sweep_scale"]
    cases = payload["cases"]

    # Build 2D grids for recall and FP rate.
    recall = [[None for _ in s_scales] for _ in w_scales]
    fp = [[None for _ in s_scales] for _ in w_scales]
    precision = [[None for _ in s_scales] for _ in w_scales]

    by_key = {}
    for case in cases:
        by_key[(case["weight_sweep_scale"], case["saturation_sweep_scale"])] = case

    for i, w in enumerate(w_scales):
        for j, s in enumerate(s_scales):
            case = by_key.get((w, s))
            if case is None:
                continue
            recall[i][j] = case["science_retention_pct"]
            fp[i][j] = case["false_positive_rate_pct"]
            precision[i][j] = case["alert_precision_pct"]

    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.2), sharey=True)

    def heat(ax, grid, title, cmap):
        im = ax.imshow(grid, origin="lower", cmap=cmap, aspect="auto")
        ax.set_title(title)
        ax.set_xticks(range(len(s_scales)), [str(v) for v in s_scales])
        ax.set_yticks(range(len(w_scales)), [str(v) for v in w_scales])
        ax.set_xlabel("Saturation scale")
        ax.grid(False)
        for i in range(len(w_scales)):
            for j in range(len(s_scales)):
                val = grid[i][j]
                if val is None:
                    continue
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=8, color="black")
        return im

    im0 = heat(axes[0], recall, "Recall (%)", cmap="Blues")
    im1 = heat(axes[1], fp, "FP rate (%)", cmap="Reds")
    im2 = heat(axes[2], precision, "Precision (%)", cmap="Greens")
    axes[0].set_ylabel("Weight scale (EVI & NDWI)")

    for ax in axes:
        ax.tick_params(axis="x", labelrotation=0)

    fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
    fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)
    fig.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04)

    fig.suptitle("CSC sensitivity on synthetic benchmark (100 seeds)")
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(out_path)
    plt.close(fig)


if __name__ == "__main__":
    main()

