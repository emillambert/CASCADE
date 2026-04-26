"""Deprecated compatibility wrapper for :mod:`cascade.core`.

New code should import from ``cascade.core`` and use ``CASCADEPolicy``. This
module remains so older notebooks, tests, and reviewer commands that import
``masfe_core`` continue to work during the CASCADE rename.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade_core import *  # noqa: F401,F403
from cascade.core import CASCADEPolicy as MASFEPolicy  # noqa: F401
