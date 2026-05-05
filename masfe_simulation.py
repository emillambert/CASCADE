# SPDX-License-Identifier: MIT
"""Deprecated compatibility wrapper for :mod:`cascade.simulation`.

New code should run ``python cascade_simulation.py`` or import from
``cascade.simulation``. This wrapper preserves the old command path.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.simulation import main


if __name__ == "__main__":
    raise SystemExit(main())
else:
    from cascade_simulation import *  # noqa: F401,F403
    from cascade.core import CASCADEPolicy as MASFEPolicy  # noqa: F401
