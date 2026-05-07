#!/usr/bin/env python3
"""
Compute a minimal NDWI ablation summary for the synthetic benchmark.

Outputs:
  build/benchmark/ndwi_ablation.json
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root / "src"))

    from cascade.core import CASCADEPolicy, Config
    from cascade.simulation import evaluate_policy, make_data

    n_seeds = 100
    datasets = [make_data(seed=seed) for seed in range(n_seeds)]

    cfg = Config()
    base = evaluate_policy("CASCADE_MDP", lambda: CASCADEPolicy(), cfg, datasets)

    cfg_no_ndwi = Config()
    setattr(cfg_no_ndwi, "ndwi_enabled", False)
    no_ndwi = evaluate_policy("CASCADE_MDP", lambda: CASCADEPolicy(), cfg_no_ndwi, datasets)

    out = {
        "n_seeds": n_seeds,
        "baseline": base["stats"],
        "ndwi_removed": no_ndwi["stats"],
    }

    out_path = repo_root / "build/benchmark/ndwi_ablation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

