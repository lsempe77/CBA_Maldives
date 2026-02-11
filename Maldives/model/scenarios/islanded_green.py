"""
Scenario 4: Islanded Green Transition
=====================================

Individual island RE systems without inter-island grid or India connection.
Each island operates independently with solar PV + battery storage.

Endogenous RE Deployment (LCOE-driven):
  Solar+battery LCOE ($0.213/kWh islanded) < Diesel LCOE ($0.299/kWh).
  Optimal outer-island RE = 100% as fast as deployable.
  Deployment ramp may be slower due to dispersed logistics.

Two-Segment Generation Model (same as National Grid):
  - OUTER ISLANDS (43% of demand): deploy at ramp rate × islanded factor
  - GREATER MALÉ (57% of demand): capped at ~4% RE (rooftop only)
  - National RE = weighted average → ceiling ~45%

Key characteristics:
- Solar PV + battery on each inhabited island
- No submarine cables between islands
- No India interconnector
- Higher per-island costs due to lack of economies of scale
- Maximum energy independence but higher redundancy costs
"""

from dataclasses import dataclass, field
from typing import Dict, List

from . import BaseScenario, GenerationMix, ScenarioResults
from ..config import Config, get_config
from ..demand import DemandProjector
from ..costs import CostCalculator, AnnualCosts
from ..emissions import EmissionsCalculator, AnnualEmissions


