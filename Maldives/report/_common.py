"""
Shared data loading and styling for the Maldives CBA Report.
Every chapter imports from this module — single source of truth for data + visuals.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio

# ---------------------------------------------------------------------------
# Output format detection — switch Plotly to static images for DOCX/PDF
# ---------------------------------------------------------------------------
# Quarto sets QUARTO_FIG_FORMAT when rendering; fall back to checking
# QUARTO_DOCUMENT_OUTPUT_FORMAT or default to interactive HTML.
_fig_fmt = os.environ.get("QUARTO_FIG_FORMAT", "")
_out_fmt = os.environ.get("QUARTO_DOCUMENT_OUTPUT_FORMAT", "html")
if _fig_fmt in ("png", "pdf") or _out_fmt in ("docx", "pdf", "latex"):
    pio.renderers.default = "png"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPORT_DIR = Path(__file__).parent
PROJECT_DIR = REPORT_DIR.parent
OUTPUTS_DIR = PROJECT_DIR / "outputs"
DATA_DIR = PROJECT_DIR / "data"
MODEL_DIR = PROJECT_DIR / "model"

# ---------------------------------------------------------------------------
# Load all JSON outputs
# ---------------------------------------------------------------------------

def _load_json(name: str) -> dict:
    """Load a JSON file from the outputs directory."""
    path = OUTPUTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Output file not found: {path}")
    with open(path) as f:
        return json.load(f)


# Core results
cba = _load_json("cba_results.json")
summaries = _load_json("scenario_summaries.json")
sensitivity = _load_json("sensitivity_results.json")
monte_carlo = _load_json("monte_carlo_results.json")
multi_horizon = _load_json("multi_horizon_results.json")
financing = _load_json("financing_analysis.json")
distributional = _load_json("distributional_results.json")
mca = _load_json("mca_results.json")
learning_curves = _load_json("learning_curve_results.json")
climate_scenarios = _load_json("climate_scenario_results.json")
transport = _load_json("transport_results.json")

# Parameters CSV — skip comment lines manually (comment="#" breaks on quoted fields)
_param_path = MODEL_DIR / "parameters.csv"
with open(_param_path) as _f:
    _lines = [line for line in _f if not line.strip().startswith("#")]
import io as _io
parameters = pd.read_csv(_io.StringIO("".join(_lines)), on_bad_lines="skip")


def param(name: str, col: str = "Value", category: str | None = None) -> Any:
    """Look up a parameter from parameters.csv by name (case-insensitive substring match).
    
    Returns the numeric value by default. Use col='Unit' or col='Source' for other fields.
    Use category= to disambiguate when multiple categories share the same parameter name
    (e.g. 'Lifetime' exists in Solar, Battery, Diesel Gen, Cable).
    Examples:
        param("Discount Rate")                    → 0.06
        param("Diesel Price 2026")                → 0.85
        param("Lifetime", category="Battery")     → 15
        param("Learning Rate", category="Battery") → 0.18
    """
    mask = parameters["Parameter"].str.contains(name, case=False, na=False)
    if category is not None:
        mask = mask & parameters["Category"].str.contains(category, case=False, na=False)
    matches = parameters.loc[mask]
    if matches.empty:
        raise KeyError(f"Parameter '{name}' (category={category}) not found in parameters.csv")
    val = matches.iloc[0][col]
    # Try to convert to float for numeric columns
    if col in ("Value", "Low", "High"):
        try:
            return float(val)
        except (ValueError, TypeError):
            return val
    return val


# Convenience: baseline system dict from CBA results
baseline = cba["baseline_system"]

# MC parameter count (count unique param names from sensitivity results for first scenario)
n_mc_params = len(sensitivity.get("bau", {}))


# ---------------------------------------------------------------------------
# Scenario metadata
# ---------------------------------------------------------------------------

SCENARIO_IDS = [
    "bau", "full_integration", "national_grid", "islanded_green",
    "nearshore_solar", "maximum_re", "lng_transition"
]

SCENARIO_LABELS = {
    "bau": "S1 — BAU (Diesel)",
    "full_integration": "S2 — Full Integration",
    "national_grid": "S3 — National Grid",
    "islanded_green": "S4 — Islanded Green",
    "nearshore_solar": "S5 — Near-Shore Solar",
    "maximum_re": "S6 — Maximum RE",
    "lng_transition": "S7 — LNG Transition",
}

SCENARIO_SHORT = {
    "bau": "S1 BAU",
    "full_integration": "S2 FI",
    "national_grid": "S3 NG",
    "islanded_green": "S4 IG",
    "nearshore_solar": "S5 NS",
    "maximum_re": "S6 MR",
    "lng_transition": "S7 LNG",
}

SCENARIO_COLORS = {
    "bau": "#6c757d",            # Gray
    "full_integration": "#0d6efd",  # Blue
    "national_grid": "#198754",     # Green
    "islanded_green": "#0dcaf0",    # Teal
    "nearshore_solar": "#fd7e14",   # Orange
    "maximum_re": "#ffc107",        # Gold
    "lng_transition": "#6f42c1",    # Purple
}

ALT_SCENARIOS = [s for s in SCENARIO_IDS if s != "bau"]

# Convenience: min/max savings across alternative scenarios
_alt_savings = [cba["incremental_vs_bau"][s]["npv_savings"] for s in ALT_SCENARIOS]
savings_min_b = min(_alt_savings) / 1e9
savings_max_b = max(_alt_savings) / 1e9

# Convenience: BCR and IRR ranges across alt scenarios
_alt_bcrs = [cba["incremental_vs_bau"][s]["bcr"] for s in ALT_SCENARIOS]
_alt_irrs = [cba["incremental_vs_bau"][s]["irr"] for s in ALT_SCENARIOS if cba["incremental_vs_bau"][s].get("irr")]
bcr_min = min(_alt_bcrs)
bcr_max = max(_alt_bcrs)
irr_min = min(_alt_irrs)
irr_max = max(_alt_irrs)

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_usd(value: float, unit: str = "B") -> str:
    """Format USD values. unit='B' for billions, 'M' for millions."""
    if unit == "B":
        return f"${value / 1e9:,.1f}B"
    elif unit == "M":
        return f"${value / 1e6:,.0f}M"
    else:
        return f"${value:,.0f}"


def fmt_pct(value: float, decimals: int = 1) -> str:
    """Format as percentage."""
    return f"{value * 100:,.{decimals}f}%"


def fmt_ratio(value: float, decimals: int = 1) -> str:
    """Format as ratio (e.g., BCR)."""
    return f"{value:,.{decimals}f}×"


def fmt_years(value: int) -> str:
    """Format payback years."""
    return f"{value} years"


# ---------------------------------------------------------------------------
# Key results accessors
# ---------------------------------------------------------------------------

def get_npv(scenario: str) -> dict:
    """Get NPV results for a scenario."""
    return cba["npv_results"][scenario]


def get_incremental(scenario: str) -> dict:
    """Get incremental-vs-BAU results for an alt scenario."""
    return cba["incremental_vs_bau"][scenario]


def get_summary(scenario: str) -> dict:
    """Get scenario summary (costs, emissions, RE share)."""
    return summaries[scenario]


# ---------------------------------------------------------------------------
# Chart template — consistent styling across all figures
# ---------------------------------------------------------------------------

CHART_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, Segoe UI, Helvetica, sans-serif", size=13, color="#2c3e50"),
        title=dict(font=dict(size=18, color="#1a1a2e"), x=0.02, xanchor="left"),
        plot_bgcolor="#fafafa",
        paper_bgcolor="white",
        colorway=list(SCENARIO_COLORS.values()),
        xaxis=dict(gridcolor="#e9ecef", linecolor="#dee2e6", zerolinecolor="#dee2e6"),
        yaxis=dict(gridcolor="#e9ecef", linecolor="#dee2e6", zerolinecolor="#dee2e6"),
        legend=dict(
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#dee2e6",
            borderwidth=1,
            font=dict(size=11),
        ),
        margin=dict(l=60, r=30, t=60, b=50),
    )
)

pio.templates["maldives"] = CHART_TEMPLATE
pio.templates.default = "maldives"


# ---------------------------------------------------------------------------
# Reusable chart builders
# ---------------------------------------------------------------------------

def bar_scenario_comparison(
    values: dict[str, float],
    title: str,
    yaxis_title: str,
    value_format: str = "$.3s",
    highlight_bau: bool = True,
    horizontal: bool = False,
) -> go.Figure:
    """
    Standard bar chart comparing a metric across scenarios.
    values: {scenario_id: value}
    """
    scenarios = list(values.keys())
    vals = list(values.values())
    colors = [SCENARIO_COLORS.get(s, "#333") for s in scenarios]
    labels = [SCENARIO_SHORT.get(s, s) for s in scenarios]

    if highlight_bau and "bau" in scenarios:
        idx = scenarios.index("bau")
        colors[idx] = "#b0b0b0"  # dimmer gray for BAU

    if horizontal:
        fig = go.Figure(go.Bar(
            y=labels, x=vals, orientation="h",
            marker_color=colors,
            text=[f"{v:,.0f}" for v in vals],
            textposition="outside",
        ))
        fig.update_layout(title=title, xaxis_title=yaxis_title, yaxis_title="")
    else:
        fig = go.Figure(go.Bar(
            x=labels, y=vals,
            marker_color=colors,
            text=[f"{v:,.0f}" for v in vals],
            textposition="outside",
        ))
        fig.update_layout(title=title, yaxis_title=yaxis_title, xaxis_title="")

    fig.update_layout(
        height=450,
        showlegend=False,
    )
    return fig


def make_summary_table() -> pd.DataFrame:
    """Build the master scenario comparison table."""
    rows = []
    for sid in SCENARIO_IDS:
        npv = get_npv(sid)
        inc = cba["incremental_vs_bau"].get(sid, {})
        smry = get_summary(sid)

        rows.append({
            "Scenario": SCENARIO_SHORT[sid],
            "PV Total Costs ($B)": npv["pv_total_costs"] / 1e9,
            "LCOE ($/kWh)": npv["lcoe"],
            "NPV Savings ($B)": inc.get("npv_savings", 0) / 1e9,
            "BCR": inc.get("bcr", "—"),
            "IRR (%)": inc.get("irr", 0) * 100 if inc.get("irr") else "—",
            "Payback (yr)": inc.get("payback_years", "—"),
            "Emissions (MtCO₂)": smry["total_emissions_mtco2"],
            "Final RE (%)": smry["final_re_share"] * 100,
        })

    df = pd.DataFrame(rows)
    return df
