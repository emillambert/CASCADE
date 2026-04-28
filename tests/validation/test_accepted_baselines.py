from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.validation

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "accepted"
ARTIFACTS = ROOT / "artifacts"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_simulation_headline_metrics_match_accepted_baseline() -> None:
    current = read_json(ARTIFACTS / "benchmark" / "simulation_metrics.json")
    accepted = read_json(FIXTURES / "simulation_headline_metrics.json")
    subset = {key: current[key] for key in accepted}
    assert subset == accepted


def test_roc_operating_point_matches_accepted_baseline() -> None:
    current = read_json(ARTIFACTS / "benchmark" / "roc_metrics.json")
    accepted = read_json(FIXTURES / "roc_metrics.json")
    assert current == accepted


def test_csc_calibration_summary_matches_accepted_baseline() -> None:
    current = read_json(ARTIFACTS / "calibration" / "calibration_summary.json")
    accepted = read_json(FIXTURES / "csc_calibration_summary.json")
    assert current == accepted


def test_replay_anchor_matches_accepted_baseline() -> None:
    current = read_json(
        ARTIFACTS / "replay" / "westlands_ca_2024-06-01_2024-10-31" / "replay_metrics.json"
    )
    accepted = read_json(FIXTURES / "replay_metrics.json")
    assert current == accepted


def test_2014_replay_anchor_matches_report_claim() -> None:
    current = read_json(
        ARTIFACTS / "replay" / "westlands_ca_2014-06-01_2014-10-31" / "replay_metrics.json"
    )
    accepted = read_json(FIXTURES / "replay_metrics_2014.json")
    assert current == accepted


def test_unit_economics_summary_matches_accepted_baseline() -> None:
    current = read_json(ARTIFACTS / "economics" / "unit_economics.json")
    accepted = read_json(FIXTURES / "unit_economics_summary.json")
    subset = {key: current[key] for key in accepted}
    assert subset == accepted
