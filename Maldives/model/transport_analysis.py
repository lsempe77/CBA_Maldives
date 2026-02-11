"""
Transport Electrification Analysis (P8)
========================================

Supplementary module that models EV adoption in the Maldives using a logistic
S-curve across three scenarios (Low / Medium / High).  Quantifies:

  - Fleet projection (total vehicles × EV share per year)
  - Petroleum fuel displacement (litres saved)
  - Additional electricity demand from EV charging (GWh/yr)
  - Health co-benefits (avoided PM2.5, NOx, noise in dense Malé)
  - CO₂ emission reduction from switching ICE → EV
  - Charging infrastructure investment
  - Vehicle cost differential (EV premium declining over time)
  - NPV of net transport electrification benefits

Context
-------
Maldives has ~131,000 registered vehicles (92 % motorcycles, 4 % EV share
in 2026).  The fleet is concentrated in Greater Malé (population density
~65,000/km²), making air-quality gains from EV transition especially high.

This module does NOT modify the core energy CBA scenarios.  It runs
alongside them as a supplementary analysis (same pattern as
financing_analysis.py and distributional_analysis.py).

All parameters loaded from parameters.csv via config.py → get_config().

References
----------
- Malé City Council / World Bank (2022) — fleet size
- gathunkaaru.com (2024) — motorcycle share, EV count
- ESMAP TA (2024) — EV transition techno-economics for SIDS
- UNDP/MOTCA (2024) — 5 solar-backed pilot charging stations
- Parry et al. (2014) IMF WP/14/199 — urban air pollution damage costs
- IEA GEVO (2024) — e-motorcycle energy consumption, cost trends
- ICCT (2021) — ICE motorcycle emissions and fuel consumption
- Griliches (1957) — logistic diffusion of technology

Author: CBA Model Team
Date: 2025
"""

import math
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from model.config import Config, get_config, BASE_YEAR, END_YEAR


# ── Logistic S-curve ────────────────────────────────────────────────

def _logistic_ev_share(
    year: int,
    s_initial: float,
    s_max: float,
    t_mid: int,
    k: float,
) -> float:
    """
    Logistic S-curve for EV adoption share.
    
    share(t) = s_initial + (s_max - s_initial) / (1 + exp(-k * (t - t_mid)))
    
    Args:
        year:      Calendar year
        s_initial: EV share in base year (e.g. 0.04)
        s_max:     Asymptotic maximum EV share (scenario target)
        t_mid:     Midpoint year (inflection of fastest growth)
        k:         Steepness parameter (1/yr)
    
    Returns:
        EV share of total fleet in [s_initial, s_max]
    """
    exponent = -k * (year - t_mid)
    # Clamp to avoid overflow
    exponent = max(min(exponent, 50), -50)
    share = s_initial + (s_max - s_initial) / (1 + math.exp(exponent))
    return min(max(share, s_initial), s_max)


# ── Fleet projection ───────────────────────────────────────────────

def _project_fleet(
    config: Config,
    years: List[int],
) -> List[int]:
    """Project total vehicle fleet for each year."""
    fleet = []
    base_fleet = config.transport.total_vehicles_2026
    g = config.transport.fleet_growth_rate
    for year in years:
        t = year - config.base_year
        fleet.append(int(base_fleet * (1 + g) ** t))
    return fleet


# ── Year-by-year analysis ──────────────────────────────────────────

