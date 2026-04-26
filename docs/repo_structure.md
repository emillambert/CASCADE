# CASCADE Repository Structure

## Layout

- `src/cascade/`: canonical package code
- `scripts/`: convenience entrypoints for build/export workflows
- `paper/`: submission source, compiled PDF, bibliography, and paper-bound figures
- `artifacts/`: tracked release-grade outputs used for validation and review
- `build/`: transient local generation outputs
- `data/cache/`: ignored AppEEARS / MODIS cache
- `tests/`: unit, integration, validation, and accepted fixtures

## Compatibility policy

- Canonical imports use `cascade.*`
- Root-level `cascade_*.py`, `csc_calibration.py`, `real_modis_replay.py`, and `unit_economics.py` remain as thin compatibility wrappers
- Legacy `masfe_*` modules remain deprecated shims only

## Output policy

- Generators write to `build/` by default
- `scripts/export_release_artifacts.py` promotes selected outputs into `artifacts/` and `paper/figures/`
- Validation tests compare `artifacts/` against `tests/fixtures/accepted/`

