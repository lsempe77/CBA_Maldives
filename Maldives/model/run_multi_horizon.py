"""
Maldives Energy CBA Model - Multi-Horizon Analysis
===================================================

This script runs the CBA for all 7 scenarios across 3 time horizons:
- Short-term: 20 years (2026-2046)
- Medium-term: 30 years (2026-2056)
- Long-term: 50 years (2026-2076)

This allows comparison of how results change with different planning horizons.

Usage:
    python run_multi_horizon.py [--output OUTPUT_DIR]

Author: CBA Model Team
Date: 2026
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List

# Add parent to path for imports
model_dir = Path(__file__).parent
maldives_dir = model_dir.parent
sys.path.insert(0, str(maldives_dir))

from model.config import (
    Config, get_config, BASE_YEAR, 
    END_YEAR_20, END_YEAR_30, END_YEAR_50,
    TIME_HORIZONS
)
from model.scenarios.status_quo import StatusQuoScenario
from model.scenarios.green_transition import NationalGridScenario
from model.scenarios.one_grid import FullIntegrationScenario
from model.scenarios.islanded_green import IslandedGreenScenario
from model.scenarios.nearshore_solar import NearShoreSolarScenario
from model.scenarios.maximum_re import MaximumREScenario
from model.scenarios.lng_transition import LNGTransitionScenario
from model.cba import CBACalculator


# =============================================================================
# HORIZON DEFINITIONS
# =============================================================================

HORIZONS = {
    "short": {
        "label": "Short-term (20 years)",
        "years": 20,
        "end_year": END_YEAR_20,
        "time_horizon": TIME_HORIZONS[20],
    },
    "medium": {
        "label": "Medium-term (30 years)",
        "years": 30,
        "end_year": END_YEAR_30,
        "time_horizon": TIME_HORIZONS[30],
    },
    "long": {
        "label": "Long-term (50 years)",
        "years": 50,
        "end_year": END_YEAR_50,
        "time_horizon": TIME_HORIZONS[50],
    },
}

SCENARIO_CLASSES = {
    "bau": ("BAU (Diesel)", StatusQuoScenario),
    "full_integration": ("Full Integration", FullIntegrationScenario),
    "national_grid": ("National Grid", NationalGridScenario),
    "islanded_green": ("Islanded Green", IslandedGreenScenario),
    "nearshore_solar": ("Near-Shore Solar", NearShoreSolarScenario),
    "maximum_re": ("Maximum RE", MaximumREScenario),
    "lng_transition": ("LNG Transition", LNGTransitionScenario),
}


# =============================================================================
# RESULT STORAGE
# =============================================================================

@dataclass
class HorizonResult:
    """Results for one scenario in one horizon."""
    scenario_name: str
    horizon_name: str
    years: int
    total_costs_million: float
    pv_total_costs_million: float
    pv_capex_million: float
    pv_fuel_million: float
    lcoe_usd_kwh: float
    total_emissions_mtco2: float
    final_re_share: float


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def print_header():
    """Print model header."""
    print("=" * 80)
    print("  MALDIVES ENERGY CBA - MULTI-HORIZON ANALYSIS")
    print("=" * 80)
    print(f"  Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Base Year: {BASE_YEAR}")
    print()
    print("  Horizons:")
    for key, h in HORIZONS.items():
        print(f"    - {h['label']}: {BASE_YEAR} to {h['end_year']}")
    print("=" * 80)
    print()


def create_config_for_horizon(horizon_key: str) -> Config:
    """Create a config object configured for a specific time horizon.
    
    Uses config.end_year_20/30/50 (loaded from parameters.csv Time category)
    to override the HORIZONS dict, ensuring CSV is the single source of truth.
    """
    config = get_config(load_from_csv=True)
    
    # Override horizon end years from config (CSV-driven) if they differ
    horizon_end_map = {
        "short": config.end_year_20,
        "medium": config.end_year_30,
        "long": config.end_year_50,
    }
    end_year = horizon_end_map.get(horizon_key, HORIZONS[horizon_key]["end_year"])
    config.end_year = end_year
    config.time_horizon = list(range(config.base_year, end_year + 1))
    
    return config


def run_scenario_for_horizon(
    scenario_key: str, 
    horizon_key: str,
    config: Config
) -> HorizonResult:
    """Run a single scenario for a single horizon."""
    label, ScenarioClass = SCENARIO_CLASSES[scenario_key]
    horizon = HORIZONS[horizon_key]
    
    # Run scenario
    scenario = ScenarioClass(config)
    results = scenario.run()
    summary = scenario.get_summary()
    
    # Calculate NPV
    calculator = CBACalculator(config)
    npv = calculator.calculate_npv(results)
    
    return HorizonResult(
        scenario_name=scenario_key,
        horizon_name=horizon_key,
        years=horizon["years"],
        total_costs_million=summary["total_costs_million"],
        pv_total_costs_million=npv.pv_total_costs / 1e6,
        pv_capex_million=npv.pv_capex / 1e6,
        pv_fuel_million=npv.pv_fuel / 1e6,
        lcoe_usd_kwh=npv.lcoe_usd_per_kwh,
        total_emissions_mtco2=summary["total_emissions_mtco2"],
        final_re_share=summary["final_re_share"],
    )


def run_all_horizons() -> Dict[str, Dict[str, HorizonResult]]:
    """Run all scenarios across all horizons."""
    results = {}
    
    for horizon_key in HORIZONS:
        print(f"\n--- Running {HORIZONS[horizon_key]['label']} ---")
        config = create_config_for_horizon(horizon_key)
        
        results[horizon_key] = {}
        
        for scenario_key, (label, _) in SCENARIO_CLASSES.items():
            print(f"  {label}...", end=" ", flush=True)
            result = run_scenario_for_horizon(scenario_key, horizon_key, config)
            results[horizon_key][scenario_key] = result
            print(f"✓ (PV Costs: ${result.pv_total_costs_million:,.0f}M)")
    
    return results


def print_comparison_table(results: Dict[str, Dict[str, HorizonResult]]):
    """Print comparison table across horizons."""
    
    print()
    print("=" * 100)
    print("  MULTI-HORIZON COMPARISON: PV Total Costs (Million USD)")
    print("=" * 100)
    print()
    
    # Header
    print(f"{'Scenario':<20}", end="")
    for h_key in HORIZONS:
        print(f"{HORIZONS[h_key]['label']:>25}", end="")
    print()
    print("-" * 95)
    
    # Data rows
    for s_key, (label, _) in SCENARIO_CLASSES.items():
        print(f"{label:<20}", end="")
        for h_key in HORIZONS:
            result = results[h_key][s_key]
            print(f"${result.pv_total_costs_million:>22,.0f}", end="")
        print()
    
    print()
    
    # LCOE comparison
    print("=" * 100)
    print("  MULTI-HORIZON COMPARISON: Levelized Cost of Energy (USD/kWh)")
    print("=" * 100)
    print()
    
    print(f"{'Scenario':<20}", end="")
    for h_key in HORIZONS:
        print(f"{HORIZONS[h_key]['label']:>25}", end="")
    print()
    print("-" * 95)
    
    for s_key, (label, _) in SCENARIO_CLASSES.items():
        print(f"{label:<20}", end="")
        for h_key in HORIZONS:
            result = results[h_key][s_key]
            print(f"${result.lcoe_usd_kwh:>23.4f}", end="")
        print()
    
    print()
    
    # Emissions comparison
    print("=" * 100)
    print("  MULTI-HORIZON COMPARISON: Total Emissions (MtCO2)")
    print("=" * 100)
    print()
    
    print(f"{'Scenario':<20}", end="")
    for h_key in HORIZONS:
        print(f"{HORIZONS[h_key]['label']:>25}", end="")
    print()
    print("-" * 95)
    
    for s_key, (label, _) in SCENARIO_CLASSES.items():
        print(f"{label:<20}", end="")
        for h_key in HORIZONS:
            result = results[h_key][s_key]
            print(f"{result.total_emissions_mtco2:>24.2f}", end="")
        print()
    
    print()


def print_incremental_analysis(results: Dict[str, Dict[str, HorizonResult]]):
    """Print incremental analysis vs BAU for each horizon."""
    
    print("=" * 100)
    print("  INCREMENTAL ANALYSIS: Savings vs BAU (Million USD)")
    print("=" * 100)
    print()
    
    for h_key, horizon in HORIZONS.items():
        print(f"--- {horizon['label']} ---")
        
        bau = results[h_key]["bau"]
        
        print(f"{'Scenario':<20} {'Add. CAPEX':>15} {'Fuel Savings':>15} {'Net Savings':>15} {'BCR':>10}")
        print("-" * 80)
        
        for s_key, (label, _) in SCENARIO_CLASSES.items():
            if s_key == "bau":
                continue
            
            result = results[h_key][s_key]
            
            add_capex = result.pv_capex_million - bau.pv_capex_million
            fuel_savings = bau.pv_fuel_million - result.pv_fuel_million
            net_savings = bau.pv_total_costs_million - result.pv_total_costs_million
            bcr = fuel_savings / add_capex if add_capex > 0 else float('inf')
            
            print(f"{label:<20} ${add_capex:>13,.0f} ${fuel_savings:>13,.0f} ${net_savings:>13,.0f} {bcr:>10.2f}")
        
        print()


def print_recommendations(results: Dict[str, Dict[str, HorizonResult]]):
    """Print recommendations for each horizon."""
    
    print("=" * 100)
    print("  RECOMMENDATIONS BY HORIZON")
    print("=" * 100)
    print()
    
    for h_key, horizon in HORIZONS.items():
        # Find least cost
        least_cost = min(
            results[h_key].items(), 
            key=lambda x: x[1].pv_total_costs_million
        )
        
        # Find lowest LCOE
        lowest_lcoe = min(
            results[h_key].items(),
            key=lambda x: x[1].lcoe_usd_kwh
        )
        
        # Find lowest emissions
        lowest_emissions = min(
            results[h_key].items(),
            key=lambda x: x[1].total_emissions_mtco2
        )
        
        print(f"--- {horizon['label']} ({BASE_YEAR}-{horizon['end_year']}) ---")
        print(f"  Least Total Cost:    {SCENARIO_CLASSES[least_cost[0]][0]} (${least_cost[1].pv_total_costs_million:,.0f}M)")
        print(f"  Lowest LCOE:         {SCENARIO_CLASSES[lowest_lcoe[0]][0]} (${lowest_lcoe[1].lcoe_usd_kwh:.4f}/kWh)")
        print(f"  Lowest Emissions:    {SCENARIO_CLASSES[lowest_emissions[0]][0]} ({lowest_emissions[1].total_emissions_mtco2:.1f} MtCO2)")
        print()
    
    # Overall recommendation
    print("=" * 100)
    print("  OVERALL RECOMMENDATION")
    print("=" * 100)
    print()
    
    # Count how many times each scenario wins
    wins = {s: 0 for s in SCENARIO_CLASSES}
    for h_key in HORIZONS:
        least_cost = min(results[h_key].items(), key=lambda x: x[1].pv_total_costs_million)
        wins[least_cost[0]] += 1
    
    winner = max(wins.items(), key=lambda x: x[1])
    print(f"  The '{SCENARIO_CLASSES[winner[0]][0]}' scenario has the lowest PV costs")
    print(f"  across {winner[1]} of {len(HORIZONS)} time horizons analyzed.")
    print()


def save_results(
    results: Dict[str, Dict[str, HorizonResult]], 
    output_dir: str
):
    """Save results to JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Convert to serializable format
    output = {}
    for h_key, horizon_results in results.items():
        output[h_key] = {
            "horizon_info": HORIZONS[h_key],
            "scenarios": {}
        }
        for s_key, result in horizon_results.items():
            output[h_key]["scenarios"][s_key] = {
                "label": SCENARIO_CLASSES[s_key][0],
                "pv_total_costs_million": result.pv_total_costs_million,
                "pv_capex_million": result.pv_capex_million,
                "pv_fuel_million": result.pv_fuel_million,
                "lcoe_usd_kwh": result.lcoe_usd_kwh,
                "total_emissions_mtco2": result.total_emissions_mtco2,
                "final_re_share": result.final_re_share,
            }
    
    with open(output_path / "multi_horizon_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Results saved to {output_path / 'multi_horizon_results.json'}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Maldives Energy CBA - Multi-Horizon Analysis"
    )
    parser.add_argument(
        "--output", "-o",
        default="outputs",
        help="Output directory for results",
    )
    args = parser.parse_args()
    
    # Print header
    print_header()
    
    # Run all horizons
    print("Running scenarios across all horizons...")
    results = run_all_horizons()
    
    # Print results
    print_comparison_table(results)
    print_incremental_analysis(results)
    print_recommendations(results)
    
    # Save results
    save_results(results, args.output)
    
    print("=" * 80)
    print("  MULTI-HORIZON ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
