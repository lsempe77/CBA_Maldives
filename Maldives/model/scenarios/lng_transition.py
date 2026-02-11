"""
LNG Transition Scenario
========================

Scenario 7: Gulhifalhu LNG terminal replaces diesel for Greater Malé.
Outer islands follow same solar+battery path as National Grid (S3).

R9 — Roadmap Calibration Task.

Two-Segment Generation Model:
  - OUTER ISLANDS (declining share of demand): deploy solar+battery at max
    ramp rate, identical to National Grid (S3).
  - GREATER MALÉ (growing share): diesel until LNG online (2031), then LNG
    baseload with 18 MWp rooftop solar (~4% RE for Malé).
  - National RE = weighted average of outer RE + Malé RE (~4%).

Key Differences from National Grid (S3):
  - Malé fuel: diesel → LNG (cleaner, cheaper than diesel, but not RE)
  - LNG emission factor: 0.40 vs diesel 0.72 kgCO₂/kWh (−44%)
  - LNG fuel cost: ~$70/MWh vs diesel ~$85/MWh → lower total costs
  - LNG CAPEX: $168M one-time (140 MW × $1.2M/MW)
  - National RE ceiling: same as S3 (~50%) — Malé RE still capped at 4%
  - Bridge scenario: LNG buys time while outer islands ramp RE

Assumptions:
  - Solar PV + battery deployment on outer islands at ramp-constrained rate
  - Malé limited to rooftop solar (ZNES Flensburg: 18 MWp)
  - Inter-island submarine cable for 3 near-hub islands (~14 km)
  - LNG replaces diesel for Malé baseload from online_year (2031)
  - Pre-LNG: Malé continues with diesel
  - Diesel backup for reliability (20% of peak)

Sources:
  - GoM Energy Roadmap 2024-2033 (LNG flagship intervention)
  - ADB/Mahurkar LNG Prefeasibility 2023
  - IEA Gas Market Report 2024
  - IPCC 2006 Vol.2 Ch.2 (natural gas emission factor)
"""

from typing import Dict
import numpy as np

from ..config import Config, get_config
from ..demand import DemandProjector
from ..costs import CostCalculator, AnnualCosts
from . import BaseScenario, GenerationMix