class IslandedGreenScenario(BaseScenario):
    """Islanded Green Transition: Individual island RE systems.
    
    Uses a two-segment model reflecting island-level solar land constraints:
    - Outer islands (43% demand): unconstrained, ramp to ~90% RE (islanded cap)
    - Greater Malé (57% demand): land-constrained, max ~4% RE (rooftop only)
    """
    
    def __init__(self, config: Config = None):
        config = config or get_config()
        super().__init__(
            name="Islanded Green",
            description="Solar+battery on each island, no inter-island grid",
            config=config,
        )
        
        # Initialize demand projector
        self.demand = self._init_demand_projector()
        
        # Endogenous deployment ramp — islanded may be slower than NG
        # Use NG ramp × islanded_re_cap_factor (0.90 = 10% slower logistics)
        re_cap = self.config.green_transition.islanded_re_cap_factor
        self.ramp_mw_yr = self.config.green_transition.deployment_ramp_mw_per_year * re_cap
        
        # Malé is land-constrained (same as NG)
        self.male_max_re = self.config.green_transition.male_max_re_share
        # D60: Density-constrained demand share — base year value stored,
        # but actual share computed per-year via config.male_demand_share()
        self.male_demand_share_base = self.config.current_system.male_electricity_share
        self._scenario_growth_rate = self.config.demand.growth_rates["green_transition"]
        
        # Track capacities (L19: init from config, not hardcoded 0)
        self.solar_capacity_mw = self.config.current_system.solar_capacity_mw
        self.battery_capacity_mwh = self.config.current_system.battery_capacity_mwh
        self.diesel_capacity_mw = self.config.current_system.diesel_capacity_mw
        
        # Malé rooftop solar (fixed cap from config)
        self.male_solar_cap_mw = self.config.current_system.male_rooftop_solar_mwp
        
        # Island cost premium (from config - diseconomies of scale)
        self.island_premium = self.config.green_transition.islanded_cost_premium
        
        # Higher battery ratio for islanded systems (from config)
        self.battery_ratio = self.config.green_transition.islanded_battery_ratio
        
        # Track capacity additions
        self.solar_additions: Dict[int, float] = {}
        self.battery_additions: Dict[int, float] = {}
        
        # Pre-calculate deployment schedule
        self._calculate_deployment_schedule()
    
    def _init_demand_projector(self) -> DemandProjector:
        """Initialize demand projector for islanded scenario.
        
        Uses green_transition growth rate (4%/yr) — same as National Grid.
        Rationale: islanded RE deployment changes supply-side costs but
        does not alter demand growth patterns. No separate 'islanded'
        growth rate exists in config because the demand driver (population
        + GDP) is independent of grid topology. If future research shows
        islanded systems induce different demand (e.g., via different
        electricity prices), add an 'islanded_green' key to
        config.demand.growth_rates.
        """
        return DemandProjector(
            config=self.config,
            scenario="green_transition",
            growth_rate=self.config.demand.growth_rates["green_transition"],
        )
    
    def _calculate_deployment_schedule(self) -> None:
        """Endogenous deployment: add solar at max ramp rate each year.
        
        Same logic as NG but with islanded ramp factor (slightly slower).
        Islanded systems don't need inter-island cables.
        Uses effective CF (raw CF × temp derating) for sizing.
        Sizes solar against gross demand (incl. distribution losses).
        """
        # LW-01: Use base class precomputed effective CF (temp-derated)
        effective_cf = self._effective_solar_cf
        
        # MR-09: Distribution loss computed per year using weighted_distribution_loss()
        
        # Existing outer-island solar (pre-base-year vintage)
        self._existing_outer_solar_mw = max(
            0, self.config.current_system.solar_capacity_mw - self.male_solar_cap_mw
        )
        prev_outer_solar_mw = self._existing_outer_solar_mw
        prev_battery = 0.0
        
        # Store the outer-island RE share per year (computed endogenously)
        self._outer_re_by_year: Dict[int, float] = {}
        # Store time-varying demand shares for generation mix
        self._male_share_by_year: Dict[int, float] = {}
        self._outer_share_by_year: Dict[int, float] = {}
        
        for year in self.config.time_horizon:
            # D60: Time-varying Malé demand share (density-constrained)
            male_share = self.config.male_demand_share(year, self._scenario_growth_rate)
            outer_share = 1.0 - male_share
            
            # MR-09: Year-varying weighted distribution loss
            dist_loss = self.config.weighted_distribution_loss(year, self._scenario_growth_rate)
            loss_factor = 1.0 / (1.0 - dist_loss)
            
            net_demand_gwh = self.demand.get_demand(year)
            gross_demand_gwh = net_demand_gwh * loss_factor
            outer_demand_gwh = gross_demand_gwh * outer_share
            
            # MW needed to serve 100% of outer demand (using effective CF)
            mw_for_100pct = (outer_demand_gwh * 1000) / (8760 * effective_cf)
            
            # Add up to ramp_mw_yr, but don't exceed what's needed
            gap_mw = max(0, mw_for_100pct - prev_outer_solar_mw)
            outer_solar_addition = min(self.ramp_mw_yr, gap_mw)
            
            new_outer_solar_mw = prev_outer_solar_mw + outer_solar_addition
            
            # Compute outer RE share (endogenous outcome, using effective CF)
            outer_gen_gwh = new_outer_solar_mw * 8760 * effective_cf / 1000
            outer_re = min(1.0, outer_gen_gwh / outer_demand_gwh) if outer_demand_gwh > 0 else 0.0
            self._outer_re_by_year[year] = outer_re
            self._male_share_by_year[year] = male_share
            self._outer_share_by_year[year] = outer_share
            
            # Total solar = outer + Malé rooftop
            total_solar_mw = new_outer_solar_mw + self.male_solar_cap_mw
            prev_total_solar = prev_outer_solar_mw + self.male_solar_cap_mw
            
            solar_addition = max(0, total_solar_mw - prev_total_solar)
            self.solar_additions[year] = solar_addition
            prev_outer_solar_mw = new_outer_solar_mw
            
            # Battery only on outer islands (Malé diesel backup, no battery needed)
            required_battery_mwh = new_outer_solar_mw * self.battery_ratio
            battery_addition = max(0, required_battery_mwh - prev_battery)
            self.battery_additions[year] = battery_addition
            prev_battery = required_battery_mwh
    
    def _get_national_re_target(self, year: int) -> float:
        """Compute national RE as weighted average of two segments.
        Outer RE is computed endogenously from ramp-based deployment.
        D60: Uses time-varying Malé demand share (density-constrained).
        """
        outer_re = self._outer_re_by_year.get(year, 0.0)
        male_share = self._male_share_by_year.get(year, self.male_demand_share_base)
        outer_share = self._outer_share_by_year.get(year, 1.0 - self.male_demand_share_base)
        national_re = (outer_share * outer_re 
                       + male_share * self.male_max_re)
        return national_re
    
    def calculate_generation_mix(self, year: int) -> GenerationMix:
        """Calculate generation mix for Islanded Green scenario.
        
        Two-segment model: national RE = weighted avg of outer + Malé.
        """
        net_demand_gwh = self.demand.get_demand(year)
        peak_mw = self.demand.get_peak(year)
        
        # C2+R5: Gross up for distribution losses (segmented Malé 8% / outer 12%)
        demand_gwh = self.cost_calc.gross_up_for_losses(
            net_demand_gwh, include_distribution=True, include_hvdc=False,
            year=year, scenario_growth_rate=self._scenario_growth_rate,
        )
        
        # Update capacities
        self.solar_capacity_mw += self.solar_additions.get(year, 0)
        self.battery_capacity_mwh += self.battery_additions.get(year, 0)
        
        # Get national RE target (weighted average of two segments)
        re_target = self._get_national_re_target(year)
        
        # Solar generation with vintage-based degradation (C7, C8)
        solar_gwh = self.cost_calc.solar_generation_vintaged(
            solar_additions=self.solar_additions,
            year=year,
            existing_mw=self._existing_outer_solar_mw + self.male_solar_cap_mw,
        )
        max_solar = demand_gwh * re_target
        solar_gwh = min(solar_gwh, max_solar)
        
        # R6: Waste-to-energy baseload (Thilafushi 12 + Addu 1.5 + Vandhoo 0.5 = 14 MW)
        wte_gwh = 0.0
        if year >= self.config.wte.online_year:
            wte_gwh = min(self.config.wte.annual_generation_gwh, max(0, demand_gwh - solar_gwh))
        
        # Diesel meets the rest after solar + WTE
        diesel_gwh = demand_gwh - solar_gwh - wte_gwh
        if diesel_gwh < 0:
            diesel_gwh = 0
        
        return GenerationMix(
            year=year,
            total_demand_gwh=round(demand_gwh, 1),
            diesel_gwh=round(diesel_gwh, 1),
            solar_gwh=round(solar_gwh, 1),
            import_gwh=0.0,
            wte_gwh=round(wte_gwh, 1),
            diesel_capacity_mw=round(self.diesel_capacity_mw, 1),
            solar_capacity_mw=round(self.solar_capacity_mw, 1),
            battery_capacity_mwh=round(self.battery_capacity_mwh, 1),
        )
    
    def calculate_annual_costs(self, year: int, gen_mix: GenerationMix) -> AnnualCosts:
        """Calculate costs for Islanded Green scenario with island premium."""
        costs = AnnualCosts(year=year)
        
        # Apply island premium to all CAPEX
        
        # Solar CAPEX
        solar_addition = self.solar_additions.get(year, 0)
        if solar_addition > 0:
            base_solar_capex = self.cost_calc.solar_capex(solar_addition, year)
            costs.capex_solar = base_solar_capex * self.island_premium
        
        # Battery CAPEX
        battery_addition = self.battery_additions.get(year, 0)
        if battery_addition > 0:
            base_battery_capex = self.cost_calc.battery_capex(battery_addition, year)
            costs.capex_battery = base_battery_capex * self.island_premium
        
        # Battery replacement (lifetime-based cycle from config)
        battery_life = self.config.technology.battery_lifetime
        if year - battery_life >= self.config.base_year:
            past_battery = self.battery_additions.get(year - battery_life, 0)
            if past_battery > 0:
                costs.capex_battery += self.cost_calc.battery_capex(past_battery, year) * self.island_premium
        
        # Diesel replacement
        # LW-07: Uses modular interval-based replacement (every diesel_life years)
        # while S3/S5/S6/S7 use continuous annual replacement (capacity/lifetime).
        # Both are defensible — lumpy replacement is more realistic for small islands
        # with discrete generator sets. Continuous is a smoothing approximation.
        diesel_life = self.config.technology.diesel_gen_lifetime
        if year == self.config.base_year or (year - self.config.base_year) % diesel_life == 0:
            diesel_mw = gen_mix.diesel_capacity_mw / diesel_life
            costs.capex_diesel = self.cost_calc.diesel_gen_capex(diesel_mw)
        
        # OPEX (with premium for islanded operations from config)
        opex_premium = self.config.green_transition.islanded_opex_premium
        costs.opex_solar = self.cost_calc.solar_opex(gen_mix.solar_capacity_mw, year) * opex_premium
        costs.opex_battery = self.cost_calc.battery_opex(gen_mix.battery_capacity_mwh) * opex_premium
        costs.opex_diesel = self.cost_calc.diesel_gen_opex(gen_mix.diesel_gwh)
        
        # Fuel costs (C9: two-part fuel curve)
        costs.fuel_diesel = self.cost_calc.diesel_fuel_cost(
            gen_mix.diesel_gwh, year,
            diesel_capacity_mw=gen_mix.diesel_capacity_mw
        )
        
        # R6: WTE CAPEX (one-time at online year) + annual OPEX
        # WTE plants at Thilafushi (Malé) + Addu + Vandhoo — no island premium
        # (Thilafushi is industrial; Addu is secondary urban)
        if year == self.config.wte.online_year:
            costs.capex_wte = self.config.wte.total_capex * (1 + self.config.technology.climate_adaptation_premium)
        if (year >= self.config.wte.online_year
                and year < self.config.wte.online_year + self.config.wte.plant_lifetime):
            costs.opex_wte = self.config.wte.annual_opex
        
        # L11: Connection costs (phased rollout, with island premium)
        conn_cfg = self.config.connection
        conn_start = self.config.base_year + 1
        conn_end = conn_start + conn_cfg.rollout_years - 1
        if conn_start <= year <= conn_end:
            annual_hh = conn_cfg.number_of_households / conn_cfg.rollout_years
            costs.capex_connection = self.cost_calc.connection_capex(int(annual_hh)) * self.island_premium
        
        return costs


if __name__ == "__main__":
    print("=" * 60)
    print("ISLANDED GREEN SCENARIO TEST")
    print("=" * 60)
    
    config = get_config()
    scenario = IslandedGreenScenario(config)
    
    results = scenario.run()
    
    print("\n--- GENERATION MIX ---")
    key_years = [config.base_year, 2028, 2030, 2040, config.end_year]
    for year in key_years:
        gen = results.generation_mix[year]
        print(f"{year}: Demand {gen.total_demand_gwh:.0f} GWh, RE {gen.re_share:.1%}")
    
    print("\n--- SUMMARY ---")
    summary = scenario.get_summary()
    print(f"Total costs: ${summary['total_costs_million']:,.0f}M")
    print(f"Total emissions: {summary['total_emissions_mtco2']:.2f} MtCO2")
    
    print("\n✓ Islanded Green scenario tests passed!")