def _analyse_scenario(
    config: Config,
    years: List[int],
    ev_target: float,
    scenario_label: str,
) -> Dict:
    """
    Run year-by-year transport electrification analysis for one scenario.
    
    Returns dict with annual arrays and cumulative totals.
    """
    tr = config.transport
    discount_rate = config.economics.discount_rate
    base_year = config.base_year
    
    # Fleet projection
    fleet = _project_fleet(config, years)
    
    # Annual arrays
    ev_shares: List[float] = []
    ev_counts: List[int] = []
    ice_counts: List[int] = []
    
    # Benefits arrays (annual, undiscounted)
    petrol_saved_litres: List[float] = []
    electricity_demand_mwh: List[float] = []
    fuel_cost_savings: List[float] = []
    maintenance_savings: List[float] = []
    health_benefits: List[float] = []
    co2_avoided_tonnes: List[float] = []
    
    # Cost arrays
    vehicle_premium_cost: List[float] = []
    charging_infra_cost: List[float] = []
    electricity_cost: List[float] = []
    
    # Net benefit (undiscounted)
    net_benefit: List[float] = []
    
    # Cumulative stations built (to avoid double-counting)
    stations_needed_prev = 0
    
    for i, year in enumerate(years):
        t = year - base_year
        
        # EV share from logistic curve
        ev_share = _logistic_ev_share(
            year, tr.ev_share_2026, ev_target, tr.ev_adoption_midpoint, tr.ev_adoption_steepness
        )
        ev_shares.append(round(ev_share, 4))
        
        n_ev = int(fleet[i] * ev_share)
        n_ice = fleet[i] - n_ev
        ev_counts.append(n_ev)
        ice_counts.append(n_ice)
        
        # -- Motorcycle subset (92% of fleet) --
        mc_ev = int(n_ev * tr.motorcycle_share)
        mc_ice = int(n_ice * tr.motorcycle_share)
        
        # Annual km per motorcycle
        annual_km = tr.motorcycle_daily_km * 365
        
        # Counterfactual: if all mc_ev were still ICE, how much petrol?
        ice_l_per_km = tr.ice_fuel_consumption_l_100km / 100
        petrol_saved = mc_ev * annual_km * ice_l_per_km
        petrol_saved_litres.append(petrol_saved)
        
        # Additional electricity demand from EVs
        ev_elec_kwh = mc_ev * annual_km * tr.ev_energy_per_km
        ev_elec_mwh = ev_elec_kwh / 1000
        electricity_demand_mwh.append(ev_elec_mwh)
        
        # Petrol price in year t
        petrol_price_t = tr.petrol_price_2026 * (1 + tr.petrol_price_escalation) ** t
        
        # Fuel cost savings (petrol avoided - electricity cost)
        fuel_savings = petrol_saved * petrol_price_t
        fuel_cost_savings.append(fuel_savings)
        
        # Electricity cost for EVs (use residential tariff from config)
        elec_tariff = config.current_system.current_retail_tariff  # $/kWh
        elec_cost = ev_elec_kwh * elec_tariff
        electricity_cost.append(elec_cost)
        
        # Maintenance savings (ICE costs more)
        maint_savings = mc_ev * (tr.ice_annual_maintenance - tr.ev_annual_maintenance)
        maintenance_savings.append(maint_savings)
        
        # Health benefits: avoided PM2.5 + NOx + noise from EV-km replacing ICE-km
        damage_per_vkm = tr.pm25_damage_per_vkm + tr.nox_damage_per_vkm
        health_benefit = mc_ev * annual_km * damage_per_vkm
        noise_benefit = mc_ev * annual_km * tr.noise_reduction_per_ev_km
        total_health = health_benefit + noise_benefit
        health_benefits.append(total_health)
        
        # CO₂ avoided (tonnes) — ICE emissions displaced, net of grid emission for EV charging
        co2_ice_avoided = mc_ev * annual_km * tr.ice_gco2_per_km / 1e6  # tonnes
        # NOTE (MR-06): Uses static diesel EF for grid emissions. This is conservative —
        # as RE share increases, the actual grid EF declines. Since transport analysis
        # is a supplementary module (not linked to scenario RE trajectories), the
        # static assumption avoids coupling complexity and overstates EV grid CO₂.
        co2_grid = ev_elec_mwh * config.fuel.emission_factor_kg_co2_per_kwh / 1000  # tonnes (MWh × kgCO₂/kWh / 1000 → tCO₂)
        # LW-06: Clamped to >= 0. In theory, if grid is very dirty and EVs are very
        # efficient, EV charging could emit more than ICE displaced. This is unlikely
        # with current Maldives parameters (motorcycle ICE is ~50 gCO2/km, grid EF
        # would need to be extremely high). Remove clamp for full lifecycle accuracy.
        co2_net = max(co2_ice_avoided - co2_grid, 0)
        co2_avoided_tonnes.append(co2_net)
        
        # Vehicle premium cost: new EVs adopted this year × declining premium
        if i == 0:
            new_evs = n_ev  # All existing EVs already paid
            new_evs = max(n_ev - int(config.transport.total_vehicles_2026 * tr.ev_share_2026), 0)
        else:
            new_evs = max(ev_counts[i] - ev_counts[i - 1], 0)
        
        premium_t = tr.e_motorcycle_premium_2026 * (1 - tr.premium_decline_rate) ** t
        premium_t = max(premium_t, 0)  # Can't go negative
        # LW-05: Only motorcycle EVs carry a premium cost (92% of fleet).
        # The remaining 8% (cars/vans) have negligible count in Maldives.
        # For a more complete model, add separate car EV premiums.
        vehicle_cost = new_evs * tr.motorcycle_share * premium_t
        vehicle_premium_cost.append(vehicle_cost)
        
        # Charging infrastructure: incremental stations needed
        stations_needed = max(1, math.ceil(n_ev / tr.vehicles_per_station))
        new_stations = max(stations_needed - stations_needed_prev, 0)
        stations_needed_prev = stations_needed
        charging_cost = new_stations * tr.charging_station_cost
        charging_infra_cost.append(charging_cost)
        
        # Net benefit = fuel savings + maintenance savings + health + SCC × CO₂
        #              - vehicle premium - charging infra - electricity cost
        scc_t = config.economics.social_cost_carbon * (1 + config.economics.scc_annual_growth) ** t
        co2_value = co2_net * scc_t
        
        net_b = (
            fuel_savings
            + maint_savings
            + total_health
            + co2_value
            - vehicle_cost
            - charging_cost
            - elec_cost
        )
        net_benefit.append(net_b)
    
    # Discount to NPV
    discount_factors = [1 / (1 + discount_rate) ** (y - base_year) for y in years]
    npv_benefits = sum(
        (fuel_cost_savings[i] + maintenance_savings[i] + health_benefits[i]) * discount_factors[i]
        for i in range(len(years))
    )
    npv_costs = sum(
        (vehicle_premium_cost[i] + charging_infra_cost[i] + electricity_cost[i]) * discount_factors[i]
        for i in range(len(years))
    )
    
    # SCC-valued CO₂
    npv_co2_value = 0
    for i, year in enumerate(years):
        t = year - base_year
        scc_t = config.economics.social_cost_carbon * (1 + config.economics.scc_annual_growth) ** t
        npv_co2_value += co2_avoided_tonnes[i] * scc_t * discount_factors[i]
    
    npv_net = sum(net_benefit[i] * discount_factors[i] for i in range(len(years)))
    
    return {
        "scenario": scenario_label,
        "ev_target": ev_target,
        "years": years,
        "fleet_total": fleet,
        "ev_share": ev_shares,
        "ev_count": ev_counts,
        "ice_count": ice_counts,
        # Annual flows (undiscounted)
        "petrol_saved_litres": [round(x, 0) for x in petrol_saved_litres],
        "electricity_demand_mwh": [round(x, 1) for x in electricity_demand_mwh],
        "electricity_demand_gwh_final": round(electricity_demand_mwh[-1] / 1000, 2),
        "fuel_cost_savings": [round(x, 0) for x in fuel_cost_savings],
        "maintenance_savings": [round(x, 0) for x in maintenance_savings],
        "health_benefits": [round(x, 0) for x in health_benefits],
        "co2_avoided_tonnes": [round(x, 1) for x in co2_avoided_tonnes],
        "vehicle_premium_cost": [round(x, 0) for x in vehicle_premium_cost],
        "charging_infra_cost": [round(x, 0) for x in charging_infra_cost],
        "electricity_cost": [round(x, 0) for x in electricity_cost],
        "net_benefit": [round(x, 0) for x in net_benefit],
        # Cumulative totals
        "cumulative_petrol_saved_ml": round(sum(petrol_saved_litres) / 1e6, 1),
        "cumulative_co2_avoided_kt": round(sum(co2_avoided_tonnes) / 1e3, 1),
        "cumulative_health_benefit_m": round(sum(health_benefits) / 1e6, 1),
        "total_charging_stations": stations_needed_prev,
        "total_charging_investment_m": round(sum(charging_infra_cost) / 1e6, 1),
        # NPV
        "npv_benefits_m": round(npv_benefits / 1e6, 1),
        "npv_costs_m": round(npv_costs / 1e6, 1),
        "npv_co2_value_m": round(npv_co2_value / 1e6, 1),
        "npv_net_m": round(npv_net / 1e6, 1),
        "bcr": round((npv_benefits + npv_co2_value) / max(npv_costs, 1), 2),
        # Final year values
        "final_ev_share": ev_shares[-1],
        "final_ev_count": ev_counts[-1],
        "final_annual_health_m": round(health_benefits[-1] / 1e6, 2),
        "final_annual_co2_kt": round(co2_avoided_tonnes[-1] / 1e3, 1),
    }


