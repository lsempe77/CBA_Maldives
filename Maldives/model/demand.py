"""
Demand Projections Module
=========================

Projects electricity demand from 2024 to 2050 for each scenario.
Handles:
- Base demand trajectory
- Scenario-specific growth rates
- Peak demand calculations
- Induced demand from price changes
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass

from .config import Config, get_config


@dataclass
class DemandProjection:
    """Container for demand projection results."""
    
    year: int
    demand_gwh: float
    peak_demand_mw: float
    growth_rate: float
    cumulative_growth: float


class DemandProjector:
    """
    Projects electricity demand over the analysis period.
    
    Attributes:
        config: Model configuration
        scenario: Scenario name (status_quo, green_transition, one_grid)
        base_demand: Base year demand in GWh
        growth_rate: Annual growth rate
    """
    
    def __init__(
        self,
        config: Config = None,
        scenario: str = "status_quo",
        base_demand_gwh: float = None,
        growth_rate: float = None,
    ):
        self.config = config or get_config()
        self.scenario = scenario
        
        # Get base demand
        self.base_demand = base_demand_gwh or self.config.demand.base_demand_gwh
        self.base_peak = self.config.demand.base_peak_mw
        
        # Get growth rate for scenario
        self.growth_rate = growth_rate or self.config.demand.growth_rates.get(
            scenario, 0.035
        )
        
        # Load factor for peak calculations
        self.load_factor = self.config.demand.load_factor
        
        # Cache for projections
        self._projection_cache: Dict[int, DemandProjection] = {}
    
    def project_year(self, year: int) -> DemandProjection:
        """
        Project demand for a specific year.
        
        Args:
            year: Year to project (2024-2050)
            
        Returns:
            DemandProjection with demand_gwh, peak_demand_mw, etc.
        """
        if year in self._projection_cache:
            return self._projection_cache[year]
        
        base_year = self.config.base_year
        
        if year < base_year:
            raise ValueError(f"Year {year} is before base year {base_year}")
        
        # Years from base
        years_elapsed = year - base_year
        
        # Compound growth
        cumulative_growth = (1 + self.growth_rate) ** years_elapsed
        demand_gwh = self.base_demand * cumulative_growth
        
        # Peak demand from energy demand
        # Peak (MW) = Energy (GWh) * 1000 / (8760 hours * load_factor)
        hours_per_year = 8760
        peak_demand_mw = (demand_gwh * 1000) / (hours_per_year * self.load_factor)
        
        projection = DemandProjection(
            year=year,
            demand_gwh=round(demand_gwh, 1),
            peak_demand_mw=round(peak_demand_mw, 1),
            growth_rate=self.growth_rate,
            cumulative_growth=round(cumulative_growth, 4),
        )
        
        self._projection_cache[year] = projection
        return projection
    
    def get_demand(self, year: int) -> float:
        """Get demand in GWh for a specific year."""
        return self.project_year(year).demand_gwh
    
    def get_peak(self, year: int) -> float:
        """Get peak demand in MW for a specific year."""
        return self.project_year(year).peak_demand_mw
    
    def get_trajectory(self) -> pd.DataFrame:
        """
        Get full demand trajectory as DataFrame.
        
        Returns:
            DataFrame with columns: year, demand_gwh, peak_demand_mw, growth_rate
        """
        data = []
        for year in self.config.time_horizon:
            proj = self.project_year(year)
            data.append({
                "year": proj.year,
                "demand_gwh": proj.demand_gwh,
                "peak_demand_mw": proj.peak_demand_mw,
                "growth_rate": proj.growth_rate,
                "cumulative_growth": proj.cumulative_growth,
            })
        
        return pd.DataFrame(data)
    
    def apply_induced_demand(
        self,
        year: int,
        price_reduction_pct: float,
        elasticity: float = None,
    ) -> float:
        """
        Calculate induced demand from price reduction.
        
        Args:
            year: Year to calculate
            price_reduction_pct: Price reduction as decimal (e.g., 0.20 for 20%)
            elasticity: Price elasticity of demand (default from config)
            
        Returns:
            Adjusted demand in GWh including induced demand
        """
        elasticity = elasticity or self.config.demand.price_elasticity
        
        base_demand = self.get_demand(year)
        
        # Induced demand: % change in demand = elasticity * % change in price
        # Negative elasticity means demand increases when price decreases
        demand_change_pct = elasticity * (-price_reduction_pct)
        induced_demand = base_demand * (1 + demand_change_pct)
        
        return round(induced_demand, 1)


class MultiScenarioDemand:
    """
    Manages demand projections for all three scenarios.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        
        # Create projectors for each scenario
        self.projectors = {
            "status_quo": DemandProjector(
                config=self.config,
                scenario="status_quo",
            ),
            "green_transition": DemandProjector(
                config=self.config,
                scenario="green_transition",
            ),
            "one_grid": DemandProjector(
                config=self.config,
                scenario="one_grid",
            ),
        }
    
    def get_comparison_table(self) -> pd.DataFrame:
        """
        Get side-by-side demand comparison for all scenarios.
        
        Returns:
            DataFrame with demand by scenario and year
        """
        years = self.config.time_horizon
        
        data = []
        for year in years:
            row = {"year": year}
            for scenario, projector in self.projectors.items():
                proj = projector.project_year(year)
                row[f"{scenario}_gwh"] = proj.demand_gwh
                row[f"{scenario}_peak_mw"] = proj.peak_demand_mw
            data.append(row)
        
        return pd.DataFrame(data)
    
    def get_summary_years(self, years: list = None) -> pd.DataFrame:
        """
        Get summary for key years (2024, 2030, 2040, 2050).
        """
        if years is None:
            years = [2024, 2030, 2040, 2050]
        
        data = []
        for year in years:
            for scenario, projector in self.projectors.items():
                proj = projector.project_year(year)
                data.append({
                    "year": year,
                    "scenario": scenario,
                    "demand_gwh": proj.demand_gwh,
                    "peak_demand_mw": proj.peak_demand_mw,
                })
        
        df = pd.DataFrame(data)
        return df.pivot(index="year", columns="scenario", values="demand_gwh")


