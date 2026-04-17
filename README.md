# MASFE

MASFE (Multi-Algorithm Scheduling and Fusion Engine) is a NASA Space-to-Soil submission that treats crop-stress monitoring as an onboard scheduling problem instead of a passive downlink problem. This repository contains the 100-seed hosted-payload Monte Carlo benchmark, a real-scene MODIS replay over Westlands/Firebaugh, the five-year rollout economics model, and the final submission paper. In the current synthetic benchmark, MASFE reduces downlink by `96.4%` versus a raw-dump baseline, saves `20.6%` payload energy, retains `100.0%` disease-event recall, and holds false-positive rate to `1.4%`.

## Verified Headline Metrics

| Downlink reduction vs raw | Disease-event recall | False-positive rate | CPU utilization (peak / seasonal) |
| ---: | ---: | ---: | ---: |
| **96.4%** | **100.0%** | **1.4%** | **92.5% / 87.5%** |

MASFE matches the fixed-onboard baseline on total downlink volume because both policies already compress the sensing pipeline onboard; the adaptive gain is payload-energy savings, priority ordering, and compute-margin management.

![Westlands replay summary](outputs/real_modis/westlands_ca_2024-06-01_2024-10-31/replay_summary.png)

## Quick Start

Create a fresh environment, install the verified pinned dependencies, and run the synthetic benchmark:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python masfe_simulation.py
```

After a successful run, the main judge-facing artifacts are refreshed at:

- `outputs/simulation_metrics.json`
- `outputs/roc.png`
- `outputs/roc_metrics.json`
- `outputs/ablation_metrics.json`
- `outputs/csc_sensitivity.json`

Optional economics refresh:

```bash
python unit_economics.py
```

This repository has been verified in a fresh virtual environment with the exact versions pinned in `requirements.txt`.

## Real MODIS Replay

The real-scene replay uses official AppEEARS subsets of `MOD13A1.061` EVI plus QA and `MOD11A1.061` daytime LST plus QC over the Westlands / Firebaugh AOI in California. It is framed as scheduler validation on official MODIS scenes, not as a labeled disease benchmark.

Activate the environment:

```bash
source .venv/bin/activate
```

Set Earthdata credentials safely:

```bash
export EARTHDATA_USERNAME='your-username'
read -s EARTHDATA_PASSWORD
export EARTHDATA_PASSWORD
```

Test the AppEEARS login before launching a long replay:

```bash
curl -i -u "$EARTHDATA_USERNAME:$EARTHDATA_PASSWORD" \
  -X POST https://appeears.earthdatacloud.nasa.gov/api/login
```

Run the paper-anchor 2024 replay:

```bash
python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-10-31 \
  --cache-dir data/modis_cache \
  --disable-fallback
```

Optional second-season extension:

```bash
python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2023-05-01 \
  --end 2023-10-31 \
  --cache-dir data/modis_cache \
  --disable-fallback
```

If you already have an AppEEARS download, reuse the bundle directly instead of authenticating again:

```bash
python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-10-31 \
  --bundle-dir /absolute/path/to/masfe-westlands-2024/
```

```bash
python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-10-31 \
  --bundle-zip /absolute/path/to/masfe-westlands-2024.zip
```

Tracked replay anchor used in the paper:

- `7` valid windows after a `3`-window warmup
- `1` confirmed `FUSE_PRIORITY` window
- first and peak alert date: `2024-07-27`
- mean valid coverage: `0.995`

## For Judges — 5-Minute Evaluation Path

1. Read the summary and headline metrics above.
2. Open `outputs/roc.png` to see the tunable operating point behind the published threshold.
3. Run `pip install -r requirements.txt && python masfe_simulation.py` to reproduce the synthetic benchmark end to end.
4. Open `outputs/real_modis/westlands_ca_2024-06-01_2024-10-31/replay_summary.png` and `outputs/real_modis/westlands_ca_2024-06-01_2024-10-31/replay_metrics.json` to confirm the real-scene replay artifacts.

## Repository Layout

- `masfe_core.py`: shared CSC computation, SWAP model, and deterministic policy logic.
- `masfe_simulation.py`: 100-seed Monte Carlo benchmark with ROC, ablation, CSC sweep, and utilization reporting.
- `real_modis_replay.py`: AppEEARS-backed MODIS replay workflow for the Westlands AOI.
- `unit_economics.py`: five-year SJV-to-global rollout model.
- `outputs/simulation_metrics.json`: paper-facing synthetic benchmark metrics written by `masfe_simulation.py`.
- `outputs/roc.png` and `outputs/roc_metrics.json`: alert-threshold sweep behind the published operating point.
- `outputs/ablation_metrics.json`: matched-recall comparison to the no-belief ablation.
- `outputs/csc_sensitivity.json`: CSC robustness sweep over weights and saturation constants.
- `outputs/unit_economics/unit_economics.json`: detailed low/base/high rollout outputs and break-even summary.
- `outputs/unit_economics/unit_economics_table.tex`: paper-ready LaTeX rendering of the economics table.
- `outputs/real_modis/westlands_ca_2024-06-01_2024-10-31/`: tracked replay artifacts used in the paper.
- `docs/unit_economics.md`: supporting explanation of the rollout model and assumptions.
- `paper/report.tex`: submission paper source of truth.
- `paper/EmilLambert_MASFE.pdf`: compiled submission PDF.

## License

Released under the MIT License. See `LICENSE`.
