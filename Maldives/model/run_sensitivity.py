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
from model.scenarios.nearshore_solar import NearShoreSolarScenario
from model.scenarios.maximum_re import MaximumREScenario
from model.scenarios.lng_transition import LNGTransitionScenario
from model.cba import CBACalculator, SensitivityAnalysis


def print_header():
    print("=" * 70)
    print("  MALDIVES ENERGY CBA - SENSITIVITY ANALYSIS (7 SCENARIOS)")
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
    elif scenario_name == "nearshore_solar":
        scenario = NearShoreSolarScenario(config)
    elif scenario_name == "maximum_re":
        scenario = MaximumREScenario(config)
    elif scenario_name == "lng_transition":
        scenario = LNGTransitionScenario(config)
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
        # Recompute cable_capex_total with new per-km cost
        submarine_cable = config.one_grid.cable_length_km * value
        converter_stations = config.technology.converter_station_cost_per_mw * config.one_grid.cable_capacity_mw
        landing = config.technology.landing_cost_per_end * config.technology.num_landings
        base_capex_val = submarine_cable + converter_stations + landing
        idc = base_capex_val * config.technology.idc_rate
        config.one_grid.cable_capex_total = base_capex_val + idc + config.technology.grid_upgrade_cost
    elif param_name == "ppa_price":
        config.ppa.import_price_2030 = value
    elif param_name == "scc":
        config.economics.social_cost_carbon = value
    elif param_name == "demand_growth":
        # CR-02 fix: Scale all scenario growth rates proportionally (not flat override)
        base_bau = base_config.demand.growth_rates.get("status_quo", 0.05)
        if base_bau != 0:
            scale = value / base_bau
        else:
            scale = 1.0
        for key in config.demand.growth_rates:
            config.demand.growth_rates[key] = base_config.demand.growth_rates[key] * scale
    elif param_name == "solar_cf":
        config.technology.solar_pv_capacity_factor = value
    elif param_name == "gom_cost_share":
        config.one_grid.gom_share_pct = value
    elif param_name == "outage_rate":
        config.cable_outage.outage_rate_per_yr = value
    elif param_name == "idle_fleet_cost":
        config.supply_security.idle_fleet_annual_cost_m = value
    elif param_name == "price_elasticity":
        config.demand.price_elasticity = value
    # L14: Expanded parameters
    elif param_name == "health_damage":
        config.economics.health_damage_cost_per_mwh = value
    elif param_name == "fuel_efficiency":
        config.fuel.kwh_per_liter = value
    elif param_name == "base_demand":
        config.demand.base_demand_gwh = value
    elif param_name == "battery_hours":
        config.technology.battery_hours = value
    elif param_name == "climate_premium":
        config.technology.climate_adaptation_premium = value
    elif param_name == "converter_station":
        config.technology.converter_station_cost_per_mw = value
        # Recompute cable_capex_total
        submarine_cable = config.one_grid.cable_length_km * config.technology.cable_capex_per_km
        converter_stations = value * config.one_grid.cable_capacity_mw
        landing = config.technology.landing_cost_per_end * config.technology.num_landings
        base_capex_val = submarine_cable + converter_stations + landing
        idc = base_capex_val * config.technology.idc_rate
        config.one_grid.cable_capex_total = base_capex_val + idc + config.technology.grid_upgrade_cost
    elif param_name == "connection_cost":
        config.connection.cost_per_household = value
        config.technology.connection_cost_per_hh = value
    elif param_name == "env_externality":
        # Scale all three proportionally
        base_env = base_config.economics.noise_damage_per_mwh + base_config.economics.fuel_spill_risk_per_mwh + base_config.economics.biodiversity_impact_per_mwh
        s = value / base_env if base_env > 0 else 1.0
        config.economics.noise_damage_per_mwh = base_config.economics.noise_damage_per_mwh * s
        config.economics.fuel_spill_risk_per_mwh = base_config.economics.fuel_spill_risk_per_mwh * s
        config.economics.biodiversity_impact_per_mwh = base_config.economics.biodiversity_impact_per_mwh * s
    elif param_name == "sectoral_residential":
        config.demand.sectoral_residential = value
        remainder = 1.0 - value
        config.demand.sectoral_commercial = remainder / 2.0
        config.demand.sectoral_public = remainder / 2.0
    # V2b: S5/S6/S7-specific parameters
    elif param_name == "lng_capex":
        config.lng.capex_per_mw = value
    elif param_name == "lng_fuel_cost":
        config.lng.fuel_cost_per_mwh = value
    elif param_name == "lng_fuel_escalation":
        config.lng.fuel_escalation = value
    elif param_name == "lng_emission_factor":
        config.lng.emission_factor = value
    elif param_name == "floating_capex_premium":
        config.nearshore.floating_solar_capex_premium = value
    elif param_name == "floating_solar_mw":
        config.nearshore.floating_solar_mw = value
    elif param_name == "nearshore_solar_mw":
        config.nearshore.nearshore_solar_mw = value
    elif param_name == "nearshore_cable_cost":
        config.nearshore.nearshore_cable_cost_per_mw = value
    elif param_name == "wte_capex":
        config.wte.capex_per_kw = value
    elif param_name == "deployment_ramp":
        config.green_transition.deployment_ramp_mw_per_year = value
    elif param_name == "male_max_re":
        config.green_transition.male_max_re_share = value
    elif param_name == "battery_ratio":
        config.green_transition.battery_ratio = value
        config.green_transition.islanded_battery_ratio = value
    # CR-03 fix: P8 transport electrification parameters (was missing)
    elif param_name == "ev_adoption_midpoint":
        config.transport.ev_adoption_midpoint = int(value)
    elif param_name == "ev_motorcycle_premium":
        config.transport.e_motorcycle_premium_2026 = value
    elif param_name == "transport_health_damage":
        config.transport.pm25_damage_per_vkm = value
    elif param_name == "petrol_price":
        config.transport.petrol_price_2026 = value
    
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
    "outage_rate": {"name": "Cable Outage Rate", "unit": "events/yr"},
    "idle_fleet_cost": {"name": "Idle Fleet Annual Cost", "unit": "$M/yr"},
    "price_elasticity": {"name": "Price Elasticity", "unit": "ratio"},
    # L14: Expanded parameters
    "health_damage": {"name": "Health Damage Cost", "unit": "USD/MWh"},
    "fuel_efficiency": {"name": "Fuel Efficiency", "unit": "kWh/L"},
    "base_demand": {"name": "Base Demand 2026", "unit": "GWh"},
    "battery_hours": {"name": "Battery Storage Hours", "unit": "hours"},
    "climate_premium": {"name": "Climate Adaptation Premium", "unit": "%"},
    "converter_station": {"name": "Converter Station Cost/MW", "unit": "USD/MW"},
    "connection_cost": {"name": "Connection Cost/HH", "unit": "USD/HH"},
    "env_externality": {"name": "Environmental Externality", "unit": "USD/MWh"},
    "sectoral_residential": {"name": "Sectoral Split (Residential)", "unit": "fraction"},
    # V2b: S5/S6/S7-specific parameters
    "lng_capex": {"name": "LNG CAPEX per MW", "unit": "USD/MW"},
    "lng_fuel_cost": {"name": "LNG Fuel Cost", "unit": "USD/MWh"},
    "lng_fuel_escalation": {"name": "LNG Fuel Escalation", "unit": "%/yr"},
    "lng_emission_factor": {"name": "LNG Emission Factor", "unit": "kgCO2/kWh"},
    "floating_capex_premium": {"name": "Floating Solar CAPEX Premium", "unit": "multiplier"},
    "floating_solar_mw": {"name": "Floating Solar MW", "unit": "MW"},
    "nearshore_solar_mw": {"name": "Near-Shore Solar MW", "unit": "MW"},
    "nearshore_cable_cost": {"name": "Near-Shore Cable Cost/MW", "unit": "USD/MW"},
    "wte_capex": {"name": "WTE CAPEX per kW", "unit": "USD/kW"},
    "deployment_ramp": {"name": "Deployment Ramp", "unit": "MW/yr"},
    "male_max_re": {"name": "Malé Max RE Share", "unit": "fraction"},
    "battery_ratio": {"name": "Battery Ratio", "unit": "MWh/MW"},
    # P8: Transport electrification parameters (F-MO-01)
    "ev_adoption_midpoint": {"name": "EV Adoption Midpoint", "unit": "year"},
    "ev_motorcycle_premium": {"name": "E-Motorcycle Premium", "unit": "USD"},
    "transport_health_damage": {"name": "Transport PM2.5 Damage", "unit": "USD/vkm"},
    "petrol_price": {"name": "Petrol Price 2026", "unit": "USD/L"},
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


