# MASFE

MASFE (Multi-Algorithm Scheduling and Fusion Engine) is a NASA Space-to-Soil submission that treats crop-stress monitoring as an onboard scheduling problem instead of a passive downlink problem. This repository contains the 100-seed hosted-payload Monte Carlo benchmark, a real-scene MODIS replay over Westlands/Firebaugh, the five-year rollout economics model, and the final submission paper. The current technical version uses a capped Beta-posterior belief state, a three-channel CSC built from `EVI + LST + NDWI`, and a tiered resolution pyramid that keeps most passes at coarse screening while reserving native evidence tiles for confirmed alerts.

## Verified Headline Metrics

| Downlink reduction vs raw | Disease-event recall | False-positive rate | CPU utilization (peak / seasonal) |
| ---: | ---: | ---: | ---: |
| **99.3%** | **100.0%** | **1.6%** | **92.5% / 49.2%** |

Compared with always-on onboard fusion, MASFE now also reduces total transmitted volume because the Bayesian belief gate leaves most passes at `30 m` screening; the adaptive gain is both volumetric and operational: lower energy draw, fewer unnecessary confirmation passes, and explicit priority evidence only when the posterior and fused CSC agree.

Tiered resolution pyramid used by the code and paper:

- `MOD13` screen: `30 m`, about `0.2 MB/km²`
- `FUSE` confirmation: `10 m`, about `1.8 MB/km²`
- `FUSE_PRIORITY` evidence: `4.6 m` native, about `8.4 MB/km²` raw or `3.36 MB/km²` delivered at the planning `2.5:1` CCSDS compression assumption

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

The real-scene replay uses official AppEEARS subsets of `MOD13A1.061` EVI plus QA, `MOD11A1.061` daytime LST plus QC, and `MOD09A1.061` surface reflectance for NDWI over the Westlands / Firebaugh AOI in California. It is framed as scheduler validation on official MODIS scenes, not as a labeled disease benchmark.

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

If the cache or AppEEARS bundle includes `MOD09A1.061`, the replay will derive median clear-sky NDWI over the same composite window and use the full `EVI + LST + NDWI` CSC. If you point the script at an older cached bundle that contains only `MOD13A1` and `MOD11A1`, it will still run and will explicitly fall back to the legacy `EVI + LST` fusion for those steps instead of failing.

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
- tracked cached artifact note: the checked-in 2024 replay rows currently show `EVI/LST fallback` because the local tracked bundle predates the MOD09 extension

## For Judges — 5-Minute Evaluation Path

1. Read the summary and headline metrics above.
2. Open `outputs/roc.png` to see the tunable operating point behind the published threshold.
3. Run `pip install -r requirements.txt && python masfe_simulation.py` to reproduce the synthetic benchmark end to end.
4. Open `outputs/real_modis/westlands_ca_2024-06-01_2024-10-31/replay_summary.png` and `outputs/real_modis/westlands_ca_2024-06-01_2024-10-31/replay_metrics.json` to confirm the real-scene replay artifacts.

## Repository Layout

- `masfe_core.py`: shared CSC computation, Beta-posterior belief model, resolution metadata, and deterministic policy logic.
- `masfe_simulation.py`: 100-seed Monte Carlo benchmark with ROC, ablation, CSC sweep, utilization reporting, and the `EVI + LST + NDWI` synthetic benchmark.
- `real_modis_replay.py`: AppEEARS-backed MODIS replay workflow for the Westlands AOI with MOD09 NDWI support and EVI/LST fallback.
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
