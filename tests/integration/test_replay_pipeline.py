from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from cascade.replay.modis import (
    classify_fusion_mode,
    group_bundle_files,
    load_env_file,
    mod09_valid_mask,
    mod11_valid_mask,
    parse_calendar_date,
    parse_layer_name,
    replay_series,
    replay_output_dir_name,
    summarize_fusion_availability,
)
from cascade.core import CSC_ALERT_THRESHOLD_DEFAULT, CASCADEPolicy


def test_parse_and_group_bundle_files_resolve_aliases_and_dates(tmp_path: Path) -> None:
    tif_dir = tmp_path / "bundle"
    tif_dir.mkdir()
    filenames = [
        "tile__500m_16_days_EVI_20240601T000000_demo.tif",
        "tile_sur_refl_b02_1_20240601T000000_demo.tif",
        "tile_QC_500m_1_20240601T000000_demo.tif",
    ]
    for name in filenames:
        (tif_dir / name).write_bytes(b"")

    assert parse_layer_name(filenames[0]) == "_500m_16_days_EVI"
    assert parse_layer_name(filenames[1]) == "sur_refl_b02"
    assert parse_layer_name(filenames[2]) == "sur_refl_qc_500m"
    assert parse_calendar_date(filenames[0]) == date(2024, 6, 1)

    grouped = group_bundle_files(tif_dir)
    assert list(grouped) == [date(2024, 6, 1)]
    assert set(grouped[date(2024, 6, 1)]) == {
        "_500m_16_days_EVI",
        "sur_refl_b02",
        "sur_refl_qc_500m",
    }


def test_load_env_file_populates_missing_values_without_overriding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "EARTHDATA_USERNAME=test-user\nEARTHDATA_PASSWORD='secret-pass'\nexport NASA_EARTHDATA_USERNAME=alias-user\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.setenv("EARTHDATA_PASSWORD", "already-set")
    monkeypatch.delenv("NASA_EARTHDATA_USERNAME", raising=False)

    load_env_file(env_path)

    assert "EARTHDATA_USERNAME" in os.environ
    assert os.environ["EARTHDATA_USERNAME"] == "test-user"
    assert os.environ["EARTHDATA_PASSWORD"] == "already-set"
    assert os.environ["NASA_EARTHDATA_USERNAME"] == "alias-user"


def test_quality_masks_filter_invalid_pixels() -> None:
    mod11_qc = np.array([[0, 1], [2, 192]], dtype="float32")
    assert mod11_valid_mask(mod11_qc).tolist() == [[True, True], [False, False]]

    mod09_qc = np.array([[0, 0], [3, 0]], dtype="float32")
    nir = np.array([[0.3, np.nan], [0.3, 2.0]], dtype="float32")
    swir = np.array([[0.1, 0.1], [0.1, 0.1]], dtype="float32")
    assert mod09_valid_mask(mod09_qc, nir, swir).tolist() == [[True, False], [False, False]]


def test_replay_series_covers_warmup_ndwi_fallback_priority_and_cloud_decay() -> None:
    base_evi = np.full((2, 2), 0.60, dtype="float32")
    base_lst = np.full((2, 2), 300.0, dtype="float32")
    base_ndwi = np.full((2, 2), 0.20, dtype="float32")
    start = date(2024, 6, 1)

    series = [
        {"date": start + timedelta(days=0), "clouded": False, "valid_fraction": 0.99, "evi": base_evi, "lst": base_lst, "ndwi": base_ndwi},
        {"date": start + timedelta(days=1), "clouded": False, "valid_fraction": 0.99, "evi": base_evi, "lst": base_lst, "ndwi": base_ndwi},
        {"date": start + timedelta(days=2), "clouded": False, "valid_fraction": 0.99, "evi": base_evi, "lst": base_lst, "ndwi": base_ndwi},
        {
            "date": start + timedelta(days=3),
            "clouded": False,
            "valid_fraction": 0.98,
            "evi": np.full((2, 2), 0.59, dtype="float32"),
            "lst": np.full((2, 2), 300.2, dtype="float32"),
            "ndwi": np.full((2, 2), 0.19, dtype="float32"),
        },
        {
            "date": start + timedelta(days=4),
            "clouded": False,
            "valid_fraction": 0.97,
            "evi": np.full((2, 2), 0.35, dtype="float32"),
            "lst": np.full((2, 2), 305.0, dtype="float32"),
            "ndwi": None,
        },
        {
            "date": start + timedelta(days=5),
            "clouded": False,
            "valid_fraction": 0.96,
            "evi": base_evi,
            "lst": base_lst,
            "ndwi": base_ndwi,
        },
        {"date": start + timedelta(days=6), "clouded": True, "valid_fraction": 0.0},
    ]

    policy = CASCADEPolicy(csc_alert_thr=CSC_ALERT_THRESHOLD_DEFAULT)
    steps, metrics, peak_alert_map, csc_snapshots = replay_series(series, policy)

    assert [step.action for step in steps] == [
        "BASELINE",
        "BASELINE",
        "BASELINE",
        "FUSE",
        "FUSE_PRIORITY",
        "MOD13",
        "MOD13",
    ]
    assert steps[3].note == "real-scene replay with NDWI"
    assert steps[4].note == "real-scene replay (EVI/LST fallback)"
    assert steps[4].alert_pixels == 4
    assert steps[4].csc_max >= policy.csc_alert_thr
    assert steps[6].csc_max == pytest.approx(steps[5].csc_max * 0.92, rel=1e-6)

    assert metrics == {
        "aoi": "westlands_ca",
        "valid_windows": 3,
        "cloud_obscured_windows": 1,
        "baseline_windows": 3,
        "action_distribution": {"FUSE": 1, "FUSE_PRIORITY": 1, "MOD13": 2},
        "alert_windows": 1,
        "first_alert_date": "2024-06-05",
        "peak_alert_date": "2024-06-05",
        "peak_csc": 1.0,
        "mean_valid_fraction": 0.728,
        "bundle_has_mod09": True,
        "ndwi_windows": 2,
        "fallback_windows": 1,
        "fusion_mode": "mixed",
        "nominal_soc": 0.84,
        "csc_alert_thr": 0.615018,
        "notes": "Real-scene policy replay on official MODIS products; not a labeled anomaly benchmark.",
    }
    assert peak_alert_map is not None
    assert len(csc_snapshots) == len(series)


