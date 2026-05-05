# CASCADE

> **Note for NASA Space-to-Soil judges:** the frozen submission version is
> available at the `v1.0.0` release:
> <https://github.com/emillambert/CASCADE/releases/tag/v1.0.0>

[![CI](https://github.com/emillambert/CASCADE/actions/workflows/ci.yml/badge.svg)](https://github.com/emillambert/CASCADE/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)

CASCADE (An Onboard Crop Anomaly Screening, Confirmation, and Alert Downlink Engine) is an open-source Python package for testing onboard Earth-observation triage policies for agricultural drought and crop-stress monitoring.

CASCADE turns crop-stress monitoring into an **onboard scheduling problem**: a Bayesian belief gate drives a finite-horizon MDP-style policy over four actions (**SKIP**, **MOD13**, **FUSE**, **FUSE_PRIORITY**) while fusing MOD13A1 EVI, MOD11A1 LST, and MOD09A1-derived NDWI into a three-channel **Crop Stress Composite (CSC)**. The repository includes the reusable package, offline replay artifacts, validation fixtures, and SoftwareX submission materials.

## Highlights

- **Paper-aligned headline metrics** (100-seed Monte Carlo): **99.1%** downlink reduction, **38.3%** energy saving, **0.6%** FP rate, **92.5% / 49.2%** CPU (peak / seasonal).
- **Real-scene replay anchors** (Westlands Water District, Firebaugh, CA):
  - **2024 quiet season**: peak CSC **`0.412`** vs threshold **`0.615`** → **no** `FUSE_PRIORITY` expected.
  - **2014 D4 drought**: peak CSC **`0.869`**, **`FUSE_PRIORITY` at 6/6 windows** → **`2.1×`** the 2024 peak (**no retuning**).
- **One-command reproducibility**: `make repro-2014`, `make repro-2024`, `make test`.
- **Canonical claims protected by tests**: failing a paper anchor fails CI.

[![A SmallSat That Flags Drought 16 Days Early - NASA Space-to-Soil 2026](https://i.vimeocdn.com/filter/overlay?src0=https%3A%2F%2Fi.vimeocdn.com%2Fvideo%2F2153258640-feae61727b4da89f0391f5507f22403fde3257dead4d2a5b5ed0f517a6525f44-d_295x166%3Fregion%3Dus&src1=http%3A%2F%2Ff.vimeocdn.com%2Fp%2Fimages%2Fcrawler_play.png)](https://vimeo.com/1188883695?share=copy&fl=sv&fe=ci)

[Watch the CASCADE video on Vimeo](https://vimeo.com/1188883695?share=copy&fl=sv&fe=ci)

## Overview

CASCADE is a reusable research-software repository containing:

- **Synthetic benchmark**: a 100-seed Monte Carlo study (ROC sweep + ablations + sensitivity).
- **Real-scene MODIS replay**: AppEEARS-backed replays over the Westlands AOI.
- **CSC calibration**: offline parameter search with accepted calibration fixtures.
- **Economics model**: a rollout model and accepted baseline fixtures.
- **SoftwareX source**: `papers/softwarex/` (submission bundle).
- **Technical disclosure paper**: `papers/nasa-space-to-soil/EmilLambert_CASCADE.tex` and compiled PDF.

## Verified headline metrics (paper numbers)

| vs raw downlink | vs fixed onboard | Recall | FP rate | CPU (peak / seasonal) |
|:---:|:---:|:---:|:---:|:---:|
| **99.1%** downlink reduction<br>**38.3%** energy saving | **77.6%** downlink reduction<br>**25.4%** energy saving | **100.0%** | **0.6%** | **92.5% / 49.2%** |

## Installation

Reviewer target: **Python `>=3.10,<3.13`** (fresh virtual environment).

Install the release package from PyPI once `cascade-eo` is published:

```bash
python -m pip install cascade-eo
```

Install from a source checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The source-tree shim supports `python -m cascade.*` directly from a checkout. If
you want an editable package install as well, run:

```bash
python -m pip install -e .
```

Legacy requirements files remain available for minimal reviewer environments:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Usage (fast path)

Run the SoftwareX worked example. It reads the tracked 2014 Westlands D4 replay
artifact by default, so it does not require Earthdata credentials:

```bash
python examples/westlands_replay.py
```

Minimal package quickstart:

```python
from cascade.replay import replay

metrics = replay(2014)
print(metrics["peak_csc"])
print(metrics["action_distribution"]["FUSE_PRIORITY"])
print(metrics["source"])
```

Run the synthetic benchmark (skips slow “additional ablations” by default):

```bash
python -m cascade.simulate
```

Run the paper-anchor replays. These prefer tracked artifacts when present, so
they work offline and return the same JSON payloads used by tests:

```bash
python -m cascade.replay --year 2014
python -m cascade.replay --year 2024
```

Run tests:

```bash
python -m pytest -q
```

Run only the accepted-artifact validation checks:

```bash
python -m pytest -m validation
```

## Makefile (judge-friendly)

```bash
make test
make repro-2014
make repro-2024
```

After reviewing regenerated files under `build/`, promote selected outputs into
tracked `artifacts/` and `papers/nasa-space-to-soil/figures/`:

```bash
make figures
```

The Makefile uses `.venv/bin/python` when available and otherwise falls back to `python3`; pass `PYTHON=/path/to/python` to override it.

## Real MODIS replay (Earthdata/AppEEARS)

For live downloads, set Earthdata credentials in `.env` or your shell:

```bash
export EARTHDATA_USERNAME='your-username'
read -s EARTHDATA_PASSWORD
export EARTHDATA_PASSWORD
```

Test AppEEARS login:

```bash
curl -i -u "$EARTHDATA_USERNAME:$EARTHDATA_PASSWORD" \
  -X POST https://appeears.earthdatacloud.nasa.gov/api/login
```

Run the lower-level live replay workflow directly:

```bash
python real_modis_replay.py --help
```

The offline reviewer replay commands above are preferred for quick evaluation;
live replay writes fresh outputs to `build/replay/` and may reuse `data/cache/`.

## Additional workflows

Regenerate CSC calibration outputs:

```bash
python scripts/calibrate_csc.py
```

Regenerate unit-economics outputs:

```bash
python scripts/unit_economics.py
```

## Repository map

- **Package code**: `src/cascade/`
- **SoftwareX example**: `examples/westlands_replay.py`
- **Replay**: `src/cascade/replay/modis.py`
- **Benchmark**: `src/cascade/simulation.py`
- **Calibration**: `src/cascade/calibration.py`
- **Economics**: `src/cascade/economics.py`
- **Tracked outputs**: `artifacts/`
- **Transient outputs**: `build/`
- **SoftwareX paper**: `papers/softwarex/cascade_softwarex.tex`
- **Technical paper**: `papers/nasa-space-to-soil/EmilLambert_CASCADE.tex`

More detail: [docs/repo_structure.md](docs/repo_structure.md)

## Concise docs

- [Repository structure](docs/repo_structure.md)
- [Reproducibility](docs/reproducibility.md)
- [Validation](docs/validation.md)
- [Replay anchors](docs/replay_anchors.md)
- [Unit economics](docs/unit_economics.md)

## For judges — 5-minute evaluation path

1. Read **Highlights** + the **metrics table** above.
2. Open `artifacts/benchmark/roc.png`.
3. Run `make repro-2014` or `make repro-2024` (or `python -m cascade.simulate`).
4. For artifact regression checks, run `python -m pytest -m validation`.
5. Open the tracked replay metrics under `artifacts/replay/` or read [docs/replay_anchors.md](docs/replay_anchors.md).

## Citation

If you use this repository, please cite the tagged release and the SoftwareX
paper when available:

```bibtex
@software{lambert_cascade_2026,
  author = {Lambert, Emil Wes},
  title = {CASCADE: An Onboard Crop Anomaly Screening, Confirmation, and Alert Downlink Engine},
  version = {1.0.0},
  year = {2026},
  url = {https://github.com/emillambert/CASCADE/releases/tag/v1.0.0}
}
```

The SoftwareX DOI and optional Zenodo DOI will be added after acceptance or
release archiving. GitHub also reads the metadata in `CITATION.cff`.

## Support

Questions about CASCADE can be sent to
[e.w.lambert@student.tudelft.nl](mailto:e.w.lambert@student.tudelft.nl) or filed
as GitHub issues.

## License

Released under the **MIT License**. See `LICENSE.txt` for the SoftwareX-required
license file and `LICENSE` for tooling compatibility.
