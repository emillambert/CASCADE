"""Centralized repo-relative paths for CASCADE."""

from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
REPO_ROOT = SRC_DIR.parent

ARTIFACTS_DIR = REPO_ROOT / "artifacts"
ARTIFACTS_BENCHMARK_DIR = ARTIFACTS_DIR / "benchmark"
ARTIFACTS_CALIBRATION_DIR = ARTIFACTS_DIR / "calibration"
ARTIFACTS_REPLAY_DIR = ARTIFACTS_DIR / "replay"
ARTIFACTS_ECONOMICS_DIR = ARTIFACTS_DIR / "economics"

BUILD_DIR = REPO_ROOT / "build"
BUILD_BENCHMARK_DIR = BUILD_DIR / "benchmark"
BUILD_CALIBRATION_DIR = BUILD_DIR / "calibration"
BUILD_REPLAY_DIR = BUILD_DIR / "replay"
BUILD_ECONOMICS_DIR = BUILD_DIR / "economics"

PAPER_DIR = REPO_ROOT / "paper"
PAPER_FIGURES_DIR = PAPER_DIR / "figures"
PAPER_SCRIPTS_DIR = PAPER_DIR / "scripts"

DOCS_DIR = REPO_ROOT / "docs"
DATA_DIR = REPO_ROOT / "data"
DATA_FIXTURES_DIR = DATA_DIR / "fixtures"
DATA_CACHE_DIR = DATA_DIR / "cache"

TESTS_DIR = REPO_ROOT / "tests"
TEST_FIXTURES_DIR = TESTS_DIR / "fixtures"
TEST_ACCEPTED_FIXTURES_DIR = TEST_FIXTURES_DIR / "accepted"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

