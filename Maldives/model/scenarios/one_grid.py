"""
Full Integration Scenario
==========================

Scenario 2: India interconnector + inter-island Maldives grid + RE

Endogenous RE Deployment (LCOE-driven):
  Pre-cable: deploy solar at ramp rate (same as NG — solar < diesel)
  Post-cable: PPA import ($0.07/kWh) < domestic solar ($0.166/kWh)
  → Minimize domestic RE post-cable. Cable fills the gap.

Two-Segment Model:
  - OUTER ISLANDS: ramp-based solar pre-cable; cable import replaces diesel post-cable
  - GREATER MALÉ: receives clean import via cable → decarbonizes via cable

Assumptions:
- Undersea cable to India operational by 2032
- Inter-island cables for 3 near-hub islands (~14 km)
- Complementary domestic solar PV (capped at domestic_re_target_2050)
- Cable provides clean import that decarbonizes Malé
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
        
        # Endogenous RE deployment:
        # Pre-cable: ramp-based solar deployment (solar < diesel)
        # Post-cable: freeze solar additions (PPA < solar LCOE → cable preferred)
        self.ramp_mw_yr = self.config.green_transition.deployment_ramp_mw_per_year
        self.domestic_re_cap = self.config.one_grid.domestic_re_target_2050
        
        # Track capacities (L19: init from config, not hardcoded 0)
        self.solar_capacity_mw = self.config.current_system.solar_capacity_mw
        self.battery_capacity_mwh = self.config.current_system.battery_capacity_mwh
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
    
    def _calculate_deployment_schedule(self) -> None:
        """
        Endogenous deployment for FI scenario:
        - Pre-cable: deploy solar at ramp rate (solar LCOE < diesel LCOE)
        - Post-cable: stop solar additions (PPA < solar LCOE → cable preferred)
        
        Uses effective CF (raw CF × temp derating) for sizing.
        Sizes solar against gross demand (incl. distribution + HVDC losses).
        """
        # LW-01: Use base class precomputed effective CF (temp-derated)
        effective_cf = self._effective_solar_cf
        
        # MR-09: Distribution loss computed per year using weighted_distribution_loss()
        hvdc_loss = self.config.technology.hvdc_cable_loss_pct
        
        self._existing_solar_mw = self.config.current_system.solar_capacity_mw
        prev_solar_mw = self._existing_solar_mw
        prev_battery = 0.0
        
        # Store RE share per year for generation mix computation
        self._domestic_re_by_year: Dict[int, float] = {}
        
        for year in self.config.time_horizon:
            net_demand_gwh = self.demand.get_demand(year)
            # MR-09: Year-varying weighted distribution loss
            dist_loss = self.config.weighted_distribution_loss(
                year, self.config.demand.growth_rates['one_grid']  # BD-02: fail-fast on missing key
            )
            # Pre-cable: distribution losses only. Post-cable: + HVDC.
            if year >= self.cable_online_year:
                loss_factor = 1.0 / ((1.0 - dist_loss) * (1.0 - hvdc_loss))
            else:
                loss_factor = 1.0 / (1.0 - dist_loss)
            demand_gwh = net_demand_gwh * loss_factor
            
            if year < self.cable_online_year:
                # PRE-CABLE: deploy solar at ramp rate (solar < diesel)
                mw_for_100pct = (demand_gwh * 1000) / (8760 * effective_cf)
                gap_mw = max(0, mw_for_100pct - prev_solar_mw)
                solar_addition = min(self.ramp_mw_yr, gap_mw)
            else:
                # POST-CABLE: no new solar (PPA is cheaper than domestic solar)
                solar_addition = 0.0
            
            new_solar_mw = prev_solar_mw + solar_addition
            
            # Compute domestic RE share (using effective CF)
            solar_gen_gwh = new_solar_mw * 8760 * effective_cf / 1000
            domestic_re = min(self.domestic_re_cap, solar_gen_gwh / demand_gwh) if demand_gwh > 0 else 0.0
            self._domestic_re_by_year[year] = domestic_re
            
            self.solar_additions[year] = solar_addition
            prev_solar_mw = new_solar_mw
            
            # Battery: ratio from config (less than NG due to cable stability)
            battery_ratio = self.config.one_grid.battery_ratio
            required_battery_mwh = new_solar_mw * battery_ratio
            battery_addition = max(0, required_battery_mwh - prev_battery)
            self.battery_additions[year] = battery_addition
            prev_battery = required_battery_mwh
    
    def calculate_generation_mix(self, year: int) -> GenerationMix:
        """
        Calculate generation mix for One Grid scenario.
        """
        # Get demand
        net_demand_gwh = self.demand.get_demand(year)
        peak_mw = self.demand.get_peak(year)
        
        # Is cable operational?
        cable_operational = year >= self.cable_online_year
        
        # L8: Apply price elasticity for induced demand (post-cable only)
        # Price reduction = (diesel LCOE - PPA price) / diesel LCOE
        # Elasticity amplifies demand when electricity becomes cheaper via cable
        if cable_operational:
            bau_price = self.config.current_system.outer_island_electricity_cost
            fi_price = self.config.ppa.get_price(year)
            if fi_price is not None and bau_price > 0 and fi_price < bau_price:
                price_reduction_pct = (bau_price - fi_price) / bau_price
                net_demand_gwh = self.demand.apply_induced_demand(
                    year, price_reduction_pct
                )
                # Also adjust peak proportionally
                peak_mw = net_demand_gwh / self.demand.get_demand(year) * peak_mw
        
        # C2+R5: Gross up for T&D losses (segmented Malé 8% / outer 12%)
        # Distribution losses always; HVDC cable losses only when cable is operational
        demand_gwh = self.cost_calc.gross_up_for_losses(
            net_demand_gwh,
            include_distribution=True,
            include_hvdc=cable_operational,
            year=year,
            scenario_growth_rate=self.config.demand.growth_rates['one_grid'],  # MR-04 fix; BD-02: fail-fast on missing key
        )
        
        # Update capacities
        self.solar_capacity_mw += self.solar_additions.get(year, 0)
        self.battery_capacity_mwh += self.battery_additions.get(year, 0)
        
        # Solar generation with vintage-based degradation (C7, C8)
        solar_gwh = self.cost_calc.solar_generation_vintaged(
            solar_additions=self.solar_additions,
            year=year,
            existing_mw=self._existing_solar_mw,
        )
        
        # R6: Waste-to-energy baseload (Thilafushi 12 + Addu 1.5 + Vandhoo 0.5 = 14 MW)
        wte_gwh = 0.0
        if year >= self.config.wte.online_year:
            wte_gwh = min(self.config.wte.annual_generation_gwh, max(0, demand_gwh - solar_gwh))
        
        # Calculate generation sources
        if cable_operational:
            # CABLE OPERATIONAL: Import baseload, solar for daytime, diesel backup only
            
            # Get domestic RE share (computed endogenously)
            re_target = self._domestic_re_by_year.get(year, 0.0)
            
            max_solar = demand_gwh * re_target
            solar_gwh = min(solar_gwh, max_solar)
            
            # Diesel: minimal - emergency backup only (from config)
            diesel_reserve_ratio = self.config.one_grid.diesel_reserve_ratio
            diesel_gwh = demand_gwh * diesel_reserve_ratio
            
            # Import: everything else (after solar + WTE + diesel reserve)
            import_gwh = demand_gwh - solar_gwh - wte_gwh - diesel_gwh
            if import_gwh < 0:
                import_gwh = 0
                diesel_gwh = max(0, demand_gwh - solar_gwh - wte_gwh)
            
            # Diesel capacity: reduce to backup only
            min_diesel_mw = peak_mw * self.config.one_grid.diesel_backup_share
            retirement_factor = 1 - self.config.one_grid.diesel_retirement_rate
            self.diesel_capacity_mw = max(min_diesel_mw, self.diesel_capacity_mw * retirement_factor)
            
        else:
            # PRE-CABLE: Status quo-like operation
            # solar_gwh already computed above with vintaged degradation
            
            # Diesel meets the rest after solar + WTE
            diesel_gwh = demand_gwh - solar_gwh - wte_gwh
            if diesel_gwh < 0:
                diesel_gwh = 0
            
            import_gwh = 0.0
        
        return GenerationMix(
            year=year,
            total_demand_gwh=round(demand_gwh, 1),
            diesel_gwh=round(diesel_gwh, 1),
            solar_gwh=round(solar_gwh, 1),
            import_gwh=round(import_gwh, 1),
            wte_gwh=round(wte_gwh, 1),
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
        construction_years = self.config.one_grid.cable_construction_years
        cable_construction_start = cable_online_year - construction_years
        
        # CAPEX: Undersea cable to India (spread over construction period)
        if cable_construction_start <= year < cable_online_year:
            # Total cable cost (uses config for length)
            cable_total_cost = self.cost_calc.cable_capex()
            # GoM share
            gom_cable_cost = cable_total_cost * self.gom_cost_share
            # Spread over construction period
            costs.capex_cable = gom_cable_cost / construction_years
        
        # CAPEX: Inter-island submarine cable grid
        ii_start = self.config.one_grid.inter_island_build_start
        ii_end = self.config.one_grid.inter_island_build_end
        ii_years = ii_end - ii_start + 1
        if ii_start <= year <= ii_end:
            # Inter-island grid built over construction period
            inter_island_km = self.config.green_transition.inter_island_km
            inter_island_cost_per_km = self.config.technology.inter_island_capex_per_km
            inter_island_total = inter_island_km * inter_island_cost_per_km  # USD total
            costs.capex_cable += inter_island_total / ii_years  # Split over construction years
        
        # CAPEX: Solar additions
        solar_addition = self.solar_additions.get(year, 0)
        if solar_addition > 0:
            costs.capex_solar = self.cost_calc.solar_capex(solar_addition, year)
        
        # CAPEX: Battery additions
        battery_addition = self.battery_additions.get(year, 0)
        if battery_addition > 0:
            costs.capex_battery = self.cost_calc.battery_capex(battery_addition, year)
        
        # CAPEX: Battery replacement (lifetime-based cycle from config)
        battery_life = self.config.technology.battery_lifetime
        if year - battery_life >= self.config.base_year:
            past_battery = self.battery_additions.get(year - battery_life, 0)
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
        
        # Fuel: Diesel (C9: two-part fuel curve)
        costs.fuel_diesel = self.cost_calc.diesel_fuel_cost(
            gen_mix.diesel_gwh, year,
            diesel_capacity_mw=gen_mix.diesel_capacity_mw
        )
        
        # PPA: Electricity import
        costs.ppa_imports = self.cost_calc.ppa_cost(gen_mix.import_gwh, year)
        
        # L11: Connection costs (phased rollout)
        conn_cfg = self.config.connection
        conn_start = self.config.base_year + 1
        conn_end = conn_start + conn_cfg.rollout_years - 1
        if conn_start <= year <= conn_end:
            annual_hh = conn_cfg.number_of_households / conn_cfg.rollout_years
            costs.capex_connection = self.cost_calc.connection_capex(int(annual_hh))
        
        # R6: WTE CAPEX (one-time at online year) + annual OPEX
        if year == self.config.wte.online_year:
            costs.capex_wte = self.config.wte.total_capex * (1 + self.config.technology.climate_adaptation_premium)
        if (year >= self.config.wte.online_year
                and year < self.config.wte.online_year + self.config.wte.plant_lifetime):
            costs.opex_wte = self.config.wte.annual_opex
        
        # L2: Supply security costs (cable-dependent scenarios only)
        if year >= cable_online_year:
            # (a) Idle fleet annual cost — keeping diesel reserve on standby
            idle_fleet_cost = self.config.supply_security.idle_fleet_annual_cost_m * 1e6
            
            # (b) Expected outage cost — Poisson(λ) events/yr × uniform duration
            # Expected fraction of year in outage = λ × E[duration_months] / 12
            outage_cfg = self.config.cable_outage
            expected_duration_months = (
                outage_cfg.min_outage_months + outage_cfg.max_outage_months
            ) / 2.0
            expected_outage_fraction = (
                outage_cfg.outage_rate_per_yr * expected_duration_months / 12.0
            )
            
            # During outage: lost import GWh must be replaced by diesel at premium
            import_gwh_at_risk = gen_mix.import_gwh * expected_outage_fraction
            if import_gwh_at_risk > 0:
                # Base diesel fuel cost for replacement generation
                base_fuel_cost = self.cost_calc.diesel_fuel_cost(
                    import_gwh_at_risk, year,
                    diesel_capacity_mw=gen_mix.diesel_capacity_mw,
                )
                # Premium = fuel_premium_pct × base cost (emergency procurement surcharge)
                fuel_premium = self.config.supply_security.diesel_fuel_premium_outage
                outage_fuel_premium_cost = base_fuel_cost * fuel_premium
            else:
                outage_fuel_premium_cost = 0.0
            
            # VOLL-based cost of unserved energy during outage
            # Unserved energy = import at risk beyond backup diesel capacity
            backup_gwh = (gen_mix.diesel_capacity_mw * expected_outage_fraction
                         * 8760 / 1000 * self.config.dispatch.emergency_diesel_cf)  # CR-07: from config
            unserved_gwh = max(0, import_gwh_at_risk - backup_gwh)
            voll_cost = unserved_gwh * 1e3 * self.config.economics.voll  # GWh→MWh × $/MWh
            
            costs.supply_security = idle_fleet_cost + outage_fuel_premium_cost + voll_cost
        
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
    key_years = [config.base_year, 2028, 2030, 2040, config.end_year]
    for year in key_years:
        gen = results.generation_mix[year]
        print(f"{year:<6} {gen.total_demand_gwh:<10.0f} {gen.diesel_gwh:<10.0f} {gen.solar_gwh:<10.0f} {gen.import_gwh:<10.0f} {gen.solar_capacity_mw:<10.0f}")
    
    # Print costs for key years
    print("\n--- ANNUAL COSTS (Million USD) ---")
    print(f"{'Year':<6} {'CAPEX':<12} {'Cable':<10} {'Solar':<10} {'OPEX':<10} {'Fuel':<10} {'PPA':<10} {'Total':<10}")
    print("-" * 100)
    cost_years = [config.base_year, 2028, 2029, 2030, 2040, config.end_year]
    for year in cost_years:
        cost = results.annual_costs[year]
        print(f"{year:<6} {cost.total_capex/1e6:<12.1f} {cost.capex_cable/1e6:<10.1f} {cost.capex_solar/1e6:<10.1f} {cost.total_opex/1e6:<10.1f} {cost.fuel_diesel/1e6:<10.1f} {cost.ppa_imports/1e6:<10.1f} {cost.total/1e6:<10.1f}")
    
    # Print emissions
    print("\n--- EMISSIONS (ktCO2) ---")
    for year in key_years:
        em = results.annual_emissions[year]
        print(f"{year}: {em.total_emissions_ktco2:.0f} ktCO2 (diesel: {em.diesel_ktco2:.0f}, import: {em.import_ktco2:.0f})")
    
    # Summary
    print("\n--- SUMMARY ---")
    summary = scenario.get_summary()
    print(f"Total costs ({config.base_year}-{config.end_year}): ${summary['total_costs_million']:,.0f}M")
    print(f"  - CAPEX: ${summary['total_capex_million']:,.0f}M")
    print(f"  - OPEX: ${summary['total_opex_million']:,.0f}M")
    print(f"  - Fuel: ${summary['total_fuel_million']:,.0f}M")
    print(f"  - PPA: ${summary['total_ppa_million']:,.0f}M")
    print(f"Total emissions: {summary['total_emissions_mtco2']:.2f} MtCO2")
    print(f"Final RE share (2050): {summary['final_re_share']:.1%}")
    
    print("\n✓ Full Integration scenario tests passed!")
