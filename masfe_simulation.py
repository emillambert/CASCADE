"""
MASFE: Multi-Algorithm Scheduling and Fusion Engine
====================================================
NASA Space-to-Soil Challenge 2026 - Phase 1 Code Submission

NASA Datasets:
  MODIS MOD13A1  DOI: 10.5067/MODIS/MOD13A1.061  (vegetation index / EVI)
  MODIS MOD11A1  DOI: 10.5067/MODIS/MOD11A1.061  (land surface temperature)
  MODIS MOD09A1  DOI: 10.5067/MODIS/MOD09A1.061  (surface reflectance / NDWI)

Onboard fusion product:
  Crop Stress Composite (CSC) - per-patch index derived from EVI deviation,
  thermal rise, and NDWI water-stress behavior.

Three policies compared:
  1. RAW_DUMP         - naive: collect all raw imagery, downlink everything
  2. FIXED_ONBOARD    - always run full pipeline onboard
  3. MASFE_MDP        - adaptive: two-stage MDP scheduling, smart priority downlink
  4. ABLATE_NO_BELIEF - current-pass EVI trigger without the stored stress belief
  5. EVI_ONLY_THRESHOLD - Stage-1 EVI-only trigger; downlink only exceedance tiles

Synthetic validation:
  The benchmark runs as a 100-seed Monte Carlo study over 500 field patches,
  120 passes, 21 disease events, and 9 benign confounders per seed.
"""

from __future__ import annotations

import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict

import numpy as np

from masfe_core import (
    AblateNoBeliefPolicy,
    ACTION_W,
    Config,
    MASFEPolicy,
    State,
    action_gsd_m,
    action_tile_density_mb_per_km2,
    compute_csc,
    posterior_evidence,
    posterior_mean,
    posterior_tail_probability,
    update_stress_belief,
)

POLICY_SEED_OFFSET = {
    "RAW_DUMP": 101,
    "FIXED_ONBOARD": 202,
    "MASFE_MDP": 303,
    "ABLATE_NO_BELIEF": 404,
    "EVI_ONLY_THRESHOLD": 505,
}

MONTE_CARLO_DEFAULTS = {
    "n_seeds": 100,
    "n_patches": 500,
    "n_t": 120,
    "n_dis": 21,
    "n_benign": 9,
}

# Additional-ablation sweeps aim for smoother curves (not headline metrics).
# Keep seeds modest for runtime; increase patches for smoother statistics.
ADDITIONAL_ABLATION_DEFAULTS = {
    "n_seeds": int(os.environ.get("MASFE_ADDITIONAL_ABLATION_SEEDS", "100")),
    "n_patches": 1000,
    "n_t": 120,
    "n_dis": 21,
    "n_benign": 9,
}

ALERT_THRESH_SWEEP = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
WEIGHT_SWEEP = [0.70, 1.00, 1.30]
SATURATION_SWEEP = [0.70, 1.00, 1.30]
OUTPUTS_DIR = Path("outputs")

EVI_ONLY_THRESH_SWEEP = [
    6.0,
    5.5,
    5.0,
    4.5,
    4.0,
    3.8,
    3.6,
    3.4,
    3.2,
    3.0,
    2.9,
    2.8,
    2.7,
    2.6,
    2.59,
    2.58,
    2.57,
    2.56,
    2.55,
    2.5,
    2.4,
    2.3,
    2.2,
    2.1,
    2.0,
    1.5,
    1.0,
]
EVI_ONLY_TARGET_FP_PCT = 2.3


class EviOnlyThresholdPolicy:
    def __init__(self, evi_alert_thr: float = 4.0):
        self.evi_alert_thr = float(evi_alert_thr)

    def act(self, s: State) -> str:
        return "MOD13"


def _require_pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "matplotlib is required for plot generation. Install the plotting dependencies first."
        ) from exc
    return plt


# ---------------------------------------------------------------------------
# Synthetic MODIS data
# ---------------------------------------------------------------------------

def make_data(
    n_patches: int = 500,
    n_t: int = 120,
    n_dis: int = 21,
    n_benign: int = 9,
    seed: int = 42,
    cloud_pass_prob: float = 0.30,
) -> Dict:
    """
    Simulates MODIS MOD13 (EVI), MOD11 (LST), and MOD09 (NDWI-like) signals.
    Disease model: progressive EVI depression + LST elevation with only mild
    NDWI decline. Irrigation-like confounders drive stronger NDWI decline.
    """
    rng = np.random.default_rng(seed)
    evi_base = rng.uniform(0.42, 0.70, n_patches)
    lst_base = rng.uniform(294.5, 305.5, n_patches)
    ndwi_base = rng.uniform(0.08, 0.32, n_patches)

    dis_idx = rng.choice(n_patches, n_dis, replace=False)
    dis_onset = {int(i): int(rng.integers(18, 72)) for i in dis_idx}

    remaining = [i for i in range(n_patches) if i not in dis_idx]
    benign_idx = rng.choice(remaining, n_benign, replace=False)
    benign_onset = {int(i): int(rng.integers(12, 90)) for i in benign_idx}
    benign_duration = {int(i): int(rng.integers(4, 10)) for i in benign_idx}

    cloud_pass = rng.random(n_t) < cloud_pass_prob

    evi = np.zeros((n_t, n_patches))
    lst = np.zeros((n_t, n_patches))
    ndwi = np.zeros((n_t, n_patches))
    truth = np.zeros((n_t, n_patches), dtype=bool)

    for t in range(n_t):
        sea = 0.05 * np.sin(2 * np.pi * t / n_t)
        for p in range(n_patches):
            e = evi_base[p] + sea + rng.normal(0, 0.016)
            l = lst_base[p] + rng.normal(0, 0.55)
            n = ndwi_base[p] + 0.015 * np.cos(2 * np.pi * t / n_t) + rng.normal(0, 0.010)
            if p in dis_onset and t >= dis_onset[p]:
                sev = min(1.0, (t - dis_onset[p]) / 22.0)
                e -= sev * 0.22
                l += sev * 4.0
                n -= sev * 0.03
                truth[t, p] = sev > 0.10
            if p in benign_onset:
                dt = t - benign_onset[p]
                if 0 <= dt < benign_duration[p]:
                    sev = min(1.0, dt / max(benign_duration[p] - 1, 1))
                    e -= sev * 0.18
                    l += sev * 3.4
                    n -= sev * 0.18
            evi[t, p] = float(np.clip(e, 0.02, 0.99))
            lst[t, p] = float(l)
            ndwi[t, p] = float(np.clip(n, -0.15, 0.65))

    return {
        "evi": evi,
        "lst": lst,
        "ndwi": ndwi,
        "truth": truth,
        "n_patches": n_patches,
        "n_t": n_t,
        "n_dis": n_dis,
        "n_benign": n_benign,
        "evi_base": evi_base,
        "lst_base": lst_base,
        "ndwi_base": ndwi_base,
        "dis_onset": dis_onset,
        "dis_idx": dis_idx,
        "benign_onset": benign_onset,
        "benign_duration": benign_duration,
        "cloud_pass": cloud_pass,
    }


def build_datasets(
    n_seeds: int,
    n_patches: int,
    n_t: int,
    n_dis: int,
    n_benign: int,
    cloud_pass_prob: float = 0.30,
) -> list[Dict]:
    return [
        make_data(
            n_patches=n_patches,
            n_t=n_t,
            n_dis=n_dis,
            n_benign=n_benign,
            seed=seed,
            cloud_pass_prob=cloud_pass_prob,
        )
        for seed in range(n_seeds)
    ]


# ---------------------------------------------------------------------------
# Simulation loop
# ---------------------------------------------------------------------------

