from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from masfe_core import Config, MASFEPolicy
from masfe_simulation import (
    ALERT_THRESH_SWEEP,
    build_datasets,
    make_data,
    run_monte_carlo,
    run_roc_sweep,
    simulate,
    write_multi_roc_plot,
    write_roc_plot,
)


def test_make_data_is_deterministic_and_preserves_expected_shapes() -> None:
    data_a = make_data(n_patches=32, n_t=40, n_dis=4, n_benign=2, seed=7, cloud_pass_prob=0.25)
    data_b = make_data(n_patches=32, n_t=40, n_dis=4, n_benign=2, seed=7, cloud_pass_prob=0.25)

    assert np.array_equal(data_a["evi"], data_b["evi"])
    assert np.array_equal(data_a["lst"], data_b["lst"])
    assert np.array_equal(data_a["ndwi"], data_b["ndwi"])
    assert np.array_equal(data_a["truth"], data_b["truth"])
    assert data_a["evi"].shape == (40, 32)
    assert data_a["truth"].dtype == bool
    assert len(data_a["dis_idx"]) == 4
    assert len(data_a["benign_onset"]) == 2


def test_simulate_small_seeded_case_remains_finite_and_more_efficient_than_raw() -> None:
    cfg = Config()
    data = make_data(n_patches=32, n_t=40, n_dis=4, n_benign=2, seed=11, cloud_pass_prob=0.15)

    raw = simulate("RAW_DUMP", None, data, cfg, outer_seed=11)
    masfe = simulate("MASFE_MDP", MASFEPolicy(), data, cfg, outer_seed=11)

    assert sum(raw["action_dist"].values()) == data["n_t"]
    assert sum(masfe["action_dist"].values()) == data["n_t"]
    assert np.isfinite(raw["energy"])
    assert np.isfinite(masfe["data_mb"])
    assert np.isfinite(masfe["min_batt"])
    assert np.isfinite(masfe["seasonal_average_compute_pct"])
    assert masfe["energy"] < raw["energy"]
    assert masfe["data_mb"] < raw["data_mb"]


def test_reduced_monte_carlo_and_roc_runs_keep_expected_schema_and_direction() -> None:
    cfg = Config()
    datasets = build_datasets(
        n_seeds=4,
        n_patches=32,
        n_t=40,
        n_dis=4,
        n_benign=2,
        cloud_pass_prob=0.25,
    )

    metrics = run_monte_carlo(
        cfg,
        n_seeds=4,
        n_patches=32,
        n_t=40,
        n_dis=4,
        n_benign=2,
        datasets=datasets,
    )
    roc_metrics = run_roc_sweep(cfg, datasets)

    assert metrics["monte_carlo"]["n_seeds"] == 4
    assert metrics["resolution_pyramid"]["screen_gsd_m"] == 30.0
    assert metrics["monte_carlo"]["policy_summary"]["MASFE_MDP"]["seasonal_average_compute_pct_mean"] < metrics[
        "monte_carlo"
    ]["policy_summary"]["FIXED_ONBOARD"]["seasonal_average_compute_pct_mean"]
    assert metrics["downlink_reduction_vs_raw_pct"] > 0.0

    thresholds = {point["threshold"]: point for point in roc_metrics["thresholds"]}
    assert roc_metrics["operating_point_threshold"] == 0.55
    assert [point["threshold"] for point in roc_metrics["thresholds"]] == ALERT_THRESH_SWEEP
    assert thresholds[0.40]["false_positive_rate_pct"] >= thresholds[0.55]["false_positive_rate_pct"]
    assert thresholds[0.55]["science_retention_pct"] >= thresholds[0.70]["science_retention_pct"]


@pytest.mark.slow
def test_plot_writers_create_png_files_when_matplotlib_is_available(tmp_path: Path) -> None:
    if importlib.util.find_spec("matplotlib") is None:
        pytest.skip("matplotlib is not installed")

    roc_metrics = {
        "thresholds": [
            {"threshold": 0.40, "science_retention_pct": 99.0, "false_positive_rate_pct": 2.0},
            {"threshold": 0.55, "science_retention_pct": 100.0, "false_positive_rate_pct": 1.5},
        ]
    }

    single_path = tmp_path / "roc.png"
    multi_path = tmp_path / "roc_compare.png"

    write_roc_plot(roc_metrics, single_path)
    write_multi_roc_plot(roc_metrics, roc_metrics, ("Baseline", "Ablation"), multi_path)

    assert single_path.exists() and single_path.stat().st_size > 0
    assert multi_path.exists() and multi_path.stat().st_size > 0
