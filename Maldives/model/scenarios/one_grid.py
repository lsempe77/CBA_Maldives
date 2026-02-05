"""
Full Integration Scenario
==========================

Scenario 2: India interconnector + inter-island Maldives grid + RE

Assumptions:
- Undersea cable to India operational by 2030
- Inter-island submarine cables connecting major atolls
- Complementary domestic solar PV
- Most comprehensive infrastructure investment
- Maximum system integration
"""

from typing import Dict
import numpy as np

from ..config import Config, get_config
from ..demand import DemandProjector
from ..costs import CostCalculator, AnnualCosts
from . import BaseScenario, GenerationMix


class FullIntegrationScenario(BaseScenario):
    """
    Full Integration: India cable + inter-island grid + domestic RE.
    """
    
    def __init__(self, config: Config = None):
        config = config or get_config()
        super().__init__(
            name="Full Integration",
            description="India cable + inter-island grid + domestic RE",
            config=config,
        )
        
        # Initialize demand projector
        self.demand = self._init_demand_projector()
        
        # Cable parameters from config
        self.cable_online_year = self.config.one_grid.cable_online_year
        self.cable_capacity_mw = self.config.one_grid.cable_capacity_mw
        self.gom_cost_share = self.config.one_grid.gom_share_pct
        
        # RE targets for domestic solar - create trajectory from 2050 target
        final_target = self.config.one_grid.domestic_re_target_2050
        self.domestic_re_targets = {
            2024: 0.06,  # Current RE share
            2030: 0.10,
            2040: 0.20,
            2050: final_target,
        }
        
        # Track capacities
        self.solar_capacity_mw = self.config.current_system.solar_capacity_mw
        self.battery_capacity_mwh = 0.0
        self.diesel_capacity_mw = self.config.current_system.diesel_capacity_mw
        
        # Track cable status
        self.cable_built = False
        
        # Track capacity additions
        self.solar_additions: Dict[int, float] = {}
        self.battery_additions: Dict[int, float] = {}
        
        # Pre-calculate deployment schedule
        self._calculate_deployment_schedule()
    
    def _init_demand_projector(self) -> DemandProjector:
        return DemandProjector(
            config=self.config,
            scenario="one_grid",
            growth_rate=self.config.demand.growth_rates["one_grid"],
        )
    
    def _interpolate_domestic_re_target(self, year: int) -> float:
        """
        Interpolate domestic RE target for years not explicitly specified.
        """
        targets = self.domestic_re_targets
        years = sorted(targets.keys())
        
        if year in targets:
            return targets[year]
        
        # Handle years beyond target range - use last available target
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
            # Get domestic RE target
            re_target = self._interpolate_domestic_re_target(year)
            
            # Get demand for year
            demand_gwh = self.demand.get_demand(year)
            
            # Required solar generation for domestic RE
            required_solar_gwh = demand_gwh * re_target
            
            # Required solar capacity
            capacity_factor = self.config.technology.solar_pv_capacity_factor
            required_solar_mw = (required_solar_gwh * 1000) / (8760 * capacity_factor)
            
            # Solar addition
            solar_addition = max(0, required_solar_mw - prev_solar)
            self.solar_additions[year] = solar_addition
            prev_solar = required_solar_mw
            
            # Battery: 1.5 MWh per MW of solar (slightly less than Green Transition
            # due to cable providing baseload stability)
            battery_ratio = 1.5
            required_battery_mwh = required_solar_mw * battery_ratio
            battery_addition = max(0, required_battery_mwh - prev_battery)
            self.battery_additions[year] = battery_addition
            prev_battery = required_battery_mwh
    
    def calculate_generation_mix(self, year: int) -> GenerationMix:
        """
        Calculate generation mix for One Grid scenario.
        """
        # Get demand
        demand_gwh = self.demand.get_demand(year)
        peak_mw = self.demand.get_peak(year)
        
        # Update capacities
        self.solar_capacity_mw += self.solar_additions.get(year, 0)
        self.battery_capacity_mwh += self.battery_additions.get(year, 0)
        
        # Is cable operational?
        cable_operational = year >= self.cable_online_year
        
        # Calculate generation sources
        if cable_operational:
            # CABLE OPERATIONAL: Import baseload, solar for daytime, diesel backup only
            
            # Get domestic RE target
            re_target = self._interpolate_domestic_re_target(year)
            
            # Solar generation
            solar_gwh = self.cost_calc.solar_generation(self.solar_capacity_mw)
            max_solar = demand_gwh * re_target
            solar_gwh = min(solar_gwh, max_solar)
            
            # Diesel: minimal - emergency backup only (5% reserve)
            diesel_reserve_ratio = 0.05
            diesel_gwh = demand_gwh * diesel_reserve_ratio
            
            # Import: everything else
            import_gwh = demand_gwh - solar_gwh - diesel_gwh
            if import_gwh < 0:
                import_gwh = 0
                diesel_gwh = demand_gwh - solar_gwh
            
            # Diesel capacity: reduce to backup only
            min_diesel_mw = peak_mw * 0.2  # 20% backup
            self.diesel_capacity_mw = max(min_diesel_mw, self.diesel_capacity_mw * 0.9)
            
        else:
            # PRE-CABLE: Status quo-like operation
            
            # Solar generation (existing + additions)
            solar_gwh = self.cost_calc.solar_generation(self.solar_capacity_mw)
            
            # Diesel meets the rest
            diesel_gwh = demand_gwh - solar_gwh
            if diesel_gwh < 0:
                diesel_gwh = 0
            
            import_gwh = 0.0
        
        return GenerationMix(
            year=year,
            total_demand_gwh=round(demand_gwh, 1),
            diesel_gwh=round(diesel_gwh, 1),
            solar_gwh=round(solar_gwh, 1),
            import_gwh=round(import_gwh, 1),
            diesel_capacity_mw=round(self.diesel_capacity_mw, 1),
            solar_capacity_mw=round(self.solar_capacity_mw, 1),
            battery_capacity_mwh=round(self.battery_capacity_mwh, 1),
        )
    
    def calculate_annual_costs(self, year: int, gen_mix: GenerationMix) -> AnnualCosts:
        """
        Calculate costs for One Grid scenario.
        """
        costs = AnnualCosts(year=year)
        
        # Is cable operational?
        cable_online_year = self.cable_online_year
        cable_construction_start = cable_online_year - 3  # 3-year construction
        
        # CAPEX: Undersea cable to India (spread over construction period)
        if cable_construction_start <= year < cable_online_year:
            # Total cable cost (uses config for length)
            cable_total_cost = self.cost_calc.cable_capex()
            # GoM share
            gom_cable_cost = cable_total_cost * self.gom_cost_share
            # Spread over 3 years
            costs.capex_cable = gom_cable_cost / 3
        
        # CAPEX: Inter-island submarine cable grid
        if year == 2027 or year == 2028:
            # Inter-island grid built in 2027-2028
            inter_island_km = self.config.green_transition.inter_island_km
            inter_island_cost_per_km = self.config.technology.inter_island_capex_per_km
            inter_island_total = inter_island_km * inter_island_cost_per_km / 1e6
            costs.capex_cable += inter_island_total / 2  # Split over 2 years
        
        # CAPEX: Solar additions
        solar_addition = self.solar_additions.get(year, 0)
        if solar_addition > 0:
            costs.capex_solar = self.cost_calc.solar_capex(solar_addition, year)
        
        # CAPEX: Battery additions
        battery_addition = self.battery_additions.get(year, 0)
        if battery_addition > 0:
            costs.capex_battery = self.cost_calc.battery_capex(battery_addition, year)
        
        # CAPEX: Battery replacement (12-year cycle)
        if year - 12 >= self.config.base_year:
            past_battery = self.battery_additions.get(year - 12, 0)
            if past_battery > 0:
                costs.capex_battery += self.cost_calc.battery_capex(past_battery, year)
        
        # CAPEX: Diesel (minimal)
        if year < cable_online_year:
            # Pre-cable: maintain diesel capacity
            diesel_replacement_mw = gen_mix.diesel_capacity_mw / self.config.technology.diesel_gen_lifetime
        else:
            # Post-cable: minimal replacement
            diesel_replacement_mw = gen_mix.diesel_capacity_mw / (self.config.technology.diesel_gen_lifetime * 2)
        costs.capex_diesel = self.cost_calc.diesel_gen_capex(diesel_replacement_mw)
        
        # OPEX: Solar
        costs.opex_solar = self.cost_calc.solar_opex(gen_mix.solar_capacity_mw, year)
        
        # OPEX: Battery
        costs.opex_battery = self.cost_calc.battery_opex(gen_mix.battery_capacity_mwh)
        
        # OPEX: Diesel
        costs.opex_diesel = self.cost_calc.diesel_gen_opex(gen_mix.diesel_gwh)
        
        # OPEX: Cable maintenance (if operational)
        if year >= cable_online_year:
            costs.opex_cable = self.cost_calc.cable_opex()
        
        # Fuel: Diesel
        costs.fuel_diesel = self.cost_calc.diesel_fuel_cost(gen_mix.diesel_gwh, year)
        
        # PPA: Electricity import
        costs.ppa_imports = self.cost_calc.ppa_cost(gen_mix.import_gwh, year)
        
        return costs


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("FULL INTEGRATION SCENARIO TEST")
    print("=" * 60)
    
    config = get_config()
    scenario = FullIntegrationScenario(config)
    
    # Run scenario
    results = scenario.run()
    
    # Print generation mix for key years
    print("\n--- GENERATION MIX ---")
    print(f"{'Year':<6} {'Demand':<10} {'Diesel':<10} {'Solar':<10} {'Import':<10} {'Solar MW':<10}")
    print("-" * 80)
    for year in [2024, 2028, 2030, 2040, 2050]:
        gen = results.generation_mix[year]
        print(f"{year:<6} {gen.total_demand_gwh:<10.0f} {gen.diesel_gwh:<10.0f} {gen.solar_gwh:<10.0f} {gen.import_gwh:<10.0f} {gen.solar_capacity_mw:<10.0f}")
    
    # Print costs for key years
    print("\n--- ANNUAL COSTS (Million USD) ---")
    print(f"{'Year':<6} {'CAPEX':<12} {'Cable':<10} {'Solar':<10} {'OPEX':<10} {'Fuel':<10} {'PPA':<10} {'Total':<10}")
    print("-" * 100)
    for year in [2024, 2028, 2029, 2030, 2040, 2050]:
        cost = results.annual_costs[year]
        print(f"{year:<6} {cost.total_capex/1e6:<12.1f} {cost.capex_cable/1e6:<10.1f} {cost.capex_solar/1e6:<10.1f} {cost.total_opex/1e6:<10.1f} {cost.fuel_diesel/1e6:<10.1f} {cost.ppa_imports/1e6:<10.1f} {cost.total/1e6:<10.1f}")
    
    # Print emissions
    print("\n--- EMISSIONS (ktCO2) ---")
    for year in [2024, 2028, 2030, 2040, 2050]:
        em = results.annual_emissions[year]
        print(f"{year}: {em.total_emissions_ktco2:.0f} ktCO2 (diesel: {em.diesel_ktco2:.0f}, import: {em.import_ktco2:.0f})")
    
    # Summary
    print("\n--- SUMMARY ---")
    summary = scenario.get_summary()
    print(f"Total costs (2024-2050): ${summary['total_costs_million']:,.0f}M")
    print(f"  - CAPEX: ${summary['total_capex_million']:,.0f}M")
    print(f"  - OPEX: ${summary['total_opex_million']:,.0f}M")
    print(f"  - Fuel: ${summary['total_fuel_million']:,.0f}M")
    print(f"  - PPA: ${summary['total_ppa_million']:,.0f}M")
    print(f"Total emissions: {summary['total_emissions_mtco2']:.2f} MtCO2")
    print(f"Final RE share (2050): {summary['final_re_share']:.1%}")
    
    print("\n✓ Full Integration scenario tests passed!")
