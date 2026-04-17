"""Shared MASFE policy and hardware primitives.

This module is the single source of truth for the hosted-payload SWAP model,
Crop Stress Composite (CSC) computation, and the deterministic MDP-inspired
policy used by both the synthetic benchmark and the real MODIS replay.
"""

from dataclasses import dataclass

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


def compute_csc(
    evi_t,
    lst_t,
    evi_base,
    lst_base,
    evi_weight: float = 0.55,
    lst_weight: float = 0.45,
    evi_saturation: float = 5.0,
    lst_saturation: float = 4.0,
) -> np.ndarray:
    """
    Crop Stress Composite — per-patch anomaly index.

    CSC = 0.55 * clamp(evi_drop / (5*sigma_evi)) +
          0.45 * clamp(lst_rise / (4*sigma_lst))
    normalized to [0, 1].
    """

    sigma_e = 0.042
    sigma_l = 1.20
    weight_sum = max(evi_weight + lst_weight, 1e-9)
    evi_weight = evi_weight / weight_sum
    lst_weight = lst_weight / weight_sum

    evi_drop = np.maximum(0.0, (evi_base - evi_t) / sigma_e) / max(evi_saturation, 1e-9)
    lst_rise = np.maximum(0.0, (lst_t - lst_base) / sigma_l) / max(lst_saturation, 1e-9)
    csc = evi_weight * np.clip(evi_drop, 0, 1) + lst_weight * np.clip(lst_rise, 0, 1)
    return np.clip(csc, 0, 1)


@dataclass
class State:
    t: int
    soc: float
    downlink: bool
    op: float
    evi_anom: np.ndarray
    csc: np.ndarray
    conf: np.ndarray
    steps_since_fuse: int


class MASFEPolicy:
    """
    Two-stage adaptive scheduling policy used in the paper and code submission.
    """

    def __init__(
        self,
        evi_fuse_thr=0.18,
        csc_alert_thr=0.55,
        explore_n=12,
        batt_crit=0.15,
        batt_cons=0.34,
    ):
        self.evi_fuse_thr = evi_fuse_thr
        self.csc_alert_thr = csc_alert_thr
        self.explore_n = explore_n
        self.batt_crit = batt_crit
        self.batt_cons = batt_cons

    def act(self, s: State) -> str:
        if s.soc < self.batt_crit:
            return "SKIP"
        if s.soc < self.batt_cons:
            return "MOD13"
        if s.csc.max() >= self.csc_alert_thr and s.downlink:
            return "FUSE_PRIORITY"
        if s.evi_anom.max() >= self.evi_fuse_thr:
            return "FUSE"
        if s.csc.max() >= self.csc_alert_thr:
            return "FUSE"
        if s.steps_since_fuse >= self.explore_n:
            return "FUSE"
        return "MOD13"


class AblateNoBeliefPolicy(MASFEPolicy):
    """
    Ablation policy that removes the cached belief state and explores every pass.

    Stage 1 runs every pass. Stage 2 is triggered only by current-pass EVI
    anomaly, ignoring cached CSC and time-since-fuse history.
    """

    def act(self, s: State) -> str:
        if s.soc < self.batt_crit:
            return "SKIP"
        if s.soc < self.batt_cons:
            return "MOD13"
        if s.evi_anom.max() >= self.evi_fuse_thr:
            return "FUSE"
        return "MOD13"
