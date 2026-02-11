"""
Status Quo / BAU Scenario
=========================

Scenario 1: Business-as-usual with minimal RE growth

Current State (2024):
- ~93% diesel, ~7% solar (68.5 MW installed)
- ~600 MW total capacity
- Some battery storage (~20 MWh)
- POISED hybrid projects reducing diesel on select islands

BAU Assumptions:
- Existing solar maintained but minimal new additions
- Diesel generator replacement as needed
- No inter-island grid development
- Full exposure to fuel price volatility
- RE share stays ~7-10% through 2050
"""

from typing import Dict
import numpy as np

from ..config import Config, get_config
from ..demand import DemandProjector
from ..costs import CostCalculator, AnnualCosts
from . import BaseScenario, GenerationMix


class StatusQuoScenario(BaseScenario):
    """
    BAU/Status Quo: Business-as-usual with minimal RE growth.
    Maintains ~7% solar share, diesel meets demand growth.
    """
    
    def __init__(self, config: Config = None):
        config = config or get_config()
        super().__init__(
            name="BAU (Diesel)",
            description="Minimal RE growth (~7% solar maintained), diesel-dominated",
            config=config,
        )
        
        # Initialize demand projector with status quo growth rate
        self.demand = self._init_demand_projector()
        
        # Fixed RE capacity (existing solar, no additions)
        self.existing_solar_mw = self.config.current_system.solar_capacity_mw
        
        # Track diesel capacity and replacement schedule
        self.diesel_capacity_mw = self.config.current_system.diesel_capacity_mw
        self._replacement_years = self._calculate_replacement_schedule()
    
    def _init_demand_projector(self) -> DemandProjector:
        return DemandProjector(
            config=self.config,
            scenario="status_quo",
            growth_rate=self.config.demand.growth_rates["status_quo"],
        )
    
    def _calculate_replacement_schedule(self) -> Dict[int, float]:
        """
        Calculate when diesel generators need replacement.
        
        Assumes capacity is replaced incrementally over lifetime.
        """
        schedule = {}
        lifetime = self.config.technology.diesel_gen_lifetime
        
        # Assume 1/lifetime of capacity replaced each year (rolling replacement)
        annual_replacement = self.diesel_capacity_mw / lifetime
        
        for year in self.config.time_horizon:
            schedule[year] = annual_replacement
        
        return schedule
    
    def calculate_generation_mix(self, year: int) -> GenerationMix:
        """
        Calculate generation mix for Status Quo.
        
        Solar stays flat, diesel meets all demand growth.
        """
        # Get demand for year
        net_demand_gwh = self.demand.get_demand(year)
        peak_mw = self.demand.get_peak(year)
        
        # C2+R5: Gross up for distribution losses (segmented Malé 8% / outer 12%)
        demand_gwh = self.cost_calc.gross_up_for_losses(
            net_demand_gwh, include_distribution=True, include_hvdc=False,
            year=year,
            scenario_growth_rate=self.config.demand.growth_rates['status_quo'],  # MR-04 fix; BD-02: fail-fast on missing key
        )
        
        # Solar generation with temp derating + degradation (C7, C8)
        solar_gwh = self.cost_calc.solar_generation(
            self.existing_solar_mw, year=year
        )
        
        # Diesel meets the rest
        diesel_gwh = demand_gwh - solar_gwh
        if diesel_gwh < 0:
            diesel_gwh = 0
            solar_gwh = demand_gwh  # Curtail solar if somehow exceeds demand
        
        # Capacity: diesel must meet peak demand with reserve margin
        reserve_margin = 1 + self.config.technology.reserve_margin
        solar_peak_contrib = self.config.technology.solar_peak_contribution
        required_diesel_mw = peak_mw * reserve_margin - self.existing_solar_mw * solar_peak_contrib
        
        # Expand diesel capacity if needed
        if required_diesel_mw > self.diesel_capacity_mw:
            self.diesel_capacity_mw = required_diesel_mw
        
        return GenerationMix(
            year=year,
            total_demand_gwh=demand_gwh,
            diesel_gwh=round(diesel_gwh, 1),
            solar_gwh=round(solar_gwh, 1),
            import_gwh=0.0,
            diesel_capacity_mw=round(self.diesel_capacity_mw, 1),
            solar_capacity_mw=self.existing_solar_mw,
            battery_capacity_mwh=self.config.current_system.battery_capacity_mwh,  # L19: from config
        )
    
    def calculate_annual_costs(self, year: int, gen_mix: GenerationMix) -> AnnualCosts:
        """
        Calculate costs for Status Quo scenario.
        """
        costs = AnnualCosts(year=year)
        
        # CAPEX: Diesel replacement (rolling)
        replacement_mw = self._replacement_years.get(year, 0)
        costs.capex_diesel = self.cost_calc.diesel_gen_capex(replacement_mw)
        
        # CAPEX: Additional capacity if peak demand grows beyond existing
        years_elapsed = year - self.config.base_year
        if years_elapsed > 0:
            prev_peak = self.demand.get_peak(year - 1)
            curr_peak = self.demand.get_peak(year)
            peak_growth = max(0, curr_peak - prev_peak)
            costs.capex_diesel += self.cost_calc.diesel_gen_capex(peak_growth)
        
        # OPEX: Diesel O&M (variable)
        costs.opex_diesel = self.cost_calc.diesel_gen_opex(gen_mix.diesel_gwh)
        
        # OPEX: Solar (minimal)
        costs.opex_solar = self.cost_calc.solar_opex(self.existing_solar_mw, year)
        
        # Fuel: Diesel (C9: two-part fuel curve)
        costs.fuel_diesel = self.cost_calc.diesel_fuel_cost(
            gen_mix.diesel_gwh, year,
            diesel_capacity_mw=gen_mix.diesel_capacity_mw
        )
        
        return costs


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("STATUS QUO SCENARIO TEST")
    print("=" * 60)
    
    config = get_config()
    scenario = StatusQuoScenario(config)
    
    # Run scenario
    results = scenario.run()
    
    # Print generation mix for key years
    print("\n--- GENERATION MIX ---")
    print(f"{'Year':<6} {'Demand':<10} {'Diesel':<10} {'Solar':<10} {'Diesel %':<10}")
    print("-" * 50)
    key_years = [config.base_year, 2030, 2040, config.end_year]
    for year in key_years:
        gen = results.generation_mix[year]
        print(f"{year:<6} {gen.total_demand_gwh:<10.0f} {gen.diesel_gwh:<10.0f} {gen.solar_gwh:<10.0f} {gen.diesel_share:<10.1%}")
    
    # Print costs for key years
    print("\n--- ANNUAL COSTS (Million USD) ---")
    print(f"{'Year':<6} {'CAPEX':<10} {'OPEX':<10} {'Fuel':<12} {'Total':<10}")
    print("-" * 50)
    for year in key_years:
        cost = results.annual_costs[year]
        print(f"{year:<6} {cost.total_capex/1e6:<10.1f} {cost.total_opex/1e6:<10.1f} {cost.fuel_diesel/1e6:<12.1f} {cost.total/1e6:<10.1f}")
    
    # Print emissions
    print("\n--- EMISSIONS (ktCO2) ---")
    for year in key_years:
        em = results.annual_emissions[year]
        print(f"{year}: {em.total_emissions_ktco2:.0f} ktCO2")
    
    # Summary
    print("\n--- SUMMARY ---")
    summary = scenario.get_summary()
    print(f"Total costs ({config.base_year}-{config.end_year}): ${summary['total_costs_million']:,.0f}M")
    print(f"  - CAPEX: ${summary['total_capex_million']:,.0f}M")
    print(f"  - OPEX: ${summary['total_opex_million']:,.0f}M")
    print(f"  - Fuel: ${summary['total_fuel_million']:,.0f}M")
    print(f"Total emissions: {summary['total_emissions_mtco2']:.2f} MtCO2")
    print(f"Final RE share (2050): {summary['final_re_share']:.1%}")
    
    print("\n✓ Status Quo scenario tests passed!")
