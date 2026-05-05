# SPDX-License-Identifier: MIT
"""Five-year geography-expansion unit economics for the CASCADE hosted-payload concept."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from cascade.paths import BUILD_ECONOMICS_DIR


PRICE_PER_HA = 4.00
PLATFORM_TAKE_RATE = 0.20
VARIABLE_SERVICE_COST_PER_HA = 0.35
CARBON_MRV_PER_HA = 0.50
CARBON_FRACTION = 0.50

SCENARIO_FIXED_COST_MUSD = {
    "low": 0.95,
    "base": 1.50,
    "high": 2.30,
}


@dataclass(frozen=True)
class MarketReference:
    label: str
    hectares: int
    source: str


MARKET_REFERENCES = {
    "sjv": MarketReference(
        label="California San Joaquin Valley",
        hectares=1_415_000,
        source="USDA 2022 Census county-level irrigation aggregation for the SJV reference geography",
    ),
    "us": MarketReference(
        label="United States irrigated land",
        hectares=22_700_000,
        source="USDA 2022 Census of Agriculture irrigated land baseline",
    ),
    "eu": MarketReference(
        label="European Union irrigated agriculture",
        hectares=11_000_000,
        source="Eurostat 2020 agricultural census / integrated farm statistics irrigation baseline",
    ),
    "eu_us": MarketReference(
        label="EU + U.S. irrigated agriculture",
        hectares=33_700_000,
        source="Combined Eurostat and USDA irrigation baselines",
    ),
    "global": MarketReference(
        label="Global irrigated agriculture",
        hectares=300_000_000,
        source="FAO AQUASTAT area equipped for irrigation baseline",
    ),
}


@dataclass(frozen=True)
class Milestone:
    year: str
    label: str
    geography: str
    hectares: int
    coverage_ref: str
    satellite_multiplier: float
    mrv_enabled: bool
    distribution: str
    rationale: str
    coverage_label_override: str | None = None
    footnote: str | None = None


MILESTONES = (
    Milestone(
        year="Y1",
        label="Anchor pilot",
        geography="EU or SJV",
        hectares=50_000,
        coverage_ref="sjv",
        satellite_multiplier=1.0,
        mrv_enabled=False,
        distribution="Validation-geography-dependent anchor customer",
        rationale=(
            "Modeled as a co-funded bridge-to-MVP pilot; the anchor geography can land "
            "in the EU wedge or the San Joaquin Valley depending on validation access."
        ),
        coverage_label_override="<=5% region",
    ),
    Milestone(
        year="Y2",
        label="Benelux + CA scale",
        geography="EU + California",
        hectares=400_000,
        coverage_ref="sjv",
        satellite_multiplier=1.0,
        mrv_enabled=True,
        distribution="Advisor / crop-platform API plus direct enterprise",
        rationale=(
            "Combines the Benelux/EU wedge with California validation-scale coverage while "
            "activating a Year 2 soil-carbon MRV add-on revenue stream."
        ),
        coverage_label_override="EU wedge + SJV",
    ),
    Milestone(
        year="Y3",
        label="EU + U.S. national",
        geography="EU + U.S. irrigated",
        hectares=2_500_000,
        coverage_ref="us",
        satellite_multiplier=1.4,
        mrv_enabled=True,
        distribution="Climate FieldView + John Deere Operations Center",
        rationale=(
            "Captures about 11.0% of U.S. irrigated acreage and reaches first commercial scale "
            "with two platform channels."
        ),
    ),
    Milestone(
        year="Y4",
        label="EU expansion + intl. org pilots",
        geography="EU + U.S.",
        hectares=6_500_000,
        coverage_ref="eu_us",
        satellite_multiplier=1.4,
        mrv_enabled=True,
        distribution="EU/U.S. commercial channels plus World Bank/FAO/CGIAR pilots",
        rationale=(
            "Expands commercial EU/U.S. coverage while running grant- or donor-funded "
            "international-organization pilots outside commercial TAM."
        ),
        footnote="b",
    ),
    Milestone(
        year="Y5",
        label="Global commercial",
        geography="Global (commercial)",
        hectares=18_000_000,
        coverage_ref="global",
        satellite_multiplier=1.8,
        mrv_enabled=True,
        distribution="FieldView + xarvio + John Deere + CropX",
        rationale=(
            "Scales to a multi-platform global offering at roughly 6.0% of worldwide irrigated "
            "farmland without changing the onboard architecture."
        ),
    ),
)

NON_COMMERCIAL_TRACK = {
    "label": "International organization pilots",
    "partners": ["World Bank", "FAO", "CGIAR"],
    "funding_model": "grant/donor funded",
    "commercial_tam_musd": 0.0,
    "role": (
        "Zero-commercial-TAM coverage, independent validation data, and food-security "
        "impact credentials that feed back into the commercial path."
    ),
}


def contribution_margin_per_ha(mrv_enabled: bool) -> float:
    base_margin = PRICE_PER_HA * (1.0 - PLATFORM_TAKE_RATE) - VARIABLE_SERVICE_COST_PER_HA
    if not mrv_enabled:
        return base_margin
    return base_margin + CARBON_MRV_PER_HA * CARBON_FRACTION


def coverage_pct(milestone: Milestone) -> float:
    reference = MARKET_REFERENCES[milestone.coverage_ref]
    return milestone.hectares / reference.hectares * 100.0


def coverage_label(milestone: Milestone) -> str:
    if milestone.coverage_label_override:
        return milestone.coverage_label_override
    reference = MARKET_REFERENCES[milestone.coverage_ref]
    ref_name = {
        "sjv": "SJV",
        "us": "US",
        "eu_us": "EU+US",
        "global": "global",
    }.get(milestone.coverage_ref, reference.label)
    return f"{coverage_pct(milestone):.1f}% {ref_name}"


def gross_arr_musd(milestone: Milestone) -> float:
    return PRICE_PER_HA * milestone.hectares / 1_000_000


def carbon_mrv_musd(milestone: Milestone) -> float:
    if not milestone.mrv_enabled:
        return 0.0
    return CARBON_MRV_PER_HA * CARBON_FRACTION * milestone.hectares / 1_000_000


def fixed_cost_musd(milestone: Milestone, scenario: str) -> float:
    return SCENARIO_FIXED_COST_MUSD[scenario] * milestone.satellite_multiplier


def row_metrics(milestone: Milestone, scenario: str) -> dict:
    gross_arr = gross_arr_musd(milestone)
    platform_take = PRICE_PER_HA * PLATFORM_TAKE_RATE * milestone.hectares / 1_000_000
    variable_cost = VARIABLE_SERVICE_COST_PER_HA * milestone.hectares / 1_000_000
    carbon_mrv = carbon_mrv_musd(milestone)
    total_revenue = gross_arr + carbon_mrv
    fixed_cost = fixed_cost_musd(milestone, scenario)
    operating_margin = total_revenue - platform_take - variable_cost - fixed_cost
    operating_margin_pct = operating_margin / total_revenue * 100.0
    reference = MARKET_REFERENCES[milestone.coverage_ref]

    return {
        "year": milestone.year,
        "milestone": milestone.label,
        "geography": milestone.geography,
        "hectares": milestone.hectares,
        "coverage_pct": round(coverage_pct(milestone), 1),
        "coverage_label": coverage_label(milestone),
        "coverage_reference": reference.label,
        "coverage_reference_hectares": reference.hectares,
        "satellite_multiplier": milestone.satellite_multiplier,
        "distribution": milestone.distribution,
        "mrv_enabled": milestone.mrv_enabled,
        "gross_arr_musd": round(gross_arr, 2),
        "carbon_mrv_musd": round(carbon_mrv, 2),
        "total_revenue_musd": round(total_revenue, 2),
        "platform_take_musd": round(platform_take, 2),
        "variable_cost_musd": round(variable_cost, 2),
        "fixed_cost_musd": round(fixed_cost, 2),
        "operating_margin_musd": round(operating_margin, 2),
        "operating_margin_pct": round(operating_margin_pct, 1),
        "contribution_margin_per_ha_usd": round(contribution_margin_per_ha(milestone.mrv_enabled), 2),
        "rationale": milestone.rationale,
    }


def first_break_even_milestone(scenario: str) -> dict | None:
    for milestone in MILESTONES:
        metrics = row_metrics(milestone, scenario)
        if metrics["operating_margin_musd"] >= 0:
            return {
                "scenario": scenario,
                "year": metrics["year"],
                "milestone": metrics["milestone"],
                "hectares": metrics["hectares"],
                "fixed_cost_musd": metrics["fixed_cost_musd"],
            }
    return None


def hectares_scale_bar(metrics: dict) -> str:
    min_log = math.log10(min(m.hectares for m in MILESTONES))
    max_log = math.log10(max(m.hectares for m in MILESTONES))
    value = (math.log10(float(metrics["hectares"])) - min_log) / max(max_log - min_log, 1e-9)
    width_cm = 0.18 + value * 1.14
    return f"\\makebox[1.35cm][l]{{\\textcolor{{codeblue}}{{\\rule{{{width_cm:.2f}cm}}{{0.7ex}}}}}}"


def latex_text(value: str) -> str:
    return str(value).replace("<=", "$\\leq$").replace("%", "\\%").replace("intl. org", "intl.\\ org")


def latex_rows() -> str:
    rows = []
    for milestone in MILESTONES:
        metrics = row_metrics(milestone, "low")
        # Paper-facing table treats Y1 as grant-funded / bridge-to-MVP rather than quoting a negative margin percent.
        if metrics["year"] == "Y1":
            op_margin_cell = "grant-funded"
        else:
            op_margin_cell = f'{metrics["operating_margin_pct"]:.1f}\\%'

        row = dict(metrics)
        for field in ("milestone", "geography", "coverage_label"):
            row[field] = latex_text(row[field])
        if milestone.footnote:
            row["milestone"] = f"{row['milestone']}\\textsuperscript{{{milestone.footnote}}}"
        row["op_margin_cell"] = op_margin_cell
        row["hectares_scale_bar"] = hectares_scale_bar(metrics)
        rows.append(
            "    {year} & {milestone} & {geography} & {coverage_label} & {hectares_scale_bar} & "
            "${total_revenue_musd:.2f}\\,M$ & {op_margin_cell} \\\\".format(**row)
        )
    return "\n".join(rows)


def paper_rollout_rows() -> list[dict]:
    rows = []
    for milestone in MILESTONES:
        metrics = row_metrics(milestone, "low")
        rows.append(
            {
                "year": metrics["year"],
                "milestone": metrics["milestone"],
                "geography": metrics["geography"],
                "coverage_label": metrics["coverage_label"],
                "hectares": metrics["hectares"],
                "total_revenue_musd": metrics["total_revenue_musd"],
                "operating_margin": "grant-funded"
                if metrics["year"] == "Y1"
                else f"{metrics['operating_margin_pct']:.1f}%",
                **({"footnote": milestone.footnote} if milestone.footnote else {}),
            }
        )
    return rows


def write_outputs(output_dir: Path | None = None) -> None:
    output_dir = output_dir or BUILD_ECONOMICS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "market_references": {
            key: asdict(value) for key, value in MARKET_REFERENCES.items()
        },
        "revenue_assumptions": {
            "price_per_ha_usd": PRICE_PER_HA,
            "platform_take_rate": PLATFORM_TAKE_RATE,
            "variable_service_cost_per_ha_usd": VARIABLE_SERVICE_COST_PER_HA,
            "carbon_mrv_per_ha_usd": CARBON_MRV_PER_HA,
            "carbon_fraction": CARBON_FRACTION,
            "contribution_margin_no_mrv_usd_per_ha": round(contribution_margin_per_ha(False), 2),
            "contribution_margin_with_mrv_usd_per_ha": round(contribution_margin_per_ha(True), 2),
        },
        "milestones_low_scenario": [row_metrics(m, "low") for m in MILESTONES],
        "milestones_base_scenario": [row_metrics(m, "base") for m in MILESTONES],
        "milestones_high_scenario": [row_metrics(m, "high") for m in MILESTONES],
        "paper_rollout_rows": paper_rollout_rows(),
        "non_commercial_track": NON_COMMERCIAL_TRACK,
        "break_even_summary": {
            scenario: first_break_even_milestone(scenario)
            for scenario in SCENARIO_FIXED_COST_MUSD
        },
    }
    (output_dir / "unit_economics.json").write_text(
        json.dumps(metrics, indent=2) + "\n",
        encoding="utf-8",
    )

    latex = (
        "% Auto-generated by unit_economics.py\n"
        "% Paper-facing table uses the low/design-to-cost case.\n"
        "% Scale is a log-scaled hectares trajectory bar.\n"
        "\\begin{tabular*}{\\linewidth}{@{\\extracolsep{\\fill}}l>{\\raggedright\\arraybackslash}p{2.75cm}>{\\raggedright\\arraybackslash}p{2.35cm}>{\\raggedright\\arraybackslash}p{2.35cm}c>{\\raggedleft\\arraybackslash}p{1.35cm}>{\\raggedleft\\arraybackslash}p{1.65cm}@{}}\n"
        "\\toprule\n"
        "Year & Milestone & Geography & Coverage & Scale & Revenue & Op. margin \\\\\n"
        "\\midrule\n"
        f"{latex_rows()}\n"
        "\\bottomrule\n"
        "\\end{tabular*}\n"
    )
    (output_dir / "unit_economics_table.tex").write_text(latex, encoding="utf-8")


if __name__ == "__main__":
    write_outputs()
