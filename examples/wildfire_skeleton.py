# SPDX-License-Identifier: MIT
"""Minimal non-CSC anomaly-index example for SoftwareX reviewers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.core import CASCADEPolicy, State, update_stress_belief  # noqa: E402


def fire_risk_index(ndvi_loss, thermal_rise, moisture_loss):
    terms = (
        0.35 * np.clip(ndvi_loss / 0.25, 0.0, 1.0)
        + 0.35 * np.clip(thermal_rise / 7.0, 0.0, 1.0)
        + 0.30 * np.clip(moisture_loss / 0.20, 0.0, 1.0)
    )
    return np.clip(terms, 0.0, 1.0)


def main() -> int:
    ndvi_loss = np.array([0.03, 0.08, 0.22, 0.31], dtype="float32")
    thermal_rise = np.array([0.4, 1.1, 4.6, 7.4], dtype="float32")
    moisture_loss = np.array([0.01, 0.04, 0.13, 0.18], dtype="float32")

    alpha = np.ones_like(ndvi_loss)
    beta = np.ones_like(ndvi_loss)
    alpha, beta = update_stress_belief(alpha, beta, ndvi_loss, moisture_loss)

    risk = fire_risk_index(ndvi_loss, thermal_rise, moisture_loss)
    policy = CASCADEPolicy(csc_alert_thr=0.62)
    state = State(4, 0.82, True, 0.0, alpha, beta, ndvi_loss, moisture_loss, risk, 3)

    action = policy.act(state)
    priority = policy.should_priority_downlink(state, risk)
    print(f"custom index: wildfire skeleton")
    print(f"peak risk: {float(np.max(risk)):.3f}")
    print(f"action: {action}")
    print(f"priority downlink: {priority}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