class LNGTransitionScenario(BaseScenario):
    """
    LNG Transition: Malé switches from diesel to LNG; outer islands go RE.
    
    Uses a two-segment model identical to National Grid for outer islands,
    but replaces diesel with LNG for Greater Malé once the terminal is online.
    """
    
    def __init__(self, config: Config = None):
        config = config or get_config()
        super().__init__(
            name="LNG Transition",
            description="LNG for Malé + RE on outer islands",
            config=config,
        )
        
        # Initialize demand projector with LNG transition growth rate (5%)
        # E-CR-01 fix: was incorrectly using green_transition (4%)
        self.demand = self._init_demand_projector()
        
        # LNG parameters from config
        self.lng_capacity_mw = self.config.lng.plant_capacity_mw
        self.lng_online_year = self.config.lng.online_year
        self.lng_capex_total = (
            self.config.lng.plant_capacity_mw * self.config.lng.capex_per_mw
        )
        self.lng_emission_factor = self.config.lng.emission_factor
        self.lng_capacity_factor = self.config.lng.capacity_factor
        
        # Two-segment RE model — same as NG for outer islands
        self.ramp_mw_yr = self.config.green_transition.deployment_ramp_mw_per_year
        self.male_max_re = self.config.green_transition.male_max_re_share
        self.male_demand_share_base = self.config.current_system.male_electricity_share
        self._scenario_growth_rate = self.config.demand.growth_rates["lng_transition"]
        
        # Track installed capacities (from config, not hardcoded)
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
        
        # LNG terminal built flag
        self.lng_built = False
        
        # Pre-calculate deployment schedule (same as NG for outer islands)
        self._calculate_deployment_schedule()
    
    def _init_demand_projector(self) -> DemandProjector:
        return DemandProjector(
            config=self.config,
            scenario="lng_transition",
            growth_rate=self.config.demand.growth_rates["lng_transition"],
        )
    
    def _calculate_deployment_schedule(self) -> None:
        """
        Endogenous deployment: identical to National Grid for outer islands.
        
        Solar+battery LCOE < diesel LCOE from day one, so the economic optimum
        is 100% outer-island RE as fast as physically deployable.
        
        Two segments:
        - Outer islands: deploy at ramp_mw_yr until 100% of outer demand served
        - Malé: rooftop solar fixed at male_solar_cap_mw (18 MWp)
        
        Uses effective CF (raw CF × temp derating) for sizing.
        """
        # LW-01: Use base class precomputed effective CF (temp-derated)
        effective_cf = self._effective_solar_cf
        
        # MR-09: Distribution loss computed per year using weighted_distribution_loss()
        
        # Existing outer-island solar
        self._existing_outer_solar_mw = max(
            0, self.config.current_system.solar_capacity_mw - self.male_solar_cap_mw
        )
        prev_outer_solar_mw = self._existing_outer_solar_mw
        prev_battery = 0.0
        
        # Store per-year data
        self._outer_re_by_year: Dict[int, float] = {}
        self._male_share_by_year: Dict[int, float] = {}
        self._outer_share_by_year: Dict[int, float] = {}
        
        for year in self.config.time_horizon:
            # D60: Time-varying Malé demand share
            male_share = self.config.male_demand_share(year, self._scenario_growth_rate)
            outer_share = 1.0 - male_share
            
            # MR-09: Year-varying weighted distribution loss
            dist_loss = self.config.weighted_distribution_loss(year, self._scenario_growth_rate)
            loss_factor = 1.0 / (1.0 - dist_loss)
            
            # Get outer-island demand (gross of T&D losses)
            net_demand_gwh = self.demand.get_demand(year)
            gross_demand_gwh = net_demand_gwh * loss_factor
            outer_demand_gwh = gross_demand_gwh * outer_share
            
            # MW needed to serve 100% of outer demand
            mw_for_100pct = (outer_demand_gwh * 1000) / (8760 * effective_cf)
            
            # Add up to ramp_mw_yr
            gap_mw = max(0, mw_for_100pct - prev_outer_solar_mw)
            outer_solar_addition = min(self.ramp_mw_yr, gap_mw)
            
            new_outer_solar_mw = prev_outer_solar_mw + outer_solar_addition
            
            # Outer RE share (endogenous)
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
            
            # Battery (outer islands only)
            required_battery_mwh = new_outer_solar_mw * self.config.green_transition.battery_ratio
            battery_addition = max(0, required_battery_mwh - prev_battery)
            self.battery_additions[year] = battery_addition
            prev_battery = required_battery_mwh
    
    def _get_national_re_target(self, year: int) -> float:
        """
        Compute national RE as weighted average of two segments.
        
        Identical to NG — Malé RE capped at ~4% (rooftop only).
        LNG is not RE — it only changes the fuel type for Malé, not the RE share.
        
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
        Calculate generation mix for LNG Transition.
        
        Two-segment model:
        - Outer islands: solar+battery, same as NG
        - Malé: diesel (pre-LNG) → LNG (post-LNG) + 18 MWp rooftop solar
        - Diesel/LNG covers all non-RE demand
        """
        net_demand_gwh = self.demand.get_demand(year)
        peak_mw = self.demand.get_peak(year)
        
        # C2+R5: Gross up for distribution losses (segmented Malé 8% / outer 12%)
        demand_gwh = self.cost_calc.gross_up_for_losses(
            net_demand_gwh, include_distribution=True, include_hvdc=False,
            year=year, scenario_growth_rate=self._scenario_growth_rate,
        )
        
        # Get national RE target
        re_target = self._get_national_re_target(year)
        
        # Update installed capacities
        self.solar_capacity_mw += self.solar_additions.get(year, 0)
        self.battery_capacity_mwh += self.battery_additions.get(year, 0)
        
        # Solar generation with vintage-based degradation (C7, C8)
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
        
        # Remaining demand met by diesel or LNG (after solar + WTE)
        fossil_gwh = demand_gwh - solar_gwh - wte_gwh
        if fossil_gwh < 0:
            fossil_gwh = 0
        
        # Split fossil between LNG (Malé) and diesel (remainder)
        lng_operational = year >= self.lng_online_year
        
        if lng_operational:
            male_share = self._male_share_by_year.get(year, self.male_demand_share_base)
            male_demand_gwh = demand_gwh * male_share
            male_solar_gwh = demand_gwh * male_share * self.male_max_re
            male_fossil_gwh = male_demand_gwh - male_solar_gwh
            
            # LNG serves Malé fossil demand (up to plant capacity)
            lng_max_gwh = (
                self.lng_capacity_mw * 8760 * self.lng_capacity_factor / 1000
            )
            lng_gwh = min(male_fossil_gwh, lng_max_gwh)
            
            # Any remaining Malé demand beyond LNG capacity → diesel backup
            diesel_gwh = fossil_gwh - lng_gwh
            if diesel_gwh < 0:
                diesel_gwh = 0
        else:
            # Pre-LNG: all fossil demand is diesel
            lng_gwh = 0.0
            diesel_gwh = fossil_gwh
        
        # Diesel capacity management
        min_diesel_capacity = peak_mw * self.config.technology.min_diesel_backup
        reserve_factor = 1 + self.config.technology.reserve_margin
        required_diesel_mw = max(
            min_diesel_capacity,
            peak_mw * (1 - re_target) * reserve_factor
        )
        
        # Don't add diesel, only maintain/reduce
        self.diesel_capacity_mw = min(self.diesel_capacity_mw, required_diesel_mw)
        self.diesel_capacity_mw = max(self.diesel_capacity_mw, min_diesel_capacity)
        
        # MR-03: Store LNG generation in dedicated lng_gwh field
        # (previously reused import_gwh, which conflated LNG with cable imports)
        return GenerationMix(
            year=year,
            total_demand_gwh=demand_gwh,
            diesel_gwh=round(diesel_gwh, 1),
            solar_gwh=round(solar_gwh, 1),
            lng_gwh=round(lng_gwh, 1),  # MR-03: LNG in its own field
            wte_gwh=round(wte_gwh, 1),
            diesel_capacity_mw=round(self.diesel_capacity_mw, 1),
            solar_capacity_mw=round(self.solar_capacity_mw, 1),
            battery_capacity_mwh=round(self.battery_capacity_mwh, 1),
        )
    
    def calculate_annual_costs(self, year: int, gen_mix: GenerationMix) -> AnnualCosts:
        """
        Calculate costs for LNG Transition scenario.
        
        Key difference from NG: LNG CAPEX (one-time) + LNG fuel costs replace
        part of diesel fuel costs.
        """
        costs = AnnualCosts(year=year)
        
        # === CAPEX: Solar additions ===
        solar_addition = self.solar_additions.get(year, 0)
        if solar_addition > 0:
            costs.capex_solar = self.cost_calc.solar_capex(solar_addition, year)
        
        # === CAPEX: Battery additions ===
        battery_addition = self.battery_additions.get(year, 0)
        if battery_addition > 0:
            costs.capex_battery = self.cost_calc.battery_capex(battery_addition, year)
        
        # === CAPEX: Battery replacement ===
        battery_life = self.config.technology.battery_lifetime
        if year - battery_life >= self.config.base_year:
            past_battery = self.battery_additions.get(year - battery_life, 0)
            if past_battery > 0:
                costs.capex_battery += self.cost_calc.battery_capex(past_battery, year)
        
        # === CAPEX: Inter-island grid (one-time) ===
        if (self.config.green_transition.inter_island_grid
            and year == self.config.green_transition.inter_island_build_end
            and not self.inter_island_built):
            costs.capex_grid = self.cost_calc.inter_island_cable_capex(
                self.config.green_transition.inter_island_km
            )
            self.inter_island_built = True
        
        # === CAPEX: LNG terminal (one-time, at online year) ===
        if year == self.lng_online_year and not self.lng_built:
            # LNG CAPEX with climate adaptation premium
            lng_capex = self.lng_capex_total
            adaptation_premium = self.config.technology.climate_adaptation_premium
            lng_capex *= (1 + adaptation_premium)
            costs.capex_grid += lng_capex  # Add to grid/infra CAPEX line
            self.lng_built = True
        
        # === CAPEX: Diesel replacement (minimal — fleet shrinking) ===
        diesel_replacement_mw = gen_mix.diesel_capacity_mw / self.config.technology.diesel_gen_lifetime
        costs.capex_diesel = self.cost_calc.diesel_gen_capex(diesel_replacement_mw)
        
        # === OPEX: Solar ===
        costs.opex_solar = self.cost_calc.solar_opex(gen_mix.solar_capacity_mw, year)
        
        # === OPEX: Battery ===
        costs.opex_battery = self.cost_calc.battery_opex(gen_mix.battery_capacity_mwh)
        
        # === OPEX: Diesel ===
        costs.opex_diesel = self.cost_calc.diesel_gen_opex(gen_mix.diesel_gwh)
        
        # === OPEX: LNG ===
        lng_gwh = gen_mix.lng_gwh  # MR-03: dedicated field
        if lng_gwh > 0:
            costs.opex_diesel += lng_gwh * 1000 * self.config.lng.opex_per_mwh  # GWh → MWh × $/MWh
        
        # === Fuel: Diesel (C9: two-part fuel curve) ===
        costs.fuel_diesel = self.cost_calc.diesel_fuel_cost(
            gen_mix.diesel_gwh, year,
            diesel_capacity_mw=gen_mix.diesel_capacity_mw
        )
        
        # === Fuel: LNG (E-CR-02 fix: use dedicated fuel_lng field) ===
        if lng_gwh > 0:
            lng_fuel_per_mwh = self.config.lng.get_fuel_cost(year, self.config.base_year)
            costs.fuel_lng = lng_gwh * 1000 * lng_fuel_per_mwh  # GWh → MWh × $/MWh
        
        # R6: WTE CAPEX (one-time at online year) + annual OPEX
        if year == self.config.wte.online_year:
            costs.capex_wte = self.config.wte.total_capex * (1 + self.config.technology.climate_adaptation_premium)
        if (year >= self.config.wte.online_year
                and year < self.config.wte.online_year + self.config.wte.plant_lifetime):
            costs.opex_wte = self.config.wte.annual_opex
        
        # === L11: Connection costs (phased rollout) ===
        conn_cfg = self.config.connection
        conn_start = self.config.base_year + 1
        conn_end = conn_start + conn_cfg.rollout_years - 1
        if conn_start <= year <= conn_end:
            annual_hh = conn_cfg.number_of_households / conn_cfg.rollout_years
            costs.capex_connection = self.cost_calc.connection_capex(int(annual_hh))
        
        return costs
    
    def calculate_annual_emissions(self, year: int, gen_mix: GenerationMix) -> 'AnnualEmissions':
        """
        Override emission calculation to use LNG-specific emission factor.
        
        Diesel uses standard 0.72 kgCO₂/kWh (via EmissionsCalculator).
        LNG uses 0.40 kgCO₂/kWh (from config.lng.emission_factor).
        Solar lifecycle emissions via EmissionsCalculator.
        
        LNG emissions are stored in import_emissions_tco2 field.
        """
        from ..emissions import AnnualEmissions
        
        # Diesel emissions — use standard calculator
        diesel_emissions_tco2 = self.emissions_calc.diesel_emissions(gen_mix.diesel_gwh)
        
        # LNG emissions — same unit conversion as diesel but with LNG factor
        lng_gwh = gen_mix.lng_gwh  # MR-03: dedicated field
        lng_ef = self.config.lng.emission_factor  # 0.40 kgCO₂/kWh
        lng_kwh = lng_gwh * 1_000_000
        lng_emissions_tco2 = lng_kwh * lng_ef / 1000  # kg → tonnes
        
        # Solar lifecycle emissions — use standard calculator
        solar_emissions_tco2 = self.emissions_calc.solar_lifecycle_emissions(gen_mix.solar_capacity_mw)
        
        return AnnualEmissions(
            year=year,
            diesel_emissions_tco2=diesel_emissions_tco2,
            import_emissions_tco2=lng_emissions_tco2,  # LNG emissions in import field
            solar_lifecycle_tco2=solar_emissions_tco2,
        )


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    config = get_config()
    scenario = LNGTransitionScenario(config)
    
    print("=" * 60)
    print("LNG TRANSITION SCENARIO TEST")
    print(f"  LNG capacity: {scenario.lng_capacity_mw} MW")
    print(f"  LNG online: {scenario.lng_online_year}")
    print(f"  LNG CAPEX: ${scenario.lng_capex_total / 1e6:,.0f}M")
    print(f"  LNG emission factor: {scenario.lng_emission_factor} kgCO2/kWh")
    print(f"  Deployment ramp: {scenario.ramp_mw_yr} MW/yr")
    print(f"  Malé demand share (base): {scenario.male_demand_share_base:.0%}")
    print("=" * 60)
    
    # Run scenario
    results = scenario.run()
    
    # Print generation mix for key years
    print("\n--- GENERATION MIX ---")
    print(f"{'Year':<6} {'Demand':<10} {'Diesel':<10} {'LNG':<10} {'Solar':<10} {'RE %':<10}")
    print("-" * 60)
    key_years = [config.base_year, 2028, 2031, 2035, 2040, config.end_year]
    for year in key_years:
        gen = results.generation_mix[year]
        print(f"{year:<6} {gen.total_demand_gwh:<10.0f} {gen.diesel_gwh:<10.0f} {gen.lng_gwh:<10.0f} {gen.solar_gwh:<10.0f} {gen.re_share:<10.1%}")
    
    # Summary
    print("\n--- SUMMARY ---")
    summary = scenario.get_summary()
    print(f"Total costs ({config.base_year}-{config.end_year}): ${summary['total_costs_million']:,.0f}M")
    print(f"Total emissions: {summary['total_emissions_mtco2']:.2f} MtCO2")
    print(f"Final RE share (2050): {summary['final_re_share']:.1%}")
    
    print("\n✓ LNG Transition scenario tests passed!")
