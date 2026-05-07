# Reproducibility

This file describes the corrected arXiv prerelease workflow for CASCADE
`v1.1.0-arxiv`. The real-scene MODIS replay is a policy-stress and
reproducibility test, not a labelled drought-validation benchmark.

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

For local plotting on macOS or headless systems, use:

```bash
export MPLBACKEND=Agg
```

## 2. Run Synthetic Benchmark

```bash
python -m cascade.simulate
```

Expected headline metrics are protected by validation fixtures:

| Metric | Expected |
| --- | ---: |
| Downlink reduction vs raw | `99.05%` |
| Energy saving vs raw | `38.3%` |
| Synthetic anomaly recall | `100.0%` |
| Synthetic false-positive rate | `0.6%` |

## 3. Run Legacy Replay

Tracked artifacts are used by default:

```bash
python -m cascade.replay --year 2014 --priority-mode legacy_max
python -m cascade.replay --year 2024 --priority-mode legacy_max
```

To force current cached/live replay instead of reading tracked artifacts:

```bash
python -m cascade.replay --year 2014 --priority-mode legacy_max --no-prefer-artifacts
python -m cascade.replay --year 2024 --priority-mode legacy_max --no-prefer-artifacts
```

## 4. Run Coherent-Priority Replay

`coherent_priority` bypasses tracked legacy artifacts and evaluates the stricter
spatial gate:

```bash
python -m cascade.replay --year 2014 --priority-mode coherent_priority --no-prefer-artifacts
python -m cascade.replay --year 2024 --priority-mode coherent_priority --no-prefer-artifacts
```

## 5. Expected Replay Table

| AOI/year | Mode | Priority alerts | Peak CSC | CSC p95 | Alert fraction | `C_max` |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Westlands 2014 | `legacy_max` | `6` | `0.869` | `0.556` | `0.041667` | `3` |
| Westlands 2024 | `legacy_max` | `5` | `0.865` | `0.243` | `0.020833` | `2` |
| Westlands 2014 | `coherent_priority` | `0` | `0.869` | `0.556` | `0.041667` | `3` |
| Westlands 2024 | `coherent_priority` | `0` | `0.865` | `0.243` | `0.020833` | `2` |

## 6. Known Limitation

The real-scene MODIS replay is not a labelled drought-validation benchmark. It
demonstrates policy replay, artifact provenance, source-bundle hashing,
component attribution, and priority-gate behavior. Current max-pixel CSC replay
can trigger on sparse vegetation/moisture changes; `coherent_priority` is
provided for spatially stricter alerting.