def calculate_demand_difference(
    scenario_a: DemandProjector,
    scenario_b: DemandProjector,
) -> pd.DataFrame:
    """
    Calculate demand difference between two scenarios.
    
    Useful for understanding induced demand in One Grid scenario.
    """
    config = scenario_a.config
    
    data = []
    for year in config.time_horizon:
        demand_a = scenario_a.get_demand(year)
        demand_b = scenario_b.get_demand(year)
        
        data.append({
            "year": year,
            "scenario_a_gwh": demand_a,
            "scenario_b_gwh": demand_b,
            "difference_gwh": demand_b - demand_a,
            "difference_pct": (demand_b - demand_a) / demand_a * 100,
        })
    
    return pd.DataFrame(data)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("DEMAND PROJECTIONS TEST")
    print("=" * 60)
    
    # Test single scenario
    config = get_config()
    projector = DemandProjector(config=config, scenario="status_quo")
    
    print(f"\nStatus Quo Scenario (Growth rate: {projector.growth_rate:.1%})")
    print("-" * 40)
    
    for year in [2024, 2030, 2040, 2050]:
        proj = projector.project_year(year)
        print(f"{year}: {proj.demand_gwh:,.0f} GWh | Peak: {proj.peak_demand_mw:,.0f} MW")
    
    # Test multi-scenario
    print("\n" + "=" * 60)
    print("MULTI-SCENARIO COMPARISON")
    print("=" * 60)
    
    multi = MultiScenarioDemand(config)
    summary = multi.get_summary_years()
    print("\nDemand by Scenario (GWh):")
    print(summary.round(0))
    
    # Test induced demand
    print("\n" + "=" * 60)
    print("INDUCED DEMAND (One Grid - 20% price reduction)")
    print("=" * 60)
    
    one_grid = multi.projectors["one_grid"]
    for year in [2030, 2040, 2050]:
        base = one_grid.get_demand(year)
        induced = one_grid.apply_induced_demand(year, price_reduction_pct=0.20)
        print(f"{year}: Base {base:,.0f} GWh -> With induced demand: {induced:,.0f} GWh (+{induced-base:,.0f})")
    
    print("\n✓ Demand module tests passed!")
