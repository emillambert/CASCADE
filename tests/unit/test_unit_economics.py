from __future__ import annotations

import json
from pathlib import Path

import pytest

from unit_economics import (
    MILESTONES,
    carbon_mrv_musd,
    contribution_margin_per_ha,
    coverage_label,
    coverage_pct,
    first_break_even_milestone,
    fixed_cost_musd,
    gross_arr_musd,
    row_metrics,
    write_outputs,
)


def test_contribution_margin_and_revenue_helpers_match_expected_assumptions() -> None:
    assert contribution_margin_per_ha(False) == pytest.approx(2.85)
    assert contribution_margin_per_ha(True) == pytest.approx(3.10)
    assert gross_arr_musd(MILESTONES[0]) == pytest.approx(0.20)
    assert carbon_mrv_musd(MILESTONES[0]) == pytest.approx(0.0)
    assert carbon_mrv_musd(MILESTONES[1]) == pytest.approx(0.10)


def test_coverage_helpers_and_fixed_cost_scenarios_are_consistent() -> None:
    assert coverage_pct(MILESTONES[1]) == pytest.approx(28.268551236749117)
    assert coverage_label(MILESTONES[1]) == "28.3% SJV"
    assert fixed_cost_musd(MILESTONES[2], "low") < fixed_cost_musd(MILESTONES[2], "base")
    assert fixed_cost_musd(MILESTONES[2], "base") < fixed_cost_musd(MILESTONES[2], "high")


def test_row_metrics_are_internally_consistent() -> None:
    metrics = row_metrics(MILESTONES[2], "base")

    assert metrics["total_revenue_musd"] == pytest.approx(
        metrics["gross_arr_musd"] + metrics["carbon_mrv_musd"],
        abs=1e-2,
    )
    assert metrics["operating_margin_musd"] == pytest.approx(
        metrics["total_revenue_musd"]
        - metrics["platform_take_musd"]
        - metrics["variable_cost_musd"]
        - metrics["fixed_cost_musd"],
        abs=2e-2,
    )
    assert metrics["coverage_label"] == "11.0% US"


def test_break_even_summary_matches_current_rollout_story() -> None:
    assert first_break_even_milestone("low") == {
        "scenario": "low",
        "year": "Y2",
        "milestone": "California scale",
        "hectares": 400000,
        "fixed_cost_musd": 0.95,
    }
    assert first_break_even_milestone("base")["year"] == "Y3"
    assert first_break_even_milestone("high")["milestone"] == "US national"


def test_write_outputs_can_target_a_temporary_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "unit_economics"

    write_outputs(output_dir)

    metrics_path = output_dir / "unit_economics.json"
    table_path = output_dir / "unit_economics_table.tex"
    assert metrics_path.exists()
    assert table_path.exists()

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["break_even_summary"]["low"]["year"] == "Y2"
    assert "grant-funded" in table_path.read_text(encoding="utf-8")
