"""
Least-Cost Electrification Engine
===================================
Per-island technology assignment using simplified OnSSET methodology.

For each of 40 islands, compute LCOE for 4 technologies:
  1. Grid extension (submarine cable to nearest hub/larger island)
  2. Solar + battery (standalone microgrid)
  3. Diesel (standalone generator)
  4. Solar-diesel hybrid

Pick minimum LCOE per island → assign technology.
Assign progressive deployment tranche (T0–T4).

Adapted from GEP-OnSSET `get_lcoe()` (archived onsset_maldives.py L406–640).
Uses verified parameters from parameters.csv via config.py.

References:
  - Korkovelos et al. (2019), Energies 12(7):1395
  - IRENA RPGC 2024, BNEF 2025, IPCC 2006
"""

import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ── Constants ──────────────────────────────────────────────────────────────────
HOURS_PER_YEAR = 8_760


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class TechParams:
    """Technology-neutral parameters loaded from config."""
    discount_rate: float = 0.06
    project_life: int = 30        # years (2026–2056)
    distribution_loss: float = 0.11
    routing_premium: float = 1.15
    reserve_margin: float = 0.15   # from Operations/Reserve Margin
    num_people_per_hh: float = 5.0  # Maldives avg household size
    default_ghi: float = 5.55       # kWh/m²/day fallback
    default_temp: float = 28.0      # °C fallback


@dataclass
class SolarBatteryParams:
    """Solar + battery microgrid parameters."""
    solar_capex_per_kw: float = 1500.0      # USD/kW (AIIB 2021 Maldives)
    solar_opex_pct: float = 0.015           # % of CAPEX/yr
    solar_lifetime: int = 30                # years
    solar_capacity_factor: float = 0.175
    solar_degradation: float = 0.005        # %/yr
    solar_cost_decline: float = 0.04        # %/yr

    battery_capex_per_kwh: float = 350.0    # USD/kWh (AIIB 2021 + Lazard 2023)
    battery_opex_per_kwh: float = 5.0       # USD/kWh/yr
    battery_lifetime: int = 15              # years
    battery_efficiency: float = 0.88        # round-trip
    battery_hours: float = 4.0              # hours of storage at peak load
    battery_cost_decline: float = 0.06      # %/yr
    battery_dod: float = 0.80               # max depth of discharge

    # Temperature derating
    temp_derating_coeff: float = 0.005      # /°C
    noct_coeff: float = 25.6                # °C per kW/m²

    # Solar land constraint
    max_solar_land_fraction: float = 0.15   # max fraction of island area for solar
    solar_area_per_kw: float = 7.0          # m²/kW (panel + spacing)


@dataclass
class DieselParams:
    """Diesel generator parameters."""
    capex_per_kw: float = 800.0             # USD/kW
    opex_per_kwh: float = 0.025             # USD/kWh O&M
    lifetime: int = 20                      # years
    fuel_price_usd_per_liter: float = 0.85  # 2026 base
    fuel_escalation: float = 0.02           # %/yr real
    fuel_curve_idle: float = 0.08145        # l/hr per kW capacity
    fuel_curve_prop: float = 0.246          # l/kWh generated
    min_load_fraction: float = 0.40
    hybrid_default_solar_share: float = 0.60  # default solar share in hybrid


@dataclass
class GridExtParams:
    """Submarine cable grid extension parameters."""
    cable_capex_per_km: float = 1_500_000.0  # USD/km (shallow intra-atoll)
    cable_opex_pct: float = 0.02             # % of CAPEX/yr
    cable_lifetime: int = 40                 # years
    cable_loss_pct: float = 0.03             # per-cable segment loss
    # The grid electricity price at the hub (blended import/local generation)
    hub_electricity_price: float = 0.06      # USD/kWh at hub (India import or local solar)


@dataclass
class IslandResult:
    """Technology assignment result for one island."""
    island: str
    atoll: str
    population: int
    demand_kwh: float          # annual demand (kWh)
    peak_kw: float             # peak demand (kW)

    # LCOE by technology (USD/kWh)
    lcoe_solar_battery: float
    lcoe_diesel: float
    lcoe_hybrid: float
    lcoe_grid_ext: float       # inf if no larger island nearby

    # Investment cost by technology (USD)
    invest_solar_battery: float
    invest_diesel: float
    invest_hybrid: float
    invest_grid_ext: float

    # Assignment
    best_tech: str             # 'solar_battery', 'diesel', 'hybrid', 'grid_ext'
    best_lcoe: float
    best_invest: float

    # Grid extension details
    nearest_hub: str
    distance_km: float
    cable_cost_usd: float

    # Tranche assignment
    tranche: str               # 'T0', 'T1', 'T2', 'T3', 'T4'

    # GIS data
    ghi: float = 0.0
    temp: float = 0.0
    area_km2: float = 0.0

    # Solar land constraint
    solar_land_fraction: float = 0.0        # fraction of island area needed for 100% solar
    solar_constrained: bool = False          # True if solar exceeds max_solar_land_fraction


# ── Core LCOE functions ───────────────────────────────────────────────────────

