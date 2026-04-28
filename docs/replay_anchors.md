# Replay Anchors

The replay anchors compare the same committed CASCADE policy on two
Westlands/Firebaugh, California seasons. Both use the unchanged CSC priority
threshold `0.615018` and the Westlands AOI implemented as `westlands_ca`
(`[-120.55, 36.55, -120.45, 36.65]`).

## Reviewer commands

```bash
python -m cascade.replay --year 2014
python -m cascade.replay --year 2024
```

These commands prefer tracked artifacts when present, so they work offline and
return the same JSON payloads used by tests. Live AppEEARS replay is available
through `real_modis_replay.py` when credentials and dependencies are present.

## Anchor results

| Season | Window | Expected result | Peak CSC | Alerts | Fusion mode |
| --- | --- | --- | ---: | ---: | --- |
| 2014 D4 drought | 2014-06-01 to 2014-10-31 | Severe stress caught | `0.869` | `6 / 6` active windows | `ndwi_full` |
| 2024 quiet season | 2024-06-01 to 2024-10-31 | No priority alerts | `0.412` | `0 / 7` active windows | `ndwi_full` |

The 2014 peak is about `2.1x` the 2024 peak and stays above the `0.615018`
priority threshold after warmup. The 2024 season remains below threshold and
therefore should not trigger `FUSE_PRIORITY`.

## Tracked evidence

2014 files:

- `artifacts/replay/westlands_ca_2014-06-01_2014-10-31/replay_metrics.json`
- `artifacts/replay/westlands_ca_2014-06-01_2014-10-31/action_timeline.csv`
- `artifacts/replay/westlands_ca_2014-06-01_2014-10-31/replay_summary.png`
- `artifacts/replay/westlands_ca_2014-06-01_2014-10-31/peak_alert_map.png`

2024 files:

- `artifacts/replay/westlands_ca_2024-06-01_2024-10-31/replay_metrics.json`
- `artifacts/replay/westlands_ca_2024-06-01_2024-10-31/action_timeline.csv`
- `artifacts/replay/westlands_ca_2024-06-01_2024-10-31/replay_summary.png`
- `artifacts/replay/westlands_ca_2024-06-01_2024-10-31/peak_alert_map.png`

The validation tests compare both replay metrics files against accepted
fixtures. The canonical-claim test also checks that the 2014 replay comes from
tracked artifacts, reaches peak CSC `0.869` within tolerance, and reports six
`FUSE_PRIORITY` windows.

## Interpretation

The replay is a content-driven policy check, not a labeled field-trial
benchmark. It shows that the same threshold separates a known severe drought
season from a quiet season in the selected agricultural AOI without retuning.