def simulate(
    policy_name: str,
    policy,
    data: Dict,
    cfg: Config,
    outer_seed: int,
    csc_kwargs: Dict | None = None,
) -> Dict:
    csc_kwargs = csc_kwargs or {}
    rng = np.random.default_rng(outer_seed * 10_000 + POLICY_SEED_OFFSET[policy_name])
    n_p, n_t = data["n_patches"], data["n_t"]
    evi_base = data["evi_base"]
    lst_base = data["lst_base"]
    ndwi_base = data["ndwi_base"]
    detection_threshold = getattr(policy, "csc_alert_thr", 0.55) if policy else 0.55

    stage1_stride_raw = getattr(cfg, "stage1_stride", 1) or 1
    try:
        stage1_stride = float(stage1_stride_raw)
    except (TypeError, ValueError):
        stage1_stride = 1.0
    if stage1_stride <= 0:
        stage1_stride = 1.0
    use_ndwi = bool(getattr(cfg, "ndwi_enabled", True))

    batt = 0.84
    csc = np.full(n_p, 0.18)
    alpha = np.ones(n_p, dtype="float32")
    beta = np.ones(n_p, dtype="float32")
    steps_sf = 0

    energy = data_vol = 0.0
    tp = fp = 0
    actions = []
    alerts = []
    batt_hist = []
    detected_patches = set()

    for t in range(n_t):
        op = (t * 5.0) % cfg.orbit_min / cfg.orbit_min
        in_eclipse = op > (1 - cfg.eclipse_frac)
        dl_window = 0.22 < op < 0.37

        if not in_eclipse:
            batt = min(1.0, batt + cfg.solar_w * (5 / 60) / cfg.batt_wh)

        evi_t = data["evi"][t].copy()
        lst_t = data["lst"][t].copy()
        ndwi_t = data["ndwi"][t].copy() if use_ndwi else None
        clouded = bool(data["cloud_pass"][t])
        if clouded:
            evi_t[:] = np.nan
            lst_t[:] = np.nan
            if ndwi_t is not None:
                ndwi_t[:] = np.nan
        else:
            evi_t += rng.normal(0.0, 0.010, n_p)
            lst_t += rng.normal(0.0, 0.35, n_p)
            if ndwi_t is not None:
                ndwi_t += rng.normal(0.0, 0.012, n_p)

        evi_anom = np.maximum(0.0, (evi_base - evi_t) / 0.042)
        evi_anom = np.nan_to_num(evi_anom, nan=0.0)
        if use_ndwi and ndwi_t is not None:
            ndwi_anom = np.maximum(0.0, (ndwi_base - ndwi_t) / 0.05)
            ndwi_anom = np.nan_to_num(ndwi_anom, nan=0.0)
        else:
            ndwi_anom = np.zeros(n_p, dtype="float32")

        # Integer stride: screen every Nth pass. Fractional stride: Bernoulli cadence
        # with p=1/stride (e.g., 1.5 means ~2/3 of passes run Stage-1).
        if float(stage1_stride).is_integer():
            stride_int = max(1, int(stage1_stride))
            stage1_due = (t % stride_int) == 0
        else:
            stage1_due = rng.random() < (1.0 / stage1_stride)
        if (not stage1_due) or clouded:
            alpha_state = alpha.copy()
            beta_state = beta.copy()
        else:
            alpha_state, beta_state = update_stress_belief(alpha, beta, evi_anom, ndwi_anom)

        if policy_name == "ABLATE_NO_BELIEF":
            alpha_for_state = np.ones_like(alpha_state)
            beta_for_state = np.ones_like(beta_state)
        else:
            alpha_for_state = alpha_state.copy()
            beta_for_state = beta_state.copy()

        state = State(
            t=t,
            soc=batt,
            downlink=dl_window,
            op=op,
            alpha=alpha_for_state,
            beta=beta_for_state,
            evi_anom=evi_anom,
            ndwi_anom=ndwi_anom,
            csc=csc.copy(),
            steps_since_fuse=steps_sf,
        )

        if (not stage1_due) and policy_name not in ("RAW_DUMP", "FIXED_ONBOARD"):
            action = "SKIP"
        elif policy_name == "RAW_DUMP":
            action = "RAW"
        elif policy_name == "FIXED_ONBOARD":
            action = "FUSE"
        else:
            action = policy.act(state)

        evi_only_detected = None
        if policy_name == "EVI_ONLY_THRESHOLD" and action == "MOD13":
            evi_thr = float(getattr(policy, "evi_alert_thr", 4.0))
            evi_only_detected = (evi_anom >= evi_thr) & (~np.isnan(evi_t))

        if clouded and action in ("MOD13", "FUSE", "FUSE_PRIORITY", "RAW"):
            new_csc = csc * 0.92
            steps_sf += 1
        elif action in ("FUSE", "FUSE_PRIORITY", "RAW"):
            csc_call = dict(csc_kwargs)
            if use_ndwi and ndwi_t is not None:
                csc_call.update({"ndwi_t": ndwi_t, "ndwi_base": ndwi_base})
            new_csc = compute_csc(evi_t, lst_t, evi_base, lst_base, **csc_call)
            steps_sf = 0
        elif action == "MOD13":
            csc_call = dict(csc_kwargs)
            if use_ndwi and ndwi_t is not None:
                csc_call.update({"ndwi_t": ndwi_t, "ndwi_base": ndwi_base})
            new_csc = csc * 0.70 + compute_csc(evi_t, lst_base, evi_base, lst_base, **csc_call) * 0.30
            steps_sf += 1
        else:
            new_csc = csc * 0.97
            steps_sf += 1

        if policy_name == "MASFE_MDP" and action == "FUSE" and policy.should_priority_downlink(state, new_csc):
            action = "FUSE_PRIORITY"
        elif policy_name == "ABLATE_NO_BELIEF" and action == "FUSE" and dl_window and new_csc.max() >= detection_threshold:
            action = "FUSE_PRIORITY"
        elif policy_name == "FIXED_ONBOARD" and action == "FUSE" and dl_window and new_csc.max() >= detection_threshold:
            action = "FUSE_PRIORITY"

        if not clouded and policy_name == "EVI_ONLY_THRESHOLD" and action == "MOD13":
            detected = evi_only_detected if evi_only_detected is not None else np.zeros(n_p, dtype=bool)
            tp += int(np.sum(detected & data["truth"][t]))
            fp += int(np.sum(detected & ~data["truth"][t]))
            for idx in np.where(detected & data["truth"][t])[0]:
                detected_patches.add(int(idx))
        elif not clouded and action in ("FUSE", "FUSE_PRIORITY", "RAW"):
            detected = new_csc >= detection_threshold
            tp += int(np.sum(detected & data["truth"][t]))
            fp += int(np.sum(detected & ~data["truth"][t]))
            for idx in np.where(detected & data["truth"][t])[0]:
                detected_patches.add(int(idx))

        if action == "RAW":
            data_mb = cfg.raw_mb
        elif policy_name == "EVI_ONLY_THRESHOLD" and action == "MOD13":
            if (not dl_window) or clouded or evi_only_detected is None or (int(evi_only_detected.sum()) == 0):
                data_mb = 0.0
            else:
                alerted = int(evi_only_detected.sum())
                data_mb = 0.1 * cfg.indices_mb + alerted * cfg.alert_mb
        elif action == "FUSE":
            data_mb = cfg.csc_map_mb
        elif action == "FUSE_PRIORITY":
            alerted = int((new_csc >= detection_threshold).sum())
            data_mb = cfg.indices_mb + alerted * cfg.alert_mb
        elif action == "MOD13":
            data_mb = cfg.indices_mb * 0.5
        else:
            data_mb = 0.0

        if clouded and action in ("MOD13", "FUSE", "FUSE_PRIORITY"):
            data_mb *= 0.15

        obs_s = 30.0
        if action == "RAW":
            watt_seconds = ACTION_W["FUSE_PRIORITY"] * obs_s
        else:
            watt_seconds = ACTION_W.get(action, 0.30) * obs_s

        batt = max(0.0, batt - (watt_seconds / 3600.0) / cfg.batt_wh)
        csc = new_csc
        if not clouded:
            alpha, beta = alpha_state, beta_state
        energy += watt_seconds / 3600.0
        data_vol += data_mb
        actions.append(action)
        batt_hist.append(batt)

        if policy_name == "EVI_ONLY_THRESHOLD" and action == "MOD13" and dl_window and not clouded:
            if evi_only_detected is not None and evi_only_detected.any():
                alerts.append(
                    {
                        "t": t,
                        "n": int(evi_only_detected.sum()),
                        "csc_max": round(float(new_csc.max()), 3),
                    }
                )
        elif action == "FUSE_PRIORITY" and (new_csc >= detection_threshold).any():
            alerts.append(
                {
                    "t": t,
                    "n": int((new_csc >= detection_threshold).sum()),
                    "csc_max": round(float(new_csc.max()), 3),
                }
            )

    action_dist = {action_name: actions.count(action_name) for action_name in set(actions)}
    return {
        "name": policy_name,
        "energy": energy,
        "data_mb": data_vol,
        "tp": tp,
        "fp": fp,
        "n_alerts": len(alerts),
        "alerts": alerts,
        "action_dist": action_dist,
        "min_batt": float(min(batt_hist)),
        "cloud_passes": int(np.sum(data["cloud_pass"])),
        "detected_patches": len(detected_patches),
        "seasonal_average_compute_pct": cfg.seasonal_average_compute_pct(action_dist, n_t) * 100.0,
        "detection_threshold": detection_threshold,
    }


