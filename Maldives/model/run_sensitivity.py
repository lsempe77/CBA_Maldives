"""
Maldives Energy CBA - Sensitivity Analysis Runner
==================================================

This script runs comprehensive sensitivity analysis:
1. One-way sensitivity for all key parameters
2. Tornado diagram data generation
3. Switching value calculations
4. Monte Carlo simulation

Usage:
    python -m model.run_sensitivity
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from copy import deepcopy
import json

# Add model to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.config import Config, get_config, SENSITIVITY_PARAMS
from model.scenarios.status_quo import StatusQuoScenario
from model.scenarios.green_transition import NationalGridScenario
from model.scenarios.one_grid import FullIntegrationScenario
from model.scenarios.islanded_green import IslandedGreenScenario
from model.cba import CBACalculator, SensitivityAnalysis


def print_header():
    print("=" * 70)
    print("  MALDIVES ENERGY CBA - SENSITIVITY ANALYSIS (4 SCENARIOS)")
    print("=" * 70)
    print(f"  Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


def run_scenario_with_config(config: Config, scenario_name: str):
    """Run a specific scenario with given config."""
    if scenario_name == "bau":
        scenario = StatusQuoScenario(config)
    elif scenario_name == "full_integration":
        scenario = FullIntegrationScenario(config)
    elif scenario_name == "national_grid":
        scenario = NationalGridScenario(config)
    elif scenario_name == "islanded_green":
        scenario = IslandedGreenScenario(config)
    else:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    
    return scenario.run()


def modify_config(base_config: Config, param_name: str, value: float) -> Config:
    """Create modified config with specified parameter value."""
    config = deepcopy(base_config)
    
    if param_name == "discount_rate":
        config.economics.discount_rate = value
    elif param_name == "diesel_price":
        config.fuel.price_2026 = value
    elif param_name == "diesel_escalation":
        config.fuel.price_escalation = value
    elif param_name == "solar_capex":
        config.technology.solar_pv_capex = value
    elif param_name == "battery_capex":
        config.technology.battery_capex = value
    elif param_name == "cable_capex":
        config.technology.cable_capex_per_km = value
    elif param_name == "ppa_price":
        config.ppa.import_price_2030 = value
    elif param_name == "scc":
        config.economics.social_cost_carbon = value
    elif param_name == "demand_growth":
        for key in config.demand.growth_rates:
            config.demand.growth_rates[key] = value
    elif param_name == "solar_cf":
        config.technology.solar_pv_capacity_factor = value
    elif param_name == "gom_cost_share":
        config.one_grid.gom_share_pct = value
    
    return config


# Parameter definitions — loaded from SENSITIVITY_PARAMS (which reads from parameters.csv)
# Labels and units for display
PARAM_LABELS = {
    "discount_rate": {"name": "Discount Rate", "unit": "%"},
    "diesel_price": {"name": "Diesel Price", "unit": "USD/L"},
    "diesel_escalation": {"name": "Diesel Escalation", "unit": "%/yr"},
    "solar_capex": {"name": "Solar PV CAPEX", "unit": "USD/kW"},
    "battery_capex": {"name": "Battery CAPEX", "unit": "USD/kWh"},
    "cable_capex": {"name": "Cable CAPEX", "unit": "USD/km"},
    "ppa_price": {"name": "Import PPA Price", "unit": "USD/kWh"},
    "scc": {"name": "Social Cost of Carbon", "unit": "USD/tCO2"},
    "gom_cost_share": {"name": "GoM Cable Cost Share", "unit": "%"},
    "demand_growth": {"name": "Demand Growth Rate", "unit": "%/yr"},
    "solar_cf": {"name": "Solar Capacity Factor", "unit": "ratio"},
}


def _build_parameters():
    """Build PARAMETERS dict from SENSITIVITY_PARAMS (populated by CSV)."""
    # Ensure config is loaded first (triggers CSV read → populates SENSITIVITY_PARAMS)
    _ = get_config()
    
    # Map from SENSITIVITY_PARAMS keys to modify_config keys
    key_map = {
        "cable_capex_per_km": "cable_capex",
        "import_price": "ppa_price",
        "social_cost_carbon": "scc",
    }
    
    params = {}
    for sens_key, vals in SENSITIVITY_PARAMS.items():
        config_key = key_map.get(sens_key, sens_key)
        label = PARAM_LABELS.get(config_key, {"name": sens_key, "unit": ""})
        params[config_key] = {
            "name": label["name"],
            "base": vals["base"],
            "low": vals["low"],
            "high": vals["high"],
            "unit": label["unit"],
        }
    return params


def run_one_way_sensitivity(base_config: Config) -> Dict:
    """
    Run one-way sensitivity for all parameters.
    """
    print("Running One-Way Sensitivity Analysis...")
    print("-" * 50)
    
    PARAMETERS = _build_parameters()
    
    results = {
        "bau": {},
        "full_integration": {},
        "national_grid": {},
        "islanded_green": {},
    }
    
    # Get base case NPVs
    print("  Computing base case...")
    bau_base = run_scenario_with_config(base_config, "bau")
    fi_base = run_scenario_with_config(base_config, "full_integration")
    ng_base = run_scenario_with_config(base_config, "national_grid")
    ig_base = run_scenario_with_config(base_config, "islanded_green")
    
    calc = CBACalculator(base_config)
    bau_npv_base = calc.calculate_npv(bau_base).pv_total_costs
    fi_npv_base = calc.calculate_npv(fi_base).pv_total_costs
    ng_npv_base = calc.calculate_npv(ng_base).pv_total_costs
    ig_npv_base = calc.calculate_npv(ig_base).pv_total_costs
    
    print(f"    BAU base: ${bau_npv_base/1e6:,.0f}M")
    print(f"    Full Integration base: ${fi_npv_base/1e6:,.0f}M")
    print(f"    National Grid base: ${ng_npv_base/1e6:,.0f}M")
    print(f"    Islanded Green base: ${ig_npv_base/1e6:,.0f}M")
    print()
    
    for param_key, param_info in PARAMETERS.items():
        print(f"  Testing: {param_info['name']}...")
        
        # Low value
        config_low = modify_config(base_config, param_key, param_info["low"])
        bau_low = run_scenario_with_config(config_low, "bau")
        fi_low = run_scenario_with_config(config_low, "full_integration")
        ng_low = run_scenario_with_config(config_low, "national_grid")
        ig_low = run_scenario_with_config(config_low, "islanded_green")
        
        calc_low = CBACalculator(config_low)
        bau_npv_low = calc_low.calculate_npv(bau_low).pv_total_costs
        fi_npv_low = calc_low.calculate_npv(fi_low).pv_total_costs
        ng_npv_low = calc_low.calculate_npv(ng_low).pv_total_costs
        ig_npv_low = calc_low.calculate_npv(ig_low).pv_total_costs
        
        # High value
        config_high = modify_config(base_config, param_key, param_info["high"])
        bau_high = run_scenario_with_config(config_high, "bau")
        fi_high = run_scenario_with_config(config_high, "full_integration")
        ng_high = run_scenario_with_config(config_high, "national_grid")
        ig_high = run_scenario_with_config(config_high, "islanded_green")
        
        calc_high = CBACalculator(config_high)
        bau_npv_high = calc_high.calculate_npv(bau_high).pv_total_costs
        fi_npv_high = calc_high.calculate_npv(fi_high).pv_total_costs
        ng_npv_high = calc_high.calculate_npv(ng_high).pv_total_costs
        ig_npv_high = calc_high.calculate_npv(ig_high).pv_total_costs
        
        # Store results
        results["bau"][param_key] = {
            "name": param_info["name"],
            "base_value": param_info["base"],
            "low_value": param_info["low"],
            "high_value": param_info["high"],
            "base_npv": bau_npv_base,
            "low_npv": bau_npv_low,
            "high_npv": bau_npv_high,
            "range": abs(bau_npv_high - bau_npv_low),
        }
        
        results["full_integration"][param_key] = {
            "name": param_info["name"],
            "base_value": param_info["base"],
            "low_value": param_info["low"],
            "high_value": param_info["high"],
            "base_npv": fi_npv_base,
            "low_npv": fi_npv_low,
            "high_npv": fi_npv_high,
            "range": abs(fi_npv_high - fi_npv_low),
        }
        
        results["national_grid"][param_key] = {
            "name": param_info["name"],
            "base_value": param_info["base"],
            "low_value": param_info["low"],
            "high_value": param_info["high"],
            "base_npv": ng_npv_base,
            "low_npv": ng_npv_low,
            "high_npv": ng_npv_high,
            "range": abs(ng_npv_high - ng_npv_low),
        }
        
        results["islanded_green"][param_key] = {
            "name": param_info["name"],
            "base_value": param_info["base"],
            "low_value": param_info["low"],
            "high_value": param_info["high"],
            "base_npv": ig_npv_base,
            "low_npv": ig_npv_low,
            "high_npv": ig_npv_high,
            "range": abs(ig_npv_high - ig_npv_low),
        }
    
    print()
    return results


def print_sensitivity_results(results: Dict):
    """Print formatted sensitivity results."""
    print("=" * 80)
    print("  ONE-WAY SENSITIVITY RESULTS")
    print("=" * 80)
    
    scenario_labels = {
        "bau": "BAU (Diesel)",
        "full_integration": "Full Integration (India + Inter-Island + RE)",
        "national_grid": "National Grid (Inter-Island + RE)",
        "islanded_green": "Islanded Green (Per-Island RE)",
    }
    
    for scenario in ["bau", "full_integration", "national_grid", "islanded_green"]:
        scenario_label = scenario_labels.get(scenario, scenario)
        print(f"\n--- {scenario_label} ---")
        print(f"{'Parameter':<25} {'Low NPV':>12} {'Base NPV':>12} {'High NPV':>12} {'Range':>12}")
        print("-" * 75)
        
        # Sort by range (descending)
        sorted_params = sorted(
            results[scenario].items(),
            key=lambda x: x[1]["range"],
            reverse=True,
        )
        
        for param_key, data in sorted_params:
            print(f"{data['name']:<25} ${data['low_npv']/1e6:>10,.0f}M ${data['base_npv']/1e6:>10,.0f}M ${data['high_npv']/1e6:>10,.0f}M ${data['range']/1e6:>10,.0f}M")
    
    print()


def print_tornado_ranking(results: Dict):
    """Print tornado diagram ranking."""
    print("=" * 80)
    print("  TORNADO DIAGRAM - PARAMETER RANKING BY IMPACT")
    print("=" * 80)
    
    # Calculate incremental sensitivity (Full Integration vs BAU)
    incremental = {}
    for param_key in results["bau"]:
        bau = results["bau"][param_key]
        fi = results["full_integration"][param_key]
        
        # Incremental NPV at each point (savings = BAU - FI)
        base_incr = bau["base_npv"] - fi["base_npv"]
        low_incr = bau["low_npv"] - fi["low_npv"]
        high_incr = bau["high_npv"] - fi["high_npv"]
        
        incremental[param_key] = {
            "name": bau["name"],
            "base_incr": base_incr,
            "low_incr": low_incr,
            "high_incr": high_incr,
            "range": abs(high_incr - low_incr),
        }
    
    print("\n--- Full Integration vs BAU (Savings) ---")
    print(f"{'Parameter':<25} {'Low Savings':>14} {'Base Savings':>14} {'High Savings':>14} {'Range':>12}")
    print("-" * 85)
    
    sorted_params = sorted(
        incremental.items(),
        key=lambda x: x[1]["range"],
        reverse=True,
    )
    
    for param_key, data in sorted_params:
        print(f"{data['name']:<25} ${data['low_incr']/1e6:>12,.0f}M ${data['base_incr']/1e6:>12,.0f}M ${data['high_incr']/1e6:>12,.0f}M ${data['range']/1e6:>10,.0f}M")
    
    print("\n  PARAMETER RANKING (by impact on Full Integration advantage):")
    for i, (param_key, data) in enumerate(sorted_params[:5], 1):
        print(f"    {i}. {data['name']}: ±${data['range']/2/1e6:.0f}M")
    
    print()


def calculate_switching_values(results: Dict):
    """Calculate and print switching values."""
    print("=" * 80)
    print("  SWITCHING VALUES")
    print("=" * 80)
    print()
    print("  Parameter values at which scenario ranking changes:")
    print("-" * 60)
    
    # Diesel price: at what price does BAU = Full Integration?
    bau_diesel = results["bau"]["diesel_price"]
    fi_diesel = results["full_integration"]["diesel_price"]
    
    # Linear interpolation
    bau_slope = (bau_diesel["high_npv"] - bau_diesel["low_npv"]) / (bau_diesel["high_value"] - bau_diesel["low_value"])
    fi_slope = (fi_diesel["high_npv"] - fi_diesel["low_npv"]) / (fi_diesel["high_value"] - fi_diesel["low_value"])
    
    if bau_slope != fi_slope:
        # BAU and FI intersect when: bau_base + bau_slope*(p-base) = fi_base + fi_slope*(p-base)
        # Solving: p = base + (fi_base - bau_base) / (bau_slope - fi_slope)
        switching_diesel = bau_diesel["base_value"] + (fi_diesel["base_npv"] - bau_diesel["base_npv"]) / (bau_slope - fi_slope)
        print(f"  Diesel price: ${switching_diesel:.2f}/L (BAU = Full Integration)")
        if switching_diesel < bau_diesel["low_value"]:
            print(f"    → Below tested range - Full Integration always preferred")
    
    # PPA price: at what price does Full Integration = National Grid?
    ng_ppa = results["national_grid"]["ppa_price"]
    fi_ppa = results["full_integration"]["ppa_price"]
    
    fi_ppa_slope = (fi_ppa["high_npv"] - fi_ppa["low_npv"]) / (fi_ppa["high_value"] - fi_ppa["low_value"])
    
    if fi_ppa_slope != 0:
        # FI = NG when: fi_base + fi_slope*(p-base) = ng_base
        # Solving: p = base + (ng_base - fi_base) / fi_slope
        switching_ppa = fi_ppa["base_value"] + (ng_ppa["base_npv"] - fi_ppa["base_npv"]) / fi_ppa_slope
        print(f"  Import PPA price: ${switching_ppa:.3f}/kWh (Full Integration = National Grid)")
        if switching_ppa > fi_ppa["high_value"]:
            print(f"    → Above tested range - Full Integration preferred in all cases")
    
    print()


def save_results(results: Dict, output_path: str = "outputs"):
    """Save results to JSON file."""
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "sensitivity_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to {output_dir / 'sensitivity_results.json'}")


def main():
    print_header()
    
    # Load base configuration
    print("Loading base configuration...")
    base_config = get_config()
    print(f"  Discount rate: {base_config.economics.discount_rate:.1%}")
    print(f"  Diesel price: ${base_config.fuel.price_2026}/L")
    print()
    
    # Run one-way sensitivity
    results = run_one_way_sensitivity(base_config)
    
    # Print results
    print_sensitivity_results(results)
    print_tornado_ranking(results)
    calculate_switching_values(results)
    
    # Save results
    save_results(results)
    
    print("=" * 70)
    print("  SENSITIVITY ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