def _discounted_lcoe(
    capex: float,
    annual_opex: float,
    annual_fuel: float,
    annual_generation_kwh: float,
    tech_life: int,
    project_life: int,
    discount_rate: float,
    degradation: float = 0.0,
) -> Tuple[float, float]:
    """
    Standard discounted lifecycle cost / discounted lifecycle generation.
    Handles reinvestment if tech_life < project_life, and salvage value.

    Returns (lcoe_usd_per_kwh, total_discounted_investment).

    Adapted from OnSSET get_lcoe() (onsset_maldives.py L574–620).
    """
    years = np.arange(project_life)
    discount_factors = (1 + discount_rate) ** years

    # Generation with degradation (year 0 = no generation, construction year)
    gen = annual_generation_kwh * np.ones(project_life)
    gen[0] = 0.0
    if degradation > 0:
        for y in range(1, project_life):
            gen[y] = annual_generation_kwh * (1 - degradation) ** (y - 1)

    # Investment schedule
    investments = np.zeros(project_life)
    investments[0] = capex
    # Reinvestment at end of tech life
    if tech_life < project_life:
        reinvest_year = tech_life
        if reinvest_year < project_life:
            investments[reinvest_year] = capex
        # Multiple reinvestments for very short-lived tech
        y = reinvest_year + tech_life
        while y < project_life:
            investments[y] = capex
            y += tech_life

    # Salvage value (straight-line depreciation at project end)
    # C-WC-02: Equivalent to npv_calculator modular arithmetic since investments
    # follow tech_life-period cycles (0, tech_life, 2*tech_life, ...)
    salvage = np.zeros(project_life)
    years_since_last_invest = project_life - 1  # default
    for y in range(project_life - 1, -1, -1):
        if investments[y] > 0:
            years_since_last_invest = (project_life - 1) - y
            break
    remaining_life_frac = max(0.0, 1.0 - years_since_last_invest / tech_life)
    salvage[-1] = capex * remaining_life_frac

    # O&M and fuel
    opex = annual_opex * np.ones(project_life)
    opex[0] = 0.0
    fuel = annual_fuel * np.ones(project_life)
    fuel[0] = 0.0

    # Discounted sums
    disc_costs = (investments + opex + fuel - salvage) / discount_factors
    disc_gen = gen / discount_factors

    total_disc_gen = np.sum(disc_gen)
    if total_disc_gen <= 0:
        return (999.0, np.sum(investments))

    lcoe = np.sum(disc_costs) / total_disc_gen
    total_disc_invest = np.sum(investments / discount_factors)
    return (lcoe, total_disc_invest)


def lcoe_solar_battery(
    peak_kw: float,
    demand_kwh: float,
    ghi_kwh_m2_day: float,
    temp_c: float,
    params: SolarBatteryParams,
    tech: TechParams,
) -> Tuple[float, float]:
    """
    LCOE for standalone solar + battery microgrid.

    Sizing:
      - Solar capacity to meet annual demand (with losses, CF, degradation)
      - Battery sized as `battery_hours` × peak_kw (usable after DoD)
    """
    if peak_kw <= 0 or demand_kwh <= 0:
        return (999.0, 0.0)

    # Gross demand (after distribution losses)
    gross_demand = demand_kwh / (1 - tech.distribution_loss)

    # Temperature derating
    t_cell = temp_c + params.noct_coeff * (ghi_kwh_m2_day / 24.0)  # approx
    derating = 1.0 - params.temp_derating_coeff * max(0, t_cell - 25.0)

    # Effective capacity factor
    effective_cf = params.solar_capacity_factor * derating

    # Solar capacity needed (kW)
    solar_kw = gross_demand / (effective_cf * HOURS_PER_YEAR)

    # Battery capacity (kWh nameplate; usable = nameplate × DoD)
    battery_kwh = (peak_kw * params.battery_hours) / params.battery_dod

    # CAPEX
    solar_capex = solar_kw * params.solar_capex_per_kw
    battery_capex = battery_kwh * params.battery_capex_per_kwh
    total_capex = solar_capex + battery_capex

    # Annual O&M
    solar_opex = solar_capex * params.solar_opex_pct
    battery_opex = battery_kwh * params.battery_opex_per_kwh
    total_opex = solar_opex + battery_opex

    # Annual generation (kWh) — solar only, battery just stores it
    annual_gen = solar_kw * effective_cf * HOURS_PER_YEAR

    # Battery reinvestment: battery has shorter life than solar
    # We handle this by computing solar and battery LCOE components separately
    # and adding them, since they have different lifetimes.

    # Solar LCOE component
    lcoe_solar, invest_solar = _discounted_lcoe(
        capex=solar_capex,
        annual_opex=solar_opex,
        annual_fuel=0.0,
        annual_generation_kwh=annual_gen,
        tech_life=params.solar_lifetime,
        project_life=tech.project_life,
        discount_rate=tech.discount_rate,
        degradation=params.solar_degradation,
    )

    # Battery LCOE component (adds cost but no generation)
    # C-MO-01 fix: use same degradation as solar — battery delivers degraded solar output
    lcoe_batt, invest_batt = _discounted_lcoe(
        capex=battery_capex,
        annual_opex=battery_opex,
        annual_fuel=0.0,
        annual_generation_kwh=annual_gen,  # attributed to solar gen
        tech_life=params.battery_lifetime,
        project_life=tech.project_life,
        discount_rate=tech.discount_rate,
        degradation=params.solar_degradation,
    )

    total_lcoe = lcoe_solar + lcoe_batt
    total_invest = invest_solar + invest_batt
    return (total_lcoe, total_invest)


