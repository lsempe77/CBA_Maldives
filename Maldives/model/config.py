"""
Configuration Module
====================

Central configuration for all model parameters, paths, and assumptions.
All values are loaded from parameters.csv via load_parameters_from_csv().

Note: Values marked with # ESTIMATE need validation from experts/data sources.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from pathlib import Path
# yaml import removed — config loads from CSV, not YAML (L-BUG-3 fix)
import csv
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# TIME HORIZON
# =============================================================================

BASE_YEAR = 2026
END_YEAR_20 = 2046  # 20-year horizon
END_YEAR_30 = 2056  # 30-year horizon (default)
END_YEAR_50 = 2076  # 50-year horizon

# Default to 30-year horizon
END_YEAR = END_YEAR_30
TIME_HORIZON = list(range(BASE_YEAR, END_YEAR + 1))  # 31 years

# Available horizons
TIME_HORIZONS = {
    20: list(range(BASE_YEAR, END_YEAR_20 + 1)),
    30: list(range(BASE_YEAR, END_YEAR_30 + 1)),
    50: list(range(BASE_YEAR, END_YEAR_50 + 1)),
}


# =============================================================================
# SCENARIO DEFINITIONS (now in dataclass configs below)
# =============================================================================


# =============================================================================
# BASELINE DEMAND (2024)
# =============================================================================

@dataclass
class DemandConfig:
    """Electricity demand parameters."""
    
    base_demand_gwh: float = 1200.0  # IRENA 2022 (1025 GWh) × 1.05^4; validated by 2018 Data Book
    base_peak_mw: float = 200.0  # STELCO data + growth
    
    # Growth rates by scenario (can be overridden)
    # LW-09: All 7 scenarios explicitly listed (S4/S5/S6/S7 share green_transition rate)
    growth_rates: Dict[str, float] = field(default_factory=lambda: {
        "status_quo": 0.05,  # 5%/yr - UNDP/ISA/STELCO
        "green_transition": 0.04,  # 4%/yr with efficiency gains
        "one_grid": 0.05,  # L8: same as BAU; induced demand now via price_elasticity
        "islanded_green": 0.04,   # Same as green_transition (same demand drivers)
        "nearshore_solar": 0.04,  # Same as green_transition
        "maximum_re": 0.04,       # Same as green_transition
        "lng_transition": 0.05,   # Same as BAU (LNG doesn't change demand growth)
    })
    
    # Load factor (peak to average demand ratio)
    load_factor: float = 0.68  # 2018 Data Book: national 0.685, Malé 0.686
    
    # R1: Segmented Greater Malé demand growth (Roadmap §4.1.1)
    # Near-term 10% (STELCO Master Plan: Hulhumalé Phase 2/3 construction boom)
    # Tapers linearly to long-term rate by saturation_year
    # Post-peak: decelerates to 3.5% (density saturation, decentralization)
    male_growth_near_term: float = 0.10   # Greater Malé near-term growth
    male_growth_long_term: float = 0.06   # Rate at saturation year (before post-peak)
    male_post_peak_growth: float = 0.035  # H17: post-boom deceleration
    male_demand_min_share: float = 0.45   # H17: Floor on Malé share (Census 2022 + HDC)
    male_demand_saturation_year: int = 2035  # Year Malé growth converges to long-term
    
    # R2: Outer island growth (Roadmap §4.1.2 — guesthouse tourism boom)
    # Post-peak: accelerates to 6% (decentralization, ARISE targets)
    outer_growth_near_term: float = 0.07  # Outer islands near-term growth
    outer_growth_long_term: float = 0.05  # Converges to national rate
    outer_post_peak_growth: float = 0.06  # H17: outer accelerates post-2035
    outer_growth_taper_year: int = 2030   # Year outer island growth converges
    
    # R3: Resort island growth (Roadmap §4.1.3 — fixed capacity, off-grid)
    resort_growth_rate: float = 0.02  # Informational only (resorts off-grid)
    
    # Induced demand elasticity (for One Grid lower prices)
    price_elasticity: float = -0.3
    
    # A-M-01: Demand saturation ceiling (per-capita)
    # Demand growth is capped when per-capita consumption reaches this level.
    # Prevents unrealistic extrapolation beyond plausible consumption levels.
    demand_saturation_kwh_per_capita: float = 7000.0  # IEA WEO 2024: Singapore ~8,800
    
    # M5: Sectoral demand split (fraction of public grid demand)
    # Resorts are off-grid and excluded from public utility CBA
    # Source: SAARC 2005 Maldives Energy Balance (household 52%, commerce 24%, public 24%)
    sectoral_residential: float = 0.52  # Residential/household
    sectoral_commercial: float = 0.24  # Commercial/tourism spillover (guest houses, shops)
    sectoral_public: float = 0.24  # Public services (desalination, hospitals, schools, govt)
    
    # M1: Island demand intensity multipliers (by urbanisation tier)
    # Population thresholds: Urban >15k, Secondary 2k-15k, Rural <2k
    intensity_urban: float = 1.8   # Malé, Hulhumalé, Addu — higher per-capita demand
    intensity_secondary: float = 1.2  # Mid-size islands (2k-15k pop)
    intensity_rural: float = 0.6   # Small outer islands (<2k pop)
    urban_pop_threshold: int = 15_000  # Census 2022 — Malé/Hulhumalé/Addu exceed 15k
    secondary_pop_threshold: int = 2_000  # Census 2022 — distinguishes mid-size from small


# =============================================================================
# TECHNOLOGY COSTS
# =============================================================================

@dataclass
class TechnologyCosts:
    """Capital and operating costs for all technologies."""
    
    # Solar PV (utility scale) - IRENA RPGC 2024
    solar_pv_capex: float = 1500.0  # USD/kW - AIIB 2021 Maldives $1667-2500/kW; ASPIRE $1431/kW; island SIDS installed cost
    solar_pv_opex_pct: float = 0.015  # 1.5% of CAPEX/year
    solar_pv_lifetime: int = 30  # years - Industry standard 2025
    solar_pv_degradation: float = 0.005  # 0.5%/year
    solar_pv_capacity_factor: float = 0.175  # World Bank/Solargis Maldives Atlas
    
    # Solar PV cost decline trajectory
    solar_pv_cost_decline: float = 0.04  # 4%/year - IRENA learning rates
    
    # P6: Endogenous learning curve (Wright's Law)
    solar_learning_rate: float = 0.20  # 20% cost reduction per doubling of cumulative capacity
    solar_global_cumulative_gw_2026: float = 1500.0  # GW — IRENA 2024
    solar_global_annual_addition_gw: float = 350.0  # GW/yr — IRENA 2024
    
    # Battery storage (Li-ion LFP) - BNEF Dec 2025
    battery_capex: float = 350.0  # USD/kWh - AIIB 2021 Maldives $460-500/kWh island allocation; Lazard LCOS 2023 $147-295/kWh utility
    battery_opex: float = 5.0  # USD/kWh/year - Ember LCOS model 2025
    battery_lifetime: int = 15  # years - LFP 6000+ cycles
    battery_efficiency: float = 0.88  # round-trip - Modern LFP 87-92%
    battery_cost_decline: float = 0.06  # 6%/year - BNEF/NREL (slowing)
    
    # P6: Endogenous learning curve (Wright's Law)
    battery_learning_rate: float = 0.18  # 18% cost reduction per doubling
    battery_global_cumulative_gwh_2026: float = 500.0  # GWh — BNEF 2025
    battery_global_annual_addition_gwh: float = 200.0  # GWh/yr — BNEF 2025
    battery_hours: float = 4.0  # hours of storage at peak load - IRENA Innovation Outlook BESS 2023
    
    # Solar lifecycle emissions
    solar_lifecycle_emission_factor: float = 0.040  # kgCO2/kWh - IPCC AR5 median
    
    # Diesel generators
    diesel_gen_capex: float = 800.0  # USD/kW - Industry estimates
    diesel_gen_opex_kwh: float = 0.025  # USD/kWh O&M
    diesel_gen_lifetime: int = 20  # years
    
    # Undersea HVDC cable (One Grid) - Recent benchmarks
    cable_capex_per_km: float = 3_000_000.0  # USD/km - Deep ocean crossing
    # cable_length_km removed — canonical copy lives in OneGridConfig.cable_length_km
    cable_capacity_mw: float = 200.0  # OSOWOG proposal
    cable_opex_pct: float = 0.02  # 2% of CAPEX/year
    cable_lifetime: int = 40  # years
    # cable_losses_pct removed (V3 fix) — was 0.03 (stale default), superseded by
    # hvdc_cable_loss_pct = 0.04 (CSV-loaded, CIGRÉ verified). See IMPROVEMENT_PLAN V3.
    
    # C4: Cable cost breakdown — converter stations, landing, IDC, grid upgrade
    converter_station_cost_per_mw: float = 1_600_000.0  # USD/MW — Härtel et al. (2017); 200MW pair
    landing_cost_per_end: float = 40_000_000.0  # USD/end — CIGRÉ TB 815; Worzyk (2009)
    num_landings: int = 2  # Two-terminal link: India + Maldives
    idc_rate: float = 0.15  # Interest During Construction — 15% of base CAPEX
    grid_upgrade_cost: float = 75_000_000.0  # USD — Maldives-side grid reinforcement
    
    # Inter-island MV submarine cable
    inter_island_capex_per_km: float = 1_500_000.0  # USD/km - Reef navigation complexity
    
    # L25: distribution infrastructure defaults (mv_line_capex_per_km, lv_line_capex_per_km,
    # transformer_capex) removed — dead code. Last-mile costs covered by connection_cost_per_household.
    # td_losses_pct removed — superseded by distribution_loss_pct + hvdc_cable_loss_pct (D12/D13)
    
    # T&D losses — verified sources
    distribution_loss_pct: float = 0.11  # 11% — World Bank WDI: Maldives T&D losses
    male_grid_loss_pct: float = 0.08    # R5: Greater Malé compact grid — STELCO 2022
    outer_grid_loss_pct: float = 0.12   # R5: Outer island dispersed grids — WB WDI 2023
    hvdc_cable_loss_pct: float = 0.04  # 4% — Skog et al. CIGRÉ 2010 B1-106, NorNed measured 4.2%
    
    # PV temperature derating — IEC 61215; GEP-OnSSET onsset.py L186
    pv_temp_derating_coeff: float = 0.005  # /°C — power loss per degree above 25°C
    pv_noct_coeff: float = 25.6  # °C per kW/m² — cell temp rise above ambient
    
    # Climate fallback defaults — used when per-island GIS data unavailable
    default_ambient_temp: float = 28.0  # °C — Maldives annual average
    default_ghi: float = 5.55  # kWh/m²/day — Maldives national average
    
    # Connection costs
    connection_cost_per_hh: float = 200.0  # USD/household — World Bank ESMAP 2019; ADB POISED PCR 2023
    
    # Network routing
    routing_premium: float = 1.15  # 1.15× straight-line distance for reef avoidance/bathymetry
    
    # Operational parameters
    reserve_margin: float = 0.15  # 15% generation reserve above peak
    min_diesel_backup: float = 0.20  # 20% of peak kept as diesel backup
    solar_peak_contribution: float = 0.10  # 10% of solar counts toward peak
    
    # Solar land constraint
    max_solar_land_fraction: float = 0.15  # Max fraction of island area usable for solar PV
    solar_area_per_kw: float = 7.0  # m²/kW — panel + spacing area per kW installed
    total_inhabited_island_area_km2: float = 134.09  # km² — sum of 176 inhabited islands

    @property
    def max_ground_mount_solar_mw(self) -> float:
        """Maximum ground-mount solar MW on all inhabited islands combined."""
        usable_m2 = self.total_inhabited_island_area_km2 * 1e6 * self.max_solar_land_fraction
        return usable_m2 / self.solar_area_per_kw / 1000  # kW → MW
    
    # Climate adaptation premium — GCA (2025); notional, no project-specific data
    climate_adaptation_premium: float = 0.075  # 7.5% CAPEX premium for coastal/submarine infrastructure
    
    # P7: Climate damage scenario parameters (RCP 4.5 / 8.5)
    rcp45_ghi_change_2050: float = -0.02  # −2% GHI by 2050 — IPCC AR6
    rcp85_ghi_change_2050: float = -0.05  # −5% GHI by 2050 — IPCC AR6
    rcp45_temp_rise_2050: float = 1.5  # °C by 2050 — IPCC AR6
    rcp85_temp_rise_2050: float = 3.0  # °C by 2050 — IPCC AR6
    climate_scenario_year: int = 2050  # Year at which full impact reached


# =============================================================================
# FUEL PARAMETERS
# =============================================================================

@dataclass
class FuelConfig:
    """Diesel fuel parameters."""
    
    price_2026: float = 0.85  # USD/liter - Platts Dec 2025; STO import data
    price_escalation: float = 0.02  # 2%/year real escalation
    
    # Generator efficiency
    kwh_per_liter: float = 3.3  # 2018 Data Book: mean 3.31, median 3.15 (115 islands)
    
    # R4: Segmented diesel efficiency
    male_diesel_efficiency: float = 3.3   # Greater Malé large gensets (>5 MW)
    outer_diesel_efficiency: float = 2.38  # Outer island small gensets (<500 kW)
    
    # Emissions
    emission_factor_kg_co2_per_kwh: float = 0.72  # kgCO2/kWh - IPCC 2006
    
    def get_price(self, year: int, base_year: int = 2026) -> float:
        """Get diesel price for a given year with escalation."""
        years_from_base = year - base_year
        return self.price_2026 * ((1 + self.price_escalation) ** years_from_base)


# =============================================================================
# POWER PURCHASE AGREEMENT (ONE GRID)
# =============================================================================

@dataclass
class PPAConfig:
    """Power Purchase Agreement parameters for One Grid scenario."""
    
    import_price_2030: float = 0.06  # USD/kWh - India wholesale + cable premium
    transmission_charge: float = 0.01  # USD/kWh - cross-border wheeling
    price_escalation: float = 0.01  # 1%/year
    cable_online_year: int = 2032  # Realistic timeline (5-7 years from decision)
    
    # India grid emission factor
    india_grid_emission_factor: float = 0.70  # kgCO2/kWh - improving over time
    india_grid_emission_decline: float = 0.02  # 2%/year improvement
    
    def get_price(self, year: int) -> float:
        """Get total import price (wholesale + transmission) for a given year."""
        if year < self.cable_online_year:
            return None  # Cable not online yet
        years_from_start = year - self.cable_online_year
        base_price = self.import_price_2030 + self.transmission_charge
        return base_price * ((1 + self.price_escalation) ** years_from_start)
    
    # Base year for India grid decarbonisation trajectory
    india_grid_base_year: int = 2024

    def get_india_emission_factor(self, year: int) -> float:
        """Get India grid emission factor for a given year."""
        years_from_base = year - self.india_grid_base_year
        return self.india_grid_emission_factor * ((1 - self.india_grid_emission_decline) ** years_from_base)


# =============================================================================
# DISPATCH PARAMETERS — Sources: GEP-OnSSET archived code (onsset.py)
# =============================================================================

@dataclass
class DispatchConfig:
    """Hourly dispatch model parameters. All verified against GEP-OnSSET code."""
    
    # Battery — GEP-OnSSET onsset.py L194
    battery_dod_max: float = 0.80  # Maximum depth of discharge (LFP)
    
    # Battery charge/discharge — GEP-OnSSET onsset.py
    battery_charge_efficiency: float = 0.938  # One-way charge efficiency (√0.88 RT; C-WC-01 fix)
    battery_discharge_efficiency: float = 0.938  # One-way discharge efficiency (√0.88 RT; C-WC-01 fix)
    battery_self_discharge_rate: float = 0.0002  # Per-hour self-discharge fraction
    
    # Battery cycle-life curve — GEP-OnSSET onsset.py L283; Schiffer et al. 2007
    battery_cycle_life_coeff_a: float = 531.52764  # Cycle-life curve coefficient A
    battery_cycle_life_coeff_b: float = -1.12297  # Cycle-life curve exponent B
    
    # Diesel generator — GEP-OnSSET onsset.py L259
    diesel_min_load_fraction: float = 0.40  # Minimum load as fraction of rated capacity
    diesel_avg_capacity_factor: float = 0.60  # Avg CF for LCOE amortisation
    
    # Fuel consumption curve — GEP-OnSSET onsset.py L266; Mandelli et al. 2016
    # fuel_litres = capacity_kW × idle_coeff + generation_kWh × proportional_coeff
    fuel_curve_idle_coeff: float = 0.08145  # l/hr per kW of installed capacity
    fuel_curve_proportional_coeff: float = 0.246  # l/kWh generated
    
    # Dispatch strategy — GEP-OnSSET
    break_hour: int = 17  # Battery priority before this hour; diesel priority after
    pv_system_derating_factor: float = 0.90  # System-level PV derating (dust/mismatch/wiring)
    hybrid_default_solar_share: float = 0.60  # Default solar share in hybrid LCOE
    
    # CR-07/CR-08: Previously hardcoded in scenarios/__init__.py, now in parameters.csv
    emergency_diesel_cf: float = 0.60  # Diesel CF during cable outage events
    max_saidi_reduction_fraction: float = 0.80  # Max SAIDI improvement from RE diversification
    
    # LW-02: Battery initial SOC for dispatch simulation (washes out after first few days)
    battery_initial_soc: float = 0.50  # Standard 50% assumption


# =============================================================================
# CABLE OUTAGE PARAMETERS — Sources: NorNed/Basslink/BritNed public record
# =============================================================================

@dataclass
class CableOutageConfig:
    """Submarine cable outage parameters for supply security analysis."""
    
    # Outage rate — NorNed ~0.13/yr (2 in 15yr); Basslink ~0.18/yr (3 in 17yr)
    outage_rate_per_yr: float = 0.15  # events/yr (Poisson), midpoint of observed
    min_outage_months: int = 1  # Minimum repair time
    max_outage_months: int = 6  # Basslink 2015-16: 6 months; NorNed 2022: 5+ months


# =============================================================================
# SUPPLY SECURITY — diesel reserve for cable outage backup
# =============================================================================

@dataclass
class SupplySecurityConfig:
    """Diesel fleet standby reserve costs for supply security."""
    
    # Annual cost of maintaining idle diesel fleet — bottom-up engineering estimate
    idle_fleet_annual_cost_m: float = 8.0  # $M/yr — 240MW × $500-800/kW × 2-4% + crew
    
    # Fuel premium during cable outage (emergency procurement)
    diesel_fuel_premium_outage: float = 0.20  # 20% fuel cost premium during outage


# =============================================================================
# L11: CONNECTION COSTS
# =============================================================================

@dataclass
class ConnectionConfig:
    """Last-mile household connection costs (L11)."""
    
    cost_per_household: float = 200.0  # USD/HH — World Bank ESMAP 2019; ADB POISED PCR 2023
    number_of_households: int = 100_000  # NBS Census 2022 (~515k pop / 5.1 per HH)
    rollout_years: int = 5  # Phased 2027-2031


# =============================================================================
# L6: TOURISM DEMAND MODULE
# =============================================================================

@dataclass
class TourismConfig:
    """Off-grid resort sector parameters (L6). NOT in public utility CBA;
    provides national emissions context and green premium revenue potential."""
    
    resort_demand_gwh: float = 1050.0  # GWh/yr — USAID/SARI; 170+ resorts × ~6 GWh
    green_premium_per_kwh: float = 0.075  # USD/kWh — WTP for green electricity
    resort_emission_factor: float = 0.85  # kgCO2/kWh — small gensets, lower efficiency
    resort_kwh_per_guest_night: float = 60.0  # kWh/guest-night — Komandoo 58.3, Crown&Champa 53


# =============================================================================
# D61: NEAR-SHORE SOLAR CONFIGURATION
# =============================================================================

@dataclass
class NearShoreConfig:
    """Near-shore and floating solar parameters for S5/S6 scenarios (D61).
    
    Uninhabited islands near Malé can host solar farms connected by short
    submarine cables, breaking the 4% rooftop RE cap.
    Floating solar on atoll lagoons pushes RE further.
    """
    
    # Near-shore solar (uninhabited islands within 10km of Malé)
    nearshore_solar_mw: float = 104.0  # MW — GIS analysis: 1.82 km² usable
    nearshore_cable_cost_per_mw: float = 250_000.0  # USD/MW — cable amortised
    nearshore_build_start: int = 2030  # After initial outer-island RE deployment
    nearshore_build_years: int = 3  # 3-year phased construction
    
    # Floating solar on Malé/Kaafu atoll lagoon
    floating_solar_mw: float = 195.0  # MW — GoM Roadmap: 100 MW Greater Malé + 95 MW outer
    floating_solar_capex_premium: float = 1.50  # 50% over ground-mount
    floating_build_start: int = 2033  # After near-shore proven
    floating_build_years: int = 5  # 5-year phased construction


# =============================================================================
# R9: LNG TRANSITION CONFIGURATION
# =============================================================================

@dataclass
class LNGConfig:
    """LNG transition parameters for S7 scenario (R9).
    
    Gulhifalhu LNG terminal replaces diesel for Greater Malé.
    Outer islands follow same solar+battery path as National Grid (S3).
    Source: GoM Energy Roadmap 2024-2033; ADB/Mahurkar Prefeasibility 2023.
    """
    
    # Plant capacity and timeline
    plant_capacity_mw: float = 140.0  # MW — GoM Roadmap: 140 MW initial
    construction_start: int = 2028  # GoM Roadmap: Gulhifalhu planning underway
    online_year: int = 2031  # 3-year construction
    plant_lifetime: int = 30  # years — typical CCGT
    capacity_factor: float = 0.80  # Baseload LNG
    
    # Costs
    capex_per_mw: float = 1_200_000.0  # USD/MW — ADB/Mahurkar Prefeasibility 2023
    opex_per_mwh: float = 8.0  # USD/MWh — IEA Gas Market Report 2024
    fuel_cost_per_mwh: float = 70.0  # USD/MWh — IEA; Platts LNG Dec 2025
    fuel_escalation: float = 0.015  # 1.5%/yr real — IEA WEO 2024
    
    # Emissions
    emission_factor: float = 0.40  # kgCO2/kWh — IPCC 2006 natural gas
    
    def get_fuel_cost(self, year: int, base_year: int = 2026) -> float:
        """Get LNG fuel cost for a given year with escalation."""
        years_from_base = year - base_year
        return self.fuel_cost_per_mwh * ((1 + self.fuel_escalation) ** years_from_base)


# =============================================================================
# R6: WASTE-TO-ENERGY PARAMETERS
# =============================================================================

@dataclass
class WTEConfig:
    """Waste-to-energy parameters (R6).
    
    3 plants: 12 MW Thilafushi + 1.5 MW Addu + 0.5 MW Vandhoo = 14 MW baseload.
    Source: GoM Energy Roadmap 2024-2033; ICLEI WtE Guidebook 2021.
    Classified as renewable (biogenic MSW, IRENA/UNFCCC methodology).
    """
    
    # Capacity
    total_capacity_mw: float = 14.0  # MW — GoM Roadmap
    capacity_factor: float = 0.80  # Baseload, limited by waste supply
    online_year: int = 2029  # Thilafushi under construction
    plant_lifetime: int = 20  # years — ICLEI 2021
    
    # Costs
    capex_per_kw: float = 8000.0  # USD/kW — ICLEI WtE Guidebook 2021; EIA AEO 2024
    opex_pct: float = 0.04  # 4% of CAPEX/yr — engineering estimate for thermal
    
    # Emissions
    emission_factor: float = 0.0  # kgCO2/kWh — biogenic; IRENA RE classification
    
    @property
    def annual_generation_gwh(self) -> float:
        """WTE annual generation in GWh."""
        return self.total_capacity_mw * 8760 * self.capacity_factor / 1000
    
    @property
    def total_capex(self) -> float:
        """Total WTE CAPEX in USD."""
        return self.total_capacity_mw * 1000 * self.capex_per_kw
    
    @property
    def annual_opex(self) -> float:
        """Annual WTE O&M in USD."""
        return self.total_capex * self.opex_pct


# =============================================================================
# L17: MULTI-CRITERIA ANALYSIS PARAMETERS
# =============================================================================

@dataclass
class MCAConfig:
    """MCA criteria weights and qualitative expert-assigned scores (L17).
    
    Weights must sum to 1.0. Qualitative scores are 0-1 where 1 = best.
    All values sourced from parameters.csv → ADB (2017) §7.3; Dodgson et al. (2009).
    """
    
    # Criteria weights (must sum to 1.0)
    w_economic_efficiency: float = 0.20
    w_environmental_impact: float = 0.15
    w_energy_security: float = 0.15
    w_health_benefits: float = 0.10
    w_fiscal_burden: float = 0.10
    w_implementation_ease: float = 0.10
    w_social_equity: float = 0.10
    w_climate_resilience: float = 0.10
    
    # Qualitative scores — Full Integration (S1: India Cable)
    fi_implementation: float = 0.30
    fi_equity: float = 0.40
    fi_resilience: float = 0.50
    
    # Qualitative scores — National Grid (S2: Progressive Grid)
    ng_implementation: float = 0.50
    ng_equity: float = 0.70
    ng_resilience: float = 0.70
    
    # Qualitative scores — Islanded Green (S3: All Solar)
    ig_implementation: float = 0.80
    ig_equity: float = 0.90
    ig_resilience: float = 0.80
    
    # Qualitative scores — Near-Shore Solar (S5)
    ns_implementation: float = 0.60
    ns_equity: float = 0.75
    ns_resilience: float = 0.75
    
    # Qualitative scores — Maximum RE (S6)
    mx_implementation: float = 0.40
    mx_equity: float = 0.80
    mx_resilience: float = 0.85
    
    # Qualitative scores — LNG Transition (S7)
    lng_implementation: float = 0.60
    lng_equity: float = 0.50
    lng_resilience: float = 0.55


# =============================================================================
# FINANCING PARAMETERS — verified rates only
# =============================================================================

@dataclass
class FinancingConfig:
    """Financing terms for supplementary fiscal analysis (L5).
    
    These params feed financing_analysis.py (standalone). They do NOT
    affect the economic CBA, which uses the social discount rate.
    """
    
    # ADB SIDS concessional terms — ADB Lending Policies and Rates 2026
    adb_sids_rate: float = 0.01  # 1% per year (Group A/B SIDS)
    adb_sids_maturity: int = 40  # years
    adb_sids_grace: int = 10  # years grace period
    
    # Commercial benchmark — World Bank WDI Lending Interest Rate Maldives 2024
    commercial_interest_rate: float = 0.1155  # 11.55% nominal
    
    # Share of alt-scenario CAPEX eligible for ADB concessional financing
    # Remainder financed at commercial_interest_rate
    adb_eligible_share: float = 0.60  # illustrative 60% — solar, battery, grid infra
    
    # Commercial loan terms
    commercial_maturity: int = 20  # years — typical infra commercial loan
    commercial_grace: int = 2  # years — typical construction grace
    
    # GDP for fiscal burden metrics — World Bank WDI 2023
    gdp_billion_usd: float = 6.0  # Maldives nominal GDP
    gdp_growth_rate: float = 0.05  # G-MO-02: nominal GDP growth for year-specific fiscal burden


# =============================================================================
# ECONOMIC PARAMETERS
# =============================================================================

@dataclass
class EconomicsConfig:
    """Economic and CBA parameters."""
    
    # Discount rate
    discount_rate: float = 0.06  # 6% real - ADB standard for SIDS
    
    # P1: Declining discount rate schedule (HM Treasury Green Book 2026)
    # Used as sensitivity comparison alongside constant ADB 6%
    ddr_rate_0_30: float = 0.035   # Years 0-30: 3.5%
    ddr_rate_31_75: float = 0.030  # Years 31-75: 3.0%
    ddr_rate_76_125: float = 0.025 # Years 76-125: 2.5%
    
    # Social cost of carbon - EPA 2023; Rennert et al. 2022 Nature
    social_cost_carbon: float = 190.0  # USD/tCO2 - Central estimate at 2% discount
    scc_iwg_interim: float = 51.0  # USD/tCO2 - US IWG 2021 interim at 3% discount
    scc_annual_growth: float = 0.02  # 2% real annual increase in SCC
    
    # Value of lost load (reliability)
    voll: float = 5.0  # USD/kWh - Island tourism-dependent economy
    
    # Health co-benefits from reduced diesel — Parry et al. (2014) IMF + Black et al. (2023) updates
    health_damage_cost_per_mwh: float = 40.0  # USD/MWh diesel — weighted avg Malé+outer atolls
    pm25_emission_factor: float = 0.0002  # t/MWh — EPA AP-42 Ch.3.4
    nox_emission_factor: float = 0.010  # t/MWh — EPA AP-42 Ch.3.4
    
    # L16: Environmental externalities (diesel displacement benefits)
    noise_damage_per_mwh: float = 5.0  # USD/MWh — ExternE (2005); Mattmann et al. (2016)
    fuel_spill_risk_per_mwh: float = 3.0  # USD/MWh — Etkin (2004); IMO IOPC Fund
    biodiversity_impact_per_mwh: float = 2.0  # USD/MWh — TEEB (2010); Costanza et al. (2014)
    
    # Currency
    exchange_rate_mvr_usd: float = 15.4  # MVR per USD


# =============================================================================
# CURRENT SYSTEM STATE (2024)
# =============================================================================

@dataclass 
class CurrentSystemConfig:
    """
    Current electricity system parameters (2024 baseline from GoM Energy Roadmap).
    
    Data sources:
    - Total capacity: 600 MW (GoM Energy Roadmap Nov 2024)
    - Solar PV: 68.5 MW (+164 MW under construction Dec 2025)
    - Battery: 8 MWh installed; 80 MWh under ADB/WB contracts
    - Generation mix: 93% diesel, 6% solar (IRENA/Ember 2023)
    """
    
    # Generation capacity (2024 baseline)
    total_capacity_mw: float = 600.0  # GoM Energy Roadmap Nov 2024
    diesel_capacity_mw: float = 531.5  # Derived (600 - 68.5)
    solar_capacity_mw: float = 68.5  # +164 MW in pipeline
    battery_capacity_mwh: float = 8.0  # 80 MWh under contract
    
    # Generation mix (2024)
    diesel_share: float = 0.93  # IRENA/Ember 2023
    re_share: float = 0.06  # GoM Energy Roadmap
    
    # Reliability (future use — L10 real options)
    saidi_minutes: float = 200.0  # ESTIMATE - minutes/year
    saifi_interruptions: float = 10.0  # ESTIMATE - interruptions/year
    
    # Population
    population_2026: int = 515_000  # NBS Census 2022 projection — overridden by CSV Macro/Population 2026
    population_growth_rate: float = 0.015  # UN WPP 2024: 1.5%/yr (declining)
    
    # Electricity structure — Island Electricity Data Book 2016-2018
    male_electricity_share: float = 0.57  # Greater Malé = 57% of inhabited-island generation
    outer_island_electricity_cost: float = 0.45  # USD/kWh — outer island diesel LCOE
    resort_capacity_share: float = 0.48  # Resorts = 48.3% of national installed capacity (off-grid)
    male_rooftop_solar_mwp: float = 18.0  # MWp — ZNES Flensburg: 5 public + 13 sports roofs
    
    # Macro context — from parameters.csv Macro category
    avg_hh_monthly_kwh: float = 300.0  # kWh/month — STELCO Annual Report 2023
    current_retail_tariff: float = 0.25  # USD/kWh — STELCO Domestic Tariff 2024
    india_domestic_rate: float = 0.10  # USD/kWh — India CEA General Review 2024
    current_subsidy_per_kwh: float = 0.15  # USD/kWh — GoM Budget 2024
    
    # Item-7: Subsidy reform schedule (linear phase-out)
    subsidy_reform_start_year: int = 2030  # GoM Medium-Term Fiscal Strategy 2024
    subsidy_reform_end_year: int = 2040  # Full cost recovery target
    
    def get_subsidy_per_kwh(self, year: int) -> float:
        """Return time-varying subsidy per kWh for a given year.
        
        Linear phase-out from current_subsidy_per_kwh to zero between
        subsidy_reform_start_year and subsidy_reform_end_year.
        Before start: full subsidy. After end: zero.
        """
        if year <= self.subsidy_reform_start_year:
            return self.current_subsidy_per_kwh
        elif year >= self.subsidy_reform_end_year:
            return 0.0
        else:
            progress = (year - self.subsidy_reform_start_year) / (
                self.subsidy_reform_end_year - self.subsidy_reform_start_year
            )
            return self.current_subsidy_per_kwh * (1.0 - progress)


# =============================================================================
# GREEN TRANSITION DEPLOYMENT SCHEDULE
# =============================================================================

@dataclass
class GreenTransitionConfig:
    """Solar PV and battery deployment schedule for Green Transition.
    
    Endogenous RE deployment: solar+battery LCOE ($0.166/kWh) < diesel LCOE
    ($0.299/kWh) from day one, so the optimal outer-island RE level is 100%
    as fast as physically deployable. The binding constraint is the deployment
    ramp (MW/year), not economics.
    """
    
    # Deployment ramp — maximum solar MW additions per year across outer islands
    # GoM pipeline: 164 MW over ~3 years ≈ 55 MW/yr
    deployment_ramp_mw_per_year: float = 50.0  # MW/yr — logistics-constrained
    
    # Starting RE share on outer islands in base year (2026)
    initial_re_share_outer: float = 0.10  # DEPRECATED (D-01): loaded from CSV but never consumed by scenarios; RE share computed endogenously via deployment ramp
    
    # Greater Malé max RE share (land-constrained: 18 MWp rooftop / 684 GWh demand)
    male_max_re_share: float = 0.04  # ZNES Flensburg study
    
    # Battery storage as % of solar capacity (MWh per MW solar)
    battery_ratio: float = 3.0  # 3 MWh storage per MW solar - modern BESS sizing
    
    # Islanded Green scenario adjustments
    islanded_cost_premium: float = 1.30  # 30% island logistics premium
    islanded_battery_ratio: float = 3.0  # MWh per MW solar for islanded
    islanded_max_re_share: float = 1.00  # Per-island ceiling for outer islands (100% solar+battery achievable)
    islanded_opex_premium: float = 1.20  # 20% higher O&M for dispersed operations
    islanded_re_cap_factor: float = 0.90  # Islanded RE targets at 90% of grid targets
    
    # Inter-island grid development
    inter_island_grid: bool = True
    inter_island_km: float = 14.0  # km — MST: 3 near-hub islands (Hulhumalé 7.5 + Vilingili 3.1 + Maradhoo 3.0)
    inter_island_build_end: int = 2030  # 3-year phased construction


# =============================================================================
# ONE GRID CONFIGURATION
# =============================================================================

@dataclass
class OneGridConfig:
    """Undersea cable and import configuration for One Grid scenario."""
    
    # Cable parameters
    cable_online_year: int = 2032  # Realistic: 5-7 years from decision
    cable_capacity_mw: float = 200.0  # OSOWOG proposal
    cable_length_km: float = 700.0  # Direct ~600 km + 15-20% routing
    cable_capex_total: float = None  # Calculated
    
    # GoM cost share
    gom_share_pct: float = 1.00  # 100% Maldives (no cost-sharing agreement exists)
    
    # Complementary domestic RE
    domestic_re_target_2050: float = 0.30  # 30% from domestic solar
    
    # One Grid operational parameters
    battery_ratio: float = 1.5  # MWh per MW solar (less than green transition)
    diesel_reserve_ratio: float = 0.05  # 5% emergency backup post-cable
    diesel_backup_share: float = 0.20  # 20% of peak retained as backup
    diesel_retirement_rate: float = 0.10  # 10% annual fleet reduction
    inter_island_build_start: int = 2027  # Start of inter-island construction
    inter_island_build_end: int = 2028  # End of inter-island construction
    cable_construction_years: int = 3  # Duration of India cable construction
    
    def __post_init__(self):
        if self.cable_capex_total is None:
            # Will be recalculated from technology.cable_capex_per_km after CSV load
            self.cable_capex_total = None  # deferred to get_config()


# =============================================================================
# SENSITIVITY ANALYSIS RANGES
# =============================================================================

# Default sensitivity ranges — overridden by parameters.csv Low/High columns
SENSITIVITY_PARAMS = {
    "discount_rate": {"low": 0.03, "base": 0.06, "high": 0.10},
    "diesel_price": {"low": 0.60, "base": 0.85, "high": 1.10},
    "diesel_escalation": {"low": 0.00, "base": 0.02, "high": 0.05},
    "import_price": {"low": 0.04, "base": 0.06, "high": 0.10},
    "solar_capex": {"low": 1000, "base": 1500, "high": 2200},
    "solar_cf": {"low": 0.15, "base": 0.175, "high": 0.22},
    "battery_capex": {"low": 200, "base": 350, "high": 500},
    "cable_capex_per_km": {"low": 2_000_000, "base": 3_000_000, "high": 5_000_000},
    "gom_cost_share": {"low": 0.25, "base": 0.30, "high": 1.00},
    "social_cost_carbon": {"low": 0, "base": 190, "high": 300},
    "demand_growth": {"low": 0.035, "base": 0.05, "high": 0.065},
    "outage_rate": {"low": 0.10, "base": 0.15, "high": 0.20},
    "idle_fleet_cost": {"low": 5, "base": 8, "high": 13},
    "price_elasticity": {"low": -0.5, "base": -0.3, "high": -0.1},
    # L14: Expanded parameters (14 → 22)
    "health_damage": {"low": 20, "base": 40, "high": 80},
    "fuel_efficiency": {"low": 2.8, "base": 3.3, "high": 3.8},
    "base_demand": {"low": 1050, "base": 1200, "high": 1350},
    "battery_hours": {"low": 3.0, "base": 4.0, "high": 6.0},
    "climate_premium": {"low": 0.05, "base": 0.075, "high": 0.10},
    "converter_station": {"low": 1_200_000, "base": 1_600_000, "high": 2_000_000},
    "connection_cost": {"low": 150, "base": 200, "high": 300},
    "env_externality": {"low": 4, "base": 10, "high": 23},
    # M5/M1: Sectoral and demand allocation
    "sectoral_residential": {"low": 0.40, "base": 0.52, "high": 0.65},
    # V2b: S5/S6/S7-specific parameters (22 → 34)
    "lng_capex": {"low": 900_000, "base": 1_200_000, "high": 1_500_000},
    "lng_fuel_cost": {"low": 50, "base": 70, "high": 100},
    "lng_fuel_escalation": {"low": 0.005, "base": 0.015, "high": 0.025},
    "lng_emission_factor": {"low": 0.35, "base": 0.40, "high": 0.45},
    "floating_capex_premium": {"low": 1.30, "base": 1.50, "high": 1.80},
    "floating_solar_mw": {"low": 100, "base": 195, "high": 250},
    "nearshore_solar_mw": {"low": 60, "base": 104, "high": 150},
    "nearshore_cable_cost": {"low": 200_000, "base": 250_000, "high": 350_000},
    "wte_capex": {"low": 6000, "base": 8000, "high": 12_000},
    "deployment_ramp": {"low": 30, "base": 50, "high": 100},
    "male_max_re": {"low": 0.02, "base": 0.04, "high": 0.08},
    "battery_ratio": {"low": 2.0, "base": 3.0, "high": 4.0},
}


# =============================================================================
# LCOE BENCHMARKS (for report comparison charts)
# =============================================================================

@dataclass
class BenchmarksConfig:
    """LCOE benchmarks from IRENA, ADB, and SIDS project reports.
    
    Used in report comparison charts. All values in USD/kWh.
    """
    global_solar_lcoe: float = 0.049         # IRENA RPGC 2024
    global_diesel_gen_lcoe: float = 0.28     # IRENA Off-Grid RE Stats 2024
    sids_avg_renewable_lcoe: float = 0.16    # Surroop et al. (2024) MDPI Energies
    maldives_cif_aspire_lcoe: float = 0.099  # World Bank ASPIRE Phase III ICR 2023
    tokelau_lcoe: float = 0.22              # Tokelau RE Project Final Report 2017
    cook_islands_lcoe: float = 0.25         # ADB Pacific Energy Update 2023
    barbados_lcoe: float = 0.19             # BNEF Caribbean Energy Outlook 2024
    fiji_lcoe: float = 0.15                 # FEA Annual Report 2023


# =============================================================================
# DISTRIBUTIONAL ASSUMPTIONS (illustrative policy scenarios)
# =============================================================================

@dataclass
class DistributionalSharesConfig:
    """Illustrative cost/benefit allocation shares for distributional analysis.
    
    These are policy assumptions — NOT model outputs. Used in the report
    to show how costs/benefits might be distributed across stakeholders.
    Cost shares and benefit shares each sum to ~100%.
    All values in percent.
    """
    # Cost shares (who pays)
    cost_share_government: float = 25.0   # GoM PSIP 2024
    cost_share_mdbs: float = 30.0         # ADB/WB SIDS energy portfolio 2020-2024
    cost_share_india: float = 25.0        # India OSOWOG/ISA proposals
    cost_share_private: float = 20.0      # SIDS IPP experience

    # Benefit shares (who gains)
    benefit_share_households: float = 35.0   # Lower electricity bills
    benefit_share_businesses: float = 25.0   # Commercial/tourism sector
    benefit_share_government: float = 15.0   # Reduced subsidy burden
    benefit_share_climate: float = 20.0      # Avoided CO2 (global public good)
    benefit_share_workers: float = 5.0       # Employment creation


# =============================================================================
# INVESTMENT PHASING (illustrative allocation across periods)
# =============================================================================

@dataclass
class InvestmentPhasingConfig:
    """Illustrative investment phasing by technology and period.
    
    These are reference allocations — NOT computed by the model's
    endogenous CAPEX scheduling. Used in report exhibits.
    All values in million USD.
    """
    # Solar PV
    solar_2026_28: float = 150.0
    solar_2029_32: float = 300.0
    solar_2033_36: float = 250.0
    solar_2037_40: float = 150.0
    solar_2041_50: float = 100.0

    # Battery
    battery_2026_28: float = 50.0
    battery_2029_32: float = 150.0
    battery_2033_36: float = 100.0
    battery_2037_40: float = 50.0
    battery_2041_50: float = 50.0

    # Inter-Island Grid
    inter_island_2026_28: float = 100.0
    inter_island_2029_32: float = 400.0
    inter_island_2033_36: float = 200.0
    inter_island_2037_40: float = 100.0
    inter_island_2041_50: float = 0.0

    # India Cable
    india_cable_2026_28: float = 200.0
    india_cable_2029_32: float = 1200.0
    india_cable_2033_36: float = 0.0
    india_cable_2037_40: float = 0.0
    india_cable_2041_50: float = 0.0


# =============================================================================
# P8: TRANSPORT ELECTRIFICATION CONFIG
# =============================================================================

@dataclass
class TransportConfig:
    """Transport electrification parameters (P8 supplementary module).
    
    Models EV adoption via logistic S-curve across Low/Medium/High scenarios.
    Covers motorcycle-dominated Maldives fleet (~131k vehicles, 92% motorcycles).
    Sources: Malé City Council, gathunkaaru.com, ESMAP, UNDP EV pilot, IEA GEVO.
    """
    # Fleet composition (2026 baseline)
    total_vehicles_2026: int = 131_000       # Malé City Council / World Bank 2022
    motorcycle_share: float = 0.92           # gathunkaaru.com 2024
    ev_share_2026: float = 0.04             # ~5,240 EVs — gathunkaaru.com 2024
    fleet_growth_rate: float = 0.03          # Annual fleet growth
    
    # EV adoption S-curve (logistic function)
    ev_target_low: float = 0.30             # Low scenario: 30% EV by 2056
    ev_target_medium: float = 0.60          # Medium scenario: 60% EV by 2056
    ev_target_high: float = 0.85            # High scenario: 85% EV by 2056
    ev_adoption_midpoint: int = 2038        # S-curve inflection year
    ev_adoption_steepness: float = 0.25     # Logistic growth rate k
    
    # Vehicle energy parameters
    motorcycle_daily_km: float = 15.0       # Average daily km per motorcycle
    ice_fuel_consumption_l_100km: float = 3.0  # L/100km for ICE motorcycle
    ev_energy_per_km: float = 0.025         # kWh/km for e-motorcycle
    petrol_price_2026: float = 1.10         # USD/L retail petrol
    petrol_price_escalation: float = 0.03   # Annual real escalation
    
    # Vehicle cost differential
    e_motorcycle_premium_2026: float = 800.0  # USD premium over ICE
    premium_decline_rate: float = 0.06       # Annual decline in premium
    charging_station_cost: float = 25_000.0  # USD per station
    vehicles_per_station: int = 100          # EVs served per station
    ice_annual_maintenance: float = 200.0    # USD/yr per ICE motorcycle
    ev_annual_maintenance: float = 80.0      # USD/yr per e-motorcycle
    
    # Health and emissions
    pm25_damage_per_vkm: float = 0.012      # USD/vkm — Parry et al. 2014
    nox_damage_per_vkm: float = 0.005       # USD/vkm — Parry et al. 2014
    noise_reduction_per_ev_km: float = 0.002  # USD/vkm benefit
    ice_gco2_per_km: float = 65.0           # gCO₂/km WTW — ICCT 2021


# =============================================================================
# MAIN CONFIG CLASS
# =============================================================================

@dataclass
class Config:
    """Main configuration container."""
    
    # Time
    base_year: int = BASE_YEAR
    end_year: int = END_YEAR
    time_horizon: List[int] = field(default_factory=lambda: TIME_HORIZON)
    end_year_20: int = 2046   # Short-term horizon
    end_year_30: int = 2056   # Medium-term horizon (default)
    end_year_50: int = 2076   # Long-term horizon
    
    # Sub-configs
    demand: DemandConfig = field(default_factory=DemandConfig)
    technology: TechnologyCosts = field(default_factory=TechnologyCosts)
    fuel: FuelConfig = field(default_factory=FuelConfig)
    ppa: PPAConfig = field(default_factory=PPAConfig)
    economics: EconomicsConfig = field(default_factory=EconomicsConfig)
    current_system: CurrentSystemConfig = field(default_factory=CurrentSystemConfig)
    green_transition: GreenTransitionConfig = field(default_factory=GreenTransitionConfig)
    one_grid: OneGridConfig = field(default_factory=OneGridConfig)
    dispatch: DispatchConfig = field(default_factory=DispatchConfig)
    cable_outage: CableOutageConfig = field(default_factory=CableOutageConfig)
    financing: FinancingConfig = field(default_factory=FinancingConfig)
    supply_security: SupplySecurityConfig = field(default_factory=SupplySecurityConfig)
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    tourism: TourismConfig = field(default_factory=TourismConfig)
    mca: MCAConfig = field(default_factory=MCAConfig)
    nearshore: NearShoreConfig = field(default_factory=NearShoreConfig)
    lng: LNGConfig = field(default_factory=LNGConfig)
    wte: WTEConfig = field(default_factory=WTEConfig)
    benchmarks: BenchmarksConfig = field(default_factory=BenchmarksConfig)
    distributional: DistributionalSharesConfig = field(default_factory=DistributionalSharesConfig)
    investment_phasing: InvestmentPhasingConfig = field(default_factory=InvestmentPhasingConfig)
    transport: TransportConfig = field(default_factory=TransportConfig)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of warnings."""
        warnings = []
        
        if self.demand.base_demand_gwh <= 0:
            warnings.append("Base demand must be positive")
            
        if self.economics.discount_rate <= 0 or self.economics.discount_rate > 0.20:
            warnings.append("Discount rate should be between 0 and 20%")
            
        if self.fuel.price_2026 <= 0:
            warnings.append("Diesel price must be positive")
            
        return warnings
    
    def _male_growth_rate(self, year: int) -> float:
        """
        R1 + H17: Time-varying Greater Malé growth rate.
        
        Three phases:
          1. Before base_year: near-term rate (10%).
          2. base_year to saturation_year: linear taper from near-term to long-term (10%→6%).
          3. After saturation_year: post-peak rate (3.5%) — density saturation,
             decentralization policy reduces Malé's growth advantage.
        """
        base = self.base_year
        sat = self.demand.male_demand_saturation_year
        g_near = self.demand.male_growth_near_term
        g_long = self.demand.male_growth_long_term
        g_post = self.demand.male_post_peak_growth
        
        if year <= base:
            return g_near
        if year >= sat:
            return g_post  # H17: post-peak deceleration
        
        # Linear taper from near-term to long-term
        frac = (year - base) / (sat - base)
        return g_near + frac * (g_long - g_near)
    
    def _outer_growth_rate(self, year: int) -> float:
        """
        R2 + H17: Time-varying outer island growth rate.
        
        Three phases:
          1. Before base_year: near-term rate (7%).
          2. base_year to outer_growth_taper_year: linear taper from near-term to long-term (7%→5%).
          3. outer_growth_taper_year to male_demand_saturation_year: long-term rate (5%).
          4. After male_demand_saturation_year: post-peak rate (6%) — outer islands
             accelerate due to decentralization policy (ARISE, SAP 2019-2023).
        """
        base = self.base_year
        tap = self.demand.outer_growth_taper_year
        sat = self.demand.male_demand_saturation_year  # H17: post-peak trigger
        g_near = self.demand.outer_growth_near_term
        g_long = self.demand.outer_growth_long_term
        g_post = self.demand.outer_post_peak_growth
        
        if year <= base:
            return g_near
        if year > sat:  # H17: post-peak acceleration
            return g_post
        if year >= tap:
            return g_long
        
        frac = (year - base) / (tap - base)
        return g_near + frac * (g_long - g_near)
    
    def male_demand_share(self, year: int, scenario_growth_rate: float = 0.05) -> float:
        """
        Compute time-varying Malé demand share (R1 + H17: Roadmap-calibrated).
        
        Three-phase model:
          Phase 1 (2026–2035): Greater Malé grows at 10% near-term (STELCO Master Plan:
            Hulhumalé Phase 2/3 construction boom), tapering to 6% by saturation year.
            Outer islands taper from 7% to 5% by 2030. Malé share RISES to ~0.62.
          Phase 2 (2035+): Post-peak — Malé decelerates to 3.5% (density saturation,
            water/power constraints, land scarcity). Outer islands accelerate to 6%
            (decentralization policy: ARISE 2024, SAP 2019-2023). Share DECLINES.
          Phase 3 (long-run): Share converges toward floor (~0.45) but never below.
        
        Calibrated trajectory (Balanced variant):
          2026: 0.57 → 2030: 0.60 → 2035: 0.62 (peak) → 2050: 0.53 → 2056: 0.50
        
        Sources: Census 2022 (NBS), HDC master plan, Bertaud (2019) primacy model,
        STELCO Master Plan, ARISE Strategic Action Plan (2024), SAP 2019-2023.
        
        Floor: male_demand_min_share (0.45 from parameters.csv).
        Cap: 0.75 (physical upper bound — Malé can't be >75% of demand).
        
        Args:
            year: Calendar year
            scenario_growth_rate: National demand growth rate (for compatibility)
            
        Returns:
            Malé demand share for the given year (fraction, 0-1)
        """
        base_share = self.current_system.male_electricity_share
        
        t = year - self.base_year
        if t <= 0:
            return base_share
        
        # Year-by-year cumulative calculation
        # Start with Malé at base_share and outer at (1 - base_share) of normalized demand
        male_demand = base_share
        outer_demand = 1.0 - base_share
        
        for y in range(self.base_year + 1, year + 1):
            g_male = self._male_growth_rate(y)
            g_outer = self._outer_growth_rate(y)
            male_demand *= (1 + g_male)
            outer_demand *= (1 + g_outer)
        
        total = male_demand + outer_demand
        share = male_demand / total if total > 0 else base_share
        
        # Floor from parameters.csv (can't drop below — Malé remains capital)
        floor = self.demand.male_demand_min_share
        # Cap at 0.75 — Malé can't physically consume more than 75% of national demand
        return max(floor, min(share, 0.75))

    def weighted_diesel_efficiency(self, year: int, scenario_growth_rate: float = 0.05) -> float:
        """
        R4: Weighted-average diesel efficiency based on Malé/outer demand share.
        
        Greater Malé uses large gensets (>5 MW): 3.3 kWh/L
        Outer islands use small gensets (<500 kW): 2.38 kWh/L
        
        The blend changes over time as the Malé share evolves:
          η_weighted(t) = share_male(t) × η_male + (1 - share_male(t)) × η_outer
        
        Args:
            year: Calendar year
            scenario_growth_rate: Passed through to male_demand_share()
            
        Returns:
            Weighted diesel efficiency in kWh/L
        """
        share = self.male_demand_share(year, scenario_growth_rate)
        eta_male = self.fuel.male_diesel_efficiency
        eta_outer = self.fuel.outer_diesel_efficiency
        return share * eta_male + (1.0 - share) * eta_outer

    def weighted_distribution_loss(self, year: int, scenario_growth_rate: float = 0.05) -> float:
        """
        R5: Weighted-average distribution loss based on Malé/outer demand share.
        
        Greater Malé grid: 8% (compact, modern switchgear)
        Outer island grids: 12% (long feeders, old transformers)
        
        The blend changes over time as the Malé share evolves:
          loss_weighted(t) = share_male(t) × loss_male + (1 - share_male(t)) × loss_outer
        
        Args:
            year: Calendar year
            scenario_growth_rate: Passed through to male_demand_share()
            
        Returns:
            Weighted distribution loss (fraction, 0-1)
        """
        share = self.male_demand_share(year, scenario_growth_rate)
        loss_male = self.technology.male_grid_loss_pct
        loss_outer = self.technology.outer_grid_loss_pct
        return share * loss_male + (1.0 - share) * loss_outer