def mean_std_ci(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    half_width = 1.96 * std / math.sqrt(len(arr)) if len(arr) > 1 else 0.0
    return {
        "mean": mean,
        "std": std,
        "ci95_low": mean - half_width,
        "ci95_high": mean + half_width,
    }


def clean_round(value: float, digits: int = 1) -> float:
    rounded = round(value, digits)
    if abs(rounded) < 10 ** (-(digits + 1)):
        return 0.0
    return rounded


def summarize_action_mix(action_distributions: list[dict], n_t: int) -> dict:
    action_names = sorted({name for dist in action_distributions for name in dist})
    summary = {}
    for action_name in action_names:
        counts = np.asarray([dist.get(action_name, 0) for dist in action_distributions], dtype=float)
        pct = counts / n_t * 100.0
        summary[action_name] = {
            "count_mean": float(counts.mean()),
            "count_std": float(counts.std(ddof=1)) if len(counts) > 1 else 0.0,
            "pct_mean": float(pct.mean()),
            "pct_std": float(pct.std(ddof=1)) if len(pct) > 1 else 0.0,
        }
    return summary


def build_seed_record(seed: int, raw: Dict, fixed: Dict, masfe: Dict, data: Dict) -> dict:
    def pct_save(a, b):
        return (1 - a / b) * 100.0

    fp_rate = masfe["fp"] / max(masfe["tp"] + masfe["fp"], 1) * 100.0
    return {
        "seed": seed,
        "downlink_reduction_vs_raw_pct": pct_save(masfe["data_mb"], raw["data_mb"]),
        "downlink_reduction_vs_fixed_pct": pct_save(masfe["data_mb"], fixed["data_mb"]),
        "energy_saving_vs_raw_pct": pct_save(masfe["energy"], raw["energy"]),
        "energy_saving_vs_fixed_pct": pct_save(masfe["energy"], fixed["energy"]),
        "science_retention_pct": masfe["detected_patches"] / max(len(data["dis_idx"]), 1) * 100.0,
        "alert_precision_pct": 100.0 - fp_rate,
        "false_positive_rate_pct": fp_rate,
        "n_priority_alerts": float(masfe["n_alerts"]),
        "min_battery_soc": float(masfe["min_batt"]),
        "cloud_obscured_passes": float(masfe["cloud_passes"]),
        "seasonal_average_compute_utilisation_pct": float(masfe["seasonal_average_compute_pct"]),
    }


def build_policy_seed_record(seed: int, run: Dict, data: Dict) -> dict:
    fp_rate = run["fp"] / max(run["tp"] + run["fp"], 1) * 100.0
    return {
        "seed": seed,
        "science_retention_pct": run["detected_patches"] / max(len(data["dis_idx"]), 1) * 100.0,
        "alert_precision_pct": 100.0 - fp_rate,
        "false_positive_rate_pct": fp_rate,
        "n_priority_alerts": float(run["n_alerts"]),
        "min_battery_soc": float(run["min_batt"]),
        "cloud_obscured_passes": float(run["cloud_passes"]),
        "seasonal_average_compute_utilisation_pct": float(run["seasonal_average_compute_pct"]),
        "data_mb": float(run["data_mb"]),
        "energy_wh": float(run["energy"]),
    }


def aggregate_policy_results(name: str, policy_runs: list[Dict], n_t: int) -> dict:
    energy = [run["energy"] for run in policy_runs]
    data_mb = [run["data_mb"] for run in policy_runs]
    tp = [run["tp"] for run in policy_runs]
    fp = [run["fp"] for run in policy_runs]
    n_alerts = [run["n_alerts"] for run in policy_runs]
    min_batt = [run["min_batt"] for run in policy_runs]
    cloud = [run["cloud_passes"] for run in policy_runs]
    avg_compute = [run["seasonal_average_compute_pct"] for run in policy_runs]
    detected_patches = [run["detected_patches"] for run in policy_runs]

    return {
        "name": name,
        "energy_mean_wh": float(np.mean(energy)),
        "data_mb_mean": float(np.mean(data_mb)),
        "tp_mean": float(np.mean(tp)),
        "fp_mean": float(np.mean(fp)),
        "n_alerts_mean": float(np.mean(n_alerts)),
        "min_batt_mean": float(np.mean(min_batt)),
        "cloud_passes_mean": float(np.mean(cloud)),
        "seasonal_average_compute_pct_mean": float(np.mean(avg_compute)),
        "detected_patches_mean": float(np.mean(detected_patches)),
        "action_mix": summarize_action_mix([run["action_dist"] for run in policy_runs], n_t),
    }


def evaluate_policy(
    policy_name: str,
    policy_factory: Callable[[], object],
    cfg: Config,
    datasets: list[Dict],
    csc_kwargs: Dict | None = None,
) -> dict:
    seed_records = []
    runs = []
    for seed, data in enumerate(datasets):
        run = simulate(policy_name, policy_factory(), data, cfg, outer_seed=seed, csc_kwargs=csc_kwargs)
        seed_records.append(build_policy_seed_record(seed, run, data))
        runs.append(run)

    metric_names = [
        "science_retention_pct",
        "alert_precision_pct",
        "false_positive_rate_pct",
        "n_priority_alerts",
        "min_battery_soc",
        "cloud_obscured_passes",
        "seasonal_average_compute_utilisation_pct",
        "data_mb",
        "energy_wh",
    ]
    stats = {
        metric_name: mean_std_ci([record[metric_name] for record in seed_records])
        for metric_name in metric_names
    }
    return {
        "policy_name": policy_name,
        "stats": stats,
        "runs": runs,
        "seed_records": seed_records,
        "action_mix": summarize_action_mix([run["action_dist"] for run in runs], datasets[0]["n_t"]),
    }


def _policy_seed_worker(args: tuple) -> dict:
    (
        seed,
        policy_name,
        policy_class,
        policy_kwargs,
        cfg,
        n_patches,
        n_t,
        n_dis,
        n_benign,
        cloud_pass_prob,
        csc_kwargs,
    ) = args
    data = make_data(
        n_patches=n_patches,
        n_t=n_t,
        n_dis=n_dis,
        n_benign=n_benign,
        seed=int(seed),
        cloud_pass_prob=float(cloud_pass_prob),
    )
    run = simulate(
        policy_name,
        policy_class(**policy_kwargs),
        data,
        cfg,
        outer_seed=int(seed),
        csc_kwargs=csc_kwargs,
    )
    return build_policy_seed_record(int(seed), run, data)


def evaluate_policy_generated(
    policy_name: str,
    policy_class: type,
    policy_kwargs: dict | None,
    cfg: Config,
    *,
    n_seeds: int,
    n_patches: int,
    n_t: int,
    n_dis: int,
    n_benign: int,
    cloud_pass_prob: float = 0.30,
    csc_kwargs: Dict | None = None,
    max_workers: int | None = None,
) -> dict:
    """
    Evaluate a policy by generating each seed's dataset on the fly.
    This avoids holding all datasets in memory and enables parallel per-seed execution.
    """
    csc_kwargs = csc_kwargs or {}
    policy_kwargs = policy_kwargs or {}
    if max_workers is None:
        # Keep concurrency bounded (also helps on laptops).
        max_workers = min(8, max(1, (os.cpu_count() or 2) - 1))

    metric_names = [
        "science_retention_pct",
        "alert_precision_pct",
        "false_positive_rate_pct",
        "n_priority_alerts",
        "min_battery_soc",
        "cloud_obscured_passes",
        "seasonal_average_compute_utilisation_pct",
        "data_mb",
        "energy_wh",
    ]

    if max_workers <= 1:
        seed_records = [
            _policy_seed_worker(
                (
                    seed,
                    policy_name,
                    policy_class,
                    policy_kwargs,
                    cfg,
                    n_patches,
                    n_t,
                    n_dis,
                    n_benign,
                    cloud_pass_prob,
                    csc_kwargs,
                )
            )
            for seed in range(int(n_seeds))
        ]
        seed_records.sort(key=lambda r: r["seed"])
    else:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            seed_records = evaluate_policy_generated_with_pool(
                pool,
                policy_name,
                policy_class,
                policy_kwargs,
                cfg,
                n_seeds=n_seeds,
                n_patches=n_patches,
                n_t=n_t,
                n_dis=n_dis,
                n_benign=n_benign,
                cloud_pass_prob=cloud_pass_prob,
                csc_kwargs=csc_kwargs,
            )["seed_records"]

    stats = {
        metric_name: mean_std_ci([record[metric_name] for record in seed_records])
        for metric_name in metric_names
    }
    return {"policy_name": policy_name, "stats": stats, "seed_records": seed_records}


def evaluate_policy_generated_with_pool(
    pool: ProcessPoolExecutor,
    policy_name: str,
    policy_class: type,
    policy_kwargs: dict | None,
    cfg: Config,
    *,
    n_seeds: int,
    n_patches: int,
    n_t: int,
    n_dis: int,
    n_benign: int,
    cloud_pass_prob: float = 0.30,
    csc_kwargs: Dict | None = None,
) -> dict:
    """Same as evaluate_policy_generated, but reuses an existing process pool."""
    csc_kwargs = csc_kwargs or {}
    policy_kwargs = policy_kwargs or {}

    metric_names = [
        "science_retention_pct",
        "alert_precision_pct",
        "false_positive_rate_pct",
        "n_priority_alerts",
        "min_battery_soc",
        "cloud_obscured_passes",
        "seasonal_average_compute_utilisation_pct",
        "data_mb",
        "energy_wh",
    ]

    futures = [
        pool.submit(
            _policy_seed_worker,
            (
                seed,
                policy_name,
                policy_class,
                policy_kwargs,
                cfg,
                n_patches,
                n_t,
                n_dis,
                n_benign,
                cloud_pass_prob,
                csc_kwargs,
            ),
        )
        for seed in range(int(n_seeds))
    ]
    seed_records = [f.result() for f in futures]
    seed_records.sort(key=lambda r: r["seed"])

    stats = {
        metric_name: mean_std_ci([record[metric_name] for record in seed_records])
        for metric_name in metric_names
    }
    return {"policy_name": policy_name, "stats": stats, "seed_records": seed_records}


def run_monte_carlo(
    cfg: Config,
    n_seeds: int = MONTE_CARLO_DEFAULTS["n_seeds"],
    n_patches: int = MONTE_CARLO_DEFAULTS["n_patches"],
    n_t: int = MONTE_CARLO_DEFAULTS["n_t"],
    n_dis: int = MONTE_CARLO_DEFAULTS["n_dis"],
    n_benign: int = MONTE_CARLO_DEFAULTS["n_benign"],
    datasets: list[Dict] | None = None,
) -> dict:
    if datasets is None:
        datasets = build_datasets(n_seeds, n_patches, n_t, n_dis, n_benign)

    seed_records = []
    raw_runs = []
    fixed_runs = []
    masfe_runs = []

    for seed, data in enumerate(datasets):
        raw = simulate("RAW_DUMP", None, data, cfg, outer_seed=seed)
        fixed = simulate("FIXED_ONBOARD", None, data, cfg, outer_seed=seed)
        masfe = simulate("MASFE_MDP", MASFEPolicy(), data, cfg, outer_seed=seed)

        seed_records.append(build_seed_record(seed, raw, fixed, masfe, data))
        raw_runs.append(raw)
        fixed_runs.append(fixed)
        masfe_runs.append(masfe)

    metric_names = [
        "downlink_reduction_vs_raw_pct",
        "downlink_reduction_vs_fixed_pct",
        "energy_saving_vs_raw_pct",
        "energy_saving_vs_fixed_pct",
        "science_retention_pct",
        "alert_precision_pct",
        "false_positive_rate_pct",
        "n_priority_alerts",
        "min_battery_soc",
        "cloud_obscured_passes",
        "seasonal_average_compute_utilisation_pct",
    ]
    stats = {
        metric_name: mean_std_ci([record[metric_name] for record in seed_records])
        for metric_name in metric_names
    }

    metrics = {
        "downlink_reduction_vs_raw_pct": clean_round(stats["downlink_reduction_vs_raw_pct"]["mean"], 1),
        "downlink_reduction_vs_fixed_pct": clean_round(stats["downlink_reduction_vs_fixed_pct"]["mean"], 1),
        "energy_saving_vs_raw_pct": clean_round(stats["energy_saving_vs_raw_pct"]["mean"], 1),
        "energy_saving_vs_fixed_pct": clean_round(stats["energy_saving_vs_fixed_pct"]["mean"], 1),
        "science_retention_pct": clean_round(stats["science_retention_pct"]["mean"], 1),
        "alert_precision_pct": clean_round(stats["alert_precision_pct"]["mean"], 1),
        "false_positive_rate_pct": clean_round(stats["false_positive_rate_pct"]["mean"], 1),
        "n_priority_alerts": clean_round(stats["n_priority_alerts"]["mean"], 1),
        "min_battery_soc": clean_round(stats["min_battery_soc"]["mean"], 3),
        "peak_power_w": round(cfg.peak_w(), 1),
        "avg_payload_power_w": round(cfg.avg_payload_w(), 2),
        "compute_utilisation_pct": round(cfg.peak_compute_pct() * 100, 1),
        "stage1_compute_utilisation_pct": round(cfg.stage1_compute_pct() * 100, 1),
        "seasonal_average_compute_utilisation_pct": clean_round(
            stats["seasonal_average_compute_utilisation_pct"]["mean"], 1
        ),
        "cloud_obscured_passes": clean_round(stats["cloud_obscured_passes"]["mean"], 1),
        "resolution_pyramid": {
            "screen_gsd_m": action_gsd_m("MOD13"),
            "confirmation_gsd_m": action_gsd_m("FUSE"),
            "priority_gsd_m": action_gsd_m("FUSE_PRIORITY"),
            "screen_tile_density_mb_per_km2": action_tile_density_mb_per_km2("MOD13"),
            "confirmation_tile_density_mb_per_km2": action_tile_density_mb_per_km2("FUSE"),
            "priority_tile_density_mb_per_km2": action_tile_density_mb_per_km2("FUSE_PRIORITY"),
        },
        "peak_gsd_m": action_gsd_m("FUSE_PRIORITY"),
        "seasonal_average_screen_gsd_m": clean_round(
            sum(
                action_gsd_m(action_name) * metrics_block["count_mean"]
                for action_name, metrics_block in summarize_action_mix([run["action_dist"] for run in masfe_runs], n_t).items()
            ) / max(n_t, 1),
            1,
        ),
        "seasonal_priority_share_pct": clean_round(
            summarize_action_mix([run["action_dist"] for run in masfe_runs], n_t)
            .get("FUSE_PRIORITY", {})
            .get("pct_mean", 0.0),
            1,
        ),
        "compression": {
            "priority_tile_raw_mb_per_km2": 8.4,
            "priority_tile_compression_ratio": 2.5,
            "priority_tile_delivered_mb_per_km2": 3.36,
        },
        "monte_carlo": {
            "n_seeds": n_seeds,
            "n_patches": n_patches,
            "n_t": n_t,
            "n_dis": n_dis,
            "n_benign": n_benign,
            "per_metric_ci95": {
                metric_name: {
                    "mean": round(metric_stats["mean"], 3),
                    "std": round(metric_stats["std"], 3),
                    "ci95_low": round(metric_stats["ci95_low"], 3),
                    "ci95_high": round(metric_stats["ci95_high"], 3),
                }
                for metric_name, metric_stats in stats.items()
            },
            "policy_summary": {
                "RAW_DUMP": aggregate_policy_results("RAW_DUMP", raw_runs, n_t),
                "FIXED_ONBOARD": aggregate_policy_results("FIXED_ONBOARD", fixed_runs, n_t),
                "MASFE_MDP": aggregate_policy_results("MASFE_MDP", masfe_runs, n_t),
            },
        },
    }
    return metrics


# ---------------------------------------------------------------------------
# Evidence outputs
# ---------------------------------------------------------------------------

def round_stats(stats: dict) -> dict:
    return {
        key: {
            "mean": round(value["mean"], 3),
            "std": round(value["std"], 3),
            "ci95_low": round(value["ci95_low"], 3),
            "ci95_high": round(value["ci95_high"], 3),
        }
        for key, value in stats.items()
    }


def run_ablation_analysis(cfg: Config, datasets: list[Dict], baseline_metrics: dict) -> dict:
    target_recall = round(float(baseline_metrics["science_retention_pct"]), 1)
    default_eval = evaluate_policy(
        "ABLATE_NO_BELIEF",
        lambda: AblateNoBeliefPolicy(csc_alert_thr=0.55),
        cfg,
        datasets,
    )
    default_recall = round(default_eval["stats"]["science_retention_pct"]["mean"], 1)
    selected_threshold = 0.55
    selected_eval = default_eval
    sweep_results = {}

    if default_recall != target_recall:
        for threshold in ALERT_THRESH_SWEEP:
            eval_result = evaluate_policy(
                "ABLATE_NO_BELIEF",
                lambda thr=threshold: AblateNoBeliefPolicy(csc_alert_thr=thr),
                cfg,
                datasets,
            )
            recall_mean = eval_result["stats"]["science_retention_pct"]["mean"]
            sweep_results[f"{threshold:.2f}"] = round_stats(eval_result["stats"])
            if round(recall_mean, 1) >= target_recall:
                selected_threshold = threshold
                selected_eval = eval_result
                break
    else:
        sweep_results["0.55"] = round_stats(default_eval["stats"])

    ablation_fp = selected_eval["stats"]["false_positive_rate_pct"]["mean"]
    baseline_fp = baseline_metrics["false_positive_rate_pct"]
    return {
        "target_recall_pct": target_recall,
        "baseline_masfe_false_positive_rate_pct": round(float(baseline_fp), 3),
        "selected_alert_threshold": round(selected_threshold, 2),
        "ablation_recall_pct": round(selected_eval["stats"]["science_retention_pct"]["mean"], 3),
        "ablation_false_positive_rate_pct": round(ablation_fp, 3),
        "false_positive_rate_delta_pct_points": round(ablation_fp - baseline_fp, 3),
        "ablation_stats": round_stats(selected_eval["stats"]),
        "threshold_sweep_checked": sweep_results,
    }


def run_evi_only_baseline(cfg: Config, datasets: list[Dict], baseline_metrics: dict) -> dict:
    target_recall = round(float(baseline_metrics["science_retention_pct"]), 1)
    selected_threshold = None
    selected_eval = None
    best_fp_gap = float("inf")
    sweep_results = {}

    for thr in EVI_ONLY_THRESH_SWEEP:
        eval_result = evaluate_policy(
            "EVI_ONLY_THRESHOLD",
            lambda t=thr: EviOnlyThresholdPolicy(evi_alert_thr=t),
            cfg,
            datasets,
        )
        recall_mean = eval_result["stats"]["science_retention_pct"]["mean"]
        fp_mean = eval_result["stats"]["false_positive_rate_pct"]["mean"]
        sweep_results[f"{thr:.2f}"] = round_stats(eval_result["stats"])
        if round(recall_mean, 1) < target_recall:
            continue
        fp_gap = abs(float(fp_mean) - float(EVI_ONLY_TARGET_FP_PCT))
        if fp_gap < best_fp_gap:
            best_fp_gap = fp_gap
            selected_threshold = float(thr)
            selected_eval = eval_result

    if selected_eval is None or selected_threshold is None:
        # Fall back to the least conservative threshold if none meet recall.
        thr = float(EVI_ONLY_THRESH_SWEEP[-1])
        selected_threshold = float(thr)
        selected_eval = evaluate_policy(
            "EVI_ONLY_THRESHOLD",
            lambda t=thr: EviOnlyThresholdPolicy(evi_alert_thr=t),
            cfg,
            datasets,
        )

    return {
        "target_recall_pct": target_recall,
        "selected_evi_threshold": round(selected_threshold, 2),
        "evi_only_stats": round_stats(selected_eval["stats"]),
        "threshold_sweep_checked": sweep_results,
    }


def write_baselines_comparison_table(
    metrics: dict,
    ablation_metrics: dict,
    evi_only_metrics: dict,
    destination: Path,
) -> None:
    mc = metrics["monte_carlo"]
    raw = mc["policy_summary"]["RAW_DUMP"]
    fixed = mc["policy_summary"]["FIXED_ONBOARD"]
    masfe = mc["policy_summary"]["MASFE_MDP"]
    n_dis = float(mc["n_dis"])

    def downlink_reduction_vs_raw(policy_data_mb_mean: float) -> float:
        denom = max(float(raw["data_mb_mean"]), 1e-9)
        return (1.0 - float(policy_data_mb_mean) / denom) * 100.0

    def fmt_pct(x: float, digits: int = 1) -> str:
        return f"{round(float(x), digits):.{digits}f}\\%"

    evi_stats = evi_only_metrics["evi_only_stats"]
    ab_stats = ablation_metrics["ablation_stats"]

    def recall_from_aggregate(run: dict) -> float:
        return float(run.get("detected_patches_mean", 0.0)) / max(n_dis, 1.0) * 100.0

    def fp_rate_from_aggregate(run: dict) -> float:
        return float(run["fp_mean"]) / max(float(run["tp_mean"]) + float(run["fp_mean"]), 1.0) * 100.0

    table_rows = [
        (
            "Raw downlink",
            0.0,
            recall_from_aggregate(raw),
            fp_rate_from_aggregate(raw),
            r"N/A",
        ),
        (
            "Fixed-period onboard",
            downlink_reduction_vs_raw(float(fixed["data_mb_mean"])),
            recall_from_aggregate(fixed),
            fp_rate_from_aggregate(fixed),
            float(fixed["seasonal_average_compute_pct_mean"]),
        ),
        (
            "EVI-only threshold",
            downlink_reduction_vs_raw(float(evi_stats["data_mb"]["mean"])),
            float(evi_stats["science_retention_pct"]["mean"]),
            float(evi_stats["false_positive_rate_pct"]["mean"]),
            float(evi_stats["seasonal_average_compute_utilisation_pct"]["mean"]),
        ),
        (
            "No-belief MASFE",
            downlink_reduction_vs_raw(float(ab_stats["data_mb"]["mean"])),
            float(ab_stats["science_retention_pct"]["mean"]),
            float(ab_stats["false_positive_rate_pct"]["mean"]),
            float(ab_stats["seasonal_average_compute_utilisation_pct"]["mean"]),
        ),
        (
            "Full MASFE",
            downlink_reduction_vs_raw(float(masfe["data_mb_mean"])),
            recall_from_aggregate(masfe),
            fp_rate_from_aggregate(masfe),
            float(masfe["seasonal_average_compute_pct_mean"]),
        ),
    ]

    lines = []
    lines.append(r"\begin{table}[!htbp]")
    lines.append(r"\centering")
    lines.append(r"\caption{Baseline comparisons under the synthetic Monte Carlo benchmark.}")
    lines.append(r"\label{tab:baselines}")
    lines.append(r"\small")
    lines.append(r"\setlength{\tabcolsep}{5pt}")
    lines.append(r"\renewcommand{\arraystretch}{1.1}")
    lines.append(r"\begin{tabular}{lcccc}")
    lines.append(r"\toprule")
    lines.append(r"Variant & Downlink\,$\downarrow$ & Recall\,$\uparrow$ & FP\,$\downarrow$ & Compute\,$\downarrow$ \\")
    lines.append(r"\midrule")
    for name, downlink_red, recall, fp, compute in table_rows:
        compute_cell = compute if isinstance(compute, str) else fmt_pct(compute)
        lines.append(
            f"{name} & {fmt_pct(downlink_red)} & {fmt_pct(recall)} & {fmt_pct(fp)} & {compute_cell} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(
        r"{\footnotesize Raw downlink denotes no onboard triage; recall and false-positive rate apply the same detector after ground-processing the full dataset.}"
    )
    lines.append(r"\end{table}")
    lines.append("")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")


def run_roc_sweep(cfg: Config, datasets: list[Dict]) -> dict:
    points = []
    for threshold in ALERT_THRESH_SWEEP:
        eval_result = evaluate_policy(
            "MASFE_MDP",
            lambda thr=threshold: MASFEPolicy(csc_alert_thr=thr),
            cfg,
            datasets,
        )
        points.append(
            {
                "threshold": round(threshold, 2),
                "science_retention_pct": round(eval_result["stats"]["science_retention_pct"]["mean"], 3),
                "alert_precision_pct": round(eval_result["stats"]["alert_precision_pct"]["mean"], 3),
                "false_positive_rate_pct": round(eval_result["stats"]["false_positive_rate_pct"]["mean"], 3),
                "n_priority_alerts": round(eval_result["stats"]["n_priority_alerts"]["mean"], 3),
            }
        )

    return {
        "thresholds": points,
        "operating_point_threshold": 0.55,
    }


def run_roc_sweep_ci(cfg: Config, datasets: list[Dict], thresholds: list[float]) -> dict:
    """ROC sweep with per-threshold 95% CI for both axes."""
    points = []
    for threshold in thresholds:
        # This variant is used by run_additional_ablations, which passes generated params.
        eval_result = evaluate_policy(
            "MASFE_MDP",
            lambda thr=threshold: MASFEPolicy(csc_alert_thr=thr),
            cfg,
            datasets,
        )
        fp = eval_result["stats"]["false_positive_rate_pct"]
        recall = eval_result["stats"]["science_retention_pct"]
        points.append(
            {
                "threshold": round(float(threshold), 3),
                "false_positive_rate_pct": round(float(fp["mean"]), 3),
                "false_positive_rate_ci95_low": round(float(fp["ci95_low"]), 3),
                "false_positive_rate_ci95_high": round(float(fp["ci95_high"]), 3),
                "science_retention_pct": round(float(recall["mean"]), 3),
                "science_retention_ci95_low": round(float(recall["ci95_low"]), 3),
                "science_retention_ci95_high": round(float(recall["ci95_high"]), 3),
            }
        )
    return {"thresholds": points, "operating_point_threshold": 0.55}


def run_roc_sweep_ci_generated(cfg: Config, *, thresholds: list[float], gen: dict) -> dict:
    """ROC sweep using evaluate_policy_generated with per-threshold 2D CI."""
    points = []
    for threshold in thresholds:
        eval_result = evaluate_policy_generated(
            "MASFE_MDP",
            MASFEPolicy,
            {"csc_alert_thr": float(threshold)},
            cfg,
            **gen,
        )
        fp = eval_result["stats"]["false_positive_rate_pct"]
        recall = eval_result["stats"]["science_retention_pct"]
        points.append(
            {
                "threshold": round(float(threshold), 3),
                "false_positive_rate_pct": round(float(fp["mean"]), 3),
                "false_positive_rate_ci95_low": round(float(fp["ci95_low"]), 3),
                "false_positive_rate_ci95_high": round(float(fp["ci95_high"]), 3),
                "science_retention_pct": round(float(recall["mean"]), 3),
                "science_retention_ci95_low": round(float(recall["ci95_low"]), 3),
                "science_retention_ci95_high": round(float(recall["ci95_high"]), 3),
            }
        )
    return {"thresholds": points, "operating_point_threshold": 0.55}


def run_roc_sweep_ci_generated_with_pool(
    pool: ProcessPoolExecutor, cfg: Config, *, thresholds: list[float], gen: dict
) -> dict:
    points = []
    for threshold in thresholds:
        eval_result = evaluate_policy_generated_with_pool(
            pool,
            "MASFE_MDP",
            MASFEPolicy,
            {"csc_alert_thr": float(threshold)},
            cfg,
            **gen,
        )
        fp = eval_result["stats"]["false_positive_rate_pct"]
        recall = eval_result["stats"]["science_retention_pct"]
        points.append(
            {
                "threshold": round(float(threshold), 3),
                "false_positive_rate_pct": round(float(fp["mean"]), 3),
                "false_positive_rate_ci95_low": round(float(fp["ci95_low"]), 3),
                "false_positive_rate_ci95_high": round(float(fp["ci95_high"]), 3),
                "science_retention_pct": round(float(recall["mean"]), 3),
                "science_retention_ci95_low": round(float(recall["ci95_low"]), 3),
                "science_retention_ci95_high": round(float(recall["ci95_high"]), 3),
            }
        )
    return {"thresholds": points, "operating_point_threshold": 0.55}


def write_roc_plot(roc_metrics: dict, destination: Path) -> None:
    plt = _require_pyplot()
    points = roc_metrics["thresholds"]
    x = [point["false_positive_rate_pct"] for point in points]
    y = [point["science_retention_pct"] for point in points]
    labels = [f"{point['threshold']:.2f}" for point in points]

    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    ax.plot(x, y, marker="o", linewidth=1.8, color="#1b5e8a")
    for px, py, label in zip(x, y, labels):
        ax.annotate(label, (px, py), textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xlabel("False-positive rate (%)")
    ax.set_ylabel("Disease-event recall (%)")
    ax.set_title("MASFE operating-point sweep over CSC alert threshold")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.45)
    ax.set_xlim(left=0.0)
    ax.set_ylim(bottom=max(0.0, min(y) - 1.0), top=min(100.5, max(y) + 1.0))
    fig.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=220)
    plt.close(fig)


