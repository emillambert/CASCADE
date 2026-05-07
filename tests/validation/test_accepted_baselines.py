from __future__ import annotations

import json
from pathlib import Path

import pytest

from cascade.replay.modis import AOIS


pytestmark = pytest.mark.validation

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "accepted"
ARTIFACTS = ROOT / "artifacts"

REQUIRED_REPLAY_PROVENANCE = {
    "aoi",
    "bbox",
    "start_date",
    "end_date",
    "code_commit",
    "appeears_task_id",
    "source_bundle_hash",
    "created_utc",
    "layers",
    "csc_stack_present",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_accepted_replay_artifact_is_auditable(metrics_path: Path) -> None:
    metrics = read_json(metrics_path)
    missing = REQUIRED_REPLAY_PROVENANCE - set(metrics)
    assert not missing, f"{metrics_path} lacks replay provenance fields: {sorted(missing)}"
    assert metrics["code_commit"]
    assert metrics["source_bundle_hash"]
    assert metrics["csc_stack_present"] is True
    assert (metrics_path.parent / "csc_stack.npz").exists()

    aoi = metrics["aoi"]
    assert aoi in AOIS
    assert metrics["bbox"] == AOIS[aoi]["bbox"]


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


def test_replay_artifacts_match_accepted_metrics_and_are_auditable() -> None:
    pairs = [
        (
            ARTIFACTS / "replay" / "westlands_ca_2014-06-01_2014-10-31" / "replay_metrics.json",
            FIXTURES / "replay_metrics_2014.json",
        ),
        (
            ARTIFACTS / "replay" / "westlands_ca_2024-06-01_2024-10-31" / "replay_metrics.json",
            FIXTURES / "replay_metrics.json",
        ),
    ]
    for artifact_path, fixture_path in pairs:
        assert_accepted_replay_artifact_is_auditable(artifact_path)
        assert read_json(artifact_path) == read_json(fixture_path)


def test_coherent_priority_replay_artifacts_are_auditable() -> None:
    metrics_paths = [
        ARTIFACTS
        / "replay"
        / "westlands_ca_2014-06-01_2014-10-31_coherent_priority"
        / "replay_metrics.json",
        ARTIFACTS
        / "replay"
        / "westlands_ca_2024-06-01_2024-10-31_coherent_priority"
        / "replay_metrics.json",
    ]
    for metrics_path in metrics_paths:
        assert_accepted_replay_artifact_is_auditable(metrics_path)
        metrics = read_json(metrics_path)
        assert metrics["priority_mode"] == "coherent_priority"
        assert metrics["action_distribution"].get("FUSE_PRIORITY", 0) == 0


def test_accepted_replay_artifact_validation_rejects_stale_wrong_aoi(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "stale"
    artifact_dir.mkdir()
    metrics_path = artifact_dir / "replay_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "aoi": "westlands_ca",
                "bbox": [-120.78, 36.19, -120.58, 36.34],
                "start_date": "2024-06-01",
                "end_date": "2024-10-31",
                "code_commit": "abc123",
                "appeears_task_id": "task",
                "source_bundle_hash": "hash",
                "created_utc": "2026-05-06T00:00:00Z",
                "layers": [],
                "csc_stack_present": True,
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "csc_stack.npz").write_bytes(b"placeholder")

    with pytest.raises(AssertionError):
        assert_accepted_replay_artifact_is_auditable(metrics_path)


def test_unit_economics_summary_matches_accepted_baseline() -> None:
    current = read_json(ARTIFACTS / "economics" / "unit_economics.json")
    accepted = read_json(FIXTURES / "unit_economics_summary.json")
    subset = {key: current[key] for key in accepted}
    assert subset == accepted
