# SPDX-License-Identifier: MIT
"""Offline CSC calibration for CASCADE.

This module searches over CSC weights, CSC saturation constants, and the
alerting threshold using the synthetic benchmark only. It writes reproducible
build outputs under ``build/calibration/`` and exits nonzero when no search
candidate clears the promotion gates relative to the current live defaults.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from cascade.core import (
    CSC_ALERT_THRESHOLD_DEFAULT,
    CSC_DEFAULTS,
    Config,
    CASCADEPolicy,
)
from cascade.paths import BUILD_CALIBRATION_DIR
from cascade.simulation import (
    MONTE_CARLO_DEFAULTS,
    build_datasets_for_seeds,
    evaluate_policy,
    round_stats,
    write_json,
)


TRAIN_SEEDS = tuple(range(60))
VALIDATION_SEEDS = tuple(range(60, 80))
TEST_SEEDS = tuple(range(80, 100))

WEIGHT_MIN = 0.10
WEIGHT_MAX = 0.70
EVI_SATURATION_MIN = 3.0
EVI_SATURATION_MAX = 7.0
THERMAL_SATURATION_MIN = 2.5
THERMAL_SATURATION_MAX = 6.0
THRESHOLD_MIN = 0.40
THRESHOLD_MAX = 0.70
DIRICHLET_CONCENTRATION = 60.0
WEIGHT_NOISE_STD = 0.10
SATURATION_NOISE_STD = 0.12
THRESHOLD_NOISE_STD = 0.03

RECALL_GATE_TRAIN_PCT = 99.5
RECALL_GATE_VALIDATION_PCT = 99.0
RECALL_GATE_TEST_PCT = 99.0
GUARDRAIL_RELATIVE_LIMIT = 1.05
MIN_VALIDATION_FP_IMPROVEMENT_PCT_POINTS = 0.10

SEARCH_METRICS = (
    "science_retention_pct",
    "false_positive_rate_pct",
    "data_mb",
    "seasonal_average_compute_utilisation_pct",
    "energy_wh",
)
GUARDRAIL_METRICS = (
    "data_mb",
    "seasonal_average_compute_utilisation_pct",
    "energy_wh",
)


@dataclass(frozen=True)
class CalibrationCandidate:
    evi_weight: float
    lst_weight: float
    ndwi_weight: float
    evi_saturation: float
    lst_saturation: float
    ndwi_saturation: float
    csc_alert_thr: float

    def compute_kwargs(self) -> dict[str, float]:
        return {
            "evi_weight": self.evi_weight,
            "lst_weight": self.lst_weight,
            "ndwi_weight": self.ndwi_weight,
            "evi_saturation": self.evi_saturation,
            "lst_saturation": self.lst_saturation,
            "ndwi_saturation": self.ndwi_saturation,
        }

    def policy_kwargs(self) -> dict[str, float]:
        return {"csc_alert_thr": self.csc_alert_thr}

    def as_dict(self) -> dict[str, float]:
        return {
            "evi_weight": round(self.evi_weight, 6),
            "lst_weight": round(self.lst_weight, 6),
            "ndwi_weight": round(self.ndwi_weight, 6),
            "evi_saturation": round(self.evi_saturation, 6),
            "lst_saturation": round(self.lst_saturation, 6),
            "ndwi_saturation": round(self.ndwi_saturation, 6),
            "csc_alert_thr": round(self.csc_alert_thr, 6),
        }


@dataclass(frozen=True)
class CalibrationSearchConfig:
    rng_seed: int = 20260424
    stage1_candidates: int = 1200
    stage2_parents: int = 24
    local_perturbations: int = 16
    train_seeds: tuple[int, ...] = TRAIN_SEEDS
    validation_seeds: tuple[int, ...] = VALIDATION_SEEDS
    test_seeds: tuple[int, ...] = TEST_SEEDS
    n_patches: int = MONTE_CARLO_DEFAULTS["n_patches"]
    n_t: int = MONTE_CARLO_DEFAULTS["n_t"]
    n_dis: int = MONTE_CARLO_DEFAULTS["n_dis"]
    n_benign: int = MONTE_CARLO_DEFAULTS["n_benign"]
    cloud_pass_prob: float = 0.30
    output_dir: Path = BUILD_CALIBRATION_DIR

    def as_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng_seed,
            "stage1_candidates": self.stage1_candidates,
            "stage2_parents": self.stage2_parents,
            "local_perturbations": self.local_perturbations,
            "n_patches": self.n_patches,
            "n_t": self.n_t,
            "n_dis": self.n_dis,
            "n_benign": self.n_benign,
            "cloud_pass_prob": self.cloud_pass_prob,
            "train_seed_range": [self.train_seeds[0], self.train_seeds[-1]],
            "validation_seed_range": [self.validation_seeds[0], self.validation_seeds[-1]],
            "test_seed_range": [self.test_seeds[0], self.test_seeds[-1]],
            "weight_bounds": [WEIGHT_MIN, WEIGHT_MAX],
            "evi_saturation_bounds": [EVI_SATURATION_MIN, EVI_SATURATION_MAX],
            "lst_saturation_bounds": [THERMAL_SATURATION_MIN, THERMAL_SATURATION_MAX],
            "ndwi_saturation_bounds": [THERMAL_SATURATION_MIN, THERMAL_SATURATION_MAX],
            "threshold_bounds": [THRESHOLD_MIN, THRESHOLD_MAX],
            "guardrail_relative_limit": GUARDRAIL_RELATIVE_LIMIT,
            "train_recall_gate_pct": RECALL_GATE_TRAIN_PCT,
            "validation_recall_gate_pct": RECALL_GATE_VALIDATION_PCT,
            "test_recall_gate_pct": RECALL_GATE_TEST_PCT,
            "min_validation_fp_improvement_pct_points": MIN_VALIDATION_FP_IMPROVEMENT_PCT_POINTS,
        }


def current_default_candidate() -> CalibrationCandidate:
    return CalibrationCandidate(
        evi_weight=CSC_DEFAULTS.evi_weight,
        lst_weight=CSC_DEFAULTS.lst_weight,
        ndwi_weight=CSC_DEFAULTS.ndwi_weight,
        evi_saturation=CSC_DEFAULTS.evi_saturation,
        lst_saturation=CSC_DEFAULTS.lst_saturation,
        ndwi_saturation=CSC_DEFAULTS.ndwi_saturation,
        csc_alert_thr=CSC_ALERT_THRESHOLD_DEFAULT,
    )


def project_weights_to_bounds(
    weights: np.ndarray | list[float],
    *,
    minimum: float = WEIGHT_MIN,
    maximum: float = WEIGHT_MAX,
) -> tuple[float, float, float]:
    arr = np.asarray(weights, dtype=float)
    if arr.shape != (3,):
        raise ValueError("CSC weight vectors must have exactly three elements.")
    arr = np.clip(arr, 0.0, None)
    if float(arr.sum()) <= 0.0:
        arr = np.full(3, 1.0 / 3.0, dtype=float)
    else:
        arr = arr / float(arr.sum())
    result = arr.copy()

    for _ in range(16):
        low = result < minimum - 1e-12
        if np.any(low):
            deficit = float(np.sum(minimum - result[low]))
            result[low] = minimum
            donors = result > minimum + 1e-12
            donor_mass = float(np.sum(result[donors] - minimum))
            if donor_mass > 0.0:
                result[donors] -= deficit * (result[donors] - minimum) / donor_mass

        high = result > maximum + 1e-12
        if np.any(high):
            excess = float(np.sum(result[high] - maximum))
            result[high] = maximum
            receivers = result < maximum - 1e-12
            receiver_capacity = float(np.sum(maximum - result[receivers]))
            if receiver_capacity > 0.0:
                result[receivers] += excess * (maximum - result[receivers]) / receiver_capacity

        if np.all(result >= minimum - 1e-9) and np.all(result <= maximum + 1e-9):
            break

    correction = 1.0 - float(result.sum())
    if abs(correction) > 1e-12:
        adjustable = np.where(
            (result > minimum + 1e-12) & (result < maximum - 1e-12)
        )[0]
        if adjustable.size == 0:
            adjustable = np.where(result < maximum - 1e-12)[0] if correction > 0 else np.where(result > minimum + 1e-12)[0]
        if adjustable.size:
            result[adjustable] += correction / adjustable.size

    result = np.clip(result, minimum, maximum)
    result /= float(result.sum())
    return tuple(float(value) for value in result)


def candidate_is_within_bounds(candidate: CalibrationCandidate) -> bool:
    weights = (candidate.evi_weight, candidate.lst_weight, candidate.ndwi_weight)
    if abs(sum(weights) - 1.0) > 1e-6:
        return False
    if any(weight < WEIGHT_MIN - 1e-9 or weight > WEIGHT_MAX + 1e-9 for weight in weights):
        return False
    if not (EVI_SATURATION_MIN <= candidate.evi_saturation <= EVI_SATURATION_MAX):
        return False
    if not (THERMAL_SATURATION_MIN <= candidate.lst_saturation <= THERMAL_SATURATION_MAX):
        return False
    if not (THERMAL_SATURATION_MIN <= candidate.ndwi_saturation <= THERMAL_SATURATION_MAX):
        return False
    if not (THRESHOLD_MIN <= candidate.csc_alert_thr <= THRESHOLD_MAX):
        return False
    return True


def make_candidate(
    *,
    weights: np.ndarray | list[float],
    evi_saturation: float,
    lst_saturation: float,
    ndwi_saturation: float,
    csc_alert_thr: float,
) -> CalibrationCandidate:
    evi_weight, lst_weight, ndwi_weight = project_weights_to_bounds(weights)
    candidate = CalibrationCandidate(
        evi_weight=evi_weight,
        lst_weight=lst_weight,
        ndwi_weight=ndwi_weight,
        evi_saturation=float(np.clip(evi_saturation, EVI_SATURATION_MIN, EVI_SATURATION_MAX)),
        lst_saturation=float(
            np.clip(lst_saturation, THERMAL_SATURATION_MIN, THERMAL_SATURATION_MAX)
        ),
        ndwi_saturation=float(
            np.clip(ndwi_saturation, THERMAL_SATURATION_MIN, THERMAL_SATURATION_MAX)
        ),
        csc_alert_thr=float(np.clip(csc_alert_thr, THRESHOLD_MIN, THRESHOLD_MAX)),
    )
    if not candidate_is_within_bounds(candidate):
        raise ValueError("Constructed CSC calibration candidate violates bounds.")
    return candidate


def baseline_distance(candidate: CalibrationCandidate) -> float:
    base = current_default_candidate()
    weight_delta = (
        abs(candidate.evi_weight - base.evi_weight)
        + abs(candidate.lst_weight - base.lst_weight)
        + abs(candidate.ndwi_weight - base.ndwi_weight)
    )
    saturation_delta = (
        abs(candidate.evi_saturation - base.evi_saturation) / max(base.evi_saturation, 1e-9)
        + abs(candidate.lst_saturation - base.lst_saturation) / max(base.lst_saturation, 1e-9)
        + abs(candidate.ndwi_saturation - base.ndwi_saturation) / max(base.ndwi_saturation, 1e-9)
    )
    threshold_delta = abs(candidate.csc_alert_thr - base.csc_alert_thr) / (
        THRESHOLD_MAX - THRESHOLD_MIN
    )
    return round(weight_delta + saturation_delta + threshold_delta, 6)


def build_split_datasets(config: CalibrationSearchConfig) -> dict[str, list[dict[str, Any]]]:
    dataset_kwargs = {
        "n_patches": config.n_patches,
        "n_t": config.n_t,
        "n_dis": config.n_dis,
        "n_benign": config.n_benign,
        "cloud_pass_prob": config.cloud_pass_prob,
    }
    return {
        "train": build_datasets_for_seeds(list(config.train_seeds), **dataset_kwargs),
        "validation": build_datasets_for_seeds(list(config.validation_seeds), **dataset_kwargs),
        "test": build_datasets_for_seeds(list(config.test_seeds), **dataset_kwargs),
    }


def candidate_metric_mean(record: dict[str, Any], split: str, metric_name: str) -> float:
    return float(record["metrics_by_split"][split][metric_name]["mean"])


def evaluate_candidate(
    candidate: CalibrationCandidate,
    cfg: Config,
    datasets_by_split: dict[str, list[dict[str, Any]]],
    *,
    split_names: tuple[str, ...],
    source_stage: str,
    candidate_index: int | None = None,
    parent_rank: int | None = None,
    parent_candidate: CalibrationCandidate | None = None,
) -> dict[str, Any]:
    metrics_by_split: dict[str, Any] = {}
    for split_name in split_names:
        result = evaluate_policy(
            "CASCADE_MDP",
            lambda candidate=candidate: CASCADEPolicy(**candidate.policy_kwargs()),
            cfg,
            datasets_by_split[split_name],
            csc_kwargs=candidate.compute_kwargs(),
        )
        metrics_by_split[split_name] = round_stats(result["stats"])

    record = {
        "parameters": candidate.as_dict(),
        "metrics_by_split": metrics_by_split,
        "distance_from_defaults": baseline_distance(candidate),
        "source_stage": source_stage,
    }
    if candidate_index is not None:
        record["candidate_index"] = int(candidate_index)
    if parent_rank is not None:
        record["parent_rank"] = int(parent_rank)
    if parent_candidate is not None:
        record["parent_parameters"] = parent_candidate.as_dict()
    return record


def evaluate_guardrails(
    candidate_record: dict[str, Any],
    baseline_record: dict[str, Any],
    *,
    split_name: str,
) -> dict[str, dict[str, float | bool]]:
    guardrails: dict[str, dict[str, float | bool]] = {}
    for metric_name in GUARDRAIL_METRICS:
        baseline_value = candidate_metric_mean(baseline_record, split_name, metric_name)
        candidate_value = candidate_metric_mean(candidate_record, split_name, metric_name)
        limit = baseline_value * GUARDRAIL_RELATIVE_LIMIT
        guardrails[metric_name] = {
            "baseline": round(baseline_value, 6),
            "candidate": round(candidate_value, 6),
            "limit": round(limit, 6),
            "passes": candidate_value <= limit + 1e-9,
        }
    return guardrails


def annotate_candidate_record(
    record: dict[str, Any],
    baseline_record: dict[str, Any],
) -> dict[str, Any]:
    train_recall = candidate_metric_mean(record, "train", "science_retention_pct")
    validation_recall = candidate_metric_mean(record, "validation", "science_retention_pct")
    validation_fp = candidate_metric_mean(record, "validation", "false_positive_rate_pct")
    baseline_validation_fp = candidate_metric_mean(
        baseline_record, "validation", "false_positive_rate_pct"
    )
    validation_guardrails = evaluate_guardrails(record, baseline_record, split_name="validation")
    validation_guardrail_pass = all(
        bool(block["passes"]) for block in validation_guardrails.values()
    )

    record["validation_fp_improvement_pct_points"] = round(
        baseline_validation_fp - validation_fp, 6
    )
    record["validation_guardrails"] = validation_guardrails
    record["train_recall_gate_passes"] = train_recall >= RECALL_GATE_TRAIN_PCT
    record["validation_recall_gate_passes"] = validation_recall >= RECALL_GATE_VALIDATION_PCT
    record["validation_guardrails_pass"] = validation_guardrail_pass
    record["feasible"] = (
        record["train_recall_gate_passes"]
        and record["validation_recall_gate_passes"]
        and validation_guardrail_pass
    )
    record["ranking_key"] = (
        validation_fp,
        candidate_metric_mean(record, "validation", "data_mb"),
        candidate_metric_mean(record, "validation", "seasonal_average_compute_utilisation_pct"),
        candidate_metric_mean(record, "validation", "energy_wh"),
        float(record["distance_from_defaults"]),
    )
    return record


def evaluate_test_promotion(
    candidate_record: dict[str, Any],
    baseline_record: dict[str, Any],
) -> dict[str, Any]:
    test_recall = candidate_metric_mean(candidate_record, "test", "science_retention_pct")
    test_guardrails = evaluate_guardrails(candidate_record, baseline_record, split_name="test")
    test_guardrails_pass = all(bool(block["passes"]) for block in test_guardrails.values())
    validation_improvement = float(candidate_record["validation_fp_improvement_pct_points"])
    promoted = (
        validation_improvement >= MIN_VALIDATION_FP_IMPROVEMENT_PCT_POINTS
        and test_recall >= RECALL_GATE_TEST_PCT
        and test_guardrails_pass
    )
    reasons = []
    if validation_improvement < MIN_VALIDATION_FP_IMPROVEMENT_PCT_POINTS:
        reasons.append("validation false-positive improvement below promotion threshold")
    if test_recall < RECALL_GATE_TEST_PCT:
        reasons.append("test recall below promotion gate")
    if not test_guardrails_pass:
        reasons.append("test guardrails exceeded")
    return {
        "promoted": promoted,
        "validation_fp_improvement_pct_points": round(validation_improvement, 6),
        "test_recall_pct": round(test_recall, 6),
        "test_guardrails": test_guardrails,
        "test_guardrails_pass": test_guardrails_pass,
        "reason": "; ".join(reasons) if reasons else "selected candidate cleared promotion gates",
    }


def sample_dirichlet_weights(
    rng: np.random.Generator,
    center: CalibrationCandidate,
    *,
    concentration: float = DIRICHLET_CONCENTRATION,
) -> tuple[float, float, float]:
    alpha = np.asarray([center.evi_weight, center.lst_weight, center.ndwi_weight], dtype=float)
    alpha = np.maximum(alpha * concentration, 1e-3)
    for _ in range(1024):
        weights = rng.dirichlet(alpha)
        if np.all(weights >= WEIGHT_MIN) and np.all(weights <= WEIGHT_MAX):
            return tuple(float(value) for value in weights)
    return project_weights_to_bounds(rng.dirichlet(alpha))


def sample_random_candidate(
    rng: np.random.Generator,
    center: CalibrationCandidate,
) -> CalibrationCandidate:
    weights = sample_dirichlet_weights(rng, center)
    return make_candidate(
        weights=np.asarray(weights, dtype=float),
        evi_saturation=rng.uniform(EVI_SATURATION_MIN, EVI_SATURATION_MAX),
        lst_saturation=rng.uniform(THERMAL_SATURATION_MIN, THERMAL_SATURATION_MAX),
        ndwi_saturation=rng.uniform(THERMAL_SATURATION_MIN, THERMAL_SATURATION_MAX),
        csc_alert_thr=rng.uniform(THRESHOLD_MIN, THRESHOLD_MAX),
    )


def sample_local_candidate(
    rng: np.random.Generator,
    parent: CalibrationCandidate,
) -> CalibrationCandidate:
    weight_vector = np.asarray(
        [parent.evi_weight, parent.lst_weight, parent.ndwi_weight], dtype=float
    )
    weight_vector = weight_vector * np.exp(rng.normal(0.0, WEIGHT_NOISE_STD, size=3))
    return make_candidate(
        weights=weight_vector,
        evi_saturation=parent.evi_saturation * np.exp(rng.normal(0.0, SATURATION_NOISE_STD)),
        lst_saturation=parent.lst_saturation * np.exp(rng.normal(0.0, SATURATION_NOISE_STD)),
        ndwi_saturation=parent.ndwi_saturation * np.exp(rng.normal(0.0, SATURATION_NOISE_STD)),
        csc_alert_thr=parent.csc_alert_thr + rng.normal(0.0, THRESHOLD_NOISE_STD),
    )


def top_ranked_feasible(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    feasible = [record for record in records if record.get("feasible")]
    feasible.sort(key=lambda record: tuple(record["ranking_key"]))
    return feasible


def pareto_frontier(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    feasible = top_ranked_feasible(records)
    frontier = []
    for candidate in feasible:
        candidate_point = tuple(candidate["ranking_key"][:4])
        dominated = False
        for other in feasible:
            if other is candidate:
                continue
            other_point = tuple(other["ranking_key"][:4])
            if all(other_metric <= candidate_metric for other_metric, candidate_metric in zip(other_point, candidate_point)) and any(
                other_metric < candidate_metric for other_metric, candidate_metric in zip(other_point, candidate_point)
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    frontier.sort(key=lambda record: tuple(record["ranking_key"]))
    return frontier


def promote_candidate_record(
    record: dict[str, Any],
    cfg: Config,
    datasets_by_split: dict[str, list[dict[str, Any]]],
    baseline_record: dict[str, Any],
) -> dict[str, Any]:
    candidate = make_candidate(**{
        "weights": [
            record["parameters"]["evi_weight"],
            record["parameters"]["lst_weight"],
            record["parameters"]["ndwi_weight"],
        ],
        "evi_saturation": record["parameters"]["evi_saturation"],
        "lst_saturation": record["parameters"]["lst_saturation"],
        "ndwi_saturation": record["parameters"]["ndwi_saturation"],
        "csc_alert_thr": record["parameters"]["csc_alert_thr"],
    })
    full_record = evaluate_candidate(
        candidate,
        cfg,
        datasets_by_split,
        split_names=("train", "validation", "test"),
        source_stage=record["source_stage"],
        candidate_index=record.get("candidate_index"),
        parent_rank=record.get("parent_rank"),
    )
    if "parent_parameters" in record:
        full_record["parent_parameters"] = record["parent_parameters"]
    full_record = annotate_candidate_record(full_record, baseline_record)
    full_record["promotion_status"] = evaluate_test_promotion(full_record, baseline_record)
    return full_record


def split_delta_payload(
    baseline_record: dict[str, Any],
    candidate_record: dict[str, Any] | None,
    split_name: str,
) -> dict[str, float] | None:
    if candidate_record is None:
        return None

    def delta(metric_name: str) -> float:
        baseline_value = candidate_metric_mean(baseline_record, split_name, metric_name)
        candidate_value = candidate_metric_mean(candidate_record, split_name, metric_name)
        return round(candidate_value - baseline_value, 6)

    def relative(metric_name: str) -> float:
        baseline_value = candidate_metric_mean(baseline_record, split_name, metric_name)
        candidate_value = candidate_metric_mean(candidate_record, split_name, metric_name)
        return round((candidate_value / max(baseline_value, 1e-9) - 1.0) * 100.0, 6)

    return {
        "science_retention_pct_points": delta("science_retention_pct"),
        "false_positive_rate_pct_points": delta("false_positive_rate_pct"),
        "data_mb_relative_pct": relative("data_mb"),
        "seasonal_average_compute_utilisation_pct_relative_pct": relative(
            "seasonal_average_compute_utilisation_pct"
        ),
        "energy_wh_relative_pct": relative("energy_wh"),
    }


def run_calibration(
    config: CalibrationSearchConfig | None = None,
    *,
    cfg: Config | None = None,
) -> dict[str, Any]:
    config = config or CalibrationSearchConfig()
    cfg = cfg or Config()
    rng = np.random.default_rng(config.rng_seed)
    datasets_by_split = build_split_datasets(config)
    baseline_candidate = current_default_candidate()
    baseline_record = evaluate_candidate(
        baseline_candidate,
        cfg,
        datasets_by_split,
        split_names=("train", "validation", "test"),
        source_stage="baseline",
    )
    baseline_record = annotate_candidate_record(baseline_record, baseline_record)
    baseline_record["promotion_status"] = {
        "promoted": False,
        "reason": "current live defaults are the baseline reference candidate",
    }

    stage1_records = []
    for candidate_index in range(config.stage1_candidates):
        candidate = sample_random_candidate(rng, baseline_candidate)
        record = evaluate_candidate(
            candidate,
            cfg,
            datasets_by_split,
            split_names=("train", "validation"),
            source_stage="random",
            candidate_index=candidate_index,
        )
        stage1_records.append(annotate_candidate_record(record, baseline_record))

    stage1_parents = top_ranked_feasible(stage1_records)[: config.stage2_parents]
    stage2_records = []
    for parent_rank, parent_record in enumerate(stage1_parents, start=1):
        parent_candidate = make_candidate(
            weights=[
                parent_record["parameters"]["evi_weight"],
                parent_record["parameters"]["lst_weight"],
                parent_record["parameters"]["ndwi_weight"],
            ],
            evi_saturation=parent_record["parameters"]["evi_saturation"],
            lst_saturation=parent_record["parameters"]["lst_saturation"],
            ndwi_saturation=parent_record["parameters"]["ndwi_saturation"],
            csc_alert_thr=parent_record["parameters"]["csc_alert_thr"],
        )
        for local_index in range(config.local_perturbations):
            candidate = sample_local_candidate(rng, parent_candidate)
            record = evaluate_candidate(
                candidate,
                cfg,
                datasets_by_split,
                split_names=("train", "validation"),
                source_stage="local",
                candidate_index=local_index,
                parent_rank=parent_rank,
                parent_candidate=parent_candidate,
            )
            stage2_records.append(annotate_candidate_record(record, baseline_record))

    combined_records = stage1_records + stage2_records
    feasible_candidates = top_ranked_feasible(combined_records)
    if feasible_candidates:
        best_candidate_record = feasible_candidates[0]
    elif combined_records:
        best_candidate_record = sorted(
            combined_records,
            key=lambda record: tuple(record["ranking_key"]),
        )[0]
    else:
        best_candidate_record = None
    selected_candidate_record = None
    promotion_status = {
        "promoted": False,
        "reason": "no feasible search candidate met the train/validation gates",
    }
    if best_candidate_record is not None:
        selected_candidate_record = promote_candidate_record(
            best_candidate_record,
            cfg,
            datasets_by_split,
            baseline_record,
        )
        if selected_candidate_record["feasible"]:
            promotion_status = dict(selected_candidate_record["promotion_status"])
        else:
            selected_candidate_record["promotion_status"] = {
                "promoted": False,
                "reason": "selected candidate did not clear the train/validation feasibility gates",
            }
            promotion_status = dict(selected_candidate_record["promotion_status"])

    top_candidates = [baseline_record] + feasible_candidates[:25]
    pareto_candidates = pareto_frontier([baseline_record] + combined_records)[:25]

    summary = {
        "search_config": config.as_dict(),
        "split_definition": {
            "train": list(config.train_seeds),
            "validation": list(config.validation_seeds),
            "test": list(config.test_seeds),
        },
        "search_outcomes": {
            "stage1_candidates_evaluated": len(stage1_records),
            "stage1_feasible_candidates": sum(1 for record in stage1_records if record["feasible"]),
            "stage2_candidates_evaluated": len(stage2_records),
            "stage2_feasible_candidates": sum(1 for record in stage2_records if record["feasible"]),
            "combined_feasible_candidates": len(feasible_candidates),
        },
        "baseline_candidate": baseline_record,
        "selected_candidate": selected_candidate_record,
        "improvement_deltas": {
            "validation": split_delta_payload(baseline_record, selected_candidate_record, "validation"),
            "test": split_delta_payload(baseline_record, selected_candidate_record, "test"),
        },
        "promotion_status": promotion_status,
    }

    config.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(config.output_dir / "calibration_summary.json", summary)
    write_json(
        config.output_dir / "selected_candidate.json",
        {
            "selected_candidate": selected_candidate_record,
            "promotion_status": promotion_status,
        },
    )
    write_json(
        config.output_dir / "top_candidates.json",
        {
            "top_candidates": top_candidates,
            "count": len(top_candidates),
        },
    )
    write_json(
        config.output_dir / "pareto_candidates.json",
        {
            "pareto_candidates": pareto_candidates,
            "count": len(pareto_candidates),
        },
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rng-seed", type=int, default=CalibrationSearchConfig.rng_seed)
    parser.add_argument(
        "--stage1-candidates",
        type=int,
        default=CalibrationSearchConfig.stage1_candidates,
    )
    parser.add_argument(
        "--stage2-parents",
        type=int,
        default=CalibrationSearchConfig.stage2_parents,
    )
    parser.add_argument(
        "--local-perturbations",
        type=int,
        default=CalibrationSearchConfig.local_perturbations,
    )
    parser.add_argument("--n-patches", type=int, default=CalibrationSearchConfig.n_patches)
    parser.add_argument("--n-t", type=int, default=CalibrationSearchConfig.n_t)
    parser.add_argument("--n-dis", type=int, default=CalibrationSearchConfig.n_dis)
    parser.add_argument("--n-benign", type=int, default=CalibrationSearchConfig.n_benign)
    parser.add_argument("--cloud-pass-prob", type=float, default=CalibrationSearchConfig.cloud_pass_prob)
    parser.add_argument(
        "--output-dir",
        default=str(CalibrationSearchConfig.output_dir),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = CalibrationSearchConfig(
        rng_seed=args.rng_seed,
        stage1_candidates=args.stage1_candidates,
        stage2_parents=args.stage2_parents,
        local_perturbations=args.local_perturbations,
        n_patches=args.n_patches,
        n_t=args.n_t,
        n_dis=args.n_dis,
        n_benign=args.n_benign,
        cloud_pass_prob=args.cloud_pass_prob,
        output_dir=Path(args.output_dir),
    )
    summary = run_calibration(config)
    print(json.dumps(summary["promotion_status"], indent=2))
    return 0 if summary["promotion_status"]["promoted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
