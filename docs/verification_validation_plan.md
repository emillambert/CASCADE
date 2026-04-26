# CASCADE Verification and Validation Plan

## Intended Use

CASCADE is intended to evaluate an onboard crop-stress scheduling policy across:

- a synthetic Monte Carlo benchmark in `cascade_simulation.py`
- a real-scene offline replay workflow in `real_modis_replay.py`
- a rollout economics model in `unit_economics.py`

The automated checks below are designed to build confidence in code correctness, seeded pipeline behavior, and the stability of published reference outputs. They do not replace live Earthdata replay runs or other external validation activities.

## Verification Strategy

The test harness mirrors the SVV split between code verification, calculation/system verification, and validation.

- Code verification:
  - `tests/unit/test_cascade_core.py`
  - `tests/unit/test_csc_calibration.py`
  - `tests/unit/test_unit_economics.py`
  - Focus: deterministic helper math, threshold logic, belief updates, CSC computation, calibration bounds/ranking/promotion logic, and economics calculations.
- Calculation and system verification:
  - `tests/integration/test_simulation_pipeline.py`
  - `tests/integration/test_replay_pipeline.py`
  - `tests/integration/test_csc_calibration_pipeline.py`
  - Focus: seeded synthetic datasets, pipeline schemas, action transitions, replay bookkeeping, deterministic calibration splits, calibration artifact writing, and plot-writer smoke tests.
- Offline validation:
  - `tests/validation/test_accepted_baselines.py`
  - Focus: regression against accepted reference artifacts derived from the checked-in outputs used in the paper and README, including the promoted CSC calibration summary.

## Automated Test Matrix

| Layer | Scope | Main checks | Default run |
| --- | --- | --- | --- |
| Unit | Core policy, calibration, and economics helpers | clipping, normalization, posterior math, threshold behavior, calibration bounds/ranking, break-even logic | Yes |
| Integration | Simulator, replay, and calibration behavior | deterministic dataset generation, action distributions, alert bookkeeping, split construction, artifact schema checks | Yes |
| Slow integration | Plot-writer smoke tests | image creation to temporary directories | No, marked `slow` |
| Validation | Accepted published outputs | simulation headline metrics, ROC sweep, calibration summary, replay anchors, economics summary | No, marked `validation` |

## Acceptance Criteria

- `python -m pytest -m "not slow and not validation"` passes in a routine development environment.
- `python -m pytest` passes in an environment with all required optional dependencies installed.
- Core verification tests confirm:
  - action metadata and compute helpers stay internally consistent
  - posterior and belief-update helpers produce expected values
  - CSC outputs remain clipped to `[0, 1]` and preserve fallback behavior
  - CSC calibration helpers enforce weight/saturation/threshold bounds and deterministic ranking logic
  - policy thresholds keep the intended `SKIP` / `MOD13` / `FUSE` / `FUSE_PRIORITY` behavior
- Integration tests confirm:
  - seeded data generation is deterministic
  - CASCADE remains more efficient than raw downlink on small seeded cases
  - reduced Monte Carlo and ROC runs produce the expected schema and trend direction
  - replay bookkeeping preserves the warmup, fusion-mode reporting, fallback, priority-alert, and cloud-decay behavior
  - CSC calibration produces deterministic split definitions and writes the expected artifact set on reduced runs
- Validation tests confirm the checked-in outputs still match accepted baselines unless intentionally updated, including the promoted calibration summary.

## Manual External Validation

The following steps remain manual because they depend on larger runtime costs, optional geospatial tooling, or external credentials:

1. Create a clean virtual environment and install `requirements.txt` plus `requirements-dev.txt`.
2. Rerun `python csc_calibration.py` and review `build/calibration/calibration_summary.json`.
3. If the selected candidate is promoted into `cascade_core.py`, rerun `python cascade_simulation.py`.
4. Rerun `python unit_economics.py`.
5. Optionally rerun `python real_modis_replay.py ...` when cached MODIS data or valid Earthdata credentials are available; use `--require-full-fusion --force-download` when the goal is to refresh the canonical NDWI-complete replay anchor rather than reusing a fallback cache.
6. If published outputs are intentionally changed, review the new artifacts and then update the accepted fixtures under `tests/fixtures/accepted/`.

## Limits

- The offline validation layer checks stability against accepted artifacts, not absolute truth.
- The automated suite intentionally avoids live AppEEARS access.
- Replay geospatial I/O is only lightly smoke-tested indirectly; full external replay verification still requires the manual workflow above.
- Replay artifacts now report `fusion_mode`, `ndwi_windows`, and `fallback_windows`, but the automated suite still cannot promote a fallback cache into a full-NDWI cache without Earthdata credentials.
- The CSC calibration step is still an offline synthetic calibration pass, not a replacement for crop-specific labeled agronomic tuning or flight-like hardware validation.
