"""
National Grid Scenario
======================

Scenario 3: Green transition with inter-island Maldives grid, NO India connection.

Endogenous RE Deployment (LCOE-driven):
  Solar+battery LCOE ($0.166/kWh) < Diesel LCOE ($0.299/kWh) from day one.
  Optimal outer-island RE = 100% as fast as deployable.
  Binding constraint = deployment ramp (MW/year), not economics.

Two-Segment Generation Model:
  - OUTER ISLANDS (43% of demand): deploy solar+battery at max ramp rate
  - GREATER MALÉ (57% of demand): capped at ~4% RE (18 MWp rooftop solar)
  - National RE = weighted average → ceiling ~45%

Assumptions:
- Solar PV + battery deployment on outer islands at ramp-constrained rate
- Malé limited to rooftop solar (ZNES Flensburg: 18 MWp)
- Inter-island submarine cable for 3 near-hub islands (~14 km)
- Diesel backup for residual demand (especially Malé)
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
    
    Uses a two-segment model reflecting island-level solar land constraints:
    - Outer islands (43% demand): unconstrained, ramp to 100% RE
    - Greater Malé (57% demand): land-constrained, max ~4% RE (rooftop only)
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
        
        # Two-segment RE model — endogenous deployment
        # Deployment ramp: max MW of solar added per year (logistics constraint)
        self.ramp_mw_yr = self.config.green_transition.deployment_ramp_mw_per_year
        # Malé is land-constrained
        self.male_max_re = self.config.green_transition.male_max_re_share
        # D60: Density-constrained demand share — base year value stored,
        # but actual share computed per-year via config.male_demand_share()
        self.male_demand_share_base = self.config.current_system.male_electricity_share
        self._scenario_growth_rate = self.config.demand.growth_rates["green_transition"]
        
        # Track installed capacities (L19: init from config, not hardcoded 0)
        self.solar_capacity_mw = self.config.current_system.solar_capacity_mw
        self.battery_capacity_mwh = self.config.current_system.battery_capacity_mwh
        self.diesel_capacity_mw = self.config.current_system.diesel_capacity_mw
        
        # Malé rooftop solar (fixed cap from config)
        self.male_solar_cap_mw = self.config.current_system.male_rooftop_solar_mwp
        
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
    
    def _calculate_deployment_schedule(self) -> None:
        """
        Endogenous deployment: add solar at max ramp rate each year.
        
        Solar+battery LCOE < diesel LCOE from day one, so the economic optimum
        is 100% outer-island RE as fast as physically deployable. The binding
        constraint is the deployment ramp (MW/year), not economics.
        
        Two segments:
        - Outer islands: deploy at ramp_mw_yr until 100% of outer demand served
        - Malé: rooftop solar fixed at male_solar_cap_mw (no additional ground-mount)
        Total solar = outer solar + Malé rooftop
        
        Uses effective CF (raw CF × temp derating) for sizing, so installed
        capacity actually meets demand after temperature losses.
        
        Note: sizes solar against gross demand (incl. distribution losses) to
        match what calculate_generation_mix() uses.
        """
        # LW-01: Use base class precomputed effective CF (temp-derated)
        effective_cf = self._effective_solar_cf
        
        # MR-09: Distribution loss computed per year using weighted_distribution_loss()
        # (previously used flat distribution_loss_pct)
        
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
            
            # Get outer-island demand for this year (gross of T&D losses)
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
            
            # Battery: ratio from config (battery only on outer islands, not Malé)
            required_battery_mwh = new_outer_solar_mw * self.config.green_transition.battery_ratio
            battery_addition = max(0, required_battery_mwh - prev_battery)
            self.battery_additions[year] = battery_addition
            prev_battery = required_battery_mwh
    
    def _get_national_re_target(self, year: int) -> float:
        """
        Compute national RE as weighted average of two segments.
        Outer-island RE is computed endogenously in _calculate_deployment_schedule.
        D60: Uses time-varying Malé demand share (density-constrained).
        
        national_re = outer_share(t) × outer_re + male_share(t) × male_re
        """
        outer_re = self._outer_re_by_year.get(year, 0.0)
        male_share = self._male_share_by_year.get(year, self.male_demand_share_base)
        outer_share = self._outer_share_by_year.get(year, 1.0 - self.male_demand_share_base)
        national_re = (outer_share * outer_re 
                       + male_share * self.male_max_re)
        return national_re
    
    def calculate_generation_mix(self, year: int) -> GenerationMix:
        """
        Calculate generation mix for Green Transition.
        
        Two-segment model:
        - National RE = weighted avg of outer-island RE + Malé RE (~4%)
        - Solar generation split: outer islands (unconstrained) + Malé (capped)
        - Diesel covers all remaining demand (especially Malé)
        """
        # Get demand for year
        net_demand_gwh = self.demand.get_demand(year)
        peak_mw = self.demand.get_peak(year)
        
        # C2+R5: Gross up for distribution losses (segmented Malé 8% / outer 12%)
        demand_gwh = self.cost_calc.gross_up_for_losses(
            net_demand_gwh, include_distribution=True, include_hvdc=False,
            year=year, scenario_growth_rate=self._scenario_growth_rate,
        )
        
        # Get national RE target (weighted average of two segments)
        re_target = self._get_national_re_target(year)
        
        # Update installed capacities
        self.solar_capacity_mw += self.solar_additions.get(year, 0)
        self.battery_capacity_mwh += self.battery_additions.get(year, 0)
        
        # Solar generation with vintage-based degradation (C7, C8)
        # Each cohort of panels degrades from its actual install year,
        # not from base_year. Prevents over-degrading newer vintages.
        solar_gwh = self.cost_calc.solar_generation_vintaged(
            solar_additions=self.solar_additions,
            year=year,
            existing_mw=self._existing_outer_solar_mw + self.male_solar_cap_mw,
        )
        
        # Cap solar at national RE target
        max_solar_gwh = demand_gwh * re_target
        solar_gwh = min(solar_gwh, max_solar_gwh)
        
        # R6: Waste-to-energy baseload (Thilafushi 12 + Addu 1.5 + Vandhoo 0.5 = 14 MW)
        wte_gwh = 0.0
        if year >= self.config.wte.online_year:
            wte_gwh = min(self.config.wte.annual_generation_gwh, max(0, demand_gwh - solar_gwh))
        
        # Diesel meets the rest after solar + WTE
        diesel_gwh = demand_gwh - solar_gwh - wte_gwh
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
            wte_gwh=round(wte_gwh, 1),
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
        
        # Fuel: Diesel (C9: two-part fuel curve, reduced)
        costs.fuel_diesel = self.cost_calc.diesel_fuel_cost(
            gen_mix.diesel_gwh, year,
            diesel_capacity_mw=gen_mix.diesel_capacity_mw
        )
        
        # R6: WTE CAPEX (one-time at online year) + annual OPEX
        if year == self.config.wte.online_year:
            costs.capex_wte = self.config.wte.total_capex * (1 + self.config.technology.climate_adaptation_premium)
        if (year >= self.config.wte.online_year
                and year < self.config.wte.online_year + self.config.wte.plant_lifetime):
            costs.opex_wte = self.config.wte.annual_opex
        
        # L11: Connection costs (phased rollout)
        conn_cfg = self.config.connection
        conn_start = self.config.base_year + 1  # Start year after base
        conn_end = conn_start + conn_cfg.rollout_years - 1
        if conn_start <= year <= conn_end:
            annual_hh = conn_cfg.number_of_households / conn_cfg.rollout_years
            costs.capex_connection = self.cost_calc.connection_capex(int(annual_hh))
        
        return costs


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    config = get_config()
    scenario = NationalGridScenario(config)
    
    print("=" * 60)
    print("NATIONAL GRID SCENARIO TEST")
    print("  Endogenous RE: LCOE-driven + deployment ramp constraint")
    print(f"  Deployment ramp: {scenario.ramp_mw_yr} MW/yr")
    print(f"  Malé demand share (base): {scenario.male_demand_share_base:.0%}")
    print(f"  Malé max RE: {scenario.male_max_re:.0%}")
    print(f"  National RE ceiling (base year): {(1.0 - scenario.male_demand_share_base) * 1.0 + scenario.male_demand_share_base * scenario.male_max_re:.1%}")
    print("=" * 60)
    
    # Run scenario
    results = scenario.run()
    
    # Print generation mix for key years
    print("\n--- GENERATION MIX ---")
    print(f"{'Year':<6} {'Demand':<10} {'Diesel':<10} {'Solar':<10} {'RE %':<10} {'Solar MW':<10} {'Battery MWh':<12}")
    print("-" * 80)
    key_years = [config.base_year, 2028, 2030, 2040, config.end_year]
    for year in key_years:
        gen = results.generation_mix[year]
        print(f"{year:<6} {gen.total_demand_gwh:<10.0f} {gen.diesel_gwh:<10.0f} {gen.solar_gwh:<10.0f} {gen.re_share:<10.1%} {gen.solar_capacity_mw:<10.0f} {gen.battery_capacity_mwh:<12.0f}")
    
    # Print costs for key years
    print("\n--- ANNUAL COSTS (Million USD) ---")
    print(f"{'Year':<6} {'CAPEX':<12} {'Solar':<10} {'Battery':<10} {'OPEX':<10} {'Fuel':<12} {'Total':<10}")
    print("-" * 80)
    for year in key_years:
        cost = results.annual_costs[year]
        print(f"{year:<6} {cost.total_capex/1e6:<12.1f} {cost.capex_solar/1e6:<10.1f} {cost.capex_battery/1e6:<10.1f} {cost.total_opex/1e6:<10.1f} {cost.fuel_diesel/1e6:<12.1f} {cost.total/1e6:<10.1f}")
    
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
    
    print("\n✓ National Grid scenario tests passed!")