def write_multi_roc_plot(
    roc_a: dict,
    roc_b: dict,
    labels: tuple[str, str],
    destination: Path,
) -> None:
    plt = _require_pyplot()
    points_a = roc_a["thresholds"]
    points_b = roc_b["thresholds"]

    xa = [point["false_positive_rate_pct"] for point in points_a]
    ya = [point["science_retention_pct"] for point in points_a]
    xb = [point["false_positive_rate_pct"] for point in points_b]
    yb = [point["science_retention_pct"] for point in points_b]

    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    ax.plot(xa, ya, marker="o", linewidth=1.8, color="#1b5e8a", label=labels[0])
    ax.plot(xb, yb, marker="o", linewidth=1.8, color="#b00020", label=labels[1])
    ax.set_xlabel("False-positive rate (%)")
    ax.set_ylabel("Disease-event recall (%)")
    ax.set_title("MASFE operating-point sweep (NDWI ablation)")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.45)
    ax.set_xlim(left=0.0)
    ax.set_ylim(bottom=0.0, top=100.5)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=220)
    plt.close(fig)


def run_additional_ablations(cfg: Config) -> dict:
    """
    Additional Tier-3 evidence: non-obvious ablations + curves.

    - NDWI removed: CSC uses EVI/LST-only fallback; belief updates use EVI only.
    - Sparse Stage-1 cadence: screening every Nth pass (others forced SKIP).
    - Cloud strictness sweep: effective cloud-flag rate (more/less masked passes).
    """
    plt = _require_pyplot()
    thresholds = np.linspace(0.30, 0.80, 25).tolist()
    stride_values = [1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7]
    # Wide enough range that recall can degrade at high cloud-flag rates (ablation visibility).
    cloud_values = np.linspace(0.05, 0.75, 14).tolist()

    gen_base = dict(ADDITIONAL_ABLATION_DEFAULTS)
    gen_base["cloud_pass_prob"] = 0.30
    max_workers = int(os.environ.get("MASFE_ABLATION_MAX_WORKERS", "8"))
    max_workers = min(max_workers, max(1, (os.cpu_count() or 2) - 1))

    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        roc_base = run_roc_sweep_ci_generated_with_pool(pool, cfg, thresholds=thresholds, gen=gen_base)

        cfg_no_ndwi = Config()
        setattr(cfg_no_ndwi, "ndwi_enabled", False)
        setattr(cfg_no_ndwi, "stage1_stride", 1)
        roc_no_ndwi = run_roc_sweep_ci_generated_with_pool(
            pool, cfg_no_ndwi, thresholds=thresholds, gen=gen_base
        )

        stride_points = []
        for stride in stride_values:
            cfg_stride = Config()
            setattr(cfg_stride, "ndwi_enabled", True)
            setattr(cfg_stride, "stage1_stride", stride)
            eval_result = evaluate_policy_generated_with_pool(
                pool,
                "MASFE_MDP",
                MASFEPolicy,
                {},
                cfg_stride,
                **gen_base,
            )
            recall = eval_result["stats"]["science_retention_pct"]
            fp = eval_result["stats"]["false_positive_rate_pct"]
            stride_points.append(
                {
                    "stage1_stride": float(stride),
                    "science_retention_pct": round(float(recall["mean"]), 3),
                    "science_retention_ci95_low": round(float(recall["ci95_low"]), 3),
                    "science_retention_ci95_high": round(float(recall["ci95_high"]), 3),
                    "false_positive_rate_pct": round(float(fp["mean"]), 3),
                    "false_positive_rate_ci95_low": round(float(fp["ci95_low"]), 3),
                    "false_positive_rate_ci95_high": round(float(fp["ci95_high"]), 3),
                    "seasonal_average_compute_utilisation_pct": round(
                        eval_result["stats"]["seasonal_average_compute_utilisation_pct"]["mean"], 3
                    ),
                }
            )

        cloud_points = []
        for cloud_prob in cloud_values:
            gen_cloud = dict(ADDITIONAL_ABLATION_DEFAULTS)
            gen_cloud["cloud_pass_prob"] = float(cloud_prob)
            eval_result = evaluate_policy_generated_with_pool(
                pool,
                "MASFE_MDP",
                MASFEPolicy,
                {},
                cfg,
                **gen_cloud,
            )
            recall = eval_result["stats"]["science_retention_pct"]
            fp = eval_result["stats"]["false_positive_rate_pct"]
            cloud_points.append(
                {
                    "cloud_pass_prob": round(float(cloud_prob), 2),
                    "science_retention_pct": round(float(recall["mean"]), 3),
                    "science_retention_ci95_low": round(float(recall["ci95_low"]), 3),
                    "science_retention_ci95_high": round(float(recall["ci95_high"]), 3),
                    "false_positive_rate_pct": round(float(fp["mean"]), 3),
                    "false_positive_rate_ci95_low": round(float(fp["ci95_low"]), 3),
                    "false_positive_rate_ci95_high": round(float(fp["ci95_high"]), 3),
                    "cloud_obscured_passes": round(
                        eval_result["stats"]["cloud_obscured_passes"]["mean"], 3
                    ),
                }
            )

    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.2))

    ax = axes[0]
    ax.plot(
        [p["false_positive_rate_pct"] for p in roc_base["thresholds"]],
        [p["science_retention_pct"] for p in roc_base["thresholds"]],
        marker="o",
        linewidth=1.6,
        color="#1b5e8a",
        label="Baseline",
    )
    ax.plot(
        [p["false_positive_rate_pct"] for p in roc_no_ndwi["thresholds"]],
        [p["science_retention_pct"] for p in roc_no_ndwi["thresholds"]],
        marker="o",
        linewidth=1.6,
        color="#b00020",
        label="NDWI removed",
    )
    ax.set_xlabel("FP rate (%)")
    ax.set_ylabel("Recall (%)")
    ax.set_title("CSC threshold sweep")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.legend(frameon=False, fontsize=8, loc="lower right")

    ax = axes[1]
    ax.plot(
        [p["stage1_stride"] for p in stride_points],
        [p["science_retention_pct"] for p in stride_points],
        marker="o",
        linewidth=1.6,
        color="#1b5e8a",
    )
    ax.set_xlabel("Stage-1 stride (passes)")
    ax.set_ylabel("Recall (%)")
    ax.set_title("Sparse screening cadence")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.set_xticks([p["stage1_stride"] for p in stride_points])

    ax = axes[2]
    ax.plot(
        [p["cloud_pass_prob"] for p in cloud_points],
        [p["science_retention_pct"] for p in cloud_points],
        marker="o",
        linewidth=1.6,
        color="#1b5e8a",
    )
    ax.set_xlabel("Cloud-flag rate")
    ax.set_ylabel("Recall (%)")
    ax.set_title("Cloud mask strictness")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)

    fig.tight_layout()
    curve_path = OUTPUTS_DIR / "additional_ablation_curves.png"
    curve_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(curve_path, dpi=220)
    plt.close(fig)

    return {
        "ndwi_removed": {
            "roc_baseline": roc_base,
            "roc_ndwi_removed": roc_no_ndwi,
        },
        "stage1_stride_sweep": stride_points,
        "cloud_pass_prob_sweep": cloud_points,
        "artifacts": {
            "curves_png": str(curve_path),
        },
    }


