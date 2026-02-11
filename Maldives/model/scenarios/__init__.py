"""
Scenario Module
===============

Abstract base class and 7 scenario implementations for the Maldives Energy CBA.

Active scenarios:
  S1 BAU (StatusQuoScenario) — Diesel status quo
  S2 Full Integration (FullIntegrationScenario) — India submarine cable + progressive grid
  S3 National Grid (NationalGridScenario) — Progressive grid, no India cable
  S4 Islanded Green (IslandedGreenScenario) — Per-island solar+battery
  S5 Near-Shore Solar (NearShoreSolarScenario) — Uninhabited island solar farms
  S6 Maximum RE (MaximumREScenario) — Rooftop + nearshore + floating solar
  S7 LNG Transition (LNGTransitionScenario) — 140 MW LNG on Gulhifalhu
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from ..config import Config, get_config
from ..demand import DemandProjector, SectoralDemand
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
    battery_discharge_gwh: float = 0.0  # Informational only (D-01): not used in cost/benefit calcs; records dispatch output for reporting
    import_gwh: float = 0.0       # India cable import (S2 Full Integration only)
    lng_gwh: float = 0.0          # MR-03: LNG generation (S7 LNG Transition only)
    wte_gwh: float = 0.0          # R6: Waste-to-energy baseload
    wind_gwh: float = 0.0          # Wind generation (S6 Maximum RE only)
    
    # Capacity (MW)
    diesel_capacity_mw: float = 0.0
    solar_capacity_mw: float = 0.0
    battery_capacity_mwh: float = 0.0
    
    @property
    def total_generation_gwh(self) -> float:
        return self.diesel_gwh + self.solar_gwh + self.import_gwh + self.lng_gwh + self.wte_gwh + self.wind_gwh
    
    @property
    def diesel_share(self) -> float:
        if self.total_generation_gwh == 0:
            return 0.0
        return self.diesel_gwh / self.total_generation_gwh
    
    @property
    def re_share(self) -> float:
        """RE share includes solar + WTE + wind (all renewable)."""
        if self.total_generation_gwh == 0:
            return 0.0
        return (self.solar_gwh + self.wte_gwh + self.wind_gwh) / self.total_generation_gwh
    
    @property
    def import_share(self) -> float:
        if self.total_generation_gwh == 0:
            return 0.0
        return self.import_gwh / self.total_generation_gwh
    
    @property
    def lng_share(self) -> float:
        """MR-03: LNG share of total generation."""
        if self.total_generation_gwh == 0:
            return 0.0
        return self.lng_gwh / self.total_generation_gwh
    
    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "total_demand_gwh": self.total_demand_gwh,
            "diesel_gwh": self.diesel_gwh,
            "solar_gwh": self.solar_gwh,
            "battery_discharge_gwh": self.battery_discharge_gwh,
            "import_gwh": self.import_gwh,
            "lng_gwh": self.lng_gwh,
            "wte_gwh": self.wte_gwh,
            "wind_gwh": self.wind_gwh,
            "diesel_capacity_mw": self.diesel_capacity_mw,
            "solar_capacity_mw": self.solar_capacity_mw,
            "battery_capacity_mwh": self.battery_capacity_mwh,
            "diesel_share": self.diesel_share,
            "re_share": self.re_share,
            "import_share": self.import_share,
            "lng_share": self.lng_share,
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
    
    # Physical pollutant reduction detail (tonnes avoided)
    pm25_avoided_tonnes: float = 0.0
    nox_avoided_tonnes: float = 0.0
    
    # L16: Environmental externalities (noise, spill risk, biodiversity)
    environmental_benefit: float = 0.0
    
    # R8: Fiscal subsidy avoidance (government saves subsidy per kWh of diesel replaced)
    fiscal_subsidy_savings: float = 0.0
    
    # Energy security (qualitative, not monetized here)
    
    @property
    def total(self) -> float:
        """Economic benefits total — excludes fiscal transfers (A-CR-01 fix)."""
        return (
            self.fuel_savings +
            self.emission_reduction_benefit +
            self.reliability_benefit +
            self.health_benefit +
            self.environmental_benefit
        )
    
    @property
    def total_with_fiscal(self) -> float:
        """Total including fiscal subsidy avoidance (for fiscal reporting only)."""
        return self.total + self.fiscal_subsidy_savings
    
    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "fuel_savings": self.fuel_savings,
            "emission_reduction_benefit": self.emission_reduction_benefit,
            "reliability_benefit": self.reliability_benefit,
            "health_benefit": self.health_benefit,
            "pm25_avoided_tonnes": self.pm25_avoided_tonnes,
            "nox_avoided_tonnes": self.nox_avoided_tonnes,
            "environmental_benefit": self.environmental_benefit,
            "fiscal_subsidy_savings": self.fiscal_subsidy_savings,
            "total_benefits": self.total,
            "total_benefits_with_fiscal": self.total_with_fiscal,
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
    
    # M5: Sectoral demand breakdown
    sectoral_demand: Dict[int, SectoralDemand] = field(default_factory=dict)
    
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
        
        # LW-01: Precompute temperature-derated capacity factor (constant for Maldives climate)
        self._effective_solar_cf = self._compute_effective_cf()
    
    def _compute_effective_cf(self) -> float:
        """
        LW-01: Compute temperature-derated solar capacity factor.
        
        Extracted from duplicated blocks in 6 scenario deployment schedules.
        Uses IEC 61215 temp derating with NOCT cell temperature model:
            T_cell = T_ambient + NOCT_coeff × (GHI / 24)
            CF_eff = CF_raw × max(0, 1 - k_t × (T_cell - 25))
        
        Returns:
            Effective capacity factor (dimensionless, ~0.167 for Maldives)
        """
        raw_cf = self.config.technology.solar_pv_capacity_factor
        ghi = self.config.technology.default_ghi
        t_amb = self.config.technology.default_ambient_temp
        noct_coeff = self.config.technology.pv_noct_coeff
        k_t = self.config.technology.pv_temp_derating_coeff
        ghi_kw_m2 = ghi / 24.0
        t_cell = t_amb + noct_coeff * ghi_kw_m2
        temp_derating = max(0.0, 1.0 - k_t * (t_cell - 25.0))
        return raw_cf * temp_derating
    
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
        baseline_gen_mix: GenerationMix = None,
    ) -> AnnualBenefits:
        """
        Calculate benefits for a specific year relative to baseline.
        
        Default implementation. Can be overridden.
        """
        benefits = AnnualBenefits(year=year)
        
        # Fuel savings relative to baseline
        # E-CR-02 fix: net fuel savings = (baseline total fuel) - (scenario total fuel)
        # This properly accounts for LNG fuel costs, not just diesel
        if baseline_costs:
            baseline_fuel = baseline_costs.fuel_diesel + baseline_costs.fuel_lng
            scenario_fuel = costs.fuel_diesel + costs.fuel_lng
            benefits.fuel_savings = baseline_fuel - scenario_fuel
            # E-4-2: negative savings are valid (scenario uses more fuel) — let them flow through to NPV
        
        # Emission reduction benefits (M-BUG-2: pass year for SCC growth)
        if baseline_emissions:
            benefits.emission_reduction_benefit = self.emissions_calc.emission_reduction_benefit(
                baseline_emissions.total_emissions_tco2,
                emissions.total_emissions_tco2,
                year=year,
            )
        
        # Health benefits (from reduced diesel)
        # S-05 fix: use baseline_gen_mix.diesel_gwh directly instead of
        # fragile backward-calculation from fuel cost / fuel price * kWh/L
        # health_damage_cost_per_mwh is in USD/MWh; diesel_reduction in GWh → ×1e3 for MWh
        if baseline_gen_mix is not None:
            diesel_baseline_gwh = baseline_gen_mix.diesel_gwh
            if gen_mix.diesel_gwh < diesel_baseline_gwh:
                diesel_reduction = diesel_baseline_gwh - gen_mix.diesel_gwh
                diesel_reduction_mwh = diesel_reduction * 1e3
                benefits.health_benefit = diesel_reduction_mwh * self.config.economics.health_damage_cost_per_mwh
                
                # Physical pollutant avoided (detail for report)
                benefits.pm25_avoided_tonnes = diesel_reduction_mwh * self.config.economics.pm25_emission_factor
                benefits.nox_avoided_tonnes = diesel_reduction_mwh * self.config.economics.nox_emission_factor
                
                # L16: Environmental externalities (noise, spill risk, biodiversity)
                benefits.environmental_benefit = self.cost_calc.environmental_externality_benefit(
                    diesel_reduction
                )
                
                # R8: Fiscal subsidy avoidance
                # Government subsidizes electricity at $0.15/kWh (gap between cost-of-service
                # and retail tariff). Each GWh of diesel displaced reduces the subsidy burden.
                # This is a fiscal transfer benefit, distinct from economic fuel savings.
                # Item-7: Time-varying subsidy — linear phase-out per tariff reform schedule
                subsidy_rate = self.config.current_system.get_subsidy_per_kwh(year)
                benefits.fiscal_subsidy_savings = (
                    diesel_reduction * 1e6  # GWh → kWh
                    * subsidy_rate
                )
        
        # L20: Reliability benefit — SAIDI/VOLL valuation
        # Diesel-dependent systems suffer frequent outages (SAIDI = 200 min/yr).
        # RE diversification + battery backup reduce outage duration.
        # Benefit = SAIDI_reduction_hours × VOLL × annual_demand_MWh
        # SAIDI reduction is proportional to RE share improvement:
        #   - Higher RE share → less single-fuel dependency → fewer outages
        #   - Capped: interconnection (import) gives best reliability
        # Cable import is discounted by cable availability (outage risk):
        #   availability ≈ 1 - lambda × mean_repair_months / 12
        if baseline_gen_mix is not None:
            baseline_re = baseline_gen_mix.re_share + baseline_gen_mix.import_share
            # Discount cable import share by cable availability factor
            cable_outage = self.config.cable_outage
            mean_outage_months = (cable_outage.min_outage_months + cable_outage.max_outage_months) / 2.0
            cable_availability = 1.0 - cable_outage.outage_rate_per_yr * mean_outage_months / 12.0
            effective_import = gen_mix.import_share * cable_availability
            scenario_re = gen_mix.re_share + effective_import
            re_improvement = max(0, scenario_re - baseline_re)
            # SAIDI reduction fraction: each 1% RE improvement reduces SAIDI by ~1%
            # (conservative linear assumption)
            saidi_reduction_fraction = min(re_improvement, self.config.dispatch.max_saidi_reduction_fraction)  # CR-08: from config
            saidi_baseline_hours = self.config.current_system.saidi_minutes / 60.0
            saidi_reduction_hours = saidi_baseline_hours * saidi_reduction_fraction
            demand_mwh = gen_mix.total_demand_gwh * 1e3
            benefits.reliability_benefit = (
                saidi_reduction_hours * self.config.economics.voll * demand_mwh
            )
        
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
            
            # M5: Calculate sectoral demand breakdown
            self.results.sectoral_demand[year] = self.demand.get_sectoral_demand(year)
        
        # V7: Validate solar deployment against physical land constraints
        self._validate_solar_land_constraints()
        
        self._calculated = True
        return self.results
    
    def _validate_solar_land_constraints(self) -> None:
        """
        V7: Check that aggregate solar deployment does not exceed the physical
        land ceiling on inhabited islands. Nearshore and floating solar are
        excluded from this check since they use uninhabited islands / water.
        
        Prints warnings for any year where ground-mount solar exceeds the
        national physical ceiling (2,873 MW for 134 km² at 15% utilization).
        """
        ceiling_mw = self.config.technology.max_ground_mount_solar_mw
        
        violations = []
        for year, gm in self.results.generation_mix.items():
            # Get ground-mount solar (subclasses override _non_ground_solar_mw)
            non_ground = self._non_ground_solar_mw(year)
            ground_solar_mw = max(0.0, gm.solar_capacity_mw - non_ground)
            
            if ground_solar_mw > ceiling_mw:
                pct = ground_solar_mw / ceiling_mw * 100
                violations.append((year, ground_solar_mw, pct))
        
        if violations:
            import warnings
            first_year, first_mw, first_pct = violations[0]
            last_year, last_mw, last_pct = violations[-1]
            warnings.warn(
                f"[{self.name}] V7 SOLAR LAND CONSTRAINT VIOLATION: "
                f"Ground-mount solar exceeds physical ceiling ({ceiling_mw:.0f} MW) "
                f"in {len(violations)} years ({first_year}–{last_year}). "
                f"Peak: {last_mw:.0f} MW ({last_pct:.0f}% of ceiling)."
            )
    
    def _non_ground_solar_mw(self, year: int) -> float:
        """Return MW of non-ground-mount solar deployed in a given year.
        
        Override in S5/S6 scenarios to subtract nearshore and floating solar
        from the land constraint check. Default: 0 (all solar is ground-mount).
        """
        return 0.0
    
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
            baseline_gen_mix = baseline_results.generation_mix.get(year)
            
            benefits = self.calculate_annual_benefits(
                year=year,
                gen_mix=gen_mix,
                costs=costs,
                emissions=emissions,
                baseline_costs=baseline_costs,
                baseline_emissions=baseline_emissions,
                baseline_gen_mix=baseline_gen_mix,
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
            "total_connection_million": costs_df["capex_connection"].sum() / 1e6 if "capex_connection" in costs_df.columns else 0.0,
            "total_emissions_mtco2": emissions_df["total_emissions_tco2"].sum() / 1e6,
            # G-MO-01: cumulative diesel GWh for MCA health criterion (physical metric)
            "total_diesel_gwh": gen_df["diesel_gwh"].sum(),
            "final_re_share": gen_df.iloc[-1]["re_share"],
            "final_diesel_share": gen_df.iloc[-1]["diesel_share"],
            # M5: Sectoral demand snapshot for final year
            "sectoral_demand_2050": (
                self.results.sectoral_demand[self.config.end_year].to_dict()
                if self.config.end_year in self.results.sectoral_demand else None
            ),
        }


# Import scenario classes for convenience
from .status_quo import StatusQuoScenario
from .green_transition import NationalGridScenario
from .one_grid import FullIntegrationScenario
from .islanded_green import IslandedGreenScenario
from .nearshore_solar import NearShoreSolarScenario
from .maximum_re import MaximumREScenario
from .lng_transition import LNGTransitionScenario

# Backward compatibility aliases
GreenTransitionScenario = NationalGridScenario
OneGridScenario = FullIntegrationScenario

__all__ = [
    # Base classes
    "BaseScenario",
    "ScenarioResults",
    "GenerationMix",
    "AnnualBenefits",
    # Active scenario implementations (S1–S7)
    "StatusQuoScenario",        # S1 BAU
    "FullIntegrationScenario",  # S2 Full Integration (India Cable)
    "NationalGridScenario",     # S3 National Grid
    "IslandedGreenScenario",    # S4 Islanded Green
    "NearShoreSolarScenario",   # S5 Near-Shore Solar
    "MaximumREScenario",        # S6 Maximum RE
    "LNGTransitionScenario",    # S7 LNG Transition
    # Backward compatibility aliases
    "GreenTransitionScenario",
    "OneGridScenario",
]