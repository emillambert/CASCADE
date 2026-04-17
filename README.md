# MASFE

## One-Paragraph Summary

MASFE (Multi-Algorithm Scheduling and Fusion Engine) is a NASA Space-to-Soil submission that turns crop-stress monitoring into an onboard scheduling problem instead of a passive downlink problem. The repo contains the 100-seed hosted-payload Monte Carlo benchmark, the real-scene MODIS replay over Westlands/Firebaugh, the five-year rollout economics model, and the single-file LaTeX paper. In the current synthetic benchmark, MASFE reduces downlink by `96.4%` versus a raw-dump baseline, saves `20.6%` payload energy, retains `100.0%` disease-event recall, and holds false-positive rate to `1.4%`, with the operating point and CSC formulation stress-tested in the supporting outputs.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/python masfe_simulation.py
```

Optional workflows:

```bash
.venv/bin/python unit_economics.py
jupyter lab notebooks/real_modis_policy_replay.ipynb
```

## Headline Results Table

| Metric | RAW_DUMP | FIXED_ONBOARD | MASFE_MDP |
| --- | ---: | ---: | ---: |
| Downlink data (MB, mean) | 14,400 | 517 | 517 |
| Energy consumed (Wh, mean) | 9.60 | 7.90 | 7.62 |
| True positives (mean) | 900.4 | 900.5 | 900.9 |
| False positives (mean) | 12.9 | 13.0 | 13.1 |
| Priority alerts sent (mean) | 0.0 | 0.0 | 12.9 |

Monte Carlo headline metrics over `100` seeds:

| Metric | Mean | 95% CI |
| --- | ---: | ---: |
| Downlink reduction vs raw | `96.4%` | `96.3-96.5%` |
| Energy saving vs raw | `20.6%` | `20.5-20.7%` |
| Disease-event recall | `100.0%` | `100.0-100.0%` |
| False-positive rate | `1.4%` | `1.4-1.5%` |
| Seasonal average compute utilization | `87.5%` | `87.2-87.8%` |

Supporting evidence in `outputs/`:

- `outputs/roc.png` and `outputs/roc_metrics.json`: operating-point sweep for `csc_alert_thr` from `0.40` to `0.70`
- `outputs/csc_sensitivity.json`: CSC robustness sweep over `0.55/0.45` weighting and `5sigma/4sigma` saturation constants under a `+/-30%` sweep
- `outputs/ablation_metrics.json`: explicit no-belief ablation against the paper operating point

The CSC sweep remains robust under the `+/-30%` perturbation: recall stays at `100.0%` across all tested cases and false-positive rate stays within `0.7-2.6%`, so the published `0.55/0.45` weighting and `5sigma/4sigma` saturation pair are not brittle one-off settings.

## File Index

- `masfe_core.py`: shared hosted-payload SWAP model, CSC computation, and deterministic policies.
- `masfe_simulation.py`: 100-seed Monte Carlo benchmark plus ablation, ROC, CSC sweep, and utilization reporting.
- `simulation_metrics.json`: paper-facing synthetic benchmark metrics refreshed by `masfe_simulation.py`.
- `real_modis_replay.py`: official MODIS replay workflow for the Westlands/Firebaugh AOI.
- `outputs/real_modis/...`: cached replay artifacts including `replay_metrics.json`, `action_timeline.csv`, `replay_summary.png`, and `peak_alert_map.png`.
- `outputs/roc.png`: ROC-style operating-point plot for the MASFE alert threshold sweep.
- `outputs/roc_metrics.json`: threshold-by-threshold ROC metadata used for the repo claim.
- `outputs/csc_sensitivity.json`: robustness sweep for CSC weights and saturation constants.
- `outputs/ablation_metrics.json`: matched-recall ablation comparing MASFE to the no-belief variant.
- `unit_economics.py`: five-year SJV-to-global platform economics model.
- `outputs/unit_economics/unit_economics.json`: detailed low/base/high rollout outputs and break-even summary.
- `notebooks/real_modis_policy_replay.ipynb`: notebook replay of cached MODIS policy decisions.
- `docs/advisor_outreach.md`: ready-to-send advisor outreach note for the final campaign.
- `docs/video_script.md`: 7-slide, sub-3-minute pitch script.
- `docs/submission_checklist.md`: final manual release and submission checklist.
- `report.tex`: single-file Overleaf-ready paper source of truth.
- `EmilLambert_MASFE.pdf`: current compiled submission PDF.

## Real MODIS Replay Reproduction

The replay targets the Westlands / Firebaugh AOI in California and uses official `MOD13A1.061` EVI plus QA and `MOD11A1.061` daytime LST plus QC.

Set NASA Earthdata credentials before the first AppEEARS-backed run:

```bash
export EARTHDATA_USERNAME="your-username"
export EARTHDATA_PASSWORD="your-password"
```

Run the replay:

```bash
.venv/bin/python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-09-30 \
  --cache-dir data/modis_cache
```

To keep the run fixed to the June-September window:

```bash
--disable-fallback
```

If you already have an AppEEARS package, point the script at either an extracted directory or a single ZIP bundle:

```bash
.venv/bin/python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-09-30 \
  --bundle-dir /absolute/path/to/masfe-westlands-2024/
```

```bash
.venv/bin/python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2024-06-01 \
  --end 2024-09-30 \
  --bundle-zip /absolute/path/to/masfe-westlands-2024.zip
```

Current replay anchor used in the paper:

- `7` valid windows after a `3`-window warmup
- `1` confirmed `FUSE_PRIORITY` window
- first and peak alert date: `2024-07-27`
- mean valid coverage: `0.995`

Second-season extension target:

```bash
.venv/bin/python real_modis_replay.py \
  --aoi westlands_ca \
  --start 2023-05-01 \
  --end 2023-10-31 \
  --cache-dir data/modis_cache
```

That 2023 replay is scripted but still depends on Earthdata access or a pre-downloaded AppEEARS bundle; it is not pre-populated in this repo.

The replay is intentionally framed as scheduler validation on official MODIS scenes, not as a labeled disease benchmark.

## License

Released under the MIT License. See `LICENSE`.