def _economic_cost(calc: CBACalculator, results) -> float:
    """F-01 fix: Return economic cost = financial + emission costs.
    
    Using pv_total_costs alone makes SCC invisible to sensitivity analysis
    because emission costs are computed as a separate field in NPVResult.
    """
    npv_r = calc.calculate_npv(results)
    return npv_r.pv_total_costs + npv_r.pv_emission_costs


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
        "nearshore_solar": {},
        "maximum_re": {},
        "lng_transition": {},
    }
    
    # Get base case NPVs
    print("  Computing base case...")
    bau_base = run_scenario_with_config(base_config, "bau")
    fi_base = run_scenario_with_config(base_config, "full_integration")
    ng_base = run_scenario_with_config(base_config, "national_grid")
    ig_base = run_scenario_with_config(base_config, "islanded_green")
    ns_base = run_scenario_with_config(base_config, "nearshore_solar")
    mx_base = run_scenario_with_config(base_config, "maximum_re")
    lng_base = run_scenario_with_config(base_config, "lng_transition")
    
    calc = CBACalculator(base_config)
    bau_npv_base = _economic_cost(calc, bau_base)
    fi_npv_base = _economic_cost(calc, fi_base)
    ng_npv_base = _economic_cost(calc, ng_base)
    ig_npv_base = _economic_cost(calc, ig_base)
    ns_npv_base = _economic_cost(calc, ns_base)
    mx_npv_base = _economic_cost(calc, mx_base)
    lng_npv_base = _economic_cost(calc, lng_base)
    
    print(f"    BAU base: ${bau_npv_base/1e6:,.0f}M")
    print(f"    Full Integration base: ${fi_npv_base/1e6:,.0f}M")
    print(f"    National Grid base: ${ng_npv_base/1e6:,.0f}M")
    print(f"    Islanded Green base: ${ig_npv_base/1e6:,.0f}M")
    print(f"    Near-Shore Solar base: ${ns_npv_base/1e6:,.0f}M")
    print(f"    Maximum RE base: ${mx_npv_base/1e6:,.0f}M")
    print(f"    LNG Transition base: ${lng_npv_base/1e6:,.0f}M")
    print()
    
    for param_key, param_info in PARAMETERS.items():
        print(f"  Testing: {param_info['name']}...")
        
        # Low value
        config_low = modify_config(base_config, param_key, param_info["low"])
        bau_low = run_scenario_with_config(config_low, "bau")
        fi_low = run_scenario_with_config(config_low, "full_integration")
        ng_low = run_scenario_with_config(config_low, "national_grid")
        ig_low = run_scenario_with_config(config_low, "islanded_green")
        ns_low = run_scenario_with_config(config_low, "nearshore_solar")
        mx_low = run_scenario_with_config(config_low, "maximum_re")
        lng_low = run_scenario_with_config(config_low, "lng_transition")
        
        calc_low = CBACalculator(config_low)
        bau_npv_low = _economic_cost(calc_low, bau_low)
        fi_npv_low = _economic_cost(calc_low, fi_low)
        ng_npv_low = _economic_cost(calc_low, ng_low)
        ig_npv_low = _economic_cost(calc_low, ig_low)
        ns_npv_low = _economic_cost(calc_low, ns_low)
        mx_npv_low = _economic_cost(calc_low, mx_low)
        lng_npv_low = _economic_cost(calc_low, lng_low)
        
        # High value
        config_high = modify_config(base_config, param_key, param_info["high"])
        bau_high = run_scenario_with_config(config_high, "bau")
        fi_high = run_scenario_with_config(config_high, "full_integration")
        ng_high = run_scenario_with_config(config_high, "national_grid")
        ig_high = run_scenario_with_config(config_high, "islanded_green")
        ns_high = run_scenario_with_config(config_high, "nearshore_solar")
        mx_high = run_scenario_with_config(config_high, "maximum_re")
        lng_high = run_scenario_with_config(config_high, "lng_transition")
        
        calc_high = CBACalculator(config_high)
        bau_npv_high = _economic_cost(calc_high, bau_high)
        fi_npv_high = _economic_cost(calc_high, fi_high)
        ng_npv_high = _economic_cost(calc_high, ng_high)
        ig_npv_high = _economic_cost(calc_high, ig_high)
        ns_npv_high = _economic_cost(calc_high, ns_high)
        mx_npv_high = _economic_cost(calc_high, mx_high)
        lng_npv_high = _economic_cost(calc_high, lng_high)
        
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
        
        results["nearshore_solar"][param_key] = {
            "name": param_info["name"],
            "base_value": param_info["base"],
            "low_value": param_info["low"],
            "high_value": param_info["high"],
            "base_npv": ns_npv_base,
            "low_npv": ns_npv_low,
            "high_npv": ns_npv_high,
            "range": abs(ns_npv_high - ns_npv_low),
        }
        
        results["maximum_re"][param_key] = {
            "name": param_info["name"],
            "base_value": param_info["base"],
            "low_value": param_info["low"],
            "high_value": param_info["high"],
            "base_npv": mx_npv_base,
            "low_npv": mx_npv_low,
            "high_npv": mx_npv_high,
            "range": abs(mx_npv_high - mx_npv_low),
        }
        
        results["lng_transition"][param_key] = {
            "name": param_info["name"],
            "base_value": param_info["base"],
            "low_value": param_info["low"],
            "high_value": param_info["high"],
            "base_npv": lng_npv_base,
            "low_npv": lng_npv_low,
            "high_npv": lng_npv_high,
            "range": abs(lng_npv_high - lng_npv_low),
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
        "nearshore_solar": "Near-Shore Solar (Uninhabited Islands)",
        "maximum_re": "Maximum RE (Floating + Near-Shore)",
        "lng_transition": "LNG Transition (LNG + Solar)",
    }
    
    for scenario in ["bau", "full_integration", "national_grid", "islanded_green",
                      "nearshore_solar", "maximum_re", "lng_transition"]:
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


