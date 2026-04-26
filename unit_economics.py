"""Compatibility wrapper for :mod:`cascade.economics`."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


if __name__ == "__main__":
    runpy.run_module("cascade.economics", run_name="__main__")
else:
    from cascade.economics import *  # noqa: F401,F403
