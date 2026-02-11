"""
Supplementary Financing Analysis (L5)
======================================

Standalone fiscal analysis that does NOT affect the economic CBA.

The economic CBA uses a social discount rate (6%) to answer
"Is the investment good for society?". This module answers a
different question: "What is the fiscal burden on the Government
of Maldives under different financing structures?"

Outputs (per scenario):
- Grant element of ADB concessional loan vs commercial benchmark
- Blended WACC (weighted average cost of capital)
- Annual debt service schedule (grace period + amortisation)
- Fiscal burden metrics (debt service / GDP, total interest paid)

All parameters flow from parameters.csv → config.py → get_config().
No hardcoded values.

Usage:
    # Standalone
    python -m model.financing_analysis

    # Called from run_cba.py after CBA completes
    from model.financing_analysis import run_financing_analysis
    results = run_financing_analysis(config, scenario_data)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from model.config import Config, get_config


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DebtServiceYear:
    """Single year of the debt service schedule."""
    year: int
    outstanding_principal: float  # start of year
    interest_payment: float
    principal_payment: float
    total_payment: float  # interest + principal


@dataclass
class LoanSchedule:
    """Full loan amortisation schedule."""
    loan_name: str
    principal: float
    interest_rate: float
    maturity_years: int
    grace_years: int
    annual_payments: List[DebtServiceYear] = field(default_factory=list)

    @property
    def total_interest_paid(self) -> float:
        return sum(p.interest_payment for p in self.annual_payments)

    @property
    def total_payments(self) -> float:
        return sum(p.total_payment for p in self.annual_payments)

    @property
    def peak_annual_service(self) -> float:
        if not self.annual_payments:
            return 0.0
        return max(p.total_payment for p in self.annual_payments)


@dataclass
class ScenarioFinancing:
    """Complete financing picture for one scenario."""
    scenario_name: str

    # CAPEX split
    total_capex_pv: float  # Present value of total CAPEX (from CBA)
    total_capex_nominal: float  # Nominal (undiscounted) sum of CAPEX
    adb_eligible_capex: float  # = nominal × adb_eligible_share
    commercial_capex: float  # = nominal × (1 - adb_eligible_share)

    # Rates
    adb_rate: float
    commercial_rate: float
    adb_eligible_share: float

    # Grant element
    grant_element_pct: float  # % concessionality of the ADB loan

    # WACC
    wacc: float  # Blended weighted average cost of capital

    # Loan schedules
    adb_loan: Optional[LoanSchedule] = None
    commercial_loan: Optional[LoanSchedule] = None

    # Fiscal metrics
    total_interest_paid: float = 0.0
    peak_annual_debt_service: float = 0.0
    peak_debt_service_pct_gdp: float = 0.0
    avg_annual_debt_service: float = 0.0

    # L21-22: Tariff / subsidy / fiscal context
    annual_subsidy_outlay: float = 0.0  # USD/yr — baseline government subsidy outlay (G-MO-05 rename)
    annual_tariff_revenue: float = 0.0  # USD/yr — current revenue at retail tariff
    tariff_revenue_mvr: float = 0.0  # MVR/yr — same in local currency
    avg_hh_annual_bill: float = 0.0  # USD/yr — average household electricity bill
    avg_hh_annual_bill_mvr: float = 0.0  # MVR/yr — same in local currency

    def to_dict(self) -> dict:
        d = {
            "scenario_name": self.scenario_name,
            "total_capex_nominal_m": round(self.total_capex_nominal / 1e6, 1),
            "adb_eligible_capex_m": round(self.adb_eligible_capex / 1e6, 1),
            "commercial_capex_m": round(self.commercial_capex / 1e6, 1),
            "adb_rate_pct": round(self.adb_rate * 100, 2),
            "commercial_rate_pct": round(self.commercial_rate * 100, 2),
            "adb_eligible_share_pct": round(self.adb_eligible_share * 100, 1),
            "grant_element_pct": round(self.grant_element_pct, 1),
            "wacc_pct": round(self.wacc * 100, 2),
            "total_interest_paid_m": round(self.total_interest_paid / 1e6, 1),
            "peak_annual_debt_service_m": round(self.peak_annual_debt_service / 1e6, 1),
            "peak_debt_service_pct_gdp": round(self.peak_debt_service_pct_gdp, 2),
            "avg_annual_debt_service_m": round(self.avg_annual_debt_service / 1e6, 1),
            # L21-22: Tariff / subsidy / fiscal context (base-year snapshot)
            "annual_subsidy_outlay_m": round(self.annual_subsidy_outlay / 1e6, 2),
            "annual_tariff_revenue_m": round(self.annual_tariff_revenue / 1e6, 1),
            "tariff_revenue_mvr_m": round(self.tariff_revenue_mvr / 1e6, 1),
            "avg_hh_annual_bill_usd": round(self.avg_hh_annual_bill, 0),
            "avg_hh_annual_bill_mvr": round(self.avg_hh_annual_bill_mvr, 0),
            "note_tariff_subsidy": "Base-year static estimates; fiscal_subsidy_savings in CBA uses time-varying phase-out schedule",
        }
        if self.adb_loan:
            d["adb_loan_schedule"] = [
                {
                    "year": p.year,
                    "outstanding": round(p.outstanding_principal / 1e6, 2),
                    "interest": round(p.interest_payment / 1e6, 2),
                    "principal": round(p.principal_payment / 1e6, 2),
                    "total": round(p.total_payment / 1e6, 2),
                }
                for p in self.adb_loan.annual_payments
            ]
        if self.commercial_loan:
            d["commercial_loan_schedule"] = [
                {
                    "year": p.year,
                    "outstanding": round(p.outstanding_principal / 1e6, 2),
                    "interest": round(p.interest_payment / 1e6, 2),
                    "principal": round(p.principal_payment / 1e6, 2),
                    "total": round(p.total_payment / 1e6, 2),
                }
                for p in self.commercial_loan.annual_payments
            ]
        return d


# =============================================================================
# CORE CALCULATIONS
# =============================================================================

def calculate_grant_element(
    concessional_rate: float,
    maturity_years: int,
    grace_years: int,
    commercial_rate: float,
) -> float:
    """
    Calculate the grant element of a concessional loan.

    Grant element = 1 - (PV of debt service at commercial rate) / Face value

    This is the standard OECD-DAC / IMF method:
    - During grace period: interest-only at concessional rate
    - After grace: equal principal repayments + interest on outstanding

    The PV of these payments is discounted at the commercial rate.
    The grant element measures how much "cheaper" the concessional
    loan is compared to market terms.

    Returns:
        Grant element as a fraction (e.g., 0.65 = 65% grant element)
    """
    if commercial_rate <= 0 or maturity_years <= 0:
        return 0.0

    face_value = 1.0  # normalised
    amort_years = maturity_years - grace_years

    if amort_years <= 0:
        # Bullet repayment at maturity — all interest-only
        pv = 0.0
        for t in range(1, maturity_years + 1):
            # Interest-only
            pv += concessional_rate * face_value / ((1 + commercial_rate) ** t)
        # Principal repaid at maturity
        pv += face_value / ((1 + commercial_rate) ** maturity_years)
        return 1.0 - pv

    # Standard amortisation with grace period
    principal_per_year = face_value / amort_years
    pv = 0.0
    outstanding = face_value

    for t in range(1, maturity_years + 1):
        interest = outstanding * concessional_rate
        if t <= grace_years:
            # Grace period: interest only, no principal
            principal = 0.0
        else:
            principal = principal_per_year
        payment = interest + principal
        pv += payment / ((1 + commercial_rate) ** t)
        outstanding -= principal

    return 1.0 - pv


def build_loan_schedule(
    loan_name: str,
    principal: float,
    interest_rate: float,
    maturity_years: int,
    grace_years: int,
    start_year: int,
) -> LoanSchedule:
    """
    Build year-by-year debt service schedule.

    - Grace period: interest-only payments
    - Amortisation period: equal principal repayments + interest on outstanding
    """
    schedule = LoanSchedule(
        loan_name=loan_name,
        principal=principal,
        interest_rate=interest_rate,
        maturity_years=maturity_years,
        grace_years=grace_years,
    )

    if principal <= 0:
        return schedule

    amort_years = maturity_years - grace_years
    if amort_years <= 0:
        amort_years = 1  # safety

    principal_per_year = principal / amort_years
    outstanding = principal

    for t in range(1, maturity_years + 1):
        year = start_year + t
        interest = outstanding * interest_rate
        if t <= grace_years:
            prin_payment = 0.0
        else:
            prin_payment = principal_per_year
        total = interest + prin_payment

        schedule.annual_payments.append(DebtServiceYear(
            year=year,
            outstanding_principal=outstanding,
            interest_payment=interest,
            principal_payment=prin_payment,
            total_payment=total,
        ))
        outstanding -= prin_payment
        outstanding = max(0, outstanding)  # avoid float rounding below zero

    return schedule


def calculate_wacc(
    adb_rate: float,
    commercial_rate: float,
    adb_share: float,
) -> float:
    """
    Weighted Average Cost of Capital.

    WACC = adb_share × adb_rate + (1 - adb_share) × commercial_rate

    This is a simplified WACC — no equity component because
    government/MDB infrastructure is 100% debt-financed.
    """
    return adb_share * adb_rate + (1 - adb_share) * commercial_rate


# =============================================================================
# SCENARIO-LEVEL ANALYSIS
# =============================================================================

def analyse_scenario(
    scenario_name: str,
    nominal_capex: float,
    pv_capex: float,
    config: Config,
) -> ScenarioFinancing:
    """
    Run complete financing analysis for one scenario.

    Args:
        scenario_name: Human-readable name
        nominal_capex: Undiscounted sum of all CAPEX over horizon
        pv_capex: Present value of CAPEX (from CBA)
        config: Model configuration
    """
    fin = config.financing
    gdp = fin.gdp_billion_usd * 1e9  # to USD

    # --- Split CAPEX ---
    adb_capex = nominal_capex * fin.adb_eligible_share
    commercial_capex = nominal_capex * (1 - fin.adb_eligible_share)

    # --- Grant element ---
    ge = calculate_grant_element(
        concessional_rate=fin.adb_sids_rate,
        maturity_years=fin.adb_sids_maturity,
        grace_years=fin.adb_sids_grace,
        commercial_rate=fin.commercial_interest_rate,
    )

    # --- WACC ---
    wacc = calculate_wacc(
        adb_rate=fin.adb_sids_rate,
        commercial_rate=fin.commercial_interest_rate,
        adb_share=fin.adb_eligible_share,
    )

    # --- Loan schedules ---
    # Assume disbursement at base_year (simplification — real projects draw down
    # over construction period, but this gives a clean illustrative schedule)
    start_year = config.base_year

    adb_loan = build_loan_schedule(
        loan_name="ADB SIDS Concessional",
        principal=adb_capex,
        interest_rate=fin.adb_sids_rate,
        maturity_years=fin.adb_sids_maturity,
        grace_years=fin.adb_sids_grace,
        start_year=start_year,
    )

    commercial_loan = build_loan_schedule(
        loan_name="Commercial",
        principal=commercial_capex,
        interest_rate=fin.commercial_interest_rate,
        maturity_years=fin.commercial_maturity,
        grace_years=fin.commercial_grace,
        start_year=start_year,
    )

    # --- Fiscal metrics ---
    total_interest = adb_loan.total_interest_paid + commercial_loan.total_interest_paid

    # Combined annual service (overlay the two schedules)
    combined_by_year: Dict[int, float] = {}
    for payment in adb_loan.annual_payments + commercial_loan.annual_payments:
        combined_by_year[payment.year] = combined_by_year.get(payment.year, 0) + payment.total_payment

    peak_service = max(combined_by_year.values()) if combined_by_year else 0.0
    avg_service = sum(combined_by_year.values()) / len(combined_by_year) if combined_by_year else 0.0
    # G-MO-02: Use year-specific GDP — project GDP forward from base year
    base_year = config.base_year
    gdp_growth = fin.gdp_growth_rate
    if combined_by_year:
        peak_year = max(combined_by_year, key=combined_by_year.get)
        years_forward = peak_year - base_year
        gdp_at_peak = gdp * (1 + gdp_growth) ** max(years_forward, 0)
    else:
        gdp_at_peak = gdp
    peak_pct_gdp = (peak_service / gdp_at_peak * 100) if gdp_at_peak > 0 else 0.0

    # --- L21-22: Tariff / subsidy / fiscal context ---
    cs = config.current_system
    econ = config.economics
    # Base-year demand for revenue/subsidy calculations (GWh → kWh)
    base_demand_gwh = config.demand.base_demand_gwh
    base_demand_kwh = base_demand_gwh * 1e6  # GWh → kWh

    # Annual tariff revenue = demand × retail tariff
    annual_tariff_revenue = base_demand_kwh * cs.current_retail_tariff
    tariff_revenue_mvr = annual_tariff_revenue * econ.exchange_rate_mvr_usd

    # Annual government subsidy = demand × subsidy per kWh
    # RE transition reduces fuel cost → reduces needed subsidy proportionally
    annual_subsidy_baseline = base_demand_kwh * cs.current_subsidy_per_kwh

    # Average household annual bill
    # 12 months × avg monthly consumption × retail tariff
    avg_hh_annual_bill = 12 * cs.avg_hh_monthly_kwh * cs.current_retail_tariff
    avg_hh_annual_bill_mvr = avg_hh_annual_bill * econ.exchange_rate_mvr_usd

    return ScenarioFinancing(
        scenario_name=scenario_name,
        total_capex_pv=pv_capex,
        total_capex_nominal=nominal_capex,
        adb_eligible_capex=adb_capex,
        commercial_capex=commercial_capex,
        adb_rate=fin.adb_sids_rate,
        commercial_rate=fin.commercial_interest_rate,
        adb_eligible_share=fin.adb_eligible_share,
        grant_element_pct=ge * 100,
        wacc=wacc,
        adb_loan=adb_loan,
        commercial_loan=commercial_loan,
        total_interest_paid=total_interest,
        peak_annual_debt_service=peak_service,
        peak_debt_service_pct_gdp=peak_pct_gdp,
        avg_annual_debt_service=avg_service,
        # L21-22: Tariff / subsidy / fiscal context
        annual_subsidy_outlay=annual_subsidy_baseline,
        annual_tariff_revenue=annual_tariff_revenue,
        tariff_revenue_mvr=tariff_revenue_mvr,
        avg_hh_annual_bill=avg_hh_annual_bill,
        avg_hh_annual_bill_mvr=avg_hh_annual_bill_mvr,
    )


# =============================================================================
# ENTRY POINTS
# =============================================================================

def run_financing_analysis(
    config: Config,
    scenario_data: dict,
    cba_results: dict,
) -> Dict[str, ScenarioFinancing]:
    """
    Run financing analysis for all non-BAU scenarios.

    Args:
        config: Model configuration
        scenario_data: Dict from run_scenarios() — has ["results"] per scenario
        cba_results: Dict from run_cba() — has ["npv_result"] per scenario

    Returns:
        Dict mapping scenario key → ScenarioFinancing
    """
    results: Dict[str, ScenarioFinancing] = {}

    scenario_labels = {
        "full_integration": "Full Integration",
        "national_grid": "National Grid",
        "islanded_green": "Islanded Green",
        "nearshore_solar": "Near-Shore Solar",
        "maximum_re": "Maximum RE",
        "lng_transition": "LNG Transition",
    }

    for key, label in scenario_labels.items():
        # Nominal (undiscounted) sum of CAPEX across all years
        annual_costs = scenario_data[key]["results"].annual_costs
        nominal_capex = sum(c.total_capex for c in annual_costs.values())

        # PV of CAPEX from CBA
        pv_capex = cba_results[key]["npv_result"].pv_capex

        results[key] = analyse_scenario(
            scenario_name=label,
            nominal_capex=nominal_capex,
            pv_capex=pv_capex,
            config=config,
        )

    return results


def print_financing_summary(results: Dict[str, ScenarioFinancing], config: Config):
    """Print financing analysis summary to console."""
    fin = config.financing
    print("=" * 80)
    print("  SUPPLEMENTARY FINANCING ANALYSIS (L5)")
    print("  Note: This is a fiscal analysis — does NOT affect economic CBA results.")
    print("=" * 80)
    print()
    print(f"  ADB SIDS concessional:  {fin.adb_sids_rate:.1%} / {fin.adb_sids_maturity}yr / {fin.adb_sids_grace}yr grace")
    print(f"  Commercial benchmark:   {fin.commercial_interest_rate:.2%}")
    print(f"  ADB-eligible CAPEX:     {fin.adb_eligible_share:.0%}")
    print()

    # Grant element (same for all scenarios — depends only on terms)
    ge = list(results.values())[0].grant_element_pct if results else 0
    wacc = list(results.values())[0].wacc if results else 0
    print(f"  Grant element:          {ge:.1f}%")
    print(f"  Blended WACC:           {wacc:.2%}")
    print()

    # Summary table
    print(f"{'Scenario':<22} {'Nominal CAPEX':>14} {'ADB Loan':>12} {'Comm. Loan':>12} {'Total Interest':>15} {'Peak Svc/yr':>13} {'% GDP':>8}")
    print("-" * 100)

    for key, sf in results.items():
        print(
            f"{sf.scenario_name:<22} "
            f"${sf.total_capex_nominal/1e6:>12,.0f}M "
            f"${sf.adb_eligible_capex/1e6:>10,.0f}M "
            f"${sf.commercial_capex/1e6:>10,.0f}M "
            f"${sf.total_interest_paid/1e6:>13,.0f}M "
            f"${sf.peak_annual_debt_service/1e6:>11,.0f}M "
            f"{sf.peak_debt_service_pct_gdp:>6.2f}%"
        )

    # L21-22: Tariff / subsidy / fiscal context (base-year snapshot)
    print()
    cs = config.current_system
    econ = config.economics
    first_sf = list(results.values())[0] if results else None
    if first_sf:
        print(f"  Tariff & Subsidy Context (base-year {config.base_year}, {config.demand.base_demand_gwh:,.0f} GWh):")
        print(f"    Retail tariff:        ${cs.current_retail_tariff:.2f}/kWh ({cs.current_retail_tariff * econ.exchange_rate_mvr_usd:.2f} MVR/kWh)")
        print(f"    Government subsidy:   ${cs.current_subsidy_per_kwh:.2f}/kWh")
        print(f"    Avg HH annual bill:   ${first_sf.avg_hh_annual_bill:,.0f} ({first_sf.avg_hh_annual_bill_mvr:,.0f} MVR)")
        print(f"    Annual tariff revenue: ${first_sf.annual_tariff_revenue/1e6:,.0f}M ({first_sf.tariff_revenue_mvr/1e6:,.0f}M MVR)")
        print(f"    Annual subsidy outlay: ${first_sf.annual_subsidy_outlay/1e6:,.0f}M")
        bau_growth = config.demand.growth_rates.get('status_quo', 0.05)
        print(f"    Note: Static base-year estimates. With {bau_growth*100:.0f}%/yr demand growth,")
        print(f"          year-30 subsidy could reach ~${first_sf.annual_subsidy_outlay * (1 + bau_growth)**30 / 1e6:,.0f}M/yr at constant rates.")

    print()


def save_financing_results(results: Dict[str, ScenarioFinancing], output_dir: str):
    """Save financing analysis to JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    output = {
        key: sf.to_dict()
        for key, sf in results.items()
    }

    with open(output_path / "financing_analysis.json", "w") as f:
        json.dump(output, f, indent=2)


