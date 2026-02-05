"""
Base Scenario Module
====================

Abstract base class for all scenario implementations.
Defines the interface that Status Quo, Green Transition, and One Grid must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from ..config import Config, get_config
from ..demand import DemandProjector
from ..costs import CostCalculator, AnnualCosts
from ..emissions import EmissionsCalculator, AnnualEmissions


@dataclass
class GenerationMix:
    """Generation mix for a single year."""
    
    year: int
    total_demand_gwh: float
    
    # Generation by source (GWh)
    diesel_gwh: float = 0.0
    solar_gwh: float = 0.0
    battery_discharge_gwh: float = 0.0
    import_gwh: float = 0.0
    
    # Capacity (MW)
    diesel_capacity_mw: float = 0.0
    solar_capacity_mw: float = 0.0
    battery_capacity_mwh: float = 0.0
    
    @property
    def total_generation_gwh(self) -> float:
        return self.diesel_gwh + self.solar_gwh + self.import_gwh
    
    @property
    def diesel_share(self) -> float:
        if self.total_generation_gwh == 0:
            return 0.0
        return self.diesel_gwh / self.total_generation_gwh
    
    @property
    def re_share(self) -> float:
        if self.total_generation_gwh == 0:
            return 0.0
        return self.solar_gwh / self.total_generation_gwh
    
    @property
    def import_share(self) -> float:
        if self.total_generation_gwh == 0:
            return 0.0
        return self.import_gwh / self.total_generation_gwh
    
    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "total_demand_gwh": self.total_demand_gwh,
            "diesel_gwh": self.diesel_gwh,
            "solar_gwh": self.solar_gwh,
            "battery_discharge_gwh": self.battery_discharge_gwh,
            "import_gwh": self.import_gwh,
            "diesel_capacity_mw": self.diesel_capacity_mw,
            "solar_capacity_mw": self.solar_capacity_mw,
            "battery_capacity_mwh": self.battery_capacity_mwh,
            "diesel_share": self.diesel_share,
            "re_share": self.re_share,
            "import_share": self.import_share,
        }


@dataclass
class AnnualBenefits:
    """Benefits for a single year."""
    
    year: int
    
    # Fuel cost savings (vs Status Quo baseline)
    fuel_savings: float = 0.0
    
    # Emission reduction benefits
    emission_reduction_benefit: float = 0.0
    
    # Reliability improvement (VOLL)
    reliability_benefit: float = 0.0
    
    # Health co-benefits
    health_benefit: float = 0.0
    
    # Energy security (qualitative, not monetized here)
    
    @property
    def total(self) -> float:
        return (
            self.fuel_savings +
            self.emission_reduction_benefit +
            self.reliability_benefit +
            self.health_benefit
        )
    
    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "fuel_savings": self.fuel_savings,
            "emission_reduction_benefit": self.emission_reduction_benefit,
            "reliability_benefit": self.reliability_benefit,
            "health_benefit": self.health_benefit,
            "total_benefits": self.total,
        }


@dataclass
class ScenarioResults:
    """Complete results for a scenario."""
    
    name: str
    description: str
    
    # Time series data
    generation_mix: Dict[int, GenerationMix] = field(default_factory=dict)
    annual_costs: Dict[int, AnnualCosts] = field(default_factory=dict)
    annual_emissions: Dict[int, AnnualEmissions] = field(default_factory=dict)
    annual_benefits: Dict[int, AnnualBenefits] = field(default_factory=dict)
    
    def get_total_costs(self) -> float:
        """Sum of all costs over analysis period (undiscounted)."""
        return sum(c.total for c in self.annual_costs.values())
    
    def get_total_emissions(self) -> float:
        """Sum of all emissions over analysis period (tCO2)."""
        return sum(e.total_emissions_tco2 for e in self.annual_emissions.values())
    
    def get_total_benefits(self) -> float:
        """Sum of all benefits over analysis period (undiscounted)."""
        return sum(b.total for b in self.annual_benefits.values())
    
    def get_generation_df(self) -> pd.DataFrame:
        """Get generation mix as DataFrame."""
        data = [g.to_dict() for g in self.generation_mix.values()]
        return pd.DataFrame(data).sort_values("year")
    
    def get_costs_df(self) -> pd.DataFrame:
        """Get costs as DataFrame."""
        data = [c.to_dict() for c in self.annual_costs.values()]
        return pd.DataFrame(data).sort_values("year")
    
    def get_emissions_df(self) -> pd.DataFrame:
        """Get emissions as DataFrame."""
        data = [e.to_dict() for e in self.annual_emissions.values()]
        return pd.DataFrame(data).sort_values("year")
    
    def get_benefits_df(self) -> pd.DataFrame:
        """Get benefits as DataFrame."""
        data = [b.to_dict() for b in self.annual_benefits.values()]
        return pd.DataFrame(data).sort_values("year")
    
    def get_cash_flow_df(self) -> pd.DataFrame:
        """Get combined cash flows (costs, benefits, net)."""
        years = sorted(self.annual_costs.keys())
        
        data = []
        for year in years:
            costs = self.annual_costs.get(year)
            benefits = self.annual_benefits.get(year)
            emissions = self.annual_emissions.get(year)
            
            data.append({
                "year": year,
                "total_costs": costs.total if costs else 0,
                "total_benefits": benefits.total if benefits else 0,
                "net_flow": (benefits.total if benefits else 0) - (costs.total if costs else 0),
                "emissions_tco2": emissions.total_emissions_tco2 if emissions else 0,
            })
        
        return pd.DataFrame(data)


class BaseScenario(ABC):
    """
    Abstract base class for scenario implementations.
    
    All scenarios must implement:
    - calculate_generation_mix(year)
    - calculate_annual_costs(year)
    - calculate_annual_benefits(year, baseline)
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        config: Config = None,
    ):
        self.name = name
        self.description = description
        self.config = config or get_config()
        
        # Initialize calculators
        self.cost_calc = CostCalculator(self.config)
        self.emissions_calc = EmissionsCalculator(self.config)
        
        # Results container
        self.results = ScenarioResults(name=name, description=description)
        
        # Cache
        self._calculated = False
    
    @abstractmethod
    def _init_demand_projector(self) -> DemandProjector:
        """Initialize demand projector for this scenario."""
        pass
    
    @abstractmethod
    def calculate_generation_mix(self, year: int) -> GenerationMix:
        """
        Calculate generation mix for a specific year.
        
        Must be implemented by each scenario to define:
        - How much diesel generation
        - How much solar generation
        - How much imported electricity
        - Capacity additions/retirements
        """
        pass
    
    @abstractmethod
    def calculate_annual_costs(self, year: int, gen_mix: GenerationMix) -> AnnualCosts:
        """
        Calculate all costs for a specific year.
        
        Must be implemented by each scenario to define:
        - CAPEX for new capacity
        - OPEX for all technologies
        - Fuel costs
        - PPA costs (if applicable)
        """
        pass
    
    def calculate_annual_emissions(self, year: int, gen_mix: GenerationMix) -> AnnualEmissions:
        """
        Calculate emissions for a specific year.
        
        Default implementation uses EmissionsCalculator.
        Can be overridden if needed.
        """
        return self.emissions_calc.calculate_annual_emissions(
            diesel_gwh=gen_mix.diesel_gwh,
            import_gwh=gen_mix.import_gwh,
            solar_capacity_mw=gen_mix.solar_capacity_mw,
            year=year,
        )
    
    def calculate_annual_benefits(
        self,
        year: int,
        gen_mix: GenerationMix,
        costs: AnnualCosts,
        emissions: AnnualEmissions,
        baseline_costs: AnnualCosts = None,
        baseline_emissions: AnnualEmissions = None,
    ) -> AnnualBenefits:
        """
        Calculate benefits for a specific year relative to baseline.
        
        Default implementation. Can be overridden.
        """
        benefits = AnnualBenefits(year=year)
        
        # Fuel savings relative to baseline
        if baseline_costs:
            benefits.fuel_savings = baseline_costs.fuel_diesel - costs.fuel_diesel
            if benefits.fuel_savings < 0:
                benefits.fuel_savings = 0  # No negative "savings"
        
        # Emission reduction benefits
        if baseline_emissions:
            benefits.emission_reduction_benefit = self.emissions_calc.emission_reduction_benefit(
                baseline_emissions.total_emissions_tco2,
                emissions.total_emissions_tco2,
            )
        
        # Health benefits (from reduced diesel)
        if baseline_costs:
            diesel_reduction_gwh = baseline_costs.fuel_diesel / self.config.fuel.get_price(year) * self.config.fuel.kwh_per_liter / 1e6
            # Simplified: health benefit proportional to diesel reduction
            if gen_mix.diesel_gwh < (baseline_costs.fuel_diesel / self.config.fuel.get_price(year) * self.config.fuel.kwh_per_liter / 1e6):
                diesel_baseline_gwh = baseline_costs.fuel_diesel / self.config.fuel.get_price(year) * self.config.fuel.kwh_per_liter / 1e6
                diesel_reduction = diesel_baseline_gwh - gen_mix.diesel_gwh
                benefits.health_benefit = diesel_reduction * 1e6 * self.config.economics.health_benefit_per_kwh_diesel
        
        return benefits
    
    def run(self) -> ScenarioResults:
        """
        Run the scenario for all years.
        
        Returns:
            ScenarioResults with all annual data
        """
        if self._calculated:
            return self.results
        
        for year in self.config.time_horizon:
            # Calculate generation mix
            gen_mix = self.calculate_generation_mix(year)
            self.results.generation_mix[year] = gen_mix
            
            # Calculate costs
            costs = self.calculate_annual_costs(year, gen_mix)
            self.results.annual_costs[year] = costs
            
            # Calculate emissions
            emissions = self.calculate_annual_emissions(year, gen_mix)
            self.results.annual_emissions[year] = emissions
        
        self._calculated = True
        return self.results
    
    def calculate_benefits_vs_baseline(
        self,
        baseline_results: ScenarioResults,
    ) -> None:
        """
        Calculate benefits relative to a baseline scenario.
        
        Should be called after run() to populate benefits.
        """
        if not self._calculated:
            self.run()
        
        for year in self.config.time_horizon:
            gen_mix = self.results.generation_mix[year]
            costs = self.results.annual_costs[year]
            emissions = self.results.annual_emissions[year]
            
            baseline_costs = baseline_results.annual_costs.get(year)
            baseline_emissions = baseline_results.annual_emissions.get(year)
            
            benefits = self.calculate_annual_benefits(
                year=year,
                gen_mix=gen_mix,
                costs=costs,
                emissions=emissions,
                baseline_costs=baseline_costs,
                baseline_emissions=baseline_emissions,
            )
            
            self.results.annual_benefits[year] = benefits
    
    def get_summary(self) -> Dict:
        """Get summary statistics for the scenario."""
        if not self._calculated:
            self.run()
        
        costs_df = self.results.get_costs_df()
        emissions_df = self.results.get_emissions_df()
        gen_df = self.results.get_generation_df()
        
        return {
            "name": self.name,
            "total_costs_million": costs_df["total"].sum() / 1e6,
            "total_capex_million": costs_df["total_capex"].sum() / 1e6,
            "total_opex_million": costs_df["total_opex"].sum() / 1e6,
            "total_fuel_million": costs_df["total_fuel"].sum() / 1e6,
            "total_emissions_mtco2": emissions_df["total_emissions_tco2"].sum() / 1e6,
            "final_re_share": gen_df.iloc[-1]["re_share"],
            "final_diesel_share": gen_df.iloc[-1]["diesel_share"],
        }


# Import scenario classes for convenience
from .status_quo import StatusQuoScenario
from .green_transition import NationalGridScenario
from .one_grid import FullIntegrationScenario
from .islanded_green import IslandedGreenScenario

# Keep old names as aliases for backward compatibility
GreenTransitionScenario = NationalGridScenario
OneGridScenario = FullIntegrationScenario

__all__ = [
    # Base classes
    "BaseScenario",
    "ScenarioResults",
    "GenerationMix",
    "AnnualBenefits",
    # Scenario implementations (new names)
    "StatusQuoScenario",
    "NationalGridScenario",
    "FullIntegrationScenario",
    "IslandedGreenScenario",
    # Backward compatibility aliases
    "GreenTransitionScenario",
    "OneGridScenario",
]