def test_replay_series_threshold_override_promotes_borderline_peak() -> None:
    base_evi = np.full((2, 2), 0.60, dtype="float32")
    base_lst = np.full((2, 2), 300.0, dtype="float32")
    base_ndwi = np.full((2, 2), 0.20, dtype="float32")
    start = date(2024, 6, 1)

    series = [
        {"date": start + timedelta(days=0), "clouded": False, "valid_fraction": 0.99, "evi": base_evi, "lst": base_lst, "ndwi": base_ndwi},
        {"date": start + timedelta(days=1), "clouded": False, "valid_fraction": 0.99, "evi": base_evi, "lst": base_lst, "ndwi": base_ndwi},
        {"date": start + timedelta(days=2), "clouded": False, "valid_fraction": 0.99, "evi": base_evi, "lst": base_lst, "ndwi": base_ndwi},
        {
            "date": start + timedelta(days=3),
            "clouded": False,
            "valid_fraction": 0.98,
            "evi": np.full((2, 2), 0.39, dtype="float32"),
            "lst": base_lst,
            "ndwi": base_ndwi,
        },
    ]

    default_steps, default_metrics, _, _ = replay_series(
        series,
        CASCADEPolicy(csc_alert_thr=CSC_ALERT_THRESHOLD_DEFAULT),
    )
    sensitive_steps, sensitive_metrics, _, _ = replay_series(
        series,
        CASCADEPolicy(csc_alert_thr=0.40),
    )

    assert default_steps[-1].action == "FUSE"
    assert 0.40 < default_steps[-1].csc_max < CSC_ALERT_THRESHOLD_DEFAULT
    assert default_metrics["alert_windows"] == 0
    assert default_metrics["csc_alert_thr"] == pytest.approx(CSC_ALERT_THRESHOLD_DEFAULT)

    assert sensitive_steps[-1].action == "FUSE_PRIORITY"
    assert sensitive_steps[-1].alert_pixels == 4
    assert sensitive_metrics["alert_windows"] == 1
    assert sensitive_metrics["first_alert_date"] == "2024-06-04"
    assert sensitive_metrics["csc_alert_thr"] == pytest.approx(0.40)


def test_replay_output_dir_name_suffixes_only_non_default_thresholds() -> None:
    start = date(2024, 6, 1)
    end = date(2024, 10, 31)

    assert replay_output_dir_name("westlands_ca", start, end, CSC_ALERT_THRESHOLD_DEFAULT) == (
        "westlands_ca_2024-06-01_2024-10-31"
    )
    assert replay_output_dir_name("westlands_ca", start, end, 0.40) == (
        "westlands_ca_2024-06-01_2024-10-31_thr_0p400"
    )


def test_fusion_summary_and_mode_classification_are_explicit() -> None:
    series = [
        {"date": date(2024, 6, 1), "clouded": False, "valid_fraction": 0.99, "ndwi": np.ones((1, 1), dtype="float32")},
        {"date": date(2024, 6, 17), "clouded": False, "valid_fraction": 0.98, "ndwi": None},
        {"date": date(2024, 7, 3), "clouded": True, "valid_fraction": 0.0},
    ]

    summary = summarize_fusion_availability(series)
    assert summary == {
        "bundle_has_mod09": True,
        "series_valid_windows": 2,
        "series_ndwi_windows": 1,
        "series_fallback_windows": 1,
    }
    assert classify_fusion_mode(ndwi_windows=1, fallback_windows=0) == "ndwi_full"
    assert classify_fusion_mode(ndwi_windows=0, fallback_windows=2) == "evi_lst_fallback"
    assert classify_fusion_mode(ndwi_windows=1, fallback_windows=1) == "mixed"
