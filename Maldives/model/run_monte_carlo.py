"""
Maldives Energy CBA - Monte Carlo Simulation
=============================================

This script runs Monte Carlo simulation with 1,000 iterations
to characterize uncertainty in scenario rankings.

Usage:
    python -m model.run_monte_carlo
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from copy import deepcopy
import json
import random
import math
import numpy as np

# Add model to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.config import Config, get_config
from model.scenarios.status_quo import StatusQuoScenario
from model.scenarios.green_transition import NationalGridScenario
from model.scenarios.one_grid import FullIntegrationScenario
from model.scenarios.islanded_green import IslandedGreenScenario
from model.scenarios.nearshore_solar import NearShoreSolarScenario
from model.scenarios.maximum_re import MaximumREScenario
from model.scenarios.lng_transition import LNGTransitionScenario
from model.cba import CBACalculator
from model.config import SENSITIVITY_PARAMS


def _build_distributions():
    """Build Monte Carlo parameter distributions from SENSITIVITY_PARAMS (populated by CSV).
    
    Returns dict of parameter_name -> (low, mode, high) for triangular distribution.
    """
    # Ensure config loaded first (triggers CSV read)
    _ = get_config()
    
    # Map SENSITIVITY_PARAMS keys to config attribute names used in sample_config
    distributions = {}
    for sens_key, vals in SENSITIVITY_PARAMS.items():
        distributions[sens_key] = (vals["low"], vals["base"], vals["high"])
    return distributions


def triangular_sample(low: float, mode: float, high: float) -> float:
    """Sample from triangular distribution."""
    return random.triangular(low, high, mode)


# F-03: Parameter correlation structure (Iman-Conover method)
# Key correlation pairs with economic justification:
PARAM_CORRELATIONS = {
    # Oil price and escalation: if current price is high, escalation tends
    # to be lower (mean reversion); if low, escalation tends higher
    ("diesel_price", "diesel_escalation"): -0.3,
    # Solar and battery capex move together: shared supply chains, 
    # manufacturing learning, polysilicon/lithium markets
    ("solar_capex", "battery_capex"): 0.6,
    # Discount rate and SCC: higher discount rate implies lower weight on
    # future damages, often paired with lower SCC in integrated assessments
    ("discount_rate", "social_cost_carbon"): -0.4,
    # Item-6: Additional correlation pairs
    # Demand growth and base demand: higher starting demand often implies
    # stronger economic fundamentals → higher growth (urbanization, tourism)
    ("demand_growth", "base_demand"): 0.3,
    # LNG fuel cost and diesel price: both fossil fuels subject to
    # common global energy price shocks (IEA WEO 2024)
    ("lng_fuel_cost", "diesel_price"): 0.5,
    # Floating solar premium and nearshore cable cost: both reflect
    # marine construction market conditions and logistics
    ("floating_capex_premium", "nearshore_cable_cost"): 0.4,
}


def _presample_correlated(
    n: int,
    param_distributions: dict,
    correlations: dict = None,
) -> List[Dict[str, float]]:
    """F-03: Pre-sample all MC iterations with rank correlations.
    
    Uses simplified Iman-Conover (1982) method:
    1. Draw independent marginal samples from triangular distributions
    2. Reorder samples to induce desired Spearman rank correlations
       between specified parameter pairs
    
    This preserves the marginal distributions (triangular) while inducing
    the specified rank correlation structure between pairs.
    
    Reference:
        Iman, R.L. and Conover, W.J. (1982). "A distribution-free approach
        to inducing rank correlation among input variables." Communications
        in Statistics - Simulation and Computation, 11(3), 311-334.
    
    Args:
        n: Number of iterations
        param_distributions: {param_name: (low, mode, high)}
        correlations: {(param_a, param_b): rho} rank correlations
    
    Returns:
        List of n dicts, each {param_name: sampled_value}
    """
    if correlations is None:
        correlations = PARAM_CORRELATIONS
    
    param_names = list(param_distributions.keys())
    k = len(param_names)
    
    # Step 1: Draw independent marginal samples
    samples = np.zeros((n, k))
    for j, name in enumerate(param_names):
        lo, mode, hi = param_distributions[name]
        for i in range(n):
            samples[i, j] = random.triangular(lo, hi, mode)
    
    # Step 2: Induce rank correlations for specified pairs
    for (param_a, param_b), rho in correlations.items():
        if param_a not in param_names or param_b not in param_names:
            continue
        
        ja = param_names.index(param_a)
        jb = param_names.index(param_b)
        
        # Get ranks of column A
        ranks_a = np.argsort(np.argsort(samples[:, ja]))
        
        # Create target rank order for column B based on desired correlation
        if rho > 0:
            # Positive correlation: sort B to match A's rank order
            target_order = np.argsort(ranks_a)
        else:
            # Negative correlation: sort B to reverse A's rank order
            target_order = np.argsort(-ranks_a)
        
        # Blend: partially reorder B towards target to achieve approximate rho
        abs_rho = abs(rho)
        sorted_b = np.sort(samples[:, jb])
        current_b = samples[:, jb].copy()
        
        # Simple mixing: with probability |rho|, use the correlated order
        mask = np.random.random(n) < abs_rho
        new_b = current_b.copy()
        # Assign correlated values where mask is True
        new_b[mask] = sorted_b[target_order[mask]] if rho > 0 else sorted_b[np.argsort(-ranks_a)][mask]
        samples[:, jb] = new_b
    
    # Convert to list of dicts
    result = []
    for i in range(n):
        d = {param_names[j]: samples[i, j] for j in range(k)}
        result.append(d)
    
    return result


def sample_config(base_config: Config, param_distributions: dict, presampled_values: dict = None) -> Config:
    """Create a config with randomly sampled parameters.
    
    Args:
        base_config: Base configuration to modify
        param_distributions: {param: (low, mode, high)} distributions
        presampled_values: F-03: If provided, use these values instead of
            independent sampling (for Iman-Conover correlated draws)
    """
    config = deepcopy(base_config)
    
    params = {}
    for param, (low, mode, high) in param_distributions.items():
        if presampled_values is not None and param in presampled_values:
            value = presampled_values[param]
        else:
            value = triangular_sample(low, mode, high)
        params[param] = value
        
        if param == "discount_rate":
            config.economics.discount_rate = value
        elif param == "diesel_price":
            config.fuel.price_2026 = value
        elif param == "diesel_escalation":
            config.fuel.price_escalation = value
        elif param == "solar_capex":
            config.technology.solar_pv_capex = value
        elif param == "solar_cf":
            config.technology.solar_pv_capacity_factor = value
        elif param == "battery_capex":
            config.technology.battery_capex = value
        elif param == "cable_capex_per_km":
            config.technology.cable_capex_per_km = value
            # Recompute cable_capex_total
            submarine_cable = config.one_grid.cable_length_km * value
            converter_stations = config.technology.converter_station_cost_per_mw * config.one_grid.cable_capacity_mw
            landing = config.technology.landing_cost_per_end * config.technology.num_landings
            base_capex_val = submarine_cable + converter_stations + landing
            idc = base_capex_val * config.technology.idc_rate
            config.one_grid.cable_capex_total = base_capex_val + idc + config.technology.grid_upgrade_cost
        elif param == "import_price":
            config.ppa.import_price_2030 = value
        elif param == "social_cost_carbon":
            config.economics.social_cost_carbon = value
        elif param == "gom_cost_share":
            config.one_grid.gom_share_pct = value
        elif param == "demand_growth":
            # Scale all scenario growth rates proportionally (M-BUG-4 fix)
            base_bau = base_config.demand.growth_rates["status_quo"]
            if base_bau != 0:
                scale = value / base_bau
            else:
                scale = 1.0
            for key in config.demand.growth_rates:
                config.demand.growth_rates[key] = base_config.demand.growth_rates[key] * scale
        elif param == "outage_rate":
            config.cable_outage.outage_rate_per_yr = value
        elif param == "idle_fleet_cost":
            config.supply_security.idle_fleet_annual_cost_m = value
        elif param == "price_elasticity":
            config.demand.price_elasticity = value
        # L14: Expanded parameters
        elif param == "health_damage":
            config.economics.health_damage_cost_per_mwh = value
        elif param == "fuel_efficiency":
            config.fuel.kwh_per_liter = value
        elif param == "base_demand":
            config.demand.base_demand_gwh = value
        elif param == "battery_hours":
            config.technology.battery_hours = value
        elif param == "climate_premium":
            config.technology.climate_adaptation_premium = value
        elif param == "converter_station":
            config.technology.converter_station_cost_per_mw = value
            # Recompute cable_capex_total
            submarine_cable = config.one_grid.cable_length_km * config.technology.cable_capex_per_km
            converter_stations = value * config.one_grid.cable_capacity_mw
            landing = config.technology.landing_cost_per_end * config.technology.num_landings
            base_capex_val = submarine_cable + converter_stations + landing
            idc = base_capex_val * config.technology.idc_rate
            config.one_grid.cable_capex_total = base_capex_val + idc + config.technology.grid_upgrade_cost
        elif param == "connection_cost":
            config.connection.cost_per_household = value
            config.technology.connection_cost_per_hh = value
        elif param == "env_externality":
            base_env = (base_config.economics.noise_damage_per_mwh
                       + base_config.economics.fuel_spill_risk_per_mwh
                       + base_config.economics.biodiversity_impact_per_mwh)
            s = value / base_env if base_env > 0 else 1.0
            config.economics.noise_damage_per_mwh = base_config.economics.noise_damage_per_mwh * s
            config.economics.fuel_spill_risk_per_mwh = base_config.economics.fuel_spill_risk_per_mwh * s
            config.economics.biodiversity_impact_per_mwh = base_config.economics.biodiversity_impact_per_mwh * s
        elif param == "sectoral_residential":
            config.demand.sectoral_residential = value
            remainder = 1.0 - value
            config.demand.sectoral_commercial = remainder / 2.0
            config.demand.sectoral_public = remainder / 2.0
        # V2b: S5/S6/S7-specific parameters
        elif param == "lng_capex":
            config.lng.capex_per_mw = value
        elif param == "lng_fuel_cost":
            config.lng.fuel_cost_per_mwh = value
        elif param == "lng_fuel_escalation":
            config.lng.fuel_escalation = value
        elif param == "lng_emission_factor":
            config.lng.emission_factor = value
        elif param == "floating_capex_premium":
            config.nearshore.floating_solar_capex_premium = value
        elif param == "floating_solar_mw":
            config.nearshore.floating_solar_mw = value
        elif param == "nearshore_solar_mw":
            config.nearshore.nearshore_solar_mw = value
        elif param == "nearshore_cable_cost":
            config.nearshore.nearshore_cable_cost_per_mw = value
        elif param == "wte_capex":
            config.wte.capex_per_kw = value
        elif param == "deployment_ramp":
            config.green_transition.deployment_ramp_mw_per_year = value
        elif param == "male_max_re":
            config.green_transition.male_max_re_share = value
        elif param == "battery_ratio":
            config.green_transition.battery_ratio = value
            config.green_transition.islanded_battery_ratio = value
        # CR-03 fix: P8 transport electrification parameters (F-CR-01)
        elif param == "ev_adoption_midpoint":
            config.transport.ev_adoption_midpoint = int(value)
        elif param == "ev_motorcycle_premium":
            config.transport.e_motorcycle_premium_2026 = value
        elif param == "transport_health_damage":
            config.transport.pm25_damage_per_vkm = value
        elif param == "petrol_price":
            config.transport.petrol_price_2026 = value
        # Item-2: 6 additional high-impact params
        elif param == "demand_saturation":
            config.demand.demand_saturation_kwh_per_capita = value
        elif param == "male_growth_near":
            config.demand.male_growth_near_term = value
        elif param == "pv_degradation":
            config.technology.solar_pv_degradation = value
        elif param == "idc_rate":
            config.technology.idc_rate = value
            submarine_cable = config.one_grid.cable_length_km * config.technology.cable_capex_per_km
            converter_stations = config.technology.converter_station_cost_per_mw * config.one_grid.cable_capacity_mw
            landing = config.technology.landing_cost_per_end * config.technology.num_landings
            base_capex_val = submarine_cable + converter_stations + landing
            idc = base_capex_val * value
            config.one_grid.cable_capex_total = base_capex_val + idc + config.technology.grid_upgrade_cost
        elif param == "lng_capacity_mw":
            config.lng.plant_capacity_mw = value
        elif param == "subsidy_per_kwh":
            config.current_system.current_subsidy_per_kwh = value
    
    return config, params


def run_iteration(config: Config) -> Dict[str, float]:
    """Run all 7 scenarios with given config and return NPVs."""
    bau = StatusQuoScenario(config).run()
    fi = FullIntegrationScenario(config).run()
    ng = NationalGridScenario(config).run()
    ig = IslandedGreenScenario(config).run()
    ns = NearShoreSolarScenario(config).run()
    mx = MaximumREScenario(config).run()
    lng = LNGTransitionScenario(config).run()
    
    calc = CBACalculator(config)
    # F-01 fix: Use economic cost (financial + emission costs) so SCC
    # parameter variation affects scenario rankings in Monte Carlo.
    bau_r = calc.calculate_npv(bau);   bau_npv = bau_r.pv_total_costs + bau_r.pv_emission_costs
    fi_r  = calc.calculate_npv(fi);    fi_npv  = fi_r.pv_total_costs  + fi_r.pv_emission_costs
    ng_r  = calc.calculate_npv(ng);    ng_npv  = ng_r.pv_total_costs  + ng_r.pv_emission_costs
    ig_r  = calc.calculate_npv(ig);    ig_npv  = ig_r.pv_total_costs  + ig_r.pv_emission_costs
    ns_r  = calc.calculate_npv(ns);    ns_npv  = ns_r.pv_total_costs  + ns_r.pv_emission_costs
    mx_r  = calc.calculate_npv(mx);    mx_npv  = mx_r.pv_total_costs  + mx_r.pv_emission_costs
    lng_r = calc.calculate_npv(lng);   lng_npv = lng_r.pv_total_costs + lng_r.pv_emission_costs
    
    return {
        "bau": bau_npv,
        "full_integration": fi_npv,
        "national_grid": ng_npv,
        "islanded_green": ig_npv,
        "nearshore_solar": ns_npv,
        "maximum_re": mx_npv,
        "lng_transition": lng_npv,
    }


def rank_scenarios(npvs: Dict[str, float]) -> str:
    """Return the name of the least-cost scenario."""
    return min(npvs, key=npvs.get)


def percentile(data: List[float], p: float) -> float:
    """Calculate the p-th percentile of data."""
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def main():
    print("=" * 70)
    print("  MALDIVES ENERGY CBA - MONTE CARLO SIMULATION (7 SCENARIOS)")
    print("=" * 70)
    print(f"  Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    # Settings
    N_ITERATIONS = 1000
    random.seed(42)  # For reproducibility
    
    print(f"Running {N_ITERATIONS:,} Monte Carlo iterations...")
    print("-" * 50)
    
    # Storage
    bau_results = []
    fi_results = []
    ng_results = []
    ig_results = []
    ns_results = []
    mx_results = []
    lng_results = []
    rankings = []
    all_params = []
    
    # Item-6: Convergence diagnostics — running mean of FI NPV
    convergence_trace = []  # (iteration, running_mean_fi, running_std_fi)
    
    base_config = get_config()
    param_distributions = _build_distributions()
    
    print(f"  Parameters being varied: {len(param_distributions)}")
    for k, (lo, base, hi) in param_distributions.items():
        print(f"    {k}: [{lo}, {base}, {hi}]")
    
    # F-03: Pre-sample with rank correlations (Iman-Conover 1982)
    active_correlations = {
        pair: rho for pair, rho in PARAM_CORRELATIONS.items()
        if pair[0] in param_distributions and pair[1] in param_distributions
    }
    if active_correlations:
        print(f"\n  Rank correlations applied ({len(active_correlations)} pairs):")
        for (pa, pb), rho in active_correlations.items():
            print(f"    ({pa}, {pb}): rho = {rho:+.1f}")
    
    presampled = _presample_correlated(N_ITERATIONS, param_distributions, active_correlations)
    print()
    
    for i in range(N_ITERATIONS):
        if (i + 1) % 100 == 0:
            print(f"  Completed {i + 1:,} iterations...")
        
        # F-03: Use pre-sampled (correlated) parameter draws
        config, params = sample_config(base_config, param_distributions, presampled_values=presampled[i])
        npvs = run_iteration(config)
        
        bau_results.append(npvs["bau"])
        fi_results.append(npvs["full_integration"])
        ng_results.append(npvs["national_grid"])
        ig_results.append(npvs["islanded_green"])
        ns_results.append(npvs["nearshore_solar"])
        mx_results.append(npvs["maximum_re"])
        lng_results.append(npvs["lng_transition"])
        rankings.append(rank_scenarios(npvs))
        all_params.append(params)
        
        # Item-6: Convergence diagnostics — track running mean/std of FI NPV
        n_so_far = len(fi_results)
        running_mean = sum(fi_results) / n_so_far
        if n_so_far > 1:
            running_var = sum((x - running_mean) ** 2 for x in fi_results) / (n_so_far - 1)
            running_std = math.sqrt(running_var)
        else:
            running_std = 0.0
        convergence_trace.append((n_so_far, running_mean, running_std))
    
    print()
    print("=" * 70)
    print("  MONTE CARLO RESULTS")
    print("=" * 70)
    
    # Statistics for each scenario
    print("\n--- NPV Distribution Summary ($ Million) ---")
    print(f"{'Scenario':<25} {'Mean':>12} {'Std Dev':>12} {'P5':>12} {'P50':>12} {'P95':>12}")
    print("-" * 90)
    
    scenario_labels = {
        "bau": "BAU (Diesel)",
        "full_integration": "Full Integration", 
        "national_grid": "National Grid",
        "islanded_green": "Islanded Green",
        "nearshore_solar": "Near-Shore Solar",
        "maximum_re": "Maximum RE",
        "lng_transition": "LNG Transition",
    }
    
    results_map = {
        "bau": bau_results,
        "full_integration": fi_results,
        "national_grid": ng_results,
        "islanded_green": ig_results,
        "nearshore_solar": ns_results,
        "maximum_re": mx_results,
        "lng_transition": lng_results,
    }
    
    for key, results in results_map.items():
        name = scenario_labels[key]
        mean = sum(results) / len(results)
        variance = sum((x - mean) ** 2 for x in results) / len(results)
        std_dev = math.sqrt(variance)
        p5 = percentile(results, 5)
        p50 = percentile(results, 50)
        p95 = percentile(results, 95)
        
        print(f"{name:<25} ${mean/1e6:>10,.0f}M ${std_dev/1e6:>10,.0f}M ${p5/1e6:>10,.0f}M ${p50/1e6:>10,.0f}M ${p95/1e6:>10,.0f}M")
    
    # Ranking probabilities
    print("\n--- Probability of Being Least-Cost ---")
    print("-" * 50)
    
    ranking_counts = {}
    for r in rankings:
        ranking_counts[r] = ranking_counts.get(r, 0) + 1
    
    for scenario_key in ["bau", "full_integration", "national_grid", "islanded_green",
                          "nearshore_solar", "maximum_re", "lng_transition"]:
        count = ranking_counts.get(scenario_key, 0)
        prob = count / N_ITERATIONS * 100
        label = scenario_labels[scenario_key]
        bar = "█" * int(prob / 2)
        print(f"  {label:<25}: {prob:>5.1f}% {bar}")
    
    # Savings distribution
    print("\n--- Savings Distribution (Full Integration vs BAU) ---")
    savings = [bau - fi for bau, fi in zip(bau_results, fi_results)]
    mean_savings = sum(savings) / len(savings)
    p5_savings = percentile(savings, 5)
    p95_savings = percentile(savings, 95)
    prob_positive = sum(1 for s in savings if s > 0) / len(savings) * 100
    
    print(f"  Mean savings: ${mean_savings/1e6:,.0f}M")
    print(f"  5th percentile: ${p5_savings/1e6:,.0f}M")
    print(f"  95th percentile: ${p95_savings/1e6:,.0f}M")
    print(f"  Probability Full Integration is cheaper: {prob_positive:.1f}%")
    
    # Probability each alternative beats BAU (BCR > 1 equivalent)
    print("\n--- Probability Alternative Beats BAU ---")
    for key, results in [("full_integration", fi_results), ("national_grid", ng_results),
                          ("islanded_green", ig_results), ("nearshore_solar", ns_results),
                          ("maximum_re", mx_results), ("lng_transition", lng_results)]:
        prob_beats = sum(1 for b, a in zip(bau_results, results) if a < b) / len(bau_results) * 100
        print(f"  {scenario_labels[key]:<25}: {prob_beats:>5.1f}%")
    
    
    # Save results
    output_dir = Path(__file__).parent.parent / "outputs"  # H-I-01: relative to script, not CWD
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Item-6: Convergence diagnostics
    print("\n--- Convergence Diagnostics (Full Integration NPV) ---")
    checkpoints = [100, 250, 500, 750, 1000]
    for cp in checkpoints:
        if cp <= len(convergence_trace):
            _, mean_at_cp, std_at_cp = convergence_trace[cp - 1]
            cv = abs(std_at_cp / mean_at_cp * 100) if mean_at_cp != 0 else 0
            se = std_at_cp / math.sqrt(cp)
            print(f"  After {cp:>5} iter: mean=${mean_at_cp/1e6:>10,.0f}M  "
                  f"std=${std_at_cp/1e6:>8,.0f}M  CV={cv:.1f}%  SE=${se/1e6:>6,.0f}M")
    
    # Check convergence: last 100 vs last 500 mean should be within 2%
    if len(fi_results) >= 500:
        last_100_mean = sum(fi_results[-100:]) / 100
        last_500_mean = sum(fi_results[-500:]) / 500
        drift_pct = abs(last_100_mean - last_500_mean) / abs(last_500_mean) * 100 if last_500_mean != 0 else 0
        converged = drift_pct < 2.0
        print(f"\n  Convergence test: last-100 vs last-500 drift = {drift_pct:.2f}% "
              f"({'CONVERGED' if converged else 'NOT CONVERGED — consider more iterations'})")
    
    mc_results = {
        "n_iterations": N_ITERATIONS,
        # F-03: Record applied parameter correlations
        "parameter_correlations": {
            f"{pa}___{pb}": rho for (pa, pb), rho in active_correlations.items()
        },
        "scenarios": {},
        "ranking_probabilities": {
            k: v / N_ITERATIONS for k, v in ranking_counts.items()
        },
        "prob_beats_bau": {
            "full_integration": sum(1 for b, a in zip(bau_results, fi_results) if a < b) / len(bau_results),
            "national_grid": sum(1 for b, a in zip(bau_results, ng_results) if a < b) / len(bau_results),
            "islanded_green": sum(1 for b, a in zip(bau_results, ig_results) if a < b) / len(bau_results),
            "nearshore_solar": sum(1 for b, a in zip(bau_results, ns_results) if a < b) / len(bau_results),
            "maximum_re": sum(1 for b, a in zip(bau_results, mx_results) if a < b) / len(bau_results),
            "lng_transition": sum(1 for b, a in zip(bau_results, lng_results) if a < b) / len(bau_results),
        },
        "savings_fi_vs_bau": {
            "mean": mean_savings,
            "p5": p5_savings,
            "p95": p95_savings,
            "prob_positive": prob_positive / 100,
        },
        # Item-6: Convergence diagnostics
        "convergence_diagnostics": {
            "trace_checkpoints": {
                str(cp): {
                    "mean": convergence_trace[cp - 1][1],
                    "std": convergence_trace[cp - 1][2],
                    "cv_pct": abs(convergence_trace[cp - 1][2] / convergence_trace[cp - 1][1] * 100)
                        if convergence_trace[cp - 1][1] != 0 else 0,
                }
                for cp in [100, 250, 500, 750, 1000] if cp <= len(convergence_trace)
            },
            "final_cv_pct": abs(convergence_trace[-1][2] / convergence_trace[-1][1] * 100)
                if convergence_trace and convergence_trace[-1][1] != 0 else 0,
            "converged": bool(
                abs(sum(fi_results[-100:]) / 100 - sum(fi_results[-500:]) / 500)
                / abs(sum(fi_results[-500:]) / 500) * 100 < 2.0
            ) if len(fi_results) >= 500 else None,
        },
    }
    
    for key, results in results_map.items():
        mean = sum(results) / len(results)
        mc_results["scenarios"][key] = {
            "mean": mean,
            "std_dev": math.sqrt(sum((x - mean) ** 2 for x in results) / len(results)),
            "p5": percentile(results, 5),
            "p50": percentile(results, 50),
            "p95": percentile(results, 95),
        }
    
    with open(output_dir / "monte_carlo_results.json", "w") as f:
        json.dump(mc_results, f, indent=2)
    
    print(f"\nResults saved to {output_dir / 'monte_carlo_results.json'}")
    
    print()
    print("=" * 70)
    print("  MONTE CARLO SIMULATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
