"""
Maldives Energy CBA - Equation Sanity Checks (V6)
===================================================

Programmatic verification of all model outputs against published benchmarks
and acceptable ranges. Every equation result is checked against external
data from IRENA, ADB, IEA, IPCC, and published SIDS energy studies.

Includes structural invariant checks (cost summation identity, generation
balance, demand monotonicity, cross-scenario demand consistency,
generation share sum, NPV identity, IRR range validation).

Usage:
    python -m model.sanity_checks

Returns exit code 0 if all checks pass, 1 if any FAIL.
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Tuple

# Add model to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.config import get_config


# =============================================================================
# CHECK FRAMEWORK
# =============================================================================

@dataclass
class SanityCheck:
    """Single sanity check result."""
    category: str
    name: str
    actual: float
    expected_low: float
    expected_high: float
    unit: str
    source: str
    status: str = ""  # PASS, WARN, FAIL
    note: str = ""
    
    def evaluate(self) -> str:
        if self.expected_low <= self.actual <= self.expected_high:
            self.status = "PASS"
        elif (self.actual < self.expected_low * 0.8 or
              self.actual > self.expected_high * 1.2):
            self.status = "FAIL"
        else:
            self.status = "WARN"
        return self.status


def run_all_checks() -> List[SanityCheck]:
    """Run all sanity checks and return results."""
    
    # Load outputs
    output_dir = Path(__file__).parent.parent / "outputs"
    
    with open(output_dir / "cba_results.json") as f:
        cba = json.load(f)
    
    with open(output_dir / "scenario_summaries.json") as f:
        summaries = json.load(f)
    
    cfg = get_config()
    
    checks: List[SanityCheck] = []
    
    # =========================================================================
    # 1. LCOE BENCHMARKS
    # =========================================================================
    
    # BAU diesel LCOE
    checks.append(SanityCheck(
        category="LCOE",
        name="BAU diesel LCOE",
        actual=cba["npv_results"]["bau"]["lcoe"],
        expected_low=0.25,
        expected_high=0.55,
        unit="USD/kWh",
        source="IRENA Off-Grid RE Statistics 2024: SIDS diesel $0.28-0.55/kWh",
    ))
    
    # Full Integration LCOE
    checks.append(SanityCheck(
        category="LCOE",
        name="Full Integration LCOE",
        actual=cba["npv_results"]["full_integration"]["lcoe"],
        expected_low=0.10,
        expected_high=0.30,
        unit="USD/kWh",
        source="IEX 2024 import price $0.06 + domestic RE + cable amortisation",
    ))
    
    # National Grid (solar+battery) LCOE
    checks.append(SanityCheck(
        category="LCOE",
        name="National Grid LCOE",
        actual=cba["npv_results"]["national_grid"]["lcoe"],
        expected_low=0.15,
        expected_high=0.40,
        unit="USD/kWh",
        source="IRENA RPGC 2024 SIDS solar+BESS $0.15-0.35/kWh; gradual transition",
    ))
    
    # LNG Transition LCOE
    checks.append(SanityCheck(
        category="LCOE",
        name="LNG Transition LCOE",
        actual=cba["npv_results"]["lng_transition"]["lcoe"],
        expected_low=0.10,
        expected_high=0.30,
        unit="USD/kWh",
        source="IEA Gas Market Report 2024: small-scale LNG LCOE $0.08-0.15 + diesel residual",
    ))
    
    # Maximum RE LCOE (should be lower than NG due to more RE displacement)
    checks.append(SanityCheck(
        category="LCOE",
        name="Maximum RE LCOE",
        actual=cba["npv_results"]["maximum_re"]["lcoe"],
        expected_low=0.12,
        expected_high=0.35,
        unit="USD/kWh",
        source="IRENA 2024; higher RE penetration reduces fuel cost dominance",
    ))
    
    # LCOE ordering: BAU > IG > NG > NS > MR > FI or LNG
    bau_lcoe = cba["npv_results"]["bau"]["lcoe"]
    fi_lcoe = cba["npv_results"]["full_integration"]["lcoe"]
    ng_lcoe = cba["npv_results"]["national_grid"]["lcoe"]
    lng_lcoe = cba["npv_results"]["lng_transition"]["lcoe"]
    
    checks.append(SanityCheck(
        category="LCOE",
        name="BAU LCOE > all alternatives",
        actual=bau_lcoe,
        expected_low=max(fi_lcoe, ng_lcoe, lng_lcoe) + 0.001,
        expected_high=9.99,
        unit="USD/kWh",
        source="By construction: diesel baseline should be most expensive",
        note=f"BAU={bau_lcoe:.3f}, best alt={min(fi_lcoe, ng_lcoe, lng_lcoe):.3f}",
    ))
    
    # =========================================================================
    # 2. TOTAL SYSTEM COSTS (PV)
    # =========================================================================
    
    # Population from config (NBS Census 2022 projection)
    pop_2026 = cfg.current_system.population_2026
    
    bau_pv = cba["npv_results"]["bau"]["pv_total_costs"]
    bau_per_capita = bau_pv / pop_2026
    
    checks.append(SanityCheck(
        category="System Costs",
        name="BAU PV total costs per capita",
        actual=bau_per_capita,
        expected_low=15_000,
        expected_high=45_000,
        unit="USD/capita",
        source="ADB Pacific Energy Update 2023: $15k-40k/capita over 30yr for SIDS diesel",
    ))
    
    # Total investment (CAPEX) ranges for alternatives
    fi_capex = cba["npv_results"]["full_integration"]["pv_capex"]
    checks.append(SanityCheck(
        category="System Costs",
        name="Full Integration PV CAPEX",
        actual=fi_capex / 1e9,
        expected_low=1.5,
        expected_high=5.0,
        unit="$B",
        source="India cable $2.1B + domestic solar + battery; OSOWOG estimates $2-4B",
    ))
    
    # LNG CAPEX (should be modest — $168M plant + solar on outer islands)
    lng_capex = cba["npv_results"]["lng_transition"]["pv_capex"]
    checks.append(SanityCheck(
        category="System Costs",
        name="LNG Transition PV CAPEX",
        actual=lng_capex / 1e9,
        expected_low=0.8,
        expected_high=3.0,
        unit="$B",
        source="$168M LNG plant + ~$1B outer-island solar+battery; ADB Mahurkar 2023",
    ))
    
    # =========================================================================
    # 3. EMISSIONS CHECKS
    # =========================================================================
    
    # Get emissions from scenario summaries
    bau_summary = summaries.get("bau", {})
    fi_summary = summaries.get("full_integration", {})
    lng_summary = summaries.get("lng_transition", {})
    
    # BAU cumulative emissions over 30 years
    bau_emissions = bau_summary.get("total_emissions_mtco2", 0)
    checks.append(SanityCheck(
        category="Emissions",
        name="BAU cumulative emissions (30yr)",
        actual=bau_emissions,
        expected_low=15,
        expected_high=80,
        unit="MtCO₂",
        source="Sum(1200×1.05^t × 0.72/1000, t=0..30) ≈ 60-70 Mt at 5% growth",
        note=f"At EF={cfg.fuel.emission_factor_kg_co2_per_kwh} kgCO₂/kWh",
    ))
    
    # Emission factor check: diesel
    checks.append(SanityCheck(
        category="Emissions",
        name="Diesel emission factor",
        actual=cfg.fuel.emission_factor_kg_co2_per_kwh,
        expected_low=0.60,
        expected_high=0.85,
        unit="kgCO₂/kWh",
        source="IPCC 2006 Vol.2 Ch.2: diesel genset 0.65-0.85 kgCO₂/kWh at 30-40% efficiency",
    ))
    
    # LNG emission factor
    checks.append(SanityCheck(
        category="Emissions",
        name="LNG emission factor",
        actual=cfg.lng.emission_factor,
        expected_low=0.35,
        expected_high=0.50,
        unit="kgCO₂/kWh",
        source="IPCC 2006: natural gas 56.1 kgCO₂/GJ; at 40-50% efficiency → 0.37-0.50",
    ))
    
    # LNG should reduce emissions vs BAU
    lng_emissions = lng_summary.get("total_emissions_mtco2", 0)
    if bau_emissions > 0 and lng_emissions > 0:
        lng_reduction_pct = (bau_emissions - lng_emissions) / bau_emissions * 100
        checks.append(SanityCheck(
            category="Emissions",
            name="LNG emission reduction vs BAU",
            actual=lng_reduction_pct,
            expected_low=15,
            expected_high=70,
            unit="%",
            source="LNG EF ~0.40 vs diesel 0.72 = ~44% lower per kWh; with outer-island RE adds more → 50-65%",
        ))
    
    # =========================================================================
    # 4. FUEL CONSUMPTION
    # =========================================================================
    
    # Base year fuel consumption: 1200 GWh ÷ 3.3 kWh/L = ~364 ML
    base_fuel_ml = cfg.demand.base_demand_gwh * 1e6 / cfg.fuel.kwh_per_liter / 1e6
    checks.append(SanityCheck(
        category="Fuel",
        name="Base year diesel consumption (2026)",
        actual=base_fuel_ml,
        expected_low=250,
        expected_high=500,
        unit="ML/yr",
        source="Maldives customs: ~300-400 ML diesel imported; 2018 IEDB: 250 ML at 800 GWh",
    ))
    
    # Fuel efficiency
    checks.append(SanityCheck(
        category="Fuel",
        name="Diesel fuel efficiency",
        actual=cfg.fuel.kwh_per_liter,
        expected_low=2.5,
        expected_high=4.0,
        unit="kWh/L",
        source="2018 IEDB (115 islands): mean=3.31, median=3.15; typical range 2.5-4.0",
    ))
    
    # =========================================================================
    # 5. DEMAND TRAJECTORY
    # =========================================================================
    
    # Base demand 2026
    checks.append(SanityCheck(
        category="Demand",
        name="Base demand 2026",
        actual=cfg.demand.base_demand_gwh,
        expected_low=900,
        expected_high=1500,
        unit="GWh",
        source="IRENA 2022: ~1,000 GWh; ×1.05^4 = ~1,200 GWh by 2026; STELCO reports ~800 GWh grid",
    ))
    
    # Growth rate
    bau_growth = cfg.demand.growth_rates["status_quo"]  # BD-02: fail-fast on missing key
    checks.append(SanityCheck(
        category="Demand",
        name="BAU demand growth rate",
        actual=bau_growth,
        expected_low=0.03,
        expected_high=0.08,
        unit="%/yr",
        source="IRENA CAGR=5.1%; STELCO MD ~5%; typical SIDS range 3-7%",
    ))
    
    # 2050 demand check (at 5% growth): 1200 × 1.05^24 = ~3,872 GWh
    demand_2050_est = cfg.demand.base_demand_gwh * (1 + bau_growth) ** 24
    checks.append(SanityCheck(
        category="Demand",
        name="Projected demand 2050 (BAU growth)",
        actual=demand_2050_est,
        expected_low=2500,
        expected_high=6000,
        unit="GWh",
        source="At 5% CAGR: ~3,900 GWh. SIDS benchmarks: 2-5× in 25 years",
    ))
    
    # =========================================================================
    # 6. SOLAR PARAMETERS
    # =========================================================================
    
    # Solar PV CAPEX
    checks.append(SanityCheck(
        category="Solar",
        name="Solar PV CAPEX",
        actual=cfg.technology.solar_pv_capex,
        expected_low=800,
        expected_high=2500,
        unit="USD/kW",
        source="IRENA RPGC 2024: $800-1,200 global; SIDS premium 20-50% → $1,000-2,200",
    ))
    
    # Solar capacity factor
    checks.append(SanityCheck(
        category="Solar",
        name="Solar capacity factor",
        actual=cfg.technology.solar_pv_capacity_factor,
        expected_low=0.14,
        expected_high=0.22,
        unit="ratio",
        source="Global Solar Atlas Maldives: GHI 5.55 kWh/m²/day → CF 17-18%; range 14-22%",
    ))
    
    # Battery CAPEX
    checks.append(SanityCheck(
        category="Solar",
        name="Battery CAPEX",
        actual=cfg.technology.battery_capex,
        expected_low=150,
        expected_high=600,
        unit="USD/kWh",
        source="BNEF 2025: $200-400/kWh for utility-scale BESS; SIDS logistics +25%",
    ))
    
    # =========================================================================
    # 7. NPV & BCR CHECKS
    # =========================================================================
    
    # All alternatives should have NPV savings > 0 vs BAU
    for scenario in ["full_integration", "national_grid", "islanded_green",
                     "nearshore_solar", "maximum_re", "lng_transition"]:
        savings = cba["incremental_vs_bau"].get(scenario, {}).get("npv_savings", 0)
        checks.append(SanityCheck(
            category="NPV",
            name=f"{scenario} NPV savings > 0",
            actual=savings / 1e9,
            expected_low=0.1,
            expected_high=15.0,
            unit="$B",
            source="All RE/hybrid alternatives should save vs diesel BAU over 30yr",
        ))
    
    # BCR should be > 1 for all alternatives
    for scenario in ["full_integration", "national_grid", "islanded_green",
                     "nearshore_solar", "maximum_re", "lng_transition"]:
        bcr = cba["incremental_vs_bau"].get(scenario, {}).get("bcr", 0)
        checks.append(SanityCheck(
            category="NPV",
            name=f"{scenario} BCR",
            actual=bcr,
            expected_low=1.0,
            expected_high=15.0,
            unit="ratio",
            source="BCR > 1 means benefits exceed costs; typical SIDS energy CBA: 1.5-8.0",
        ))
    
    # Discount rate check
    checks.append(SanityCheck(
        category="NPV",
        name="Social discount rate",
        actual=cfg.economics.discount_rate,
        expected_low=0.03,
        expected_high=0.12,
        unit="%",
        source="ADB standard for SIDS: 6%; Boardman (2018): 3.5-8%; SIDS range 3-10%",
    ))
    
    # SCC range
    checks.append(SanityCheck(
        category="NPV",
        name="Social cost of carbon",
        actual=cfg.economics.social_cost_carbon,
        expected_low=50,
        expected_high=300,
        unit="USD/tCO₂",
        source="US EPA 2023: $190; Rennert et al. 2022: $185; IWG 2021: $51; Stern: $300",
    ))
    
    # =========================================================================
    # 8. RE SHARES (physical limits)
    # =========================================================================
    
    # BAU final RE should be minimal
    bau_final_re = bau_summary.get("final_re_share", 0)
    checks.append(SanityCheck(
        category="RE Share",
        name="BAU final RE share (2056)",
        actual=bau_final_re * 100 if bau_final_re < 1 else bau_final_re,
        expected_low=0,
        expected_high=20,
        unit="%",
        source="BAU = continued diesel; minimal RE additions (~68.5 MW installed baseline)",
    ))
    
    # Maximum RE scenario should achieve high RE
    mr_final_re = summaries.get("maximum_re", {}).get("final_re_share", 0)
    checks.append(SanityCheck(
        category="RE Share",
        name="Maximum RE final share (2056)",
        actual=mr_final_re * 100 if mr_final_re < 1 else mr_final_re,
        expected_low=50,
        expected_high=100,
        unit="%",
        source="S6 design: outer islands 100% RE + near-shore + floating → 65-85% national",
    ))
    
    # =========================================================================
    # 9. HEALTH BENEFITS
    # =========================================================================
    
    checks.append(SanityCheck(
        category="Health",
        name="Health damage cost per MWh diesel",
        actual=cfg.economics.health_damage_cost_per_mwh,
        expected_low=10,
        expected_high=100,
        unit="USD/MWh",
        source="Parry et al. 2014 (IMF WP/14/199): $30-60/MWh for developing countries",
    ))
    
    # =========================================================================
    # 10. CABLE PARAMETERS (FI-specific)
    # =========================================================================
    
    checks.append(SanityCheck(
        category="Cable",
        name="India-Maldives cable length",
        actual=cfg.one_grid.cable_length_km,
        expected_low=600,
        expected_high=1000,
        unit="km",
        source="Direct distance ~600km; routing premium 15-20%; OSOWOG estimates 700-800 km",
    ))
    
    checks.append(SanityCheck(
        category="Cable",
        name="Cable CAPEX per km",
        actual=cfg.technology.cable_capex_per_km / 1e6,
        expected_low=1.5,
        expected_high=6.0,
        unit="$M/km",
        source="CIGRÉ TB 610: $2-5M/km for HVDC submarine cable; Skog 2010: $3M/km typical",
    ))
    
    # =========================================================================
    # 11. WTE PARAMETERS
    # =========================================================================
    
    checks.append(SanityCheck(
        category="WTE",
        name="WTE CAPEX per kW",
        actual=cfg.wte.capex_per_kw,
        expected_low=5000,
        expected_high=15000,
        unit="USD/kW",
        source="ICLEI WtE Guidebook 2021: $8k-12k/kW for <20 MW; EIA AEO 2024: $8.5k/kW",
    ))
    
    checks.append(SanityCheck(
        category="WTE",
        name="WTE capacity factor",
        actual=cfg.wte.capacity_factor,
        expected_low=0.60,
        expected_high=0.90,
        unit="ratio",
        source="Typical WTE CF 70-85% (waste supply limited); ICLEI 2021",
    ))
    
    # =========================================================================
    # 12. LNG COST PARAMETERS
    # =========================================================================
    
    checks.append(SanityCheck(
        category="LNG",
        name="LNG CAPEX per MW",
        actual=cfg.lng.capex_per_mw / 1e6,
        expected_low=0.8,
        expected_high=2.0,
        unit="$M/MW",
        source="ADB/Mahurkar 2023; IEA WEO 2024: $0.8-1.5M/MW for small-scale LNG",
    ))
    
    checks.append(SanityCheck(
        category="LNG",
        name="LNG fuel cost per MWh",
        actual=cfg.lng.fuel_cost_per_mwh,
        expected_low=40,
        expected_high=120,
        unit="USD/MWh",
        source="IEA Gas Market Report 2024; Platts LNG ~$14/MMBtu × 7 MMBtu/MWh = $98 max",
    ))
    
    # =========================================================================
    # 13. CROSS-SCENARIO CONSISTENCY
    # =========================================================================
    
    # All scenarios should use same discount rate, base year, emission factor
    # (These are structural — checked via config, not per-scenario)
    checks.append(SanityCheck(
        category="Consistency",
        name="Discount rate = 6% (ADB SIDS standard)",
        actual=cba["discount_rate"],
        expected_low=0.05999,
        expected_high=0.06001,
        unit="%",
        source="All scenarios must use same discount rate for comparability",
    ))
    
    checks.append(SanityCheck(
        category="Consistency",
        name="Base year = 2026",
        actual=cba["base_year"],
        expected_low=2025,
        expected_high=2027,
        unit="year",
        source="All scenarios must use same base year",
    ))
    
    checks.append(SanityCheck(
        category="Consistency",
        name="End year = 2056 (30yr horizon)",
        actual=cba["end_year"],
        expected_low=2055,
        expected_high=2057,
        unit="year",
        source="All scenarios must use same analysis horizon",
    ))
    
    # NPV ordering: LNG < MR < NS < NG ~ FI < IG < BAU (total costs)
    scenario_npvs = {k: v["pv_total_costs"] / 1e9 for k, v in cba["npv_results"].items()}
    bau_npv = scenario_npvs["bau"]
    best_alt_npv = min(v for k, v in scenario_npvs.items() if k != "bau")
    checks.append(SanityCheck(
        category="Consistency",
        name="BAU is most expensive scenario",
        actual=bau_npv,
        expected_low=best_alt_npv + 0.001,
        expected_high=50.0,
        unit="$B",
        source="Diesel status quo should have highest total costs (fuel dominates)",
        note=f"BAU={bau_npv:.1f}B, cheapest={best_alt_npv:.1f}B",
    ))
    
    # =========================================================================
    # 14. STRUCTURAL INVARIANT CHECKS
    # =========================================================================
    
    # --- 14a. Cost Summation Identity ---
    # pv_total_costs should equal capex + opex + fuel + ppa - salvage
    # Since salvage is not exported, verify: parts >= total (difference = salvage >= 0)
    for s_key in ["bau", "full_integration", "national_grid", "islanded_green",
                   "nearshore_solar", "maximum_re", "lng_transition"]:
        npv_r = cba["npv_results"][s_key]
        parts = (npv_r["pv_capex"] + npv_r["pv_opex"] +
                 npv_r["pv_fuel"] + npv_r["pv_ppa"])
        total = npv_r["pv_total_costs"]
        implied_salvage = parts - total  # should be >= 0
        checks.append(SanityCheck(
            category="Structural",
            name=f"{s_key} cost identity (salvage≥0)",
            actual=implied_salvage / 1e6,
            expected_low=0.0,
            expected_high=5000.0,  # salvage up to $5B for cable scenarios
            unit="$M",
            source="pv_total = capex + opex + fuel + ppa - salvage; salvage must be non-negative",
            note=f"total={total/1e9:.2f}B, parts={parts/1e9:.2f}B",
        ))
    
    # --- 14b. Demand Monotonicity (BAU) ---
    # At 5% growth, BAU demand should be monotonically non-decreasing
    # (even with saturation ceiling, demand should never fall)
    # Run BAU scenario to get per-year demand
    try:
        from model.scenarios.status_quo import StatusQuoScenario
        sq = StatusQuoScenario(cfg)
        sq_results = sq.run()
        demands = [(yr, gm.total_demand_gwh) 
                    for yr, gm in sorted(sq_results.generation_mix.items())]
        
        # Check monotonicity
        violations = 0
        for i in range(1, len(demands)):
            if demands[i][1] < demands[i-1][1] - 0.001:  # 1 MWh tolerance
                violations += 1
        
        checks.append(SanityCheck(
            category="Structural",
            name="BAU demand monotonically increasing",
            actual=violations,
            expected_low=0,
            expected_high=0,
            unit="violations",
            source="At positive growth rate, demand must never decrease year-over-year",
            note=f"Checked {len(demands)} years; first={demands[0][1]:.0f} GWh, last={demands[-1][1]:.0f} GWh",
        ))
        
        # --- 14c. Generation Balance ---
        # Total generation from all sources should equal demand for each year
        # (generation = diesel + solar + imports + lng + wte; should match demand)
        gen_balance_max_err = 0.0
        gen_balance_worst_year = demands[0][0]
        for yr, gm in sq_results.generation_mix.items():
            total_gen = gm.diesel_gwh + gm.solar_gwh + gm.import_gwh + gm.lng_gwh + gm.wte_gwh
            err_pct = abs(total_gen - gm.total_demand_gwh) / max(gm.total_demand_gwh, 0.001) * 100
            if err_pct > gen_balance_max_err:
                gen_balance_max_err = err_pct
                gen_balance_worst_year = yr
        
        checks.append(SanityCheck(
            category="Structural",
            name="BAU generation = demand (max error %)",
            actual=gen_balance_max_err,
            expected_low=0.0,
            expected_high=1.0,  # <1% tolerance
            unit="%",
            source="Energy balance: sum of generation sources must equal demand",
            note=f"Worst year: {gen_balance_worst_year}",
        ))
        
        # --- 14d. Cross-Scenario Demand Consistency ---
        # All scenarios with same growth rate should have same base demand
        # Check that FI (5% growth) and NG (4% growth) both start at same base
        from model.scenarios.one_grid import FullIntegrationScenario
        from model.scenarios.green_transition import NationalGridScenario
        from model.config import BASE_YEAR
        
        fi_scenario = FullIntegrationScenario(cfg)
        fi_results = fi_scenario.run()
        ng_scenario = NationalGridScenario(cfg)
        ng_results = ng_scenario.run()
        
        base_year = BASE_YEAR
        sq_base = sq_results.generation_mix[base_year].total_demand_gwh
        fi_base = fi_results.generation_mix[base_year].total_demand_gwh
        ng_base = ng_results.generation_mix[base_year].total_demand_gwh
        
        # All should share the same base-year demand (1,200 GWh)
        max_base_diff = max(
            abs(sq_base - fi_base),
            abs(sq_base - ng_base),
            abs(fi_base - ng_base),
        )
        
        checks.append(SanityCheck(
            category="Structural",
            name="Base-year demand consistent across scenarios",
            actual=max_base_diff,
            expected_low=0.0,
            expected_high=0.1,  # < 0.1 GWh tolerance
            unit="GWh",
            source="All scenarios must share the same base-year demand from config",
            note=f"BAU={sq_base:.1f}, FI={fi_base:.1f}, NG={ng_base:.1f} GWh",
        ))
        
        # --- 14e. Generation Share Sum ---
        # diesel_share + re_share + import_share + lng_share should sum to ~1.0
        for s_key, s_results in [("bau", sq_results), ("full_integration", fi_results),
                                  ("national_grid", ng_results)]:
            last_year = max(s_results.generation_mix.keys())
            gm_last = s_results.generation_mix[last_year]
            share_sum = gm_last.diesel_share + gm_last.re_share + gm_last.import_share + gm_last.lng_share
            checks.append(SanityCheck(
                category="Structural",
                name=f"{s_key} gen shares sum to 1.0",
                actual=share_sum,
                expected_low=0.99,
                expected_high=1.01,
                unit="fraction",
                source="Generation shares must sum to 100% (diesel + RE + import + LNG)",
                note=f"diesel={gm_last.diesel_share:.3f} re={gm_last.re_share:.3f} import={gm_last.import_share:.3f} lng={gm_last.lng_share:.3f}",
            ))
        
        # --- 14f. NPV Identity: total_benefits = fuel + emission + health + reliability + environmental ---
        # Reported total_benefits should equal the sum of itemised benefit streams.
        # This catches silent omissions without comparing to financial-only cost diff
        # (which excludes externalities by design).
        for s_key in ["full_integration", "national_grid", "islanded_green",
                       "nearshore_solar", "maximum_re", "lng_transition"]:
            inc = cba.get("incremental_vs_bau", {}).get(s_key, {})
            if not inc:
                continue
            itemised = (inc.get("fuel_savings", 0)
                        + inc.get("emission_savings", 0)
                        + inc.get("health_savings", 0)
                        + inc.get("reliability_savings", 0)
                        + inc.get("environmental_savings", 0))
            reported_total = inc.get("total_benefits", 0)
            if abs(reported_total) > 0:
                identity_err_pct = abs(itemised - reported_total) / abs(reported_total) * 100
            else:
                identity_err_pct = 0.0
            checks.append(SanityCheck(
                category="Structural",
                name=f"{s_key} benefit-streams identity (err %)",
                actual=identity_err_pct,
                expected_low=0.0,
                expected_high=1.0,  # <1% tolerance
                unit="%",
                source="total_benefits = fuel + emission + health + reliability + environmental savings",
                note=f"itemised={itemised/1e9:.2f}B, reported={reported_total/1e9:.2f}B",
            ))
        
        # --- 14g. IRR Range Validation ---
        # IRR should be within plausible range (0% to 100%) for all alternatives
        for s_key in ["full_integration", "national_grid", "islanded_green",
                       "nearshore_solar", "maximum_re", "lng_transition"]:
            inc = cba.get("incremental_vs_bau", {}).get(s_key, {})
            irr = inc.get("irr", None)
            if irr is not None and irr > 0:
                irr_pct = irr * 100
                checks.append(SanityCheck(
                    category="Structural",
                    name=f"{s_key} IRR range",
                    actual=irr_pct,
                    expected_low=1.0,   # At least 1%
                    expected_high=100.0,  # No more than 100%
                    unit="%",
                    source="IRR must be in plausible range (1%-100%) for infrastructure projects",
                ))
        
    except Exception as e:
        # If live scenario checks fail, add a warning-level check
        checks.append(SanityCheck(
            category="Structural",
            name="Live scenario checks",
            actual=-1,
            expected_low=0,
            expected_high=0,
            unit="status",
            source=f"Could not run live scenario checks: {type(e).__name__}: {e}",
        ))
    
    # Evaluate all checks
    for check in checks:
        check.evaluate()
    
    return checks


def print_results(checks: List[SanityCheck]) -> int:
    """Print formatted results and return exit code."""
    
    print("=" * 80)
    print("  MALDIVES ENERGY CBA — EQUATION SANITY CHECKS (V6)")
    print("=" * 80)
    print()
    
    categories = {}
    for check in checks:
        if check.category not in categories:
            categories[check.category] = []
        categories[check.category].append(check)
    
    n_pass = sum(1 for c in checks if c.status == "PASS")
    n_warn = sum(1 for c in checks if c.status == "WARN")
    n_fail = sum(1 for c in checks if c.status == "FAIL")
    
    for cat, cat_checks in categories.items():
        print(f"\n  [{cat}]")
        print(f"  {'-' * 76}")
        for check in cat_checks:
            icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[check.status]
            color_status = check.status
            
            if isinstance(check.actual, float) and abs(check.actual) >= 1000:
                actual_str = f"{check.actual:,.1f}"
            elif isinstance(check.actual, float):
                actual_str = f"{check.actual:.4f}"
            else:
                actual_str = f"{check.actual}"
            
            range_str = f"[{check.expected_low:.4g} – {check.expected_high:.4g}]"
            print(f"  {icon} {color_status:4s} | {check.name:<40s} | "
                  f"{actual_str:>12s} {check.unit:<12s} | range: {range_str}")
            if check.note:
                print(f"         | note: {check.note}")
    
    print()
    print("=" * 80)
    print(f"  SUMMARY: {n_pass} PASS, {n_warn} WARN, {n_fail} FAIL "
          f"(total: {len(checks)} checks)")
    print("=" * 80)
    
    if n_fail > 0:
        print("\n  ✗ FAILURES DETECTED — review model equations and parameters")
        for check in checks:
            if check.status == "FAIL":
                print(f"    - {check.category}/{check.name}: "
                      f"{check.actual} not in [{check.expected_low}, {check.expected_high}]")
                print(f"      Source: {check.source}")
        return 1
    
    if n_warn > 0:
        print("\n  ⚠ WARNINGS — values near boundary of expected range")
        for check in checks:
            if check.status == "WARN":
                print(f"    - {check.category}/{check.name}: "
                      f"{check.actual} near boundary of [{check.expected_low}, {check.expected_high}]")
        return 0
    
    print("\n  ✓ All checks passed")
    return 0


if __name__ == "__main__":
    checks = run_all_checks()
    exit_code = print_results(checks)
    sys.exit(exit_code)
