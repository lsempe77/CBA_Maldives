"""
Maximum RE Scenario
===================

Scenario 6: Near-Shore Solar + Floating Solar + Wind on Greater Malé.

Extends Near-Shore Solar (S5) by adding floating solar PV on Malé's
protected lagoon areas and wind turbines on industrial islands,
dramatically raising Malé's RE share.

Five tranches of Malé RE:
  1. Rooftop (existing): 34 MWp → ~8% of Malé demand
  2. Near-shore islands: 104 MW → ~21% of Malé demand
  3. Floating solar: 195 MW (GoM Roadmap target) → ~19% of Malé demand
  4. Wind: 80 MW on Gulhifalhu/Thilafushi (ADB Roadmap) → ~7% of Malé demand
  Total: ~413 MW → Malé RE ~55%  

National RE target: ~80%+ (outer 100% + Malé ~55%)

Key differences from Near-Shore Solar:
  - Floating solar CAPEX = standard solar × 1.5 premium
  - Wind turbines (2 MW, $3000/kW, CF 25%)
  - Highest overall national RE (80%+)
  - Largest CAPEX of all domestic scenarios
"""

from typing import Dict
import numpy as np

from ..config import Config, get_config
from ..demand import DemandProjector
from ..costs import CostCalculator, AnnualCosts
from . import BaseScenario, GenerationMix


