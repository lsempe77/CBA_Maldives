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
    capex_connection: float = 0.0  # L11: last-mile household connections
    capex_wte: float = 0.0  # R6: waste-to-energy plant CAPEX
    capex_lng: float = 0.0  # E-3-4: LNG plant CAPEX (S7 LNG Transition)
    capex_wind: float = 0.0  # Wind turbine CAPEX (S6 Maximum RE)
    
    # OPEX
    opex_solar: float = 0.0
    opex_battery: float = 0.0
    opex_diesel: float = 0.0
    opex_cable: float = 0.0
    opex_wte: float = 0.0  # R6: waste-to-energy O&M
    opex_wind: float = 0.0  # Wind turbine O&M
    
    # Fuel and imports
    fuel_diesel: float = 0.0
    fuel_lng: float = 0.0  # E-CR-02: LNG fuel cost (separate from ppa_imports)
    ppa_imports: float = 0.0
    
    # Supply security (L2: idle fleet + expected outage premium — Full Integration only)
    supply_security: float = 0.0
    
    # Other
    decommissioning: float = 0.0
    
    @property
    def total_capex(self) -> float:
        return (
            self.capex_solar + 
            self.capex_battery + 
            self.capex_diesel + 
            self.capex_cable + 
            self.capex_grid +
            self.capex_connection +
            self.capex_wte +
            self.capex_lng +  # E-3-4: include LNG CAPEX
            self.capex_wind  # Wind CAPEX
        )
    
    @property
    def total_opex(self) -> float:
        return (
            self.opex_solar + 
            self.opex_battery + 
            self.opex_diesel + 
            self.opex_cable +
            self.opex_wte +
            self.opex_wind +
            self.supply_security
        )
    
    @property
    def total_fuel(self) -> float:
        return self.fuel_diesel + self.fuel_lng + self.ppa_imports
    
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
            "capex_connection": self.capex_connection,
            "capex_wte": self.capex_wte,
            "opex_solar": self.opex_solar,
            "opex_battery": self.opex_battery,
            "opex_diesel": self.opex_diesel,
            "opex_cable": self.opex_cable,
            "opex_wte": self.opex_wte,
            "fuel_diesel": self.fuel_diesel,
            "fuel_lng": self.fuel_lng,
            "ppa_imports": self.ppa_imports,
            "supply_security": self.supply_security,
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
    
    def solar_capex_at_year(self, year: int) -> float:
        """
        C-CR-01 fix: Return total solar CAPEX (USD) for 1 MW at given year.
        Used by vintage O&M tracking in solar_opex().
        
        Args:
            year: Year of installation
            
        Returns:
            Total CAPEX in USD for 1 MW
        """
        return self.solar_capex(capacity_mw=1.0, year=year)
    
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
        years_from_base = year - self.config.base_year
        cost_per_kw = self.tech.solar_pv_capex * (
            (1 - self.tech.solar_pv_cost_decline) ** years_from_base
        )
        
        # Convert MW to kW
        capacity_kw = capacity_mw * 1000
        
        # Climate adaptation premium for coastal infrastructure
        capex = capacity_kw * cost_per_kw
        capex *= (1 + self.tech.climate_adaptation_premium)
        
        return capex
    
    def learning_curve_solar_capex(self, capacity_mw: float, year: int) -> float:
        """
        P6: Calculate solar PV CAPEX using endogenous learning curve (Wright's Law).
        
        C_t = C_0 × (Q_t / Q_0)^(-α)
        where α = ln(1 - LR) / ln(2), LR = learning rate (20%)
        Q_t = cumulative global deployment at time t
        
        This replaces the exogenous 4%/yr decline with a deployment-driven
        cost trajectory. Costs decline faster when deployment is high, slower
        when markets saturate.
        
        References:
            Wright, T.P. (1936). J. Aeronautical Sciences 3(4):122-128.
            Rubin, E.S. et al. (2015). Energy & Environmental Policy 3(2).
            IRENA (2024). Renewable Power Generation Costs 2023.
        
        Args:
            capacity_mw: Capacity to install in MW
            year: Year of installation
            
        Returns:
            Total CAPEX in USD
        """
        import math
        
        years_from_base = year - self.config.base_year
        lr = self.tech.solar_learning_rate  # 0.20
        alpha = -math.log(1 - lr) / math.log(2)  # ~0.322 for 20% LR
        
        # Cumulative deployment: Q_t = Q_0 + annual_addition × years
        q_0 = self.tech.solar_global_cumulative_gw_2026
        q_t = q_0 + self.tech.solar_global_annual_addition_gw * max(0, years_from_base)
        
        # Cost ratio
        cost_ratio = (q_t / q_0) ** (-alpha)
        cost_per_kw = self.tech.solar_pv_capex * cost_ratio
        
        capacity_kw = capacity_mw * 1000
        capex = capacity_kw * cost_per_kw
        capex *= (1 + self.tech.climate_adaptation_premium)
        
        return capex
    
    def solar_opex(self, installed_capacity_mw: float, year: int, solar_additions: dict = None) -> float:
        """
        Calculate annual solar PV O&M cost.
        
        MR-02 fix: Uses vintage-weighted CAPEX for O&M calculation.
        Panels installed in later years at lower CAPEX should have proportionally
        lower O&M costs.
        
        Args:
            installed_capacity_mw: Total installed capacity
            year: Year (affects degraded capacity)
            solar_additions: Dict {install_year: MW} for vintage tracking
            
        Returns:
            Annual OPEX in USD
        """
        if solar_additions is not None and len(solar_additions) > 0:
            # MR-02: Vintage-weighted O&M — each cohort uses its install-year CAPEX
            total_opex = 0.0
            for install_year, mw in solar_additions.items():
                if install_year <= year:
                    # solar_capex_at_year returns total CAPEX for 1 MW; divide by 1000 to get $/kW
                    vintage_capex_per_kw = self.solar_capex_at_year(install_year) / 1000 if mw > 0 else self.tech.solar_pv_capex
                    total_opex += mw * 1000 * vintage_capex_per_kw * self.tech.solar_pv_opex_pct
            return total_opex
        else:
            # Fallback: base-year CAPEX (for status_quo / simple scenarios)
            # C-WC-05: include climate adaptation premium to match vintage path
            capacity_kw = installed_capacity_mw * 1000
            capex_with_climate = self.tech.solar_pv_capex * (1 + self.tech.climate_adaptation_premium)
            annual_opex = capacity_kw * capex_with_climate * self.tech.solar_pv_opex_pct
            return annual_opex
    
    def solar_generation(
        self,
        capacity_mw: float,
        year: int = None,
        install_year: int = None,
        ambient_temp_c: float = None,
        ghi_kwh_m2_day: float = None,
    ) -> float:
        """
        Calculate annual solar generation in GWh.
        
        Includes:
        - C7: Temperature derating (IEC 61215; OnSSET L186)
          P_out = P_STC × (1 - k_t × (T_cell - 25))
          T_cell = T_amb + NOCT_coeff × GHI_kW/m²
        - C8: Annual degradation (Jordan & Kurtz 2013; IRENA RPGC 2024)
          Output_year_n = Output_year_0 × (1 - deg_rate)^n
        
        Args:
            capacity_mw: Installed capacity in MW
            year: Current year (for degradation calculation)
            install_year: Year panels were installed (defaults to base_year)
            ambient_temp_c: Annual average ambient temperature (°C)
            ghi_kwh_m2_day: Average daily GHI in kWh/m²/day
            
        Returns:
            Annual generation in GWh
        """
        hours_per_year = 8760
        capacity_factor = self.tech.solar_pv_capacity_factor
        
        # Default climate values from config if not provided
        if ambient_temp_c is None:
            ambient_temp_c = self.tech.default_ambient_temp
        if ghi_kwh_m2_day is None:
            ghi_kwh_m2_day = self.tech.default_ghi
        
        # --- C7: Temperature derating ---
        # Cell temperature: T_cell = T_amb + NOCT_coeff × GHI (in kW/m²)
        # GHI in kW/m²: daily kWh/m² / peak sun hours ~ kW/m² at peak
        # OnSSET uses instantaneous W/m² but for annual average we use
        # daily GHI / 24 * 1000 to get avg W/m², then /1000 for kW/m²
        # Simplified: use daily GHI directly as proxy (GHI_kWh/m²/day ≈ peak kW/m² for ~5.5h)
        ghi_kw_m2 = ghi_kwh_m2_day / 24  # Average over 24h in kW/m²
        t_cell = ambient_temp_c + self.tech.pv_noct_coeff * ghi_kw_m2
        k_t = self.tech.pv_temp_derating_coeff
        temp_derating = max(0.0, 1.0 - k_t * (t_cell - 25.0))
        
        # --- C8: Annual degradation ---
        degradation_factor = 1.0
        if year is not None:
            if install_year is None:
                install_year = self.config.base_year
            years_operating = max(0, year - install_year)
            deg_rate = self.tech.solar_pv_degradation  # 0.005 = 0.5%/yr
            degradation_factor = (1.0 - deg_rate) ** years_operating
        
        # Generation in MWh
        generation_mwh = (
            capacity_mw * hours_per_year * capacity_factor
            * temp_derating
            * degradation_factor
        )
        
        # Convert to GWh
        return generation_mwh / 1000
    
    def solar_generation_vintaged(
        self,
        solar_additions: dict,
        year: int,
        existing_mw: float = 0.0,
        existing_install_year: int = None,
        ambient_temp_c: float = None,
        ghi_kwh_m2_day: float = None,
    ) -> float:
        """
        Calculate annual solar generation with vintage-based degradation.
        
        Each cohort of panels degrades from its actual install year, not
        from the base year.  This fixes the bug where calling
        solar_generation(total_mw, year=year) treats ALL panels as
        installed in base_year, over-degrading newer vintages.
        
        Args:
            solar_additions: Dict {install_year: mw_added} from scenario
            year: Current year
            existing_mw: Pre-existing capacity (installed before base_year)
            existing_install_year: When existing capacity was installed
                                   (defaults to base_year)
            ambient_temp_c: Annual average ambient temperature (°C)
            ghi_kwh_m2_day: Average daily GHI in kWh/m²/day
            
        Returns:
            Total annual generation in GWh (sum of all vintage outputs)
        """
        if existing_install_year is None:
            existing_install_year = self.config.base_year
        
        total_gwh = 0.0
        
        # Generation from pre-existing capacity
        if existing_mw > 0:
            total_gwh += self.solar_generation(
                existing_mw, year=year, install_year=existing_install_year,
                ambient_temp_c=ambient_temp_c, ghi_kwh_m2_day=ghi_kwh_m2_day,
            )
        
        # Generation from each vintage of new additions
        for install_yr, mw_added in solar_additions.items():
            if mw_added > 0 and install_yr <= year:
                total_gwh += self.solar_generation(
                    mw_added, year=year, install_year=install_yr,
                    ambient_temp_c=ambient_temp_c,
                    ghi_kwh_m2_day=ghi_kwh_m2_day,
                )
        
        return total_gwh
    
    def solar_generation_climate_adjusted(
        self,
        capacity_mw: float,
        year: int,
        rcp_scenario: str = 'baseline',
        install_year: int = None,
    ) -> float:
        """
        P7: Calculate solar generation with climate change adjustments.
        
        Adjusts GHI and ambient temperature linearly from base year to
        the climate scenario year (2050), based on RCP 4.5 or 8.5 projections.
        
        GHI_adjusted = GHI_base × (1 + ghi_change × progress)
        T_adjusted = T_base + temp_rise × progress
        
        where progress = (year - base_year) / (scenario_year - base_year)
        
        References:
            IPCC (2021). AR6 WG1 Ch.7, Table 7.2.
            Crook et al. (2011). Energy & Env. Science 4:3101.
            Wild et al. (2015). J. Geophys. Res. 120:8141.
        
        Args:
            capacity_mw: Installed solar capacity
            year: Current year
            rcp_scenario: 'baseline', 'rcp45', or 'rcp85'
            install_year: Year panels were installed
            
        Returns:
            Annual generation in GWh
        """
        tech = self.tech
        base_year = self.config.base_year
        scenario_year = tech.climate_scenario_year  # 2050
        
        # Climate progress fraction (0 at base_year, 1 at scenario_year)
        progress = max(0.0, min(1.0,
            (year - base_year) / (scenario_year - base_year)
        )) if scenario_year > base_year else 0.0
        
        # Adjust GHI and temperature based on RCP
        ghi_base = tech.default_ghi
        temp_base = tech.default_ambient_temp
        
        if rcp_scenario == 'rcp45':
            ghi_adjusted = ghi_base * (1 + tech.rcp45_ghi_change_2050 * progress)
            temp_adjusted = temp_base + tech.rcp45_temp_rise_2050 * progress
        elif rcp_scenario == 'rcp85':
            ghi_adjusted = ghi_base * (1 + tech.rcp85_ghi_change_2050 * progress)
            temp_adjusted = temp_base + tech.rcp85_temp_rise_2050 * progress
        else:
            ghi_adjusted = ghi_base
            temp_adjusted = temp_base
        
        return self.solar_generation(
            capacity_mw=capacity_mw,
            year=year,
            install_year=install_year,
            ambient_temp_c=temp_adjusted,
            ghi_kwh_m2_day=ghi_adjusted,
        )
    
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
        years_from_base = year - self.config.base_year
        cost_per_kwh = self.tech.battery_capex * (
            (1 - self.tech.battery_cost_decline) ** years_from_base
        )
        
        capacity_kwh = capacity_mwh * 1000
        
        # Climate adaptation premium for coastal infrastructure
        capex = capacity_kwh * cost_per_kwh
        capex *= (1 + self.tech.climate_adaptation_premium)
        
        return capex
    
    def learning_curve_battery_capex(self, capacity_mwh: float, year: int) -> float:
        """
        P6: Calculate battery CAPEX using endogenous learning curve (Wright's Law).
        
        C_t = C_0 × (Q_t / Q_0)^(-α)
        where α = ln(1 - LR) / ln(2), LR = learning rate (18%)
        
        References:
            Ziegler, M.S. & Trancik, J.E. (2021). Energy Policy 151.
            BNEF (2023). Battery Price Survey.
        
        Args:
            capacity_mwh: Storage capacity in MWh
            year: Year of installation
            
        Returns:
            Total CAPEX in USD
        """
        import math
        
        years_from_base = year - self.config.base_year
        lr = self.tech.battery_learning_rate  # 0.18
        alpha = -math.log(1 - lr) / math.log(2)  # ~0.286 for 18% LR
        
        q_0 = self.tech.battery_global_cumulative_gwh_2026
        q_t = q_0 + self.tech.battery_global_annual_addition_gwh * max(0, years_from_base)
        
        cost_ratio = (q_t / q_0) ** (-alpha)
        cost_per_kwh = self.tech.battery_capex * cost_ratio
        
        capacity_kwh = capacity_mwh * 1000
        capex = capacity_kwh * cost_per_kwh
        capex *= (1 + self.tech.climate_adaptation_premium)
        
        return capex
    
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
    
    def diesel_fuel_cost(
        self,
        generation_gwh: float,
        year: int,
        diesel_capacity_mw: float = None,
    ) -> float:
        """
        Calculate diesel fuel cost using two-part fuel curve (C9).
        
        Fuel curve (Mandelli et al. 2016; OnSSET onsset.py L266):
          fuel_litres = capacity_kW × idle_coeff × hours + generation_kWh × prop_coeff
        
        Falls back to flat efficiency if diesel_capacity_mw is not provided
        (backward compatibility).
        
        Args:
            generation_gwh: Electricity generated from diesel in GWh
            year: Year (affects fuel price)
            diesel_capacity_mw: Installed diesel capacity (enables two-part curve)
            
        Returns:
            Annual fuel cost in USD
        """
        fuel_price = self.fuel.get_price(year)
        liters_needed = self.diesel_fuel_consumption(
            generation_gwh, diesel_capacity_mw=diesel_capacity_mw
        )
        return liters_needed * fuel_price
    
    def diesel_fuel_consumption(
        self,
        generation_gwh: float,
        diesel_capacity_mw: float = None,
    ) -> float:
        """
        Calculate diesel fuel consumption in liters using two-part curve (C9).
        
        If diesel_capacity_mw is provided, uses:
          fuel = capacity_kW × 0.08145 × operating_hours + generation_kWh × 0.246
        Otherwise falls back to flat efficiency (generation / kwh_per_liter).
        
        Args:
            generation_gwh: Electricity generated in GWh
            diesel_capacity_mw: Installed diesel capacity in MW (optional)
            
        Returns:
            Fuel consumption in liters
        """
        generation_kwh = generation_gwh * 1_000_000
        
        if diesel_capacity_mw is not None and diesel_capacity_mw > 0:
            # C9: Two-part fuel curve (OnSSET L266, Mandelli et al. 2016)
            capacity_kw = diesel_capacity_mw * 1000
            idle_coeff = self.config.dispatch.fuel_curve_idle_coeff  # 0.08145 l/hr/kW
            prop_coeff = self.config.dispatch.fuel_curve_proportional_coeff  # 0.246 l/kWh
            
            # M-BUG-3 fix: estimate operating hours from generation and capacity
            # instead of assuming 8760h (which overstated idle fuel for high-RE scenarios)
            # operating_hours = generation / (capacity × assumed_load_fraction)
            # Use min_load_ratio as the assumed average load when running
            min_load = self.config.dispatch.diesel_min_load_fraction  # 0.40
            if capacity_kw > 0 and generation_kwh > 0:
                # Hours = energy / (capacity × average_load_when_running)
                # Average load when running ≈ midpoint between min_load and 1.0
                avg_load = (min_load + 1.0) / 2  # ~0.70
                hours = min(8760, generation_kwh / (capacity_kw * avg_load))
            else:
                hours = 0
            
            idle_fuel = capacity_kw * idle_coeff * hours
            proportional_fuel = generation_kwh * prop_coeff
            
            return idle_fuel + proportional_fuel
        else:
            # Fallback: flat efficiency — R4: use weighted (Malé 3.3 / outer 2.38)
            weighted_eff = self.config.weighted_diesel_efficiency(2026)
            return generation_kwh / weighted_eff
    
    # =========================================================================
    # T&D LOSSES (C2)
    # =========================================================================
    
    def gross_up_for_losses(
        self,
        net_demand_gwh: float,
        include_distribution: bool = True,
        include_hvdc: bool = False,
        year: int = None,
        scenario_growth_rate: float = 0.05,
    ) -> float:
        """
        Gross up net demand to account for T&D losses (C2 + R5).
        
        Generation must exceed consumption to cover losses:
          gross = net / (1 - loss)
        
        R5: If year is provided, uses weighted distribution loss
        (Malé 8%, outer 12%) based on demand share for that year.
        Otherwise falls back to flat national average (11%).
        
        Args:
            net_demand_gwh: End-user demand in GWh
            include_distribution: Apply island distribution losses
            include_hvdc: Apply HVDC cable losses (4%) — only for import scenarios
            year: Calendar year (enables R5 segmented losses)
            scenario_growth_rate: Passed to weighted_distribution_loss()
            
        Returns:
            Required gross generation in GWh
        """
        # Multiplicative losses — each stage compounds independently (M-BUG-1 fix)
        factor = 1.0
        if include_distribution:
            if year is not None:
                # R5: weighted distribution loss (Malé 8%, outer 12%)
                dist_loss = self.config.weighted_distribution_loss(year, scenario_growth_rate)
            else:
                # Fallback: flat national average
                dist_loss = self.tech.distribution_loss_pct
            factor /= (1.0 - dist_loss)
        if include_hvdc:
            factor /= (1.0 - self.tech.hvdc_cable_loss_pct)     # e.g. 1/0.96 = 1.042
        
        if factor > 10.0:
            raise ValueError(f"Implausible gross-up factor {factor:.2f} — check loss params")
        
        return net_demand_gwh * factor
    
    # =========================================================================
    # UNDERSEA CABLE COSTS (ONE GRID)
    # =========================================================================
    
    def cable_capex(self) -> float:
        """
        Calculate undersea cable total capital cost (C4 breakdown).
        
        Components:
        1. Submarine cable: length_km × CAPEX/km
        2. Converter stations (VSC-HVDC pair): capacity_MW × cost/MW
        3. Landing stations: num_landings × cost/end
        4. Interest During Construction (IDC): rate × (cable + converters + landing)
        5. Grid upgrade: Maldives-side reinforcement (fixed cost)
        6. Climate adaptation premium: applied to all components
        """
        # Use pre-computed total from config (includes all C4 components)
        capex = self.config.one_grid.cable_capex_total
        # Climate adaptation premium for submarine infrastructure
        capex *= (1 + self.tech.climate_adaptation_premium)
        return capex
    
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
    
    def connection_capex(self, num_households: int) -> float:
        """
        Calculate last-mile household connection cost (L11).
        
        Args:
            num_households: Number of households to connect
            
        Returns:
            Total connection CAPEX in USD
        """
        return num_households * self.config.connection.cost_per_household
    
    def environmental_externality_benefit(self, diesel_avoided_gwh: float) -> float:
        """
        Calculate environmental externality benefit from avoided diesel (L16).
        
        Includes noise damage, fuel spill risk, and biodiversity impact.
        
        Args:
            diesel_avoided_gwh: Diesel generation avoided vs baseline (GWh)
            
        Returns:
            Annual environmental benefit in USD
        """
        diesel_avoided_mwh = diesel_avoided_gwh * 1000
        econ = self.config.economics
        benefit_per_mwh = (
            econ.noise_damage_per_mwh
            + econ.fuel_spill_risk_per_mwh
            + econ.biodiversity_impact_per_mwh
        )
        return diesel_avoided_mwh * benefit_per_mwh
    
    # L25: distribution_capex() removed — dead code, never called by any scenario.
    # Last-mile costs are covered by connection_cost_per_household ($200/HH).
    # See CBA_METHODOLOGY.md §13.4 and IMPROVEMENT_PLAN.md L25.
    
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
            lifetime = self.tech.solar_pv_lifetime
            
            # NPV of generation (with degradation + temp derating per year)
            npv_gen = sum(
                self.solar_generation(1.0, year=year + t, install_year=year) * 1_000_000
                / ((1 + discount_rate) ** t)
                for t in range(1, lifetime + 1)
            )
            
            # NPV of costs
            npv_costs = capex + sum(
                annual_opex / ((1 + discount_rate) ** t)
                for t in range(1, lifetime + 1)
            )
            
            return npv_costs / npv_gen
        
        elif technology == "diesel":
            # M-BUG-5 fix: include amortized CAPEX in diesel LCOE
            # R4: Use weighted diesel efficiency (Malé 3.3, outer 2.38 kWh/L)
            fuel_price = self.fuel.get_price(year)
            weighted_eff = self.config.weighted_diesel_efficiency(year)
            fuel_cost_per_kwh = fuel_price / weighted_eff
            opex_per_kwh = self.tech.diesel_gen_opex_kwh
            
            # Amortized CAPEX: $/kW over lifetime, converted to $/kWh
            diesel_capex_per_kw = self.tech.diesel_gen_capex  # $/kW
            diesel_life = self.tech.diesel_gen_lifetime  # years
            cf = self.config.dispatch.diesel_avg_capacity_factor
            capex_per_kwh = diesel_capex_per_kw / (diesel_life * 8760 * cf)
            
            return fuel_cost_per_kwh + opex_per_kwh + capex_per_kwh
        
        elif technology == "import":
            # PPA price plus losses
            if year < self.config.one_grid.cable_online_year:
                return None
            
            ppa_price = self.ppa.get_price(year)
            # V3 fix: use hvdc_cable_loss_pct (4%, CSV-loaded) instead of
            # cable_losses_pct (3%, stale default) — see IMPROVEMENT_PLAN V3
            losses = self.tech.hvdc_cable_loss_pct
            
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
