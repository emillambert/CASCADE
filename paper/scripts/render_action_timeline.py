from __future__ import annotations

import argparse
import json
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


COLORS = {
    "BASELINE": "#6e6e6e",
    "MOD13": "#2ca02c",
    "FUSE": "#1f77b4",
    "FUSE_PRIORITY": "#b00020",
}
GRID = "#e0e0e0"
EDGE = "#888888"
DARK = "#222222"
ALERT_THR = 0.615
Y_ORDER = ["BASELINE", "FUSE", "FUSE_PRIORITY"]
Y_MAP = {name: idx for idx, name in enumerate(Y_ORDER)}
Y_TICK_LABELS = {"BASELINE": "BASE", "FUSE": "FUSE", "FUSE_PRIORITY": "PRIORITY"}


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 8.8,
            "ytick.labelsize": 8.8,
            "axes.edgecolor": "#666666",
            "axes.linewidth": 0.75,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.alpha": 1.0,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "legend.fontsize": 8.0,
        }
    )


def load_timeline(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "date" not in df.columns or "action" not in df.columns:
        raise SystemExit(f"Unexpected CSV schema in {csv_path}")
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_metrics(metrics_path: Path) -> dict:
    if not metrics_path.exists():
        return {}
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def _clean_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(EDGE)
    ax.spines["bottom"].set_color(EDGE)


def plot_action_panel(ax, df: pd.DataFrame, title: str, compact_rows: bool) -> None:
    plot_df = df[df["action"].isin(Y_MAP)].copy()
    if compact_rows:
        present = [a for a in Y_ORDER if a in plot_df["action"].unique()]
        y_map = {a: i for i, a in enumerate(present)}
        tick_actions = present
    else:
        y_map = Y_MAP
        tick_actions = Y_ORDER
    plot_df["y"] = plot_df["action"].map(y_map)

    ax.set_axisbelow(True)
    ax.grid(True, axis="both", alpha=0.55)
    for action in tick_actions:
        subset = plot_df[plot_df["action"] == action]
        if subset.empty:
            continue
        ax.scatter(
            subset["date"],
            subset["y"],
            s=46 if action != "FUSE_PRIORITY" else 66,
            color=COLORS[action],
            edgecolors="white",
            linewidths=0.6,
            zorder=3,
            label=Y_TICK_LABELS[action],
        )

    ax.set_yticks([y_map[a] for a in tick_actions], labels=[Y_TICK_LABELS[a] for a in tick_actions])
    ax.set_ylim(-0.45, (len(tick_actions) - 0.55) if compact_rows else 2.45)
    ax.set_title(title, fontsize=10.5, pad=4)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    for tick in ax.get_xticklabels():
        tick.set_rotation(25)
        tick.set_ha("right")
    _clean_axes(ax)


def plot_csc_panel(ax, df: pd.DataFrame, ylim: tuple[float, float], annotate_values: bool = True) -> None:
    ax.set_axisbelow(True)
    ax.grid(True, axis="y", alpha=0.55)

    act_df = df[df["action"].isin(["FUSE", "FUSE_PRIORITY", "MOD13"])].copy().sort_values("date")
    bar_colors = [COLORS.get(action, "#888888") for action in act_df["action"]]
    ax.bar(
        act_df["date"],
        act_df["csc_max"],
        width=pd.Timedelta(days=10),
        color=bar_colors,
        alpha=0.88,
        zorder=2,
    )
    ax.axhline(ALERT_THR, color=COLORS["FUSE_PRIORITY"], linewidth=1.1, linestyle="--", zorder=3)
    ax.set_ylabel("CSC max")
    ax.set_ylim(*ylim)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    for tick in ax.get_xticklabels():
        tick.set_rotation(25)
        tick.set_ha("right")
    _clean_axes(ax)

    if annotate_values:
        for _, row in act_df.iterrows():
            ax.text(
                row["date"],
                min(row["csc_max"] + 0.025, ylim[1] - 0.03),
                f"{row['csc_max']:.2f}",
                ha="center",
                va="bottom",
                fontsize=7.0,
                color=COLORS.get(row["action"], "#444444"),
            )


def render(csv_path: Path, out_path: Path, title: str = "", show_csc_panel: bool = True) -> None:
    df = load_timeline(csv_path)
    has_csc = show_csc_panel and "csc_max" in df.columns

    nrows = 2 if has_csc else 1
    height = 3.8 if has_csc else 2.35
    fig, axes = plt.subplots(
        nrows,
        1,
        figsize=(8.2, height),
        gridspec_kw={"height_ratios": [0.7, 1.0]} if has_csc else {},
        sharex=False,
    )
    if nrows == 1:
        axes = [axes]

    plot_action_panel(axes[0], df, title, compact_rows=True)
    if has_csc:
        plot_csc_panel(axes[1], df, ylim=(0, min(1.05, df["csc_max"].max() * 1.25 + 0.05)))
        axes[1].set_xlabel("Date")
        axes[1].legend(
            handles=[plt.Line2D([0], [0], color=COLORS["FUSE_PRIORITY"], linestyle="--", lw=1.2)],
            labels=[f"Alert threshold ({ALERT_THR})"],
            frameon=False,
            fontsize=8.5,
            loc="upper right",
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    top = 0.93 if not title else 0.89
    if has_csc:
        fig.subplots_adjust(left=0.10, right=0.985, top=top, bottom=0.18, hspace=0.55)
    else:
        fig.subplots_adjust(left=0.14, right=0.995, top=top, bottom=0.32)
    fig.savefig(out_path, dpi=300)
    fig.savefig(out_path.with_suffix(".svg"), format="svg")
    fig.savefig(out_path.with_suffix(".pdf"), format="pdf")
    plt.close(fig)
    print(f"Saved {out_path.with_suffix('.pdf')}")


def render_combined(csv_2014: Path, csv_2024: Path, out_path: Path) -> None:
    df_2014 = load_timeline(csv_2014)
    df_2024 = load_timeline(csv_2024)
    peak_2014 = float(df_2014["csc_max"].max())
    peak_2024 = float(df_2024["csc_max"].max())
    ratio = peak_2014 / peak_2024 if peak_2024 else 0.0

    fig = plt.figure(figsize=(8.2, 4.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[0.72, 1.0], hspace=0.42, wspace=0.20)
    axes = [[fig.add_subplot(gs[row, col]) for col in range(2)] for row in range(2)]

    plot_action_panel(axes[0][0], df_2014, "2014 D4 drought replay", compact_rows=False)
    plot_action_panel(axes[0][1], df_2024, "2024 quiet-season replay", compact_rows=False)
    plot_csc_panel(axes[1][0], df_2014, ylim=(0, 0.95))
    plot_csc_panel(axes[1][1], df_2024, ylim=(0, 0.95))

    axes[1][0].set_xlabel("Date")
    axes[1][1].set_xlabel("Date")
    axes[0][1].set_yticklabels([])
    axes[1][1].set_ylabel("")
    axes[1][1].set_yticklabels([])

    for ax in (axes[1][0], axes[1][1]):
        ax.text(
            0.98,
            ALERT_THR + 0.02,
            "alert threshold",
            transform=ax.get_yaxis_transform(),
            ha="right",
            va="bottom",
            fontsize=7.1,
            color=COLORS["FUSE_PRIORITY"],
        )

    axes[1][0].annotate(
        f"peak {peak_2014:.3f}\n6/6 priority",
        xy=(df_2014.loc[df_2014["csc_max"].idxmax(), "date"], peak_2014),
        xytext=(-18, 18),
        textcoords="offset points",
        fontsize=7.8,
        color=COLORS["FUSE_PRIORITY"],
        ha="right",
        arrowprops=dict(arrowstyle="->", color=COLORS["FUSE_PRIORITY"], lw=0.75),
    )
    axes[1][1].annotate(
        f"peak {peak_2024:.3f}\n0 alerts",
        xy=(df_2024.loc[df_2024["csc_max"].idxmax(), "date"], peak_2024),
        xytext=(14, 18),
        textcoords="offset points",
        fontsize=7.8,
        color=COLORS["FUSE"],
        ha="left",
        arrowprops=dict(arrowstyle="->", color=COLORS["FUSE"], lw=0.75),
    )

    fig.text(
        0.50,
        0.515,
        f"{ratio:.1f}x peak CSC\nno parameter retuning",
        ha="center",
        va="center",
        fontsize=9.4,
        weight="bold",
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#fafafa", edgecolor="#d5d5d5", linewidth=0.8),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.08, right=0.985, top=0.93, bottom=0.13)
    fig.savefig(out_path, dpi=300)
    fig.savefig(out_path.with_suffix(".svg"), format="svg")
    fig.savefig(out_path.with_suffix(".pdf"), format="pdf")
    plt.close(fig)
    print(f"Saved {out_path.with_suffix('.pdf')}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", choices=["2014", "2024", "both", "combined"], default="both")
    args = parser.parse_args()
    configure_style()

    csv_2014 = BUILD_REPLAY_DIR / "westlands_ca_2014-06-01_2014-10-31" / "action_timeline.csv"
    csv_2024 = ARTIFACTS_REPLAY_DIR / "westlands_ca_2024-06-01_2024-10-31" / "action_timeline.csv"

    if args.year in ("2014", "both"):
        if not csv_2014.exists():
            print(f"WARNING: 2014 CSV not found at {csv_2014} - skipping")
        else:
            render(
                csv_2014,
                PAPER_FIGURES_DIR / "action_timeline_2014.png",
                title="Westlands 2014 - D4 Exceptional Drought (alert thr = 0.615, unmodified)",
                show_csc_panel=True,
            )

    if args.year in ("2024", "both"):
        if not csv_2024.exists():
            print(f"WARNING: 2024 CSV not found at {csv_2024} - skipping")
        else:
            render(
                csv_2024,
                PAPER_FIGURES_DIR / "action_timeline_2024.png",
                title="Westlands 2024 - quiet season (csc_alert_thr = 0.615, unmodified)",
                show_csc_panel=True,
            )

    if args.year in ("both", "combined"):
        if not csv_2014.exists() or not csv_2024.exists():
            print("WARNING: combined replay CSVs missing - skipping")
        else:
            render_combined(csv_2014, csv_2024, PAPER_FIGURES_DIR / "action_timeline_westlands_split.png")


if __name__ == "__main__":
    main()
