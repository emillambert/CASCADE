# Repository Structure

CASCADE is organized as a small Python package plus reviewer-facing scripts,
tracked outputs, tests, and the paper bundle.

## Main directories

| Path | Purpose |
| --- | --- |
| `src/cascade/` | Canonical package code for the policy, simulator, replay, calibration, economics, and path helpers. |
| `cascade/` | Source-tree import shim so `python -m cascade.*` works without an editable install. |
| `scripts/` | Convenience entrypoints for benchmark, replay, calibration, economics, and artifact export workflows. |
| `tests/` | Unit, integration, validation, and canonical-claim tests. |
| `tests/fixtures/accepted/` | Accepted baseline JSON used by validation tests. |
| `artifacts/` | Tracked release-grade outputs used by the README, paper, and validation tests. |
| `build/` | Local regenerated outputs. Treat this as transient unless files are intentionally promoted. |
| `data/cache/` | Local AppEEARS/MODIS cache. This is environment-specific and not required for offline review. |
| `paper/` | LaTeX paper source, compiled PDF, bibliography, and paper-bound figures. |
| `docs/` | Concise reviewer references. The README remains the hub. |

## Canonical imports

New code should import from `cascade.*`, for example:

```python
from cascade.core import CASCADEPolicy, compute_csc
from cascade.replay import replay
```

Root-level files such as `cascade_core.py`, `cascade_simulation.py`,
`csc_calibration.py`, `real_modis_replay.py`, and `unit_economics.py` are
compatibility wrappers. The legacy `masfe_*` modules are deprecated shims kept
so older notebooks and reviewer commands still resolve.

## Output policy

Generators write to `build/` first. The tracked `artifacts/` directory contains
the release outputs that are safe for offline review and regression checks.
When outputs are intentionally refreshed, `scripts/export_release_artifacts.py`
promotes selected files from `build/` into `artifacts/` and `paper/figures/`.

Validation tests compare the tracked outputs against accepted fixtures, so a
change to `artifacts/` should be intentional and reviewed alongside the
matching fixture update.

## Paper source

The paper source of truth is `paper/EmilLambert_CASCADE.tex`; the compiled PDF
is `paper/EmilLambert_CASCADE.pdf`. The paper may contain more narrative
context than the docs, but the README and tracked artifacts are the fastest
review path.
