# SPDX-License-Identifier: MIT
"""Replay workflows for CASCADE."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cascade.paths import DATA_CACHE_DIR
from cascade.replay.modis import parse_iso_date, run_window


_YEAR_WINDOWS: dict[int, tuple[str, str]] = {
    2014: ("2014-06-01", "2014-10-31"),
    2024: ("2024-06-01", "2024-10-31"),
}

_REPO_ROOT = Path(__file__).resolve().parents[3]

_ARTIFACT_REPLAY_METRICS: dict[int, Path] = {
    2014: _REPO_ROOT
    / "artifacts"
    / "replay"
    / "westlands_ca_2014-06-01_2014-10-31"
    / "replay_metrics.json",
    2024: _REPO_ROOT
    / "artifacts"
    / "replay"
    / "westlands_ca_2024-06-01_2024-10-31"
    / "replay_metrics.json",
}


@dataclass(frozen=True)
class ReplayResult:
    metrics: dict[str, Any]

    @property
    def peak_csc(self) -> float:
        return float(self.metrics.get("peak_csc", 0.0))

    @property
    def fuse_priority_windows(self) -> int:
        dist = self.metrics.get("action_distribution") or {}
        return int(dist.get("FUSE_PRIORITY", 0))


def replay(
    year: int,
    *,
    aoi: str = "westlands_ca",
    cache_dir: str | None = None,
    prefer_artifacts: bool = True,
    priority_mode: str = "legacy_max",
) -> dict[str, Any]:
    """Run (or reuse cached) MODIS replay for paper-anchor years.

    Returns the `replay_metrics.json` payload plus convenience keys used in tests.
    """
    if year not in _YEAR_WINDOWS:
        raise ValueError(f"Unsupported replay year: {year}. Supported: {sorted(_YEAR_WINDOWS)}")

    if prefer_artifacts and priority_mode == "legacy_max":
        artifact_path = _ARTIFACT_REPLAY_METRICS.get(year)
        if artifact_path and artifact_path.exists():
            metrics = json.loads(artifact_path.read_text(encoding="utf-8"))
            result = ReplayResult(metrics=metrics)
            return {
                **metrics,
                "peak_csc": result.peak_csc,
                "fuse_priority_windows": result.fuse_priority_windows,
                "source": "artifacts",
            }

    start, end = _YEAR_WINDOWS[year]
    cache_dir = cache_dir or str(DATA_CACHE_DIR)

    args = argparse.Namespace(
        aoi=aoi,
        bbox=None,
        aoi_label=None,
        start=start,
        end=end,
        cache_dir=cache_dir,
        csc_alert_thr=None,  # filled by modis.parse_args default in CLI; use default in policy when None.
        bundle_dir=None,
        bundle_zip=None,
        poll_seconds=20,
        max_poll_minutes=90,
        earthdata_username=None,
        earthdata_password=None,
        force_download=False,
        download_only=False,
        disable_date_extension=True,
        require_full_fusion=True,
        priority_mode=priority_mode,
    )

    # modis.run_window expects a float for csc_alert_thr; mirror CLI default by
    # leaving it unset and letting CASCADEPolicy default kick in.
    if args.csc_alert_thr is None:
        from cascade.core import CSC_ALERT_THRESHOLD_DEFAULT

        args.csc_alert_thr = float(CSC_ALERT_THRESHOLD_DEFAULT)

    _, metrics = run_window(args, parse_iso_date(start), parse_iso_date(end))
    result = ReplayResult(metrics=metrics)
    return {
        **metrics,
        "peak_csc": result.peak_csc,
        "fuse_priority_windows": result.fuse_priority_windows,
        "source": "live",
    }