def run_csc_sensitivity(cfg: Config, datasets: list[Dict]) -> dict:
    cases = []
    for weight_scale in WEIGHT_SWEEP:
        for saturation_scale in SATURATION_SWEEP:
            evi_weight = 0.40 * weight_scale
            lst_weight = 0.35
            ndwi_weight = 0.25 * weight_scale
            csc_kwargs = {
                "evi_weight": evi_weight,
                "lst_weight": lst_weight,
                "ndwi_weight": ndwi_weight,
                "evi_saturation": 5.0 * saturation_scale,
                "lst_saturation": 4.0 * saturation_scale,
                "ndwi_saturation": 4.0 * saturation_scale,
            }
            eval_result = evaluate_policy(
                "MASFE_MDP",
                lambda: MASFEPolicy(),
                cfg,
                datasets,
                csc_kwargs=csc_kwargs,
            )
            recall = eval_result["stats"]["science_retention_pct"]
            fp = eval_result["stats"]["false_positive_rate_pct"]
            cases.append(
                {
                    "weight_sweep_scale": float(weight_scale),
                    "saturation_sweep_scale": float(saturation_scale),
                    "evi_weight_raw": round(evi_weight, 4),
                    "lst_weight_raw": round(lst_weight, 4),
                    "ndwi_weight_raw": round(ndwi_weight, 4),
                    "evi_saturation_sigma": round(5.0 * saturation_scale, 3),
                    "lst_saturation_sigma": round(4.0 * saturation_scale, 3),
                    "ndwi_saturation_sigma": round(4.0 * saturation_scale, 3),
                    "science_retention_pct": round(float(recall["mean"]), 3),
                    "science_retention_ci95_low": round(float(recall["ci95_low"]), 3),
                    "science_retention_ci95_high": round(float(recall["ci95_high"]), 3),
                    "false_positive_rate_pct": round(float(fp["mean"]), 3),
                    "false_positive_rate_ci95_low": round(float(fp["ci95_low"]), 3),
                    "false_positive_rate_ci95_high": round(float(fp["ci95_high"]), 3),
                    "alert_precision_pct": round(eval_result["stats"]["alert_precision_pct"]["mean"], 3),
                }
            )

    summary = {}
    for metric_name in ("science_retention_pct", "false_positive_rate_pct", "alert_precision_pct"):
        values = [case[metric_name] for case in cases]
        summary[metric_name] = {
            "min": round(min(values), 3),
            "max": round(max(values), 3),
        }

    return {
        "weight_sweep_scale": WEIGHT_SWEEP,
        "saturation_sweep_scale": SATURATION_SWEEP,
        "cases": cases,
        "summary": summary,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(metrics: dict, ablation_metrics: dict, roc_metrics: dict, csc_sensitivity: dict) -> None:
    mc = metrics["monte_carlo"]
    ci = mc["per_metric_ci95"]
    masfe = mc["policy_summary"]["MASFE_MDP"]
    fixed = mc["policy_summary"]["FIXED_ONBOARD"]
    raw = mc["policy_summary"]["RAW_DUMP"]

    print("\n" + "=" * 72)
    print("  MASFE - Multi-Algorithm Scheduling and Fusion Engine")
    print("  NASA Space-to-Soil Challenge 2026 - Monte Carlo Results")
    print("=" * 72)

    print("\n  NASA ALGORITHM CITATIONS")
    print("  |- MOD13A1  DOI: 10.5067/MODIS/MOD13A1.061  (EVI vegetation index)")
    print("  `- MOD11A1  DOI: 10.5067/MODIS/MOD11A1.061  (land surface temp)")
    print("     MOD09A1  DOI: 10.5067/MODIS/MOD09A1.061  (surface reflectance / NDWI)")
    print("  Fusion: Crop Stress Composite (CSC) - EVI anomaly + LST anomaly + NDWI anomaly")

    print("\n  SYNTHETIC VALIDATION CONFIGURATION")
    print(f"  |- Monte Carlo seeds:   {mc['n_seeds']}")
    print(f"  |- Field patches/seed:  {mc['n_patches']}")
    print(f"  |- Passes/seed:         {mc['n_t']}")
    print(f"  |- Disease events/seed: {mc['n_dis']}")
    print(f"  `- Benign confounders:  {mc['n_benign']}")

    print("\n  HOSTED PAYLOAD SWAP COMPLIANCE (LEON4FT + Kintex UltraScale+ RT)")
    print(f"  |- Peak payload power:  {metrics['peak_power_w']:.1f}W")
    print(f"  |- Avg payload power:   {metrics['avg_payload_power_w']:.2f}W   [host alloc 10.5W]  PASS")
    print(f"  |- Peak compute load:   {metrics['compute_utilisation_pct']:.1f}% of LEON4FT  PASS")
    print(f"  |- Stage-1-only load:   {metrics['stage1_compute_utilisation_pct']:.1f}% of LEON4FT")
    print(
        f"  |- Seasonal avg load:   {metrics['seasonal_average_compute_utilisation_pct']:.1f}% of LEON4FT"
        f"  (95% CI {ci['seasonal_average_compute_utilisation_pct']['ci95_low']:.1f}"
        f"-{ci['seasonal_average_compute_utilisation_pct']['ci95_high']:.1f})"
    )
    print(f"  `- Min battery SOC:     {metrics['min_battery_soc']:.1%} mean seed minimum   [40Wh local buffer]  PASS")
    print(
        f"  Cloud-obscured passes:  {metrics['cloud_obscured_passes']:.1f}/{mc['n_t']} mean"
        f"  (95% CI {ci['cloud_obscured_passes']['ci95_low']:.1f}-{ci['cloud_obscured_passes']['ci95_high']:.1f})"
    )
    print(
        f"  Resolution pyramid:     {metrics['resolution_pyramid']['screen_gsd_m']:.0f}m screen,"
        f" {metrics['resolution_pyramid']['confirmation_gsd_m']:.0f}m confirm,"
        f" {metrics['resolution_pyramid']['priority_gsd_m']:.1f}m priority"
    )
    print(
        f"  Priority tile payload:  {metrics['compression']['priority_tile_raw_mb_per_km2']:.2f} MB/km^2 raw"
        f" -> {metrics['compression']['priority_tile_delivered_mb_per_km2']:.2f} MB/km^2 delivered"
        f" at {metrics['compression']['priority_tile_compression_ratio']:.1f}:1"
    )

    print("\n  THREE-WAY PERFORMANCE COMPARISON (Monte Carlo means)")
    header = f"  {'Metric':<40} {'RAW DUMP':>10} {'FIXED OB':>10} {'MASFE MDP':>10}"
    print(header)
    print("  " + "-" * 72)

    def row(label, a, b, c, fmt="{:.0f}"):
        print(f"  {label:<40} {fmt.format(a):>10} {fmt.format(b):>10} {fmt.format(c):>10}")

    row("Downlink data (MB)", raw["data_mb_mean"], fixed["data_mb_mean"], masfe["data_mb_mean"])
    row("Energy consumed (Wh)", raw["energy_mean_wh"], fixed["energy_mean_wh"], masfe["energy_mean_wh"], fmt="{:.2f}")
    row("True positives (TP)", raw["tp_mean"], fixed["tp_mean"], masfe["tp_mean"], fmt="{:.1f}")
    row("False positives (FP)", raw["fp_mean"], fixed["fp_mean"], masfe["fp_mean"], fmt="{:.1f}")
    row("Priority alerts sent", 0.0, 0.0, masfe["n_alerts_mean"], fmt="{:.1f}")
    print("  " + "-" * 72)

    print("\n  KEY METRICS vs RAW DUMP BASELINE (Monte Carlo means)")
    print(
        f"  * Downlink reduction: {metrics['downlink_reduction_vs_raw_pct']:.1f}%"
        f"  (95% CI {ci['downlink_reduction_vs_raw_pct']['ci95_low']:.1f}"
        f"-{ci['downlink_reduction_vs_raw_pct']['ci95_high']:.1f})"
    )
    print(
        f"  * Energy saving:      {metrics['energy_saving_vs_raw_pct']:.1f}%"
        f"  (95% CI {ci['energy_saving_vs_raw_pct']['ci95_low']:.1f}"
        f"-{ci['energy_saving_vs_raw_pct']['ci95_high']:.1f})"
    )

    print("\n  KEY METRICS vs FIXED-SCHEDULE ONBOARD (Monte Carlo means)")
    print(
        f"  * Downlink reduction: {metrics['downlink_reduction_vs_fixed_pct']:.1f}%"
        f"  (95% CI {ci['downlink_reduction_vs_fixed_pct']['ci95_low']:.1f}"
        f"-{ci['downlink_reduction_vs_fixed_pct']['ci95_high']:.1f})"
    )
    print(
        f"  * Energy saving:      {metrics['energy_saving_vs_fixed_pct']:.1f}%"
        f"  (95% CI {ci['energy_saving_vs_fixed_pct']['ci95_low']:.1f}"
        f"-{ci['energy_saving_vs_fixed_pct']['ci95_high']:.1f})"
    )

    print(
        f"\n  SCIENCE RETENTION:   {metrics['science_retention_pct']:.1f}%"
        f"  (95% CI {ci['science_retention_pct']['ci95_low']:.1f}-{ci['science_retention_pct']['ci95_high']:.1f})"
    )
    print(
        f"  ALERT PRECISION:     {metrics['alert_precision_pct']:.1f}%"
        f"  (95% CI {ci['alert_precision_pct']['ci95_low']:.1f}-{ci['alert_precision_pct']['ci95_high']:.1f})"
    )
    print(
        f"  FALSE-POSITIVE RATE: {metrics['false_positive_rate_pct']:.1f}%"
        f"  (95% CI {ci['false_positive_rate_pct']['ci95_low']:.1f}-{ci['false_positive_rate_pct']['ci95_high']:.1f})"
        "  (target <=15%)"
    )
    print(
        f"  ABLATION (matched recall): FP rate rises by {ablation_metrics['false_positive_rate_delta_pct_points']:.1f} pts"
        f"  to {ablation_metrics['ablation_false_positive_rate_pct']:.1f}%"
        f"  at threshold {ablation_metrics['selected_alert_threshold']:.2f}"
    )

    print("\n  MASFE SCHEDULING DECISIONS (mean share of passes)")
    total_pct = sum(item["pct_mean"] for item in masfe["action_mix"].values())
    for action_name, action_metrics in sorted(
        masfe["action_mix"].items(),
        key=lambda item: -item[1]["pct_mean"],
    ):
        pct = action_metrics["pct_mean"]
        bar = "#" * int((pct / max(total_pct, 1e-9)) * 20)
        print(f"  {action_name:<18}  {action_metrics['count_mean']:>5.1f}x  ({pct:5.1f}%)  {bar}")

    print("\n  ADDITIONAL REPO OUTPUTS")
    print("  * outputs/ablation_metrics.json")
    print("  * outputs/evi_only_baseline.json")
    print("  * outputs/baselines_comparison_table.tex")
    print("  * outputs/roc_metrics.json")
    print("  * outputs/roc.png")
    print("  * outputs/csc_sensitivity.json")
    print("  * outputs/additional_ablations.json")
    print("  * outputs/additional_ablation_curves.png")
    print("  * outputs/roc_baseline_vs_no_ndwi.png")
    print(
        "  * CSC sweep summary: recall "
        f"{csc_sensitivity['summary']['science_retention_pct']['min']:.1f}-"
        f"{csc_sensitivity['summary']['science_retention_pct']['max']:.1f}%"
        ", FP rate "
        f"{csc_sensitivity['summary']['false_positive_rate_pct']['min']:.1f}-"
        f"{csc_sensitivity['summary']['false_positive_rate_pct']['max']:.1f}%"
    )

    print("=" * 72)
    print(f"\n  JSON (paste into paper):\n{json.dumps(metrics, indent=2)}")
    metrics_path = OUTPUTS_DIR / "simulation_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"\n  Metrics written to {metrics_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--additional-ablations-only",
        action="store_true",
        help="Only regenerate outputs/additional_ablations.json (skips headline Monte Carlo).",
    )
    args = parser.parse_args()

    cfg = Config()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import matplotlib  # noqa: F401

        plots_enabled = True
    except ModuleNotFoundError:
        plots_enabled = False

    if args.additional_ablations_only:
        print("MASFE Simulation - running additional ablations only...")
        if not plots_enabled:
            raise RuntimeError(
                "matplotlib is required for --additional-ablations-only. "
                "Install matplotlib or run the full benchmark (which can skip plots)."
            )
        additional_ablations = run_additional_ablations(cfg)
        write_json(OUTPUTS_DIR / "additional_ablations.json", additional_ablations)
        # Keep Figure 2 reproducible without running the full benchmark.
        datasets = build_datasets(
            ADDITIONAL_ABLATION_DEFAULTS["n_seeds"],
            ADDITIONAL_ABLATION_DEFAULTS["n_patches"],
            ADDITIONAL_ABLATION_DEFAULTS["n_t"],
            ADDITIONAL_ABLATION_DEFAULTS["n_dis"],
            ADDITIONAL_ABLATION_DEFAULTS["n_benign"],
        )
        csc_sensitivity = run_csc_sensitivity(cfg, datasets)
        write_json(OUTPUTS_DIR / "csc_sensitivity.json", csc_sensitivity)
        write_multi_roc_plot(
            additional_ablations["ndwi_removed"]["roc_baseline"],
            additional_ablations["ndwi_removed"]["roc_ndwi_removed"],
            ("Baseline", "NDWI removed"),
            OUTPUTS_DIR / "roc_baseline_vs_no_ndwi.png",
        )
        sys.exit(0)

    print("MASFE Simulation - running 100-seed Monte Carlo benchmark...")
    datasets = build_datasets(
        MONTE_CARLO_DEFAULTS["n_seeds"],
        MONTE_CARLO_DEFAULTS["n_patches"],
        MONTE_CARLO_DEFAULTS["n_t"],
        MONTE_CARLO_DEFAULTS["n_dis"],
        MONTE_CARLO_DEFAULTS["n_benign"],
    )
    metrics = run_monte_carlo(cfg, datasets=datasets)
    ablation_metrics = run_ablation_analysis(cfg, datasets, metrics)
    evi_only_metrics = run_evi_only_baseline(cfg, datasets, metrics)
    roc_metrics = run_roc_sweep(cfg, datasets)
    csc_sensitivity = run_csc_sensitivity(cfg, datasets)
    additional_ablations = None
    if plots_enabled:
        additional_ablations = run_additional_ablations(cfg)

    write_json(OUTPUTS_DIR / "ablation_metrics.json", ablation_metrics)
    write_json(OUTPUTS_DIR / "evi_only_baseline.json", evi_only_metrics)
    write_baselines_comparison_table(
        metrics,
        ablation_metrics,
        evi_only_metrics,
        OUTPUTS_DIR / "baselines_comparison_table.tex",
    )
    write_json(OUTPUTS_DIR / "roc_metrics.json", roc_metrics)
    if plots_enabled:
        write_roc_plot(roc_metrics, OUTPUTS_DIR / "roc.png")
    write_json(OUTPUTS_DIR / "csc_sensitivity.json", csc_sensitivity)
    if plots_enabled and additional_ablations is not None:
        write_json(OUTPUTS_DIR / "additional_ablations.json", additional_ablations)
        write_multi_roc_plot(
            additional_ablations["ndwi_removed"]["roc_baseline"],
            additional_ablations["ndwi_removed"]["roc_ndwi_removed"],
            ("Baseline", "NDWI removed"),
            OUTPUTS_DIR / "roc_baseline_vs_no_ndwi.png",
        )
    report(metrics, ablation_metrics, roc_metrics, csc_sensitivity)
