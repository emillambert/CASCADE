# Reproducibility

This page gives the shortest path from a fresh checkout to the reviewer-visible
CASCADE results. The target environment is Python `>=3.10,<3.13`.

## Clean install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

The `Makefile` uses `.venv/bin/python` when it exists and falls back to
`python3`; override with `PYTHON=/path/to/python` if needed.

## Fast commands

| Command | What it checks or regenerates |
| --- | --- |
| `make test` | Runs `python -m pytest -q`. |
| `python -m cascade.simulate` | Runs the reviewer-fast benchmark path and skips slow additional ablations by default. |
| `python -m cascade.replay --year 2014` | Reads the tracked 2014 Westlands replay artifact when present. |
| `python -m cascade.replay --year 2024` | Reads the tracked 2024 Westlands replay artifact when present. |
| `make repro-2014` | Runs the benchmark, then the 2014 paper-anchor replay. |
| `make repro-2024` | Runs the benchmark, then the 2024 paper-anchor replay. |
| `make figures` | Promotes selected regenerated outputs into `artifacts/` and `paper/figures/`. |

Expected regenerated benchmark outputs land in `build/benchmark/`. Expected
tracked reviewer outputs are already under `artifacts/benchmark/`,
`artifacts/replay/`, `artifacts/calibration/`, and `artifacts/economics/`.

## Offline vs live replay

The reviewer replay command uses tracked artifacts by default, which makes the
paper anchors reproducible without Earthdata credentials:

```bash
python -m cascade.replay --year 2014
python -m cascade.replay --year 2024
```

To force a live replay, use the lower-level AppEEARS workflow after configuring
Earthdata credentials:

```bash
python real_modis_replay.py --help
```

Live replay writes to `build/replay/` and may reuse `data/cache/`. It depends on
NASA AppEEARS availability, local geospatial dependencies, and credentials, so
it is intentionally separate from the default offline review path.

## Artifact promotion

Use `make figures` only after reviewing regenerated files in `build/`. The
promotion script copies selected benchmark, calibration, economics, replay, and
paper-figure outputs into their tracked locations. If promoted metrics change,
update the accepted fixtures in `tests/fixtures/accepted/` in the same review.
