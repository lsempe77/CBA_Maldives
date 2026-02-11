"""
Maldives Energy CBA Model - Main Entry Point
=============================================

This script runs the complete Cost-Benefit Analysis for the four
energy transition scenarios:

1. BAU (Status Quo) - Continued diesel dependence
2. Full Integration - India cable + inter-island grid + domestic RE
3. National Grid - Inter-island grid + RE (no India cable)
4. Islanded Green - Individual island RE systems (no grids)

Usage:
    python run_cba.py [--output OUTPUT_DIR] [--sensitivity] [--monte-carlo N]

Author: CBA Model Team
Date: 2024
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
import json

# Add model to path
sys.path.insert(0, str(Path(__file__).parent))

from model.config import Config, get_config
from model.scenarios.status_quo import StatusQuoScenario
from model.scenarios.green_transition import NationalGridScenario
from model.scenarios.one_grid import FullIntegrationScenario
from model.scenarios.islanded_green import IslandedGreenScenario
from model.scenarios.nearshore_solar import NearShoreSolarScenario
from model.scenarios.maximum_re import MaximumREScenario
from model.scenarios.lng_transition import LNGTransitionScenario
from model.cba import CBACalculator, CBAComparison, SensitivityAnalysis
from model.cba.mca_analysis import run_mca, print_mca_results, weight_sensitivity
from model.financing_analysis import (
    run_financing_analysis,
    print_financing_summary,
    save_financing_results,
)
from model.distributional_analysis import (
    run_distributional_analysis,
    print_distributional_summary,
    save_distributional_results,
)
from model.transport_analysis import (
    run_transport_analysis,
    print_transport_summary,
    save_transport_results,
)


def print_header():
    """Print model header."""
    print("=" * 70)
    print("  MALDIVES ENERGY TRANSITION - COST-BENEFIT ANALYSIS MODEL")
    print("=" * 70)
    print(f"  Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


def run_scenarios(config: Config) -> dict:
    """
    Run all four scenarios and return results.
    """
    print("Running scenarios...")
    print("-" * 50)
    
    # S1: BAU / Status Quo
    print("  1. BAU (Diesel)...")
    sq = StatusQuoScenario(config)
    sq_results = sq.run()
    sq_summary = sq.get_summary()
    print(f"     ✓ Complete (Total costs: ${sq_summary['total_costs_million']:,.0f}M)")
    
    # S2: Full Integration
    print("  2. Full Integration (India + inter-island + RE)...")
    fi = FullIntegrationScenario(config)
    fi_results = fi.run()
    fi_summary = fi.get_summary()
    print(f"     ✓ Complete (Total costs: ${fi_summary['total_costs_million']:,.0f}M)")
    
    # S3: National Grid
    print("  3. National Grid (inter-island + RE, no India)...")
    ng = NationalGridScenario(config)
    ng_results = ng.run()
    ng_summary = ng.get_summary()
    print(f"     ✓ Complete (Total costs: ${ng_summary['total_costs_million']:,.0f}M)")
    
    # S4: Islanded Green
    print("  4. Islanded Green (per-island RE, no grids)...")
    ig = IslandedGreenScenario(config)
    ig_results = ig.run()
    ig_summary = ig.get_summary()
    print(f"     ✓ Complete (Total costs: ${ig_summary['total_costs_million']:,.0f}M)")
    
    # S5: Near-Shore Solar
    print("  5. Near-Shore Solar (NG + uninhabited island solar)...")
    ns = NearShoreSolarScenario(config)
    ns_results = ns.run()
    ns_summary = ns.get_summary()
    print(f"     ✓ Complete (Total costs: ${ns_summary['total_costs_million']:,.0f}M)")
    
    # S6: Maximum RE
    print("  6. Maximum RE (near-shore + floating solar)...")
    mx = MaximumREScenario(config)
    mx_results = mx.run()
    mx_summary = mx.get_summary()
    print(f"     ✓ Complete (Total costs: ${mx_summary['total_costs_million']:,.0f}M)")
    
    # S7: LNG Transition
    print("  7. LNG Transition (Malé LNG + outer island RE)...")
    lng = LNGTransitionScenario(config)
    lng_results = lng.run()
    lng_summary = lng.get_summary()
    print(f"     ✓ Complete (Total costs: ${lng_summary['total_costs_million']:,.0f}M)")
    
    # L4: Calculate benefits vs BAU baseline (populates annual_benefits incl. health)
    print("  Calculating benefits vs BAU baseline...")
    fi.calculate_benefits_vs_baseline(sq_results)
    ng.calculate_benefits_vs_baseline(sq_results)
    ig.calculate_benefits_vs_baseline(sq_results)
    ns.calculate_benefits_vs_baseline(sq_results)
    mx.calculate_benefits_vs_baseline(sq_results)
    lng.calculate_benefits_vs_baseline(sq_results)
    print(f"     ✓ Benefits calculated (fuel savings, emissions, health)")
    
    print()
    
    return {
        "bau": {
            "scenario": sq,
            "results": sq_results,
            "summary": sq_summary,
        },
        "full_integration": {
            "scenario": fi,
            "results": fi_results,
            "summary": fi_summary,
        },
        "national_grid": {
            "scenario": ng,
            "results": ng_results,
            "summary": ng_summary,
        },
        "islanded_green": {
            "scenario": ig,
            "results": ig_results,
            "summary": ig_summary,
        },
        "nearshore_solar": {
            "scenario": ns,
            "results": ns_results,
            "summary": ns_summary,
        },
        "maximum_re": {
            "scenario": mx,
            "results": mx_results,
            "summary": mx_summary,
        },
        "lng_transition": {
            "scenario": lng,
            "results": lng_results,
            "summary": lng_summary,
        },
    }


def run_cba(config: Config, scenario_data: dict) -> dict:
    """
    Run CBA calculations for 6 scenarios.
    Returns both per-scenario NPV results and the full CBAComparison object.
    """
    print("Running CBA calculations...")
    print("-" * 50)
    
    calculator = CBACalculator(config)
    
    # Use compare_all_scenarios to get full incremental analysis with IRR/payback
    comparison = calculator.compare_all_scenarios(
        status_quo_results=scenario_data["bau"]["results"],
        green_results=scenario_data["national_grid"]["results"],
        one_grid_results=scenario_data["full_integration"]["results"],
        islanded_green_results=scenario_data["islanded_green"]["results"],
        nearshore_solar_results=scenario_data["nearshore_solar"]["results"],
        maximum_re_results=scenario_data["maximum_re"]["results"],
        lng_transition_results=scenario_data["lng_transition"]["results"],
    )
    
    # Build results dict for backwards compatibility
    results = {}
    for name, npv_obj in [
        ("bau", comparison.bau),
        ("full_integration", comparison.full_integration),
        ("national_grid", comparison.national_grid),
        ("islanded_green", comparison.islanded_green),
        ("nearshore_solar", comparison.nearshore_solar),
        ("maximum_re", comparison.maximum_re),
        ("lng_transition", comparison.lng_transition),
    ]:
        results[name] = {
            "npv_result": npv_obj,
            "summary": scenario_data[name]["summary"],
        }
    
    # Attach the full comparison object for save_results
    results["_comparison"] = comparison
    
    print(f"  ✓ NPV calculations complete")
    print(f"  ✓ Incremental analysis complete (IRR, payback, BCR)")
    print(f"  ✓ All 7 scenarios analyzed")
    print()
    
    return results


def print_scenario_summary(scenario_data: dict):
    """Print summary of scenario results."""
    print("=" * 130)
    print("  SCENARIO SUMMARY (2024-2056)")
    print("=" * 130)
    print()
    
    scenarios = [
        ("bau", "BAU"),
        ("full_integration", "Full Integ"),
        ("national_grid", "Natl Grid"),
        ("islanded_green", "Islanded"),
        ("nearshore_solar", "NearShore"),
        ("maximum_re", "Max RE"),
        ("lng_transition", "LNG Trans"),
    ]
    
    header = f"{'Metric':<25}"
    for _, label in scenarios:
        header += f" {label:>14}"
    print(header)
    print("-" * 130)
    
    data = {k: scenario_data[k]["summary"] for k, _ in scenarios}
    
    # Total costs
    row = f"{'Total Costs (M USD)':<25}"
    for k, _ in scenarios:
        row += f" ${data[k]['total_costs_million']:>12,.0f}"
    print(row)
    for cost_key, label in [("total_capex_million", "  - CAPEX"), ("total_opex_million", "  - OPEX"), ("total_fuel_million", "  - Fuel")]:
        row = f"{label:<25}"
        for k, _ in scenarios:
            row += f" ${data[k][cost_key]:>12,.0f}"
        print(row)
    
    # Emissions
    row = f"{'Total Emissions (MtCO2)':<25}"
    for k, _ in scenarios:
        row += f" {data[k]['total_emissions_mtco2']:>13.2f}"
    print(row)
    
    # Final RE share
    row = f"{'Final RE Share':<25}"
    for k, _ in scenarios:
        row += f" {data[k]['final_re_share']:>13.1%}"
    print(row)
    
    print()


def print_cba_summary(cba_results: dict, config: Config):
    """Print CBA summary for 4 scenarios."""
    print("=" * 90)
    print(f"  CBA RESULTS (Present Value @ {config.economics.discount_rate:.0%} Discount Rate)")
    print("=" * 90)
    print()
    
    # NPV Summary
    print("--- NPV Summary (Million USD) ---")
    print()
    print(f"{'Scenario':<20} {'PV Total':>15} {'PV CAPEX':>15} {'PV Fuel':>15} {'LCOE':>12}")
    print("-" * 80)
    
    for name, data in cba_results.items():
        if name.startswith("_"):
            continue
        npv = data["npv_result"]
        label = name.replace("_", " ").title()
        print(f"{label:<20} ${npv.pv_total_costs/1e6:>13,.0f} ${npv.pv_capex/1e6:>13,.0f} ${npv.pv_fuel/1e6:>13,.0f} ${npv.lcoe_usd_per_kwh:>10.4f}")
    
    print()
    
    # Find least cost
    least_cost = min(
        ((k, v) for k, v in cba_results.items() if not k.startswith("_")),
        key=lambda x: x[1]["npv_result"].pv_total_costs,
    )
    bau = cba_results["bau"]["npv_result"]
    
    # Incremental Analysis vs BAU
    print("--- Incremental Analysis vs BAU ---")
    print()
    
    for name, data in cba_results.items():
        if name == "bau" or name.startswith("_"):
            continue
        npv = data["npv_result"]
        label = name.replace("_", " ").title()
        savings = bau.pv_total_costs - npv.pv_total_costs
        add_capex = npv.pv_capex - bau.pv_capex
        fuel_savings = bau.pv_fuel - npv.pv_fuel
        
        print(f"{label}:")
        print(f"  Additional Investment (PV): ${add_capex/1e6:,.0f}M")
        print(f"  Fuel/Import Savings (PV):   ${fuel_savings/1e6:,.0f}M")
        print(f"  Net Savings (PV):           ${savings/1e6:,.0f}M")
        if add_capex > 0:
            bcr = (fuel_savings) / add_capex
            print(f"  Benefit-Cost Ratio:         {bcr:.2f}")
        print()
    
    # Recommendation
    print("=" * 90)
    print("  RECOMMENDATIONS")
    print("=" * 90)
    print()
    least_label = least_cost[0].replace("_", " ").title()
    print(f"  Least Cost Scenario:     {least_label}")
    print(f"  (PV Total Costs: ${least_cost[1]['npv_result'].pv_total_costs/1e6:,.0f}M)")
    print()


def print_generation_trajectory(scenario_data: dict):
    """Print generation mix trajectory."""
    print("=" * 70)
    print("  GENERATION MIX TRAJECTORY")
    print("=" * 70)
    print()
    
    key_years = [2024, 2028, 2030, 2035, 2040, 2045, 2050]
    
    for scenario_key, label in [
        ("bau", "BAU (Diesel)"),
        ("full_integration", "Full Integration"),
        ("national_grid", "National Grid"),
        ("islanded_green", "Islanded Green"),
        ("nearshore_solar", "Near-Shore Solar"),
        ("maximum_re", "Maximum RE"),
        ("lng_transition", "LNG Transition"),
    ]:
        print(f"--- {label} ---")
        data = scenario_data[scenario_key]["results"]
        
        # Check if results have generation_mix attribute
        if hasattr(data, 'generation_mix'):
            print(f"{'Year':<6} {'Demand':>10} {'Diesel':>10} {'Solar':>10} {'RE %':>10}")
            print("-" * 50)
            for year in key_years:
                if year in data.generation_mix:
                    gen = data.generation_mix[year]
                    print(f"{year:<6} {gen.total_demand_gwh:>10.0f} {gen.diesel_gwh:>10.0f} {gen.solar_gwh:>10.0f} {gen.re_share:>10.1%}")
        else:
            # Handle ScenarioResults from simpler scenario classes
            print("  (Generation details available in detailed output)")
        print()


def print_solar_land_summary(scenario_data: dict, config):
    """V7: Print solar land constraint utilization per scenario."""
    ceiling_mw = config.technology.max_ground_mount_solar_mw
    total_area = config.technology.total_inhabited_island_area_km2
    max_frac = config.technology.max_solar_land_fraction
    
    print("=" * 70)
    print("  V7: SOLAR LAND CONSTRAINT CHECK")
    print("=" * 70)
    print()
    print(f"  Physical ceiling: {ceiling_mw:,.0f} MW ground-mount solar")
    print(f"  ({total_area:.1f} km2 x {max_frac:.0%} usable / {config.technology.solar_area_per_kw} m2/kW)")
    print()
    print(f"  {'Scenario':<22} {'Peak Solar':>12} {'Ground-Mount':>14} {'Utilization':>13} {'Status':>8}")
    print("  " + "-" * 73)
    
    for scenario_key, label in [
        ("bau", "BAU"),
        ("full_integration", "Full Integration"),
        ("national_grid", "National Grid"),
        ("islanded_green", "Islanded Green"),
        ("nearshore_solar", "Near-Shore Solar"),
        ("maximum_re", "Maximum RE"),
        ("lng_transition", "LNG Transition"),
    ]:
        data = scenario_data[scenario_key]
        results = data["results"]
        scen = data["scenario"]
        
        if hasattr(results, 'generation_mix') and results.generation_mix:
            last_year = max(results.generation_mix.keys())
            gm = results.generation_mix[last_year]
            total_solar = gm.solar_capacity_mw
            
            # Use the scenario's _non_ground_solar_mw if available
            non_ground = scen._non_ground_solar_mw(last_year) if hasattr(scen, '_non_ground_solar_mw') else 0.0
            ground = max(0.0, total_solar - non_ground)
            pct = ground / ceiling_mw * 100
            status = "OK" if ground <= ceiling_mw else "EXCEED"
            
            print(f"  {label:<22} {total_solar:>10,.0f} MW {ground:>12,.0f} MW {pct:>11.1f}%  {status:>8}")
    
    print()


def print_sectoral_demand(scenario_data: dict, config):
    """M5: Print sectoral demand breakdown for key years."""
    print("=" * 70)
    print("  SECTORAL DEMAND BREAKDOWN (GWh)")
    print("=" * 70)
    print()
    print("  Note: Shares from SAARC 2005 Energy Balance (52/24/24).")
    print("  Resorts (48% installed capacity) are off-grid and excluded.")
    print()
    
    key_years = [config.base_year, 2030, 2040, config.end_year]
    
    # Use BAU as representative (all scenarios use same sectoral shares)
    results = scenario_data["bau"]["results"]
    if not hasattr(results, 'sectoral_demand') or not results.sectoral_demand:
        print("  (Sectoral demand not available)")
        return
    
    print(f"{'Year':<6} {'Total':>10} {'Residential':>14} {'Commercial':>14} {'Public':>14}")
    print("-" * 62)
    for year in key_years:
        if year in results.sectoral_demand:
            sd = results.sectoral_demand[year]
            print(f"{year:<6} {sd.total_gwh:>10.0f} {sd.residential_gwh:>14.0f} {sd.commercial_gwh:>14.0f} {sd.public_gwh:>14.0f}")
    
    print(f"\n  Shares: Residential {results.sectoral_demand[config.base_year].residential_share:.0%}"
          f"  |  Commercial {results.sectoral_demand[config.base_year].commercial_share:.0%}"
          f"  |  Public {results.sectoral_demand[config.base_year].public_share:.0%}")
    print()


def print_resort_emissions_context(config):
    """L6: Print national emissions context including off-grid resort sector."""
    resort_gwh = config.tourism.resort_demand_gwh
    resort_ef = config.tourism.resort_emission_factor
    resort_intensity = config.tourism.resort_kwh_per_guest_night
    resort_mtco2_yr = resort_gwh * resort_ef / 1000  # GWh × kgCO₂/kWh / 1000 = ktCO₂ → /1000 = MtCO₂
    years = config.end_year - config.base_year
    resort_total_mtco2 = resort_mtco2_yr * years
    
    print("=" * 70)
    print("  NATIONAL EMISSIONS CONTEXT (incl. off-grid resorts)")
    print("=" * 70)
    print()
    print(f"  Resort sector (off-grid, self-generated diesel):")
    print(f"    Demand:              {resort_gwh:,.0f} GWh/yr")
    print(f"    Emission factor:     {resort_ef:.2f} kgCO\u2082/kWh (small gensets)")
    print(f"    Annual emissions:    {resort_mtco2_yr:.2f} MtCO\u2082/yr")
    print(f"    Cumulative ({years}yr):  {resort_total_mtco2:.1f} MtCO\u2082")
    print(f"    Intensity:           {resort_intensity:.0f} kWh/guest-night")
    print()
    print(f"  Note: Resort emissions are NOT included in CBA scenarios")
    print(f"  (resorts are off-grid, 48% of national installed capacity).")
    print(f"  These figures provide context for total national CO\u2082 accounting.")
    print()


def run_ddr_comparison(config: Config, scenario_data: dict) -> dict:
    """
    P1: Run declining discount rate comparison.
    
    Computes NPV for all scenarios under both:
      (a) Constant 6% ADB rate (base case)
      (b) HM Treasury Green Book declining schedule (3.5% → 3.0% → 2.5%)
    
    Returns dict suitable for JSON serialisation.
    
    References:
      - HM Treasury (2026). The Green Book. Table 8.
      - Drupp et al. (2018). AEJ: Economic Policy 10(4):109-134.
      - Weitzman (2001). AER 91(1):260-271.
    """
    calc = CBACalculator(config)
    
    scenario_names = [
        "bau", "full_integration", "national_grid", "islanded_green",
        "nearshore_solar", "maximum_re", "lng_transition"
    ]
    scenario_labels = {
        "bau": "BAU (Diesel)",
        "full_integration": "Full Integration",
        "national_grid": "National Grid",
        "islanded_green": "Islanded Green",
        "nearshore_solar": "Near-Shore Solar",
        "maximum_re": "Maximum RE",
        "lng_transition": "LNG Transition",
    }
    
    ddr_results = {
        "method": "HM Treasury Green Book (2026) declining schedule",
        "constant_rate": config.economics.discount_rate,
        "ddr_schedule": {
            "years_0_30": config.economics.ddr_rate_0_30,
            "years_31_75": config.economics.ddr_rate_31_75,
            "years_76_125": config.economics.ddr_rate_76_125,
        },
        "references": [
            "HM Treasury (2026). The Green Book: Central Government Guidance on Appraisal and Evaluation. Table 8.",
            "Drupp, M.A. et al. (2018). Discounting Disentangled. AEJ: Economic Policy 10(4):109-134.",
            "Weitzman, M.L. (2001). Gamma Discounting. AER 91(1):260-271.",
        ],
        "scenarios": {},
    }
    
    print("=" * 70)
    print("  P1: DECLINING DISCOUNT RATE COMPARISON")
    print("=" * 70)
    print()
    print(f"  Constant rate:  {config.economics.discount_rate:.1%} (ADB SIDS standard)")
    print(f"  DDR schedule:   {config.economics.ddr_rate_0_30:.1%} (yr 0-30) → "
          f"{config.economics.ddr_rate_31_75:.1%} (yr 31-75) → "
          f"{config.economics.ddr_rate_76_125:.1%} (yr 76+)")
    print()
    print(f"  {'Scenario':<22} {'Constant 6%':>14} {'DDR (3.5%→)':>14} {'Δ PV Costs':>14} {'Δ %':>8}")
    print("  " + "-" * 74)
    
    for name in scenario_names:
        if name not in scenario_data:
            continue
        results = scenario_data[name]["results"]
        
        # Constant rate NPV (already computed, but re-compute for consistency)
        npv_constant = calc.calculate_npv(results)
        
        # DDR NPV
        npv_ddr = calc.calculate_npv_declining(results)
        
        delta = npv_ddr.pv_total_costs - npv_constant.pv_total_costs
        pct = (delta / npv_constant.pv_total_costs * 100) if npv_constant.pv_total_costs != 0 else 0
        
        label = scenario_labels.get(name, name)
        print(f"  {label:<22} ${npv_constant.pv_total_costs/1e9:>12.2f}B ${npv_ddr.pv_total_costs/1e9:>12.2f}B "
              f"${delta/1e9:>12.2f}B {pct:>+7.1f}%")
        
        ddr_results["scenarios"][name] = {
            "label": label,
            "pv_total_costs_constant": npv_constant.pv_total_costs,
            "pv_total_costs_ddr": npv_ddr.pv_total_costs,
            "delta_pv_costs": delta,
            "delta_pct": round(pct, 2),
            "lcoe_constant": npv_constant.lcoe_usd_per_kwh,
            "lcoe_ddr": npv_ddr.lcoe_usd_per_kwh,
            "pv_emission_costs_constant": npv_constant.pv_emission_costs,
            "pv_emission_costs_ddr": npv_ddr.pv_emission_costs,
        }
    
    # Check if ranking changes under DDR
    costs_constant = {
        name: ddr_results["scenarios"][name]["pv_total_costs_constant"]
        for name in ddr_results["scenarios"]
    }
    costs_ddr = {
        name: ddr_results["scenarios"][name]["pv_total_costs_ddr"]
        for name in ddr_results["scenarios"]
    }
    
    rank_constant = sorted(costs_constant, key=costs_constant.get)
    rank_ddr = sorted(costs_ddr, key=costs_ddr.get)
    
    ddr_results["ranking_constant"] = rank_constant
    ddr_results["ranking_ddr"] = rank_ddr
    ddr_results["ranking_changed"] = rank_constant != rank_ddr
    
    print()
    print(f"  Ranking (constant):  {' > '.join(scenario_labels.get(s, s) for s in rank_constant[:3])}")
    print(f"  Ranking (DDR):       {' > '.join(scenario_labels.get(s, s) for s in rank_ddr[:3])}")
    print(f"  Ranking changed:     {'YES ⚠' if ddr_results['ranking_changed'] else 'No — results robust to DDR'}")
    print()
    
    return ddr_results


def run_learning_curve_comparison(config: Config) -> dict:
    """
    P6: Compare exogenous (constant %/yr) vs endogenous (Wright's Law) cost decline.
    
    Shows how solar and battery CAPEX evolves under both approaches over
    the analysis horizon, and the implied LCOE difference.
    
    References:
        Wright, T.P. (1936). J. Aeronautical Sciences 3(4):122-128.
        Rubin, E.S. et al. (2015). EEEP 3(2).
        Ziegler, M.S. & Trancik, J.E. (2021). Energy Policy 151.
    """
    import math
    from model.costs import CostCalculator
    
    calc = CostCalculator(config)
    tech = config.technology
    
    # Learning exponents
    solar_alpha = -math.log(1 - tech.solar_learning_rate) / math.log(2)
    battery_alpha = -math.log(1 - tech.battery_learning_rate) / math.log(2)
    
    print("=" * 70)
    print("  P6: ENDOGENOUS LEARNING CURVE COMPARISON")
    print("=" * 70)
    print()
    print(f"  Solar:   LR={tech.solar_learning_rate:.0%} → α={solar_alpha:.3f} "
          f"(exog: {tech.solar_pv_cost_decline:.0%}/yr)")
    print(f"  Battery: LR={tech.battery_learning_rate:.0%} → α={battery_alpha:.3f} "
          f"(exog: {tech.battery_cost_decline:.0%}/yr)")
    print(f"  Global solar: {tech.solar_global_cumulative_gw_2026:.0f} GW (2026), "
          f"+{tech.solar_global_annual_addition_gw:.0f} GW/yr")
    print(f"  Global battery: {tech.battery_global_cumulative_gwh_2026:.0f} GWh (2026), "
          f"+{tech.battery_global_annual_addition_gwh:.0f} GWh/yr")
    print()
    
    results = {
        "method": "Wright's Law endogenous learning curve",
        "solar_learning_rate": tech.solar_learning_rate,
        "battery_learning_rate": tech.battery_learning_rate,
        "solar_exog_decline": tech.solar_pv_cost_decline,
        "battery_exog_decline": tech.battery_cost_decline,
        "references": [
            "Wright, T.P. (1936). Factors Affecting the Cost of Airplanes. J. Aeronautical Sciences 3(4):122-128.",
            "Rubin, E.S. et al. (2015). A review of learning rates for electricity supply technologies. EEEP 3(2).",
            "Ziegler, M.S. & Trancik, J.E. (2021). Re-examining rates of lithium-ion battery technology improvement. Energy Policy 151.",
            "IRENA (2024). Renewable Power Generation Costs in 2023.",
        ],
        "trajectory": [],
    }
    
    print(f"  {'Year':>6} {'Solar Exog':>12} {'Solar Endog':>13} {'Δ%':>7} "
          f"{'Batt Exog':>11} {'Batt Endog':>12} {'Δ%':>7}")
    print("  " + "-" * 72)
    
    for year in range(config.base_year, config.end_year + 1, 5):
        # 1 MW / 1 MWh test capacity for unit cost comparison
        solar_exog = calc.solar_capex(1.0, year) / 1000  # $/kW
        solar_endog = calc.learning_curve_solar_capex(1.0, year) / 1000
        solar_delta = (solar_endog / solar_exog - 1) * 100 if solar_exog > 0 else 0
        
        battery_exog = calc.battery_capex(1.0, year) / 1000  # $/kWh
        battery_endog = calc.learning_curve_battery_capex(1.0, year) / 1000
        battery_delta = (battery_endog / battery_exog - 1) * 100 if battery_exog > 0 else 0
        
        # Remove climate premium for display (already included in both)
        premium = 1 + tech.climate_adaptation_premium
        
        print(f"  {year:>6} ${solar_exog/premium:>10,.0f}/kW ${solar_endog/premium:>11,.0f}/kW {solar_delta:>+6.1f}% "
              f"${battery_exog/premium:>9,.0f}/kWh ${battery_endog/premium:>10,.0f}/kWh {battery_delta:>+6.1f}%")
        
        results["trajectory"].append({
            "year": year,
            "solar_exog_usd_kw": round(solar_exog / premium, 0),
            "solar_endog_usd_kw": round(solar_endog / premium, 0),
            "solar_delta_pct": round(solar_delta, 1),
            "battery_exog_usd_kwh": round(battery_exog / premium, 0),
            "battery_endog_usd_kwh": round(battery_endog / premium, 0),
            "battery_delta_pct": round(battery_delta, 1),
        })
    
    # Summary: cumulative CAPEX difference for a representative scenario
    # (100 MW solar + 400 MWh battery over horizon)
    total_exog_solar = sum(calc.solar_capex(4.0, y) for y in range(config.base_year, config.end_year + 1))
    total_endog_solar = sum(calc.learning_curve_solar_capex(4.0, y) for y in range(config.base_year, config.end_year + 1))
    total_exog_batt = sum(calc.battery_capex(16.0, y) for y in range(config.base_year, config.end_year + 1))
    total_endog_batt = sum(calc.learning_curve_battery_capex(16.0, y) for y in range(config.base_year, config.end_year + 1))
    
    solar_saving = total_exog_solar - total_endog_solar
    batt_saving = total_exog_batt - total_endog_batt
    results["cumulative_solar_saving_usd"] = solar_saving
    results["cumulative_battery_saving_usd"] = batt_saving
    
    print()
    print(f"  Representative 100 MW solar programme over {config.end_year - config.base_year + 1}yr:")
    print(f"    Exogenous CAPEX: ${total_exog_solar/1e6:,.0f}M")
    print(f"    Endogenous CAPEX: ${total_endog_solar/1e6:,.0f}M (Δ ${solar_saving/1e6:+,.0f}M)")
    print(f"  Representative 400 MWh battery programme:")
    print(f"    Exogenous CAPEX: ${total_exog_batt/1e6:,.0f}M")
    print(f"    Endogenous CAPEX: ${total_endog_batt/1e6:,.0f}M (Δ ${batt_saving/1e6:+,.0f}M)")
    print()
    
    return results


def run_climate_scenario_comparison(config: Config) -> dict:
    """
    P7: Compare solar generation under baseline, RCP 4.5, and RCP 8.5.
    
    Climate change affects solar output through:
    1. GHI reduction (increased cloud cover / aerosols)
    2. Temperature rise (higher PV derating)
    
    Shows annual generation trajectory for a reference 100 MW plant.
    
    References:
        IPCC (2021). AR6 WG1 Ch.7, Table 7.2.
        Crook, J.A. et al. (2011). Energy & Env. Science 4:3101.
        Wild, M. et al. (2015). J. Geophys. Res. 120:8141.
    """
    from model.costs import CostCalculator
    
    calc = CostCalculator(config)
    tech = config.technology
    
    print("=" * 70)
    print("  P7: CLIMATE DAMAGE SCENARIO COMPARISON (RCP 4.5 / 8.5)")
    print("=" * 70)
    print()
    print(f"  Baseline GHI: {tech.default_ghi:.2f} kWh/m²/day, "
          f"Temp: {tech.default_ambient_temp:.1f}°C")
    print(f"  RCP 4.5 by {tech.climate_scenario_year}: "
          f"GHI {tech.rcp45_ghi_change_2050:+.0%}, "
          f"Temp +{tech.rcp45_temp_rise_2050:.1f}°C")
    print(f"  RCP 8.5 by {tech.climate_scenario_year}: "
          f"GHI {tech.rcp85_ghi_change_2050:+.0%}, "
          f"Temp +{tech.rcp85_temp_rise_2050:.1f}°C")
    print()
    
    results = {
        "method": "IPCC AR6 WG1 Indian Ocean regional projections",
        "baseline_ghi": tech.default_ghi,
        "baseline_temp": tech.default_ambient_temp,
        "rcp45": {"ghi_change": tech.rcp45_ghi_change_2050, "temp_rise": tech.rcp45_temp_rise_2050},
        "rcp85": {"ghi_change": tech.rcp85_ghi_change_2050, "temp_rise": tech.rcp85_temp_rise_2050},
        "scenario_year": tech.climate_scenario_year,
        "references": [
            "IPCC (2021). AR6 WG1 Ch.7 Table 7.2; Ch.4 Table 4.5.",
            "Crook, J.A. et al. (2011). Climate change impacts on future PV output. Energy & Env. Science 4:3101.",
            "Wild, M. et al. (2015). Projections of long-term changes in solar radiation. J. Geophys. Res. 120:8141.",
        ],
        "trajectory": [],
    }
    
    # Reference: 100 MW installed at base year
    ref_mw = 100.0
    install_year = config.base_year
    
    print(f"  Reference: {ref_mw:.0f} MW installed in {install_year}")
    print()
    print(f"  {'Year':>6} {'Baseline':>12} {'RCP 4.5':>12} {'Δ%':>7} {'RCP 8.5':>12} {'Δ%':>7}")
    print("  " + "-" * 58)
    
    cumulative = {'baseline': 0, 'rcp45': 0, 'rcp85': 0}
    
    for year in range(config.base_year, config.end_year + 1):
        gen_base = calc.solar_generation_climate_adjusted(ref_mw, year, 'baseline', install_year)
        gen_45 = calc.solar_generation_climate_adjusted(ref_mw, year, 'rcp45', install_year)
        gen_85 = calc.solar_generation_climate_adjusted(ref_mw, year, 'rcp85', install_year)
        
        cumulative['baseline'] += gen_base
        cumulative['rcp45'] += gen_45
        cumulative['rcp85'] += gen_85
        
        delta_45 = (gen_45 / gen_base - 1) * 100 if gen_base > 0 else 0
        delta_85 = (gen_85 / gen_base - 1) * 100 if gen_base > 0 else 0
        
        if (year - config.base_year) % 5 == 0 or year == config.end_year:
            print(f"  {year:>6} {gen_base:>10.1f} GWh {gen_45:>10.1f} GWh {delta_45:>+6.1f}% "
                  f"{gen_85:>10.1f} GWh {delta_85:>+6.1f}%")
        
        results["trajectory"].append({
            "year": year,
            "generation_baseline_gwh": round(gen_base, 2),
            "generation_rcp45_gwh": round(gen_45, 2),
            "generation_rcp85_gwh": round(gen_85, 2),
            "delta_rcp45_pct": round(delta_45, 2),
            "delta_rcp85_pct": round(delta_85, 2),
        })
    
    # Cumulative impact
    loss_45 = cumulative['baseline'] - cumulative['rcp45']
    loss_85 = cumulative['baseline'] - cumulative['rcp85']
    loss_45_pct = loss_45 / cumulative['baseline'] * 100 if cumulative['baseline'] > 0 else 0
    loss_85_pct = loss_85 / cumulative['baseline'] * 100 if cumulative['baseline'] > 0 else 0
    
    results["cumulative_baseline_gwh"] = round(cumulative['baseline'], 1)
    results["cumulative_rcp45_gwh"] = round(cumulative['rcp45'], 1)
    results["cumulative_rcp85_gwh"] = round(cumulative['rcp85'], 1)
    results["cumulative_loss_rcp45_gwh"] = round(loss_45, 1)
    results["cumulative_loss_rcp85_gwh"] = round(loss_85, 1)
    results["cumulative_loss_rcp45_pct"] = round(loss_45_pct, 2)
    results["cumulative_loss_rcp85_pct"] = round(loss_85_pct, 2)
    
    print()
    print(f"  Cumulative generation ({config.end_year - config.base_year + 1} years):")
    print(f"    Baseline: {cumulative['baseline']:,.0f} GWh")
    print(f"    RCP 4.5:  {cumulative['rcp45']:,.0f} GWh (loss: {loss_45:,.0f} GWh = {loss_45_pct:.1f}%)")
    print(f"    RCP 8.5:  {cumulative['rcp85']:,.0f} GWh (loss: {loss_85:,.0f} GWh = {loss_85_pct:.1f}%)")
    print()
    
    return results


def _build_cba_output(cba_results: dict, config: Config, scenario_data: dict) -> dict:
    """Build CBA output dict (same structure as cba_results.json) for MCA input."""
    cba_output = {
        "discount_rate": config.economics.discount_rate,
        "base_year": config.base_year,
        "end_year": config.end_year,
        "npv_results": {},
        "incremental_vs_bau": {},
    }
    for name, data in cba_results.items():
        if name.startswith("_"):
            continue
        npv = data["npv_result"]
        cba_output["npv_results"][name] = {
            "pv_total_costs": npv.pv_total_costs,
            "pv_capex": npv.pv_capex,
            "pv_opex": npv.pv_opex,
            "pv_fuel": npv.pv_fuel,
            "pv_ppa": npv.pv_ppa,
            "pv_emission_costs": npv.pv_emission_costs,
            "pv_health_benefits": npv.pv_health_benefits,
            "pv_reliability_benefits": npv.pv_reliability_benefits,  # L20
            "pv_environmental_benefits": npv.pv_environmental_benefits,  # A-MO-01
            "lcoe": npv.lcoe_usd_per_kwh,
        }
    comparison = cba_results.get("_comparison")
    if comparison:
        for label, incr in [
            ("full_integration", comparison.fi_vs_bau),
            ("national_grid", comparison.ng_vs_bau),
            ("islanded_green", comparison.ig_vs_bau),
            ("nearshore_solar", comparison.ns_vs_bau),
            ("maximum_re", comparison.mx_vs_bau),
            ("lng_transition", comparison.lng_vs_bau),
        ]:
            cba_output["incremental_vs_bau"][label] = {
                "npv_savings": incr.npv,
                "additional_capex": incr.incremental_pv_capex,
                "fuel_savings": incr.pv_fuel_savings,
                "emission_savings": incr.pv_emission_savings,
                "health_savings": incr.pv_health_savings,
                "reliability_savings": incr.pv_reliability_savings,  # L20
                "environmental_savings": incr.pv_environmental_savings,  # A-MO-01
                "total_benefits": incr.pv_total_benefits,
                "bcr": incr.bcr,
                "irr": incr.irr,
                "payback_years": incr.payback_years,
            }
    return cba_output


def save_results(scenario_data: dict, cba_results: dict, output_dir: str, config: Config):
    """Save results to files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save scenario summaries as JSON (all 4 scenarios)
    summaries = {k: v["summary"] for k, v in scenario_data.items()}
    
    with open(output_path / "scenario_summaries.json", "w") as f:
        json.dump(summaries, f, indent=2)
    
    # Save CBA results (all 4 scenarios)
    cba_output = {
        "discount_rate": config.economics.discount_rate,
        "base_year": config.base_year,
        "end_year": config.end_year,
        "npv_results": {},
        "incremental_vs_bau": {},
    }
    
    for name, data in cba_results.items():
        if name.startswith("_"):
            continue
        npv = data["npv_result"]
        cba_output["npv_results"][name] = {
            "pv_total_costs": npv.pv_total_costs,
            "pv_capex": npv.pv_capex,
            "pv_opex": npv.pv_opex,
            "pv_fuel": npv.pv_fuel,
            "pv_ppa": npv.pv_ppa,
            "pv_emission_costs": npv.pv_emission_costs,
            "pv_health_benefits": npv.pv_health_benefits,
            "pv_reliability_benefits": npv.pv_reliability_benefits,  # L20
            "pv_environmental_benefits": npv.pv_environmental_benefits,  # A-MO-01
            "lcoe": npv.lcoe_usd_per_kwh,
        }
    
    # Serialize full incremental analysis from CBAComparison (includes IRR, payback, BCR)
    comparison = cba_results.get("_comparison")
    if comparison:
        for label, incr in [
            ("full_integration", comparison.fi_vs_bau),
            ("national_grid", comparison.ng_vs_bau),
            ("islanded_green", comparison.ig_vs_bau),
            ("nearshore_solar", comparison.ns_vs_bau),
            ("maximum_re", comparison.mx_vs_bau),
            ("lng_transition", comparison.lng_vs_bau),
        ]:
            cba_output["incremental_vs_bau"][label] = {
                "npv_savings": incr.npv,
                "additional_capex": incr.incremental_pv_capex,
                "incremental_opex": incr.incremental_pv_opex,
                "incremental_ppa": incr.incremental_pv_ppa,
                "fuel_savings": incr.pv_fuel_savings,
                "emission_savings": incr.pv_emission_savings,
                "health_savings": incr.pv_health_savings,
                "reliability_savings": incr.pv_reliability_savings,  # L20
                "environmental_savings": incr.pv_environmental_savings,  # A-MO-01
                "total_benefits": incr.pv_total_benefits,
                "bcr": incr.bcr,
                "irr": incr.irr,
                "payback_years": incr.payback_years,
            }
        
        # Also save FI vs NG incremental
        cba_output["incremental_fi_vs_ng"] = {
            "npv_savings": comparison.fi_vs_ng.npv,
            "additional_capex": comparison.fi_vs_ng.incremental_pv_capex,
            "fuel_savings": comparison.fi_vs_ng.pv_fuel_savings,
            "bcr": comparison.fi_vs_ng.bcr,
            "irr": comparison.fi_vs_ng.irr,
            "payback_years": comparison.fi_vs_ng.payback_years,
        }
    
    # Add recommendation
    npv_costs = {name: data["npv_result"].pv_total_costs 
                 for name, data in cba_results.items() if not name.startswith("_")}
    least_cost = min(npv_costs, key=npv_costs.get)
    cba_output["recommendation"] = {
        "least_cost": least_cost,
        "least_cost_label": least_cost.replace("_", " ").title(),
    }
    
    # M5: Add sectoral demand breakdown for key years
    cba_output["sectoral_demand"] = {}
    key_years = [config.base_year, 2030, 2040, config.end_year]
    for name, data in scenario_data.items():
        results = data["results"]
        if hasattr(results, 'sectoral_demand') and results.sectoral_demand:
            cba_output["sectoral_demand"][name] = {
                str(yr): results.sectoral_demand[yr].to_dict()
                for yr in key_years if yr in results.sectoral_demand
            }
    
    # --- Config-driven reference data for report rendering ---
    
    # LCOE benchmarks (for comparison charts) + validation flags
    bm = config.benchmarks
    cba_output["benchmarks"] = {
        "global_solar_lcoe": bm.global_solar_lcoe,
        "global_diesel_gen_lcoe": bm.global_diesel_gen_lcoe,
        "sids_avg_renewable_lcoe": bm.sids_avg_renewable_lcoe,
        "maldives_cif_aspire_lcoe": bm.maldives_cif_aspire_lcoe,
        "tokelau_lcoe": bm.tokelau_lcoe,
        "cook_islands_lcoe": bm.cook_islands_lcoe,
        "barbados_lcoe": bm.barbados_lcoe,
        "fiji_lcoe": bm.fiji_lcoe,
    }
    # Validate model LCOEs against benchmark range
    sids_range = (bm.maldives_cif_aspire_lcoe, bm.cook_islands_lcoe)  # ~$0.099-$0.25
    cba_output["lcoe_validation"] = {}
    for name in cba_output["npv_results"]:
        model_lcoe = cba_output["npv_results"][name].get("lcoe", 0)
        in_range = sids_range[0] <= model_lcoe <= sids_range[1]
        cba_output["lcoe_validation"][name] = {
            "model_lcoe": round(model_lcoe, 4),
            "sids_range_low": sids_range[0],
            "sids_range_high": sids_range[1],
            "within_sids_range": in_range,
            "vs_global_diesel": round(model_lcoe / bm.global_diesel_gen_lcoe, 2) if bm.global_diesel_gen_lcoe > 0 else None,
        }
    # PPA floor validation: India domestic rate as floor for import pricing
    ppa_floor = config.current_system.india_domestic_rate
    for name in ["full_integration"]:
        lcoe_val = cba_output["npv_results"].get(name, {}).get("lcoe", 0)
        cba_output["lcoe_validation"][f"{name}_ppa_floor_check"] = {
            "india_domestic_rate": ppa_floor,
            "scenario_lcoe": round(lcoe_val, 4),
            "lcoe_above_ppa_floor": lcoe_val >= ppa_floor,
        }
    
    # L23: Distributional shares — apply to actual scenario costs/benefits
    ds = config.distributional
    cba_output["distributional_shares"] = {
        "cost_shares_pct": {
            "government": ds.cost_share_government,
            "mdbs": ds.cost_share_mdbs,
            "india": ds.cost_share_india,
            "private": ds.cost_share_private,
        },
        "benefit_shares_pct": {
            "households": ds.benefit_share_households,
            "businesses": ds.benefit_share_businesses,
            "government": ds.benefit_share_government,
            "climate": ds.benefit_share_climate,
            "workers": ds.benefit_share_workers,
        },
    }
    # Compute per-scenario stakeholder allocations (million USD)
    # Cost shares are scenario-specific: India share only applies to FI (cable scenario)
    # For NG/IG/BAU, India's share is redistributed proportionally to govt/mdbs/private
    cba_output["stakeholder_allocation"] = {}
    for name, data in cba_results.items():
        if name.startswith("_"):
            continue
        npv = data["npv_result"]
        total_cost = npv.pv_total_costs
        # Benefits: sum of all benefit categories from incremental vs BAU
        incr_key = name  # same key
        incr_data = cba_output.get("incremental_vs_bau", {}).get(incr_key, {})
        total_benefit = incr_data.get("total_benefits", 0)

        # Scenario-specific cost shares
        if name == "full_integration":
            # FI: India contributes (cable co-financing)
            cs_govt = ds.cost_share_government
            cs_mdbs = ds.cost_share_mdbs
            cs_india = ds.cost_share_india
            cs_private = ds.cost_share_private
        else:
            # NG/IG/BAU: No India involvement — redistribute India share
            # proportionally among govt, mdbs, private
            non_india = ds.cost_share_government + ds.cost_share_mdbs + ds.cost_share_private
            if non_india > 0:
                scale = 100.0 / non_india  # scale to sum to 100%
                cs_govt = ds.cost_share_government * scale
                cs_mdbs = ds.cost_share_mdbs * scale
                cs_private = ds.cost_share_private * scale
            else:
                cs_govt = cs_mdbs = cs_private = 100.0 / 3
            cs_india = 0.0

        cba_output["stakeholder_allocation"][name] = {
            "cost_allocation_musd": {
                "government": round(total_cost * cs_govt / 100 / 1e6, 1),
                "mdbs": round(total_cost * cs_mdbs / 100 / 1e6, 1),
                "india": round(total_cost * cs_india / 100 / 1e6, 1),
                "private": round(total_cost * cs_private / 100 / 1e6, 1),
            },
            "benefit_allocation_musd": {
                "households": round(total_benefit * ds.benefit_share_households / 100 / 1e6, 1),
                "businesses": round(total_benefit * ds.benefit_share_businesses / 100 / 1e6, 1),
                "government": round(total_benefit * ds.benefit_share_government / 100 / 1e6, 1),
                "climate": round(total_benefit * ds.benefit_share_climate / 100 / 1e6, 1),
                "workers": round(total_benefit * ds.benefit_share_workers / 100 / 1e6, 1),
            },
        }
    
    # L24: Investment phasing — computed from model scenario CAPEX by period
    # Aggregate actual CAPEX by technology and 5-year period across scenarios
    periods = [
        ("2026-28", 2026, 2028),
        ("2029-32", 2029, 2032),
        ("2033-36", 2033, 2036),
        ("2037-40", 2037, 2040),
        ("2041-50", 2041, 2050),
    ]
    cba_output["investment_phasing_musd"] = {}
    for name, data in scenario_data.items():
        results = data["results"]
        phasing = {"solar": {}, "battery": {}, "inter_island": {}, "india_cable": {}}
        for label, yr_start, yr_end in periods:
            solar_sum = battery_sum = grid_sum = cable_sum = 0.0
            for yr in range(yr_start, yr_end + 1):
                costs = results.annual_costs.get(yr)
                if costs:
                    solar_sum += costs.capex_solar
                    battery_sum += costs.capex_battery
                    grid_sum += costs.capex_grid
                    cable_sum += costs.capex_cable
            phasing["solar"][label] = round(solar_sum / 1e6, 1)
            phasing["battery"][label] = round(battery_sum / 1e6, 1)
            phasing["inter_island"][label] = round(grid_sum / 1e6, 1)
            phasing["india_cable"][label] = round(cable_sum / 1e6, 1)
        cba_output["investment_phasing_musd"][name] = phasing
    
    # Baseline system context (for report baseline description)
    cs = config.current_system
    econ = config.economics
    cba_output["baseline_system"] = {
        "total_capacity_mw": cs.total_capacity_mw,
        "diesel_capacity_mw": cs.diesel_capacity_mw,
        "solar_capacity_mw": cs.solar_capacity_mw,
        "battery_capacity_mwh": cs.battery_capacity_mwh,
        "diesel_share": cs.diesel_share,
        "re_share": cs.re_share,
        "male_electricity_share": cs.male_electricity_share,
        "resort_capacity_share": cs.resort_capacity_share,
        "saidi_minutes_per_year": cs.saidi_minutes,
        "saifi_interruptions_per_year": cs.saifi_interruptions,
        "avg_hh_monthly_kwh": cs.avg_hh_monthly_kwh,
        "current_retail_tariff_usd_kwh": cs.current_retail_tariff,
        "india_domestic_rate_usd_kwh": cs.india_domestic_rate,
        "current_subsidy_per_kwh": cs.current_subsidy_per_kwh,
        # L21-22: Additional fiscal context
        "outer_island_electricity_cost_usd_kwh": cs.outer_island_electricity_cost,
        "male_rooftop_solar_mwp": cs.male_rooftop_solar_mwp,
        "population_2026": cs.population_2026,
        "exchange_rate_mvr_usd": econ.exchange_rate_mvr_usd,
        "voll_usd_kwh": econ.voll,
    }

    # Per-capita metrics (using population_2026 + demand)
    base_demand_gwh = config.demand.base_demand_gwh
    per_capita_kwh = base_demand_gwh * 1e6 / cs.population_2026 if cs.population_2026 > 0 else 0
    cba_output["per_capita_metrics"] = {
        "base_demand_gwh": base_demand_gwh,
        "population": cs.population_2026,
        "per_capita_kwh_year": round(per_capita_kwh, 0),
        "per_capita_cost_bau_usd": round(
            cba_output["npv_results"].get("bau", {}).get("pv_total_costs", 0) / cs.population_2026, 0
        ) if cs.population_2026 > 0 else 0,
    }
    
    # Time horizons (for multi-horizon reference)
    cba_output["time_horizons"] = {
        "base_year": config.base_year,
        "end_year_20": config.end_year_20,
        "end_year_30": config.end_year_30,
        "end_year_50": config.end_year_50,
    }
    
    # SCC context (scc_iwg_interim for sensitivity reference)
    cba_output["scc_context"] = {
        "scc_central_usd_tco2": config.economics.social_cost_carbon,
        "scc_iwg_interim_usd_tco2": config.economics.scc_iwg_interim,
        "scc_annual_growth_pct": config.economics.scc_annual_growth,
        # Sensitivity: % change in emission benefits if IWG SCC used instead
        "iwg_vs_central_ratio": round(
            config.economics.scc_iwg_interim / config.economics.social_cost_carbon, 2
        ) if config.economics.social_cost_carbon > 0 else None,
    }
    
    # Tourism green premium revenue potential
    tourism = config.tourism
    green_premium_potential_musd = (
        tourism.resort_demand_gwh * 1e3  # GWh → MWh
        * tourism.green_premium_per_kwh * 1e3  # $/kWh × MWh → $ (×1000 for kWh/MWh)
        / 1e6  # → million USD
    )
    cba_output["tourism_context"] = {
        "resort_demand_gwh": tourism.resort_demand_gwh,
        "resort_emission_factor": tourism.resort_emission_factor,
        "resort_kwh_per_guest_night": tourism.resort_kwh_per_guest_night,
        "green_premium_per_kwh": tourism.green_premium_per_kwh,
        "green_premium_potential_musd_yr": green_premium_potential_musd,
    }
    
    # P1: Declining discount rate comparison
    ddr_results = run_ddr_comparison(config, scenario_data)
    cba_output["declining_discount_rate"] = ddr_results
    
    with open(output_path / "cba_results.json", "w") as f:
        json.dump(cba_output, f, indent=2)
    
    # L17: Save MCA results
    mca_output = run_mca(cba_output, summaries, config)
    ws = weight_sensitivity(cba_output, summaries, config)
    mca_output["weight_sensitivity"] = ws
    with open(output_path / "mca_results.json", "w") as f:
        json.dump(mca_output, f, indent=2)
    
    print(f"Results saved to {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Maldives Energy CBA Model")
    parser.add_argument(
        "--output", "-o",
        default="outputs",
        help="Output directory for results",
    )
    parser.add_argument(
        "--sensitivity", "-s",
        action="store_true",
        help="Run sensitivity analysis",
    )
    parser.add_argument(
        "--monte-carlo", "-mc",
        type=int,
        default=0,
        help="Number of Monte Carlo iterations (0 to skip)",
    )
    
    args = parser.parse_args()
    
    # Print header
    print_header()
    
    # Load configuration
    print("Loading configuration...")
    config = get_config()
    print(f"  Time horizon: {config.base_year}-{config.end_year}")
    print(f"  Discount rate: {config.economics.discount_rate:.1%}")
    print()
    
    # Run scenarios
    scenario_data = run_scenarios(config)
    
    # Run CBA
    cba_results = run_cba(config, scenario_data)
    
    # Print results
    print_scenario_summary(scenario_data)
    print_cba_summary(cba_results, config)
    print_generation_trajectory(scenario_data)
    print_solar_land_summary(scenario_data, config)
    print_sectoral_demand(scenario_data, config)
    print_resort_emissions_context(config)
    
    # P1: Declining discount rate comparison
    ddr_results = run_ddr_comparison(config, scenario_data)
    
    # P6: Endogenous learning curve comparison
    learning_results = run_learning_curve_comparison(config)
    
    # P7: Climate damage scenario comparison
    climate_results = run_climate_scenario_comparison(config)
    
    # L5: Supplementary financing analysis (does not affect economic CBA)
    fin_results = run_financing_analysis(config, scenario_data, cba_results)
    print_financing_summary(fin_results, config)
    
    # L17: Multi-Criteria Analysis
    summaries = {k: v["summary"] for k, v in scenario_data.items()}
    # Build CBA output dict for MCA (mirrors save_results structure)
    cba_output_for_mca = _build_cba_output(cba_results, config, scenario_data)
    mca_output = run_mca(cba_output_for_mca, summaries, config)
    print_mca_results(mca_output)
    
    # L15: Distributional analysis (uses HIES 2019 microdata)
    try:
        dist_results = run_distributional_analysis(
            config, cba_output_for_mca, summaries
        )
        print_distributional_summary(dist_results)
    except FileNotFoundError as e:
        print(f"\n  ⚠ Distributional analysis skipped: {e}")
        dist_results = None
    
    # P8: Transport electrification analysis (supplementary — does not affect core CBA)
    transport_results = run_transport_analysis(config)
    print_transport_summary(transport_results)
    
    # Run sensitivity analysis if requested
    if args.sensitivity:
        print("=" * 70)
        print("  SENSITIVITY ANALYSIS")
        print("=" * 70)
        print()
        
        sensitivity = SensitivityAnalysis(config)
        print(sensitivity.get_parameter_summary())
        print()
        print("(Full sensitivity analysis requires additional computation time)")
        print()
    
    # Save results
    save_results(scenario_data, cba_results, args.output, config)
    save_financing_results(fin_results, args.output)
    if dist_results is not None:
        save_distributional_results(dist_results, args.output)
    save_transport_results(transport_results, args.output)
    
    # Save P6 + P7 results
    import json
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    with open(output_path / "learning_curve_results.json", "w") as f:
        json.dump(learning_results, f, indent=2)
    print(f"  Learning curve results saved to {output_path / 'learning_curve_results.json'}")
    with open(output_path / "climate_scenario_results.json", "w") as f:
        json.dump(climate_results, f, indent=2)
    print(f"  Climate scenario results saved to {output_path / 'climate_scenario_results.json'}")
    
    print("=" * 70)
    print("  MODEL RUN COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
