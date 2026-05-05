from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_root_wrappers_reexport_canonical_symbols() -> None:
    cascade_core = importlib.import_module("cascade_core")
    canonical = importlib.import_module("cascade.core")

    assert cascade_core.CASCADEPolicy is canonical.CASCADEPolicy
    assert cascade_core.Config is canonical.Config


def test_legacy_masfe_wrappers_are_archived() -> None:
    archive = ROOT / "archive" / "legacy-root-scripts"

    assert (archive / "masfe_core.py").is_file()
    assert (archive / "masfe_simulation.py").is_file()
    assert not (ROOT / "masfe_core.py").exists()
    assert not (ROOT / "masfe_simulation.py").exists()