def calculate_switching_values(results: Dict) -> Dict:
    """
    P4: Calculate switching values for all key scenario pairs.
    
    For each parameter × scenario pair, finds the parameter value at which
    the two scenarios have equal NPV (linear interpolation from low/high).
    
    This is standard ADB/World Bank practice and communicates robustness
    far more intuitively than tornado diagrams alone.
    
    Reference: ADB (2017) Guidelines for Economic Analysis, §6.37–6.40.
    """
    print("=" * 80)
    print("  P4: SWITCHING VALUE ANALYSIS")
    print("=" * 80)
    print()
    print("  Parameter values at which scenario ranking changes:")
    print("-" * 90)
    
    # Define scenario pairs to compare
    scenario_pairs = [
        ("maximum_re", "lng_transition", "S6 Max RE vs S7 LNG"),
        ("full_integration", "national_grid", "S2 Full Integration vs S3 National Grid"),
        ("national_grid", "islanded_green", "S3 National Grid vs S4 Islanded Green"),
        ("maximum_re", "national_grid", "S6 Max RE vs S3 National Grid"),
        ("nearshore_solar", "maximum_re", "S5 Near-Shore vs S6 Max RE"),
        ("bau", "full_integration", "S1 BAU vs S2 Full Integration"),
    ]
    
    switching = {"scenario_pairs": {}, "summary": []}
    
    for scen_a, scen_b, pair_label in scenario_pairs:
        if scen_a not in results or scen_b not in results:
            continue
        
        pair_key = f"{scen_a}_vs_{scen_b}"
        switching["scenario_pairs"][pair_key] = {
            "label": pair_label,
            "parameters": {},
        }
        
        print(f"\n  --- {pair_label} ---")
        print(f"  {'Parameter':<30} {'Switch Value':>14} {'Unit':>10} {'Base':>10} {'Range':>16} {'Note':>20}")
        print("  " + "-" * 102)
        
        for param_key in results[scen_a]:
            if param_key not in results[scen_b]:
                continue
            
            a_data = results[scen_a][param_key]
            b_data = results[scen_b][param_key]
            
            # Linear slopes: how NPV changes with parameter
            param_range = a_data["high_value"] - a_data["low_value"]
            if param_range == 0:
                continue
            
            a_slope = (a_data["high_npv"] - a_data["low_npv"]) / param_range
            b_slope = (b_data["high_npv"] - b_data["low_npv"]) / param_range
            
            # Switching value: where a_npv(x) = b_npv(x)
            # a_base + a_slope * (x - base) = b_base + b_slope * (x - base)
            # (a_slope - b_slope) * (x - base) = b_base - a_base
            # x = base + (b_base - a_base) / (a_slope - b_slope)
            slope_diff = a_slope - b_slope
            if abs(slope_diff) < 1e-6:
                continue  # Lines are parallel — no switching value
            
            base_value = a_data["base_value"]
            switching_x = base_value + (b_data["base_npv"] - a_data["base_npv"]) / slope_diff
            
            # Check if switching value is within a reasonable range (±3× of test range)
            low_bound = a_data["low_value"] - 2 * param_range
            high_bound = a_data["high_value"] + 2 * param_range
            
            within_range = a_data["low_value"] <= switching_x <= a_data["high_value"]
            near_range = low_bound <= switching_x <= high_bound
            
            # Get unit from PARAM_LABELS
            label_info = PARAM_LABELS.get(param_key, {"name": param_key, "unit": ""})
            param_name = label_info["name"]
            unit = label_info["unit"]
            
            if near_range:
                note = "within range" if within_range else "outside test range"
                
                # Format switching value based on unit
                if unit in ["%", "%/yr", "ratio", "fraction", "multiplier"]:
                    sv_str = f"{switching_x:.4f}"
                elif unit in ["USD/L", "USD/kWh"]:
                    sv_str = f"${switching_x:.3f}"
                elif unit in ["USD/tCO2", "USD/MWh", "USD/MW", "USD/kW", "USD/HH", "USD/km"]:
                    sv_str = f"${switching_x:,.0f}"
                elif unit == "MW":
                    sv_str = f"{switching_x:,.0f}"
                elif unit == "GWh":
                    sv_str = f"{switching_x:,.0f}"
                elif unit == "hours":
                    sv_str = f"{switching_x:.1f}"
                else:
                    sv_str = f"{switching_x:.4g}"
                
                print(f"  {param_name:<30} {sv_str:>14} {unit:>10} {base_value:>10.4g} "
                      f"[{a_data['low_value']:.4g}–{a_data['high_value']:.4g}] {note:>20}")
                
                switching["scenario_pairs"][pair_key]["parameters"][param_key] = {
                    "name": param_name,
                    "switching_value": round(switching_x, 6),
                    "base_value": base_value,
                    "low_value": a_data["low_value"],
                    "high_value": a_data["high_value"],
                    "unit": unit,
                    "within_test_range": within_range,
                    "note": note,
                }
                
                # Add to summary if within test range
                if within_range:
                    switching["summary"].append({
                        "pair": pair_label,
                        "parameter": param_name,
                        "switching_value": round(switching_x, 6),
                        "base_value": base_value,
                        "unit": unit,
                    })
    
    # Print summary
    print()
    print("  " + "=" * 90)
    print("  KEY SWITCHING VALUES (within tested parameter ranges):")
    print("  " + "=" * 90)
    if switching["summary"]:
        for item in switching["summary"]:
            print(f"    • {item['parameter']}: {item['switching_value']:.4g} {item['unit']} "
                  f"(base: {item['base_value']:.4g}) → {item['pair']}")
    else:
        print("    No switching values found within tested ranges — all rankings are robust.")
    print()
    
    return switching


def save_results(results: Dict, switching: Dict = None, output_path: str = "outputs"):
    """Save results to JSON file."""
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output = dict(results)
    if switching:
        output["switching_values"] = switching
    
    with open(output_dir / "sensitivity_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
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
    switching = calculate_switching_values(results)
    
    # Save results
    save_results(results, switching=switching)
    
    print("=" * 70)
    print("  SENSITIVITY ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