# =============================================================================
# DEFAULT CONFIG INSTANCE
# =============================================================================

# Path to parameters CSV
PARAMETERS_CSV = Path(__file__).parent / "parameters.csv"


def _parse_numeric(value_str: str):
    """Parse a string to int or float, or return None if empty/invalid."""
    if not value_str or not value_str.strip():
        return None
    value_str = value_str.strip()
    try:
        if '.' in value_str:
            return float(value_str)
        else:
            return int(value_str)
    except ValueError:
        return value_str


def load_parameters_from_csv(csv_path: Path = PARAMETERS_CSV) -> Dict[str, Dict[str, any]]:
    """
    Load parameters from CSV file.
    
    Returns dict organized by Category -> Parameter -> {value, low, high}
    The CSV must have columns: Category, Parameter, Value, Low, High, Unit, Source, Notes
    """
    params = {}
    
    if not csv_path.exists():
        print(f"Warning: Parameters CSV not found at {csv_path}")
        return params
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip comment rows
            if not row.get('Category') or row['Category'].startswith('#'):
                continue
            
            category = row['Category'].strip()
            param = row['Parameter'].strip()
            value = _parse_numeric(row.get('Value', ''))
            low = _parse_numeric(row.get('Low', ''))
            high = _parse_numeric(row.get('High', ''))
            
            if value is None:
                continue
            
            if category not in params:
                params[category] = {}
            
            # Store as dict with value + optional sensitivity bounds
            entry = {'value': value}
            if low is not None:
                entry['low'] = low
            if high is not None:
                entry['high'] = high
            params[category][param] = entry
    
    return params


