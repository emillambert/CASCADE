"""Replay MASFE decisions on real MODIS scenes for one agricultural AOI.

This script uses AppEEARS area requests to fetch subset GeoTIFFs for:
  - MOD13A1.061: _500m_16_days_EVI, _500m_16_days_pixel_reliability
  - MOD11A1.061: LST_Day_1km, QC_Day
  - MOD09A1.061: sur_refl_b02, sur_refl_b06, sur_refl_qc_500m

The replay keeps the MASFE policy thresholds unchanged and treats the replay
as a content-driven policy validation workflow rather than a labeled disease
benchmark.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import requests

from masfe_core import (
    Config,
    MASFEPolicy,
    State,
    action_gsd_m,
    action_tile_density_mb_per_km2,
    compute_csc,
    posterior_mean,
    posterior_tail_probability,
    update_stress_belief,
)


APP_EEARS_API = "https://appeears.earthdatacloud.nasa.gov/api"
WARMUP_VALID_STEPS = 3
MIN_VALID_FRACTION = 0.60
LST_WINDOW_DAYS = 16
TARGET_SOC = 0.84

AOIS = {
    "westlands_ca": {
        "label": "Westlands / Firebaugh, California",
        "bbox": [-120.78, 36.19, -120.58, 36.34],
    }
}

MOD13_LAYERS = (
    "_500m_16_days_EVI",
    "_500m_16_days_pixel_reliability",
)
MOD11_LAYERS = (
    "LST_Day_1km",
    "QC_Day",
)
MOD09_LAYERS = (
    "sur_refl_b02",
    "sur_refl_b06",
    "sur_refl_qc_500m",
)
REQUESTED_LAYER_KEYS = tuple(
    [f"MOD13A1.061:{layer}" for layer in MOD13_LAYERS]
    + [f"MOD11A1.061:{layer}" for layer in MOD11_LAYERS]
    + [f"MOD09A1.061:{layer}" for layer in MOD09_LAYERS]
)
LAYER_ALIASES = {
    "_500m_16_days_EVI": "_500m_16_days_EVI",
    "_500m_16_days_pixel_reliability": "_500m_16_days_pixel_reliability",
    "LST_Day_1km": "LST_Day_1km",
    "QC_Day": "QC_Day",
    "sur_refl_b02_1": "sur_refl_b02",
    "sur_refl_b02": "sur_refl_b02",
    "sur_refl_b06_1": "sur_refl_b06",
    "sur_refl_b06": "sur_refl_b06",
    "QC_500m_1": "sur_refl_qc_500m",
    "sur_refl_qc_500m": "sur_refl_qc_500m",
}


@dataclass
class ReplayStep:
    step_date: date
    action: str
    valid_fraction: float
    csc_max: float
    alert_pixels: int
    gsd_m: float
    tile_density_mb_per_km2: float
    posterior_mean_max: float
    posterior_tail_max: float
    note: str


def log(message: str) -> None:
    print(f"[masfe] {message}", flush=True)


def require_deps():
    try:
        import matplotlib.pyplot as plt  # noqa: F401
        import pandas as pd  # noqa: F401
        import rasterio  # noqa: F401
        from rasterio.enums import Resampling  # noqa: F401
        from rasterio.warp import reproject  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing Python dependency: "
            f"{exc.name}. Install `pip3 install -r requirements.txt` first."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aoi", default="westlands_ca", choices=sorted(AOIS))
    parser.add_argument("--start", default="2024-06-01")
    parser.add_argument("--end", default="2024-09-30")
    parser.add_argument("--cache-dir", default="data/modis_cache")
    parser.add_argument(
        "--bundle-dir",
        help="Use an existing AppEEARS bundle directory instead of downloading through the API.",
    )
    parser.add_argument(
        "--bundle-zip",
        help="Use a single downloaded AppEEARS ZIP bundle instead of downloading through the API.",
    )
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--max-poll-minutes", type=int, default=90)
    parser.add_argument("--earthdata-username", default=os.environ.get("EARTHDATA_USERNAME") or os.environ.get("NASA_EARTHDATA_USERNAME"))
    parser.add_argument("--earthdata-password", default=os.environ.get("EARTHDATA_PASSWORD") or os.environ.get("NASA_EARTHDATA_PASSWORD"))
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument(
        "--disable-fallback",
        action="store_true",
        help="Do not auto-extend the replay window to October when the primary season is short.",
    )
    args = parser.parse_args()
    if args.bundle_dir and args.bundle_zip:
        parser.error("Use only one of --bundle-dir or --bundle-zip.")
    return args


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def format_app_date(value: date) -> str:
    return value.strftime("%m-%d-%Y")


def aoi_geojson(aoi_name: str) -> dict[str, Any]:
    west, south, east, north = AOIS[aoi_name]["bbox"]
    coords = [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
    ]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": aoi_name, "label": AOIS[aoi_name]["label"]},
                "geometry": {"type": "Polygon", "coordinates": [coords]},
            }
        ],
    }


class AppEEARSClient:
    def __init__(self, username: str | None, password: str | None):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.token: str | None = None

    def has_credentials(self) -> bool:
        return bool(self.username and self.password)

    def login(self) -> None:
        if self.token:
            return
        if not self.has_credentials():
            raise SystemExit(
                "No Earthdata credentials were found. Set EARTHDATA_USERNAME and "
                "EARTHDATA_PASSWORD or pass them as CLI arguments, or reuse an "
                "existing cache directory."
            )
        response = self.session.post(
            f"{APP_EEARS_API}/login",
            auth=(self.username, self.password),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        self.token = payload["token"]

    def headers(self) -> dict[str, str]:
        self.login()
        return {"Authorization": f"Bearer {self.token}"}

    def submit_task(self, payload: dict[str, Any]) -> str:
        response = self.session.post(
            f"{APP_EEARS_API}/task",
            json=payload,
            headers=self.headers(),
            timeout=60,
        )
        response.raise_for_status()
        task = response.json()
        return task["task_id"]

    def task_status(self, task_id: str) -> dict[str, Any]:
        response = self.session.get(
            f"{APP_EEARS_API}/status/{task_id}",
            headers=self.headers(),
            allow_redirects=False,
            timeout=30,
        )
        if response.status_code == 303:
            return {"task_id": task_id, "status": "done"}
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload[0]
        return payload

    def wait_for_task(self, task_id: str, poll_seconds: int, max_poll_minutes: int) -> None:
        deadline = time.time() + max_poll_minutes * 60
        started = time.time()
        last_label = None
        poll_count = 0
        while time.time() < deadline:
            status = self.task_status(task_id)
            label = status.get("status", "unknown")
            detail = status.get("message") or status.get("summary") or ""
            elapsed_min = (time.time() - started) / 60.0
            poll_count += 1
            heartbeat_every = max(1, int(round(60 / max(1, poll_seconds))))
            if label != last_label or poll_count % heartbeat_every == 0:
                suffix = f" — {detail}" if detail else ""
                log(f"AppEEARS task {task_id}: {label} after {elapsed_min:.1f} min{suffix}")
                last_label = label
            if label == "done":
                log(f"AppEEARS task {task_id}: complete")
                return
            time.sleep(poll_seconds)
        raise TimeoutError(f"Timed out waiting for AppEEARS task {task_id}")

    def list_bundle_files(self, task_id: str) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{APP_EEARS_API}/bundle/{task_id}",
            headers=self.headers(),
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("files", [])

    def download_bundle_file(self, task_id: str, file_id: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(
            f"{APP_EEARS_API}/bundle/{task_id}/{file_id}",
            headers=self.headers(),
            timeout=300,
            stream=True,
        ) as response:
            response.raise_for_status()
            with destination.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)


def cache_root(cache_dir: Path, aoi: str, start: date, end: date) -> Path:
    return cache_dir / f"{aoi}_{start.isoformat()}_{end.isoformat()}"


def find_tifs(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.tif") if path.is_file())


def load_manifest(manifest_path: Path) -> dict[str, Any] | None:
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def reuse_from_existing_caches(
    cache_dir: Path,
    bundle_dir: Path,
    requested_files: list[dict[str, Any]],
    aoi: str,
    start: date,
    end: date,
) -> int:
    prefix = f"{aoi}_{start.isoformat()}_"
    candidates = [
        path
        for path in cache_dir.iterdir()
        if path.is_dir() and path.name.startswith(prefix) and path.name != bundle_dir.name
    ]
    if not candidates:
        return 0

    basename_to_source: dict[str, Path] = {}
    for candidate in candidates:
        for tif in find_tifs(candidate):
            basename_to_source.setdefault(tif.name, tif)

    reused = 0
    for item in requested_files:
        destination = bundle_dir / item["file_name"]
        if destination.exists() and destination.stat().st_size > 0:
            continue
        source = basename_to_source.get(destination.name)
        if source is None:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        reused += 1

    if reused:
        log(
            f"Reused {reused} overlapping GeoTIFFs from existing {aoi} cache "
            f"for {start.isoformat()} to {end.isoformat()}"
        )
    return reused


def prepare_local_bundle(
    cache_dir: Path,
    aoi: str,
    start: date,
    end: date,
    bundle_dir_override: str | None,
    bundle_zip: str | None,
    force_download: bool,
) -> Path | None:
    if bundle_dir_override:
        source_dir = Path(bundle_dir_override).expanduser().resolve()
        tif_files = find_tifs(source_dir)
        if not tif_files:
            raise SystemExit(f"No .tif files were found under {source_dir}")
        return source_dir

    if not bundle_zip:
        return None

    archive_path = Path(bundle_zip).expanduser().resolve()
    if not archive_path.exists():
        raise SystemExit(f"Bundle ZIP not found: {archive_path}")

    extract_dir = cache_root(cache_dir, aoi, start, end) / "local_bundle"
    if force_download and extract_dir.exists():
        for path in sorted(extract_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    extract_dir.mkdir(parents=True, exist_ok=True)

    if not find_tifs(extract_dir):
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(extract_dir)

    tif_files = find_tifs(extract_dir)
    if not tif_files:
        raise SystemExit(f"No .tif files were found after extracting {archive_path}")
    return extract_dir


def task_payload(aoi: str, start: date, end: date) -> dict[str, Any]:
    return {
        "task_type": "area",
        "task_name": f"masfe-{aoi}-{start.isoformat()}-{end.isoformat()}",
        "params": {
            "dates": [{"startDate": format_app_date(start), "endDate": format_app_date(end)}],
            "layers": (
                [{"product": "MOD13A1.061", "layer": layer} for layer in MOD13_LAYERS]
                + [{"product": "MOD11A1.061", "layer": layer} for layer in MOD11_LAYERS]
                + [{"product": "MOD09A1.061", "layer": layer} for layer in MOD09_LAYERS]
            ),
            "geo": aoi_geojson(aoi),
            "output": {
                "format": {"type": "geotiff", "filename_date": "calendar"},
                "projection": "geographic",
            },
        },
    }


def download_or_reuse_bundle(
    client: AppEEARSClient,
    aoi: str,
    start: date,
    end: date,
    cache_dir: Path,
    bundle_dir_override: str | None,
    bundle_zip: str | None,
    poll_seconds: int,
    max_poll_minutes: int,
    force_download: bool,
) -> Path:
    local_bundle = prepare_local_bundle(
        cache_dir=cache_dir,
        aoi=aoi,
        start=start,
        end=end,
        bundle_dir_override=bundle_dir_override,
        bundle_zip=bundle_zip,
        force_download=force_download,
    )
    if local_bundle is not None:
        return local_bundle

    bundle_dir = cache_root(cache_dir, aoi, start, end)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = bundle_dir / "bundle_manifest.json"
    manifest = load_manifest(manifest_path)
    existing_tifs = find_tifs(bundle_dir)
    requested_layers = list(REQUESTED_LAYER_KEYS)
    manifest_matches_request = bool(manifest and manifest.get("requested_layers") == requested_layers)
    if existing_tifs and manifest and manifest.get("files") and not force_download:
        expected = sum(1 for item in manifest["files"] if item.get("file_type", "").lower() == "tif")
        if len(existing_tifs) >= expected and manifest_matches_request:
            log(f"Reusing cached bundle in {bundle_dir} ({len(existing_tifs)} GeoTIFFs found)")
            return bundle_dir
        if len(existing_tifs) >= expected and not manifest_matches_request and not client.has_credentials():
            log(
                "Reusing cached bundle without MOD09A1 NDWI layers because no Earthdata "
                "credentials are available; replay will fall back to EVI/LST fusion where needed."
            )
            return bundle_dir

    task_id = manifest.get("task_id") if manifest else None
    if task_id and not force_download and manifest_matches_request:
        log(f"Resuming existing AppEEARS task {task_id}")
    else:
        log(f"Submitting AppEEARS area request for {aoi} {start.isoformat()} to {end.isoformat()}")
        task_id = client.submit_task(task_payload(aoi, start, end))
        log(f"Submitted AppEEARS task {task_id}")
        manifest = {
            "task_id": task_id,
            "aoi": aoi,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "requested_layers": requested_layers,
            "files": [],
        }
        save_manifest(manifest_path, manifest)

    client.wait_for_task(task_id, poll_seconds=poll_seconds, max_poll_minutes=max_poll_minutes)
    files = client.list_bundle_files(task_id)
    tif_files = [item for item in files if item.get("file_type", "").lower() == "tif"]
    if not tif_files:
        raise RuntimeError(f"No GeoTIFF outputs were returned for task {task_id}")

    manifest = {
        "task_id": task_id,
        "aoi": aoi,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "requested_layers": requested_layers,
        "files": tif_files,
    }
    save_manifest(manifest_path, manifest)
    reuse_from_existing_caches(
        cache_dir=cache_dir,
        bundle_dir=bundle_dir,
        requested_files=tif_files,
        aoi=aoi,
        start=start,
        end=end,
    )

    total = len(tif_files)
    # Parallelize bundle downloads with a small bounded pool.
    max_workers = int(os.environ.get("APPEEARS_DOWNLOAD_WORKERS", "6"))
    max_workers = max(1, min(max_workers, 12))

    skipped = 0
    to_download: list[tuple[int, dict, Path]] = []
    for index, item in enumerate(tif_files, start=1):
        destination = bundle_dir / item["file_name"]
        if destination.exists() and destination.stat().st_size > 0 and not force_download:
            skipped += 1
        else:
            to_download.append((index, item, destination))

    downloaded = 0
    failures: list[str] = []

    def _download_one(file_id: str, destination: Path) -> None:
        # Use a fresh session per worker for thread safety.
        url = f"{APP_EEARS_API}/bundle/{task_id}/{file_id}"
        headers = {}
        if getattr(client, "token", None):
            headers["Authorization"] = f"Bearer {client.token}"
        with requests.Session() as session:
            with session.get(url, headers=headers, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

    if to_download:
        log(f"Downloading {len(to_download)}/{total} GeoTIFFs with {max_workers} workers")
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = {
                pool.submit(_download_one, item["file_id"], destination): (index, item["file_name"])
                for (index, item, destination) in to_download
            }
            for fut in as_completed(futs):
                index, name = futs[fut]
                try:
                    fut.result()
                    downloaded += 1
                    if downloaded == 1 or downloaded == len(to_download) or downloaded % 25 == 0:
                        log(f"Download progress: {downloaded}/{len(to_download)} completed (e.g., {name})")
                except Exception as e:
                    failures.append(f"{name}: {e}")

    if failures:
        raise RuntimeError(
            "One or more AppEEARS bundle downloads failed:\n" + "\n".join(f"- {msg}" for msg in failures)
        )

    log(
        f"Bundle ready in {bundle_dir} "
        f"({total} GeoTIFFs, {downloaded} downloaded this run, {skipped} reused)"
    )
    return bundle_dir


def parse_layer_name(filename: str) -> str | None:
    for alias, canonical in sorted(LAYER_ALIASES.items(), key=lambda item: -len(item[0])):
        if alias in filename:
            return canonical
    return None


def parse_calendar_date(filename: str) -> date:
    match = re.search(r"_(\d{8})T\d{6}_", filename)
    if not match:
        match = re.search(r"_(\d{8})_", filename)
    if not match:
        raise ValueError(f"Could not parse date from {filename}")
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def group_bundle_files(bundle_dir: Path) -> dict[date, dict[str, Path]]:
    grouped: dict[date, dict[str, Path]] = {}
    for path in find_tifs(bundle_dir):
        layer = parse_layer_name(path.name)
        if layer is None:
            continue
        step_date = parse_calendar_date(path.name)
        grouped.setdefault(step_date, {})[layer] = path
    return grouped


def mod11_valid_mask(qc: np.ndarray) -> np.ndarray:
    qc_int = np.nan_to_num(qc, nan=255).astype("uint8")
    mandatory = qc_int & 0b11
    lst_error = (qc_int >> 6) & 0b11
    return (mandatory <= 1) & (lst_error <= 1)


def read_raster(path: Path, scale_override: float | None = None):
    import rasterio

    with rasterio.open(path) as src:
        array = src.read(1).astype("float32")
        nodata = src.nodata
        tags = src.tags()
        profile = {
            "crs": src.crs,
            "transform": src.transform,
            "width": src.width,
            "height": src.height,
            "dtype": "float32",
            "nodata": np.nan,
        }
    if nodata is not None:
        array[array == nodata] = np.nan
    scale_factor = float(tags.get("scale_factor", "1") or "1")
    add_offset = float(tags.get("add_offset", "0") or "0")
    if scale_override is not None and scale_factor == 1.0:
        scale_factor = scale_override
    if scale_factor != 1.0 or add_offset != 0.0:
        finite = np.isfinite(array)
        array[finite] = array[finite] * scale_factor + add_offset
    return array, profile


def reproject_average(src_array, src_profile, dst_profile):
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    src_nodata = -9999.0
    dst_nodata = -9999.0
    src = np.where(np.isfinite(src_array), src_array, src_nodata).astype("float32")
    dst = np.full((dst_profile["height"], dst_profile["width"]), dst_nodata, dtype="float32")
    reproject(
        source=src,
        destination=dst,
        src_transform=src_profile["transform"],
        src_crs=src_profile["crs"],
        src_nodata=src_nodata,
        dst_transform=dst_profile["transform"],
        dst_crs=dst_profile["crs"],
        dst_nodata=dst_nodata,
        resampling=Resampling.average,
    )
    dst[dst == dst_nodata] = np.nan
    return dst


def median_lst_window(grouped_files: dict[date, dict[str, Path]], step_date: date):
    candidates = []
    profile = None
    for obs_date, files in sorted(grouped_files.items()):
        if not (step_date - timedelta(days=LST_WINDOW_DAYS - 1) <= obs_date <= step_date):
            continue
        if "LST_Day_1km" not in files or "QC_Day" not in files:
            continue
        lst, profile = read_raster(files["LST_Day_1km"])
        qc, _ = read_raster(files["QC_Day"])
        valid = mod11_valid_mask(qc) & np.isfinite(lst)
        masked = np.where(valid, lst, np.nan)
        if np.isfinite(masked).any():
            candidates.append(masked)
    if not candidates or profile is None:
        return None, None
    return np.nanmedian(np.stack(candidates, axis=0), axis=0), profile


def mod09_valid_mask(qc: np.ndarray, nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    qc_int = np.nan_to_num(qc, nan=3).astype("uint32")
    modland = qc_int & 0b11
    reflectance_ok = (
        np.isfinite(nir)
        & np.isfinite(swir)
        & (nir >= -0.01)
        & (nir <= 1.6)
        & (swir >= -0.01)
        & (swir <= 1.6)
        & (np.abs(nir + swir) > 1e-6)
    )
    return (modland <= 1) & reflectance_ok


def median_ndwi_window(
    grouped_files: dict[date, dict[str, Path]],
    step_date: date,
    dst_profile: dict[str, Any],
):
    candidates = []
    for obs_date, files in sorted(grouped_files.items()):
        if not (step_date - timedelta(days=LST_WINDOW_DAYS - 1) <= obs_date <= step_date):
            continue
        if not all(layer in files for layer in MOD09_LAYERS):
            continue
        nir, mod09_profile = read_raster(files["sur_refl_b02"], scale_override=0.0001)
        swir, _ = read_raster(files["sur_refl_b06"], scale_override=0.0001)
        qc, _ = read_raster(files["sur_refl_qc_500m"])
        valid = mod09_valid_mask(qc, nir, swir)
        ndwi = np.where(valid, (nir - swir) / (nir + swir), np.nan)
        ndwi_1km = reproject_average(ndwi, mod09_profile, dst_profile)
        if np.isfinite(ndwi_1km).any():
            candidates.append(ndwi_1km)
    if not candidates:
        return None
    return np.nanmedian(np.stack(candidates, axis=0), axis=0)


def build_replay_series(
    grouped_files: dict[date, dict[str, Path]], start_date: date, end_date: date
) -> list[dict[str, Any]]:
    series = []
    mod13_dates = sorted(
        d
        for d, layers in grouped_files.items()
        if "_500m_16_days_EVI" in layers and start_date <= d <= end_date
    )
    for step_date in mod13_dates:
        files = grouped_files[step_date]
        if "_500m_16_days_EVI" not in files or "_500m_16_days_pixel_reliability" not in files:
            continue
        evi, evi_profile = read_raster(files["_500m_16_days_EVI"])
        reliability, _ = read_raster(files["_500m_16_days_pixel_reliability"])
        lst_window, lst_profile = median_lst_window(grouped_files, step_date)
        if lst_window is None or lst_profile is None:
            series.append({"date": step_date, "clouded": True, "valid_fraction": 0.0})
            continue

        evi_valid = np.isin(np.nan_to_num(reliability, nan=-1).astype("int16"), [0, 1]) & np.isfinite(evi)
        evi_masked = np.where(evi_valid, evi, np.nan)
        evi_1km = reproject_average(evi_masked, evi_profile, lst_profile)
        evi_valid_fraction = reproject_average(evi_valid.astype("float32"), evi_profile, lst_profile)
        ndwi_window = median_ndwi_window(grouped_files, step_date, lst_profile)

        overlap_valid = np.isfinite(evi_1km) & np.isfinite(lst_window)
        valid_fraction = float(np.nanmean(np.where(np.isfinite(evi_valid_fraction), evi_valid_fraction, 0.0)))
        clouded = valid_fraction < MIN_VALID_FRACTION or not overlap_valid.any()

        series.append(
            {
                "date": step_date,
                "clouded": clouded,
                "valid_fraction": valid_fraction,
                "evi": evi_1km,
                "lst": lst_window,
                "ndwi": ndwi_window,
            }
        )
    return series


def replay_series(
    series: list[dict[str, Any]], policy: MASFEPolicy
) -> tuple[list[ReplayStep], dict[str, Any], np.ndarray | None, list[np.ndarray]]:
    cfg = Config()
    history_evi: list[np.ndarray] = []
    history_lst: list[np.ndarray] = []
    history_ndwi: list[np.ndarray] = []
    csc = None
    alpha = None
    beta = None
    steps_since_fuse = 0
    steps: list[ReplayStep] = []
    csc_snapshots: list[np.ndarray] = []
    peak_alert_map = None
    peak_csc = -1.0
    default_shape = next(
        (entry["evi"].shape for entry in series if not entry.get("clouded") and "evi" in entry),
        (10, 10),
    )

    for entry in series:
        step_date = entry["date"]
        if entry.get("clouded"):
            if csc is None:
                steps.append(
                    ReplayStep(
                        step_date,
                        "BASELINE",
                        0.0,
                        0.0,
                        0,
                        0.0,
                        0.0,
                        0.5,
                        0.5,
                        "cloud-obscured warmup",
                    )
                )
                csc_snapshots.append(np.zeros(default_shape, dtype="float32"))
                continue
            alpha_state = alpha.copy()
            beta_state = beta.copy()
            state = State(
                t=len(steps),
                soc=TARGET_SOC,
                downlink=True,
                op=0.30,
                alpha=alpha_state,
                beta=beta_state,
                evi_anom=np.zeros_like(csc),
                ndwi_anom=np.zeros_like(csc),
                csc=csc.copy(),
                steps_since_fuse=steps_since_fuse,
            )
            action = policy.act(state)
            new_csc = csc * 0.92
            steps_since_fuse += 1
            csc = new_csc
            steps.append(
                ReplayStep(
                    step_date,
                    action,
                    0.0,
                    float(np.nanmax(csc)),
                    0,
                    action_gsd_m(action),
                    action_tile_density_mb_per_km2(action),
                    float(np.nanmax(posterior_mean(alpha_state, beta_state))),
                    float(np.nanmax(posterior_tail_probability(alpha_state, beta_state))),
                    "cloud-obscured",
                )
            )
            csc_snapshots.append(csc.copy())
            continue

        evi = entry["evi"]
        lst = entry["lst"]
        ndwi = entry.get("ndwi")

        if len(history_evi) < WARMUP_VALID_STEPS:
            history_evi.append(evi)
            history_lst.append(lst)
            history_ndwi.append(ndwi if ndwi is not None else np.full(evi.shape, np.nan, dtype="float32"))
            if csc is None:
                csc = np.full(evi.shape, 0.18, dtype="float32")
                alpha = np.ones(evi.shape, dtype="float32")
                beta = np.ones(evi.shape, dtype="float32")
            steps.append(
                ReplayStep(
                    step_date,
                    "BASELINE",
                    entry["valid_fraction"],
                    float(np.nanmax(csc)),
                    0,
                    0.0,
                    0.0,
                    float(np.nanmax(posterior_mean(alpha, beta))),
                    float(np.nanmax(posterior_tail_probability(alpha, beta))),
                    "baseline warmup",
                )
            )
            csc_snapshots.append(csc.copy())
            continue

        evi_base = np.nanmedian(np.stack(history_evi[-WARMUP_VALID_STEPS :], axis=0), axis=0)
        lst_base = np.nanmedian(np.stack(history_lst[-WARMUP_VALID_STEPS :], axis=0), axis=0)
        ndwi_history_window = np.stack(history_ndwi[-WARMUP_VALID_STEPS :], axis=0)
        if np.isfinite(ndwi_history_window).any():
            ndwi_base = np.nanmedian(ndwi_history_window, axis=0)
        else:
            ndwi_base = None
        evi_anom = np.maximum(0.0, (evi_base - evi) / 0.042)
        evi_anom = np.nan_to_num(evi_anom, nan=0.0)
        if ndwi is not None and ndwi_base is not None:
            ndwi_anom = np.maximum(0.0, (ndwi_base - ndwi) / 0.05)
            ndwi_anom = np.nan_to_num(ndwi_anom, nan=0.0)
        else:
            ndwi_anom = np.zeros_like(evi_anom)

        if csc is None:
            csc = np.full(evi.shape, 0.18, dtype="float32")
        if alpha is None or beta is None:
            alpha = np.ones(evi.shape, dtype="float32")
            beta = np.ones(evi.shape, dtype="float32")

        alpha_state, beta_state = update_stress_belief(alpha, beta, evi_anom, ndwi_anom)

        state = State(
            t=len(steps),
            soc=TARGET_SOC,
            downlink=True,
            op=0.30,
            alpha=alpha_state.copy(),
            beta=beta_state.copy(),
            evi_anom=evi_anom,
            ndwi_anom=ndwi_anom,
            csc=csc.copy(),
            steps_since_fuse=steps_since_fuse,
        )
        action = policy.act(state)
        action_for_log = action

        if action in ("FUSE", "FUSE_PRIORITY"):
            if ndwi is not None and ndwi_base is not None and np.isfinite(ndwi).any():
                new_csc = compute_csc(
                    evi,
                    lst,
                    evi_base,
                    lst_base,
                    ndwi_t=ndwi,
                    ndwi_base=ndwi_base,
                )
                note = "real-scene replay with NDWI"
            else:
                new_csc = compute_csc(evi, lst, evi_base, lst_base)
                note = "real-scene replay (EVI/LST fallback)"
            steps_since_fuse = 0
        elif action == "MOD13":
            if ndwi is not None and ndwi_base is not None and np.isfinite(ndwi).any():
                stage1_csc = compute_csc(
                    evi,
                    lst_base,
                    evi_base,
                    lst_base,
                    ndwi_t=ndwi,
                    ndwi_base=ndwi_base,
                )
                note = "real-scene replay with NDWI"
            else:
                stage1_csc = compute_csc(evi, lst_base, evi_base, lst_base)
                note = "real-scene replay (EVI/LST fallback)"
            new_csc = csc * 0.70 + stage1_csc * 0.30
            steps_since_fuse += 1
        else:
            new_csc = csc * 0.97
            steps_since_fuse += 1
            note = "real-scene replay"

        priority_confirmed = False
        if action == "FUSE" and policy.should_priority_downlink(state, new_csc):
            priority_confirmed = True
            action_for_log = "FUSE_PRIORITY" if priority_confirmed else "FUSE"

        csc = new_csc
        alpha, beta = alpha_state, beta_state
        history_evi.append(evi)
        history_lst.append(lst)
        history_ndwi.append(ndwi if ndwi is not None else np.full(evi.shape, np.nan, dtype="float32"))
        if len(history_evi) > WARMUP_VALID_STEPS:
            history_evi = history_evi[-WARMUP_VALID_STEPS :]
            history_lst = history_lst[-WARMUP_VALID_STEPS :]
            history_ndwi = history_ndwi[-WARMUP_VALID_STEPS :]

        csc_max = float(np.nanmax(csc))
        alert_pixels = int(np.nansum(csc >= policy.csc_alert_thr)) if priority_confirmed else 0
        posterior_mean_max = float(np.nanmax(posterior_mean(alpha_state, beta_state)))
        posterior_tail_max = float(np.nanmax(posterior_tail_probability(alpha_state, beta_state)))
        steps.append(
            ReplayStep(
                step_date,
                action_for_log,
                entry["valid_fraction"],
                csc_max,
                alert_pixels,
                action_gsd_m(action_for_log),
                action_tile_density_mb_per_km2(action_for_log),
                posterior_mean_max,
                posterior_tail_max,
                note,
            )
        )
        csc_snapshots.append(csc.copy())

        if csc_max > peak_csc:
            peak_csc = csc_max
            peak_alert_map = csc.copy()

    action_steps = [step for step in steps if step.action != "BASELINE"]
    action_counts: dict[str, int] = {}
    for step in action_steps:
        action_counts[step.action] = action_counts.get(step.action, 0) + 1

    alert_steps = [step for step in action_steps if step.alert_pixels > 0]
    metrics = {
        "aoi": "westlands_ca",
        "valid_windows": sum(1 for step in action_steps if step.valid_fraction >= MIN_VALID_FRACTION),
        "cloud_obscured_windows": sum(1 for step in action_steps if step.valid_fraction < MIN_VALID_FRACTION),
        "baseline_windows": sum(1 for step in steps if step.action == "BASELINE"),
        "action_distribution": action_counts,
        "alert_windows": len(alert_steps),
        "first_alert_date": alert_steps[0].step_date.isoformat() if alert_steps else None,
        "peak_alert_date": max(alert_steps, key=lambda s: s.csc_max).step_date.isoformat() if alert_steps else None,
        "peak_csc": round(max((step.csc_max for step in action_steps), default=0.0), 3),
        "mean_valid_fraction": round(
            float(np.mean([step.valid_fraction for step in action_steps])) if action_steps else 0.0,
            3,
        ),
        "nominal_soc": TARGET_SOC,
        "notes": "Real-scene policy replay on official MODIS products; not a labeled disease benchmark.",
    }
    return steps, metrics, peak_alert_map, csc_snapshots


def save_timeline_csv(output_dir: Path, steps: list[ReplayStep]) -> None:
    lines = [
        "date,action,valid_fraction,csc_max,alert_pixels,gsd_m,tile_density_mb_per_km2,posterior_mean_max,posterior_tail_max,note"
    ]
    for step in steps:
        lines.append(
            f"{step.step_date.isoformat()},{step.action},{step.valid_fraction:.3f},"
            f"{step.csc_max:.3f},{step.alert_pixels},{step.gsd_m:.1f},"
            f"{step.tile_density_mb_per_km2:.2f},{step.posterior_mean_max:.3f},"
            f"{step.posterior_tail_max:.3f},{step.note}"
        )
    (output_dir / "action_timeline.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_metrics_json(output_dir: Path, metrics: dict[str, Any]) -> None:
    (output_dir / "replay_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n",
        encoding="utf-8",
    )


def save_csc_stack(output_dir: Path, steps: list[ReplayStep], csc_snapshots: list[np.ndarray]) -> None:
    np.savez_compressed(
        output_dir / "csc_stack.npz",
        dates=np.array([step.step_date.isoformat() for step in steps], dtype="U10"),
        actions=np.array([step.action for step in steps], dtype="U16"),
        csc=np.stack(csc_snapshots, axis=0),
    )


def save_plots(output_dir: Path, steps: list[ReplayStep], peak_alert_map: np.ndarray | None) -> None:
    import matplotlib.pyplot as plt
    import pandas as pd

    df = pd.DataFrame(
        {
            "date": pd.to_datetime([step.step_date.isoformat() for step in steps]),
            "action": [step.action for step in steps],
            "valid_fraction": [step.valid_fraction for step in steps],
            "csc_max": [step.csc_max for step in steps],
            "alert_pixels": [step.alert_pixels for step in steps],
            "posterior_mean_max": [step.posterior_mean_max for step in steps],
        }
    )
    action_colors = {
        "BASELINE": "#bdbdbd",
        "MOD13": "#1f77b4",
        "FUSE": "#ff7f0e",
        "FUSE_PRIORITY": "#d62728",
        "SKIP": "#7f7f7f",
    }

    fig, axes = plt.subplots(2, 1, figsize=(9, 6), constrained_layout=True)
    axes[0].plot(df["date"], df["csc_max"], color="#d62728", linewidth=2, label="CSC max")
    axes[0].plot(df["date"], df["valid_fraction"], color="#1f77b4", linewidth=2, label="Valid fraction")
    axes[0].plot(df["date"], df["posterior_mean_max"], color="#2ca02c", linewidth=1.8, label="Posterior mean max")
    axes[0].set_ylabel("Value")
    axes[0].set_title("MASFE replay on real MODIS scenes")
    axes[0].legend(loc="upper left")

    axes[1].bar(
        df["date"],
        np.ones(len(df)),
        color=[action_colors.get(action, "#7f7f7f") for action in df["action"]],
        width=10,
    )
    axes[1].set_yticks([])
    axes[1].set_ylabel("Action")
    axes[1].set_xlabel("Replay date")
    for idx, action in enumerate(df["action"]):
        axes[1].text(df["date"].iloc[idx], 0.5, action, rotation=90, ha="center", va="center", fontsize=7)
    fig.savefig(output_dir / "replay_summary.png", dpi=200)
    plt.close(fig)

    if peak_alert_map is None:
        peak_alert_map = np.zeros((10, 10), dtype="float32")
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(peak_alert_map, cmap="inferno", vmin=0.0, vmax=max(0.7, float(np.nanmax(peak_alert_map))))
    ax.set_title("Peak replay CSC map")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="CSC")
    fig.savefig(output_dir / "peak_alert_map.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def run_window(args: argparse.Namespace, start: date, end: date):
    cache_dir = Path(args.cache_dir)
    client = AppEEARSClient(args.earthdata_username, args.earthdata_password)
    bundle_dir = download_or_reuse_bundle(
        client=client,
        aoi=args.aoi,
        start=start,
        end=end,
        cache_dir=cache_dir,
        bundle_dir_override=args.bundle_dir,
        bundle_zip=args.bundle_zip,
        poll_seconds=args.poll_seconds,
        max_poll_minutes=args.max_poll_minutes,
        force_download=args.force_download,
    )
    grouped = group_bundle_files(bundle_dir)
    series = build_replay_series(grouped, start, end)
    steps, metrics, peak_alert_map, csc_snapshots = replay_series(series, MASFEPolicy())

    output_dir = Path("outputs/real_modis") / f"{args.aoi}_{start.isoformat()}_{end.isoformat()}"
    output_dir.mkdir(parents=True, exist_ok=True)
    save_timeline_csv(output_dir, steps)
    save_metrics_json(output_dir, metrics)
    save_csc_stack(output_dir, steps, csc_snapshots)
    save_plots(output_dir, steps, peak_alert_map)
    return output_dir, metrics


def main() -> None:
    require_deps()
    args = parse_args()
    start = parse_iso_date(args.start)
    end = parse_iso_date(args.end)

    output_dir, metrics = run_window(args, start, end)
    needs_fallback = metrics["valid_windows"] < 6 or metrics["alert_windows"] == 0
    if needs_fallback and not args.disable_fallback:
        fallback_end = date(2024, 10, 31)
        if fallback_end > end:
            reason = []
            if metrics["valid_windows"] < 6:
                reason.append(f"{metrics['valid_windows']} valid windows")
            if metrics["alert_windows"] == 0:
                reason.append("no alert windows")

            fallback_cache = cache_root(Path(args.cache_dir), args.aoi, start, fallback_end)
            has_cached_fallback = bool(find_tifs(fallback_cache))
            has_credentials = bool(args.earthdata_username and args.earthdata_password)
            can_request_fallback = not args.bundle_dir and not args.bundle_zip

            if has_cached_fallback or (can_request_fallback and has_credentials):
                log(
                    "Extending replay window to 2024-10-31 "
                    f"because the primary season produced {', '.join(reason)}"
                )
                output_dir, metrics = run_window(args, start, fallback_end)
            else:
                log(
                    "Skipping October fallback; primary-season outputs were written, "
                    "but no credentials or cached extended-window bundle are available."
                )

    print(json.dumps({"output_dir": str(output_dir), **metrics}, indent=2))


if __name__ == "__main__":
    main()
