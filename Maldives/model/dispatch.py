"""
Hourly Dispatch Module (M4)
============================

PV-diesel-battery hourly dispatch simulation for a single island.
Based on GEP-OnSSET onsset.py L175-365 dispatch algorithm.

Inputs:
  - GHI hourly (W/m²) and Temperature hourly (°C) from supplementary CSVs
  - Island demand (kWh/yr), PV capacity (kW), battery capacity (kWh), diesel capacity (kW)
  - Dispatch parameters from config: DoD, min diesel load, fuel curve, etc.

Outputs:
  - Curtailment %, battery utilisation, diesel hours, unmet demand hours
  - Effective capacity factor (accounting for curtailment)
  - Fuel consumption (litres/yr)
  - SOC profile summary

Adapted from OnSSET tier-5 load curve and break_hour=17 dispatch strategy.
All dispatch parameters flow from parameters.csv → config.py → get_config().
"""

import os
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, Tuple

try:
    from .config import get_config
except ImportError:
    from model.config import get_config


# ── Tier-5 load curve (OnSSET onsset.py L207-213) ─────────────────────────────
# Normalised hourly share of daily demand (sum = 1.0)
TIER5_LOAD_CURVE = np.array([
    0.021008403, 0.021008403, 0.021008403, 0.021008403,  # 00-03
    0.027310924, 0.037815126, 0.042016807, 0.042016807,  # 04-07
    0.042016807, 0.042016807, 0.042016807, 0.042016807,  # 08-11
    0.042016807, 0.042016807, 0.042016807, 0.042016807,  # 12-15
    0.046218487, 0.050420168, 0.067226891, 0.084033613,  # 16-19
    0.073529412, 0.052521008, 0.033613445, 0.023109244,  # 20-23
])


@dataclass
class DispatchResult:
    """Results from a single year's hourly dispatch simulation."""

    # Capacities (inputs)
    pv_capacity_kw: float
    battery_capacity_kwh: float
    diesel_capacity_kw: float
    annual_demand_kwh: float

    # Generation (kWh/yr)
    pv_generation_kwh: float = 0.0
    diesel_generation_kwh: float = 0.0
    battery_discharge_kwh: float = 0.0
    curtailment_kwh: float = 0.0
    unmet_demand_kwh: float = 0.0

    # Fuel
    fuel_litres: float = 0.0

    # Metrics
    diesel_hours: int = 0           # Hours diesel ran
    unmet_hours: int = 0            # Hours with unmet demand
    curtailment_hours: int = 0      # Hours with curtailed PV

    # Battery
    avg_soc: float = 0.0
    max_dod: float = 0.0
    battery_cycles: float = 0.0     # Equivalent full cycles

    @property
    def effective_pv_cf(self) -> float:
        """Effective PV capacity factor after curtailment."""
        max_gen = self.pv_capacity_kw * 8760
        return self.pv_generation_kwh / max_gen if max_gen > 0 else 0.0

    @property
    def curtailment_pct(self) -> float:
        """Fraction of potential PV generation curtailed."""
        total_pv = self.pv_generation_kwh + self.curtailment_kwh
        return self.curtailment_kwh / total_pv if total_pv > 0 else 0.0

    @property
    def diesel_share(self) -> float:
        total = self.pv_generation_kwh + self.diesel_generation_kwh
        return self.diesel_generation_kwh / total if total > 0 else 0.0

    @property
    def lpsp(self) -> float:
        """Loss of Power Supply Probability."""
        return self.unmet_demand_kwh / self.annual_demand_kwh if self.annual_demand_kwh > 0 else 0.0

    @property
    def battery_utilisation(self) -> float:
        """Battery discharge as fraction of throughput capacity."""
        max_discharge = self.battery_capacity_kwh * 365  # Rough daily cycle potential
        return self.battery_discharge_kwh / max_discharge if max_discharge > 0 else 0.0

    def summary(self) -> dict:
        return {
            "pv_kw": self.pv_capacity_kw,
            "battery_kwh": self.battery_capacity_kwh,
            "diesel_kw": self.diesel_capacity_kw,
            "demand_kwh": self.annual_demand_kwh,
            "pv_gen_kwh": round(self.pv_generation_kwh, 1),
            "diesel_gen_kwh": round(self.diesel_generation_kwh, 1),
            "curtailment_kwh": round(self.curtailment_kwh, 1),
            "unmet_kwh": round(self.unmet_demand_kwh, 1),
            "fuel_litres": round(self.fuel_litres, 1),
            "effective_cf": round(self.effective_pv_cf, 4),
            "curtailment_pct": round(self.curtailment_pct, 4),
            "diesel_share": round(self.diesel_share, 4),
            "lpsp": round(self.lpsp, 4),
            "diesel_hours": self.diesel_hours,
            "unmet_hours": self.unmet_hours,
            "battery_cycles": round(self.battery_cycles, 1),
        }


