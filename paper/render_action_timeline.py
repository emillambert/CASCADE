from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


def configure_style() -> None:
    # Match the report’s print-like feel (Times + restrained grays).
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


def render(csv_path: Path, out_path: Path) -> None:
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

    # Keep it short (paper figure), but readable.
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

    # Label the priority event (if any) without shouting.
    pri = df[df["action"] == "FUSE_PRIORITY"].sort_values("date")
    if not pri.empty:
        first = pri.iloc[0]
        ax.annotate(
            f"FUSE_PRIORITY ({first['date'].date().isoformat()})",
            xy=(first["date"], first["y"]),
            xytext=(8, 6),
            textcoords="offset points",
            fontsize=9.5,
            color=colors["FUSE_PRIORITY"],
        )

    ax.set_yticks([y_map[name] for name in y_order], labels=y_tick_labels)
    ax.set_ylabel("Action")
    ax.set_xlabel("Composite date")

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    for tick in ax.get_xticklabels():
        tick.set_rotation(18)
        tick.set_ha("right")

    # Reduce “boxy” feel while keeping print clarity.
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#777777")
    ax.spines["bottom"].set_color("#777777")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Tight margins so the figure fits under a caption nicely.
    # Extra left margin prevents y-label clipping once framed in LaTeX.
    fig.subplots_adjust(left=0.14, right=0.995, top=0.90, bottom=0.32)
    fig.savefig(out_path, dpi=300)
    # Vector versions for the report.
    fig.savefig(out_path.with_suffix(".svg"), format="svg")
    fig.savefig(out_path.with_suffix(".pdf"), format="pdf")
    plt.close(fig)


def main() -> None:
    configure_style()
    repo_root = Path(__file__).resolve().parents[1]
    csv_path = (
        repo_root
        / "outputs/real_modis/westlands_ca_2024-06-01_2024-10-31/action_timeline.csv"
    )
    render(csv_path, repo_root / "outputs/action_timeline_2024.png")


if __name__ == "__main__":
    main()