def _v(entry):
    """Extract value from a parameter entry (dict or raw value)."""
    if isinstance(entry, dict):
        return entry['value']
    return entry


def get_config(load_from_csv: bool = True) -> Config:
    """
    Get configuration instance.
    
    Args:
        load_from_csv: If True, override defaults with values from parameters.csv
    """
    config = Config()
    
    if load_from_csv and PARAMETERS_CSV.exists():
        params = load_parameters_from_csv()
        
        # Apply CSV values to config
        if 'Current System' in params:
            cs = params['Current System']
            if 'Total Installed Capacity' in cs:
                config.current_system.total_capacity_mw = float(_v(cs['Total Installed Capacity']))
            if 'Diesel Capacity' in cs:
                config.current_system.diesel_capacity_mw = float(_v(cs['Diesel Capacity']))
            if 'Solar PV Capacity' in cs:
                config.current_system.solar_capacity_mw = float(_v(cs['Solar PV Capacity']))
            if 'Battery Storage' in cs:
                config.current_system.battery_capacity_mwh = float(_v(cs['Battery Storage']))
            if 'Diesel Generation Share' in cs:
                config.current_system.diesel_share = float(_v(cs['Diesel Generation Share']))
            if 'RE Generation Share' in cs:
                config.current_system.re_share = float(_v(cs['RE Generation Share']))
        
        # D-CR-01: Reliability parameters from CSV
        if 'Reliability' in params:
            rel = params['Reliability']
            if 'SAIDI Minutes' in rel:
                config.current_system.saidi_minutes = float(_v(rel['SAIDI Minutes']))
            if 'SAIFI Interruptions' in rel:
                config.current_system.saifi_interruptions = float(_v(rel['SAIFI Interruptions']))
        
        if 'Demand' in params:
            d = params['Demand']
            if 'Base Demand 2026' in d:
                config.demand.base_demand_gwh = float(_v(d['Base Demand 2026']))
            if 'Base Peak 2026' in d:
                config.demand.base_peak_mw = float(_v(d['Base Peak 2026']))
            if 'Load Factor' in d:
                config.demand.load_factor = float(_v(d['Load Factor']))
            if 'Growth Rate - BAU' in d:
                config.demand.growth_rates['status_quo'] = float(_v(d['Growth Rate - BAU']))
            if 'Growth Rate - National Grid' in d:
                config.demand.growth_rates['green_transition'] = float(_v(d['Growth Rate - National Grid']))
            if 'Growth Rate - Full Integration' in d:
                config.demand.growth_rates['one_grid'] = float(_v(d['Growth Rate - Full Integration']))
            if 'Price Elasticity of Demand' in d:
                config.demand.price_elasticity = float(_v(d['Price Elasticity of Demand']))
            # M1: Island demand intensity multipliers
            if 'Intensity Urban' in d:
                config.demand.intensity_urban = float(_v(d['Intensity Urban']))
            if 'Intensity Secondary' in d:
                config.demand.intensity_secondary = float(_v(d['Intensity Secondary']))
            if 'Intensity Rural' in d:
                config.demand.intensity_rural = float(_v(d['Intensity Rural']))
        
        if 'Fuel' in params:
            f = params['Fuel']
            if 'Diesel Price 2026' in f:
                config.fuel.price_2026 = float(_v(f['Diesel Price 2026']))
            if 'Diesel Price Escalation' in f:
                config.fuel.price_escalation = float(_v(f['Diesel Price Escalation']))
            if 'Fuel Efficiency' in f:
                config.fuel.kwh_per_liter = float(_v(f['Fuel Efficiency']))
            if 'CO2 Emission Factor' in f:
                config.fuel.emission_factor_kg_co2_per_kwh = float(_v(f['CO2 Emission Factor']))
            # R4: Segmented diesel efficiency
            if 'Male Diesel Efficiency' in f:
                config.fuel.male_diesel_efficiency = float(_v(f['Male Diesel Efficiency']))
            if 'Outer Diesel Efficiency' in f:
                config.fuel.outer_diesel_efficiency = float(_v(f['Outer Diesel Efficiency']))
        
        if 'Solar' in params:
            s = params['Solar']
            if 'CAPEX 2026' in s:
                config.technology.solar_pv_capex = float(_v(s['CAPEX 2026']))
            if 'CAPEX Annual Decline' in s:
                config.technology.solar_pv_cost_decline = float(_v(s['CAPEX Annual Decline']))
            if 'OPEX (% of CAPEX)' in s:
                config.technology.solar_pv_opex_pct = float(_v(s['OPEX (% of CAPEX)']))
            if 'Capacity Factor' in s:
                config.technology.solar_pv_capacity_factor = float(_v(s['Capacity Factor']))
            if 'Lifecycle Emission Factor' in s:
                config.technology.solar_lifecycle_emission_factor = float(_v(s['Lifecycle Emission Factor']))
            if 'Degradation Rate' in s:
                config.technology.solar_pv_degradation = float(_v(s['Degradation Rate']))
            if 'Lifetime' in s:
                config.technology.solar_pv_lifetime = int(_v(s['Lifetime']))
            # P6: Learning curve params
            if 'Learning Rate' in s:
                config.technology.solar_learning_rate = float(_v(s['Learning Rate']))
            if 'Global Cumulative GW 2026' in s:
                config.technology.solar_global_cumulative_gw_2026 = float(_v(s['Global Cumulative GW 2026']))
            if 'Global Annual Addition GW' in s:
                config.technology.solar_global_annual_addition_gw = float(_v(s['Global Annual Addition GW']))
        
        if 'Battery' in params:
            b = params['Battery']
            if 'CAPEX 2026' in b:
                config.technology.battery_capex = float(_v(b['CAPEX 2026']))
            if 'CAPEX Annual Decline' in b:
                config.technology.battery_cost_decline = float(_v(b['CAPEX Annual Decline']))
            if 'Round-trip Efficiency' in b:
                config.technology.battery_efficiency = float(_v(b['Round-trip Efficiency']))
            if 'Lifetime' in b:
                config.technology.battery_lifetime = int(_v(b['Lifetime']))
            if 'OPEX' in b:
                config.technology.battery_opex = float(_v(b['OPEX']))
            if 'Storage Hours' in b:
                config.technology.battery_hours = float(_v(b['Storage Hours']))
            # P6: Learning curve params
            if 'Learning Rate' in b:
                config.technology.battery_learning_rate = float(_v(b['Learning Rate']))
            if 'Global Cumulative GWh 2026' in b:
                config.technology.battery_global_cumulative_gwh_2026 = float(_v(b['Global Cumulative GWh 2026']))
            if 'Global Annual Addition GWh' in b:
                config.technology.battery_global_annual_addition_gwh = float(_v(b['Global Annual Addition GWh']))
        
        if 'Diesel Gen' in params:
            dg = params['Diesel Gen']
            if 'CAPEX' in dg:
                config.technology.diesel_gen_capex = float(_v(dg['CAPEX']))
            if 'OPEX' in dg:
                config.technology.diesel_gen_opex_kwh = float(_v(dg['OPEX']))
            if 'Lifetime' in dg:
                config.technology.diesel_gen_lifetime = int(_v(dg['Lifetime']))
        
        if 'Cable' in params:
            c = params['Cable']
            if 'Length to India' in c:
                config.one_grid.cable_length_km = float(_v(c['Length to India']))
            if 'Capacity' in c:
                config.one_grid.cable_capacity_mw = float(_v(c['Capacity']))
            if 'GoM Cost Share' in c:
                config.one_grid.gom_share_pct = float(_v(c['GoM Cost Share']))
            if 'Online Year' in c:
                config.one_grid.cable_online_year = int(_v(c['Online Year']))
            if 'CAPEX per km' in c:
                config.technology.cable_capex_per_km = float(_v(c['CAPEX per km']))
            # C4: Cable cost breakdown
            if 'Converter Station Cost per MW' in c:
                config.technology.converter_station_cost_per_mw = float(_v(c['Converter Station Cost per MW']))
            if 'Landing Cost per End' in c:
                config.technology.landing_cost_per_end = float(_v(c['Landing Cost per End']))
            if 'Number of Landings' in c:
                config.technology.num_landings = int(_v(c['Number of Landings']))
            if 'IDC Rate' in c:
                config.technology.idc_rate = float(_v(c['IDC Rate']))
            if 'Grid Upgrade Cost' in c:
                config.technology.grid_upgrade_cost = float(_v(c['Grid Upgrade Cost']))
        
        if 'Economics' in params:
            e = params['Economics']
            if 'Discount Rate' in e:
                config.economics.discount_rate = float(_v(e['Discount Rate']))
            if 'Social Cost of Carbon' in e:
                config.economics.social_cost_carbon = float(_v(e['Social Cost of Carbon']))
            if 'SCC IWG Interim' in e:
                config.economics.scc_iwg_interim = float(_v(e['SCC IWG Interim']))
            if 'SCC Annual Growth' in e:
                config.economics.scc_annual_growth = float(_v(e['SCC Annual Growth']))
            if 'Value of Lost Load' in e:
                config.economics.voll = float(_v(e['Value of Lost Load']))
            # P1: Declining discount rate schedule
            if 'DDR Rate 0-30yr' in e:
                config.economics.ddr_rate_0_30 = float(_v(e['DDR Rate 0-30yr']))
            if 'DDR Rate 31-75yr' in e:
                config.economics.ddr_rate_31_75 = float(_v(e['DDR Rate 31-75yr']))
            if 'DDR Rate 76-125yr' in e:
                config.economics.ddr_rate_76_125 = float(_v(e['DDR Rate 76-125yr']))
            # D-CR-02: Exchange rate from CSV
            if 'Exchange Rate MVR/USD' in e:
                config.economics.exchange_rate_mvr_usd = float(_v(e['Exchange Rate MVR/USD']))
        
        if 'PPA' in params:
            p = params['PPA']
            if 'Import Price 2030' in p:
                config.ppa.import_price_2030 = float(_v(p['Import Price 2030']))
            if 'Transmission Charge' in p:
                config.ppa.transmission_charge = float(_v(p['Transmission Charge']))
            if 'Price Escalation' in p:
                config.ppa.price_escalation = float(_v(p['Price Escalation']))
            if 'India Grid Emission Factor' in p:
                config.ppa.india_grid_emission_factor = float(_v(p['India Grid Emission Factor']))
            if 'India Grid Emission Decline' in p:
                config.ppa.india_grid_emission_decline = float(_v(p['India Grid Emission Decline']))
            # D-MO-04: Wire india_grid_base_year from CSV
            if 'India Grid Base Year' in p:
                config.ppa.india_grid_base_year = int(_v(p['India Grid Base Year']))
        
        if 'Islanded' in params:
            i = params['Islanded']
            if 'Cost Premium' in i:
                config.green_transition.islanded_cost_premium = float(_v(i['Cost Premium']))
            if 'Battery Ratio' in i:
                config.green_transition.islanded_battery_ratio = float(_v(i['Battery Ratio']))
            if 'Max RE Share' in i:
                config.green_transition.islanded_max_re_share = float(_v(i['Max RE Share']))
            if 'OPEX Premium' in i:
                config.green_transition.islanded_opex_premium = float(_v(i['OPEX Premium']))
            if 'RE Cap Factor' in i:
                config.green_transition.islanded_re_cap_factor = float(_v(i['RE Cap Factor']))
        
        if 'One Grid' in params:
            og = params['One Grid']
            if 'Battery Ratio' in og:
                config.one_grid.battery_ratio = float(_v(og['Battery Ratio']))
            if 'Diesel Reserve Ratio' in og:
                config.one_grid.diesel_reserve_ratio = float(_v(og['Diesel Reserve Ratio']))
            if 'Diesel Backup Share' in og:
                config.one_grid.diesel_backup_share = float(_v(og['Diesel Backup Share']))
            if 'Diesel Retirement Rate' in og:
                config.one_grid.diesel_retirement_rate = float(_v(og['Diesel Retirement Rate']))
            if 'Inter-Island Build Start' in og:
                config.one_grid.inter_island_build_start = int(_v(og['Inter-Island Build Start']))
            if 'Inter-Island Build End' in og:
                config.one_grid.inter_island_build_end = int(_v(og['Inter-Island Build End']))
            if 'Cable Construction Years' in og:
                config.one_grid.cable_construction_years = int(_v(og['Cable Construction Years']))
        
        if 'Operations' in params:
            o = params['Operations']
            if 'Reserve Margin' in o:
                config.technology.reserve_margin = float(_v(o['Reserve Margin']))
            if 'Min Diesel Backup' in o:
                config.technology.min_diesel_backup = float(_v(o['Min Diesel Backup']))
            if 'Solar Peak Contribution' in o:
                config.technology.solar_peak_contribution = float(_v(o['Solar Peak Contribution']))
        
        # Network routing parameters
        if 'Network' in params:
            net = params['Network']
            if 'Routing Premium' in net:
                config.technology.routing_premium = float(_v(net['Routing Premium']))
        
        # NEW: Dispatch parameters — GEP-OnSSET verified
        if 'Dispatch' in params:
            dp = params['Dispatch']
            if 'Battery DoD Max' in dp:
                config.dispatch.battery_dod_max = float(_v(dp['Battery DoD Max']))
            if 'Diesel Min Load Fraction' in dp:
                config.dispatch.diesel_min_load_fraction = float(_v(dp['Diesel Min Load Fraction']))
            if 'Fuel Curve Idle Coeff' in dp:
                config.dispatch.fuel_curve_idle_coeff = float(_v(dp['Fuel Curve Idle Coeff']))
            if 'Fuel Curve Proportional Coeff' in dp:
                config.dispatch.fuel_curve_proportional_coeff = float(_v(dp['Fuel Curve Proportional Coeff']))
            if 'Battery Charge Efficiency' in dp:
                config.dispatch.battery_charge_efficiency = float(_v(dp['Battery Charge Efficiency']))
            if 'Battery Discharge Efficiency' in dp:
                config.dispatch.battery_discharge_efficiency = float(_v(dp['Battery Discharge Efficiency']))
            if 'Battery Self Discharge Rate' in dp:
                config.dispatch.battery_self_discharge_rate = float(_v(dp['Battery Self Discharge Rate']))
            if 'Battery Cycle Life Coeff A' in dp:
                config.dispatch.battery_cycle_life_coeff_a = float(_v(dp['Battery Cycle Life Coeff A']))
            if 'Battery Cycle Life Coeff B' in dp:
                config.dispatch.battery_cycle_life_coeff_b = float(_v(dp['Battery Cycle Life Coeff B']))
            if 'Break Hour' in dp:
                config.dispatch.break_hour = int(_v(dp['Break Hour']))
            if 'PV System Derating Factor' in dp:
                config.dispatch.pv_system_derating_factor = float(_v(dp['PV System Derating Factor']))
            if 'Diesel Avg Capacity Factor' in dp:
                config.dispatch.diesel_avg_capacity_factor = float(_v(dp['Diesel Avg Capacity Factor']))
            if 'Hybrid Default Solar Share' in dp:
                config.dispatch.hybrid_default_solar_share = float(_v(dp['Hybrid Default Solar Share']))
            # CR-07/CR-08: Wire new dispatch params from CSV
            if 'Emergency Diesel CF' in dp:
                config.dispatch.emergency_diesel_cf = float(_v(dp['Emergency Diesel CF']))
            if 'Max SAIDI Reduction Fraction' in dp:
                config.dispatch.max_saidi_reduction_fraction = float(_v(dp['Max SAIDI Reduction Fraction']))
        
        # NEW: PV temperature derating — IEC 61215 verified
        if 'Solar' in params:
            s = params['Solar']
            if 'Temp Derating Coeff' in s:
                config.technology.pv_temp_derating_coeff = float(_v(s['Temp Derating Coeff']))
            if 'NOCT Coeff' in s:
                config.technology.pv_noct_coeff = float(_v(s['NOCT Coeff']))
            if 'Max Land Fraction' in s:
                config.technology.max_solar_land_fraction = float(_v(s['Max Land Fraction']))
            if 'Area Per kW' in s:
                config.technology.solar_area_per_kw = float(_v(s['Area Per kW']))
            if 'Total Inhabited Island Area' in s:
                config.technology.total_inhabited_island_area_km2 = float(_v(s['Total Inhabited Island Area']))
            if 'Default Ambient Temp' in s:
                config.technology.default_ambient_temp = float(_v(s['Default Ambient Temp']))
            if 'Default GHI' in s:
                config.technology.default_ghi = float(_v(s['Default GHI']))
        
        # NEW: T&D losses — World Bank WDI + CIGRÉ verified
        if 'Losses' in params:
            lo = params['Losses']
            if 'Distribution Loss' in lo:
                config.technology.distribution_loss_pct = float(_v(lo['Distribution Loss']))
            if 'Male Grid Loss' in lo:
                config.technology.male_grid_loss_pct = float(_v(lo['Male Grid Loss']))
            if 'Outer Grid Loss' in lo:
                config.technology.outer_grid_loss_pct = float(_v(lo['Outer Grid Loss']))
            if 'HVDC Cable Loss' in lo:
                config.technology.hvdc_cable_loss_pct = float(_v(lo['HVDC Cable Loss']))
        
        # NEW: Cable outage — NorNed/Basslink public record
        if 'Cable Outage' in params:
            co = params['Cable Outage']
            if 'Outage Rate' in co:
                config.cable_outage.outage_rate_per_yr = float(_v(co['Outage Rate']))
            if 'Min Outage Duration' in co:
                config.cable_outage.min_outage_months = int(_v(co['Min Outage Duration']))
            if 'Max Outage Duration' in co:
                config.cable_outage.max_outage_months = int(_v(co['Max Outage Duration']))
        
        # NEW: Financing — ADB verified + commercial benchmark
        if 'Financing' in params:
            fi = params['Financing']
            if 'ADB SIDS Concessional Rate' in fi:
                config.financing.adb_sids_rate = float(_v(fi['ADB SIDS Concessional Rate']))
            if 'ADB SIDS Maturity' in fi:
                config.financing.adb_sids_maturity = int(_v(fi['ADB SIDS Maturity']))
            if 'ADB SIDS Grace Period' in fi:
                config.financing.adb_sids_grace = int(_v(fi['ADB SIDS Grace Period']))
            if 'ADB Eligible CAPEX Share' in fi:
                config.financing.adb_eligible_share = float(_v(fi['ADB Eligible CAPEX Share']))
            if 'Commercial Loan Maturity' in fi:
                config.financing.commercial_maturity = int(_v(fi['Commercial Loan Maturity']))
            if 'Commercial Loan Grace' in fi:
                config.financing.commercial_grace = int(_v(fi['Commercial Loan Grace']))
        
        # Load commercial interest rate from Economics into financing config
        if 'Economics' in params:
            ec = params['Economics']
            if 'Commercial Interest Rate' in ec:
                config.financing.commercial_interest_rate = float(_v(ec['Commercial Interest Rate']))
        
        # Health co-benefits — Parry et al. (2014) / Black et al. (2023)
        if 'Health' in params:
            h = params['Health']
            if 'Damage Cost per MWh Diesel' in h:
                config.economics.health_damage_cost_per_mwh = float(_v(h['Damage Cost per MWh Diesel']))
            if 'PM25 Emission Factor' in h:
                config.economics.pm25_emission_factor = float(_v(h['PM25 Emission Factor']))
            if 'NOx Emission Factor' in h:
                config.economics.nox_emission_factor = float(_v(h['NOx Emission Factor']))
        
        # Climate adaptation premium — GCA (2025)
        if 'Climate' in params:
            cl = params['Climate']
            if 'Adaptation CAPEX Premium' in cl:
                config.technology.climate_adaptation_premium = float(_v(cl['Adaptation CAPEX Premium']))
        
        # L11: Connection costs
        if 'Connection' in params:
            cn = params['Connection']
            if 'Cost per Household' in cn:
                config.connection.cost_per_household = float(_v(cn['Cost per Household']))
                config.technology.connection_cost_per_hh = float(_v(cn['Cost per Household']))
            if 'Number of Households' in cn:
                config.connection.number_of_households = int(_v(cn['Number of Households']))
            if 'Connection Rollout Years' in cn:
                config.connection.rollout_years = int(_v(cn['Connection Rollout Years']))
        
        # L16: Environmental externalities
        if 'Environment' in params:
            ev = params['Environment']
            if 'Noise Damage per MWh Diesel' in ev:
                config.economics.noise_damage_per_mwh = float(_v(ev['Noise Damage per MWh Diesel']))
            if 'Fuel Spill Risk per MWh Diesel' in ev:
                config.economics.fuel_spill_risk_per_mwh = float(_v(ev['Fuel Spill Risk per MWh Diesel']))
            if 'Biodiversity Impact per MWh Diesel' in ev:
                config.economics.biodiversity_impact_per_mwh = float(_v(ev['Biodiversity Impact per MWh Diesel']))
        
        # L6: Tourism demand module
        if 'Tourism' in params:
            tm = params['Tourism']
            if 'Resort Electricity Demand' in tm:
                config.tourism.resort_demand_gwh = float(_v(tm['Resort Electricity Demand']))
            if 'Green Premium per kWh' in tm:
                config.tourism.green_premium_per_kwh = float(_v(tm['Green Premium per kWh']))
            if 'Resort Diesel Emission Factor' in tm:
                config.tourism.resort_emission_factor = float(_v(tm['Resort Diesel Emission Factor']))
            if 'Resort kWh per Guest Night' in tm:
                config.tourism.resort_kwh_per_guest_night = float(_v(tm['Resort kWh per Guest Night']))
        
        # Supply security — diesel reserve costs
        if 'Supply Security' in params:
            ss = params['Supply Security']
            if 'Idle Fleet Annual Cost' in ss:
                config.supply_security.idle_fleet_annual_cost_m = float(_v(ss['Idle Fleet Annual Cost']))
            if 'Diesel Fuel Premium During Outage' in ss:
                config.supply_security.diesel_fuel_premium_outage = float(_v(ss['Diesel Fuel Premium During Outage']))
        
        # Electricity structure — Maldives-specific
        if 'Electricity Structure' in params:
            es = params['Electricity Structure']
            if 'Male Electricity Share' in es:
                config.current_system.male_electricity_share = float(_v(es['Male Electricity Share']))
            if 'Outer Island Electricity Cost' in es:
                config.current_system.outer_island_electricity_cost = float(_v(es['Outer Island Electricity Cost']))
            if 'Resort Installed Capacity Share' in es:
                config.current_system.resort_capacity_share = float(_v(es['Resort Installed Capacity Share']))
            if 'Male Rooftop Solar Potential' in es:
                config.current_system.male_rooftop_solar_mwp = float(_v(es['Male Rooftop Solar Potential']))
            # M5: Sectoral demand split
            if 'Sectoral Split Residential' in es:
                config.demand.sectoral_residential = float(_v(es['Sectoral Split Residential']))
            if 'Sectoral Split Commercial' in es:
                config.demand.sectoral_commercial = float(_v(es['Sectoral Split Commercial']))
            if 'Sectoral Split Public' in es:
                config.demand.sectoral_public = float(_v(es['Sectoral Split Public']))
        
        # Inter-Island Grid — wire CSV to existing config fields
        if 'Inter-Island Grid' in params:
            ig = params['Inter-Island Grid']
            if 'Total Length' in ig:
                config.green_transition.inter_island_km = float(_v(ig['Total Length']))
            if 'CAPEX per km' in ig:
                config.technology.inter_island_capex_per_km = float(_v(ig['CAPEX per km']))
            if 'Build Start Year' in ig:
                config.one_grid.inter_island_build_start = int(_v(ig['Build Start Year']))
            if 'Build End Year' in ig:
                config.green_transition.inter_island_build_end = int(_v(ig['Build End Year']))
        
        # Cable O&M and Lifetime — wire to existing technology fields
        if 'Cable' in params:
            c2 = params['Cable']
            if 'O&M Cost' in c2:
                config.technology.cable_opex_pct = float(_v(c2['O&M Cost']))
            if 'Lifetime' in c2:
                config.technology.cable_lifetime = int(_v(c2['Lifetime']))
        
        # Demand population thresholds — wire to new DemandConfig fields
        if 'Demand' in params:
            d2 = params['Demand']
            if 'Urban Population Threshold' in d2:
                config.demand.urban_pop_threshold = int(_v(d2['Urban Population Threshold']))
            if 'Secondary Population Threshold' in d2:
                config.demand.secondary_pop_threshold = int(_v(d2['Secondary Population Threshold']))
        
        # Macro context — GDP for fiscal burden analysis (L5) + tariff/subsidy/consumption
        if 'Macro' in params:
            mc = params['Macro']
            if 'GDP Billion USD' in mc:
                config.financing.gdp_billion_usd = float(_v(mc['GDP Billion USD']))
            if 'GDP Growth Rate' in mc:
                config.financing.gdp_growth_rate = float(_v(mc['GDP Growth Rate']))
            if 'Number of Households' in mc:
                config.connection.number_of_households = int(_v(mc['Number of Households']))
            if 'Avg Household Monthly Consumption' in mc:
                config.current_system.avg_hh_monthly_kwh = float(_v(mc['Avg Household Monthly Consumption']))
            if 'Current Retail Tariff' in mc:
                config.current_system.current_retail_tariff = float(_v(mc['Current Retail Tariff']))
            if 'India Domestic Rate' in mc:
                config.current_system.india_domestic_rate = float(_v(mc['India Domestic Rate']))
            if 'Current Subsidy per kWh' in mc:
                config.current_system.current_subsidy_per_kwh = float(_v(mc['Current Subsidy per kWh']))
            # Item-7: Subsidy reform schedule
            if 'Subsidy Reform Start Year' in mc:
                config.current_system.subsidy_reform_start_year = int(float(_v(mc['Subsidy Reform Start Year'])))
            if 'Subsidy Reform End Year' in mc:
                config.current_system.subsidy_reform_end_year = int(float(_v(mc['Subsidy Reform End Year'])))
            if 'Population 2026' in mc:
                config.current_system.population_2026 = int(_v(mc['Population 2026']))
            if 'Population Growth Rate' in mc:
                config.current_system.population_growth_rate = float(_v(mc['Population Growth Rate']))
        
        # R1/R2/R3: Segmented demand growth (Roadmap calibration)
        if 'Demand' in params:
            d3 = params['Demand']
            # R1: Greater Malé segmented growth
            if 'Male Growth Near Term' in d3:
                config.demand.male_growth_near_term = float(_v(d3['Male Growth Near Term']))
            if 'Male Growth Long Term' in d3:
                config.demand.male_growth_long_term = float(_v(d3['Male Growth Long Term']))
            if 'Male Post-Peak Growth Rate' in d3:
                config.demand.male_post_peak_growth = float(_v(d3['Male Post-Peak Growth Rate']))
            if 'Male Demand Min Share' in d3:
                config.demand.male_demand_min_share = float(_v(d3['Male Demand Min Share']))
            if 'Male Demand Saturation Year' in d3:
                config.demand.male_demand_saturation_year = int(_v(d3['Male Demand Saturation Year']))
            # R2: Outer island segmented growth
            if 'Outer Growth Near Term' in d3:
                config.demand.outer_growth_near_term = float(_v(d3['Outer Growth Near Term']))
            if 'Outer Growth Long Term' in d3:
                config.demand.outer_growth_long_term = float(_v(d3['Outer Growth Long Term']))
            if 'Outer Growth Taper Year' in d3:
                config.demand.outer_growth_taper_year = int(_v(d3['Outer Growth Taper Year']))
            if 'Outer Post-Peak Growth Rate' in d3:
                config.demand.outer_post_peak_growth = float(_v(d3['Outer Post-Peak Growth Rate']))
            # R3: Resort growth (informational)
            if 'Resort Growth Rate' in d3:
                config.demand.resort_growth_rate = float(_v(d3['Resort Growth Rate']))
            # A-M-01: Demand saturation ceiling
            if 'Demand Saturation kWh per Capita' in d3:
                config.demand.demand_saturation_kwh_per_capita = float(_v(d3['Demand Saturation kWh per Capita']))
        
        # D61: Near-shore and floating solar
        if 'Near-Shore Solar' in params:
            ns = params['Near-Shore Solar']
            if 'Near-Shore Solar MW' in ns:
                config.nearshore.nearshore_solar_mw = float(_v(ns['Near-Shore Solar MW']))
            if 'Near-Shore Cable Cost per MW' in ns:
                config.nearshore.nearshore_cable_cost_per_mw = float(_v(ns['Near-Shore Cable Cost per MW']))
            if 'Near-Shore Build Start' in ns:
                config.nearshore.nearshore_build_start = int(_v(ns['Near-Shore Build Start']))
            if 'Near-Shore Build Years' in ns:
                config.nearshore.nearshore_build_years = int(_v(ns['Near-Shore Build Years']))
            if 'Floating Solar MW' in ns:
                config.nearshore.floating_solar_mw = float(_v(ns['Floating Solar MW']))
            if 'Floating Solar CAPEX Premium' in ns:
                config.nearshore.floating_solar_capex_premium = float(_v(ns['Floating Solar CAPEX Premium']))
            if 'Floating Solar Build Start' in ns:
                config.nearshore.floating_build_start = int(_v(ns['Floating Solar Build Start']))
            if 'Floating Solar Build Years' in ns:
                config.nearshore.floating_build_years = int(_v(ns['Floating Solar Build Years']))
        
        # R9: LNG Transition parameters
        if 'LNG' in params:
            lng = params['LNG']
            if 'LNG Plant Capacity MW' in lng:
                config.lng.plant_capacity_mw = float(_v(lng['LNG Plant Capacity MW']))
            if 'LNG CAPEX per MW' in lng:
                config.lng.capex_per_mw = float(_v(lng['LNG CAPEX per MW']))
            if 'LNG OPEX per MWh' in lng:
                config.lng.opex_per_mwh = float(_v(lng['LNG OPEX per MWh']))
            if 'LNG Fuel Cost per MWh' in lng:
                config.lng.fuel_cost_per_mwh = float(_v(lng['LNG Fuel Cost per MWh']))
            if 'LNG Fuel Escalation' in lng:
                config.lng.fuel_escalation = float(_v(lng['LNG Fuel Escalation']))
            if 'LNG Emission Factor' in lng:
                config.lng.emission_factor = float(_v(lng['LNG Emission Factor']))
            if 'LNG Construction Start' in lng:
                config.lng.construction_start = int(_v(lng['LNG Construction Start']))
            if 'LNG Online Year' in lng:
                config.lng.online_year = int(_v(lng['LNG Online Year']))
            if 'LNG Plant Lifetime' in lng:
                config.lng.plant_lifetime = int(_v(lng['LNG Plant Lifetime']))
            if 'LNG Capacity Factor' in lng:
                config.lng.capacity_factor = float(_v(lng['LNG Capacity Factor']))
        
        # MCA Scores — LNG Transition (S7) — deferred to after score_map is defined
        
        # R6: Waste-to-Energy parameters
        if 'WTE' in params:
            wte = params['WTE']
            if 'WTE Total Capacity MW' in wte:
                config.wte.total_capacity_mw = float(_v(wte['WTE Total Capacity MW']))
            if 'WTE CAPEX per kW' in wte:
                config.wte.capex_per_kw = float(_v(wte['WTE CAPEX per kW']))
            if 'WTE OPEX pct' in wte:
                config.wte.opex_pct = float(_v(wte['WTE OPEX pct']))
            if 'WTE Capacity Factor' in wte:
                config.wte.capacity_factor = float(_v(wte['WTE Capacity Factor']))
            if 'WTE Plant Lifetime' in wte:
                config.wte.plant_lifetime = int(_v(wte['WTE Plant Lifetime']))
            if 'WTE Online Year' in wte:
                config.wte.online_year = int(_v(wte['WTE Online Year']))
            if 'WTE Emission Factor' in wte:
                config.wte.emission_factor = float(_v(wte['WTE Emission Factor']))
        
        # RE deployment parameters — endogenous ramp-based approach
        # CSV category: "RE Deployment" (replaces old "RE Targets")
        for cat_key in ('RE Deployment', 'RE Targets'):
            if cat_key in params:
                rd = params[cat_key]
                if 'Deployment Ramp MW per Year' in rd:
                    config.green_transition.deployment_ramp_mw_per_year = float(_v(rd['Deployment Ramp MW per Year']))
                if 'Initial RE Share Outer' in rd:
                    config.green_transition.initial_re_share_outer = float(_v(rd['Initial RE Share Outer']))
                if 'Domestic RE Target 2050' in rd:
                    config.one_grid.domestic_re_target_2050 = float(_v(rd['Domestic RE Target 2050']))
                if 'Male Max RE Share' in rd:
                    config.green_transition.male_max_re_share = float(_v(rd['Male Max RE Share']))
                # D-MO-07: Wire inter_island_grid boolean from CSV
                if 'Inter Island Grid' in rd:
                    config.green_transition.inter_island_grid = bool(int(float(_v(rd['Inter Island Grid']))))
        
        # L17: MCA weights and qualitative scores
        if 'MCA Weights' in params:
            mw = params['MCA Weights']
            weight_map = {
                'Economic Efficiency': 'w_economic_efficiency',
                'Environmental Impact': 'w_environmental_impact',
                'Energy Security': 'w_energy_security',
                'Health Benefits': 'w_health_benefits',
                'Fiscal Burden': 'w_fiscal_burden',
                'Implementation Feasibility': 'w_implementation_ease',
                'Social Equity': 'w_social_equity',
                'Climate Resilience': 'w_climate_resilience',
            }
            for csv_name, attr_name in weight_map.items():
                if csv_name in mw:
                    setattr(config.mca, attr_name, float(_v(mw[csv_name])))
            # G-LO-03: Validate MCA weights sum to ~1.0 at load time
            weight_sum = sum(
                getattr(config.mca, attr) for attr in weight_map.values()
            )
            if abs(weight_sum - 1.0) > 0.01:
                logger.warning(
                    "G-LO-03: MCA weights sum to %.3f (expected 1.0) — "
                    "check MCA Weights in parameters.csv",
                    weight_sum
                )
        
        # MCA qualitative scores per scenario
        score_map = {
            'Implementation Feasibility': 'implementation',
            'Social Equity': 'equity',
            'Climate Resilience': 'resilience',
        }
        for cat_suffix, prefix in [('MCA Scores FI', 'fi'), ('MCA Scores NG', 'ng'), ('MCA Scores IG', 'ig')]:
            if cat_suffix in params:
                sc = params[cat_suffix]
                for csv_name, short in score_map.items():
                    if csv_name in sc:
                        setattr(config.mca, f'{prefix}_{short}', float(_v(sc[csv_name])))
        
        # MCA Scores — Near-Shore Solar (S5), Maximum RE (S6), LNG Transition (S7)
        for cat_suffix, prefix in [('MCA Scores NS', 'ns'), ('MCA Scores MX', 'mx'), ('MCA Scores LNG', 'lng')]:
            if cat_suffix in params:
                sc = params[cat_suffix]
                for csv_name, short in score_map.items():
                    if csv_name in sc:
                        setattr(config.mca, f'{prefix}_{short}', float(_v(sc[csv_name])))
        
        # Time category — wire CSV to Config time fields
        if 'Time' in params:
            t = params['Time']
            if 'Base Year' in t:
                config.base_year = int(_v(t['Base Year']))
            if 'Horizon 20yr' in t:
                config.end_year_20 = int(_v(t['Horizon 20yr']))
            if 'Horizon 30yr' in t:
                config.end_year_30 = int(_v(t['Horizon 30yr']))
                config.end_year = int(_v(t['Horizon 30yr']))
            if 'Horizon 50yr' in t:
                config.end_year_50 = int(_v(t['Horizon 50yr']))
            # Rebuild time_horizon from updated base/end years
            config.time_horizon = list(range(config.base_year, config.end_year + 1))
        
        # LCOE Benchmarks — for report comparison charts
        if 'Benchmarks' in params:
            bm = params['Benchmarks']
            bm_map = {
                'Global Solar LCOE': 'global_solar_lcoe',
                'Global Diesel Gen LCOE': 'global_diesel_gen_lcoe',
                'SIDS Avg Renewable LCOE': 'sids_avg_renewable_lcoe',
                'Maldives CIF ASPIRE LCOE': 'maldives_cif_aspire_lcoe',
                'Tokelau LCOE': 'tokelau_lcoe',
                'Cook Islands LCOE': 'cook_islands_lcoe',
                'Barbados LCOE': 'barbados_lcoe',
                'Fiji LCOE': 'fiji_lcoe',
            }
            for csv_name, attr_name in bm_map.items():
                if csv_name in bm:
                    setattr(config.benchmarks, attr_name, float(_v(bm[csv_name])))
        
        # Distributional shares — illustrative cost/benefit allocation
        if 'Distributional' in params:
            ds = params['Distributional']
            ds_map = {
                'Cost Share Government': 'cost_share_government',
                'Cost Share MDBs': 'cost_share_mdbs',
                'Cost Share India': 'cost_share_india',
                'Cost Share Private': 'cost_share_private',
                'Benefit Share Households': 'benefit_share_households',
                'Benefit Share Businesses': 'benefit_share_businesses',
                'Benefit Share Government': 'benefit_share_government',
                'Benefit Share Climate': 'benefit_share_climate',
                'Benefit Share Workers': 'benefit_share_workers',
            }
            for csv_name, attr_name in ds_map.items():
                if csv_name in ds:
                    setattr(config.distributional, attr_name, float(_v(ds[csv_name])))
        
        # Investment Phasing — illustrative allocation by technology × period
        if 'Investment Phasing' in params:
            ip = params['Investment Phasing']
            ip_map = {
                'Solar 2026-28': 'solar_2026_28',
                'Solar 2029-32': 'solar_2029_32',
                'Solar 2033-36': 'solar_2033_36',
                'Solar 2037-40': 'solar_2037_40',
                'Solar 2041-50': 'solar_2041_50',
                'Battery 2026-28': 'battery_2026_28',
                'Battery 2029-32': 'battery_2029_32',
                'Battery 2033-36': 'battery_2033_36',
                'Battery 2037-40': 'battery_2037_40',
                'Battery 2041-50': 'battery_2041_50',
                'Inter-Island 2026-28': 'inter_island_2026_28',
                'Inter-Island 2029-32': 'inter_island_2029_32',
                'Inter-Island 2033-36': 'inter_island_2033_36',
                'Inter-Island 2037-40': 'inter_island_2037_40',
                'Inter-Island 2041-50': 'inter_island_2041_50',
                'India Cable 2026-28': 'india_cable_2026_28',
                'India Cable 2029-32': 'india_cable_2029_32',
                'India Cable 2033-36': 'india_cable_2033_36',
                'India Cable 2037-40': 'india_cable_2037_40',
                'India Cable 2041-50': 'india_cable_2041_50',
            }
            for csv_name, attr_name in ip_map.items():
                if csv_name in ip:
                    setattr(config.investment_phasing, attr_name, float(_v(ip[csv_name])))
        
        # P7: Climate damage scenario parameters
        if 'Climate' in params:
            cl = params['Climate']
            if 'RCP45 GHI Change 2050' in cl:
                config.technology.rcp45_ghi_change_2050 = float(_v(cl['RCP45 GHI Change 2050']))
            if 'RCP85 GHI Change 2050' in cl:
                config.technology.rcp85_ghi_change_2050 = float(_v(cl['RCP85 GHI Change 2050']))
            if 'RCP45 Temp Rise 2050' in cl:
                config.technology.rcp45_temp_rise_2050 = float(_v(cl['RCP45 Temp Rise 2050']))
            if 'RCP85 Temp Rise 2050' in cl:
                config.technology.rcp85_temp_rise_2050 = float(_v(cl['RCP85 Temp Rise 2050']))
            if 'Climate Scenario Year' in cl:
                config.technology.climate_scenario_year = int(_v(cl['Climate Scenario Year']))
        
        # P8: Transport electrification parameters
        if 'Transport Fleet' in params:
            tf = params['Transport Fleet']
            if 'Total Vehicles 2026' in tf:
                config.transport.total_vehicles_2026 = int(_v(tf['Total Vehicles 2026']))
            if 'Motorcycle Share' in tf:
                config.transport.motorcycle_share = float(_v(tf['Motorcycle Share']))
            if 'EV Share 2026' in tf:
                config.transport.ev_share_2026 = float(_v(tf['EV Share 2026']))
            if 'Fleet Growth Rate' in tf:
                config.transport.fleet_growth_rate = float(_v(tf['Fleet Growth Rate']))
        
        if 'Transport EV' in params:
            te = params['Transport EV']
            if 'EV Target Low 2056' in te:
                config.transport.ev_target_low = float(_v(te['EV Target Low 2056']))
            if 'EV Target Medium 2056' in te:
                config.transport.ev_target_medium = float(_v(te['EV Target Medium 2056']))
            if 'EV Target High 2056' in te:
                config.transport.ev_target_high = float(_v(te['EV Target High 2056']))
            if 'EV Adoption Midpoint' in te:
                config.transport.ev_adoption_midpoint = int(_v(te['EV Adoption Midpoint']))
            if 'EV Adoption Steepness' in te:
                config.transport.ev_adoption_steepness = float(_v(te['EV Adoption Steepness']))
        
        if 'Transport Energy' in params:
            ten = params['Transport Energy']
            if 'Motorcycle Daily km' in ten:
                config.transport.motorcycle_daily_km = float(_v(ten['Motorcycle Daily km']))
            if 'ICE Fuel Consumption' in ten:
                config.transport.ice_fuel_consumption_l_100km = float(_v(ten['ICE Fuel Consumption']))
            if 'EV Energy per km' in ten:
                config.transport.ev_energy_per_km = float(_v(ten['EV Energy per km']))
            if 'Petrol Price 2026' in ten:
                config.transport.petrol_price_2026 = float(_v(ten['Petrol Price 2026']))
            if 'Petrol Price Escalation' in ten:
                config.transport.petrol_price_escalation = float(_v(ten['Petrol Price Escalation']))
        
        if 'Transport Costs' in params:
            tc = params['Transport Costs']
            if 'E-Motorcycle Premium 2026' in tc:
                config.transport.e_motorcycle_premium_2026 = float(_v(tc['E-Motorcycle Premium 2026']))
            if 'Premium Decline Rate' in tc:
                config.transport.premium_decline_rate = float(_v(tc['Premium Decline Rate']))
            if 'Charging Station Cost' in tc:
                config.transport.charging_station_cost = float(_v(tc['Charging Station Cost']))
            if 'Vehicles per Station' in tc:
                config.transport.vehicles_per_station = int(_v(tc['Vehicles per Station']))
            if 'ICE Annual Maintenance' in tc:
                config.transport.ice_annual_maintenance = float(_v(tc['ICE Annual Maintenance']))
            if 'EV Annual Maintenance' in tc:
                config.transport.ev_annual_maintenance = float(_v(tc['EV Annual Maintenance']))
        
        if 'Transport Health' in params:
            th = params['Transport Health']
            if 'PM25 Damage per Vehicle km' in th:
                config.transport.pm25_damage_per_vkm = float(_v(th['PM25 Damage per Vehicle km']))
            if 'NOx Damage per Vehicle km' in th:
                config.transport.nox_damage_per_vkm = float(_v(th['NOx Damage per Vehicle km']))
            if 'Noise Reduction per EV km' in th:
                config.transport.noise_reduction_per_ev_km = float(_v(th['Noise Reduction per EV km']))
        
        if 'Transport CO2' in params:
            tco2 = params['Transport CO2']
            if 'ICE Motorcycle gCO2 per km' in tco2:
                config.transport.ice_gco2_per_km = float(_v(tco2['ICE Motorcycle gCO2 per km']))
        
        # Build sensitivity ranges from CSV Low/High columns
        _update_sensitivity_params_from_csv(params)
    
    # Compute derived values that depend on multiple config sections
    # C4: Full cable cost = submarine cable + converter stations + landing + IDC + grid upgrade
    if config.one_grid.cable_capex_total is None:
        submarine_cable = config.one_grid.cable_length_km * config.technology.cable_capex_per_km
        converter_stations = config.technology.converter_station_cost_per_mw * config.one_grid.cable_capacity_mw
        landing = config.technology.landing_cost_per_end * config.technology.num_landings
        base_capex = submarine_cable + converter_stations + landing
        idc = base_capex * config.technology.idc_rate
        grid_upgrade = config.technology.grid_upgrade_cost
        config.one_grid.cable_capex_total = base_capex + idc + grid_upgrade
    
    # D-MO-01: Log warnings for critical CSV categories that were not found
    if load_from_csv and PARAMETERS_CSV.exists():
        expected_categories = [
            'Current System', 'Solar', 'Battery', 'Diesel Gen', 'Economics',
            'Demand', 'Environment', 'Health', 'Cable', 'Financing', 'Macro',
            'Fuel', 'Losses', 'Dispatch', 'PPA', 'Reliability',
        ]
        for cat in expected_categories:
            if cat not in params:
                logger.warning(
                    "D-MO-01: CSV category '%s' not found in %s — "
                    "using dataclass defaults (potential silent bug)",
                    cat, PARAMETERS_CSV
                )
    
    return config


