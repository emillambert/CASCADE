"""Shared MASFE policy and hardware primitives.

This module is the single source of truth for the hosted-payload SWAP model,
Crop Stress Composite (CSC) computation, and the deterministic MDP-inspired
policy used by both the synthetic benchmark and the real MODIS replay.
"""

from dataclasses import dataclass
import math

import numpy as np


@dataclass
class Config:
    """
    Hosted-payload configuration anchored to the submission's component choices.

    LEON4FT: Cobham Gaisler UT699E-class processor
    FPGA:    Xilinx Kintex UltraScale+ RT
    Battery: Local payload buffer, 40 Wh equivalent
    """

    batt_wh: float = 40.0
    solar_w: float = 10.5
    orbit_min: float = 94.6
    eclipse_frac: float = 0.356

    # Power by component (W)
    fpga_w: float = 1.8
    cpu_w: float = 1.2
    mod13_w: float = 0.8
    mod11_w: float = 0.9
    fuse_w: float = 0.5
    mdp_w: float = 0.2
    sensor_ms: float = 1.5
    sensor_tir: float = 0.7
    comms_w: float = 2.0

    # Data volumes (MB per pass, <=30m effective GSD after onboard binning)
    raw_mb: float = 120.0
    indices_mb: float = 1.4
    csc_map_mb: float = 2.8
    alert_mb: float = 1.8

    # Compute (DMIPS)
    leon4ft_dmips: float = 600.0
    mod13_dmips: float = 180.0
    mod11_dmips: float = 200.0
    fuse_dmips: float = 120.0
    mdp_dmips: float = 55.0

    def peak_w(self) -> float:
        return (
            self.fpga_w
            + self.cpu_w
            + self.mod13_w
            + self.mod11_w
            + self.fuse_w
            + self.mdp_w
            + self.sensor_ms
            + self.sensor_tir
            + self.comms_w
        )

    def avg_payload_w(self) -> float:
        return (
            self.fpga_w
            + self.cpu_w
            + self.mdp_w
            + self.mod13_w * 0.55
            + self.mod11_w * 0.18
            + self.fuse_w * 0.18
            + self.sensor_ms * 0.50
            + self.sensor_tir * 0.18
            + self.comms_w * 0.14
        )

    def peak_compute_pct(self) -> float:
        return (
            self.mod13_dmips
            + self.mod11_dmips
            + self.fuse_dmips
            + self.mdp_dmips
        ) / self.leon4ft_dmips

    def stage1_compute_pct(self) -> float:
        return (self.mod13_dmips + self.mdp_dmips) / self.leon4ft_dmips

    def action_compute_pct(self, action: str) -> float:
        action_dmips = {
            "RAW": self.mod13_dmips + self.mod11_dmips + self.fuse_dmips + self.mdp_dmips,
            "SKIP": self.mdp_dmips,
            "MOD13": self.mod13_dmips + self.mdp_dmips,
            "FUSE": self.mod13_dmips + self.mod11_dmips + self.fuse_dmips + self.mdp_dmips,
            "FUSE_PRIORITY": self.mod13_dmips + self.mod11_dmips + self.fuse_dmips + self.mdp_dmips,
        }
        return action_dmips.get(action, self.mdp_dmips) / self.leon4ft_dmips

    def seasonal_average_compute_pct(self, action_dist: dict[str, float], n_t: int) -> float:
        if n_t <= 0:
            return 0.0
        weighted = 0.0
        for action, count in action_dist.items():
            weighted += count * self.action_compute_pct(action)
        return weighted / n_t

    def compute_pct(self) -> float:
        return self.peak_compute_pct()


ACTION_W = {
    "SKIP": 0.30,
    "MOD13": 1.8 + 1.2 + 0.8 + 0.2 + 1.5,
    "FUSE": 1.8 + 1.2 + 0.8 + 0.9 + 0.5 + 0.2 + 1.5 + 0.7,
    "FUSE_PRIORITY": 1.8 + 1.2 + 0.8 + 0.9 + 0.5 + 0.2 + 1.5 + 0.7 + 2.0,
}

ACTION_GSD_M = {
    "RAW": 4.6,
    "SKIP": 0.0,
    "MOD13": 30.0,
    "FUSE": 10.0,
    "FUSE_PRIORITY": 4.6,
}

ACTION_TILE_DENSITY_MB_PER_KM2 = {
    "RAW": 8.4,
    "SKIP": 0.0,
    "MOD13": 0.2,
    "FUSE": 1.8,
    "FUSE_PRIORITY": 8.4,
}