def lcoe_diesel(
    peak_kw: float,
    demand_kwh: float,
    params: DieselParams,
    tech: TechParams,
) -> Tuple[float, float]:
    """
    LCOE for standalone diesel generation.

    Uses two-part fuel curve: fuel = capacity × idle_coeff + generation × prop_coeff
    """
    if peak_kw <= 0 or demand_kwh <= 0:
        return (999.0, 0.0)

    gross_demand = demand_kwh / (1 - tech.distribution_loss)

    # Diesel capacity (kW) = peak + reserve margin
    reserve_margin = tech.reserve_margin
    diesel_kw = peak_kw * (1.0 + reserve_margin)

    capex = diesel_kw * params.capex_per_kw

    # Annual generation
    annual_gen = gross_demand

    # Fuel consumption (two-part curve, annual)
    # C-WC-03: 8760h is correct for standalone diesel — it's the sole power source,
    # so idle fuel accrues over all hours. Hybrid function adjusts by (1-solar_share).
    fuel_litres = (diesel_kw * params.fuel_curve_idle * HOURS_PER_YEAR +
                   annual_gen * params.fuel_curve_prop)

    # Average annual fuel cost (use midpoint escalation for lifecycle)
    # For LCOE we use base-year price; escalation is handled in the
    # discounted framework via annual fuel cost growth
    annual_fuel_cost = fuel_litres * params.fuel_price_usd_per_liter

    # O&M
    annual_opex = annual_gen * params.opex_per_kwh

    # For fuel escalation, we compute LCOE with escalating fuel costs
    years = np.arange(tech.project_life)
    discount_factors = (1 + tech.discount_rate) ** years

    gen = annual_gen * np.ones(tech.project_life)
    gen[0] = 0.0

    investments = np.zeros(tech.project_life)
    investments[0] = capex
    if params.lifetime < tech.project_life:
        y = params.lifetime
        while y < tech.project_life:
            investments[y] = capex
            y += params.lifetime

    # Salvage
    salvage = np.zeros(tech.project_life)
    last_invest_year = 0
    for y in range(tech.project_life - 1, -1, -1):
        if investments[y] > 0:
            last_invest_year = y
            break
    years_used = (tech.project_life - 1) - last_invest_year
    salvage[-1] = capex * max(0, 1 - years_used / params.lifetime)

    opex_arr = annual_opex * np.ones(tech.project_life)
    opex_arr[0] = 0.0

    # Fuel with escalation
    fuel_arr = np.zeros(tech.project_life)
    for y in range(1, tech.project_life):
        esc_price = params.fuel_price_usd_per_liter * (1 + params.fuel_escalation) ** (y - 1)
        fuel_litres_y = (diesel_kw * params.fuel_curve_idle * HOURS_PER_YEAR +
                         gen[y] * params.fuel_curve_prop)
        fuel_arr[y] = fuel_litres_y * esc_price

    disc_costs = (investments + opex_arr + fuel_arr - salvage) / discount_factors
    disc_gen = gen / discount_factors

    total_disc_gen = np.sum(disc_gen)
    if total_disc_gen <= 0:
        return (999.0, capex)

    lcoe = np.sum(disc_costs) / total_disc_gen
    total_invest = np.sum(investments / discount_factors)
    return (lcoe, total_invest)


