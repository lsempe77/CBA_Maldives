"""
National Grid Scenario
======================

Scenario 3: Green transition with inter-island Maldives grid, NO India connection.

Assumptions:
- 33% RE by 2028, 70% by 2050
- Solar PV + battery deployment
- Inter-island submarine cable network (NOT to India)
- Diesel backup for residual demand
- Energy independence (no imports)
"""

from typing import Dict
import numpy as np

from ..config import Config, get_config
from ..demand import DemandProjector
from ..costs import CostCalculator, AnnualCosts
from . import BaseScenario, GenerationMix


class NationalGridScenario(BaseScenario):
    """
    National Grid: RE acceleration with inter-island grid (no India cable).
    """
    
    def __init__(self, config: Config = None):
        config = config or get_config()
        super().__init__(
            name="National Grid",
            description="RE + inter-island grid (no India cable)",
            config=config,
        )
        
        # Initialize demand projector with green transition growth rate
        self.demand = self._init_demand_projector()
        
        # RE targets from config
        self.re_targets = self.config.green_transition.re_targets
        
        # Track installed capacities
        self.solar_capacity_mw = self.config.current_system.solar_capacity_mw
        self.battery_capacity_mwh = 0.0
        self.diesel_capacity_mw = self.config.current_system.diesel_capacity_mw
        
        # Track capacity additions by year (for CAPEX)
        self.solar_additions: Dict[int, float] = {}
        self.battery_additions: Dict[int, float] = {}
        
        # Inter-island grid
        self.inter_island_built = False
        
        # Pre-calculate deployment schedule
        self._calculate_deployment_schedule()
    
    def _init_demand_projector(self) -> DemandProjector:
        return DemandProjector(
            config=self.config,
            scenario="green_transition",
            growth_rate=self.config.demand.growth_rates["green_transition"],
        )
    
    def _interpolate_re_target(self, year: int) -> float:
        """
        Interpolate RE target for years not explicitly specified.
        """
        targets = self.re_targets
        years = sorted(targets.keys())
        
        if year in targets:
            return targets[year]
        
        # Handle years beyond target range - use last/first available target
        if year > max(years):
            return targets[max(years)]
        if year < min(years):
            return targets[min(years)]
        
        # Find surrounding years
        lower_year = max(y for y in years if y <= year)
        upper_year = min(y for y in years if y >= year)
        
        if lower_year == upper_year:
            return targets[lower_year]
        
        # Linear interpolation
        lower_target = targets[lower_year]
        upper_target = targets[upper_year]
        
        fraction = (year - lower_year) / (upper_year - lower_year)
        return lower_target + fraction * (upper_target - lower_target)
    
    def _calculate_deployment_schedule(self) -> None:
        """
        Pre-calculate solar and battery additions for each year.
        """
        prev_solar = self.config.current_system.solar_capacity_mw
        prev_battery = 0.0
        
        for year in self.config.time_horizon:
            # Get RE target for year
            re_target = self._interpolate_re_target(year)
            
            # Get demand for year
            demand_gwh = self.demand.get_demand(year)
            
            # Required solar generation to meet RE target
            required_solar_gwh = demand_gwh * re_target
            
            # Required solar capacity
            # Generation = Capacity * 8760 * Capacity_Factor / 1000
            capacity_factor = self.config.technology.solar_pv_capacity_factor
            required_solar_mw = (required_solar_gwh * 1000) / (8760 * capacity_factor)
            
            # Solar addition
            solar_addition = max(0, required_solar_mw - prev_solar)
            self.solar_additions[year] = solar_addition
            prev_solar = required_solar_mw
            
            # Battery: 2 MWh per MW of solar (from config)
            required_battery_mwh = required_solar_mw * self.config.green_transition.battery_ratio
            battery_addition = max(0, required_battery_mwh - prev_battery)
            self.battery_additions[year] = battery_addition
            prev_battery = required_battery_mwh
    
    def calculate_generation_mix(self, year: int) -> GenerationMix:
        """
        Calculate generation mix for Green Transition.
        """
        # Get demand for year
        demand_gwh = self.demand.get_demand(year)
        peak_mw = self.demand.get_peak(year)
        
        # Get RE target
        re_target = self._interpolate_re_target(year)
        
        # Update installed capacities
        self.solar_capacity_mw += self.solar_additions.get(year, 0)
        self.battery_capacity_mwh += self.battery_additions.get(year, 0)
        
        # Solar generation
        solar_gwh = self.cost_calc.solar_generation(self.solar_capacity_mw)
        
        # Cap solar at RE target (simplified - no detailed dispatch)
        max_solar_gwh = demand_gwh * re_target
        solar_gwh = min(solar_gwh, max_solar_gwh)
        
        # Diesel meets the rest
        diesel_gwh = demand_gwh - solar_gwh
        if diesel_gwh < 0:
            diesel_gwh = 0
        
        # Diesel capacity (reserve for backup)
        # Even with high RE, need diesel for reliability
        min_diesel_capacity = peak_mw * self.config.technology.min_diesel_backup
        reserve_factor = 1 + self.config.technology.reserve_margin
        required_diesel_mw = max(
            min_diesel_capacity,
            peak_mw * (1 - re_target) * reserve_factor  # Diesel to cover non-RE peak
        )
        
        # Don't add diesel, only maintain/reduce
        self.diesel_capacity_mw = min(self.diesel_capacity_mw, required_diesel_mw)
        self.diesel_capacity_mw = max(self.diesel_capacity_mw, min_diesel_capacity)
        
        return GenerationMix(
            year=year,
            total_demand_gwh=demand_gwh,
            diesel_gwh=round(diesel_gwh, 1),
            solar_gwh=round(solar_gwh, 1),
            import_gwh=0.0,
            diesel_capacity_mw=round(self.diesel_capacity_mw, 1),
            solar_capacity_mw=round(self.solar_capacity_mw, 1),
            battery_capacity_mwh=round(self.battery_capacity_mwh, 1),
        )
    
    def calculate_annual_costs(self, year: int, gen_mix: GenerationMix) -> AnnualCosts:
        """
        Calculate costs for Green Transition scenario.
        """
        costs = AnnualCosts(year=year)
        
        # CAPEX: Solar additions
        solar_addition = self.solar_additions.get(year, 0)
        if solar_addition > 0:
            costs.capex_solar = self.cost_calc.solar_capex(solar_addition, year)
        
        # CAPEX: Battery additions
        battery_addition = self.battery_additions.get(year, 0)
        if battery_addition > 0:
            costs.capex_battery = self.cost_calc.battery_capex(battery_addition, year)
        
        # CAPEX: Battery replacement (check if any batteries need replacing)
        # Lifetime-based replacement cycle from config
        battery_life = self.config.technology.battery_lifetime
        if year - battery_life >= self.config.base_year:
            past_battery = self.battery_additions.get(year - battery_life, 0)
            if past_battery > 0:
                costs.capex_battery += self.cost_calc.battery_capex(past_battery, year)
        
        # CAPEX: Inter-island grid (one-time)
        if (self.config.green_transition.inter_island_grid and 
            year == self.config.green_transition.inter_island_build_end and
            not self.inter_island_built):
            costs.capex_grid = self.cost_calc.inter_island_cable_capex(
                self.config.green_transition.inter_island_km
            )
            self.inter_island_built = True
        
        # CAPEX: Diesel (minimal - only replacements, no expansion)
        # Reduced replacement as fleet shrinks
        diesel_replacement_mw = gen_mix.diesel_capacity_mw / self.config.technology.diesel_gen_lifetime
        costs.capex_diesel = self.cost_calc.diesel_gen_capex(diesel_replacement_mw)
        
        # OPEX: Solar
        costs.opex_solar = self.cost_calc.solar_opex(gen_mix.solar_capacity_mw, year)
        
        # OPEX: Battery
        costs.opex_battery = self.cost_calc.battery_opex(gen_mix.battery_capacity_mwh)
        
        # OPEX: Diesel
        costs.opex_diesel = self.cost_calc.diesel_gen_opex(gen_mix.diesel_gwh)
        
        # Fuel: Diesel (reduced)
        costs.fuel_diesel = self.cost_calc.diesel_fuel_cost(gen_mix.diesel_gwh, year)
        
        return costs


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("NATIONAL GRID SCENARIO TEST")
    print("=" * 60)
    
    config = get_config()
    scenario = NationalGridScenario(config)
    
    # Run scenario
    results = scenario.run()
    
    # Print generation mix for key years
    print("\n--- GENERATION MIX ---")
    print(f"{'Year':<6} {'Demand':<10} {'Diesel':<10} {'Solar':<10} {'RE %':<10} {'Solar MW':<10} {'Battery MWh':<12}")
    print("-" * 80)
    for year in [2024, 2028, 2030, 2040, 2050]:
        gen = results.generation_mix[year]
        print(f"{year:<6} {gen.total_demand_gwh:<10.0f} {gen.diesel_gwh:<10.0f} {gen.solar_gwh:<10.0f} {gen.re_share:<10.1%} {gen.solar_capacity_mw:<10.0f} {gen.battery_capacity_mwh:<12.0f}")
    
    # Print costs for key years
    print("\n--- ANNUAL COSTS (Million USD) ---")
    print(f"{'Year':<6} {'CAPEX':<12} {'Solar':<10} {'Battery':<10} {'OPEX':<10} {'Fuel':<12} {'Total':<10}")
    print("-" * 80)
    for year in [2024, 2028, 2030, 2040, 2050]:
        cost = results.annual_costs[year]
        print(f"{year:<6} {cost.total_capex/1e6:<12.1f} {cost.capex_solar/1e6:<10.1f} {cost.capex_battery/1e6:<10.1f} {cost.total_opex/1e6:<10.1f} {cost.fuel_diesel/1e6:<12.1f} {cost.total/1e6:<10.1f}")
    
    # Print emissions
    print("\n--- EMISSIONS (ktCO2) ---")
    for year in [2024, 2028, 2030, 2040, 2050]:
        em = results.annual_emissions[year]
        print(f"{year}: {em.total_emissions_ktco2:.0f} ktCO2")
    
    # Summary
    print("\n--- SUMMARY ---")
    summary = scenario.get_summary()
    print(f"Total costs (2024-2050): ${summary['total_costs_million']:,.0f}M")
    print(f"  - CAPEX: ${summary['total_capex_million']:,.0f}M")
    print(f"  - OPEX: ${summary['total_opex_million']:,.0f}M")
    print(f"  - Fuel: ${summary['total_fuel_million']:,.0f}M")
    print(f"Total emissions: {summary['total_emissions_mtco2']:.2f} MtCO2")
    print(f"Final RE share (2050): {summary['final_re_share']:.1%}")
    
    print("\n✓ National Grid scenario tests passed!")