def _update_sensitivity_params_from_csv(params: Dict):
    """Update SENSITIVITY_PARAMS from CSV Low/High columns."""
    global SENSITIVITY_PARAMS
    
    mapping = [
        ('Economics', 'Discount Rate', 'discount_rate'),
        ('Fuel', 'Diesel Price 2026', 'diesel_price'),
        ('Fuel', 'Diesel Price Escalation', 'diesel_escalation'),
        ('PPA', 'Import Price 2030', 'import_price'),
        ('Solar', 'CAPEX 2026', 'solar_capex'),
        ('Solar', 'Capacity Factor', 'solar_cf'),
        ('Battery', 'CAPEX 2026', 'battery_capex'),
        ('Cable', 'CAPEX per km', 'cable_capex_per_km'),
        ('Cable', 'GoM Cost Share', 'gom_cost_share'),
        ('Economics', 'Social Cost of Carbon', 'social_cost_carbon'),
        ('Demand', 'Growth Rate - BAU', 'demand_growth'),
        ('Cable Outage', 'Outage Rate', 'outage_rate'),
        ('Supply Security', 'Idle Fleet Annual Cost', 'idle_fleet_cost'),
        ('Demand', 'Price Elasticity of Demand', 'price_elasticity'),
        # L14: Expanded parameters
        ('Health', 'Damage Cost per MWh Diesel', 'health_damage'),
        ('Fuel', 'Fuel Efficiency', 'fuel_efficiency'),
        ('Demand', 'Base Demand 2026', 'base_demand'),
        ('Battery', 'Storage Hours', 'battery_hours'),
        ('Climate', 'Adaptation CAPEX Premium', 'climate_premium'),
        ('Cable', 'Converter Station Cost per MW', 'converter_station'),
        ('Connection', 'Cost per Household', 'connection_cost'),
        # M5: Sectoral split
        ('Electricity Structure', 'Sectoral Split Residential', 'sectoral_residential'),
        # V2b: S5/S6/S7-specific parameters
        ('LNG', 'LNG CAPEX per MW', 'lng_capex'),
        ('LNG', 'LNG Fuel Cost per MWh', 'lng_fuel_cost'),
        ('LNG', 'LNG Fuel Escalation', 'lng_fuel_escalation'),
        ('LNG', 'LNG Emission Factor', 'lng_emission_factor'),
        ('Near-Shore Solar', 'Floating Solar CAPEX Premium', 'floating_capex_premium'),
        ('Near-Shore Solar', 'Floating Solar MW', 'floating_solar_mw'),
        ('Near-Shore Solar', 'Near-Shore Solar MW', 'nearshore_solar_mw'),
        ('Near-Shore Solar', 'Near-Shore Cable Cost per MW', 'nearshore_cable_cost'),
        ('WTE', 'WTE CAPEX per kW', 'wte_capex'),
        ('RE Deployment', 'Deployment Ramp MW per Year', 'deployment_ramp'),
        ('RE Deployment', 'Male Max RE Share', 'male_max_re'),
        ('Islanded', 'Battery Ratio', 'battery_ratio'),
        # P8: Transport electrification
        ('Transport EV', 'EV Adoption Midpoint', 'ev_adoption_midpoint'),
        ('Transport Costs', 'E-Motorcycle Premium 2026', 'ev_motorcycle_premium'),
        ('Transport Health', 'PM25 Damage per Vehicle km', 'transport_health_damage'),
        ('Transport Energy', 'Petrol Price 2026', 'petrol_price'),
        # Item-2: 6 additional high-impact params
        ('Demand', 'Demand Saturation kWh per Capita', 'demand_saturation'),
        ('Demand', 'Male Growth Near Term', 'male_growth_near'),
        ('Solar', 'Degradation Rate', 'pv_degradation'),
        ('Cable', 'IDC Rate', 'idc_rate'),
        ('LNG', 'LNG Plant Capacity MW', 'lng_capacity_mw'),
        ('Macro', 'Current Subsidy per kWh', 'subsidy_per_kwh'),
    ]
    
    for category, param_name, sens_key in mapping:
        if category in params and param_name in params[category]:
            entry = params[category][param_name]
            if isinstance(entry, dict):
                base = entry['value']
                low = entry.get('low', base * 0.7)
                high = entry.get('high', base * 1.3)
                SENSITIVITY_PARAMS[sens_key] = {
                    'low': float(low), 'base': float(base), 'high': float(high)
                }
    
    # L14: env_externality is a composite (noise + spill + biodiversity)
    # Build from individual Environment params if available
    if 'Environment' in params:
        ev = params['Environment']
        noise = _v(ev.get('Noise Damage per MWh Diesel', {'value': 5}))
        spill = _v(ev.get('Fuel Spill Risk per MWh Diesel', {'value': 3}))
        bio = _v(ev.get('Biodiversity Impact per MWh Diesel', {'value': 2}))
        base_env = float(noise) + float(spill) + float(bio)
        # Sum of individual lows/highs
        n_entry = ev.get('Noise Damage per MWh Diesel', {})
        s_entry = ev.get('Fuel Spill Risk per MWh Diesel', {})
        b_entry = ev.get('Biodiversity Impact per MWh Diesel', {})
        low_env = (float(n_entry.get('low', 2)) + float(s_entry.get('low', 1))
                   + float(b_entry.get('low', 1))) if isinstance(n_entry, dict) else base_env * 0.4
        high_env = (float(n_entry.get('high', 10)) + float(s_entry.get('high', 8))
                    + float(b_entry.get('high', 5))) if isinstance(n_entry, dict) else base_env * 2.3
        SENSITIVITY_PARAMS['env_externality'] = {
            'low': low_env, 'base': base_env, 'high': high_env
        }


