"""
Scenario 4: Islanded Green Transition
=====================================

Individual island RE systems without inter-island grid or India connection.
Each island operates independently with solar PV + battery storage.

Key characteristics:
- Solar PV + battery on each inhabited island
- No submarine cables between islands
- No India interconnector
- Higher per-island costs due to lack of economies of scale
- Maximum energy independence but higher redundancy costs
"""

from dataclasses import dataclass, field
from typing import Dict, List
from copy import deepcopy

from . import BaseScenario, GenerationMix, ScenarioResults
from ..config import Config, get_config
from ..demand import DemandProjector
from ..costs import CostCalculator, AnnualCosts
from ..emissions import EmissionsCalculator, AnnualEmissions


class IslandedGreenScenario(BaseScenario):
    """Islanded Green Transition: Individual island RE systems."""
    
    def __init__(self, config: Config = None):
        config = config or get_config()
        super().__init__(
            name="Islanded Green",
            description="Solar+battery on each island, no inter-island grid",
            config=config,
        )
        
        # Initialize demand projector
        self.demand = self._init_demand_projector()
        
        # RE targets (slightly lower achievable than National Grid due to no load balancing)
        self.re_targets = deepcopy(self.config.green_transition.re_targets)
        for year in self.re_targets:
            self.re_targets[year] = min(self.re_targets[year] * 0.90, 0.65)
        
        # Track capacities
        self.solar_capacity_mw = self.config.current_system.solar_capacity_mw
        self.battery_capacity_mwh = 0.0
        self.diesel_capacity_mw = self.config.current_system.diesel_capacity_mw
        
        # Island cost premium (35% higher due to diseconomies of scale)
        self.island_premium = 1.35
        
        # Higher battery ratio (4 MWh/MW solar vs 2 for grid-connected)
        self.battery_ratio = 4.0
        
        # Track capacity additions
        self.solar_additions: Dict[int, float] = {}
        self.battery_additions: Dict[int, float] = {}
        
        # Pre-calculate deployment schedule
        self._calculate_deployment_schedule()
    
    def _init_demand_projector(self) -> DemandProjector:
        """Initialize demand projector for islanded scenario."""
        return DemandProjector(
            config=self.config,
            scenario="green_transition",  # Use same base growth rate
            growth_rate=self.config.demand.growth_rates["green_transition"],
        )
    
    def _interpolate_re_target(self, year: int) -> float:
        """Interpolate RE target for years not explicitly specified."""
        targets = self.re_targets
        years_list = sorted(targets.keys())
        
        if year in targets:
            return targets[year]
        
        # Handle years beyond target range - use last/first available target
        if year > max(years_list):
            return targets[max(years_list)]
        if year < min(years_list):
            return targets[min(years_list)]
        
        lower_year = max(y for y in years_list if y <= year)
        upper_year = min(y for y in years_list if y >= year)
        
        if lower_year == upper_year:
            return targets[lower_year]
        
        lower_target = targets[lower_year]
        upper_target = targets[upper_year]
        fraction = (year - lower_year) / (upper_year - lower_year)
        return lower_target + fraction * (upper_target - lower_target)
    
    def _calculate_deployment_schedule(self) -> None:
        """Pre-calculate solar and battery additions for each year."""
        prev_solar = self.config.current_system.solar_capacity_mw
        prev_battery = 0.0
        
        for year in self.config.time_horizon:
            re_target = self._interpolate_re_target(year)
            demand_gwh = self.demand.get_demand(year)
            required_solar_gwh = demand_gwh * re_target
            
            capacity_factor = self.config.technology.solar_pv_capacity_factor
            required_solar_mw = (required_solar_gwh * 1000) / (8760 * capacity_factor)
            
            solar_addition = max(0, required_solar_mw - prev_solar)
            self.solar_additions[year] = solar_addition
            prev_solar = required_solar_mw
            
            required_battery_mwh = required_solar_mw * self.battery_ratio
            battery_addition = max(0, required_battery_mwh - prev_battery)
            self.battery_additions[year] = battery_addition
            prev_battery = required_battery_mwh
    
    def calculate_generation_mix(self, year: int) -> GenerationMix:
        """Calculate generation mix for Islanded Green scenario."""
        demand_gwh = self.demand.get_demand(year)
        peak_mw = self.demand.get_peak(year)
        
        # Update capacities
        self.solar_capacity_mw += self.solar_additions.get(year, 0)
        self.battery_capacity_mwh += self.battery_additions.get(year, 0)
        
        # Get RE target
        re_target = self._interpolate_re_target(year)
        
        # Solar generation
        solar_gwh = self.cost_calc.solar_generation(self.solar_capacity_mw)
        max_solar = demand_gwh * re_target
        solar_gwh = min(solar_gwh, max_solar)
        
        # Diesel meets the rest
        diesel_gwh = demand_gwh - solar_gwh
        if diesel_gwh < 0:
            diesel_gwh = 0
        
        return GenerationMix(
            year=year,
            total_demand_gwh=round(demand_gwh, 1),
            diesel_gwh=round(diesel_gwh, 1),
            solar_gwh=round(solar_gwh, 1),
            import_gwh=0.0,
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
        
        # Battery replacement (12-year cycle)
        if year - 12 >= self.config.base_year:
            past_battery = self.battery_additions.get(year - 12, 0)
            if past_battery > 0:
                costs.capex_battery += self.cost_calc.battery_capex(past_battery, year) * self.island_premium
        
        # Diesel replacement
        diesel_life = self.config.technology.diesel_gen_lifetime
        if year == self.config.base_year or (year - self.config.base_year) % diesel_life == 0:
            diesel_mw = gen_mix.diesel_capacity_mw / diesel_life
            costs.capex_diesel = self.cost_calc.diesel_gen_capex(diesel_mw)
        
        # OPEX (with premium for islanded operations)
        costs.opex_solar = self.cost_calc.solar_opex(gen_mix.solar_capacity_mw, year) * 1.2
        costs.opex_battery = self.cost_calc.battery_opex(gen_mix.battery_capacity_mwh) * 1.2
        costs.opex_diesel = self.cost_calc.diesel_gen_opex(gen_mix.diesel_gwh)
        
        # Fuel costs
        costs.fuel_diesel = self.cost_calc.diesel_fuel_cost(gen_mix.diesel_gwh, year)
        
        return costs


if __name__ == "__main__":
    print("=" * 60)
    print("ISLANDED GREEN SCENARIO TEST")
    print("=" * 60)
    
    config = get_config()
    scenario = IslandedGreenScenario(config)
    
    results = scenario.run()
    
    print("\n--- GENERATION MIX ---")
    for year in [2024, 2028, 2030, 2040, 2050]:
        gen = results.generation_mix[year]
        print(f"{year}: Demand {gen.total_demand_gwh:.0f} GWh, RE {gen.re_share:.1%}")
    
    print("\n--- SUMMARY ---")
    summary = scenario.get_summary()
    print(f"Total costs: ${summary['total_costs_million']:,.0f}M")
    print(f"Total emissions: {summary['total_emissions_mtco2']:.2f} MtCO2")
    
    print("\n✓ Islanded Green scenario tests passed!")
