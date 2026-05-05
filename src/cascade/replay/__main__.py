# SPDX-License-Identifier: MIT
from __future__ import annotations

import argparse
import json

from cascade.replay import replay


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the paper-anchor MODIS replays.")
    parser.add_argument("--year", type=int, required=True, choices=[2014, 2024])
    parser.add_argument("--aoi", default="westlands_ca")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument(
        "--prefer-artifacts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use tracked `artifacts/` outputs when present (default: true).",
    )
    args = parser.parse_args(argv)

    metrics = replay(
        args.year,
        aoi=args.aoi,
        cache_dir=args.cache_dir,
        prefer_artifacts=bool(args.prefer_artifacts),
    )
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
