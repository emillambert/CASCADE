# MASFE Verification and Validation Plan

## Intended Use

MASFE is intended to evaluate an onboard crop-stress scheduling policy across:

- a synthetic Monte Carlo benchmark in `masfe_simulation.py`
- a real-scene offline replay workflow in `real_modis_replay.py`
- a rollout economics model in `unit_economics.py`

The automated checks below are designed to build confidence in code correctness, seeded pipeline behavior, and the stability of published reference outputs. They do not replace live Earthdata replay runs or other external validation activities.

## Verification Strategy

The test harness mirrors the SVV split between code verification, calculation/system verification, and validation.

- Code verification:
  - `tests/unit/test_masfe_core.py`
  - `tests/unit/test_unit_economics.py`
  - Focus: deterministic helper math, threshold logic, belief updates, CSC computation, and economics calculations.
- Calculation and system verification:
  - `tests/integration/test_simulation_pipeline.py`
  - `tests/integration/test_replay_pipeline.py`
  - Focus: seeded synthetic datasets, pipeline schemas, action transitions, replay bookkeeping, and plot-writer smoke tests.
- Offline validation:
  - `tests/validation/test_accepted_baselines.py`
  - Focus: regression against accepted reference artifacts derived from the checked-in outputs used in the paper and README.

## Automated Test Matrix

| Layer | Scope | Main checks | Default run |
| --- | --- | --- | --- |
| Unit | Core policy and economics helpers | clipping, normalization, posterior math, threshold behavior, break-even logic | Yes |
| Integration | Simulator and replay pipeline behavior | deterministic dataset generation, action distributions, alert bookkeeping, schema checks | Yes |
| Slow integration | Plot-writer smoke tests | image creation to temporary directories | No, marked `slow` |
| Validation | Accepted published outputs | simulation headline metrics, ROC sweep, replay anchors, economics summary | No, marked `validation` |

## Acceptance Criteria

- `python -m pytest -m "not slow and not validation"` passes in a routine development environment.
- `python -m pytest` passes in an environment with all required optional dependencies installed.
- Core verification tests confirm:
  - action metadata and compute helpers stay internally consistent
  - posterior and belief-update helpers produce expected values
  - CSC outputs remain clipped to `[0, 1]` and preserve fallback behavior
  - policy thresholds keep the intended `SKIP` / `MOD13` / `FUSE` / `FUSE_PRIORITY` behavior
- Integration tests confirm:
  - seeded data generation is deterministic
  - MASFE remains more efficient than raw downlink on small seeded cases
  - reduced Monte Carlo and ROC runs produce the expected schema and trend direction
  - replay bookkeeping preserves the warmup, fallback, priority-alert, and cloud-decay behavior
- Validation tests confirm the checked-in outputs still match accepted baselines unless intentionally updated.

## Manual External Validation

The following steps remain manual because they depend on larger runtime costs, optional geospatial tooling, or external credentials:

1. Create a clean virtual environment and install `requirements.txt` plus `requirements-dev.txt`.
2. Rerun `python unit_economics.py`.
3. Rerun `python masfe_simulation.py`.
4. Optionally rerun `python real_modis_replay.py ...` when cached MODIS data or valid Earthdata credentials are available.
5. If published outputs are intentionally changed, review the new artifacts and then update the accepted fixtures under `tests/fixtures/accepted/`.

## Limits

- The offline validation layer checks stability against accepted artifacts, not absolute truth.
- The automated suite intentionally avoids live AppEEARS access.
- Replay geospatial I/O is only lightly smoke-tested indirectly; full external replay verification still requires the manual workflow above.