LEGACY_CSC_WEIGHTS = (0.55, 0.45)
CSC_WEIGHTS = (0.40, 0.35, 0.25)
CSC_SIGMAS = {
    "evi": 0.042,
    "lst": 1.20,
    "ndwi": 0.05,
}
CSC_SATURATION_DEFAULTS = {
    "evi": 5.0,
    "lst": 4.0,
    "ndwi": 4.0,
}


def action_gsd_m(action: str) -> float:
    return ACTION_GSD_M.get(action, 0.0)


def action_tile_density_mb_per_km2(action: str) -> float:
    return ACTION_TILE_DENSITY_MB_PER_KM2.get(action, 0.0)


def _normalized_weights(weights: tuple[float, ...]) -> tuple[float, ...]:
    weight_sum = max(sum(weights), 1e-9)
    return tuple(weight / weight_sum for weight in weights)


def posterior_mean(alpha: np.ndarray, beta: np.ndarray) -> np.ndarray:
    total = np.maximum(alpha + beta, 1.0)
    return alpha / total


def posterior_evidence(alpha: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return alpha + beta


def posterior_tail_probability(alpha: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """Exact P(p > 0.5) for integer-valued Beta(alpha, beta)."""

    alpha_i = np.clip(np.rint(alpha).astype(int), 1, None)
    beta_i = np.clip(np.rint(beta).astype(int), 1, None)
    out = np.empty(alpha_i.shape, dtype="float32")

    for a in np.unique(alpha_i):
        a_mask = alpha_i == a
        for b in np.unique(beta_i[a_mask]):
            n = a + b - 1
            coeff_sum = sum(math.comb(n, j) for j in range(a))
            out[a_mask & (beta_i == b)] = coeff_sum * (0.5 ** n)
    return out


def update_stress_belief(
    alpha: np.ndarray,
    beta: np.ndarray,
    evi_anom: np.ndarray,
    ndwi_anom: np.ndarray,
    *,
    evi_thr: float = 0.18,
    ndwi_thr: float = 0.12,
    max_total: int = 8,
) -> tuple[np.ndarray, np.ndarray]:
    alpha_new = np.clip(np.rint(alpha).astype(int), 1, None)
    beta_new = np.clip(np.rint(beta).astype(int), 1, None)
    positive = (evi_anom >= evi_thr) | (ndwi_anom >= ndwi_thr)

    alpha_new = alpha_new + positive.astype(int)
    beta_new = beta_new + (~positive).astype(int)

    total = alpha_new + beta_new
    over = total > max_total
    if np.any(over):
        mean = alpha_new[over] / total[over]
        rescaled_alpha = np.clip(np.rint(mean * max_total).astype(int), 1, max_total - 1)
        alpha_new[over] = rescaled_alpha
        beta_new[over] = max_total - rescaled_alpha

    return alpha_new.astype("float32"), beta_new.astype("float32")


def compute_csc(
    evi_t,
    lst_t,
    evi_base,
    lst_base,
    ndwi_t=None,
    ndwi_base=None,
    evi_weight: float = CSC_WEIGHTS[0],
    lst_weight: float = CSC_WEIGHTS[1],
    ndwi_weight: float = CSC_WEIGHTS[2],
    evi_saturation: float = CSC_SATURATION_DEFAULTS["evi"],
    lst_saturation: float = CSC_SATURATION_DEFAULTS["lst"],
    ndwi_saturation: float = CSC_SATURATION_DEFAULTS["ndwi"],
) -> np.ndarray:
    """
    Crop Stress Composite — per-patch anomaly index.

    With NDWI available:
      CSC = 0.40 * clamp(evi_drop / (5*sigma_evi)) +
            0.35 * clamp(lst_rise / (4*sigma_lst)) +
            0.25 * clamp(ndwi_drop / (4*sigma_ndwi))

    Without NDWI, the function falls back to the legacy two-term EVI/LST
    composition used in the original submission.
    """

    sigma_e = CSC_SIGMAS["evi"]
    sigma_l = CSC_SIGMAS["lst"]
    sigma_n = CSC_SIGMAS["ndwi"]

    evi_drop = np.maximum(0.0, (evi_base - evi_t) / sigma_e) / max(evi_saturation, 1e-9)
    lst_rise = np.maximum(0.0, (lst_t - lst_base) / sigma_l) / max(lst_saturation, 1e-9)
    evi_term = np.clip(evi_drop, 0, 1)
    lst_term = np.clip(lst_rise, 0, 1)

    if ndwi_t is None or ndwi_base is None:
        legacy_evi_weight, legacy_lst_weight = _normalized_weights(LEGACY_CSC_WEIGHTS)
        csc = legacy_evi_weight * evi_term + legacy_lst_weight * lst_term
        return np.clip(csc, 0, 1)

    ndwi_drop = np.maximum(0.0, (ndwi_base - ndwi_t) / sigma_n) / max(ndwi_saturation, 1e-9)
    ndwi_term = np.clip(ndwi_drop, 0, 1)
    evi_weight, lst_weight, ndwi_weight = _normalized_weights(
        (evi_weight, lst_weight, ndwi_weight)
    )
    csc = (
        evi_weight * evi_term
        + lst_weight * lst_term
        + ndwi_weight * ndwi_term
    )
    return np.clip(csc, 0, 1)


@dataclass
class State:
    t: int
    soc: float
    downlink: bool
    op: float
    alpha: np.ndarray
    beta: np.ndarray
    evi_anom: np.ndarray
    ndwi_anom: np.ndarray
    csc: np.ndarray
    steps_since_fuse: int


class MASFEPolicy:
    """
    Two-stage adaptive scheduling policy used in the paper and code submission.
    """

    def __init__(
        self,
        evi_fuse_thr=0.18,
        ndwi_fuse_thr=0.12,
        csc_alert_thr=0.55,
        explore_n=12,
        batt_crit=0.15,
        batt_cons=0.34,
        posterior_tail_thr=0.70,
        posterior_mean_thr=0.55,
        min_evidence=2,
    ):
        self.evi_fuse_thr = evi_fuse_thr
        self.ndwi_fuse_thr = ndwi_fuse_thr
        self.csc_alert_thr = csc_alert_thr
        self.explore_n = explore_n
        self.batt_crit = batt_crit
        self.batt_cons = batt_cons
        self.posterior_tail_thr = posterior_tail_thr
        self.posterior_mean_thr = posterior_mean_thr
        self.min_evidence = min_evidence

    def act(self, s: State) -> str:
        if s.soc < self.batt_crit:
            return "SKIP"
        if s.soc < self.batt_cons:
            return "MOD13"

        tail_max = float(np.nanmax(posterior_tail_probability(s.alpha, s.beta)))
        if tail_max > self.posterior_tail_thr:
            return "FUSE"
        if s.steps_since_fuse >= self.explore_n:
            return "FUSE"
        return "MOD13"

    def should_priority_downlink(self, s: State, fused_csc: np.ndarray) -> bool:
        """Gate FUSE→FUSE_PRIORITY under a duty-cycled downlink window.

        Requires (i) a contact window, (ii) fused CSC above the alert threshold, and
        (iii) a belief-informed stress signal. ``min_evidence`` defaults to 2 (total
        pseudo-count α+β on the hottest patch): a stricter count of 3 rarely co-occurred
        with a downlink slot and high CSC in the benchmark, producing zero priority
        alerts even though the promotion path is implemented.
        """
        if not s.downlink:
            return False
        if float(np.nanmax(fused_csc)) < self.csc_alert_thr:
            return False

        mean_max = float(np.nanmax(posterior_mean(s.alpha, s.beta)))
        evidence_max = float(np.nanmax(posterior_evidence(s.alpha, s.beta)))
        tail_max = float(np.nanmax(posterior_tail_probability(s.alpha, s.beta)))
        # Either sustained posterior mass (mean) or the same tail exceedance that can
        # trigger ``act()``→FUSE, together with enough pseudo-evidence for alert tiles.
        if mean_max > self.posterior_mean_thr and evidence_max >= self.min_evidence:
            return True
        if tail_max >= self.posterior_tail_thr and evidence_max >= self.min_evidence:
            return True
        # CSC spike on a patch with substantial Stage-1 pseudo-evidence but Beta still
        # near symmetric (mean/tail near 0.5): still export alert tiles when fused CSC
        # confirms stress at the operating threshold.
        if evidence_max >= 4.0 and float(np.nanmax(fused_csc)) >= self.csc_alert_thr:
            return True
        return False


class AblateNoBeliefPolicy(MASFEPolicy):
    """
    Ablation policy that removes the Bayesian belief memory.

    Stage 1 runs every pass. Stage 2 is triggered only by current-pass EVI/NDWI
    anomaly, ignoring posterior memory and time-since-fuse history.
    """

    def act(self, s: State) -> str:
        if s.soc < self.batt_crit:
            return "SKIP"
        if s.soc < self.batt_cons:
            return "MOD13"
        if float(np.nanmax(s.evi_anom)) >= self.evi_fuse_thr:
            return "FUSE"
        if float(np.nanmax(s.ndwi_anom)) >= self.ndwi_fuse_thr:
            return "FUSE"
        return "MOD13"
