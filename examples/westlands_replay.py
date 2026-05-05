# SPDX-License-Identifier: MIT
"""Run the SoftwareX Westlands replay example.

By default this uses the tracked 2014 replay artifact, so it works offline and
does not require Earthdata/AppEEARS credentials. Pass ``--live`` to force the
lower-level MODIS replay workflow.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.replay import replay  # noqa: E402


def _action_distribution(metrics: dict[str, Any]) -> dict[str, int]:
    return {
        str(action): int(count)
        for action, count in (metrics.get("action_distribution") or {}).items()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the CASCADE SoftwareX Westlands replay example."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2014,
        choices=[2014, 2024],
        help="Replay anchor year. Defaults to the 2014 D4 drought case.",
    )
    parser.add_argument("--aoi", default="westlands_ca")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Force live AppEEARS replay instead of tracked artifacts.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full replay metrics JSON payload.",
    )
    args = parser.parse_args(argv)

    metrics = replay(
        args.year,
        aoi=args.aoi,
        cache_dir=args.cache_dir,
        prefer_artifacts=not args.live,
    )

    if args.json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
        return 0

    actions = _action_distribution(metrics)
    print(f"CASCADE Westlands replay ({args.year})")
    print(f"source: {metrics.get('source', 'unknown')}")
    print(f"peak CSC: {float(metrics['peak_csc']):.3f}")
    print(f"FUSE_PRIORITY windows: {int(actions.get('FUSE_PRIORITY', 0))}")
    print("action distribution:")
    for action in ("SKIP", "MOD13", "FUSE", "FUSE_PRIORITY"):
        print(f"  {action}: {actions.get(action, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