def lcoe_solar_diesel_hybrid(
    peak_kw: float,
    demand_kwh: float,
    ghi_kwh_m2_day: float,
    temp_c: float,
    solar_params: SolarBatteryParams,
    diesel_params: DieselParams,
    tech: TechParams,
    solar_share: float = 0.60,
) -> Tuple[float, float]:
    """
    LCOE for solar-diesel hybrid (no battery, diesel backs up solar).

    Simple approach: solar meets `solar_share` of annual demand,
    diesel provides the rest + all peak/night load.
    """
    if peak_kw <= 0 or demand_kwh <= 0:
        return (999.0, 0.0)

    gross_demand = demand_kwh / (1 - tech.distribution_loss)

    # Solar sizing for its share
    t_cell = temp_c + solar_params.noct_coeff * (ghi_kwh_m2_day / 24.0)
    derating = 1.0 - solar_params.temp_derating_coeff * max(0, t_cell - 25.0)
    effective_cf = solar_params.solar_capacity_factor * derating

    solar_gen = gross_demand * solar_share
    solar_kw = solar_gen / (effective_cf * HOURS_PER_YEAR)
    solar_capex = solar_kw * solar_params.solar_capex_per_kw
    solar_opex = solar_capex * solar_params.solar_opex_pct

    # Diesel for the remainder
    diesel_gen = gross_demand * (1 - solar_share)
    diesel_kw = peak_kw * 1.0  # full peak backup
    diesel_capex = diesel_kw * diesel_params.capex_per_kw
    diesel_opex = diesel_gen * diesel_params.opex_per_kwh

    total_capex = solar_capex + diesel_capex
    total_opex = solar_opex + diesel_opex

    # Fuel (diesel portion only)
    fuel_litres = (diesel_kw * diesel_params.fuel_curve_idle * HOURS_PER_YEAR *
                   (1 - solar_share) +  # idle proportional to diesel runtime
                   diesel_gen * diesel_params.fuel_curve_prop)
    annual_fuel = fuel_litres * diesel_params.fuel_price_usd_per_liter

    # Use blended lifecycle approach
    years = np.arange(tech.project_life)
    discount_factors = (1 + tech.discount_rate) ** years

    # Generation
    gen = gross_demand * np.ones(tech.project_life)
    gen[0] = 0.0
    # Apply solar degradation to solar portion
    for y in range(1, tech.project_life):
        solar_y = solar_gen * (1 - solar_params.solar_degradation) ** (y - 1)
        gen[y] = solar_y + diesel_gen  # diesel fills the rest anyway

    # Investments
    investments = np.zeros(tech.project_life)
    investments[0] = total_capex
    # Diesel reinvestment
    if diesel_params.lifetime < tech.project_life:
        y = diesel_params.lifetime
        while y < tech.project_life:
            investments[y] += diesel_capex
            y += diesel_params.lifetime
    # Solar lasts 30yr, so no reinvestment in 30yr project

    # Salvage
    salvage = np.zeros(tech.project_life)
    # Solar salvage
    solar_years_used = tech.project_life - 1
    solar_salvage_frac = max(0, 1 - solar_years_used / solar_params.solar_lifetime)
    salvage[-1] += solar_capex * solar_salvage_frac
    # Diesel salvage
    last_diesel_invest = 0
    for y in range(tech.project_life - 1, -1, -1):
        if y == 0 or (y > 0 and y % diesel_params.lifetime == 0 and y < tech.project_life):
            last_diesel_invest = y
            break
    diesel_years_used = (tech.project_life - 1) - last_diesel_invest
    diesel_salvage_frac = max(0, 1 - diesel_years_used / diesel_params.lifetime)
    salvage[-1] += diesel_capex * diesel_salvage_frac

    opex_arr = total_opex * np.ones(tech.project_life)
    opex_arr[0] = 0.0

    # Fuel with escalation
    fuel_arr = np.zeros(tech.project_life)
    for y in range(1, tech.project_life):
        esc_price = diesel_params.fuel_price_usd_per_liter * (1 + diesel_params.fuel_escalation) ** (y - 1)
        diesel_gen_y = gen[y] - solar_gen * (1 - solar_params.solar_degradation) ** (y - 1)
        diesel_gen_y = max(0, diesel_gen_y)
        fuel_litres_y = (diesel_kw * diesel_params.fuel_curve_idle * HOURS_PER_YEAR *
                         (1 - solar_share) +
                         diesel_gen_y * diesel_params.fuel_curve_prop)
        fuel_arr[y] = fuel_litres_y * esc_price

    disc_costs = (investments + opex_arr + fuel_arr - salvage) / discount_factors
    disc_gen = gen / discount_factors
    total_disc_gen = np.sum(disc_gen)
    if total_disc_gen <= 0:
        return (999.0, total_capex)

    lcoe = np.sum(disc_costs) / total_disc_gen
    total_invest = np.sum(investments / discount_factors)
    return (lcoe, total_invest)


def lcoe_grid_extension(
    peak_kw: float,
    demand_kwh: float,
    distance_km: float,
    params: GridExtParams,
    tech: TechParams,
) -> Tuple[float, float]:
    """
    LCOE for grid extension via submarine cable to nearest hub.

    Cost = cable CAPEX + cable O&M + hub electricity price.
    Hub electricity price represents the cost of generation at the hub
    (either India import or local diesel/solar mix).
    """
    if peak_kw <= 0 or demand_kwh <= 0 or distance_km <= 0:
        return (999.0, 0.0)

    gross_demand = demand_kwh / (1 - tech.distribution_loss)
    # Additional cable loss
    gross_demand_after_cable = gross_demand / (1 - params.cable_loss_pct)

    cable_capex = distance_km * params.cable_capex_per_km
    annual_cable_opex = cable_capex * params.cable_opex_pct
    annual_electricity_cost = gross_demand_after_cable * params.hub_electricity_price

    lcoe, invest = _discounted_lcoe(
        capex=cable_capex,
        annual_opex=annual_cable_opex,
        annual_fuel=annual_electricity_cost,  # "fuel" = electricity purchase
        annual_generation_kwh=gross_demand,
        tech_life=params.cable_lifetime,
        project_life=tech.project_life,
        discount_rate=tech.discount_rate,
    )
    return (lcoe, invest)


# ── Distance helper ────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ── Tranche assignment ─────────────────────────────────────────────────────────

def assign_tranche(
    island: str,
    atoll: str,
    best_tech: str,
    distance_km: float,
    cable_standalone_ratio: float,
    nearest_hub: str,
) -> str:
    """
    Assign progressive deployment tranche.

    T0: All islands get solar immediately (universal)
    T1: Greater Malé hub connections (2027-2030)
    T2: Economic intra-atoll clusters, ratio < 1.0 (2030-2035)
    T3: Borderline extensions, ratio 1.0-3.0 (2035-2040)
    T4: Everything else — standalone (2040+)
    """
    # T1: Greater Malé area (check both island name AND atoll)
    male_hub_islands = {
        ("Maale", "Male"), ("Hulhumaale", "Male"), ("Vilin'gili", "Male"),
    }
    if (island, atoll) in male_hub_islands:
        return "T1"

    # Grid extension islands
    if best_tech == "grid_ext":
        if cable_standalone_ratio < 1.0:
            # Check if it's a Kaafu/Male atoll connection (part of Greater Malé)
            if atoll in ("Kaafu", "Male"):
                return "T1"
            return "T2"
        elif cable_standalone_ratio < 3.0:
            return "T3"

    # All others: standalone solar (T0 gets solar, T4 is future eval)
    if best_tech in ("solar_battery", "hybrid"):
        return "T0"

    return "T4"


