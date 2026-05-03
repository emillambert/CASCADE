from __future__ import annotations

import numpy as np
import pytest

from cascade.core import (
    ACTION_GSD_M,
    ACTION_TILE_DENSITY_MB_PER_KM2,
    AblateNoBeliefPolicy,
    CSC_DEFAULTS,
    CSC_SIGMAS,
    Config,
    CASCADEPolicy,
    State,
    _normalized_weights,
    action_gsd_m,
    action_tile_density_mb_per_km2,
    compute_csc,
    posterior_evidence,
    posterior_mean,
    posterior_tail_probability,
    update_stress_belief,
)


def make_state(
    *,
    soc: float = 0.84,
    downlink: bool = True,
    alpha: np.ndarray | None = None,
    beta: np.ndarray | None = None,
    evi_anom: np.ndarray | None = None,
    ndwi_anom: np.ndarray | None = None,
    csc: np.ndarray | None = None,
    steps_since_fuse: int = 0,
) -> State:
    alpha = np.array([1.0], dtype="float32") if alpha is None else alpha.astype("float32")
    beta = np.array([1.0], dtype="float32") if beta is None else beta.astype("float32")
    evi_anom = np.zeros_like(alpha) if evi_anom is None else evi_anom.astype("float32")
    ndwi_anom = np.zeros_like(alpha) if ndwi_anom is None else ndwi_anom.astype("float32")
    csc = np.full_like(alpha, 0.18) if csc is None else csc.astype("float32")
    return State(
        t=0,
        soc=soc,
        downlink=downlink,
        op=0.30,
        alpha=alpha,
        beta=beta,
        evi_anom=evi_anom,
        ndwi_anom=ndwi_anom,
        csc=csc,
        steps_since_fuse=steps_since_fuse,
    )


def test_config_helpers_and_action_lookups_stay_consistent() -> None:
    cfg = Config()

    assert cfg.peak_w() > cfg.avg_payload_w() > 0.0
    assert cfg.peak_compute_pct() == pytest.approx(cfg.action_compute_pct("RAW"))
    assert cfg.compute_pct() == pytest.approx(cfg.peak_compute_pct())
    assert cfg.seasonal_average_compute_pct({"MOD13": 1, "FUSE": 1}, 2) == pytest.approx(
        (cfg.action_compute_pct("MOD13") + cfg.action_compute_pct("FUSE")) / 2.0
    )
    assert cfg.seasonal_average_compute_pct({}, 0) == 0.0

    assert action_gsd_m("FUSE_PRIORITY") == ACTION_GSD_M["FUSE_PRIORITY"]
    assert action_tile_density_mb_per_km2("FUSE") == ACTION_TILE_DENSITY_MB_PER_KM2["FUSE"]
    assert action_gsd_m("UNKNOWN") == 0.0
    assert action_tile_density_mb_per_km2("UNKNOWN") == 0.0


def test_normalized_weights_and_posterior_helpers_match_known_values() -> None:
    assert _normalized_weights((2.0, 1.0, 1.0)) == pytest.approx((0.5, 0.25, 0.25))

    alpha = np.array([1.0, 2.0, 1.0], dtype="float32")
    beta = np.array([1.0, 1.0, 2.0], dtype="float32")

    assert posterior_mean(alpha, beta).tolist() == pytest.approx([0.5, 2.0 / 3.0, 1.0 / 3.0])
    assert posterior_evidence(alpha, beta).tolist() == pytest.approx([2.0, 3.0, 3.0])
    assert posterior_tail_probability(alpha, beta).tolist() == pytest.approx([0.5, 0.75, 0.25])


