from __future__ import annotations

import importlib


def test_root_wrappers_reexport_canonical_symbols() -> None:
    cascade_core = importlib.import_module("cascade_core")
    canonical = importlib.import_module("cascade.core")

    assert cascade_core.CASCADEPolicy is canonical.CASCADEPolicy
    assert cascade_core.Config is canonical.Config


def test_legacy_masfe_wrappers_still_resolve() -> None:
    masfe_core = importlib.import_module("masfe_core")
    masfe_simulation = importlib.import_module("masfe_simulation")
    canonical_core = importlib.import_module("cascade.core")
    canonical_simulation = importlib.import_module("cascade.simulation")

    assert masfe_core.MASFEPolicy is canonical_core.CASCADEPolicy
    assert masfe_simulation.run_monte_carlo is canonical_simulation.run_monte_carlo
