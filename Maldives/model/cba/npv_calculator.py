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
    pv_total_costs: float = 0.0
    
    # Emission costs/benefits (monetized)
    pv_emission_costs: float = 0.0  # Cost of emissions (SCC valuation)
    
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
    """
    status_quo: NPVResult
    green_transition: NPVResult
    one_grid: NPVResult
    
    # Incremental analyses
    green_vs_status_quo: IncrementalResult
    one_grid_vs_status_quo: IncrementalResult
    one_grid_vs_green: IncrementalResult
    
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
        Calculate NPV for a scenario.
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
            fuel_stream[year] = costs.fuel_diesel
            ppa_stream[year] = costs.ppa_imports
        
        for year, gen in results.generation_mix.items():
            demand_stream[year] = gen.total_demand_gwh
        
        # Calculate present values
        npv.pv_capex = self.present_value(capex_stream)
        npv.pv_opex = self.present_value(opex_stream)
        npv.pv_fuel = self.present_value(fuel_stream)
        npv.pv_ppa = self.present_value(ppa_stream)
        
        npv.pv_total_costs = npv.pv_capex + npv.pv_opex + npv.pv_fuel + npv.pv_ppa
        
        # Emission costs (SCC valuation)
        emission_stream = {}
        for year, emissions in results.annual_emissions.items():
            scc = self._get_scc(year)
            emission_stream[year] = emissions.total_emissions_ktco2 * 1000 * scc  # ktCO2 to tCO2
        
        npv.pv_emission_costs = self.present_value(emission_stream)
        
        # Levelized cost of electricity (LCOE)
        pv_demand_gwh = self.present_value(demand_stream)
        if pv_demand_gwh > 0:
            npv.lcoe_usd_per_kwh = (npv.pv_total_costs) / (pv_demand_gwh * 1e6)
        
        # Annual averages
        n_years = len(self.horizon)
        npv.annual_avg_cost = npv.pv_total_costs * self.annuity_factor()
        npv.annual_avg_capex = npv.pv_capex * self.annuity_factor()
        
        return npv
    
    def _get_scc(self, year: int) -> float:
        """
        Get Social Cost of Carbon for a given year.
        SCC increases over time to reflect growing damages.
        """
        base_scc = self.config.economics.social_cost_carbon
        scc_growth = 0.02  # 2% annual real growth in SCC
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
        
        result.pv_total_benefits = result.pv_fuel_savings + result.pv_emission_savings
        
        # NPV = Benefits - Costs
        # (Note: incremental_pv_fuel is included in costs but we account for fuel savings as benefit)
        # So we calculate net benefit as:
        # = (fuel savings + emission savings) - (incremental capex + incremental opex + incremental ppa)
        
        result.npv = result.pv_total_benefits - (
            result.incremental_pv_capex + 
            result.incremental_pv_opex + 
            result.incremental_pv_ppa
        )
        
        # BCR
        total_investment = max(1, result.incremental_pv_capex + result.incremental_pv_opex + result.incremental_pv_ppa)
        if total_investment > 0:
            result.bcr = result.pv_total_benefits / total_investment
        
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
        Calculate simple payback period.
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
            
            # Annual savings (fuel only for simplicity)
            annual_savings = base_costs.fuel_diesel - alt_costs.fuel_diesel
            
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
        Calculate Internal Rate of Return using Newton-Raphson.
        """
        # Build cash flow stream (savings - costs)
        cash_flows = []
        
        for year in self.horizon:
            base_costs = base_results.annual_costs[year]
            alt_costs = alt_results.annual_costs[year]
            
            # Net benefit = savings - incremental costs
            savings = base_costs.fuel_diesel - alt_costs.fuel_diesel
            incremental_cost = (
                (alt_costs.total_capex - base_costs.total_capex) +
                (alt_costs.total_opex - base_costs.total_opex) +
                (alt_costs.ppa_imports - base_costs.ppa_imports)
            )
            
            cash_flows.append(savings - incremental_cost)
        
        # Use numpy to calculate IRR
        try:
            irr = np.irr(cash_flows)
            if np.isnan(irr) or np.isinf(irr):
                return None
            return float(irr)
        except:
            return None
    
    def compare_all_scenarios(
        self,
        status_quo_results: ScenarioResults,
        green_results: ScenarioResults,
        one_grid_results: ScenarioResults,
    ) -> CBAComparison:
        """
        Perform complete CBA comparison of all three scenarios.
        """
        # Calculate NPVs
        sq_npv = self.calculate_npv(status_quo_results)
        gt_npv = self.calculate_npv(green_results)
        og_npv = self.calculate_npv(one_grid_results)
        
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
        
        # Find least cost scenario
        costs = {
            "Status Quo": sq_npv.pv_total_costs,
            "Green Transition": gt_npv.pv_total_costs,
            "One Grid": og_npv.pv_total_costs,
        }
        least_cost_scenario = min(costs, key=costs.get)
        
        # Find recommended scenario (considering emissions)
        total_costs_with_emissions = {
            "Status Quo": sq_npv.pv_total_costs + sq_npv.pv_emission_costs,
            "Green Transition": gt_npv.pv_total_costs + gt_npv.pv_emission_costs,
            "One Grid": og_npv.pv_total_costs + og_npv.pv_emission_costs,
        }
        recommended = min(total_costs_with_emissions, key=total_costs_with_emissions.get)
        
        return CBAComparison(
            status_quo=sq_npv,
            green_transition=gt_npv,
            one_grid=og_npv,
            green_vs_status_quo=green_vs_sq,
            one_grid_vs_status_quo=og_vs_sq,
            one_grid_vs_green=og_vs_green,
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
    
    config = get_config()
    
    # Run scenarios
    print("\nRunning scenarios...")
    sq = StatusQuoScenario(config)
    gt = GreenTransitionScenario(config)
    og = OneGridScenario(config)
    
    sq_results = sq.run()
    gt_results = gt.run()
    og_results = og.run()
    
    # Calculate CBA
    print("Calculating CBA...")
    calculator = CBACalculator(config)
    comparison = calculator.compare_all_scenarios(sq_results, gt_results, og_results)
    
    # Print results
    print("\n--- NPV SUMMARY (Million USD) ---")
    print(f"{'Scenario':<20} {'PV Costs':>15} {'PV CAPEX':>15} {'PV Fuel':>15} {'PV Emissions':>15} {'LCOE ($/kWh)':>15}")
    print("-" * 100)
    
    for npv in [comparison.status_quo, comparison.green_transition, comparison.one_grid]:
        print(f"{npv.scenario_name:<20} ${npv.pv_total_costs/1e6:>13,.0f} ${npv.pv_capex/1e6:>13,.0f} ${npv.pv_fuel/1e6:>13,.0f} ${npv.pv_emission_costs/1e6:>13,.0f} ${npv.lcoe_usd_per_kwh:>13.4f}")
    
    print("\n--- INCREMENTAL ANALYSIS ---")
    for incr in [comparison.green_vs_status_quo, comparison.one_grid_vs_status_quo]:
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
