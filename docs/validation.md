# Validation

CASCADE validation is split into fast code checks, integration checks, and
offline regression checks against accepted artifacts. The suite is designed to
protect the paper-facing claims without requiring live AppEEARS access.

## Test layers

| Layer | Location | Purpose |
| --- | --- | --- |
| Unit | `tests/unit/` | Core policy math, CSC computation, calibration helpers, economics calculations, wrappers, and console smoke checks. |
| Integration | `tests/integration/` | Seeded simulator behavior, replay bookkeeping, calibration artifact writing, and reduced pipeline runs. |
| Validation | `tests/validation/` | Regression checks against accepted outputs in `tests/fixtures/accepted/`. |
| Canonical claims | `tests/test_canonical_claims.py` | Direct guardrails for headline replay claims such as the 2014 Westlands anchor. |

Routine local check:

```bash
python -m pytest -q
```

SoftwareX release check:

```bash
python -m pytest -q --cov=src/cascade --cov-fail-under=60
python examples/westlands_replay.py
```

The coverage threshold is applied to the offline package core. The live
AppEEARS adapter in `src/cascade/replay/modis.py` is excluded from the coverage
percentage because it depends on external credentials and service availability;
its parser, masking, output, and replay-bookkeeping helpers are still exercised
by integration tests.

Offline baseline check:

```bash
python -m pytest -m validation
```

CI runs `pytest -q --cov=src/cascade --cov-fail-under=60` across Python 3.10,
3.11, and 3.12 on Linux and macOS using `.github/workflows/ci.yml`.

## What CI protects

The automated suite protects deterministic helper behavior, seeded benchmark
behavior, replay schemas and accounting, compatibility wrappers, and the
accepted JSON outputs used by the README and paper. The validation layer checks
that tracked artifacts still match:

- `artifacts/benchmark/simulation_metrics.json`
- `artifacts/benchmark/roc_metrics.json`
- `artifacts/calibration/calibration_summary.json`
- `artifacts/replay/.../replay_metrics.json`
- `artifacts/economics/unit_economics.json`

The current paper-aligned headline metrics are 99.1% downlink reduction, 38.3%
energy saving, 77.6% downlink reduction vs fixed onboard, 25.4% energy saving
vs fixed onboard, 100.0% recall, and 0.6% false-positive rate.

## Manual validation

The suite does not replace live external validation. These steps remain manual:

- Force a live AppEEARS/MODIS replay with valid Earthdata credentials.
- Review new `build/replay/` maps, timelines, and `replay_metrics.json`.
- Rerun full calibration if CSC defaults are intentionally changed.
- Review any promoted artifact before updating accepted fixtures.
- Check the compiled paper PDF separately for layout, page count, fonts, and
  final submission requirements.

When metrics change intentionally, update the artifact and accepted fixture
together so reviewers can see both the new evidence and the new baseline.
