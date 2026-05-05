# SPDX-License-Identifier: MIT
"""Promote build outputs into tracked artifacts and paper figures."""

from __future__ import annotations

import shutil
import sys
import runpy
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.paths import (
    ARTIFACTS_BENCHMARK_DIR,
    ARTIFACTS_CALIBRATION_DIR,
    ARTIFACTS_ECONOMICS_DIR,
    ARTIFACTS_REPLAY_DIR,
    BUILD_BENCHMARK_DIR,
    BUILD_CALIBRATION_DIR,
    BUILD_ECONOMICS_DIR,
    BUILD_REPLAY_DIR,
    PAPER_FIGURES_DIR,
    SOFTWAREX_FIGURES_DIR,
    SOFTWAREX_SCRIPTS_DIR,
    ensure_dir,
)


BENCHMARK_FILES = (
    "simulation_metrics.json",
    "roc_metrics.json",
    "ablation_metrics.json",
    "csc_sensitivity.json",
    "evi_only_baseline.json",
    "additional_ablations.json",
    "roc.png",
    "roc_baseline_vs_no_ndwi.png",
    "baselines_comparison_table.tex",
)
PAPER_FIGURE_FILES = (
    "action_timeline_2024.pdf",
    "action_timeline_2024.png",
    "action_timeline_2024.svg",
    "additional_ablation_curves.pdf",
    "additional_ablation_curves.png",
    "additional_ablation_curves.svg",
)
REPLAY_WINDOWS = (
    "westlands_ca_2014-06-01_2014-10-31",
    "westlands_ca_2024-06-01_2024-10-31",
)
SOFTWAREX_FIGURE_FILES = (
    (
        PAPER_FIGURES_DIR / "action_timeline_westlands_split.pdf",
        SOFTWAREX_FIGURES_DIR / "Figure_2_westlands_replay.pdf",
    ),
)


def _copy_file(src, dst) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_tree(src, dst) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _render_softwarex_peak_alert_figure() -> None:
    script = SOFTWAREX_SCRIPTS_DIR / "render_peak_alert_figure.py"
    if script.exists():
        runpy.run_path(str(script), run_name="__main__")


def _render_softwarex_architecture_figure() -> None:
    script = SOFTWAREX_SCRIPTS_DIR / "render_architecture_figure.py"
    if script.exists():
        runpy.run_path(str(script), run_name="__main__")


def _render_softwarex_baseline_comparison_figure() -> None:
    script = SOFTWAREX_SCRIPTS_DIR / "render_baseline_comparison_figure.py"
    if script.exists():
        runpy.run_path(str(script), run_name="__main__")


def main() -> None:
    ensure_dir(ARTIFACTS_BENCHMARK_DIR)
    ensure_dir(ARTIFACTS_CALIBRATION_DIR)
    ensure_dir(ARTIFACTS_ECONOMICS_DIR)
    ensure_dir(ARTIFACTS_REPLAY_DIR)
    ensure_dir(PAPER_FIGURES_DIR)
    ensure_dir(SOFTWAREX_FIGURES_DIR)

    for name in BENCHMARK_FILES:
        _copy_file(BUILD_BENCHMARK_DIR / name, ARTIFACTS_BENCHMARK_DIR / name)

    for name in PAPER_FIGURE_FILES:
        _copy_file(BUILD_BENCHMARK_DIR / name, PAPER_FIGURES_DIR / name)

    for path in BUILD_CALIBRATION_DIR.glob("*.json"):
        _copy_file(path, ARTIFACTS_CALIBRATION_DIR / path.name)

    for path in BUILD_ECONOMICS_DIR.iterdir():
        if path.is_file():
            _copy_file(path, ARTIFACTS_ECONOMICS_DIR / path.name)

    for replay_window in REPLAY_WINDOWS:
        _copy_tree(
            BUILD_REPLAY_DIR / replay_window,
            ARTIFACTS_REPLAY_DIR / replay_window,
        )

    for src, dst in SOFTWAREX_FIGURE_FILES:
        _copy_file(src, dst)

    _render_softwarex_architecture_figure()
    _render_softwarex_peak_alert_figure()
    _render_softwarex_baseline_comparison_figure()


if __name__ == "__main__":
    main()
