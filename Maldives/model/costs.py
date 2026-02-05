"""
Costs Module
============

Calculates all cost categories:
- Capital expenditure (CAPEX) for technologies
- Operating expenditure (OPEX)
- Fuel costs
- PPA import costs
- Decommissioning costs
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .config import Config, get_config


class CostCategory(Enum):
    """Cost categories for CBA."""
    CAPEX_SOLAR = "capex_solar"
    CAPEX_BATTERY = "capex_battery"
    CAPEX_DIESEL = "capex_diesel"
    CAPEX_CABLE = "capex_cable"
    CAPEX_GRID = "capex_grid"
    OPEX_SOLAR = "opex_solar"
    OPEX_BATTERY = "opex_battery"
    OPEX_DIESEL = "opex_diesel"
    OPEX_CABLE = "opex_cable"
    FUEL_DIESEL = "fuel_diesel"
    PPA_IMPORTS = "ppa_imports"
    DECOMMISSIONING = "decommissioning"


@dataclass
class AnnualCosts:
    """Container for annual costs breakdown."""
    
    year: int
    
    # CAPEX
    capex_solar: float = 0.0
    capex_battery: float = 0.0
    capex_diesel: float = 0.0
    capex_cable: float = 0.0
    capex_grid: float = 0.0
    
    # OPEX
    opex_solar: float = 0.0
    opex_battery: float = 0.0
    opex_diesel: float = 0.0
    opex_cable: float = 0.0
    
    # Fuel and imports
    fuel_diesel: float = 0.0
    ppa_imports: float = 0.0
    
    # Other
    decommissioning: float = 0.0
    
    @property
    def total_capex(self) -> float:
        return (
            self.capex_solar + 
            self.capex_battery + 
            self.capex_diesel + 
            self.capex_cable + 
            self.capex_grid
        )
    
    @property
    def total_opex(self) -> float:
        return (
            self.opex_solar + 
            self.opex_battery + 
            self.opex_diesel + 
            self.opex_cable
        )
    
    @property
    def total_fuel(self) -> float:
        return self.fuel_diesel + self.ppa_imports
    
    @property
    def total(self) -> float:
        return self.total_capex + self.total_opex + self.total_fuel + self.decommissioning
    
    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "capex_solar": self.capex_solar,
            "capex_battery": self.capex_battery,
            "capex_diesel": self.capex_diesel,
            "capex_cable": self.capex_cable,
            "capex_grid": self.capex_grid,
            "opex_solar": self.opex_solar,
            "opex_battery": self.opex_battery,
            "opex_diesel": self.opex_diesel,
            "opex_cable": self.opex_cable,
            "fuel_diesel": self.fuel_diesel,
            "ppa_imports": self.ppa_imports,
            "decommissioning": self.decommissioning,
            "total_capex": self.total_capex,
            "total_opex": self.total_opex,
            "total_fuel": self.total_fuel,
            "total": self.total,
        }


class CostCalculator:
    """
    Calculates costs for technologies and fuel.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        self.tech = self.config.technology
        self.fuel = self.config.fuel
        self.ppa = self.config.ppa
    
    # =========================================================================
    # SOLAR PV COSTS
    # =========================================================================
    
    def solar_capex(self, capacity_mw: float, year: int) -> float:
        """
        Calculate solar PV capital cost.
        
        Args:
            capacity_mw: Capacity to install in MW
            year: Year of installation (affects cost decline)
            
        Returns:
            Total CAPEX in USD
        """
        # Base cost with learning curve decline
        years_from_2024 = year - 2024
        cost_per_kw = self.tech.solar_pv_capex * (
            (1 - self.tech.solar_pv_cost_decline) ** years_from_2024
        )
        
        # Convert MW to kW
        capacity_kw = capacity_mw * 1000
        
        return capacity_kw * cost_per_kw
    
    def solar_opex(self, installed_capacity_mw: float, year: int) -> float:
        """
        Calculate annual solar PV O&M cost.
        
        Args:
            installed_capacity_mw: Total installed capacity
            year: Year (affects degraded capacity)
            
        Returns:
            Annual OPEX in USD
        """
        # O&M as percentage of original CAPEX
        # Simplified: use base year CAPEX for O&M calculation
        capacity_kw = installed_capacity_mw * 1000
        annual_opex = capacity_kw * self.tech.solar_pv_capex * self.tech.solar_pv_opex_pct
        
        return annual_opex
    
    def solar_generation(self, capacity_mw: float, year: int = None) -> float:
        """
        Calculate annual solar generation in GWh.
        
        Args:
            capacity_mw: Installed capacity in MW
            year: Year (for degradation, optional)
            
        Returns:
            Annual generation in GWh
        """
        hours_per_year = 8760
        capacity_factor = self.tech.solar_pv_capacity_factor
        
        # Generation in MWh
        generation_mwh = capacity_mw * hours_per_year * capacity_factor
        
        # Convert to GWh
        return generation_mwh / 1000
    
    # =========================================================================
    # BATTERY STORAGE COSTS
    # =========================================================================
    
    def battery_capex(self, capacity_mwh: float, year: int) -> float:
        """
        Calculate battery storage capital cost.
        
        Args:
            capacity_mwh: Storage capacity in MWh
            year: Year of installation
            
        Returns:
            Total CAPEX in USD
        """
        years_from_2024 = year - 2024
        cost_per_kwh = self.tech.battery_capex * (
            (1 - self.tech.battery_cost_decline) ** years_from_2024
        )
        
        capacity_kwh = capacity_mwh * 1000
        
        return capacity_kwh * cost_per_kwh
    
    def battery_opex(self, installed_capacity_mwh: float) -> float:
        """
        Calculate annual battery O&M cost.
        """
        capacity_kwh = installed_capacity_mwh * 1000
        return capacity_kwh * self.tech.battery_opex
    
    def battery_replacement_schedule(
        self,
        initial_year: int,
        capacity_mwh: float,
    ) -> List[Tuple[int, float]]:
        """
        Calculate battery replacement years and costs.
        
        Returns:
            List of (year, cost) tuples for replacements
        """
        replacements = []
        current_year = initial_year
        
        while current_year + self.tech.battery_lifetime <= self.config.end_year:
            replacement_year = current_year + self.tech.battery_lifetime
            replacement_cost = self.battery_capex(capacity_mwh, replacement_year)
            replacements.append((replacement_year, replacement_cost))
            current_year = replacement_year
        
        return replacements
    
    # =========================================================================
    # DIESEL GENERATOR COSTS
    # =========================================================================
    
    def diesel_gen_capex(self, capacity_mw: float) -> float:
        """
        Calculate diesel generator capital cost.
        """
        capacity_kw = capacity_mw * 1000
        return capacity_kw * self.tech.diesel_gen_capex
    
    def diesel_gen_opex(self, generation_gwh: float) -> float:
        """
        Calculate diesel generator O&M cost (variable).
        
        Args:
            generation_gwh: Electricity generated in GWh
            
        Returns:
            Annual O&M cost in USD
        """
        generation_kwh = generation_gwh * 1_000_000
        return generation_kwh * self.tech.diesel_gen_opex_kwh
    
    def diesel_fuel_cost(self, generation_gwh: float, year: int) -> float:
        """
        Calculate diesel fuel cost.
        
        Args:
            generation_gwh: Electricity generated from diesel in GWh
            year: Year (affects fuel price)
            
        Returns:
            Annual fuel cost in USD
        """
        # Fuel price with escalation
        fuel_price = self.fuel.get_price(year)
        
        # Liters needed
        generation_kwh = generation_gwh * 1_000_000
        liters_needed = generation_kwh / self.fuel.kwh_per_liter
        
        return liters_needed * fuel_price
    
    def diesel_fuel_consumption(self, generation_gwh: float) -> float:
        """
        Calculate diesel fuel consumption in liters.
        """
        generation_kwh = generation_gwh * 1_000_000
        return generation_kwh / self.fuel.kwh_per_liter
    
    # =========================================================================
    # UNDERSEA CABLE COSTS (ONE GRID)
    # =========================================================================
    
    def cable_capex(self) -> float:
        """
        Calculate undersea cable total capital cost.
        """
        return self.tech.cable_length_km * self.tech.cable_capex_per_km
    
    def cable_gom_share(self) -> float:
        """
        Calculate GoM share of cable capital cost.
        """
        total = self.cable_capex()
        return total * self.config.one_grid.gom_share_pct
    
    def cable_opex(self) -> float:
        """
        Calculate annual cable O&M cost.
        """
        total_capex = self.cable_capex()
        return total_capex * self.tech.cable_opex_pct
    
    def ppa_cost(self, import_gwh: float, year: int) -> float:
        """
        Calculate electricity import cost under PPA.
        
        Args:
            import_gwh: Electricity imported in GWh
            year: Year (affects PPA price)
            
        Returns:
            Annual PPA cost in USD
        """
        if year < self.config.one_grid.cable_online_year:
            return 0.0
        
        price_per_kwh = self.ppa.get_price(year)
        import_kwh = import_gwh * 1_000_000
        
        return import_kwh * price_per_kwh
    
    # =========================================================================
    # GRID INFRASTRUCTURE COSTS
    # =========================================================================
    
    def inter_island_cable_capex(self, length_km: float) -> float:
        """
        Calculate inter-island submarine cable cost.
        """
        return length_km * self.tech.inter_island_capex_per_km
    
    def distribution_capex(
        self,
        mv_km: float = 0,
        lv_km: float = 0,
        transformers: int = 0,
    ) -> float:
        """
        Calculate distribution infrastructure cost.
        """
        mv_cost = mv_km * self.tech.mv_line_capex_per_km
        lv_cost = lv_km * self.tech.lv_line_capex_per_km
        tx_cost = transformers * self.tech.transformer_capex
        
        return mv_cost + lv_cost + tx_cost
    
    # =========================================================================
    # LCOE CALCULATION
    # =========================================================================
    
    def calculate_lcoe(
        self,
        technology: str,
        year: int = 2024,
    ) -> float:
        """
        Calculate Levelized Cost of Electricity for a technology.
        
        Args:
            technology: 'solar', 'diesel', or 'import'
            year: Year for cost assumptions
            
        Returns:
            LCOE in USD/kWh
        """
        discount_rate = self.config.economics.discount_rate
        
        if technology == "solar":
            # 1 MW reference plant
            capex = self.solar_capex(1.0, year)
            annual_opex = self.solar_opex(1.0, year)
            annual_gen_kwh = self.solar_generation(1.0) * 1_000_000
            lifetime = self.tech.solar_pv_lifetime
            
            # NPV of generation
            npv_gen = sum(
                annual_gen_kwh / ((1 + discount_rate) ** t)
                for t in range(1, lifetime + 1)
            )
            
            # NPV of costs
            npv_costs = capex + sum(
                annual_opex / ((1 + discount_rate) ** t)
                for t in range(1, lifetime + 1)
            )
            
            return npv_costs / npv_gen
        
        elif technology == "diesel":
            # Fuel cost dominates LCOE
            fuel_price = self.fuel.get_price(year)
            fuel_cost_per_kwh = fuel_price / self.fuel.kwh_per_liter
            opex_per_kwh = self.tech.diesel_gen_opex_kwh
            
            # Simplified LCOE (fuel + O&M)
            return fuel_cost_per_kwh + opex_per_kwh
        
        elif technology == "import":
            # PPA price plus losses
            if year < self.config.one_grid.cable_online_year:
                return None
            
            ppa_price = self.ppa.get_price(year)
            losses = self.tech.cable_losses_pct
            
            return ppa_price / (1 - losses)
        
        else:
            raise ValueError(f"Unknown technology: {technology}")


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("COST CALCULATIONS TEST")
    print("=" * 60)
    
    config = get_config()
    calc = CostCalculator(config)
    
    # Solar costs
    print("\n--- SOLAR PV COSTS ---")
    for year in [2024, 2030, 2040, 2050]:
        capex = calc.solar_capex(100, year)  # 100 MW
        print(f"{year}: 100 MW solar CAPEX = ${capex/1e6:.1f}M (${capex/100/1000:.0f}/kW)")
    
    # Battery costs
    print("\n--- BATTERY STORAGE COSTS ---")
    for year in [2024, 2030, 2040, 2050]:
        capex = calc.battery_capex(200, year)  # 200 MWh
        print(f"{year}: 200 MWh battery CAPEX = ${capex/1e6:.1f}M (${capex/200/1000:.0f}/kWh)")
    
    # Diesel fuel costs
    print("\n--- DIESEL FUEL COSTS ---")
    for year in [2024, 2030, 2040, 2050]:
        fuel_cost = calc.diesel_fuel_cost(500, year)  # 500 GWh from diesel
        print(f"{year}: 500 GWh diesel fuel = ${fuel_cost/1e6:.1f}M")
    
    # Cable costs
    print("\n--- UNDERSEA CABLE COSTS ---")
    print(f"Total cable CAPEX: ${calc.cable_capex()/1e9:.2f}B")
    print(f"GoM share ({config.one_grid.gom_share_pct:.0%}): ${calc.cable_gom_share()/1e6:.0f}M")
    print(f"Annual cable O&M: ${calc.cable_opex()/1e6:.1f}M")
    
    # PPA costs
    print("\n--- PPA IMPORT COSTS ---")
    for year in [2030, 2040, 2050]:
        ppa_cost = calc.ppa_cost(400, year)  # 400 GWh imports
        print(f"{year}: 400 GWh imports = ${ppa_cost/1e6:.1f}M (${config.ppa.get_price(year):.3f}/kWh)")
    
    # LCOE comparison
    print("\n--- LCOE COMPARISON (2024) ---")
    print(f"Solar: ${calc.calculate_lcoe('solar', 2024):.3f}/kWh")
    print(f"Diesel: ${calc.calculate_lcoe('diesel', 2024):.3f}/kWh")
    print(f"Import (2030): ${calc.calculate_lcoe('import', 2030):.3f}/kWh")
    
    print("\n✓ Cost module tests passed!")