def test_compute_csc_preserves_fallback_weights_and_clips_outputs() -> None:
    evi_base = np.array([0.60], dtype="float32")
    lst_base = np.array([300.0], dtype="float32")
    ndwi_base = np.array([0.20], dtype="float32")

    legacy = compute_csc(
        evi_t=np.array([0.39], dtype="float32"),
        lst_t=np.array([300.0], dtype="float32"),
        evi_base=evi_base,
        lst_base=lst_base,
    )
    assert legacy.tolist() == pytest.approx([0.55], abs=1e-6)

    full = compute_csc(
        evi_t=np.array([0.39], dtype="float32"),
        lst_t=np.array([300.0], dtype="float32"),
        evi_base=evi_base,
        lst_base=lst_base,
        ndwi_t=ndwi_base,
        ndwi_base=ndwi_base,
    )
    expected_full = CSC_DEFAULTS.evi_weight * min(
        (0.60 - 0.39) / (CSC_DEFAULTS.evi_saturation * CSC_SIGMAS["evi"]),
        1.0,
    )
    assert full.tolist() == pytest.approx([expected_full], abs=1e-6)

    clipped = compute_csc(
        evi_t=np.array([0.10], dtype="float32"),
        lst_t=np.array([306.0], dtype="float32"),
        evi_base=evi_base,
        lst_base=lst_base,
        ndwi_t=np.array([0.00], dtype="float32"),
        ndwi_base=ndwi_base,
    )
    expected_clipped = (
        CSC_DEFAULTS.evi_weight * 1.0
        + CSC_DEFAULTS.lst_weight * 1.0
        + CSC_DEFAULTS.ndwi_weight
        * min((0.20 - 0.00) / (CSC_DEFAULTS.ndwi_saturation * CSC_SIGMAS["ndwi"]), 1.0)
    )
    assert clipped.tolist() == pytest.approx([expected_clipped], abs=1e-6)


def test_update_stress_belief_uses_inclusive_thresholds_and_caps_evidence() -> None:
    alpha = np.array([1.0, 7.0, 2.0], dtype="float32")
    beta = np.array([1.0, 1.0, 2.0], dtype="float32")
    evi_anom = np.array([0.18, 0.00, 0.17], dtype="float32")
    ndwi_anom = np.array([0.00, 0.12, 0.11], dtype="float32")

    alpha_new, beta_new = update_stress_belief(alpha, beta, evi_anom, ndwi_anom)

    assert alpha_new.tolist() == pytest.approx([2.0, 7.0, 2.0])
    assert beta_new.tolist() == pytest.approx([1.0, 1.0, 3.0])
    assert np.all(alpha_new + beta_new <= 8.0)


def test_cascade_policy_action_order_matches_battery_tail_and_exploration_rules() -> None:
    policy = CASCADEPolicy()
    strong_belief = dict(alpha=np.array([2.0]), beta=np.array([1.0]))

    assert policy.act(make_state(soc=0.10)) == "SKIP"
    assert policy.act(make_state(soc=0.20)) == "MOD13"
    assert policy.batt_cons == pytest.approx(0.35)
    assert policy.act(make_state(soc=0.34, **strong_belief)) == "MOD13"
    assert policy.act(make_state(soc=0.35, **strong_belief)) == "FUSE"
    assert policy.act(make_state(**strong_belief)) == "FUSE"
    assert policy.act(make_state(alpha=np.array([1.0]), beta=np.array([2.0]), steps_since_fuse=12)) == "FUSE"
    assert policy.act(make_state(alpha=np.array([1.0]), beta=np.array([2.0]), steps_since_fuse=0)) == "MOD13"


def test_priority_downlink_and_ablation_policy_gate_on_expected_signals() -> None:
    policy = CASCADEPolicy()
    strong_state = make_state(alpha=np.array([2.0]), beta=np.array([1.0]))
    above_threshold = np.array([policy.csc_alert_thr + 0.05], dtype="float32")
    below_threshold = np.array([max(policy.csc_alert_thr - 0.05, 0.0)], dtype="float32")

    assert policy.should_priority_downlink(strong_state, above_threshold)
    assert not policy.should_priority_downlink(strong_state, below_threshold)
    assert not policy.should_priority_downlink(
        make_state(alpha=np.array([1.0]), beta=np.array([1.0])),
        above_threshold,
    )
    assert not policy.should_priority_downlink(
        make_state(alpha=np.array([2.0]), beta=np.array([1.0]), downlink=False),
        above_threshold,
    )
    # Symmetric Beta with high pseudo-evidence but mean/tail near 0.5: CSC branch.
    sym = make_state(
        alpha=np.array([4.0], dtype="float32"),
        beta=np.array([4.0], dtype="float32"),
        downlink=True,
    )
    assert policy.should_priority_downlink(sym, above_threshold)

    ablation = AblateNoBeliefPolicy()
    assert ablation.act(make_state(evi_anom=np.array([0.19], dtype="float32"))) == "FUSE"
    assert ablation.act(make_state(ndwi_anom=np.array([0.13], dtype="float32"))) == "FUSE"
    assert ablation.act(make_state()) == "MOD13"