# ── Main entry point ───────────────────────────────────────────────

def run_transport_analysis(
    config: Optional[Config] = None,
) -> Dict:
    """
    Run transport electrification analysis across Low / Medium / High scenarios.
    
    Returns:
        Full results dict suitable for JSON serialisation.
    """
    if config is None:
        config = get_config()
    
    years = list(range(config.base_year, config.end_year + 1))
    tr = config.transport
    
    scenarios = [
        (tr.ev_target_low, "Low (30% EV by 2056)"),
        (tr.ev_target_medium, "Medium (60% EV by 2056)"),
        (tr.ev_target_high, "High (85% EV by 2056)"),
    ]
    
    results = {
        "method": "Transport Electrification Analysis (P8)",
        "description": (
            "Supplementary analysis of motorcycle fleet electrification in the "
            "Maldives using logistic S-curve adoption across three scenarios. "
            "Quantifies fuel savings, health co-benefits, CO₂ reduction, "
            "and charging infrastructure needs. Does NOT modify core energy CBA."
        ),
        "parameters": {
            "total_vehicles_2026": tr.total_vehicles_2026,
            "motorcycle_share": tr.motorcycle_share,
            "ev_share_2026": tr.ev_share_2026,
            "fleet_growth_rate": tr.fleet_growth_rate,
            "ev_adoption_midpoint": tr.ev_adoption_midpoint,
            "ev_adoption_steepness": tr.ev_adoption_steepness,
            "motorcycle_daily_km": tr.motorcycle_daily_km,
            "ice_fuel_l_100km": tr.ice_fuel_consumption_l_100km,
            "ev_energy_kwh_per_km": tr.ev_energy_per_km,
            "petrol_price_2026_usd_l": tr.petrol_price_2026,
            "petrol_price_escalation": tr.petrol_price_escalation,
            "discount_rate": config.economics.discount_rate,
        },
        "scenarios": {},
        "summary": {},
    }
    
    scenario_summaries = []
    for target, label in scenarios:
        scenario_result = _analyse_scenario(config, years, target, label)
        key = label.split("(")[0].strip().lower()
        results["scenarios"][key] = scenario_result
        scenario_summaries.append({
            "scenario": label,
            "npv_net_m": scenario_result["npv_net_m"],
            "bcr": scenario_result["bcr"],
            "cumulative_co2_kt": scenario_result["cumulative_co2_avoided_kt"],
            "cumulative_health_m": scenario_result["cumulative_health_benefit_m"],
            "final_ev_share": scenario_result["final_ev_share"],
            "electricity_demand_gwh_final": scenario_result["electricity_demand_gwh_final"],
        })
    
    results["summary"] = {
        "comparison": scenario_summaries,
        "note": (
            "The Medium scenario is recommended for policy modelling. "
            "Health benefits are driven by Malé's extreme population density "
            "(~65,000/km²). EV electricity demand adds 1-5% to national "
            "grid load depending on scenario, manageable within existing "
            "capacity planning."
        ),
    }
    
    return results