def load_hourly_data(
    ghi_path: Optional[str] = None,
    temp_path: Optional[str] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load hourly GHI (W/m²) and temperature (°C) from supplementary CSVs.

    Returns:
        (ghi_array, temp_array) — each shape (8760,)
    """
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "supplementary")

    if ghi_path is None:
        ghi_path = os.path.join(data_dir, "GHI_hourly.csv")
    if temp_path is None:
        temp_path = os.path.join(data_dir, "Temperature_hourly.csv")

    ghi = pd.read_csv(ghi_path, usecols=[4], sep=";", skiprows=22, header=None).values.flatten()
    temp = pd.read_csv(temp_path, usecols=[4], sep=";", skiprows=22, header=None).values.flatten()

    # Validate
    if len(ghi) < 8760:
        raise ValueError(f"GHI data has {len(ghi)} rows, expected ≥8760")
    if len(temp) < 8760:
        raise ValueError(f"Temperature data has {len(temp)} rows, expected ≥8760")

    return ghi[:8760].astype(float), temp[:8760].astype(float)


def build_load_profile(
    annual_demand_kwh: float,
    load_curve: np.ndarray = None,
) -> np.ndarray:
    """
    Build 8760-hour load profile from daily load curve.

    Args:
        annual_demand_kwh: Total annual demand in kWh
        load_curve: 24-hour normalised load curve (sum=1). Defaults to Tier-5.

    Returns:
        Array of shape (8760,) with hourly demand in kWh.
    """
    if load_curve is None:
        load_curve = TIER5_LOAD_CURVE

    daily_demand = annual_demand_kwh / 365.0
    hourly_demand = load_curve * daily_demand  # 24 values

    # Tile to 8760 hours (365 identical days)
    hour_of_day = np.tile(np.arange(24), 365)
    profile = np.array([hourly_demand[h] for h in hour_of_day])

    return profile[:8760]


def run_dispatch(
    pv_capacity_kw: float,
    battery_capacity_kwh: float,
    diesel_capacity_kw: float,
    annual_demand_kwh: float,
    ghi: np.ndarray = None,
    temp: np.ndarray = None,
    load_curve: np.ndarray = None,
    config=None,
) -> DispatchResult:
    """
    Run hourly PV-diesel-battery dispatch for one year.

    Algorithm follows GEP-OnSSET onsset.py L245-289 dispatch strategy:
    - PV generation first (with temperature derating)
    - Excess PV → charge battery (capped by efficiency and SOC)
    - Deficit: battery discharge during peak hours, diesel otherwise
    - Diesel generator subject to minimum load fraction
    - Self-discharge of battery: 0.02%/hour (OnSSET L251)
    - break_hour=17: diesel strategy changes at hour 17
    - Fuel curve: two-part (idle + proportional)

    Args:
        pv_capacity_kw: PV capacity in kW
        battery_capacity_kwh: Battery storage capacity in kWh
        diesel_capacity_kw: Diesel generator capacity in kW
        annual_demand_kwh: Annual demand in kWh
        ghi: Hourly GHI array (W/m²), shape (8760,). If None, loads from file.
        temp: Hourly temperature array (°C), shape (8760,). If None, loads from file.
        load_curve: 24-hour normalised load curve. Defaults to Tier-5.
        config: Config object. If None, uses get_config().

    Returns:
        DispatchResult with all dispatch outcomes.
    """
    if config is None:
        config = get_config()

    # Load climate data if not provided
    if ghi is None or temp is None:
        ghi_loaded, temp_loaded = load_hourly_data()
        if ghi is None:
            ghi = ghi_loaded
        if temp is None:
            temp = temp_loaded

    # Build load profile
    load = build_load_profile(annual_demand_kwh, load_curve)

    # ── Parameters from config ──
    dispatch = config.dispatch
    tech = config.technology
    k_t = tech.pv_temp_derating_coeff       # 0.005 /°C
    noct_coeff = tech.pv_noct_coeff          # 25.6 °C per kW/m²
    dod_max = dispatch.battery_dod_max       # 0.80
    min_diesel_load = dispatch.diesel_min_load_fraction  # 0.40
    idle_coeff = dispatch.fuel_curve_idle_coeff  # 0.08145
    prop_coeff = dispatch.fuel_curve_proportional_coeff  # 0.246
    n_chg = dispatch.battery_charge_efficiency  # 0.92
    n_dis = dispatch.battery_discharge_efficiency  # 0.92
    self_discharge = dispatch.battery_self_discharge_rate  # 0.0002/hr
    break_hour = dispatch.break_hour  # 17
    pv_derating = dispatch.pv_system_derating_factor  # 0.90
    cycle_coeff_a = dispatch.battery_cycle_life_coeff_a  # 531.52764
    cycle_coeff_b = dispatch.battery_cycle_life_coeff_b  # -1.12297

    # Hour of day for each timestep
    hour_of_day = np.tile(np.arange(24), 365)[:8760]

    # ── State variables ──
    soc = dispatch.battery_initial_soc  # LW-02: from config (default 0.5)
    total_pv_gen = 0.0
    total_diesel_gen = 0.0
    total_curtailed = 0.0
    total_unmet = 0.0
    total_fuel = 0.0
    total_battery_discharge = 0.0
    diesel_hours = 0
    unmet_hours = 0
    curtailment_hours = 0
    soc_sum = 0.0
    max_dod_val = 0.0

    # Daily DOD tracking for battery wear
    daily_battery_use = np.zeros(24)
    daily_dod = np.zeros(24)
    total_battery_wear = 0.0

    for i in range(8760):
        h = hour_of_day[i]

        # Battery self-discharge
        daily_battery_use[h] = self_discharge * soc
        soc *= (1 - self_discharge)

        # ── PV generation with temperature derating ──
        # T_cell = T_amb + NOCT_coeff * GHI_kW/m² (OnSSET L252)
        ghi_kw = ghi[i] / 1000.0
        t_cell = temp[i] + noct_coeff * ghi_kw
        # PV output: capacity * derating * GHI/1000 * temp derating
        pv_gen = pv_capacity_kw * pv_derating * ghi_kw * max(0, 1 - k_t * (t_cell - 25.0))
        total_pv_gen += pv_gen

        # ── Net load after PV ──
        net_load = load[i] - pv_gen

        if net_load <= 0:
            # PV exceeds load → charge battery
            excess = -net_load
            if battery_capacity_kwh > 0:
                charge = min(excess, (1.0 - soc) * battery_capacity_kwh / n_chg)
                soc += n_chg * charge / battery_capacity_kwh
                curtailed = excess - charge
            else:
                curtailed = excess
            if curtailed > 0:
                total_curtailed += curtailed
                curtailment_hours += 1
            net_load = 0.0
        else:
            # PV insufficient — need diesel and/or battery
            diesel_gen = 0.0

            # Maximum diesel that could be useful (to supply load + charge battery)
            if battery_capacity_kwh > 0:
                max_diesel = min(diesel_capacity_kw,
                                 net_load + (1 - soc) * battery_capacity_kwh / n_chg)
            else:
                max_diesel = min(diesel_capacity_kw, net_load)

            # ── OnSSET dispatch strategy (L259-268) ──
            # Day hours (5-17): use battery first, diesel if battery insufficient
            # Evening hours (18-23): use diesel to supply load AND charge battery
            # Night hours (0-4): diesel if battery insufficient
            if break_hour + 1 > h > 4:
                # Daytime: run diesel only if battery can't cover
                if net_load > soc * battery_capacity_kwh * n_dis:
                    diesel_gen = min(diesel_capacity_kw,
                                     max(min_diesel_load * diesel_capacity_kw, net_load))
            elif 23 > h > break_hour:
                # Evening peak: run diesel at maximum useful level
                if max_diesel > min_diesel_load * diesel_capacity_kw:
                    diesel_gen = max_diesel
            elif n_dis * soc * battery_capacity_kwh < net_load:
                # Night/other: run diesel if battery insufficient
                diesel_gen = max(min_diesel_load * diesel_capacity_kw, max_diesel)

            # Enforce minimum diesel load
            if 0 < diesel_gen < min_diesel_load * diesel_capacity_kw:
                diesel_gen = min_diesel_load * diesel_capacity_kw

            if diesel_gen > 0:
                # Fuel consumption: two-part curve (OnSSET L266)
                total_fuel += diesel_capacity_kw * idle_coeff + diesel_gen * prop_coeff
                total_diesel_gen += diesel_gen
                diesel_hours += 1

            # Remaining load after diesel
            remaining = net_load - diesel_gen

            if remaining > 0:
                # Discharge battery
                if battery_capacity_kwh > 0:
                    # MR-01 fix: enforce DoD limit as minimum SOC floor
                    min_soc = 1.0 - dod_max
                    available_soc = max(0, soc - min_soc)
                    discharge = min(remaining, available_soc * battery_capacity_kwh * n_dis)
                    soc -= discharge / (n_dis * battery_capacity_kwh) if battery_capacity_kwh > 0 else 0
                    total_battery_discharge += discharge
                    daily_battery_use[h] += discharge / (n_dis * battery_capacity_kwh) if battery_capacity_kwh > 0 else 0
                    remaining -= discharge

                    if soc < min_soc:
                        total_unmet += abs(soc - min_soc) * n_dis * battery_capacity_kwh
                        daily_battery_use[h] += (soc - min_soc)  # Negative adjustment
                        soc = min_soc
                        unmet_hours += 1

                if remaining > 1e-6:
                    # CR-06 fix: count unmet demand regardless of battery presence
                    total_unmet += remaining
                    unmet_hours += 1
            else:
                # Diesel gen exceeded load → charge battery with excess
                excess_diesel = -remaining
                if battery_capacity_kwh > 0 and excess_diesel > 0:
                    soc += n_chg * excess_diesel / battery_capacity_kwh

        # Clamp SOC
        soc = min(soc, 1.0)
        soc = max(soc, 0.0)
        soc_sum += soc

        # Track DOD
        daily_dod[h] = 1.0 - soc
        max_dod_val = max(max_dod_val, 1.0 - soc)

        # End of day: calculate battery wear (OnSSET L283-284)
        if h == 23 and max(daily_dod) > 0:
            total_battery_wear += sum(daily_battery_use) / (
                cycle_coeff_a * max(0.1, max(daily_dod) * dod_max) ** cycle_coeff_b
            )
            daily_battery_use[:] = 0
            daily_dod[:] = 0

    # Battery equivalent cycles
    if battery_capacity_kwh > 0:
        battery_cycles = total_battery_discharge / battery_capacity_kwh
    else:
        battery_cycles = 0.0

    return DispatchResult(
        pv_capacity_kw=pv_capacity_kw,
        battery_capacity_kwh=battery_capacity_kwh,
        diesel_capacity_kw=diesel_capacity_kw,
        annual_demand_kwh=annual_demand_kwh,
        pv_generation_kwh=total_pv_gen,
        diesel_generation_kwh=total_diesel_gen,
        battery_discharge_kwh=total_battery_discharge,
        curtailment_kwh=total_curtailed,
        unmet_demand_kwh=total_unmet,
        fuel_litres=total_fuel,
        diesel_hours=diesel_hours,
        unmet_hours=unmet_hours,
        curtailment_hours=curtailment_hours,
        avg_soc=soc_sum / 8760,
        max_dod=max_dod_val,
        battery_cycles=battery_cycles,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE TESTING
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  HOURLY DISPATCH VALIDATION (M4)")
    print("=" * 70)
    print()

    # Load data
    print("Loading hourly GHI and temperature data...")
    ghi, temp = load_hourly_data()
    print(f"  GHI: {len(ghi)} hours, range {ghi.min():.0f}-{ghi.max():.0f} W/m²")
    print(f"  Temp: {len(temp)} hours, range {temp.min():.1f}-{temp.max():.1f} °C")
    print()

    cfg = get_config()

    # Test cases: typical island configurations
    test_cases = [
        # (name, pv_kw, battery_kwh, diesel_kw, demand_kwh)
        ("Small island (100 hh)",      50,   100,    30,    200_000),
        ("Medium island (500 hh)",    300,   600,   150,  1_000_000),
        ("Large island (2000 hh)",  1_200, 2_400,   600,  4_000_000),
        ("Solar-only (no diesel)",    500, 1_000,     0,    500_000),
        ("Diesel-only (no solar)",      0,     0,   200,    500_000),
        ("Malé-scale (constrained)", 5_000, 10_000, 50_000, 200_000_000),
    ]

    print(f"{'Case':<26} {'PV CF':>7} {'Curt%':>6} {'Diesel%':>8} {'LPSP':>6} {'Fuel kL':>8} {'DslHrs':>7} {'BatCyc':>7}")
    print("-" * 78)

    for name, pv, bat, dsl, demand in test_cases:
        result = run_dispatch(
            pv_capacity_kw=pv,
            battery_capacity_kwh=bat,
            diesel_capacity_kw=dsl,
            annual_demand_kwh=demand,
            ghi=ghi, temp=temp,
            config=cfg,
        )
        print(
            f"{name:<26} "
            f"{result.effective_pv_cf:>7.3f} "
            f"{result.curtailment_pct*100:>5.1f}% "
            f"{result.diesel_share*100:>7.1f}% "
            f"{result.lpsp:>6.4f} "
            f"{result.fuel_litres/1000:>8.1f} "
            f"{result.diesel_hours:>7d} "
            f"{result.battery_cycles:>7.1f}"
        )

    print()
    print("=" * 70)
    print("  DETAILED: Medium island (500 hh)")
    print("=" * 70)
    result = run_dispatch(
        pv_capacity_kw=300,
        battery_capacity_kwh=600,
        diesel_capacity_kw=150,
        annual_demand_kwh=1_000_000,
        ghi=ghi, temp=temp,
        config=cfg,
    )
    for k, v in result.summary().items():
        print(f"  {k:<20s}: {v}")

    print()
    print("✓ Dispatch module validation complete.")
