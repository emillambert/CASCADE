from __future__ import annotations

import json
from pathlib import Path

from cascade.calibration import CalibrationSearchConfig, run_calibration


def test_small_calibration_run_is_deterministic_and_writes_expected_artifacts(
    tmp_path: Path,
) -> None:
    common = dict(
        rng_seed=11,
        stage1_candidates=12,
        stage2_parents=3,
        local_perturbations=4,
        train_seeds=(0, 1, 2, 3),
        validation_seeds=(4, 5),
        test_seeds=(6, 7),
        n_patches=32,
        n_t=40,
        n_dis=4,
        n_benign=2,
        cloud_pass_prob=0.25,
    )
    summary_a = run_calibration(
        CalibrationSearchConfig(
            output_dir=tmp_path / "run_a",
            **common,
        )
    )
    summary_b = run_calibration(
        CalibrationSearchConfig(
            output_dir=tmp_path / "run_b",
            **common,
        )
    )

    assert summary_a["split_definition"] == {
        "train": [0, 1, 2, 3],
        "validation": [4, 5],
        "test": [6, 7],
    }
    assert summary_a["search_outcomes"]["stage1_candidates_evaluated"] == 12
    assert summary_a["search_outcomes"]["stage2_candidates_evaluated"] <= 12
    assert summary_a["selected_candidate"] is not None
    assert summary_a["selected_candidate"]["parameters"] == summary_b["selected_candidate"]["parameters"]
    assert summary_a["promotion_status"] == summary_b["promotion_status"]

    for run_name in ("run_a", "run_b"):
        out_dir = tmp_path / run_name
        assert (out_dir / "calibration_summary.json").exists()
        assert (out_dir / "selected_candidate.json").exists()
        assert (out_dir / "top_candidates.json").exists()
        assert (out_dir / "pareto_candidates.json").exists()

    written = json.loads((tmp_path / "run_a" / "calibration_summary.json").read_text(encoding="utf-8"))
    assert written["promotion_status"] == summary_a["promotion_status"]
    assert written["baseline_candidate"]["parameters"] == summary_a["baseline_candidate"]["parameters"]
