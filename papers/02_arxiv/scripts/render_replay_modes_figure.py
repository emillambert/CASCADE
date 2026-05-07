# SPDX-License-Identifier: MIT
"""Render the arXiv replay comparison figure from accepted replay artifacts."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ARXIV_DIR = Path(__file__).resolve().parents[1]
ROOT = ARXIV_DIR.parents[1]
OUT_DIR = ARXIV_DIR / "figures"
REPLAY_DIR = ROOT / "artifacts" / "replay"
WINDOWS = {
    ("2014", "legacy_max"): REPLAY_DIR / "westlands_ca_2014-06-01_2014-10-31",
    ("2024", "legacy_max"): REPLAY_DIR / "westlands_ca_2024-06-01_2024-10-31",
    ("2014", "coherent_priority"): REPLAY_DIR / "westlands_ca_2014-06-01_2014-10-31_coherent_priority",
    ("2024", "coherent_priority"): REPLAY_DIR / "westlands_ca_2024-06-01_2024-10-31_coherent_priority",
}


def load_metrics(path: Path) -> dict:
    return json.loads((path / "replay_metrics.json").read_text(encoding="utf-8"))


def load_timeline(path: Path) -> list[dict[str, str]]:
    with (path / "action_timeline.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def alert_series(path: Path) -> tuple[list[str], list[float], list[int]]:
    rows = load_timeline(path)
    active = [row for row in rows if row["action"] != "BASELINE"]
    labels = [row["date"] for row in active]
    csc = [float(row["csc_max"]) for row in active]
    alerts = [int(row["alert_pixels"]) for row in active]
    return labels, csc, alerts


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = {key: load_metrics(path) for key, path in WINDOWS.items()}

    fig = plt.figure(figsize=(8.8, 6.4))
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=[1.1, 1.0],
        height_ratios=[1.0, 0.92],
        left=0.08,
        right=0.98,
        top=0.92,
        bottom=0.12,
        wspace=0.28,
        hspace=0.42,
    )
    ax_legacy = fig.add_subplot(grid[0, 0])
    ax_coherent = fig.add_subplot(grid[0, 1])
    ax_components = fig.add_subplot(grid[1, 0])
    ax_provenance = fig.add_subplot(grid[1, 1])

    colors = {"2014": "#9b1d20", "2024": "#2b6cb0"}
    for ax, mode, title in [
        (ax_legacy, "legacy_max", "Legacy max-CSC replay"),
        (ax_coherent, "coherent_priority", "Coherent-priority replay"),
    ]:
        for year in ("2014", "2024"):
            labels, csc, alerts = alert_series(WINDOWS[(year, mode)])
            x = np.arange(len(labels))
            offset = -0.08 if year == "2014" else 0.08
            ax.plot(x + offset, csc, marker="o", linewidth=1.6, markersize=4.8, color=colors[year], label=year)
            alert_x = [idx + offset for idx, value in enumerate(alerts) if value > 0]
            alert_y = [csc[idx] for idx, value in enumerate(alerts) if value > 0]
            ax.scatter(alert_x, alert_y, s=48, facecolors="none", edgecolors=colors[year], linewidths=1.6)
        ax.axhline(0.615018, color="#444444", linestyle="--", linewidth=1, label="CSC threshold")
        ax.set_title(title, fontsize=10, pad=8)
        ax.set_ylabel("CSC max", fontsize=9)
        ax.set_xticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
        ax.set_ylim(0, 1.02)
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(axis="y", color="#dddddd", linewidth=0.6, alpha=0.7)
    ax_legacy.legend(loc="upper left", fontsize=7, frameon=True)

    component_names = ["EVI", "LST", "NDWI"]
    x = np.arange(4)
    labels = ["2014\nlegacy", "2024\nlegacy", "2014\ncoherent", "2024\ncoherent"]
    bottoms = np.zeros(4)
    for component, color in zip(component_names, ["#3b7a57", "#c05621", "#2b6cb0"]):
        values = [
            metrics[("2014", "legacy_max")]["peak_component_values"][component],
            metrics[("2024", "legacy_max")]["peak_component_values"][component],
            metrics[("2014", "coherent_priority")]["peak_component_values"][component],
            metrics[("2024", "coherent_priority")]["peak_component_values"][component],
        ]
        ax_components.bar(x, values, bottom=bottoms, label=component, color=color)
        bottoms += np.array(values)
    ax_components.axhline(0.615018, color="#444444", linestyle="--", linewidth=1)
    ax_components.set_title("Peak-pixel component attribution", fontsize=10, pad=8)
    ax_components.set_ylabel("Weighted CSC contribution", fontsize=9)
    ax_components.set_xticks(x)
    ax_components.set_xticklabels(labels, fontsize=7)
    ax_components.tick_params(axis="y", labelsize=8)
    ax_components.set_ylim(0, 1.0)
    ax_components.grid(axis="y", color="#dddddd", linewidth=0.6, alpha=0.7)
    ax_components.legend(fontsize=7, loc="upper right", frameon=True)

    legacy_2014 = metrics[("2014", "legacy_max")]
    legacy_2024 = metrics[("2024", "legacy_max")]
    coherent_2014 = metrics[("2014", "coherent_priority")]
    coherent_2024 = metrics[("2024", "coherent_priority")]
    ax_provenance.axis("off")
    ax_provenance.set_title("Replay diagnostics", fontsize=10, pad=8)
    rows = [
        [
            "2014 legacy",
            legacy_2014["action_distribution"].get("FUSE_PRIORITY", 0),
            f"{legacy_2014['peak_csc']:.3f}",
            f"{legacy_2014['csc_p95']:.3f}",
            f"{legacy_2014['alert_fraction']:.3f}",
            legacy_2014["max_connected_component"],
        ],
        [
            "2024 legacy",
            legacy_2024["action_distribution"].get("FUSE_PRIORITY", 0),
            f"{legacy_2024['peak_csc']:.3f}",
            f"{legacy_2024['csc_p95']:.3f}",
            f"{legacy_2024['alert_fraction']:.3f}",
            legacy_2024["max_connected_component"],
        ],
        [
            "2014 coherent",
            coherent_2014["action_distribution"].get("FUSE_PRIORITY", 0),
            f"{coherent_2014['peak_csc']:.3f}",
            f"{coherent_2014['csc_p95']:.3f}",
            f"{coherent_2014['alert_fraction']:.3f}",
            coherent_2014["max_connected_component"],
        ],
        [
            "2024 coherent",
            coherent_2024["action_distribution"].get("FUSE_PRIORITY", 0),
            f"{coherent_2024['peak_csc']:.3f}",
            f"{coherent_2024['csc_p95']:.3f}",
            f"{coherent_2024['alert_fraction']:.3f}",
            coherent_2024["max_connected_component"],
        ],
    ]
    table = ax_provenance.table(
        cellText=rows,
        colLabels=["case", "alerts", "max", "p95", r"$f_{\mathrm{alert}}$", r"$C_{\max}$"],
        loc="upper left",
        cellLoc="center",
        colLoc="center",
        colWidths=[0.34, 0.12, 0.13, 0.13, 0.13, 0.13],
        bbox=[0.0, 0.37, 1.0, 0.56],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(6.6)
    for (row, _col), cell in table.get_celld().items():
        cell.set_edgecolor("#cfcfcf")
        cell.set_linewidth(0.45)
        if row == 0:
            cell.set_facecolor("#eeeeee")
            cell.set_text_props(weight="bold")

    provenance = (
        "Policy-stress replay, not drought-label validation\n"
        f"AOI bbox: {legacy_2014['bbox']}\n"
        "Bundle hashes: regenerated per release\n"
        f"Peak component: 2014 {legacy_2014['peak_component']}; "
        f"2024 {legacy_2024['peak_component']}"
    )
    ax_provenance.text(
        0.0,
        0.27,
        provenance,
        va="top",
        ha="left",
        fontsize=7.3,
        linespacing=1.25,
        transform=ax_provenance.transAxes,
    )

    fig.suptitle("Westlands current-AOI replay: legacy max-pixel vs coherent-priority gate", fontsize=11)
    png_path = OUT_DIR / "Figure_3_replay_modes.png"
    pdf_path = OUT_DIR / "Figure_3_replay_modes.pdf"
    fig.savefig(png_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    Image.open(png_path).convert("RGB").save(pdf_path, "PDF", resolution=220)


if __name__ == "__main__":
    sys.exit(main())
