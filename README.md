# CASCADE

CASCADE (An Onboard Crop Anomaly Screening, Confirmation, and Alert Downlink Engine) is a NASA Space-to-Soil submission that treats crop-stress monitoring as an onboard scheduling problem instead of a passive downlink problem. The scheduler is a Bayesian Beta(α, β) posterior driving a finite-horizon MDP over four actions (SKIP, MOD13, FUSE, FUSE_PRIORITY), fusing MOD13A1 EVI, MOD11A1 LST, and MOD09A1-derived NDWI into a three-channel Crop Stress Composite. The repository contains the 100-seed hosted-payload Monte Carlo benchmark, a real-scene MODIS replay over Westlands/Firebaugh (CA, 2024), the five-year rollout economics model, and the final submission paper.

## Verified Headline Metrics (100-seed Monte Carlo)

| vs raw downlink | vs fixed onboard | Recall | FP rate | CPU (peak / seasonal) |
|:---:|:---:|:---:|:---:|:---:|
| **99.1%** downlink reduction<br>**38.3%** energy saving | **77.6%** downlink reduction<br>**25.4%** energy saving | **100.0%** | **0.6%** | **92.5% / 49.2%** |

The Bayesian belief gate keeps about **81%** of passes at cheap 30 m screening, **17%** at FUSE confirmation, and **~2%** at FUSE_PRIORITY alert export in the 100-seed benchmark — that is what drops seasonal compute from 92.5% (always-on fusion baseline) to 49.2% while preserving full benchmark anomaly-event recall. In the calibrated configuration, the matched-recall no-belief ablation lands at **0.5%** FP instead of **0.6%**, but it drives seasonal compute up to **76.2%** and alert-tile downlink up by roughly **4.3x**; the posterior is load-bearing as a scheduler.

Priority evidence tiles are compressed onboard via CCSDS 122.0 wavelet coding at ~2.5:1, reducing an 8.4 MB/km² native alert stream to ~3.36 MB/km² delivered.

![Westlands replay summary](artifacts/replay/westlands_ca_2024-06-01_2024-10-31/replay_summary.png)

## Quick Start

Create a fresh environment, install dependencies, and run the synthetic benchmark:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python cascade_simulation.py
```

Reviewer baseline: Python `3.11` in a fresh virtual environment.

The full benchmark can take several minutes. **Progress:** `tqdm` bars on stderr for Monte Carlo, each policy evaluation, and the ROC sweep; phase banners mark ablation / EVI / CSC / optional “additional ablations”. A plain-text milestone log is always written to **`build/benchmark/benchmark_run.log`** (phase lines and start/finish timestamps), so you can `tail -f build/benchmark/benchmark_run.log` even when the terminal UI hides stderr. Use `python -u cascade_simulation.py` if stdout/stderr appear stuck in a pipe. Set `CASCADE_BENCHMARK_QUIET=1` or `CASCADE_MONTE_CARLO_QUIET=1` to silence tqdm and phase banners on stderr only; legacy `MASFE_BENCHMARK_QUIET` and `MASFE_MONTE_CARLO_QUIET` are still accepted.

After a successful run, transient outputs land in `build/benchmark/`:

- `build/benchmark/simulation_metrics.json`
- `build/benchmark/roc.png`
- `build/benchmark/roc_metrics.json`
- `build/benchmark/ablation_metrics.json`
- `build/benchmark/csc_sensitivity.json`

Promote the current build outputs into tracked release artifacts and paper figures with:

```bash
python scripts/export_release_artifacts.py
```

Optional economics refresh:

```bash
python unit_economics.py
```

This repository has been verified in a fresh virtual environment using the compatibility ranges in `requirements.txt`; the reviewer baseline is Python `3.11`.

## CSC Calibration

CASCADE now includes a standalone offline CSC calibration workflow for the live
weights, saturation constants, and alert threshold:

```bash
python csc_calibration.py
```

The default search is split deterministically across synthetic benchmark seeds:

- train: `0-59`
- validation: `60-79`
- test: `80-99`

The selection objective is conservative:

- keep train recall at or above `99.5%`
- keep validation recall at or above `99.0%`
- keep validation `data_mb`, seasonal-average compute, and energy within `105%` of the current defaults
- among feasible candidates, minimize validation false-positive rate first, then data volume, compute, energy, and distance from the current defaults

Build outputs are written to:

- `build/calibration/calibration_summary.json`
- `build/calibration/selected_candidate.json`
- `build/calibration/top_candidates.json`
- `build/calibration/pareto_candidates.json`

`csc_calibration.py` does not rewrite the live code defaults automatically. If a
selected candidate is promoted into `cascade_core.py`, rerun `python
cascade_simulation.py` and rebuild the paper so the checked-in metrics and
submission text stay aligned with the promoted configuration.

## Verification and Validation

The repository now includes a layered V&V harness aligned with the TU Delft SVV framing:

- code verification through focused unit tests of the core policy, CSC, replay utilities, and economics math
- calculation/system verification through small seeded pipeline tests for the simulator and replay logic
- offline validation through accepted reference fixtures for the published synthetic metrics, ROC sweep, CSC calibration summary, replay anchors, and economics summary

From a fresh environment, install the project and test dependencies and run the fast suite:

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -m "not slow and not validation"
```

Run the full automated suite:

```bash
python -m pytest
```

Run only the offline validation checks:

```bash
python -m pytest -m validation
```

Heavy plot-oriented smoke tests are marked `slow`, and the validation baselines are isolated behind the `validation` marker so routine development runs stay fast and deterministic.

The detailed V&V plan and acceptance criteria live in [docs/verification_validation_plan.md](docs/verification_validation_plan.md).

