from __future__ import annotations

from cascade.simulation import main as simulation_main


def main(argv: list[str] | None = None) -> int:
    # Keep the reviewer path fast/deterministic: headline benchmark, skip slow extra ablations.
    argv = list(argv) if argv is not None else ["--skip-additional-ablations"]
    if "--skip-additional-ablations" not in argv and "--additional-ablations-only" not in argv:
        argv = ["--skip-additional-ablations", *argv]
    return int(simulation_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())