def print_loaded_parameters():
    """Print all parameters loaded from CSV for verification."""
    params = load_parameters_from_csv()
    print("\n" + "="*60)
    print("PARAMETERS LOADED FROM CSV")
    print("="*60)
    for category, values in params.items():
        print(f"\n[{category}]")
        for param, entry in values.items():
            if isinstance(entry, dict):
                v = entry['value']
                low = entry.get('low', '')
                high = entry.get('high', '')
                if low or high:
                    print(f"  {param}: {v}  [Low={low}, High={high}]")
                else:
                    print(f"  {param}: {v}")
            else:
                print(f"  {param}: {entry}")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Test configuration
    print("Testing parameter loading from CSV...")
    
    # Print what's in the CSV
    print_loaded_parameters()
    
    # Load config with CSV values
    config = get_config(load_from_csv=True)
    
    print("\nConfig values after loading:")
    print(f"  Time horizon: {config.base_year} - {config.end_year}")
    print(f"  Available horizons: 20yr (2026-2046), 30yr (2026-2056), 50yr (2026-2076)")
    print(f"  Base demand: {config.demand.base_demand_gwh} GWh")
    print(f"  Current solar capacity: {config.current_system.solar_capacity_mw} MW")
    print(f"  Current RE share: {config.current_system.re_share:.1%}")
    print(f"  Diesel price 2026: ${config.fuel.price_2026}/L")
    print(f"  Diesel price 2036: ${config.fuel.get_price(2036):.2f}/L")
    print(f"  Discount rate: {config.economics.discount_rate:.1%}")
    print(f"  Solar CAPEX: ${config.technology.solar_pv_capex}/kW")
    print(f"  Cable length: {config.one_grid.cable_length_km} km")
    
    warnings = config.validate()
    if warnings:
        print(f"\nWarnings: {warnings}")
    else:
        print("\n✓ Configuration valid!")