# ── Main engine ────────────────────────────────────────────────────────────────

def load_params_from_config():
    """
    Load all parameters from the config system (which reads parameters.csv).
    Returns (TechParams, SolarBatteryParams, DieselParams, GridExtParams).
    """
    try:
        from .config import get_config
    except ImportError:
        from model.config import get_config

    cfg = get_config()

    tech = TechParams(
        discount_rate=cfg.economics.discount_rate,
        project_life=cfg.end_year - cfg.base_year,  # 2056 - 2026 = 30
        distribution_loss=cfg.technology.distribution_loss_pct,
        routing_premium=cfg.technology.routing_premium,
        reserve_margin=cfg.technology.reserve_margin,
        default_ghi=cfg.technology.default_ghi,
        default_temp=cfg.technology.default_ambient_temp,
    )

    solar = SolarBatteryParams(
        solar_capex_per_kw=cfg.technology.solar_pv_capex,
        solar_opex_pct=cfg.technology.solar_pv_opex_pct,
        solar_lifetime=cfg.technology.solar_pv_lifetime,
        solar_capacity_factor=cfg.technology.solar_pv_capacity_factor,
        solar_degradation=cfg.technology.solar_pv_degradation,
        solar_cost_decline=cfg.technology.solar_pv_cost_decline,
        battery_capex_per_kwh=cfg.technology.battery_capex,
        battery_opex_per_kwh=cfg.technology.battery_opex,
        battery_lifetime=cfg.technology.battery_lifetime,
        battery_efficiency=cfg.technology.battery_efficiency,
        battery_cost_decline=cfg.technology.battery_cost_decline,
        battery_hours=cfg.technology.battery_hours,
        battery_dod=cfg.dispatch.battery_dod_max,
        temp_derating_coeff=cfg.technology.pv_temp_derating_coeff,
        noct_coeff=cfg.technology.pv_noct_coeff,
        max_solar_land_fraction=cfg.technology.max_solar_land_fraction,
        solar_area_per_kw=cfg.technology.solar_area_per_kw,
    )

    diesel = DieselParams(
        capex_per_kw=cfg.technology.diesel_gen_capex,
        opex_per_kwh=cfg.technology.diesel_gen_opex_kwh,
        lifetime=cfg.technology.diesel_gen_lifetime,
        fuel_price_usd_per_liter=cfg.fuel.price_2026,
        fuel_escalation=cfg.fuel.price_escalation,
        fuel_curve_idle=cfg.dispatch.fuel_curve_idle_coeff,
        fuel_curve_prop=cfg.dispatch.fuel_curve_proportional_coeff,
        min_load_fraction=cfg.dispatch.diesel_min_load_fraction,
        hybrid_default_solar_share=cfg.dispatch.hybrid_default_solar_share,
    )

    grid = GridExtParams(
        cable_capex_per_km=cfg.technology.inter_island_capex_per_km,
        cable_opex_pct=cfg.technology.cable_opex_pct,
        cable_lifetime=cfg.technology.cable_lifetime,
        hub_electricity_price=cfg.ppa.import_price_2030,
        cable_loss_pct=cfg.technology.hvdc_cable_loss_pct,
    )

    return tech, solar, diesel, grid