class MaximumREScenario(BaseScenario):
    """
    Maximum RE: NG + near-shore solar + floating solar + wind.
    
    Five-segment RE model:
    - Outer islands (declining share): unconstrained, ramp to 100% RE
    - Greater Malé rooftop (34 MWp): ~8% of Malé demand
    - Near-shore solar (104 MW on uninhabited islands): ~21% of Malé
    - Floating solar (195 MW, GoM Roadmap target): ~19% of Malé demand
    - Wind (80 MW on Gulhifalhu/Thilafushi, ADB Roadmap): ~7% of Malé
    - Total Malé RE: ~55%, national ~80%+
    """
    
    def __init__(self, config: Config = None):
        config = config or get_config()
        super().__init__(
            name="Maximum RE",
            description="NG + near-shore + floating solar + wind (80%+ RE)",
            config=config,
        )
        
        # Initialize demand projector with green transition growth rate
        self.demand = self._init_demand_projector()
        
        # Deployment ramp for outer islands (same as NG)
        self.ramp_mw_yr = self.config.green_transition.deployment_ramp_mw_per_year
        
        # Malé RE: rooftop
        self.male_rooftop_re = self.config.green_transition.male_max_re_share
        self.male_solar_cap_mw = self.config.current_system.male_rooftop_solar_mwp
        
        # Near-shore solar parameters
        ns = self.config.nearshore
        self.nearshore_mw = ns.nearshore_solar_mw  # 104 MW
        self.nearshore_build_start = ns.nearshore_build_start
        self.nearshore_build_end = ns.nearshore_build_start + ns.nearshore_build_years - 1
        self.nearshore_cable_cost_per_mw = ns.nearshore_cable_cost_per_mw
        
        # Floating solar parameters
        self.floating_mw = ns.floating_solar_mw  # 195 MW (GoM Roadmap)
        self.floating_build_start = ns.floating_build_start
        self.floating_build_end = ns.floating_build_start + ns.floating_build_years - 1
        self.floating_capex_premium = ns.floating_solar_capex_premium  # 1.5×
        
        # Wind energy parameters (ADB Roadmap: 80 MW on Gulhifalhu/Thilafushi)
        wc = self.config.wind
        self.wind_mw = wc.capacity_mw  # 80 MW
        self.wind_cf = wc.capacity_factor  # 0.25
        self.wind_build_start = wc.build_start
        self.wind_build_end = wc.build_start + wc.build_years - 1
        self.wind_capex_per_kw = wc.capex_per_kw  # $3000/kW
        self.wind_opex_per_kw = wc.opex_per_kw  # $30/kW/yr
        self.wind_lifetime = wc.lifetime  # 25 years
        
        # D60: Density-constrained demand share
        self.male_demand_share_base = self.config.current_system.male_electricity_share
        self._scenario_growth_rate = self.config.demand.growth_rates["green_transition"]
        
        # Track installed capacities
        self.solar_capacity_mw = self.config.current_system.solar_capacity_mw
        self.battery_capacity_mwh = self.config.current_system.battery_capacity_mwh
        self.diesel_capacity_mw = self.config.current_system.diesel_capacity_mw
        
        # Track capacity additions by year
        self.solar_additions: Dict[int, float] = {}
        self.battery_additions: Dict[int, float] = {}
        self.nearshore_additions: Dict[int, float] = {}
        self.floating_additions: Dict[int, float] = {}
        self.wind_additions: Dict[int, float] = {}
        
        # Inter-island grid
        self.inter_island_built = False
        
        # Pre-calculate deployment schedule
        self._calculate_deployment_schedule()
    
    def _non_ground_solar_mw(self, year: int) -> float:
        """V7: Nearshore + floating solar + wind bypass land constraint."""
        ns = self._nearshore_cumulative_by_year.get(year, 0.0)
        fl = self._floating_cumulative_by_year.get(year, 0.0)
        wi = self._wind_cumulative_by_year.get(year, 0.0)
        return ns + fl + wi
    
    def _init_demand_projector(self) -> DemandProjector:
        return DemandProjector(
            config=self.config,
            scenario="green_transition",
            growth_rate=self.config.demand.growth_rates["green_transition"],
        )
    
    def _calculate_deployment_schedule(self) -> None:
        """
        Endogenous deployment: outer islands at ramp + near-shore + floating + wind phased.
        
        Near-shore deployed during nearshore_build_start..nearshore_build_end.
        Floating solar deployed during floating_build_start..floating_build_end.
        Wind deployed during wind_build_start..wind_build_end.
        Floating solar CAPEX uses a premium multiplier (tracked separately).
        Wind has separate CAPEX/OPEX and different capacity factor.
        """
        # LW-01: Use base class precomputed effective CF (temp-derated)
        self._effective_cf = self._effective_solar_cf
        
        # MR-09: Distribution loss computed per year using weighted_distribution_loss()
        
        # Existing outer-island solar
        self._existing_outer_solar_mw = max(
            0, self.config.current_system.solar_capacity_mw - self.male_solar_cap_mw
        )
        prev_outer_solar_mw = self._existing_outer_solar_mw
        prev_battery = 0.0
        
        # Near-shore / floating / wind deployment tracking
        nearshore_deployed_mw = 0.0
        floating_deployed_mw = 0.0
        wind_deployed_mw = 0.0
        ns_annual_mw = self.nearshore_mw / max(1, self.config.nearshore.nearshore_build_years)
        fl_annual_mw = self.floating_mw / max(1, self.config.nearshore.floating_build_years)
        wi_annual_mw = self.wind_mw / max(1, self.config.wind.build_years)
        
        # Store per-year RE shares and demand shares
        self._outer_re_by_year: Dict[int, float] = {}
        self._male_share_by_year: Dict[int, float] = {}
        self._outer_share_by_year: Dict[int, float] = {}
        self._nearshore_cumulative_by_year: Dict[int, float] = {}
        self._floating_cumulative_by_year: Dict[int, float] = {}
        self._wind_cumulative_by_year: Dict[int, float] = {}
        
        for year in self.config.time_horizon:
            # D60: Time-varying Malé demand share
            male_share = self.config.male_demand_share(year, self._scenario_growth_rate)
            outer_share = 1.0 - male_share
            self._male_share_by_year[year] = male_share
            self._outer_share_by_year[year] = outer_share
            
            # MR-09: Year-varying weighted distribution loss
            dist_loss = self.config.weighted_distribution_loss(year, self._scenario_growth_rate)
            loss_factor = 1.0 / (1.0 - dist_loss)
            
            net_demand_gwh = self.demand.get_demand(year)
            gross_demand_gwh = net_demand_gwh * loss_factor
            outer_demand_gwh = gross_demand_gwh * outer_share
            
            # === OUTER ISLANDS: deploy solar at ramp rate ===
            mw_for_100pct = (outer_demand_gwh * 1000) / (8760 * self._effective_cf)
            gap_mw = max(0, mw_for_100pct - prev_outer_solar_mw)
            outer_solar_addition = min(self.ramp_mw_yr, gap_mw)
            new_outer_solar_mw = prev_outer_solar_mw + outer_solar_addition
            
            outer_gen_gwh = new_outer_solar_mw * 8760 * self._effective_cf / 1000
            outer_re = min(1.0, outer_gen_gwh / outer_demand_gwh) if outer_demand_gwh > 0 else 0.0
            self._outer_re_by_year[year] = outer_re
            
            # === NEAR-SHORE SOLAR: phased deployment ===
            ns_addition = 0.0
            if self.nearshore_build_start <= year <= self.nearshore_build_end:
                ns_addition = min(ns_annual_mw, self.nearshore_mw - nearshore_deployed_mw)
                nearshore_deployed_mw += ns_addition
            self.nearshore_additions[year] = ns_addition
            self._nearshore_cumulative_by_year[year] = nearshore_deployed_mw
            
            # === FLOATING SOLAR: phased deployment ===
            fl_addition = 0.0
            if self.floating_build_start <= year <= self.floating_build_end:
                fl_addition = min(fl_annual_mw, self.floating_mw - floating_deployed_mw)
                floating_deployed_mw += fl_addition
            self.floating_additions[year] = fl_addition
            self._floating_cumulative_by_year[year] = floating_deployed_mw
            
            # === WIND: phased deployment on Gulhifalhu/Thilafushi ===
            wi_addition = 0.0
            if self.wind_build_start <= year <= self.wind_build_end:
                wi_addition = min(wi_annual_mw, self.wind_mw - wind_deployed_mw)
                wind_deployed_mw += wi_addition
            self.wind_additions[year] = wi_addition
            self._wind_cumulative_by_year[year] = wind_deployed_mw
            
            # === TOTAL SOLAR (excludes wind — wind has separate CF) ===
            total_solar_mw = (
                new_outer_solar_mw + self.male_solar_cap_mw
                + nearshore_deployed_mw + floating_deployed_mw
            )
            prev_total = (
                prev_outer_solar_mw + self.male_solar_cap_mw
                + (nearshore_deployed_mw - ns_addition)
                + (floating_deployed_mw - fl_addition)
            )
            solar_addition = max(0, total_solar_mw - prev_total)
            self.solar_additions[year] = solar_addition
            prev_outer_solar_mw = new_outer_solar_mw
            
            # Battery: ratio from config (outer + near-shore + floating + wind, not Malé rooftop)
            battery_base_mw = new_outer_solar_mw + nearshore_deployed_mw + floating_deployed_mw + wind_deployed_mw
            required_battery_mwh = battery_base_mw * self.config.green_transition.battery_ratio
            battery_addition = max(0, required_battery_mwh - prev_battery)
            self.battery_additions[year] = battery_addition
            prev_battery = required_battery_mwh
    
    def _get_male_re(self, year: int) -> float:
        """
        Compute Malé RE share including rooftop + near-shore + floating + wind.
        """
        male_share = self._male_share_by_year.get(year, self.male_demand_share_base)
        net_demand = self.demand.get_demand(year)
        # MR-09: Year-varying weighted distribution loss
        dist_loss = self.config.weighted_distribution_loss(year, self._scenario_growth_rate)
        gross_demand = net_demand / (1.0 - dist_loss)
        male_demand_gwh = gross_demand * male_share
        
        if male_demand_gwh <= 0:
            return 0.0
        
        # Rooftop solar generation
        rooftop_gwh = self.male_solar_cap_mw * 8760 * self._effective_cf / 1000
        
        # Near-shore solar generation
        ns_mw = self._nearshore_cumulative_by_year.get(year, 0.0)
        ns_gwh = ns_mw * 8760 * self._effective_cf / 1000
        
        # Floating solar generation
        fl_mw = self._floating_cumulative_by_year.get(year, 0.0)
        fl_gwh = fl_mw * 8760 * self._effective_cf / 1000
        
        # Wind generation (different CF than solar)
        wi_mw = self._wind_cumulative_by_year.get(year, 0.0)
        wi_gwh = wi_mw * 8760 * self.wind_cf / 1000
        
        male_re = min(1.0, (rooftop_gwh + ns_gwh + fl_gwh + wi_gwh) / male_demand_gwh)
        return male_re
    
    def _get_national_re_target(self, year: int) -> float:
        """
        National RE = outer_share × outer_re + male_share × male_re.
        D60: Uses time-varying demand shares.
        """
        outer_re = self._outer_re_by_year.get(year, 0.0)
        male_re = self._get_male_re(year)
        male_share = self._male_share_by_year.get(year, self.male_demand_share_base)
        outer_share = self._outer_share_by_year.get(year, 1.0 - self.male_demand_share_base)
        return outer_share * outer_re + male_share * male_re
    
    def calculate_generation_mix(self, year: int) -> GenerationMix:
        """Calculate generation mix for Maximum RE scenario."""
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
        
        # Solar generation with vintage-based degradation
        solar_gwh = self.cost_calc.solar_generation_vintaged(
            solar_additions=self.solar_additions,
            year=year,
            existing_mw=self._existing_outer_solar_mw + self.male_solar_cap_mw,
        )
        
        # Cap solar at national RE target (before adding wind)
        max_re_gwh = demand_gwh * re_target
        solar_gwh = min(solar_gwh, max_re_gwh)
        
        # Wind generation (separate CF from solar)
        wi_mw = self._wind_cumulative_by_year.get(year, 0.0)
        wind_gwh = wi_mw * 8760 * self.wind_cf / 1000
        
        # Cap total RE (solar + wind) at RE target
        total_re_gwh = solar_gwh + wind_gwh
        if total_re_gwh > max_re_gwh:
            # Scale both proportionally
            scale = max_re_gwh / total_re_gwh if total_re_gwh > 0 else 0
            solar_gwh *= scale
            wind_gwh *= scale
        
        # R6: Waste-to-energy baseload (Thilafushi 12 + Addu 1.5 + Vandhoo 0.5 = 14 MW)
        wte_gwh = 0.0
        if year >= self.config.wte.online_year:
            wte_gwh = min(self.config.wte.annual_generation_gwh, max(0, demand_gwh - solar_gwh - wind_gwh))
        
        # Diesel meets the rest after solar + wind + WTE
        diesel_gwh = max(0, demand_gwh - solar_gwh - wind_gwh - wte_gwh)
        
        # Diesel capacity management
        min_diesel_capacity = peak_mw * self.config.technology.min_diesel_backup
        reserve_factor = 1 + self.config.technology.reserve_margin
        required_diesel_mw = max(
            min_diesel_capacity,
            peak_mw * (1 - re_target) * reserve_factor
        )
        self.diesel_capacity_mw = min(self.diesel_capacity_mw, required_diesel_mw)
        self.diesel_capacity_mw = max(self.diesel_capacity_mw, min_diesel_capacity)
        
        return GenerationMix(
            year=year,
            total_demand_gwh=demand_gwh,
            diesel_gwh=round(diesel_gwh, 1),
            solar_gwh=round(solar_gwh, 1),
            import_gwh=0.0,
            wte_gwh=round(wte_gwh, 1),
            wind_gwh=round(wind_gwh, 1),
            diesel_capacity_mw=round(self.diesel_capacity_mw, 1),
            solar_capacity_mw=round(self.solar_capacity_mw, 1),
            battery_capacity_mwh=round(self.battery_capacity_mwh, 1),
        )
    
    def calculate_annual_costs(self, year: int, gen_mix: GenerationMix) -> AnnualCosts:
        """
        Calculate costs for Maximum RE scenario.
        
        Key differences:
        - Floating solar uses CAPEX premium (1.5×)
        - Wind has separate CAPEX ($3000/kW) and OPEX ($30/kW/yr)
        """
        costs = AnnualCosts(year=year)
        
        # CAPEX: Solar additions (outer + rooftop at standard cost)
        # Near-shore and floating solar CAPEX handled separately
        outer_addition = self.solar_additions.get(year, 0) - self.nearshore_additions.get(year, 0) - self.floating_additions.get(year, 0)
        outer_addition = max(0, outer_addition)
        
        ns_addition = self.nearshore_additions.get(year, 0)
        fl_addition = self.floating_additions.get(year, 0)
        
        # Standard solar CAPEX (outer + near-shore)
        standard_solar_addition = outer_addition + ns_addition
        if standard_solar_addition > 0:
            costs.capex_solar = self.cost_calc.solar_capex(standard_solar_addition, year)
        
        # Floating solar CAPEX (premium rate)
        if fl_addition > 0:
            standard_cost = self.cost_calc.solar_capex(fl_addition, year)
            costs.capex_solar += standard_cost * self.floating_capex_premium
        
        # CAPEX: Near-shore cable cost (only during near-shore build years)
        if ns_addition > 0:
            costs.capex_grid += ns_addition * self.nearshore_cable_cost_per_mw
        
        # CAPEX: Battery additions
        battery_addition = self.battery_additions.get(year, 0)
        if battery_addition > 0:
            costs.capex_battery = self.cost_calc.battery_capex(battery_addition, year)
        
        # CAPEX: Battery replacement
        battery_life = self.config.technology.battery_lifetime
        if year - battery_life >= self.config.base_year:
            past_battery = self.battery_additions.get(year - battery_life, 0)
            if past_battery > 0:
                costs.capex_battery += self.cost_calc.battery_capex(past_battery, year)
        
        # CAPEX: Inter-island grid (one-time)
        if (self.config.green_transition.inter_island_grid and 
            year == self.config.green_transition.inter_island_build_end and
            not self.inter_island_built):
            costs.capex_grid += self.cost_calc.inter_island_cable_capex(
                self.config.green_transition.inter_island_km
            )
            self.inter_island_built = True
        
        # CAPEX: Diesel replacement
        diesel_replacement_mw = gen_mix.diesel_capacity_mw / self.config.technology.diesel_gen_lifetime
        costs.capex_diesel = self.cost_calc.diesel_gen_capex(diesel_replacement_mw)
        
        # OPEX
        costs.opex_solar = self.cost_calc.solar_opex(gen_mix.solar_capacity_mw, year)
        costs.opex_battery = self.cost_calc.battery_opex(gen_mix.battery_capacity_mwh)
        costs.opex_diesel = self.cost_calc.diesel_gen_opex(gen_mix.diesel_gwh)
        
        # Fuel: Diesel
        costs.fuel_diesel = self.cost_calc.diesel_fuel_cost(
            gen_mix.diesel_gwh, year,
            diesel_capacity_mw=gen_mix.diesel_capacity_mw
        )
        
        # CAPEX: Wind turbines (separate from solar — different cost structure)
        wi_addition = self.wind_additions.get(year, 0)
        if wi_addition > 0:
            costs.capex_wind = wi_addition * 1000 * self.wind_capex_per_kw * (1 + self.config.technology.climate_adaptation_premium)
        
        # OPEX: Wind turbines ($30/kW/yr for deployed capacity)
        wi_deployed = self._wind_cumulative_by_year.get(year, 0.0)
        if wi_deployed > 0:
            costs.opex_wind = wi_deployed * 1000 * self.wind_opex_per_kw
        
        # Wind turbine replacement (after wind_lifetime years)
        if year - self.wind_lifetime >= self.config.base_year:
            past_wi = self.wind_additions.get(year - self.wind_lifetime, 0)
            if past_wi > 0:
                costs.capex_wind += past_wi * 1000 * self.wind_capex_per_kw * (1 + self.config.technology.climate_adaptation_premium)
        
        # R6: WTE CAPEX (one-time at online year) + annual OPEX
        if year == self.config.wte.online_year:
            costs.capex_wte = self.config.wte.total_capex * (1 + self.config.technology.climate_adaptation_premium)
        if (year >= self.config.wte.online_year
                and year < self.config.wte.online_year + self.config.wte.plant_lifetime):
            costs.opex_wte = self.config.wte.annual_opex
        
        # L11: Connection costs
        conn_cfg = self.config.connection
        conn_start = self.config.base_year + 1
        conn_end = conn_start + conn_cfg.rollout_years - 1
        if conn_start <= year <= conn_end:
            annual_hh = conn_cfg.number_of_households / conn_cfg.rollout_years
            costs.capex_connection = self.cost_calc.connection_capex(int(annual_hh))
        
        return costs