# ── Console output ──────────────────────────────────────────────────

def print_transport_summary(results: Dict) -> None:
    """Print transport analysis summary to console."""
    print()
    print("=" * 70)
    print("  P8: TRANSPORT ELECTRIFICATION ANALYSIS")
    print("=" * 70)
    print()
    print("  Maldives motorcycle fleet EV adoption — logistic S-curve model")
    print(f"  Base fleet: {results['parameters']['total_vehicles_2026']:,} vehicles "
          f"({results['parameters']['motorcycle_share']:.0%} motorcycles)")
    print(f"  Current EV share: {results['parameters']['ev_share_2026']:.0%}")
    print(f"  S-curve midpoint: {results['parameters']['ev_adoption_midpoint']}")
    print()
    
    header = f"  {'Scenario':<28} {'NPV Net':>10} {'BCR':>6} {'CO₂ kt':>8} {'Health $M':>10} {'EV 2056':>8} {'Elec GWh':>9}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    
    for s in results["summary"]["comparison"]:
        print(f"  {s['scenario']:<28} "
              f"${s['npv_net_m']:>8.1f}M "
              f"{s['bcr']:>5.2f} "
              f"{s['cumulative_co2_kt']:>7.1f} "
              f"${s['cumulative_health_m']:>8.1f}M "
              f"{s['final_ev_share']:>7.0%} "
              f"{s['electricity_demand_gwh_final']:>8.1f}")
    
    print()
    print(f"  Note: {results['summary']['note']}")
    print()


# ── File output ─────────────────────────────────────────────────────

def save_transport_results(results: Dict, output_dir: str) -> None:
    """Save transport analysis results to JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    filepath = output_path / "transport_results.json"
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Transport analysis results saved to {filepath}")


# ── Standalone entry ────────────────────────────────────────────────

if __name__ == "__main__":
    config = get_config()
    results = run_transport_analysis(config)
    print_transport_summary(results)
    save_transport_results(results, str(Path(__file__).parent.parent / "outputs"))