def run_least_cost(
    csv_path: Optional[str] = None,
    tech: Optional[TechParams] = None,
    solar: Optional[SolarBatteryParams] = None,
    diesel: Optional[DieselParams] = None,
    grid: Optional[GridExtParams] = None,
    demand_kwh_per_capita: float = None,
    load_factor: float = None,
) -> List[IslandResult]:
    """
    Run least-cost analysis for all inhabited islands.

    Parameters
    ----------
    csv_path : str
        Path to islands_master.csv (176 islands from GDB + Census P5 2022)
    demand_kwh_per_capita : float
        Annual electricity demand per person (kWh/capita/yr).
        Default loaded from config: base_demand / population.
    load_factor : float
        Ratio of average to peak demand. Default from config.

    Returns
    -------
    List of IslandResult, one per island, sorted by population descending.
    """
    # Load demand defaults from config if not provided
    if demand_kwh_per_capita is None or load_factor is None:
        try:
            from .config import get_config as _gc
        except ImportError:
            from model.config import get_config as _gc
        _cfg = _gc()
        if demand_kwh_per_capita is None:
            # ~1,100 GWh / 337,000 pop = ~3,260 kWh/capita
            demand_kwh_per_capita = (
                _cfg.demand.base_demand_gwh * 1e6 / _cfg.current_system.population_2026
            )
        if load_factor is None:
            load_factor = _cfg.demand.load_factor
    # Default params — always load from config, never use bare dataclass defaults
    if tech is None or solar is None or diesel is None or grid is None:
        _tech, _solar, _diesel, _grid = load_params_from_config()
        if tech is None:
            tech = _tech
        if solar is None:
            solar = _solar
        if diesel is None:
            diesel = _diesel
        if grid is None:
            grid = _grid

    # Default CSV path
    if csv_path is None:
        csv_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "islands_master.csv"
        )

    # Load M1 intensity multipliers from config
    try:
        from .config import get_config as _gc2
    except ImportError:
        from model.config import get_config as _gc2
    _cfg2 = _gc2()
    intensity_urban = _cfg2.demand.intensity_urban
    intensity_secondary = _cfg2.demand.intensity_secondary
    intensity_rural = _cfg2.demand.intensity_rural
    urban_threshold = _cfg2.demand.urban_pop_threshold
    secondary_threshold = _cfg2.demand.secondary_pop_threshold
    # H16: Malé rooftop solar cap (MWp) — ZNES Flensburg study
    male_rooftop_solar_kw = _cfg2.current_system.male_rooftop_solar_mwp * 1000  # MWp → kW

    df = pd.read_csv(csv_path)
    results = []

    for idx, row in df.iterrows():
        island = row["Island_Name"]
        atoll = row["Atoll"]
        pop = int(row["Pop"])
        lat = row["Y_deg"]
        lon = row["X_deg"]
        ghi = row.get("GHI_GSA", tech.default_ghi)  # kWh/m²/day
        temp = row.get("TEMP_GSA", tech.default_temp)  # °C
        area_km2 = row.get("Area_km2", 0.0)  # km²

        if pop <= 0:
            continue

        # M1: Island demand with urbanisation intensity multiplier
        if pop > urban_threshold:
            intensity = intensity_urban
        elif pop > secondary_threshold:
            intensity = intensity_secondary
        else:
            intensity = intensity_rural
        demand_kwh = pop * demand_kwh_per_capita * intensity
        avg_kw = demand_kwh / HOURS_PER_YEAR
        peak_kw = avg_kw / load_factor

        # ── Solar land constraint check ──
        # Compute solar capacity needed for 100% supply and compare to island area
        t_cell_check = temp + solar.noct_coeff * (ghi / 24.0)
        derating_check = 1.0 - solar.temp_derating_coeff * max(0, t_cell_check - 25.0)
        effective_cf_check = solar.solar_capacity_factor * derating_check
        gross_demand_check = demand_kwh / (1 - tech.distribution_loss)
        solar_kw_needed = gross_demand_check / (effective_cf_check * HOURS_PER_YEAR)
        solar_area_m2 = solar_kw_needed * solar.solar_area_per_kw
        island_area_m2 = area_km2 * 1e6  # km² → m²
        solar_land_frac = solar_area_m2 / island_area_m2 if island_area_m2 > 0 else 999.0
        solar_constrained = solar_land_frac > solar.max_solar_land_fraction

        # H16: Malé rooftop solar cap — dense urban, no ground-mount space
        if island == "Maale" and atoll == "Male" and solar_kw_needed > male_rooftop_solar_kw:
            solar_constrained = True

        # ── 1. Solar + Battery LCOE ──
        if solar_constrained:
            # Solar cannot fully supply this island — set standalone solar LCOE to inf
            lcoe_sb = 999.0
            invest_sb = 0.0
        else:
            lcoe_sb, invest_sb = lcoe_solar_battery(
                peak_kw=peak_kw,
                demand_kwh=demand_kwh,
                ghi_kwh_m2_day=ghi,
                temp_c=temp,
                params=solar,
                tech=tech,
            )

        # ── 2. Diesel LCOE ──
        lcoe_dsl, invest_dsl = lcoe_diesel(
            peak_kw=peak_kw,
            demand_kwh=demand_kwh,
            params=diesel,
            tech=tech,
        )

        # ── 3. Solar-Diesel Hybrid LCOE ──
        # If solar-constrained, cap the solar share to what land allows
        if solar_constrained and solar_land_frac > 0:
            max_solar_share = min(diesel.hybrid_default_solar_share, solar.max_solar_land_fraction / solar_land_frac)
        else:
            max_solar_share = diesel.hybrid_default_solar_share

        lcoe_hyb, invest_hyb = lcoe_solar_diesel_hybrid(
            peak_kw=peak_kw,
            demand_kwh=demand_kwh,
            ghi_kwh_m2_day=ghi,
            temp_c=temp,
            solar_params=solar,
            diesel_params=diesel,
            tech=tech,
            solar_share=max_solar_share,
        )

        # ── 4. Grid Extension LCOE ──
        # Find nearest larger island
        min_dist = float("inf")
        nearest = "(none)"
        for j, other in df.iterrows():
            if other["Pop"] > pop:
                d = haversine_km(lat, lon, other["Y_deg"], other["X_deg"])
                d *= tech.routing_premium
                if d < min_dist:
                    min_dist = d
                    nearest = other["Island_Name"]

        # Malé is the hub — grid ext LCOE = inf (it IS the hub)
        if nearest == "(none)":
            lcoe_ge = 999.0
            invest_ge = 0.0
            min_dist = 0.0
            cable_cost = 0.0
        else:
            lcoe_ge, invest_ge = lcoe_grid_extension(
                peak_kw=peak_kw,
                demand_kwh=demand_kwh,
                distance_km=min_dist,
                params=grid,
                tech=tech,
            )
            cable_cost = min_dist * grid.cable_capex_per_km

        # ── Pick best technology ──
        options = {
            "solar_battery": (lcoe_sb, invest_sb),
            "diesel": (lcoe_dsl, invest_dsl),
            "hybrid": (lcoe_hyb, invest_hyb),
            "grid_ext": (lcoe_ge, invest_ge),
        }

        best_tech = min(options, key=lambda k: options[k][0])
        best_lcoe = options[best_tech][0]
        best_invest = options[best_tech][1]

        # Cable/standalone ratio for tranche assignment
        standalone_cost = min(invest_sb, invest_dsl, invest_hyb)
        cable_ratio = cable_cost / standalone_cost if standalone_cost > 0 else 999.0

        # Tranche
        tranche = assign_tranche(
            island=island,
            atoll=atoll,
            best_tech=best_tech,
            distance_km=min_dist,
            cable_standalone_ratio=cable_ratio,
            nearest_hub=nearest,
        )

        results.append(IslandResult(
            island=island,
            atoll=atoll,
            population=pop,
            demand_kwh=demand_kwh,
            peak_kw=peak_kw,
            lcoe_solar_battery=round(lcoe_sb, 4),
            lcoe_diesel=round(lcoe_dsl, 4),
            lcoe_hybrid=round(lcoe_hyb, 4),
            lcoe_grid_ext=round(lcoe_ge, 4),
            invest_solar_battery=round(invest_sb, 0),
            invest_diesel=round(invest_dsl, 0),
            invest_hybrid=round(invest_hyb, 0),
            invest_grid_ext=round(invest_ge, 0),
            best_tech=best_tech,
            best_lcoe=round(best_lcoe, 4),
            best_invest=round(best_invest, 0),
            nearest_hub=nearest,
            distance_km=round(min_dist, 1),
            cable_cost_usd=round(cable_cost, 0),
            tranche=tranche,
            ghi=ghi,
            temp=temp,
            area_km2=area_km2,
            solar_land_fraction=round(solar_land_frac, 4),
            solar_constrained=solar_constrained,
        ))

    # Sort by population descending
    results.sort(key=lambda r: r.population, reverse=True)
    return results


