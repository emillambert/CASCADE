# Unit Economics

The unit-economics model is a concise rollout scenario for the CASCADE
hosted-payload concept. It is judge-facing: the goal is to show a plausible
path from validation geography to commercial scale, not to replace a full
investor diligence model.

## Core assumptions

| Assumption | Value |
| --- | ---: |
| Alerting price | `$4.00/ha/year` |
| Platform take rate | `20%` |
| Variable service cost | `$0.35/ha/year` |
| Carbon MRV add-on | `$0.50/ha/year` |
| Carbon MRV coverage | `50%` of enrolled hectares from `Y2` onward |
| Contribution margin without MRV | `$2.85/ha/year` |
| Contribution margin with MRV | `$3.10/ha/year` |

The model tracks low, base, and high fixed-cost cases. The low/design-to-cost
case is the paper-facing table; base and high are retained as sensitivity
checks.

## Rollout story

The validation anchor is the Westlands/San Joaquin Valley replay, but the
commercial scenario scales across broader irrigated geographies. In the current
low case:

| Year | Milestone | Hectares | Revenue | Operating margin |
| --- | --- | ---: | ---: | ---: |
| `Y1` | Anchor pilot | `50k` | `$0.20M` | grant-funded bridge |
| `Y2` | Benelux + CA scale | `400k` | `$1.70M` | `17.1%` |
| `Y3` | EU + U.S. national | `2.5M` | `$10.62M` | `60.4%` |
| `Y4` | Brazil entry | `6.5M` | `$27.62M` | `68.1%` |
| `Y5` | Global platform | `18.0M` | `$76.50M` | `70.7%` |

Break-even occurs in `Y2` for the low case and `Y3` for both the base and high
fixed-cost cases, according to `artifacts/economics/unit_economics.json`.

## Regenerating outputs

Run:

```bash
python scripts/unit_economics.py
```

or, through the compatibility wrapper:

```bash
python unit_economics.py
```

Generated files are written under `build/economics/`:

- `unit_economics.json`
- `unit_economics_table.tex`

After reviewing regenerated outputs, `make figures` promotes selected economics
files into `artifacts/economics/`. If the promoted JSON changes intentionally,
update `tests/fixtures/accepted/unit_economics_summary.json` in the same review.
