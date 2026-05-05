# Repository Structure

CASCADE is organized as a small Python package plus reviewer-facing scripts,
tracked outputs, tests, and the paper bundles.

## Main directories

| Path | Purpose |
| --- | --- |
| `src/cascade/` | Canonical package code for the policy, simulator, replay, calibration, economics, and path helpers. |
| `cascade/` | Source-tree import shim so `python -m cascade.*` works without an editable install. |
| `scripts/` | Convenience entrypoints for benchmark, replay, calibration, economics, and artifact export workflows. |
| `examples/` | Short SoftwareX-facing examples that run from tracked artifacts by default. |
| `tests/` | Unit, integration, validation, and canonical-claim tests. |
| `tests/fixtures/accepted/` | Accepted baseline JSON used by validation tests. |
| `artifacts/` | Tracked release-grade outputs used by the README, paper, and validation tests. |
| `build/` | Local regenerated outputs. Treat this as transient unless files are intentionally promoted. |
| `data/cache/` | Local AppEEARS/MODIS cache. This is environment-specific and not required for offline review. |
| `papers/` | Manuscript bundles, with one subfolder per paper and separate manuscript/script/submission folders. |
| `archive/` | Reserved for retired compatibility files that should remain discoverable but outside active workflows. |
| `docs/` | Concise reviewer references. The README remains the hub. |

## Canonical imports

New code should import from `cascade.*`, for example:

```python
from cascade.core import CASCADEPolicy, compute_csc
from cascade.replay import replay
```

Root-level files such as `cascade_core.py`, `cascade_simulation.py`,
`csc_calibration.py`, `real_modis_replay.py`, and `unit_economics.py` are
supported compatibility wrappers for reviewer commands and older CASCADE import
paths. The MASFE-era wrappers are retired and archived under
`archive/legacy-root-scripts/`.

## Output policy

Generators write to `build/` first. The tracked `artifacts/` directory contains
the release outputs that are safe for offline review and regression checks.
When outputs are intentionally refreshed, `scripts/export_release_artifacts.py`
promotes selected files from `build/` into `artifacts/` and the paper figure folders.

Validation tests compare the tracked outputs against accepted fixtures, so a
change to `artifacts/` should be intentional and reviewed alongside the
matching fixture update.

## Paper source

The NASA Space-to-Soil paper source of truth is
`papers/nasa-space-to-soil/manuscript/EmilLambert_CASCADE.tex`; the compiled PDF is
`papers/nasa-space-to-soil/manuscript/EmilLambert_CASCADE.pdf`. The paper may contain more
narrative context than the docs, but the README and tracked artifacts are the
fastest review path.

The SoftwareX bundle lives in `papers/softwarex/`: source files in
`manuscript/`, generated paper figures in `figures/`, helper scripts in
`scripts/`, and journal submission materials in `submission/`. It is
intentionally separate from the technical disclosure paper so the SoftwareX
manuscript can follow the journal template and word-limit gates without
disturbing the challenge-era source.
