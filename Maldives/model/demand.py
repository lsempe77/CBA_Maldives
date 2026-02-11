"""
Demand Projections Module
=========================

Projects electricity demand from 2026 to 2056 for each scenario.
Handles:
- Base demand trajectory
- Scenario-specific growth rates
- Peak demand calculations
- Induced demand from price changes

DEMAND SCOPE (R7):
  base_demand_2026 = 1,200 GWh is PUBLIC UTILITY demand only.
  This EXCLUDES resort sector (~1,050 GWh off-grid self-generated diesel).
  Total national electricity: ~2,250 GWh (1,200 utility + 1,050 resort).
  The Roadmap's 2,400 GWh figure INCLUDES resort demand.
  
  All scenario projections operate on the 1,200 GWh utility base.
  Resort emissions are reported separately for context (see run_cba.py).
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


@dataclass
class SectoralDemand:
    """M5: Disaggregated demand by sector.
    
    Splits total public grid demand into residential, commercial, and public
    sectors. Resorts are off-grid and excluded from this breakdown.
    Shares from SAARC 2005 Energy Balance (52/24/24 residential/commercial/public).
    """
    year: int
    total_gwh: float
    residential_gwh: float
    commercial_gwh: float
    public_gwh: float
    residential_share: float
    commercial_share: float
    public_share: float
    
    def to_dict(self) -> dict:
        return {
            'year': self.year,
            'total_gwh': self.total_gwh,
            'residential_gwh': round(self.residential_gwh, 2),
            'commercial_gwh': round(self.commercial_gwh, 2),
            'public_gwh': round(self.public_gwh, 2),
            'residential_share': self.residential_share,
            'commercial_share': self.commercial_share,
            'public_share': self.public_share,
        }


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
        # LW-10: base_peak_mw not stored — peak is always derived from
        # energy demand and load factor in project_year() for consistency
        
        # Get growth rate for scenario — must be defined in config
        if growth_rate is not None:
            self.growth_rate = growth_rate
        elif scenario in self.config.demand.growth_rates:
            self.growth_rate = self.config.demand.growth_rates[scenario]
        else:
            raise ValueError(
                f"No growth rate defined for scenario '{scenario}'. "
                f"Available: {list(self.config.demand.growth_rates.keys())}. "
                f"Add to parameters.csv or pass growth_rate explicitly."
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
        
        # A-M-01: Demand saturation ceiling (per-capita)
        # Cap demand when per-capita consumption reaches the ceiling.
        # Prevents unrealistic extrapolation (e.g., 5%/yr for 30 years would
        # yield ~14,000 kWh/capita — higher than Singapore). Once the ceiling
        # binds, demand grows only at the population growth rate.
        sat_ceiling = self.config.demand.demand_saturation_kwh_per_capita
        pop_base = self.config.current_system.population_2026
        pop_growth = self.config.current_system.population_growth_rate
        population = pop_base * ((1 + pop_growth) ** years_elapsed)
        max_demand_gwh = sat_ceiling * population / 1e6  # kWh → GWh
        if demand_gwh > max_demand_gwh:
            demand_gwh = max_demand_gwh
        
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
    
    def get_sectoral_demand(self, year: int) -> SectoralDemand:
        """M5: Disaggregate total demand into sectors.
        
        Applies static sectoral shares from config (parameters.csv).
        Shares are for public grid demand only — resorts are off-grid.
        
        Args:
            year: Year to calculate sectoral breakdown for
            
        Returns:
            SectoralDemand with residential, commercial, and public GWh
        """
        total = self.get_demand(year)
        res_share = self.config.demand.sectoral_residential
        com_share = self.config.demand.sectoral_commercial
        pub_share = self.config.demand.sectoral_public
        
        return SectoralDemand(
            year=year,
            total_gwh=total,
            residential_gwh=total * res_share,
            commercial_gwh=total * com_share,
            public_gwh=total * pub_share,
            residential_share=res_share,
            commercial_share=com_share,
            public_share=pub_share,
        )
    
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
        price_drop_fraction: float,  # C-WC-04: positive fraction (e.g. 0.20 = price 20% lower)
        elasticity: float = None,
    ) -> float:
        """
        Calculate induced demand from price reduction.
        
        L8: Activated for Full Integration scenario post-cable.
        Price reduction computed as (diesel_LCOE - PPA_price) / diesel_LCOE.
        Elasticity from config.demand.price_elasticity (default -0.3).
        
        Args:
            year: Year to calculate
            price_drop_fraction: Fraction by which price dropped (positive = cheaper,
                e.g. 0.20 means new price is 20% below baseline). Sign convention:
                elasticity < 0 and price_drop > 0 → demand increases.
            elasticity: Price elasticity of demand (default from config)
            
        Returns:
            Adjusted demand in GWh including induced demand
        """
        elasticity = elasticity or self.config.demand.price_elasticity
        
        base_demand = self.get_demand(year)
        
        # Induced demand: % change in demand = elasticity × (–price_drop_fraction)
        # Negative elasticity × negative price change → positive demand change
        demand_change_pct = elasticity * (-price_drop_fraction)
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
        induced = one_grid.apply_induced_demand(year, price_drop_fraction=0.20)
        print(f"{year}: Base {base:,.0f} GWh -> With induced demand: {induced:,.0f} GWh (+{induced-base:,.0f})")
    
    print("\n✓ Demand module tests passed!")
