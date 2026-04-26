from __future__ import annotations

import json
from pathlib import Path

import pytest

from cascade.calibration import (
    CalibrationCandidate,
    annotate_candidate_record,
    candidate_is_within_bounds,
    current_default_candidate,
    evaluate_test_promotion,
    make_candidate,
    project_weights_to_bounds,
)


ROOT = Path(__file__).resolve().parents[2]
ACCEPTED = ROOT / "tests" / "fixtures" / "accepted" / "csc_calibration_summary.json"


def make_record(
    *,
    train_recall: float,
    validation_recall: float,
    validation_fp: float,
    validation_data_mb: float,
    validation_compute: float,
    validation_energy: float,
    test_recall: float = 99.5,
    test_fp: float = 1.0,
    test_data_mb: float = 95.0,
    test_compute: float = 48.0,
    test_energy: float = 5.8,
) -> dict:
    return {
        "parameters": current_default_candidate().as_dict(),
        "metrics_by_split": {
            "train": {
                "science_retention_pct": {"mean": train_recall},
            },
            "validation": {
                "science_retention_pct": {"mean": validation_recall},
                "false_positive_rate_pct": {"mean": validation_fp},
                "data_mb": {"mean": validation_data_mb},
                "seasonal_average_compute_utilisation_pct": {"mean": validation_compute},
                "energy_wh": {"mean": validation_energy},
            },
            "test": {
                "science_retention_pct": {"mean": test_recall},
                "false_positive_rate_pct": {"mean": test_fp},
                "data_mb": {"mean": test_data_mb},
                "seasonal_average_compute_utilisation_pct": {"mean": test_compute},
                "energy_wh": {"mean": test_energy},
            },
        },
        "distance_from_defaults": 0.0,
        "source_stage": "test",
    }


def test_project_weights_to_bounds_enforces_simplex_and_floor_ceiling() -> None:
    weights = project_weights_to_bounds([0.98, 0.01, 0.01])

    assert sum(weights) == pytest.approx(1.0)
    assert all(0.10 <= value <= 0.70 for value in weights)
    assert weights[0] == pytest.approx(0.70, abs=1e-6)


def test_make_candidate_clips_values_and_reports_validity() -> None:
    candidate = make_candidate(
        weights=[1.2, -0.1, -0.1],
        evi_saturation=10.0,
        lst_saturation=0.5,
        ndwi_saturation=8.0,
        csc_alert_thr=0.9,
    )

    assert candidate_is_within_bounds(candidate)
    assert candidate.evi_saturation == pytest.approx(7.0)
    assert candidate.lst_saturation == pytest.approx(2.5)
    assert candidate.ndwi_saturation == pytest.approx(6.0)
    assert candidate.csc_alert_thr == pytest.approx(0.70)


def test_annotate_candidate_record_applies_recall_and_guardrail_logic() -> None:
    baseline = make_record(
        train_recall=100.0,
        validation_recall=100.0,
        validation_fp=1.50,
        validation_data_mb=100.0,
        validation_compute=50.0,
        validation_energy=6.0,
    )
    candidate = make_record(
        train_recall=99.8,
        validation_recall=99.2,
        validation_fp=1.30,
        validation_data_mb=104.0,
        validation_compute=52.0,
        validation_energy=6.2,
    )

    annotated = annotate_candidate_record(candidate, baseline)
    assert annotated["feasible"]
    assert annotated["validation_fp_improvement_pct_points"] == pytest.approx(0.20)

    too_heavy = make_record(
        train_recall=99.8,
        validation_recall=99.2,
        validation_fp=1.20,
        validation_data_mb=106.0,
        validation_compute=52.0,
        validation_energy=6.2,
    )
    annotated_heavy = annotate_candidate_record(too_heavy, baseline)
    assert not annotated_heavy["feasible"]
    assert not annotated_heavy["validation_guardrails"]["data_mb"]["passes"]


def test_evaluate_test_promotion_requires_improvement_and_test_guardrails() -> None:
    baseline = make_record(
        train_recall=100.0,
        validation_recall=100.0,
        validation_fp=1.50,
        validation_data_mb=100.0,
        validation_compute=50.0,
        validation_energy=6.0,
        test_recall=100.0,
        test_fp=1.45,
        test_data_mb=98.0,
        test_compute=49.0,
        test_energy=5.9,
    )
    candidate = make_record(
        train_recall=99.9,
        validation_recall=99.3,
        validation_fp=1.35,
        validation_data_mb=103.0,
        validation_compute=51.5,
        validation_energy=6.1,
        test_recall=99.2,
        test_fp=1.30,
        test_data_mb=101.0,
        test_compute=50.0,
        test_energy=6.0,
    )
    annotated = annotate_candidate_record(candidate, baseline)
    promotion = evaluate_test_promotion(annotated, baseline)
    assert promotion["promoted"]

    weak = make_record(
        train_recall=99.9,
        validation_recall=99.3,
        validation_fp=1.43,
        validation_data_mb=103.0,
        validation_compute=51.5,
        validation_energy=6.1,
        test_recall=99.2,
        test_fp=1.40,
        test_data_mb=101.0,
        test_compute=50.0,
        test_energy=6.0,
    )
    weak_annotated = annotate_candidate_record(weak, baseline)
    weak_promotion = evaluate_test_promotion(weak_annotated, baseline)
    assert not weak_promotion["promoted"]


def test_current_defaults_match_the_accepted_calibration_record() -> None:
    if not ACCEPTED.exists():
        pytest.skip("accepted calibration fixture not generated yet")
    accepted = json.loads(ACCEPTED.read_text(encoding="utf-8"))
    selected = (
        accepted["selected_candidate"]
        if accepted.get("promotion_status", {}).get("promoted")
        else accepted["baseline_candidate"]
    )

    current = current_default_candidate()
    accepted_candidate = CalibrationCandidate(**selected["parameters"])

    assert current.as_dict() == accepted_candidate.as_dict()