def print_results(results: List[IslandResult]):
    """Pretty-print the least-cost assignment results."""
    print("=" * 150)
    print("  LEAST-COST ELECTRIFICATION ASSIGNMENT -- MALDIVES INHABITED ISLANDS")
    print("  Technologies: Solar+Battery | Diesel | Solar-Diesel Hybrid | Grid Extension")
    print("  All LCOEs in USD/kWh, investments in USD (discounted)")
    print("=" * 150)

    header = (
        f"{'Island':>18s} {'Atoll':>12s} {'Pop':>8s} "
        f"{'SolBat':>8s} {'Diesel':>8s} {'Hybrid':>8s} {'GridEx':>8s} "
        f"{'BEST':>10s} {'LCOE':>7s} {'SolLand':>8s} {'Dist':>6s} {'Nearest':>14s} {'Tranche':>8s}"
    )
    print(header)
    print("-" * 150)

    for r in results:
        ge_str = f"{r.lcoe_grid_ext:.4f}" if r.lcoe_grid_ext < 900 else "   n/a"
        sol_str = f"{r.solar_land_fraction:.0%}" if r.solar_land_fraction < 900 else " n/a"
        if r.solar_constrained:
            sol_str += "!"
        print(
            f"{r.island:>18s} {r.atoll:>12s} {r.population:>8,d} "
            f"{r.lcoe_solar_battery:>8.4f} {r.lcoe_diesel:>8.4f} {r.lcoe_hybrid:>8.4f} {ge_str:>8s} "
            f"{r.best_tech:>10s} {r.best_lcoe:>7.4f} {sol_str:>8s} {r.distance_km:>6.1f} {r.nearest_hub:>14s} {r.tranche:>8s}"
        )

    # Summary
    print()
    print("=" * 150)
    print("  SUMMARY BY TECHNOLOGY")
    print("=" * 150)

    tech_groups = {}
    for r in results:
        tech_groups.setdefault(r.best_tech, []).append(r)

    total_pop = sum(r.population for r in results)
    for tech_name in ["solar_battery", "hybrid", "diesel", "grid_ext"]:
        islands = tech_groups.get(tech_name, [])
        pop = sum(r.population for r in islands)
        avg_lcoe = (sum(r.best_lcoe * r.population for r in islands) / pop
                    if pop > 0 else 0)
        total_invest = sum(r.best_invest for r in islands)
        print(f"  {tech_name:>15s}: {len(islands):>3d} islands, "
              f"pop {pop:>8,d} ({pop / total_pop * 100:>5.1f}%), "
              f"avg LCOE ${avg_lcoe:.4f}/kWh, "
              f"total invest ${total_invest / 1e6:>8.1f}M")

    print()
    print("  SUMMARY BY TRANCHE")
    print("=" * 150)

    tranche_groups = {}
    for r in results:
        tranche_groups.setdefault(r.tranche, []).append(r)

    for tranche in ["T0", "T1", "T2", "T3", "T4"]:
        islands = tranche_groups.get(tranche, [])
        pop = sum(r.population for r in islands)
        total_invest = sum(r.best_invest for r in islands)
        names = ", ".join(r.island for r in sorted(islands, key=lambda x: -x.population)[:5])
        if len(islands) > 5:
            names += f" +{len(islands) - 5} more"
        print(f"  {tranche}: {len(islands):>3d} islands, "
              f"pop {pop:>8,d} ({pop / total_pop * 100:>5.1f}%), "
              f"invest ${total_invest / 1e6:>8.1f}M -- {names}")

    # Solar-constrained islands
    constrained = [r for r in results if r.solar_constrained]
    if constrained:
        print()
        print("  SOLAR LAND-CONSTRAINED ISLANDS (solar_land_fraction > max)")
        print("=" * 150)
        for r in sorted(constrained, key=lambda x: -x.solar_land_fraction):
            status = "IMPOSSIBLE" if r.solar_land_fraction > 0.30 else "TIGHT"
            print(f"  {r.island:>18s} ({r.atoll:>12s}): "
                  f"pop {r.population:>8,d}, area {r.area_km2:.3f} km², "
                  f"solar needs {r.solar_land_fraction:.1%} of island [{status}] "
                  f"→ assigned {r.best_tech} (LCOE ${r.best_lcoe:.4f}/kWh)")


