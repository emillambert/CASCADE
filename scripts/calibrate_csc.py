# SPDX-License-Identifier: MIT
"""Run the CASCADE CSC calibration workflow."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


if __name__ == "__main__":
    runpy.run_module("cascade.calibration", run_name="__main__")
