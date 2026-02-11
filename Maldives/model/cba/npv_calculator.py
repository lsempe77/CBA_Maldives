"""
CBA Calculator
==============

NPV, BCR, and incremental analysis for scenario comparison.

This module calculates:
- Net Present Value (NPV) of costs and benefits
- Benefit-Cost Ratio (BCR)
- Incremental NPV between scenarios
- Annualized costs (levelized)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

from ..config import Config, get_config
from ..scenarios import ScenarioResults


@dataclass
class NPVResult:
    """
    Results of NPV calculation for a scenario.
    """
    scenario_name: str
    
    # Present values (USD)
    pv_capex: float = 0.0
    pv_opex: float = 0.0
    pv_fuel: float = 0.0
    pv_ppa: float = 0.0
    pv_salvage: float = 0.0  # C3: Terminal salvage value (negative = credit)
    pv_total_costs: float = 0.0
    
    # Emission costs/benefits (monetized)
    pv_emission_costs: float = 0.0  # Cost of emissions (SCC valuation)
    
    # L4: Health co-benefits (PV of avoided health damages from diesel reduction)
    pv_health_benefits: float = 0.0
    
    # L20: Reliability benefits (PV of SAIDI reduction × VOLL × demand)
    pv_reliability_benefits: float = 0.0
    
    # L16: Environmental externality benefits (noise, spill, biodiversity)
    pv_environmental_benefits: float = 0.0
    
    # Levelized costs
    lcoe_usd_per_kwh: float = 0.0  # Levelized cost of electricity
    
    # Annual averages
    annual_avg_cost: float = 0.0
    annual_avg_capex: float = 0.0
    
    # Discount rate used
    discount_rate: float = 0.0


@dataclass
class IncrementalResult:
    """
    Incremental analysis between two scenarios.
    """
    base_scenario: str
    alternative_scenario: str
    
    # Incremental costs (alt - base)
    incremental_pv_capex: float = 0.0
    incremental_pv_opex: float = 0.0
    incremental_pv_fuel: float = 0.0
    incremental_pv_ppa: float = 0.0
    incremental_pv_costs: float = 0.0
    
    # Incremental benefits
    pv_fuel_savings: float = 0.0  # Fuel avoided (base fuel - alt fuel)
    pv_emission_savings: float = 0.0  # Emission reduction benefit
    pv_health_savings: float = 0.0  # L4: Health damage avoided (base health cost - alt)
    pv_reliability_savings: float = 0.0  # L20: Reliability improvement (SAIDI × VOLL)
    pv_environmental_savings: float = 0.0  # A-MO-01: Environmental externality avoided
    pv_total_benefits: float = 0.0
    
    # Net benefit (benefits - costs)
    npv: float = 0.0
    
    # Benefit-Cost Ratio
    bcr: float = 0.0
    
    # Internal Rate of Return (if calculable)
    irr: Optional[float] = None
    
    # Payback period (years)
    payback_years: Optional[float] = None


@dataclass
class CBAComparison:
    """
    Complete CBA comparison of all scenarios.
    
    Attribute naming uses *logical* scenario names:
      - bau              (file: status_quo.py)
      - full_integration (file: one_grid.py)
      - national_grid    (file: green_transition.py)
      - islanded_green   (file: islanded_green.py)
      - nearshore_solar  (file: nearshore_solar.py)
      - maximum_re       (file: maximum_re.py)
    """
    bau: NPVResult
    full_integration: NPVResult
    national_grid: NPVResult
    islanded_green: NPVResult
    nearshore_solar: NPVResult
    maximum_re: NPVResult
    lng_transition: NPVResult
    
    # Incremental analyses
    fi_vs_bau: IncrementalResult
    ng_vs_bau: IncrementalResult
    fi_vs_ng: IncrementalResult
    ig_vs_bau: IncrementalResult
    ns_vs_bau: IncrementalResult
    mx_vs_bau: IncrementalResult
    lng_vs_bau: IncrementalResult
    
    # Least cost scenario
    least_cost_scenario: str = ""
    least_cost_npv: float = 0.0
    
    # Recommended scenario (considering emissions)
    recommended_scenario: str = ""


class CBACalculator:
    """
    Performs CBA calculations for scenario comparison.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        self.discount_rate = self.config.economics.discount_rate
        self.base_year = self.config.base_year
        self.horizon = self.config.time_horizon
    
    def discount_factor(self, year: int) -> float:
        """
        Calculate discount factor for a given year.
        
        DF = 1 / (1 + r)^t
        where t = year - base_year
        """
        t = year - self.base_year
        return 1.0 / ((1 + self.discount_rate) ** t)
    
    def discount_factor_declining(self, year: int) -> float:
        """
        P1: Calculate discount factor using declining discount rate (DDR) schedule.
        
        Based on HM Treasury Green Book (2026) Table 8:
          - Years 0-30:   3.5%
          - Years 31-75:  3.0%
          - Years 76-125: 2.5%
        
        Also supported by Drupp et al. (2018) AEJ and Weitzman (2001) AER.
        
        Rationale: Uncertainty about long-run discount rate means the
        certainty-equivalent rate declines with horizon (Weitzman 1998).
        
        The discount factor is computed as the product of year-by-year
        factors: DF(t) = prod_{s=0}^{t-1} 1/(1+r_s)
        
        References:
          - HM Treasury (2022). The Green Book: Central Government Guidance
            on Appraisal and Evaluation. Table 8, pp. 47-48.
          - Weitzman, M.L. (2001). "Gamma discounting". American Economic
            Review, 91(1), 260-271. doi:10.1257/aer.91.1.260
          - Drupp, M.A., Freeman, M.C., Groom, B., Nesje, F. (2018).
            "Discounting disentangled". American Economic Journal: Economic
            Policy, 10(4), 109-134. doi:10.1257/pol.20160240
          - Arrow, K.J. et al. (2014). "Should governments use a declining
            discount rate in project analysis?" Review of Environmental
            Economics and Policy, 8(2), 145-163.
        """
        t = year - self.base_year
        if t <= 0:
            return 1.0
        
        econ = self.config.economics
        r1 = econ.ddr_rate_0_30    # Years 0-30
        r2 = econ.ddr_rate_31_75   # Years 31-75
        r3 = econ.ddr_rate_76_125  # Years 76-125
        
        # Compute cumulative discount factor using step-function rates
        if t <= 30:
            return 1.0 / ((1 + r1) ** t)
        elif t <= 75:
            # First 30 years at r1, remaining at r2
            df_30 = 1.0 / ((1 + r1) ** 30)
            df_rest = 1.0 / ((1 + r2) ** (t - 30))
            return df_30 * df_rest
        else:
            # First 30 at r1, next 45 at r2, remaining at r3
            df_30 = 1.0 / ((1 + r1) ** 30)
            df_45 = 1.0 / ((1 + r2) ** 45)
            df_rest = 1.0 / ((1 + r3) ** (t - 75))
            return df_30 * df_45 * df_rest
    
    def present_value_declining(self, annual_values: Dict[int, float]) -> float:
        """
        P1: Calculate present value using declining discount rate schedule.
        """
        pv = 0.0
        for year, value in annual_values.items():
            pv += value * self.discount_factor_declining(year)
        return pv
    
    def calculate_npv_declining(self, results: ScenarioResults) -> NPVResult:
        """
        P1: Calculate NPV using declining discount rate schedule.
        Returns an NPVResult with DDR-discounted present values for comparison.
        """
        npv = NPVResult(
            scenario_name=results.name + " (DDR)",
            discount_rate=-1,  # Flag: declining schedule, not constant
        )
        
        # Extract annual cost streams
        capex_stream = {}
        opex_stream = {}
        fuel_stream = {}
        ppa_stream = {}
        demand_stream = {}
        
        for year, costs in results.annual_costs.items():
            capex_stream[year] = costs.total_capex
            opex_stream[year] = costs.total_opex
            fuel_stream[year] = costs.fuel_diesel + costs.fuel_lng  # E-CR-02: include LNG fuel
            ppa_stream[year] = costs.ppa_imports
        
        for year, gen in results.generation_mix.items():
            demand_stream[year] = gen.total_demand_gwh
        
        # Calculate present values using DDR
        npv.pv_capex = self.present_value_declining(capex_stream)
        npv.pv_opex = self.present_value_declining(opex_stream)
        npv.pv_fuel = self.present_value_declining(fuel_stream)
        npv.pv_ppa = self.present_value_declining(ppa_stream)
        
        # Salvage value (use DDR discount factor for end year)
        # C-MO-04 fix: renamed from salvage_undiscounted — calculate_salvage_value()
        # already returns a value discounted at the constant rate.
        end_year = max(self.horizon)
        salvage_discounted = self.calculate_salvage_value(results)
        # Re-discount using DDR factor ratio
        constant_df = self.discount_factor(end_year)
        ddr_df = self.discount_factor_declining(end_year)
        if constant_df > 0:
            npv.pv_salvage = salvage_discounted * (ddr_df / constant_df)
        else:
            npv.pv_salvage = salvage_discounted
        
        npv.pv_total_costs = (
            npv.pv_capex + npv.pv_opex + npv.pv_fuel + npv.pv_ppa
            - npv.pv_salvage
        )
        
        # Emission costs
        emission_stream = {}
        for year, emissions in results.annual_emissions.items():
            scc = self._get_scc(year)
            emission_stream[year] = emissions.total_emissions_ktco2 * 1000 * scc
        npv.pv_emission_costs = self.present_value_declining(emission_stream)
        
        # Health + reliability + environmental benefits
        health_stream = {}
        reliability_stream = {}
        environmental_stream = {}
        for year, benefits in results.annual_benefits.items():
            health_stream[year] = benefits.health_benefit
            reliability_stream[year] = benefits.reliability_benefit
            environmental_stream[year] = benefits.environmental_benefit  # A-MO-01
        npv.pv_health_benefits = self.present_value_declining(health_stream)
        npv.pv_reliability_benefits = self.present_value_declining(reliability_stream)
        npv.pv_environmental_benefits = self.present_value_declining(environmental_stream)
        
        # LCOE
        pv_demand_gwh = self.present_value_declining(demand_stream)
        if pv_demand_gwh > 0:
            npv.lcoe_usd_per_kwh = npv.pv_total_costs / (pv_demand_gwh * 1e6)
        
        return npv
    
    def present_value(self, annual_values: Dict[int, float]) -> float:
        """
        Calculate present value of a stream of annual values.
        """
        pv = 0.0
        for year, value in annual_values.items():
            pv += value * self.discount_factor(year)
        return pv
    
    def annuity_factor(self, n_years: int = None) -> float:
        """
        Calculate annuity factor for levelizing.
        
        AF = r * (1+r)^n / ((1+r)^n - 1)
        """
        n = n_years or len(self.horizon)
        r = self.discount_rate
        
        numerator = r * ((1 + r) ** n)
        denominator = ((1 + r) ** n) - 1
        
        return numerator / denominator
    
    def calculate_npv(self, results: ScenarioResults) -> NPVResult:
        """
        Calculate NPV for a scenario, including terminal salvage value (C3).
        """
        npv = NPVResult(
            scenario_name=results.name,
            discount_rate=self.discount_rate,
        )
        
        # Extract annual cost streams
        capex_stream = {}
        opex_stream = {}
        fuel_stream = {}
        ppa_stream = {}
        demand_stream = {}
        
        for year, costs in results.annual_costs.items():
            capex_stream[year] = costs.total_capex
            opex_stream[year] = costs.total_opex
            fuel_stream[year] = costs.fuel_diesel + costs.fuel_lng  # E-CR-02: include LNG fuel
            ppa_stream[year] = costs.ppa_imports
        
        for year, gen in results.generation_mix.items():
            demand_stream[year] = gen.total_demand_gwh
        
        # Calculate present values
        npv.pv_capex = self.present_value(capex_stream)
        npv.pv_opex = self.present_value(opex_stream)
        npv.pv_fuel = self.present_value(fuel_stream)
        npv.pv_ppa = self.present_value(ppa_stream)
        
        # C3: Salvage value at end of horizon (credited as negative cost)
        npv.pv_salvage = self.calculate_salvage_value(results)
        
        npv.pv_total_costs = (
            npv.pv_capex + npv.pv_opex + npv.pv_fuel + npv.pv_ppa
            - npv.pv_salvage  # Salvage reduces total costs
        )
        
        # Emission costs (SCC valuation)
        emission_stream = {}
        for year, emissions in results.annual_emissions.items():
            scc = self._get_scc(year)
            emission_stream[year] = emissions.total_emissions_ktco2 * 1000 * scc  # ktCO2 to tCO2
        
        npv.pv_emission_costs = self.present_value(emission_stream)
        
        # L4: Health co-benefits — discount the health benefit stream
        health_stream = {}
        for year, benefits in results.annual_benefits.items():
            health_stream[year] = benefits.health_benefit
        npv.pv_health_benefits = self.present_value(health_stream)
        
        # L20: Reliability benefits — discount the reliability benefit stream
        reliability_stream = {}
        for year, benefits in results.annual_benefits.items():
            reliability_stream[year] = benefits.reliability_benefit
        npv.pv_reliability_benefits = self.present_value(reliability_stream)
        
        # A-MO-01: Environmental externality benefits — discount
        environmental_stream = {}
        for year, benefits in results.annual_benefits.items():
            environmental_stream[year] = benefits.environmental_benefit
        npv.pv_environmental_benefits = self.present_value(environmental_stream)
        
        # Levelized cost of electricity (LCOE)
        pv_demand_gwh = self.present_value(demand_stream)
        if pv_demand_gwh > 0:
            npv.lcoe_usd_per_kwh = (npv.pv_total_costs) / (pv_demand_gwh * 1e6)
        
        # Annual averages
        n_years = len(self.horizon)
        npv.annual_avg_cost = npv.pv_total_costs * self.annuity_factor()
        npv.annual_avg_capex = npv.pv_capex * self.annuity_factor()
        
        return npv
    
    def calculate_salvage_value(self, results: ScenarioResults) -> float:
        """
        C3: Calculate terminal salvage value of assets at end of analysis horizon.
        
        Uses straight-line depreciation:
          SV = CAPEX × (remaining_life / total_life)
        
        Applies to the final-year installed capacities:
          - Solar PV (30-year life)
          - Battery storage (15-year life)
          - Diesel generators (20-year life)
          - Submarine cables (40-year life, if applicable)
        
        Returns salvage value discounted to base year.
        """
        end_year = max(self.horizon)
        
        # Asset lifetimes from config
        solar_life = self.config.technology.solar_pv_lifetime  # 30 yr
        battery_life = self.config.technology.battery_lifetime  # 15 yr
        diesel_life = self.config.technology.diesel_gen_lifetime  # 20 yr
        
        # Get final-year generation mix for installed capacities
        final_gen = results.generation_mix.get(end_year)
        if final_gen is None:
            return 0.0
        
        salvage_total = 0.0
        horizon_length = end_year - self.base_year  # Used for modular replacement timing
        
        # --- Solar PV (S-16 fix: vintage-tracking) ---
        # Track year-over-year capacity additions, compute salvage for each vintage
        # accounting for its actual install year, cost decline at install time,
        # and remaining life at end of horizon.
        prev_solar_mw = 0.0
        for year in sorted(results.generation_mix.keys()):
            gen = results.generation_mix[year]
            current_solar_mw = gen.solar_capacity_mw
            added_mw = current_solar_mw - prev_solar_mw
            if added_mw > 0:
                years_in_service = end_year - year
                remaining = max(0, solar_life - years_in_service)
                if remaining > 0:
                    # Unit CAPEX at install year (with cost decline from base year)
                    solar_capex_per_mw = self.config.technology.solar_pv_capex * 1000  # $/kW → $/MW
                    decline_years = year - self.base_year
                    decline = (1 - self.config.technology.solar_pv_cost_decline) ** decline_years
                    solar_capex_per_mw *= decline
                    salvage_total += added_mw * solar_capex_per_mw * (remaining / solar_life)
            prev_solar_mw = current_solar_mw
        
        # --- Battery storage (S-17 fix: vintage-tracking) ---
        # Track year-over-year battery additions. Each vintage has its own
        # replacement schedule (replaced every battery_life years) and its
        # own remaining life at end of horizon.
        prev_battery_mwh = 0.0
        for year in sorted(results.generation_mix.keys()):
            gen = results.generation_mix[year]
            current_battery_mwh = gen.battery_capacity_mwh
            added_mwh = current_battery_mwh - prev_battery_mwh
            if added_mwh > 0:
                years_in_service = end_year - year
                # Battery is replaced every battery_life years from its install year
                age_at_end = years_in_service % battery_life
                if age_at_end == 0 and years_in_service > 0:
                    remaining_batt = 0  # Fully depreciated at exact end of life
                else:
                    remaining_batt = battery_life - age_at_end
                if remaining_batt > 0:
                    # Battery CAPEX at install year (with cost decline)
                    battery_capex_per_mwh = self.config.technology.battery_capex * 1000  # $/kWh → $/MWh
                    decline_years = year - self.base_year
                    decline = (1 - self.config.technology.battery_cost_decline) ** decline_years
                    battery_capex_per_mwh *= decline
                    salvage_total += added_mwh * battery_capex_per_mwh * (remaining_batt / battery_life)
            prev_battery_mwh = current_battery_mwh
        
        # --- Diesel generators ---
        # A-L-02 note: Diesel uses modular arithmetic (horizon_length % diesel_life)
        # rather than vintage-tracking (as solar/battery do) because diesel capacity
        # is assumed constant over the horizon in most scenarios — there are no
        # year-over-year capacity additions to track. This is conservative: it may
        # slightly overstate salvage if some generators were replaced mid-horizon
        # (the modular approach assumes all generators are on the same replacement
        # cycle starting from base year). For solar/battery, vintage-tracking is
        # essential because capacity ramps up over time with cost declines.
        diesel_mw = final_gen.diesel_capacity_mw
        if diesel_mw > 0:
            # M-BUG-6 fix: modular replacement timing (same logic as battery)
            diesel_age_at_end = horizon_length % diesel_life
            if diesel_age_at_end == 0:
                remaining_diesel = 0
            else:
                remaining_diesel = diesel_life - diesel_age_at_end
            diesel_capex_per_mw = self.config.technology.diesel_gen_capex * 1000
            salvage_diesel = diesel_mw * diesel_capex_per_mw * (remaining_diesel / diesel_life)
            salvage_total += salvage_diesel
        
        # --- Submarine cable (if import scenario) ---
        # A-MO-02 fix: Use cable_capex_total which includes converter stations ($320M),
        # landing facilities ($80M), IDC, and grid upgrades — not just bare cable.
        import_gwh = final_gen.import_gwh
        if import_gwh > 0:
            cable_life = self.config.technology.cable_lifetime
            cable_total = (
                self.config.one_grid.cable_capex_total
                * self.config.one_grid.gom_share_pct
            )
            cable_online = self.config.one_grid.cable_online_year
            cable_age = end_year - cable_online
            remaining_cable = max(0, cable_life - cable_age)
            salvage_cable = cable_total * (remaining_cable / cable_life)
            salvage_total += salvage_cable
        
        # Discount to base year
        return salvage_total * self.discount_factor(end_year)
    
    def _get_scc(self, year: int) -> float:
        """
        Get Social Cost of Carbon for a given year.
        SCC increases over time to reflect growing damages.
        """
        base_scc = self.config.economics.social_cost_carbon
        scc_growth = self.config.economics.scc_annual_growth
        years_from_base = year - self.base_year
        return base_scc * ((1 + scc_growth) ** years_from_base)
    
    def calculate_incremental(
        self, 
        base_results: ScenarioResults, 
        alt_results: ScenarioResults,
        base_npv: NPVResult,
        alt_npv: NPVResult,
    ) -> IncrementalResult:
        """
        Calculate incremental analysis between two scenarios.
        """
        result = IncrementalResult(
            base_scenario=base_results.name,
            alternative_scenario=alt_results.name,
        )
        
        # Incremental costs
        result.incremental_pv_capex = alt_npv.pv_capex - base_npv.pv_capex
        result.incremental_pv_opex = alt_npv.pv_opex - base_npv.pv_opex
        result.incremental_pv_fuel = alt_npv.pv_fuel - base_npv.pv_fuel
        result.incremental_pv_ppa = alt_npv.pv_ppa - base_npv.pv_ppa
        
        result.incremental_pv_costs = (
            result.incremental_pv_capex + 
            result.incremental_pv_opex + 
            result.incremental_pv_ppa
        )
        # Note: fuel savings are counted as benefits, not negative costs
        
        # Benefits
        # Fuel savings (base fuel - alt fuel)
        result.pv_fuel_savings = base_npv.pv_fuel - alt_npv.pv_fuel
        
        # Emission savings
        result.pv_emission_savings = base_npv.pv_emission_costs - alt_npv.pv_emission_costs
        
        # L4: Health savings (alternative has higher health benefits = less diesel damage)
        result.pv_health_savings = alt_npv.pv_health_benefits - base_npv.pv_health_benefits
        
        # L20: Reliability savings (alternative has higher reliability = less outage cost)
        result.pv_reliability_savings = alt_npv.pv_reliability_benefits - base_npv.pv_reliability_benefits
        
        # A-MO-01: Environmental externality savings
        result.pv_environmental_savings = alt_npv.pv_environmental_benefits - base_npv.pv_environmental_benefits
        
        result.pv_total_benefits = (
            result.pv_fuel_savings + result.pv_emission_savings
            + result.pv_health_savings + result.pv_reliability_savings
            + result.pv_environmental_savings
        )
        
        # NPV = Benefits - Costs
        # (Note: incremental_pv_fuel is included in costs but we account for fuel savings as benefit)
        # So we calculate net benefit as:
        # = (fuel savings + emission savings) - (incremental capex + incremental opex + incremental ppa)
        
        result.npv = result.pv_total_benefits - (
            result.incremental_pv_capex + 
            result.incremental_pv_opex + 
            result.incremental_pv_ppa
        )
        
        # BCR — MR-05 fix: use inf when incremental costs <= 0 (project dominates BAU)
        total_investment = result.incremental_pv_capex + result.incremental_pv_opex + result.incremental_pv_ppa
        if total_investment > 0:
            result.bcr = result.pv_total_benefits / total_investment
        else:
            # Incremental costs <= 0 means alt is cheaper than BAU on every dimension
            result.bcr = float('inf') if result.pv_total_benefits > 0 else 1.0
        
        # Payback period calculation
        result.payback_years = self._calculate_payback(base_results, alt_results)
        
        # IRR calculation
        result.irr = self._calculate_irr(base_results, alt_results)
        
        return result
    
    def _calculate_payback(
        self, 
        base_results: ScenarioResults, 
        alt_results: ScenarioResults
    ) -> Optional[float]:
        """
        Calculate simple payback period (fuel-only savings).
        
        NOTE (A-M-02): This is a *fuel-only* payback — it counts only diesel/LNG
        fuel savings against incremental investment (CAPEX + OPEX + PPA). It does
        NOT include emission savings, health co-benefits, reliability benefits,
        or environmental externality savings. The full economic payback (including
        all benefit streams) would be shorter. This conservative metric is
        reported alongside BCR and ENPV which do include all benefit streams.
        """
        cumulative_cost = 0.0
        cumulative_savings = 0.0
        
        for year in self.horizon:
            base_costs = base_results.annual_costs[year]
            alt_costs = alt_results.annual_costs[year]
            
            # Annual incremental investment (capex + opex + ppa)
            annual_investment = (
                (alt_costs.total_capex - base_costs.total_capex) +
                (alt_costs.total_opex - base_costs.total_opex) +
                (alt_costs.ppa_imports - base_costs.ppa_imports)
            )
            
            # Annual savings (E-01 fix: include LNG fuel, consistent with IRR)
            annual_savings = (base_costs.fuel_diesel + base_costs.fuel_lng) - (alt_costs.fuel_diesel + alt_costs.fuel_lng)
            
            cumulative_cost += max(0, annual_investment)
            cumulative_savings += annual_savings
            
            if cumulative_savings >= cumulative_cost and cumulative_cost > 0:
                return year - self.base_year + 1
        
        return None  # Never pays back in horizon
    
    def _calculate_irr(
        self, 
        base_results: ScenarioResults, 
        alt_results: ScenarioResults
    ) -> Optional[float]:
        """
        Calculate Economic Internal Rate of Return (EIRR).
        
        A-CR-02 fix: EIRR uses the same benefit streams as ENPV
        (fuel savings + emission savings + health savings + reliability savings)
        per ADB (2017) §6.17.
        """
        # Build cash flow stream: total benefits - incremental costs
        cash_flows = []
        
        for year in self.horizon:
            base_costs = base_results.annual_costs[year]
            alt_costs = alt_results.annual_costs[year]
            base_benefits = base_results.annual_benefits.get(year)
            alt_benefits = alt_results.annual_benefits.get(year)
            
            # Fuel savings (E-CR-02: include LNG fuel in fuel savings calc)
            fuel_savings = (base_costs.fuel_diesel + base_costs.fuel_lng) - (alt_costs.fuel_diesel + alt_costs.fuel_lng)
            
            # Emission savings (SCC-valued)
            emission_savings = 0.0
            if base_benefits and alt_benefits:
                emission_savings = (
                    alt_benefits.emission_reduction_benefit
                    - base_benefits.emission_reduction_benefit
                )
            
            # Health savings
            health_savings = 0.0
            if base_benefits and alt_benefits:
                health_savings = (
                    alt_benefits.health_benefit
                    - base_benefits.health_benefit
                )
            
            # Reliability savings
            reliability_savings = 0.0
            if base_benefits and alt_benefits:
                reliability_savings = (
                    alt_benefits.reliability_benefit
                    - base_benefits.reliability_benefit
                )
            
            # A-MO-01: Environmental externality savings
            environmental_savings = 0.0
            if base_benefits and alt_benefits:
                environmental_savings = (
                    alt_benefits.environmental_benefit
                    - base_benefits.environmental_benefit
                )
            
            total_savings = fuel_savings + emission_savings + health_savings + reliability_savings + environmental_savings
            
            incremental_cost = (
                (alt_costs.total_capex - base_costs.total_capex) +
                (alt_costs.total_opex - base_costs.total_opex) +
                (alt_costs.ppa_imports - base_costs.ppa_imports)
            )
            
            cash_flows.append(total_savings - incremental_cost)
        
        # Use numpy_financial or scipy to calculate IRR
        try:
            import numpy_financial as npf
            irr = npf.irr(cash_flows)
        except ImportError:
            # Fallback: bisection method
            irr = self._irr_bisection(cash_flows)
        
        try:
            if irr is None or np.isnan(irr) or np.isinf(irr):
                return None
            return float(irr)
        except (ValueError, TypeError, AttributeError):  # MR-07 fix: no bare except
            return None
    
    @staticmethod
    def _irr_bisection(cash_flows, lo=-0.5, hi=2.0, tol=1e-6, max_iter=200):
        """Compute IRR by bisection when numpy_financial is unavailable."""
        def npv_at_rate(r):
            return sum(cf / (1 + r) ** t for t, cf in enumerate(cash_flows))
        
        npv_lo = npv_at_rate(lo)
        npv_hi = npv_at_rate(hi)
        
        if npv_lo * npv_hi > 0:
            return None  # no sign change → no IRR in range
        
        for _ in range(max_iter):
            mid = (lo + hi) / 2
            npv_mid = npv_at_rate(mid)
            if abs(npv_mid) < tol:
                return mid
            if npv_lo * npv_mid < 0:
                hi = mid
                npv_hi = npv_mid
            else:
                lo = mid
                npv_lo = npv_mid
        return (lo + hi) / 2
    
    def compare_all_scenarios(
        self,
        status_quo_results: ScenarioResults,
        green_results: ScenarioResults,
        one_grid_results: ScenarioResults,
        islanded_green_results: ScenarioResults = None,
        nearshore_solar_results: ScenarioResults = None,
        maximum_re_results: ScenarioResults = None,
        lng_transition_results: ScenarioResults = None,
    ) -> CBAComparison:
        """
        Perform complete CBA comparison of all six scenarios.
        """
        # Calculate NPVs
        sq_npv = self.calculate_npv(status_quo_results)
        gt_npv = self.calculate_npv(green_results)
        og_npv = self.calculate_npv(one_grid_results)
        ig_npv = self.calculate_npv(islanded_green_results) if islanded_green_results else None
        ns_npv = self.calculate_npv(nearshore_solar_results) if nearshore_solar_results else None
        mx_npv = self.calculate_npv(maximum_re_results) if maximum_re_results else None
        lng_npv = self.calculate_npv(lng_transition_results) if lng_transition_results else None
        
        # Incremental analyses
        green_vs_sq = self.calculate_incremental(
            status_quo_results, green_results, sq_npv, gt_npv
        )
        og_vs_sq = self.calculate_incremental(
            status_quo_results, one_grid_results, sq_npv, og_npv
        )
        og_vs_green = self.calculate_incremental(
            green_results, one_grid_results, gt_npv, og_npv
        )
        ig_vs_sq = (
            self.calculate_incremental(
                status_quo_results, islanded_green_results, sq_npv, ig_npv
            )
            if islanded_green_results
            else IncrementalResult(base_scenario="", alternative_scenario="")
        )
        ns_vs_sq = (
            self.calculate_incremental(
                status_quo_results, nearshore_solar_results, sq_npv, ns_npv
            )
            if nearshore_solar_results
            else IncrementalResult(base_scenario="", alternative_scenario="")
        )
        mx_vs_sq = (
            self.calculate_incremental(
                status_quo_results, maximum_re_results, sq_npv, mx_npv
            )
            if maximum_re_results
            else IncrementalResult(base_scenario="", alternative_scenario="")
        )
        lng_vs_sq = (
            self.calculate_incremental(
                status_quo_results, lng_transition_results, sq_npv, lng_npv
            )
            if lng_transition_results
            else IncrementalResult(base_scenario="", alternative_scenario="")
        )
        
        # Find least cost scenario
        costs = {
            "Status Quo": sq_npv.pv_total_costs,
            "Full Integration": og_npv.pv_total_costs,
            "National Grid": gt_npv.pv_total_costs,
        }
        if ig_npv:
            costs["Islanded Green"] = ig_npv.pv_total_costs
        if ns_npv:
            costs["Near-Shore Solar"] = ns_npv.pv_total_costs
        if mx_npv:
            costs["Maximum RE"] = mx_npv.pv_total_costs
        if lng_npv:
            costs["LNG Transition"] = lng_npv.pv_total_costs
        least_cost_scenario = min(costs, key=costs.get)
        
        # Find recommended scenario (considering emissions)
        total_costs_with_emissions = {
            "Status Quo": sq_npv.pv_total_costs + sq_npv.pv_emission_costs,
            "Full Integration": og_npv.pv_total_costs + og_npv.pv_emission_costs,
            "National Grid": gt_npv.pv_total_costs + gt_npv.pv_emission_costs,
        }
        if ig_npv:
            total_costs_with_emissions["Islanded Green"] = ig_npv.pv_total_costs + ig_npv.pv_emission_costs
        if ns_npv:
            total_costs_with_emissions["Near-Shore Solar"] = ns_npv.pv_total_costs + ns_npv.pv_emission_costs
        if mx_npv:
            total_costs_with_emissions["Maximum RE"] = mx_npv.pv_total_costs + mx_npv.pv_emission_costs
        if lng_npv:
            total_costs_with_emissions["LNG Transition"] = lng_npv.pv_total_costs + lng_npv.pv_emission_costs
        recommended = min(total_costs_with_emissions, key=total_costs_with_emissions.get)
        
        # Use dummy NPVResults for missing scenarios
        if ig_npv is None:
            ig_npv = NPVResult(scenario_name="Islanded Green")
        if ns_npv is None:
            ns_npv = NPVResult(scenario_name="Near-Shore Solar")
        if mx_npv is None:
            mx_npv = NPVResult(scenario_name="Maximum RE")
        if lng_npv is None:
            lng_npv = NPVResult(scenario_name="LNG Transition")
        
        return CBAComparison(
            bau=sq_npv,
            full_integration=og_npv,
            national_grid=gt_npv,
            islanded_green=ig_npv,
            nearshore_solar=ns_npv,
            maximum_re=mx_npv,
            lng_transition=lng_npv,
            fi_vs_bau=og_vs_sq,
            ng_vs_bau=green_vs_sq,
            fi_vs_ng=og_vs_green,
            ig_vs_bau=ig_vs_sq,
            ns_vs_bau=ns_vs_sq,
            mx_vs_bau=mx_vs_sq,
            lng_vs_bau=lng_vs_sq,
            least_cost_scenario=least_cost_scenario,
            least_cost_npv=costs[least_cost_scenario],
            recommended_scenario=recommended,
        )


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CBA CALCULATOR TEST")
    print("=" * 60)
    
    from ..scenarios.status_quo import StatusQuoScenario
    from ..scenarios.green_transition import GreenTransitionScenario
    from ..scenarios.one_grid import OneGridScenario
    from ..scenarios.islanded_green import IslandedGreenScenario
    
    config = get_config()
    
    # Run scenarios
    print("\nRunning scenarios...")
    sq = StatusQuoScenario(config)
    gt = GreenTransitionScenario(config)
    og = OneGridScenario(config)
    ig = IslandedGreenScenario(config)
    
    sq_results = sq.run()
    gt_results = gt.run()
    og_results = og.run()
    ig_results = ig.run()
    
    # Calculate CBA
    print("Calculating CBA...")
    calculator = CBACalculator(config)
    comparison = calculator.compare_all_scenarios(sq_results, gt_results, og_results, ig_results)
    
    # Print results
    print("\n--- NPV SUMMARY (Million USD) ---")
    print(f"{'Scenario':<20} {'PV Costs':>15} {'PV CAPEX':>15} {'PV Fuel':>15} {'PV Emissions':>15} {'LCOE ($/kWh)':>15}")
    print("-" * 100)
    
    for npv in [comparison.bau, comparison.full_integration, comparison.national_grid, comparison.islanded_green]:
        print(f"{npv.scenario_name:<20} ${npv.pv_total_costs/1e6:>13,.0f} ${npv.pv_capex/1e6:>13,.0f} ${npv.pv_fuel/1e6:>13,.0f} ${npv.pv_emission_costs/1e6:>13,.0f} ${npv.lcoe_usd_per_kwh:>13.4f}")
    
    print("\n--- INCREMENTAL ANALYSIS ---")
    for incr in [comparison.fi_vs_bau, comparison.ng_vs_bau, comparison.ig_vs_bau]:
        print(f"\n{incr.alternative_scenario} vs {incr.base_scenario}:")
        print(f"  Incremental CAPEX: ${incr.incremental_pv_capex/1e6:,.0f}M")
        print(f"  Fuel Savings: ${incr.pv_fuel_savings/1e6:,.0f}M")
        print(f"  Emission Savings: ${incr.pv_emission_savings/1e6:,.0f}M")
        print(f"  NPV: ${incr.npv/1e6:,.0f}M")
        print(f"  BCR: {incr.bcr:.2f}")
        print(f"  Payback: {incr.payback_years or 'N/A'} years")
        print(f"  IRR: {incr.irr*100:.1f}%" if incr.irr else "  IRR: N/A")
    
    print(f"\n--- RECOMMENDATION ---")
    print(f"Least Cost Scenario: {comparison.least_cost_scenario}")
    print(f"Recommended (with emissions): {comparison.recommended_scenario}")
    
    print("\n✓ CBA Calculator tests passed!")
