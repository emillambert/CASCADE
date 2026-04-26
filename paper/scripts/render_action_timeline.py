from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.paths import ARTIFACTS_REPLAY_DIR, BUILD_REPLAY_DIR, PAPER_FIGURES_DIR


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
            "axes.titlesize": 12,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "axes.edgecolor": "#666666",
            "axes.linewidth": 0.8,
            "grid.color": "#d9d9d9",
            "grid.linewidth": 0.8,
            "grid.alpha": 0.8,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def render(csv_path: Path, out_path: Path, title: str = "") -> None:
    df = pd.read_csv(csv_path)
    if "date" not in df.columns or "action" not in df.columns:
        raise SystemExit(f"Unexpected CSV schema in {csv_path}")

    df["date"] = pd.to_datetime(df["date"])

    y_order = ["BASELINE", "FUSE", "FUSE_PRIORITY"]
    y_map = {name: idx for idx, name in enumerate(y_order)}
    df = df[df["action"].isin(y_map)].copy()
    df["y"] = df["action"].map(y_map)

    y_tick_labels = ["BASELINE", "FUSE", "PRIORITY"]

    colors = {
        "BASELINE": "#6e6e6e",
        "FUSE": "#1f77b4",
        "FUSE_PRIORITY": "#b00020",
    }

    fig, ax = plt.subplots(figsize=(8.2, 2.35))
    ax.set_axisbelow(True)
    ax.grid(True, axis="both")

    for action in y_order:
        subset = df[df["action"] == action]
        if subset.empty:
            continue
        ax.scatter(
            subset["date"],
            subset["y"],
            s=46 if action != "FUSE_PRIORITY" else 72,
            color=colors[action],
            edgecolors="white",
            linewidths=0.6,
            zorder=3,
        )

    pri = df[df["action"] == "FUSE_PRIORITY"].sort_values("date")
    fuse_only = df[df["action"] == "FUSE"]

    if not pri.empty:
        if "csc_max" in df.columns:
            peak_row = pri.loc[pri["csc_max"].idxmax()]
        else:
            peak_row = pri.iloc[0]
        n_pri = len(pri)
        n_active = len(df[df["action"] != "BASELINE"])
        if n_pri > 1:
            # All-PRIORITY case: annotate below the dots to avoid title collision.
            label = f"Peak CSC {peak_row['csc_max']:.3f} — {n_pri}/{n_active} windows FUSE_PRIORITY"
            ax.annotate(
                label,
                xy=(peak_row["date"], peak_row["y"]),
                xytext=(0, -28),
                textcoords="offset points",
                fontsize=9.0,
                color=colors["FUSE_PRIORITY"],
                ha="center",
                arrowprops=dict(arrowstyle="-", color=colors["FUSE_PRIORITY"], lw=0.8),
            )
        else:
            ax.annotate(
                f"FUSE_PRIORITY ({peak_row['date'].date().isoformat()})",
                xy=(peak_row["date"], peak_row["y"]),
                xytext=(8, 6),
                textcoords="offset points",
                fontsize=9.0,
                color=colors["FUSE_PRIORITY"],
            )
    elif not fuse_only.empty and "csc_max" in df.columns:
        peak = df.loc[df["csc_max"].idxmax()]
        ax.annotate(
            "Peak CSC 0.412;\npromotes at csc_alert_thr = 0.40",
            xy=(peak["date"], peak["y"]),
            xytext=(10, 8),
            textcoords="offset points",
            fontsize=8.8,
            color=colors["FUSE"],
            ha="left",
        )

    ax.set_yticks([y_map[name] for name in y_order], labels=y_tick_labels)
    ax.set_ylabel("Action")
    ax.set_xlabel("Composite date")
    if title:
        ax.set_title(title, fontsize=10.5, pad=4)

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    for tick in ax.get_xticklabels():
        tick.set_rotation(18)
        tick.set_ha("right")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#777777")
    ax.spines["bottom"].set_color("#777777")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.14, right=0.995, top=0.90, bottom=0.32)
    fig.savefig(out_path, dpi=300)
    fig.savefig(out_path.with_suffix(".svg"), format="svg")
    fig.savefig(out_path.with_suffix(".pdf"), format="pdf")
    plt.close(fig)
    print(f"Saved {out_path.with_suffix('.pdf')}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--year",
        choices=["2014", "2024", "both"],
        default="both",
        help="Which replay year to render (default: both)",
    )
    args = parser.parse_args()

    configure_style()

    if args.year in ("2014", "both"):
        csv_2014 = (
            BUILD_REPLAY_DIR
            / "westlands_ca_2014-06-01_2014-10-31"
            / "action_timeline.csv"
        )
        if not csv_2014.exists():
            print(f"WARNING: 2014 CSV not found at {csv_2014} — skipping")
        else:
            render(
                csv_2014,
                PAPER_FIGURES_DIR / "action_timeline_2014.png",
                title="Westlands 2014 replay — D4 Exceptional Drought (csc_alert_thr = 0.615, unmodified)",
            )

    if args.year in ("2024", "both"):
        csv_2024 = (
            ARTIFACTS_REPLAY_DIR
            / "westlands_ca_2024-06-01_2024-10-31"
            / "action_timeline.csv"
        )
        if not csv_2024.exists():
            print(f"WARNING: 2024 CSV not found at {csv_2024} — skipping")
        else:
            render(
                csv_2024,
                PAPER_FIGURES_DIR / "action_timeline_2024.png",
                title="Westlands 2024 replay — quiet season (csc_alert_thr = 0.615, unmodified)",
            )


if __name__ == "__main__":
    main()
