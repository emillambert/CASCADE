from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

replay_api = importlib.import_module("cascade.replay")
replay_cli = importlib.import_module("cascade.replay.__main__")
from cascade.replay.modis import (
    aoi_geojson,
    classify_fusion_mode,
    csc_component_terms,
    crop_to_finite_extent,
    group_bundle_files,
    load_env_file,
    max_connected_component,
    mod09_valid_mask,
    mod11_valid_mask,
    parse_bbox,
    parse_calendar_date,
    parse_layer_name,
    peak_component_diagnostics,
    replay_provenance,
    replay_series,
    replay_output_dir_name,
    source_bundle_hash,
    spatial_priority_stats,
    summarize_fusion_availability,
    task_payload,
)
from cascade.replay import modis
from cascade.core import CSC_ALERT_THRESHOLD_DEFAULT, CASCADEPolicy


def test_bbox_parser_validates_custom_aoi_bounds() -> None:
    assert parse_bbox("-120.55,36.55,-120.45,36.65") == (-120.55, 36.55, -120.45, 36.65)

    with pytest.raises(argparse.ArgumentTypeError):
        parse_bbox("-120.45,36.55,-120.55,36.65")


def test_custom_aoi_geojson_uses_bbox_and_label() -> None:
    geo = aoi_geojson(
        "custom_area",
        bbox=(-120.55, 36.55, -120.45, 36.65),
        label="Custom Area",
    )

    feature = geo["features"][0]
    assert feature["properties"] == {"id": "custom_area", "label": "Custom Area"}
    assert feature["geometry"]["coordinates"][0] == [
        [-120.55, 36.55],
        [-120.45, 36.55],
        [-120.45, 36.65],
        [-120.55, 36.65],
        [-120.55, 36.55],
    ]


def test_task_payload_accepts_custom_aoi_bbox() -> None:
    payload = task_payload(
        "custom_area",
        date(2024, 6, 1),
        date(2024, 10, 31),
        bbox=(-120.55, 36.55, -120.45, 36.65),
        aoi_label="Custom Area",
    )

    assert payload["task_name"] == "cascade-custom_area-2024-06-01-2024-10-31"
    feature = payload["params"]["geo"]["features"][0]
    assert feature["properties"]["label"] == "Custom Area"
    assert feature["geometry"]["type"] == "Polygon"


def test_download_only_stops_before_replay_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle_dir = tmp_path / "bundle"

    def fake_download_only_bundle(args, start: date, end: date) -> Path:
        assert args.download_only
        assert start == date(2024, 6, 1)
        assert end == date(2024, 10, 31)
        bundle_dir.mkdir()
        return bundle_dir

    def fail_run_window(*_args, **_kwargs):
        raise AssertionError("download-only should not run replay outputs")

    monkeypatch.setattr(modis, "DOTENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(
        modis,
        "require_deps",
        lambda: (_ for _ in ()).throw(AssertionError("download-only should not require replay deps")),
    )
    monkeypatch.setattr(modis, "download_only_bundle", fake_download_only_bundle)
    monkeypatch.setattr(modis, "run_window", fail_run_window)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "real_modis_replay.py",
            "--aoi",
            "custom_area",
            "--bbox",
            "-120.55,36.55,-120.45,36.65",
            "--start",
            "2024-06-01",
            "--end",
            "2024-10-31",
            "--download-only",
        ],
    )

    modis.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["bundle_dir"] == str(bundle_dir)
    assert payload["aoi"] == "custom_area"
    assert payload["bbox"] == [-120.55, 36.55, -120.45, 36.65]