# =============================================================================
# STANDALONE CLI
# =============================================================================

def main():
    """Run financing analysis standalone (without full CBA)."""
    from model.scenarios.status_quo import StatusQuoScenario
    from model.scenarios.green_transition import NationalGridScenario
    from model.scenarios.one_grid import FullIntegrationScenario
    from model.scenarios.islanded_green import IslandedGreenScenario
    from model.scenarios.nearshore_solar import NearShoreSolarScenario
    from model.scenarios.maximum_re import MaximumREScenario
    from model.scenarios.lng_transition import LNGTransitionScenario
    from model.cba import CBACalculator

    print("=" * 70)
    print("  STANDALONE FINANCING ANALYSIS")
    print("=" * 70)
    print()

    config = get_config()
    print(f"Loading config... Horizon {config.base_year}-{config.end_year}")
    print()

    # Run scenarios (needed for CAPEX streams)
    print("Running scenarios for CAPEX extraction...")
    scenarios = {
        "bau": StatusQuoScenario(config),
        "full_integration": FullIntegrationScenario(config),
        "national_grid": NationalGridScenario(config),
        "islanded_green": IslandedGreenScenario(config),
        "nearshore_solar": NearShoreSolarScenario(config),
        "maximum_re": MaximumREScenario(config),
        "lng_transition": LNGTransitionScenario(config),
    }

    scenario_data = {}
    for key, scen in scenarios.items():
        results = scen.run()
        if key != "bau":
            scen.calculate_benefits_vs_baseline(scenarios["bau"].results if hasattr(scenarios["bau"], 'results') else scenario_data.get("bau", {}).get("results"))
        scenario_data[key] = {
            "scenario": scen,
            "results": results,
            "summary": scen.get_summary(),
        }

    # Quick CBA for PV CAPEX
    calc = CBACalculator(config)
    cba_results = {}
    for key in ["full_integration", "national_grid", "islanded_green",
                 "nearshore_solar", "maximum_re", "lng_transition"]:
        npv = calc.calculate_npv(scenario_data[key]["results"])
        cba_results[key] = {"npv_result": npv}

    # Financing analysis
    fin_results = run_financing_analysis(config, scenario_data, cba_results)
    print_financing_summary(fin_results, config)
    save_financing_results(fin_results, "outputs")
    print("Results saved to outputs/financing_analysis.json")


if __name__ == "__main__":
    main()
