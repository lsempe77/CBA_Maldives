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
from model.cba import CBACalculator, CBAComparison, SensitivityAnalysis


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
    }


def run_cba(config: Config, scenario_data: dict) -> dict:
    """
    Run CBA calculations for 4 scenarios.
    """
    print("Running CBA calculations...")
    print("-" * 50)
    
    calculator = CBACalculator(config)
    
    # Calculate NPV for each scenario
    results = {}
    for name, data in scenario_data.items():
        npv = calculator.calculate_npv(data["results"])
        results[name] = {
            "npv_result": npv,
            "summary": data["summary"],
        }
    
    print(f"  ✓ NPV calculations complete")
    print(f"  ✓ All 4 scenarios analyzed")
    print()
    
    return results


def print_scenario_summary(scenario_data: dict):
    """Print summary of scenario results."""
    print("=" * 90)
    print("  SCENARIO SUMMARY (2024-2050)")
    print("=" * 90)
    print()
    
    headers = ["Metric", "BAU", "Full Integration", "National Grid", "Islanded Green"]
    print(f"{headers[0]:<25} {headers[1]:>12} {headers[2]:>18} {headers[3]:>15} {headers[4]:>16}")
    print("-" * 90)
    
    bau = scenario_data["bau"]["summary"]
    fi = scenario_data["full_integration"]["summary"]
    ng = scenario_data["national_grid"]["summary"]
    ig = scenario_data["islanded_green"]["summary"]
    
    # Total costs
    print(f"{'Total Costs (M USD)':<25} ${bau['total_costs_million']:>10,.0f} ${fi['total_costs_million']:>16,.0f} ${ng['total_costs_million']:>13,.0f} ${ig['total_costs_million']:>14,.0f}")
    print(f"{'  - CAPEX':<25} ${bau['total_capex_million']:>10,.0f} ${fi['total_capex_million']:>16,.0f} ${ng['total_capex_million']:>13,.0f} ${ig['total_capex_million']:>14,.0f}")
    print(f"{'  - OPEX':<25} ${bau['total_opex_million']:>10,.0f} ${fi['total_opex_million']:>16,.0f} ${ng['total_opex_million']:>13,.0f} ${ig['total_opex_million']:>14,.0f}")
    print(f"{'  - Fuel':<25} ${bau['total_fuel_million']:>10,.0f} ${fi['total_fuel_million']:>16,.0f} ${ng['total_fuel_million']:>13,.0f} ${ig['total_fuel_million']:>14,.0f}")
    
    # Emissions
    print(f"{'Total Emissions (MtCO2)':<25} {bau['total_emissions_mtco2']:>11.2f} {fi['total_emissions_mtco2']:>17.2f} {ng['total_emissions_mtco2']:>14.2f} {ig['total_emissions_mtco2']:>15.2f}")
    
    # Final RE share
    print(f"{'Final RE Share (2050)':<25} {bau['final_re_share']:>11.1%} {fi['final_re_share']:>17.1%} {ng['final_re_share']:>14.1%} {ig['final_re_share']:>15.1%}")
    
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
        npv = data["npv_result"]
        label = name.replace("_", " ").title()
        print(f"{label:<20} ${npv.pv_total_costs/1e6:>13,.0f} ${npv.pv_capex/1e6:>13,.0f} ${npv.pv_fuel/1e6:>13,.0f} ${npv.lcoe_usd_per_kwh:>10.4f}")
    
    print()
    
    # Find least cost
    least_cost = min(cba_results.items(), key=lambda x: x[1]["npv_result"].pv_total_costs)
    bau = cba_results["bau"]["npv_result"]
    
    # Incremental Analysis vs BAU
    print("--- Incremental Analysis vs BAU ---")
    print()
    
    for name, data in cba_results.items():
        if name == "bau":
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
    
    bau_npv = cba_results["bau"]["npv_result"] if "bau" in cba_results else None
    
    for name, data in cba_results.items():
        npv = data["npv_result"]
        cba_output["npv_results"][name] = {
            "pv_total_costs": npv.pv_total_costs,
            "pv_capex": npv.pv_capex,
            "pv_opex": npv.pv_opex,
            "pv_fuel": npv.pv_fuel,
            "pv_ppa": npv.pv_ppa,
            "pv_emission_costs": npv.pv_emission_costs,
            "lcoe": npv.lcoe_usd_per_kwh,
        }
        
        # Incremental analysis vs BAU for non-BAU scenarios
        if name != "bau" and bau_npv is not None:
            savings = bau_npv.pv_total_costs - npv.pv_total_costs
            add_capex = npv.pv_capex - bau_npv.pv_capex
            fuel_savings = bau_npv.pv_fuel - npv.pv_fuel
            bcr = fuel_savings / max(1, add_capex) if add_capex > 0 else None
            cba_output["incremental_vs_bau"][name] = {
                "npv_savings": savings,
                "additional_capex": add_capex,
                "fuel_savings": fuel_savings,
                "bcr": bcr,
            }
    
    # Add recommendation
    npv_costs = {name: data["npv_result"].pv_total_costs for name, data in cba_results.items()}
    least_cost = min(npv_costs, key=npv_costs.get)
    cba_output["recommendation"] = {
        "least_cost": least_cost,
        "least_cost_label": least_cost.replace("_", " ").title(),
    }
    
    with open(output_path / "cba_results.json", "w") as f:
        json.dump(cba_output, f, indent=2)
    
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
    
    print("=" * 70)
    print("  MODEL RUN COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