def test_replay_cli_accepts_priority_mode_and_passes_it_through(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_replay(year, **kwargs):
        kwargs["year"] = year
        captured.update(kwargs)
        return {"priority_mode": kwargs["priority_mode"], "source": "live"}

    monkeypatch.setattr(replay_cli, "replay", fake_replay)
    exit_code = replay_cli.main(
        [
            "--year",
            "2024",
            "--priority-mode",
            "coherent_priority",
            "--no-prefer-artifacts",
        ]
    )

    assert exit_code == 0
    assert captured["year"] == 2024
    assert captured["priority_mode"] == "coherent_priority"
    assert captured["prefer_artifacts"] is False
    payload = json.loads(capsys.readouterr().out)
    assert payload["priority_mode"] == "coherent_priority"


def test_replay_api_bypasses_artifacts_for_non_legacy_priority_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact_metrics.json"
    artifact_path.write_text(
        json.dumps(
            {
                "peak_csc": 0.412,
                "action_distribution": {"FUSE_PRIORITY": 0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(replay_api._ARTIFACT_REPLAY_METRICS, 2024, artifact_path)

    def fake_run_window(args, start: date, end: date):
        assert args.priority_mode == "coherent_priority"
        return tmp_path, {
            "peak_csc": 0.865,
            "action_distribution": {"FUSE_PRIORITY": 3},
            "priority_mode": args.priority_mode,
        }

    monkeypatch.setattr(replay_api, "run_window", fake_run_window)

    legacy = replay_api.replay(2024, prefer_artifacts=True, priority_mode="legacy_max")
    coherent = replay_api.replay(2024, prefer_artifacts=True, priority_mode="coherent_priority")

    assert legacy["source"] == "artifacts"
    assert legacy["peak_csc"] == pytest.approx(0.412)
    assert coherent["source"] == "live"
    assert coherent["priority_mode"] == "coherent_priority"
    assert coherent["fuse_priority_windows"] == 3


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


def test_spatial_priority_stats_measure_finite_alert_extent() -> None:
    csc = np.array(
        [
            [0.70, np.nan, 0.10],
            [0.10, 0.72, 0.74],
            [0.10, 0.73, 0.75],
        ],
        dtype="float32",
    )

    stats = spatial_priority_stats(csc, threshold=0.615)

    assert stats["alert_pixels"] == 5
    assert stats["alert_fraction"] == pytest.approx(5.0 / 8.0)
    assert stats["max_connected_component"] == 4
    assert stats["csc_p95"] > stats["csc_p99"] - 0.1


def test_connected_component_distinguishes_sparse_from_coherent_alerts() -> None:
    sparse = np.zeros((4, 4), dtype=bool)
    sparse[0, 0] = True
    sparse[3, 3] = True
    coherent = np.zeros((4, 4), dtype=bool)
    coherent[1:3, 1:3] = True

    assert max_connected_component(sparse) == 1
    assert max_connected_component(coherent) == 4


def test_crop_to_finite_extent_removes_blank_plot_borders() -> None:
    array = np.full((4, 5), np.nan, dtype="float32")
    array[1:, 1:4] = 0.2
    array[2, 3] = 0.9

    cropped = crop_to_finite_extent(array)

    assert cropped.shape == (3, 3)
    assert np.isfinite(cropped).all()
    assert cropped[1, 2] == pytest.approx(0.9)


def test_peak_component_attribution_uses_largest_weighted_term() -> None:
    evi_base = np.full((2, 2), 0.60, dtype="float32")
    lst_base = np.full((2, 2), 300.0, dtype="float32")
    ndwi_base = np.full((2, 2), 0.20, dtype="float32")
    evi = evi_base.copy()
    lst = lst_base.copy()
    ndwi = ndwi_base.copy()
    evi[1, 1] = 0.20
    lst[1, 1] = 306.0
    ndwi[1, 1] = 0.00
    terms = csc_component_terms(evi, lst, evi_base, lst_base, ndwi_t=ndwi, ndwi_base=ndwi_base)
    csc = terms["EVI"] + terms["LST"] + terms["NDWI"]

    peak_component, values = peak_component_diagnostics(csc, terms)

    assert peak_component == "EVI"
    assert values["EVI"] > values["LST"]
    assert values["EVI"] > values["NDWI"]
    assert values["evi_drop_sigma"] > 0.0


def test_replay_provenance_records_auditable_bundle_identity(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    tif = bundle_dir / "scene_A.tif"
    tif.write_bytes(b"fake geotiff bytes")
    manifest = {
        "task_id": "task-123",
        "aoi": "westlands_ca",
        "bbox": [-120.55, 36.55, -120.45, 36.65],
        "start": "2024-06-01",
        "end": "2024-10-31",
        "requested_layers": ["MOD13A1.061:_500m_16_days_EVI"],
        "files": [{"file_name": tif.name, "file_id": "file-1", "file_type": "tif"}],
    }
    (bundle_dir / "bundle_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    first_hash = source_bundle_hash(bundle_dir, manifest)
    provenance = replay_provenance(
        aoi="westlands_ca",
        bbox=(-120.55, 36.55, -120.45, 36.65),
        start=date(2024, 6, 1),
        end=date(2024, 10, 31),
        bundle_dir=bundle_dir,
        csc_stack_present=True,
    )

    assert provenance["aoi"] == "westlands_ca"
    assert provenance["bbox"] == [-120.55, 36.55, -120.45, 36.65]
    assert provenance["start_date"] == "2024-06-01"
    assert provenance["end_date"] == "2024-10-31"
    assert provenance["appeears_task_id"] == "task-123"
    assert provenance["source_bundle_hash"] == first_hash
    assert provenance["source_bundle_hash"] == source_bundle_hash(bundle_dir, manifest)
    assert provenance["code_commit"]
    assert provenance["created_utc"].endswith("Z")
    assert provenance["csc_stack_present"] is True


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

    assert {
        key: metrics[key]
        for key in [
            "aoi",
            "valid_windows",
            "cloud_obscured_windows",
            "baseline_windows",
            "action_distribution",
            "alert_windows",
            "first_alert_date",
            "peak_alert_date",
            "peak_csc",
            "mean_valid_fraction",
            "bundle_has_mod09",
            "ndwi_windows",
            "fallback_windows",
            "fusion_mode",
            "nominal_soc",
            "csc_alert_thr",
            "priority_mode",
            "notes",
        ]
    } == {
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
        "priority_mode": "legacy_max",
        "notes": "Real-scene policy replay on official MODIS products; not a labeled anomaly benchmark.",
    }
    assert metrics["csc_p95"] == pytest.approx(1.0)
    assert metrics["csc_p99"] == pytest.approx(1.0)
    assert metrics["alert_fraction"] == pytest.approx(1.0)
    assert metrics["max_connected_component"] == 4
    assert metrics["ever_alert_pixels"] == 4
    assert metrics["peak_component"] in {"EVI", "LST", "NDWI"}
    assert set(metrics["peak_component_values"]) == {
        "EVI",
        "LST",
        "NDWI",
        "evi_drop_sigma",
        "lst_rise_sigma",
        "ndwi_drop_sigma",
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
    assert replay_output_dir_name(
        "westlands_ca",
        start,
        end,
        CSC_ALERT_THRESHOLD_DEFAULT,
        priority_mode="coherent_priority",
    ) == "westlands_ca_2024-06-01_2024-10-31_coherent_priority"


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
