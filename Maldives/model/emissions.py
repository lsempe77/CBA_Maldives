"""
Emissions Module
================

Calculates CO2 emissions for each scenario and monetizes using social cost of carbon.
"""

import pandas as pd
from typing import Dict, Optional
from dataclasses import dataclass

from .config import Config, get_config


@dataclass
class AnnualEmissions:
    """Container for annual emissions."""
    
    year: int
    diesel_emissions_tco2: float = 0.0
    import_emissions_tco2: float = 0.0
    solar_lifecycle_tco2: float = 0.0  # Minimal
    
    @property
    def total_emissions_tco2(self) -> float:
        return self.diesel_emissions_tco2 + self.import_emissions_tco2 + self.solar_lifecycle_tco2
    
    @property
    def total_emissions_ktco2(self) -> float:
        return self.total_emissions_tco2 / 1000
    
    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "diesel_emissions_tco2": self.diesel_emissions_tco2,
            "import_emissions_tco2": self.import_emissions_tco2,
            "solar_lifecycle_tco2": self.solar_lifecycle_tco2,
            "total_emissions_tco2": self.total_emissions_tco2,
            "total_emissions_ktco2": self.total_emissions_ktco2,
        }


class EmissionsCalculator:
    """
    Calculates greenhouse gas emissions.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        self.fuel = self.config.fuel
        self.ppa = self.config.ppa
        self.econ = self.config.economics
    
    def diesel_emissions(self, generation_gwh: float) -> float:
        """
        Calculate CO2 emissions from diesel generation.
        
        Args:
            generation_gwh: Electricity generated from diesel in GWh
            
        Returns:
            Emissions in tonnes CO2
        """
        generation_kwh = generation_gwh * 1_000_000
        emissions_kg = generation_kwh * self.fuel.emission_factor_kg_co2_per_kwh
        emissions_tonnes = emissions_kg / 1000
        
        return emissions_tonnes
    
    def import_emissions(self, import_gwh: float, year: int) -> float:
        """
        Calculate CO2 emissions from electricity imports (India grid).
        
        Args:
            import_gwh: Electricity imported in GWh
            year: Year (affects India grid emission factor)
            
        Returns:
            Emissions in tonnes CO2
        """
        if year < self.config.one_grid.cable_online_year:
            return 0.0
        
        # India grid emission factor (declining over time as India greens its grid)
        emission_factor = self.ppa.get_india_emission_factor(year)
        
        import_kwh = import_gwh * 1_000_000
        emissions_kg = import_kwh * emission_factor
        emissions_tonnes = emissions_kg / 1000
        
        return emissions_tonnes
    
    def solar_lifecycle_emissions(self, capacity_mw: float) -> float:
        """
        Calculate lifecycle emissions from solar PV manufacturing.
        
        Very small compared to operational emissions, but included for completeness.
        Typically ~40-50 gCO2/kWh over lifetime.
        
        Args:
            capacity_mw: Solar capacity installed
            
        Returns:
            Annualized lifecycle emissions in tonnes CO2
        """
        # Lifecycle emissions: ~40 gCO2/kWh, spread over 25-year lifetime
        lifecycle_g_per_kwh = 0.040  # 40 gCO2/kWh
        annual_gen_kwh = self.config.technology.solar_pv_capacity_factor * 8760 * capacity_mw * 1000
        
        emissions_g = annual_gen_kwh * lifecycle_g_per_kwh
        emissions_tonnes = emissions_g / 1_000_000
        
        return emissions_tonnes
    
    def monetize_emissions(self, emissions_tco2: float, year: int = None) -> float:
        """
        Monetize emissions using social cost of carbon.
        
        Args:
            emissions_tco2: Emissions in tonnes CO2
            year: Year (SCC could vary, but we use constant for simplicity)
            
        Returns:
            Emission cost in USD
        """
        scc = self.econ.social_cost_carbon
        return emissions_tco2 * scc
    
    def emission_reduction_benefit(
        self,
        baseline_emissions_tco2: float,
        scenario_emissions_tco2: float,
    ) -> float:
        """
        Calculate the benefit (avoided cost) from emission reductions.
        
        Args:
            baseline_emissions_tco2: Emissions under baseline (Status Quo)
            scenario_emissions_tco2: Emissions under alternative scenario
            
        Returns:
            Benefit in USD
        """
        reduction = baseline_emissions_tco2 - scenario_emissions_tco2
        if reduction < 0:
            return 0.0  # No benefit if emissions increase
        
        return self.monetize_emissions(reduction)
    
    def calculate_annual_emissions(
        self,
        diesel_gwh: float,
        import_gwh: float,
        solar_capacity_mw: float,
        year: int,
    ) -> AnnualEmissions:
        """
        Calculate all emission sources for a year.
        """
        return AnnualEmissions(
            year=year,
            diesel_emissions_tco2=self.diesel_emissions(diesel_gwh),
            import_emissions_tco2=self.import_emissions(import_gwh, year),
            solar_lifecycle_tco2=self.solar_lifecycle_emissions(solar_capacity_mw),
        )


class EmissionsTrajectory:
    """
    Tracks emissions over full analysis period.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        self.calculator = EmissionsCalculator(config)
        self.annual_data: Dict[int, AnnualEmissions] = {}
    
    def add_year(
        self,
        year: int,
        diesel_gwh: float,
        import_gwh: float = 0.0,
        solar_capacity_mw: float = 0.0,
    ) -> None:
        """Add emissions for a year."""
        emissions = self.calculator.calculate_annual_emissions(
            diesel_gwh=diesel_gwh,
            import_gwh=import_gwh,
            solar_capacity_mw=solar_capacity_mw,
            year=year,
        )
        self.annual_data[year] = emissions
    
    def get_cumulative_emissions(self) -> float:
        """Get total cumulative emissions over analysis period."""
        return sum(e.total_emissions_tco2 for e in self.annual_data.values())
    
    def get_cumulative_emissions_mt(self) -> float:
        """Get cumulative emissions in million tonnes."""
        return self.get_cumulative_emissions() / 1_000_000
    
    def get_trajectory_df(self) -> pd.DataFrame:
        """Get emissions trajectory as DataFrame."""
        data = [e.to_dict() for e in self.annual_data.values()]
        return pd.DataFrame(data).sort_values("year")
    
    def get_total_emission_cost(self) -> float:
        """Get total monetized emission cost over analysis period."""
        return sum(
            self.calculator.monetize_emissions(e.total_emissions_tco2)
            for e in self.annual_data.values()
        )


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("EMISSIONS CALCULATIONS TEST")
    print("=" * 60)
    
    config = get_config()
    calc = EmissionsCalculator(config)
    
    # Diesel emissions
    print("\n--- DIESEL EMISSIONS ---")
    for gwh in [500, 700, 850]:
        emissions = calc.diesel_emissions(gwh)
        cost = calc.monetize_emissions(emissions)
        print(f"{gwh} GWh diesel -> {emissions/1000:.1f} ktCO2 (SCC: ${cost/1e6:.1f}M)")
    
    # Import emissions (India grid)
    print("\n--- IMPORT EMISSIONS (India Grid) ---")
    for year in [2030, 2040, 2050]:
        ef = config.ppa.get_india_emission_factor(year)
        emissions = calc.import_emissions(400, year)
        print(f"{year}: 400 GWh imports @ {ef:.3f} kgCO2/kWh -> {emissions/1000:.1f} ktCO2")
    
    # Emission reduction benefit
    print("\n--- EMISSION REDUCTION BENEFIT ---")
    baseline = calc.diesel_emissions(850)  # Status quo
    green = calc.diesel_emissions(300) + calc.solar_lifecycle_emissions(200)
    reduction = baseline - green
    benefit = calc.emission_reduction_benefit(baseline, green)
    print(f"Baseline (850 GWh diesel): {baseline/1000:.1f} ktCO2")
    print(f"Green Transition (300 GWh diesel + 200 MW solar): {green/1000:.1f} ktCO2")
    print(f"Reduction: {reduction/1000:.1f} ktCO2")
    print(f"Annual benefit @ ${config.economics.social_cost_carbon}/tCO2: ${benefit/1e6:.1f}M")
    
    # Trajectory example
    print("\n--- STATUS QUO EMISSIONS TRAJECTORY ---")
    trajectory = EmissionsTrajectory(config)
    for year in range(2024, 2051):
        # Simple growth assumption
        diesel_gwh = 800 * (1.035 ** (year - 2024))
        trajectory.add_year(year, diesel_gwh=diesel_gwh)
    
    print(f"Cumulative emissions 2024-2050: {trajectory.get_cumulative_emissions_mt():.2f} MtCO2")
    print(f"Total emission cost: ${trajectory.get_total_emission_cost()/1e9:.2f}B")
    
    print("\n✓ Emissions module tests passed!")
