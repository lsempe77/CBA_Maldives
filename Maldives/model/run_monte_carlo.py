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

# Add model to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.config import Config, get_config
from model.scenarios.status_quo import StatusQuoScenario
from model.scenarios.green_transition import NationalGridScenario
from model.scenarios.one_grid import FullIntegrationScenario
from model.scenarios.islanded_green import IslandedGreenScenario
from model.cba import CBACalculator


# Monte Carlo parameter distributions (triangular)
# Format: (min, mode/base, max)
PARAMETER_DISTRIBUTIONS = {
    "discount_rate": (0.03, 0.06, 0.10),
    "diesel_price": (0.60, 0.85, 1.10),
    "diesel_escalation": (0.00, 0.02, 0.05),
    "solar_capex": (700, 1000, 1300),
    "battery_capex": (200, 400, 600),
    "cable_capex_per_km": (1_400_000, 2_000_000, 3_000_000),
    "ppa_price": (0.05, 0.08, 0.12),
    "scc": (0, 80, 200),
    "gom_share": (0.25, 0.30, 1.00),
}


def triangular_sample(low: float, mode: float, high: float) -> float:
    """Sample from triangular distribution."""
    return random.triangular(low, high, mode)


def sample_config(base_config: Config) -> Config:
    """Create a config with randomly sampled parameters."""
    config = deepcopy(base_config)
    
    params = {}
    for param, (low, mode, high) in PARAMETER_DISTRIBUTIONS.items():
        value = triangular_sample(low, mode, high)
        params[param] = value
        
        if param == "discount_rate":
            config.economics.discount_rate = value
        elif param == "diesel_price":
            config.fuel.price_2024 = value
        elif param == "diesel_escalation":
            config.fuel.price_escalation = value
        elif param == "solar_capex":
            config.technology.solar_pv_capex = value
        elif param == "battery_capex":
            config.technology.battery_capex = value
        elif param == "cable_capex_per_km":
            config.technology.cable_capex_per_km = value
        elif param == "ppa_price":
            config.ppa.import_price_2030 = value
        elif param == "scc":
            config.economics.social_cost_carbon = value
        elif param == "gom_share":
            config.one_grid.gom_share_pct = value
    
    return config, params


def run_iteration(config: Config) -> Dict[str, float]:
    """Run all 4 scenarios with given config and return NPVs."""
    bau = StatusQuoScenario(config).run()
    fi = FullIntegrationScenario(config).run()
    ng = NationalGridScenario(config).run()
    ig = IslandedGreenScenario(config).run()
    
    calc = CBACalculator(config)
    bau_npv = calc.calculate_npv(bau).pv_total_costs
    fi_npv = calc.calculate_npv(fi).pv_total_costs
    ng_npv = calc.calculate_npv(ng).pv_total_costs
    ig_npv = calc.calculate_npv(ig).pv_total_costs
    
    return {
        "bau": bau_npv,
        "full_integration": fi_npv,
        "national_grid": ng_npv,
        "islanded_green": ig_npv,
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
    print("  MALDIVES ENERGY CBA - MONTE CARLO SIMULATION (4 SCENARIOS)")
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
    rankings = []
    all_params = []
    
    base_config = get_config()
    
    for i in range(N_ITERATIONS):
        if (i + 1) % 100 == 0:
            print(f"  Completed {i + 1:,} iterations...")
        
        config, params = sample_config(base_config)
        npvs = run_iteration(config)
        
        bau_results.append(npvs["bau"])
        fi_results.append(npvs["full_integration"])
        ng_results.append(npvs["national_grid"])
        ig_results.append(npvs["islanded_green"])
        rankings.append(rank_scenarios(npvs))
        all_params.append(params)
    
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
    }
    
    results_map = {
        "bau": bau_results,
        "full_integration": fi_results,
        "national_grid": ng_results,
        "islanded_green": ig_results,
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
    
    for scenario_key in ["bau", "full_integration", "national_grid", "islanded_green"]:
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
    
    # Save results
    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    mc_results = {
        "n_iterations": N_ITERATIONS,
        "scenarios": {},
        "ranking_probabilities": {
            k: v / N_ITERATIONS for k, v in ranking_counts.items()
        },
        "savings_fi_vs_bau": {
            "mean": mean_savings,
            "p5": p5_savings,
            "p95": p95_savings,
            "prob_positive": prob_positive / 100,
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
