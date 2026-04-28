from __future__ import annotations

import json
from pathlib import Path

import pytest


pytest.importorskip("fastapi")
pytest.importorskip("cascade_console")


def test_console_preflight_shape() -> None:
    from cascade_console.app import collect_preflight

    preflight = collect_preflight()
    assert "python" in preflight
    assert "env" in preflight
    assert "cache" in preflight


def test_console_index_loads() -> None:
    from starlette.requests import Request

    from cascade_console.app import index

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []}, receive)
    response = index(request)
    assert response.status_code == 200
    assert b"CASCADE Local Engineering Console" in response.body
    assert b"Run Advanced" not in response.body
    assert b"No advanced controls" not in response.body
    assert b"Run Reviewer Mode" not in response.body
    assert b"Modify .env" in response.body


def test_console_env_writer_uses_quoted_values(tmp_path, monkeypatch) -> None:
    import cascade_console.app as console_app

    env_path = tmp_path / ".env"
    monkeypatch.setattr(console_app, "ENV_PATH", env_path)
    console_app.save_earthdata_env("reviewer", "pass word")

    written = env_path.read_text(encoding="utf-8")
    assert 'EARTHDATA_USERNAME="reviewer"' in written
    assert 'EARTHDATA_PASSWORD="pass word"' in written


def test_console_env_writer_rejects_blank_values(tmp_path, monkeypatch) -> None:
    import cascade_console.app as console_app

    monkeypatch.setattr(console_app, "ENV_PATH", tmp_path / ".env")
    with pytest.raises(Exception):
        console_app.save_earthdata_env("", "")


def test_console_rejects_result_path_escape() -> None:
    from fastapi import HTTPException

    from cascade_console.app import safe_result_path

    with pytest.raises(HTTPException):
        safe_result_path("artifacts", "../README.md")


def test_replay_default_command_keeps_builtin_westlands() -> None:
    from cascade_console.app import build_command

    command = build_command("replay", "reviewer", {})

    assert command[command.index("--aoi") + 1] == "westlands_ca"
    assert command[command.index("--start") + 1] == "2024-06-01"
    assert command[command.index("--end") + 1] == "2024-10-31"
    assert "--bbox" not in command
    assert "--download-only" not in command


def test_replay_custom_bbox_command_generates_stable_slug() -> None:
    from cascade_console.app import build_command

    command = build_command(
        "replay",
        "reviewer",
        {
            "use_bbox": "1",
            "aoi": "westlands_ca",
            "aoi_label": "Custom Area",
            "bbox": "-120.55,36.55,-120.45,36.65",
        },
    )

    assert command[command.index("--aoi") + 1] == "bbox_w120p550_n36p550_w120p450_n36p650"
    assert command[command.index("--bbox") + 1] == "-120.55,36.55,-120.45,36.65"
    assert command[command.index("--aoi-label") + 1] == "Custom Area"


def test_replay_cached_area_command_can_use_bundle_offline(tmp_path: Path) -> None:
    from cascade_console.app import build_command

    bundle_dir = tmp_path / "custom_bundle"
    command = build_command(
        "replay",
        "reviewer",
        {
            "use_bbox": "1",
            "aoi": "custom_area",
            "bbox": "-120.55,36.55,-120.45,36.65",
            "bundle_dir": str(bundle_dir),
        },
    )

    assert command[command.index("--aoi") + 1] == "custom_area"
    assert command[command.index("--bbox") + 1] == "-120.55,36.55,-120.45,36.65"
    assert command[command.index("--bundle-dir") + 1] == str(bundle_dir)


def test_replay_download_command_uses_download_only() -> None:
    from cascade_console.app import build_command

    command = build_command("replay", "download", {"aoi": "westlands_ca", "use_bbox": "0"})

    assert "--download-only" in command
    assert "--bbox" not in command


def test_replay_command_rejects_invalid_bbox() -> None:
    from fastapi import HTTPException

    from cascade_console.app import build_command

    with pytest.raises(HTTPException):
        build_command("replay", "reviewer", {"use_bbox": "1", "bbox": "-120.45,36.55,-120.55,36.65"})


def test_replay_area_discovery_backfills_old_westlands_manifest(tmp_path: Path) -> None:
    from cascade_console.app import replay_areas

    bundle = tmp_path / "westlands_ca_2024-06-01_2024-10-31"
    bundle.mkdir()
    (bundle / "bundle_manifest.json").write_text(
        json.dumps(
            {
                "aoi": "westlands_ca",
                "start": "2024-06-01",
                "end": "2024-10-31",
                "requested_layers": [],
                "files": [],
            }
        ),
        encoding="utf-8",
    )

    areas = replay_areas(tmp_path)
    cached = areas["cached"][0]
    assert cached["aoi"] == "westlands_ca"
    assert cached["bbox_text"] == "-120.55,36.55,-120.45,36.65"
    assert cached["uses_bbox"] is False
