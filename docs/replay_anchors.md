# Replay Anchor Status

The old Westlands 2014/2024 drought-vs-quiet comparison is deprecated. The
previous 2024 quiet-season artifact was generated from an older wrong-AOI
bundle and is no longer part of the accepted replay evidence. The current
tracked replay artifacts have been regenerated from the current
Westlands/Firebaugh AOI with provenance, source bundle hashes, and CSC stacks.

The current `westlands_ca` AOI is:

```text
[-120.55, 36.55, -120.45, 36.65]
```

The accepted legacy-mode artifacts now give similar peak CSC values in both
seasons:

| Season | Window | Peak CSC | Alert windows | First alert | Mean valid |
| --- | --- | ---: | ---: | --- | ---: |
| Westlands 2014 | 2014-06-01 to 2014-10-31 | `0.869` | `6 / 6` active windows | `2014-07-28` | `0.852` |
| Westlands 2024 | 2024-06-01 to 2024-10-31 | `0.865` | `5 / 7` active windows | `2024-07-27` | `0.820` |

This means the current rolling-baseline replay configuration should be
interpreted as adaptive crop-stress/phenology prioritization, not as a validated
drought-vs-quiet discriminator. The replay infrastructure is still useful, but
drought-specific claims require AOI provenance, spatial coherence diagnostics,
and external drought context.

The stricter `coherent_priority` replay artifacts suppress priority downlinks in
both years:

| Season | Priority mode | Priority alerts | Peak CSC | CSC p95 | Alert fraction | Max component |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Westlands 2014 | `coherent_priority` | `0` | `0.869` | `0.556` | `0.041667` | `3` |
| Westlands 2024 | `coherent_priority` | `0` | `0.865` | `0.243` | `0.020833` | `2` |

That result is also not a drought validation success. It shows that even the
2014 current-AOI MODIS replay is spatially sparse under the p95/extent/component
gate.

## Reviewer Commands

```bash
python -m cascade.replay --year 2014
python -m cascade.replay --year 2024
```

These commands prefer the tracked legacy-mode artifacts when present. To
evaluate the current cached bundle under a selected policy mode, bypass
artifacts:

```bash
python -m cascade.replay --year 2014 --priority-mode legacy_max --no-prefer-artifacts
python -m cascade.replay --year 2024 --priority-mode legacy_max --no-prefer-artifacts
python -m cascade.replay --year 2014 --priority-mode coherent_priority --no-prefer-artifacts
python -m cascade.replay --year 2024 --priority-mode coherent_priority --no-prefer-artifacts
```

Live AppEEARS replay is available through `real_modis_replay.py` when
credentials and dependencies are present.

## Artifact Provenance

Every newly generated `replay_metrics.json` records:

- `aoi`, `bbox`, `start_date`, and `end_date`
- `code_commit`
- `appeears_task_id`
- `source_bundle_hash`
- `created_utc`
- `layers`
- `csc_stack_present`

Accepted replay artifacts must also include a neighboring `csc_stack.npz`, must
have a `bbox` matching the current AOI registry, and must match the accepted
JSON fixture when one is present.

## Interpretation

CASCADE's real-scene replay currently serves as a policy-stress demonstration.
The rolling same-season CSC is sensitive to sparse field-level vegetation,
thermal, and moisture changes. For drought validation, future accepted anchors
must distinguish adaptive crop-stress triggers from externally labeled drought
outcomes and should report spatial extent, connected components, component
attribution, and independent drought labels.