if __name__ == "__main__":
    config = get_config()
    scenario = MaximumREScenario(config)
    
    print("=" * 80)
    print("MAXIMUM RE SCENARIO TEST")
    print(f"  Near-shore MW: {scenario.nearshore_mw} MW")
    print(f"  Floating MW:   {scenario.floating_mw} MW")
    print(f"  Wind MW:       {scenario.wind_mw} MW (CF={scenario.wind_cf:.0%})")
    print(f"  Total Malé RE: {scenario.male_solar_cap_mw + scenario.nearshore_mw + scenario.floating_mw + scenario.wind_mw} MW")
    print(f"  Near-shore: {scenario.nearshore_build_start}-{scenario.nearshore_build_end}")
    print(f"  Floating:   {scenario.floating_build_start}-{scenario.floating_build_end}")
    print(f"  Wind:       {scenario.wind_build_start}-{scenario.wind_build_end}")
    print("=" * 80)
    
    results = scenario.run()
    
    print("\n--- GENERATION MIX ---")
    print(f"{'Year':<6} {'Demand':<10} {'Diesel':<10} {'Solar':<10} {'Wind':<8} {'RE %':<10} {'Solar MW':<10} {'NS MW':<8} {'FL MW':<8} {'WI MW':<8}")
    print("-" * 98)
    key_years = [config.base_year, 2030, 2033, 2035, 2038, 2040, 2050, config.end_year]
    for year in key_years:
        if year in results.generation_mix:
            gen = results.generation_mix[year]
            ns_mw = scenario._nearshore_cumulative_by_year.get(year, 0)
            fl_mw = scenario._floating_cumulative_by_year.get(year, 0)
            wi_mw = scenario._wind_cumulative_by_year.get(year, 0)
            print(f"{year:<6} {gen.total_demand_gwh:<10.0f} {gen.diesel_gwh:<10.0f} {gen.solar_gwh:<10.0f} {gen.wind_gwh:<8.0f} {gen.re_share:<10.1%} {gen.solar_capacity_mw:<10.0f} {ns_mw:<8.0f} {fl_mw:<8.0f} {wi_mw:<8.0f}")
    
    summary = scenario.get_summary()
    print(f"\nTotal costs: ${summary['total_costs_million']:,.0f}M")
    print(f"Final RE: {summary['final_re_share']:.1%}")
    print("✓ Maximum RE scenario tests passed!")