def results_to_dataframe(results: List[IslandResult]) -> pd.DataFrame:
    """Convert results to a DataFrame for further analysis."""
    rows = []
    for r in results:
        rows.append({
            "Island": r.island,
            "Atoll": r.atoll,
            "Population": r.population,
            "Demand_kWh": r.demand_kwh,
            "Peak_kW": r.peak_kw,
            "LCOE_SolarBat": r.lcoe_solar_battery,
            "LCOE_Diesel": r.lcoe_diesel,
            "LCOE_Hybrid": r.lcoe_hybrid,
            "LCOE_GridExt": r.lcoe_grid_ext if r.lcoe_grid_ext < 900 else None,
            "Invest_SolarBat": r.invest_solar_battery,
            "Invest_Diesel": r.invest_diesel,
            "Invest_Hybrid": r.invest_hybrid,
            "Invest_GridExt": r.invest_grid_ext if r.lcoe_grid_ext < 900 else None,
            "Best_Tech": r.best_tech,
            "Best_LCOE": r.best_lcoe,
            "Best_Invest": r.best_invest,
            "Nearest_Hub": r.nearest_hub,
            "Distance_km": r.distance_km,
            "Cable_Cost_USD": r.cable_cost_usd,
            "Tranche": r.tranche,
            "GHI": r.ghi,
            "Temp": r.temp,
            "Area_km2": r.area_km2,
            "Solar_Land_Fraction": r.solar_land_fraction,
            "Solar_Constrained": r.solar_constrained,
        })
    return pd.DataFrame(rows)


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "islands_master.csv"
    )

    # Load params from config system (parameters.csv)
    tech_p, solar_p, diesel_p, grid_p = load_params_from_config()

    # Get hub prices from config
    try:
        from .config import get_config as _gc_cli
    except ImportError:
        from model.config import get_config as _gc_cli
    _cfg_cli = _gc_cli()
    india_hub_price = _cfg_cli.ppa.import_price_2030
    # R4: weighted diesel efficiency (Malé 3.3, outer 2.38 kWh/L)
    diesel_lcoe = _cfg_cli.fuel.price_2026 / _cfg_cli.weighted_diesel_efficiency(_cfg_cli.base_year) + _cfg_cli.technology.diesel_gen_opex_kwh

    # Run with India cable hub price
    print("\n" + "=" * 80)
    print(f"  SCENARIO S1: India cable hub -- electricity at ${india_hub_price:.3f}/kWh")
    print("=" * 80)
    grid_india = GridExtParams(
        cable_capex_per_km=grid_p.cable_capex_per_km,
        cable_opex_pct=grid_p.cable_opex_pct,
        cable_lifetime=grid_p.cable_lifetime,
        hub_electricity_price=india_hub_price,
    )
    results_s1 = run_least_cost(csv_path=csv_path, tech=tech_p, solar=solar_p, diesel=diesel_p, grid=grid_india)
    print_results(results_s1)

    # Run with local solar hub price (= solar LCOE from model)
    # Compute approximate solar LCOE from config
    solar_lcoe = solar_p.solar_capex_per_kw / (solar_p.solar_capacity_factor * 8760 * solar_p.solar_lifetime) * 1000
    print("\n" + "=" * 80)
    print(f"  SCENARIO S2: No India cable -- hub uses local solar at ~${solar_lcoe:.3f}/kWh")
    print("=" * 80)
    grid_local = GridExtParams(
        cable_capex_per_km=grid_p.cable_capex_per_km,
        cable_opex_pct=grid_p.cable_opex_pct,
        cable_lifetime=grid_p.cable_lifetime,
        hub_electricity_price=solar_lcoe,
    )
    results_s2 = run_least_cost(csv_path=csv_path, tech=tech_p, solar=solar_p, diesel=diesel_p, grid=grid_local)
    print_results(results_s2)

    # Run with diesel hub price (BAU)
    print("\n" + "=" * 80)
    print(f"  SCENARIO S0: BAU diesel -- hub uses diesel at ~${diesel_lcoe:.3f}/kWh")
    print("=" * 80)
    grid_diesel = GridExtParams(
        cable_capex_per_km=grid_p.cable_capex_per_km,
        cable_opex_pct=grid_p.cable_opex_pct,
        cable_lifetime=grid_p.cable_lifetime,
        hub_electricity_price=diesel_lcoe,
    )
    results_s0 = run_least_cost(csv_path=csv_path, tech=tech_p, solar=solar_p, diesel=diesel_p, grid=grid_diesel)
    print_results(results_s0)