## Real MODIS Replay

The real-scene replay uses official AppEEARS subsets of `MOD13A1.061` EVI plus QA, `MOD11A1.061` daytime LST plus QC, and `MOD09A1.061` surface reflectance for NDWI over the Westlands / Firebaugh AOI in California. It is framed as an unlabeled scheduler exercise on official MODIS scenes, not as a labeled anomaly benchmark. In the tracked 2024 season, the calibrated production replay stays intentionally sub-threshold: peak CSC is `0.412` versus `csc_alert_thr = 0.615`, so zero `FUSE_PRIORITY` alerts is expected behavior rather than a failure to fire.

Activate the environment:

```bash
source .venv/bin/activate
```

Set Earthdata credentials in the repo-root `.env` file or export them in your shell.

The replay script auto-loads:

```bash
EARTHDATA_USERNAME=
EARTHDATA_PASSWORD=
```

Shell export path:

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
  --cache-dir data/cache \
  --require-full-fusion \
  --disable-date-extension
```

Run the optional field-ops sensitivity check at the low end of the published threshold sweep:

```bash
python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-10-31 \
  --cache-dir data/cache \
  --csc-alert-thr 0.40 \
  --require-full-fusion \
  --disable-date-extension
```

That non-default run writes to a threshold-suffixed build directory such as `build/replay/westlands_ca_2024-06-01_2024-10-31_thr_0p400/`, and `replay_metrics.json` records the active `csc_alert_thr`.

To force a fresh AppEEARS download instead of reusing the refreshed cache:

```bash
python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-10-31 \
  --cache-dir data/cache \
  --force-download \
  --require-full-fusion \
  --disable-date-extension
```

If the cache or AppEEARS bundle includes `MOD09A1.061`, the replay derives median clear-sky NDWI over the same composite window and uses the full `EVI + LST + NDWI` CSC. If you point the script at an older cached bundle that contains only `MOD13A1` and `MOD11A1`, it can still run in a labeled `evi_lst_fallback` mode, and `replay_metrics.json` now reports that fusion mode explicitly.

Optional second-season extension:

```bash
python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2023-05-01 \
  --end 2023-10-31 \
  --cache-dir data/cache \
  --disable-date-extension \
  --require-full-fusion
```

If you already have an AppEEARS download, reuse the bundle directly instead of authenticating again:

```bash
python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-10-31 \
  --bundle-dir /absolute/path/to/cascade-westlands-2024/
```

```bash
python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-10-31 \
  --bundle-zip /absolute/path/to/cascade-westlands-2024.zip
```

Tracked replay anchor used in the paper:

- `7` valid windows after a `3`-window warmup
- `fusion_mode: ndwi_full` with `bundle_has_mod09: true`
- `7` `FUSE` windows and `0` `FUSE_PRIORITY` windows under the refreshed 2024 NDWI-complete bundle
- no priority-alert date in the 2024 replay
- peak CSC: `0.412` on `2024-09-13`
- the absence of `FUSE_PRIORITY` is expected because the seasonal peak stayed below the calibrated `0.615` threshold
- an optional `csc_alert_thr = 0.40` sensitivity replay yields `1` `FUSE_PRIORITY` window on `2024-09-13`
- mean valid coverage: `0.995`
- tracked artifact note: the checked-in 2024 replay rows now reflect the full `EVI + LST + NDWI` path

## For Judges — 5-Minute Evaluation Path

1. Read the summary and headline metrics above.
2. Open `artifacts/benchmark/roc.png` to see the tunable operating point behind the published threshold.
3. Run `pip install -r requirements.txt && python cascade_simulation.py` to reproduce the synthetic benchmark end to end.
4. Open `artifacts/replay/westlands_ca_2024-06-01_2024-10-31/replay_summary.png` and `artifacts/replay/westlands_ca_2024-06-01_2024-10-31/replay_metrics.json` to confirm the real-scene replay artifacts.

## Repository Layout

- `src/cascade/core.py`: shared CSC computation, Beta-posterior belief model, resolution metadata, and deterministic policy logic.
- `src/cascade/simulation.py`: 100-seed Monte Carlo benchmark with ROC, ablation, CSC sweep, utilization reporting, and the `EVI + LST + NDWI` synthetic benchmark.
- `masfe_core.py` and `masfe_simulation.py`: deprecated compatibility wrappers for older reviewer commands.
- `src/cascade/replay/modis.py`: AppEEARS-backed MODIS replay workflow for the Westlands AOI with MOD09 NDWI support, explicit full-fusion enforcement, and fallback reporting.
- `src/cascade/economics.py`: five-year SJV-to-global rollout model.
- `build/`: transient local generation outputs.
- `artifacts/benchmark/`: tracked synthetic benchmark metrics and plots.
- `artifacts/calibration/`: tracked offline CSC calibration summaries.
- `artifacts/economics/`: tracked rollout-model outputs.
- `artifacts/replay/westlands_ca_2024-06-01_2024-10-31/`: tracked replay artifacts used in the paper.
- `paper/figures/`: paper-bound rendered figure assets.
- `docs/unit_economics.md`: supporting explanation of the rollout model and assumptions.
- `docs/repo_structure.md`: repository layout, output policy, and compatibility notes.
- `paper/EmilLambert_CASCADE.tex`: submission paper source of truth.
- `paper/EmilLambert_CASCADE.pdf`: compiled submission PDF.

## Submission alignment (source of truth)

The submission source of truth is `paper/EmilLambert_CASCADE.tex`. Rebuild `paper/EmilLambert_CASCADE.pdf` from that file after any narrative or metric update so the checked-in paper and repo artifacts stay aligned.

## License

Released under the MIT License. See `LICENSE`.
