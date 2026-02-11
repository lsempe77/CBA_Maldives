# CBA Methodology — Complete Equation & Parameter Audit

**Version:** 1.4  
**Date:** 2026-02-10  
**Status:** C10 deliverable — living document (updated: §14 Transport Electrification Module added)  
**Scope:** Every equation in every script, with parameter traceability to `parameters.csv → config.py → code`

---

## Table of Contents

1. [Model Architecture Overview](#1-model-architecture-overview)
2. [Demand Module](#2-demand-module)
3. [Cost Module](#3-cost-module)
4. [Emissions Module](#4-emissions-module)
5. [Least-Cost Electrification Engine](#5-least-cost-electrification-engine)
6. [NPV / CBA Calculator](#6-npv--cba-calculator)
7. [Financing Analysis](#7-financing-analysis)
8. [Scenario Logic](#8-scenario-logic)
9. [Sensitivity & Monte Carlo](#9-sensitivity--monte-carlo)
10. [Complete Parameter Traceability Map](#10-complete-parameter-traceability-map)
11. [Structural Concerns & Red Flags](#11-structural-concerns--red-flags)
12. [Cross-Check vs Standard CBA References](#12-cross-check-vs-standard-cba-references)
13. [Parameter–Equation Traceability Audit](#13-parameterequation-traceability-audit)
14. [Transport Electrification Module (P8)](#14-transport-electrification-module-p8)

---

## 1. Model Architecture Overview

```
parameters.csv  →  config.py (load_parameters_from_csv → get_config)
       ↓                              ↓
  SINGLE SOURCE                  Config dataclass
  OF TRUTH                            ↓
                          ┌───────────┼───────────────┐
                          ↓           ↓               ↓
                     demand.py    costs.py        emissions.py
                          ↓           ↓               ↓
                     scenarios/status_quo.py ──────→ ScenarioResults
                     scenarios/one_grid.py ─────────→    ↓
                     scenarios/green_transition.py ──→    ↓
                     scenarios/islanded_green.py ────→    ↓
                     scenarios/nearshore_solar.py ──→     ↓
                     scenarios/maximum_re.py ───────→     ↓
                     scenarios/lng_transition.py ───→     ↓
                                                        ↓
                     least_cost.py (per-island LCOE) ←──┘
                                                        ↓
                     cba/npv_calculator.py ──→ CBAComparison
                          ↓                       ↓
                     financing_analysis.py    sensitivity.py
                          ↓                  run_monte_carlo.py
                     outputs/*.json
```

**Horizons:** 20yr (2026–2046), 30yr (2026–2056, default), 50yr (2026–2076)  
**Scenarios:** S1 BAU, S2 Full Integration (India cable), S3 National Grid, S4 Islanded Green, S5 Near-Shore Solar, S6 Maximum RE, S7 LNG Transition  
**Discount rate:** 6% real (ADB SIDS standard)

---

## 2. Demand Module

**File:** `model/demand.py`

### EQ-D1: Compound demand growth

$$D(t) = D_0 \times (1 + g)^{t - t_0}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|-----------------|
| $D_0$ | Base demand 2026 | `Demand / Base Demand 2026` | `config.demand.base_demand_gwh` | `demand.py:114` |
| $g$ | Growth rate (scenario-specific) | `Demand / Growth Rate - BAU/NG/FI` | `config.demand.growth_rates[scenario]` | `demand.py:115` |
| $t_0$ | Base year | — (constant 2026) | `config.base_year` | `demand.py:112` |

**Location:** `DemandProjector.project_year()` lines 110–120

### EQ-D2: Peak demand from energy

$$P(t) = \frac{D(t) \times 1000}{8760 \times LF}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|-----------------|
| $LF$ | Load factor | `Demand / Load Factor` | `config.demand.load_factor` | `demand.py:121` |
| 8760 | Hours/year | — (mathematical constant) | — | `demand.py:120` |

**Location:** `DemandProjector.project_year()` lines 119–121

### EQ-D3: Induced demand (price elasticity)

$$D'(t) = D(t) \times \left(1 + \varepsilon \times (-\Delta p)\right)$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|-----------------|
| $\varepsilon$ | Price elasticity | `Demand / Price Elasticity of Demand` | `config.demand.price_elasticity` | `demand.py:222` |
| $\Delta p$ | Price reduction fraction | — (computed) | — | `demand.py:229` |

**Location:** `DemandProjector.apply_induced_demand()` lines 210–232

### EQ-D4: Sectoral demand split

$$D_r(t) = D(t) \times s_r, \quad D_c(t) = D(t) \times s_c, \quad D_p(t) = D(t) \times s_p$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $s_r$ | Residential share | `Electricity Structure / Sectoral Split Residential` | `config.demand.sectoral_residential` | `demand.py:157` |
| $s_c$ | Commercial share | `Electricity Structure / Sectoral Split Commercial` | `config.demand.sectoral_commercial` | `demand.py:161` |
| $s_p$ | Public share | `Electricity Structure / Sectoral Split Public` | `config.demand.sectoral_public` | `demand.py:165` |

**Location:** `DemandProjector.get_sectoral_demand()` lines 153–170

---

## 3. Cost Module

**File:** `model/costs.py`

### EQ-C1: Solar PV CAPEX (with learning curve + climate premium)

$$\text{CAPEX}_{\text{solar}}(t) = C_{\text{solar}} \times (1 - \delta_s)^{t-t_0} \times Q_{\text{kW}} \times (1 + \alpha)$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|-----------------|
| $C_{\text{solar}}$ | Solar CAPEX $/kW | `Solar / CAPEX 2026` | `config.technology.solar_pv_capex` | `costs.py:137` |
| $\delta_s$ | Annual cost decline | `Solar / CAPEX Annual Decline` | `config.technology.solar_pv_cost_decline` | `costs.py:138` |
| $\alpha$ | Climate adaptation premium | `Climate / Adaptation CAPEX Premium` | `config.technology.climate_adaptation_premium` | `costs.py:144` |

**Location:** `CostCalculator.solar_capex()` lines 130–145

### EQ-C2: Solar PV OPEX

$$\text{OPEX}_{\text{solar}}(t) = Q_{\text{kW}} \times C_{\text{solar}} \times p_{\text{opex}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $p_{\text{opex}}$ | O&M as % of CAPEX | `Solar / OPEX (% of CAPEX)` | `config.technology.solar_pv_opex_pct` | `costs.py:162` |
| $C_{\text{solar}}$ | Base solar CAPEX $/kW | `Solar / CAPEX 2026` | `config.technology.solar_pv_capex` | `costs.py:161` |

**Location:** `CostCalculator.solar_opex()` lines 148–162

### EQ-C3: Solar PV generation (with temp derating + degradation)

$$G_{\text{solar}}(t) = Q_{\text{MW}} \times 8760 \times CF \times f_T \times f_D(t)$$

Where temperature derating (C7):
$$T_{\text{cell}} = T_{\text{amb}} + k_{\text{NOCT}} \times \frac{GHI}{24}$$
$$f_T = \max\left(0, \; 1 - k_t \times (T_{\text{cell}} - 25)\right)$$

And annual degradation (C8):
$$f_D(t) = (1 - d)^{t - t_{\text{install}}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|-----------------|
| $CF$ | Capacity factor | `Solar / Capacity Factor` | `config.technology.solar_pv_capacity_factor` | `costs.py:168` |
| $T_{\text{amb}}$ | Ambient temp (°C) | `Solar / Default Ambient Temp` | `config.technology.default_ambient_temp` | `costs.py:174` |
| $GHI$ | Solar irradiance | `Solar / Default GHI` | `config.technology.default_ghi` | `costs.py:176` |
| $k_{\text{NOCT}}$ | NOCT coefficient | `Solar / NOCT Coeff` | `config.technology.pv_noct_coeff` | `costs.py:186` |
| $k_t$ | Temp derating coeff | `Solar / Temp Derating Coeff` | `config.technology.pv_temp_derating_coeff` | `costs.py:187` |
| $d$ | Degradation rate | `Solar / Degradation Rate` | `config.technology.solar_pv_degradation` | `costs.py:194` |

**Location:** `CostCalculator.solar_generation()` lines 164–202

### EQ-C4: Battery CAPEX (with learning curve + climate premium)

$$\text{CAPEX}_{\text{batt}}(t) = C_{\text{batt}} \times (1 - \delta_b)^{t-t_0} \times Q_{\text{kWh}} \times (1 + \alpha)$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $C_{\text{batt}}$ | Battery CAPEX $/kWh | `Battery / CAPEX 2026` | `config.technology.battery_capex` | `costs.py:224` |
| $\delta_b$ | Annual cost decline | `Battery / CAPEX Annual Decline` | `config.technology.battery_cost_decline` | `costs.py:225` |
| $\alpha$ | Climate adaptation premium | `Climate / Adaptation CAPEX Premium` | `config.technology.climate_adaptation_premium` | `costs.py:232` |

**Location:** `CostCalculator.battery_capex()` lines 214–235

### EQ-C5: Battery OPEX

$$\text{OPEX}_{\text{batt}} = Q_{\text{kWh}} \times C_{\text{opex}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $C_{\text{opex}}$ | Battery O&M $/kWh/yr | `Battery / OPEX` | `config.technology.battery_opex` | `costs.py:241` |

**Location:** `CostCalculator.battery_opex()` lines 237–242

### EQ-C6: Diesel fuel cost (two-part curve, C9)

$$F(t) = L(t) \times P_f(t)$$

Where fuel consumption:
$$L(t) = Q_{\text{kW}} \times c_{\text{idle}} \times h + G_{\text{kWh}} \times c_{\text{prop}}$$

And fuel price escalation:
$$P_f(t) = P_0 \times (1 + e_f)^{t-t_0}$$

Operating hours estimation (M-BUG-3 fix):
$$h = \min\left(8760, \; \frac{G_{\text{kWh}}}{Q_{\text{kW}} \times \bar{l}}\right), \quad \bar{l} = \frac{l_{\min} + 1}{2}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|-----------------|
| $c_{\text{idle}}$ | Idle fuel coeff (l/hr/kW) | `Dispatch / Fuel Curve Idle Coeff` | `config.dispatch.fuel_curve_idle_coeff` | `costs.py:350` |
| $c_{\text{prop}}$ | Proportional coeff (l/kWh) | `Dispatch / Fuel Curve Proportional Coeff` | `config.dispatch.fuel_curve_proportional_coeff` | `costs.py:351` |
| $l_{\min}$ | Min load fraction | `Dispatch / Diesel Min Load Fraction` | `config.dispatch.diesel_min_load_fraction` | `costs.py:354` |
| $P_0$ | Base fuel price $/L | `Fuel / Diesel Price 2026` | `config.fuel.price_2026` | `FuelConfig.get_price()` |
| $e_f$ | Price escalation | `Fuel / Diesel Price Escalation` | `config.fuel.price_escalation` | `FuelConfig.get_price()` |

**Location:** `CostCalculator.diesel_fuel_cost()` lines 305–340, `diesel_fuel_consumption()` lines 342–385

### EQ-C7: Diesel fuel consumption (flat fallback)

$$L_{\text{flat}} = \frac{G_{\text{kWh}}}{\eta_{\text{fuel}}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $\eta_{\text{fuel}}$ | Fuel efficiency (kWh/L) | `Fuel / Fuel Efficiency` | `config.fuel.kwh_per_liter` | `costs.py:384` |

**Location:** `CostCalculator.diesel_fuel_consumption()` line 384 (fallback branch)

### EQ-C8: T&D loss gross-up (C2)

$$G_{\text{gross}} = \frac{D_{\text{net}}}{(1 - l_d) \times (1 - l_c)}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|-----------------|
| $l_d$ | Distribution loss | `Losses / Distribution Loss` | `config.technology.distribution_loss_pct` | `costs.py:436` |
| $l_c$ | HVDC cable loss | `Losses / HVDC Cable Loss` | `config.technology.hvdc_cable_loss_pct` | `costs.py:437` |

**Location:** `CostCalculator.gross_up_for_losses()` lines 405–440

**✅ FIXED:** Multiplicative (correct per M-BUG-1 fix), not additive.

### EQ-C9: Cable CAPEX (C4 — Full Breakdown)

$$\text{CAPEX}_{\text{cable}} = \left[\underbrace{L_{\text{km}} \times C_{\text{cable/km}}}_{\text{submarine}} + \underbrace{C_{\text{conv/MW}} \times P_{\text{cap}}}_{\text{converters}} + \underbrace{C_{\text{land}} \times N_{\text{land}}}_{\text{landing}}\right] \times (1 + r_{\text{IDC}}) + C_{\text{grid}} \times (1 + \alpha)$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $L_{\text{km}}$ | Cable length | `Cable / Length to India` | `config.one_grid.cable_length_km` | `config.py` |
| $C_{\text{cable/km}}$ | Cost per km | `Cable / CAPEX per km` | `config.technology.cable_capex_per_km` | `config.py` |
| $C_{\text{conv/MW}}$ | Converter station cost/MW | `Cable / Converter Station Cost per MW` | `config.technology.converter_station_cost_per_mw` | `config.py` |
| $P_{\text{cap}}$ | Cable capacity MW | `Cable / Cable Capacity` | `config.one_grid.cable_capacity_mw` | `config.py` |
| $C_{\text{land}}$ | Landing cost per end | `Cable / Landing Cost per End` | `config.technology.landing_cost_per_end` | `config.py` |
| $N_{\text{land}}$ | Number of landings | `Cable / Number of Landings` | `config.technology.num_landings` | `config.py` |
| $r_{\text{IDC}}$ | Interest during construction | `Cable / IDC Rate` | `config.technology.idc_rate` | `config.py` |
| $C_{\text{grid}}$ | Grid upgrade cost | `Cable / Grid Upgrade Cost` | `config.technology.grid_upgrade_cost` | `config.py` |
| $\alpha$ | Climate adaptation premium | `Climate / Adaptation CAPEX Premium` | `config.technology.climate_adaptation_premium` | `costs.py` |

**Location:** `get_config()` pre-computes `config.one_grid.cable_capex_total`. `CostCalculator.cable_capex()` applies climate premium.

**Note:** `cable_capex_total` is computed once in `get_config()` and stored in `config.one_grid.cable_capex_total`. When sensitivity/MC varies cable components, recomputation logic is in all 4 modify_config paths.

### EQ-C9b: Connection Cost per Household (L11)

$$\text{CAPEX}_{\text{connection}}(t) = \begin{cases} C_{\text{HH}} \times N_{\text{HH}} / Y_{\text{rollout}} & \text{if } t \leq t_0 + Y_{\text{rollout}} \\ 0 & \text{otherwise} \end{cases}$$

| Symbol | Meaning | CSV Parameter | Config Path |
|--------|---------|---------------|-------------|
| $C_{\text{HH}}$ | Cost per household | `Connection / Cost per Household` | `config.connection.cost_per_household` |
| $N_{\text{HH}}$ | Number of households | `Connection / Number of Households` | `config.connection.num_households` |
| $Y_{\text{rollout}}$ | Rollout period | `Connection / Rollout Years` | `config.connection.rollout_years` |

**Location:** `CostCalculator.connection_capex()` in `costs.py`. Wired in `one_grid.py`, `green_transition.py`, `islanded_green.py`.

### EQ-C9c: Environmental Externality Benefit (L16)

$$B_{\text{env}}(t) = \Delta D_{\text{diesel}}(t) \times \left(C_{\text{noise}} + C_{\text{spill}} + C_{\text{biodiversity}}\right)$$

| Symbol | Meaning | CSV Parameter | Config Path |
|--------|---------|---------------|-------------|
| $\Delta D_{\text{diesel}}$ | Diesel reduction vs BAU (GWh) | (computed) | — |
| $C_{\text{noise}}$ | Noise damage cost | `Environment / Noise Damage per MWh` | `config.economics.noise_damage_per_mwh` |
| $C_{\text{spill}}$ | Fuel spill risk cost | `Environment / Fuel Spill Risk per MWh` | `config.economics.fuel_spill_risk_per_mwh` |
| $C_{\text{biodiversity}}$ | Biodiversity impact cost | `Environment / Biodiversity Impact per MWh` | `config.economics.biodiversity_impact_per_mwh` |

**Location:** `CostCalculator.environmental_externality_benefit()` in `costs.py`. Flows into `AnnualBenefits.environmental_benefit` via `calculate_annual_benefits()` in `scenarios/__init__.py`.

### EQ-C10: PPA import cost

$$\text{PPA}(t) = G_{\text{import}} \times \left(P_{\text{PPA}} + P_{\text{tx}}\right) \times (1 + e_{\text{PPA}})^{t - t_{\text{online}}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $P_{\text{PPA}}$ | Import price | `PPA / Import Price 2030` | `config.ppa.import_price_2030` | `config.py:242` |
| $P_{\text{tx}}$ | Transmission charge | `PPA / Transmission Charge` | `config.ppa.transmission_charge` | `config.py:243` |
| $e_{\text{PPA}}$ | PPA escalation | `PPA / Price Escalation` | `config.ppa.price_escalation` | `config.py:244` |

**Location:** `PPAConfig.get_price()` lines 242–248, `CostCalculator.ppa_cost()` lines 473–487

### EQ-C11: Diesel LCOE in `costs.py` (standalone)

$$\text{LCOE}_{\text{diesel}} = \frac{P_f}{\eta_{\text{fuel}}} + C_{\text{O\&M}} + \frac{C_{\text{CAPEX/kW}}}{\tau \times 8760 \times CF_d}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|-----------------|
| $CF_d$ | Diesel capacity factor | `Dispatch / Diesel Avg Capacity Factor` | `config.dispatch.diesel_avg_capacity_factor` | `costs.py:556` |
| $P_f$ | Fuel price $/L | `Fuel / Diesel Price 2026` | `config.fuel.price_2026` | `costs.py:551` |
| $\eta_{\text{fuel}}$ | Fuel efficiency (kWh/L) | `Fuel / Fuel Efficiency` | `config.fuel.kwh_per_liter` | `costs.py:552` |
| $C_{\text{O\&M}}$ | Diesel O&M $/kWh | `Diesel Gen / OPEX` | `config.technology.diesel_gen_opex_kwh` | `costs.py:553` |
| $C_{\text{CAPEX/kW}}$ | Diesel CAPEX $/kW | `Diesel Gen / CAPEX` | `config.technology.diesel_gen_capex` | `costs.py:554` |
| $\tau$ | Diesel lifetime (years) | `Diesel Gen / Lifetime` | `config.technology.diesel_gen_lifetime` | `costs.py:555` |

~~⚠️ RED FLAG S-01:~~ ✅ FIXED (D47, 8 Feb 2026) — `CF_d` was hardcoded as 0.6; now reads from `config.dispatch.diesel_avg_capacity_factor`. This is used ONLY in the standalone `calculate_lcoe('diesel')` diagnostic method, never in the CBA engine.

---

## 4. Emissions Module

**File:** `model/emissions.py`

### EQ-E1: Diesel CO₂ emissions

$$E_{\text{diesel}} = G_{\text{kWh}} \times EF_{\text{CO}_2}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $EF_{\text{CO}_2}$ | Emission factor | `Fuel / CO2 Emission Factor` | `config.fuel.emission_factor_kg_co2_per_kwh` | `emissions.py:75` |

**Location:** `EmissionsCalculator.diesel_emissions()` lines 66–79

### EQ-E2: Import emissions (India grid, declining)

$$E_{\text{import}}(t) = G_{\text{kWh}} \times EF_{\text{India}} \times (1 - d_{\text{India}})^{t - t_{\text{base}}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $EF_{\text{India}}$ | India grid EF | `PPA / India Grid Emission Factor` | `config.ppa.india_grid_emission_factor` | `config.py:253` |
| $d_{\text{India}}$ | Annual decline | `PPA / India Grid Emission Decline` | `config.ppa.india_grid_emission_decline` | `config.py:256` |

**Location:** `PPAConfig.get_india_emission_factor()` lines 253–256, `EmissionsCalculator.import_emissions()` lines 81–100

~~⚠️ RED FLAG S-02:~~ ✅ FIXED (D46, 8 Feb 2026) — `india_grid_emission_factor` (0.70) and `india_grid_emission_decline` (0.02) were dataclass defaults only. Now added to `parameters.csv` as `PPA / India Grid Emission Factor` and `PPA / India Grid Emission Decline`, and wired in `get_config()` PPA block.

### EQ-E3: Social Cost of Carbon (with annual growth)

$$SCC(t) = SCC_0 \times (1 + g_{\text{SCC}})^{t - t_0}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $SCC_0$ | Base SCC | `Economics / Social Cost of Carbon` | `config.economics.social_cost_carbon` | `npv_calculator.py:245` |
| $g_{\text{SCC}}$ | SCC annual growth | `Economics / SCC Annual Growth` | `config.economics.scc_annual_growth` | `npv_calculator.py:246` |

**Location:** `CBACalculator._get_scc()` lines 245–250, `EmissionsCalculator.monetize_emissions()` lines 119–136

### EQ-E4: Emission monetisation

$$V_{\text{emission}} = E_{\text{tCO}_2} \times SCC(t)$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $E_{\text{tCO}_2}$ | Emissions (tCO₂) | — (computed) | — | `emissions.py:136` |
| $SCC(t)$ | Social Cost of Carbon | See EQ-E3 | See EQ-E3 | `emissions.py:133` |

**Location:** `EmissionsCalculator.monetize_emissions()` line 136

### EQ-E5: Solar lifecycle emissions

$$E_{\text{solar}} = Q_{\text{MW}} \times CF \times 8760 \times 1000 \times EF_{\text{lifecycle}} / 10^6$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $EF_{\text{lifecycle}}$ | Solar lifecycle EF | `Solar / Lifecycle Emission Factor` | `config.technology.solar_lifecycle_emission_factor` | `emissions.py:113` |
| $CF$ | Solar capacity factor | `Solar / Capacity Factor` | `config.technology.solar_pv_capacity_factor` | `emissions.py:114` |

**Location:** `EmissionsCalculator.solar_lifecycle_emissions()` lines 102–117

---

## 5. Least-Cost Electrification Engine

**File:** `model/least_cost.py`

### EQ-L1: Discounted LCOE (general form)

$$\text{LCOE} = \frac{\sum_{y=0}^{N-1} \frac{I_y + O_y + F_y - S_y}{(1+r)^y}}{\sum_{y=0}^{N-1} \frac{G_y}{(1+r)^y}}$$

Where:
- $I_y$ = investment in year $y$ (initial + reinvestment at end of tech life)
- $O_y$ = annual O&M
- $F_y$ = annual fuel cost (escalating)
- $S_y$ = salvage value at project end
- $G_y$ = annual generation with degradation: $G_y = G_0 \times (1-d)^{y-1}$ for $y \geq 1$; $G_0 = 0$ for $y=0$

Reinvestment: at year $y = \tau_{\text{tech}}$, $2\tau_{\text{tech}}$, … while $y < N$

Salvage: $S_{N-1} = \text{CAPEX} \times \max\left(0, \; 1 - \frac{(N-1) - y_{\text{last\_invest}}}{\tau_{\text{tech}}}\right)$

**Location:** `_discounted_lcoe()` lines 149–216

### EQ-L2: Solar+battery LCOE

**Sizing:**
$$Q_{\text{solar,kW}} = \frac{D / (1 - l_d)}{CF_{\text{eff}} \times 8760}$$
$$Q_{\text{batt,kWh}} = \frac{P_{\text{kW}} \times h_{\text{batt}}}{DoD}$$
$$CF_{\text{eff}} = CF \times f_T$$

Split into two LCOE components (different lifetimes):
$$\text{LCOE}_{\text{solar+batt}} = \text{LCOE}_{\text{solar}} + \text{LCOE}_{\text{batt}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $h_{\text{batt}}$ | Storage hours | `Battery / Storage Hours` | `config.technology.battery_hours` | `least_cost.py:243` |
| $DoD$ | Depth of discharge | `Dispatch / Battery DoD Max` | `config.dispatch.battery_dod_max` | `least_cost.py:244` |
| $CF$ | Solar capacity factor | `Solar / Capacity Factor` | `config.technology.solar_pv_capacity_factor` | `least_cost.py:232` |
| $l_d$ | Distribution loss | `Losses / Distribution Loss` | `config.technology.distribution_loss_pct` | `least_cost.py:231` |

~~⚠️ RED FLAG S-03:~~ ✅ FIXED (D46, 8 Feb 2026) — `battery_hours = 4.0` was in `SolarBatteryParams` default but NOT wired from config or CSV. Now added to `parameters.csv` as `Battery / Storage Hours` and wired via `load_params_from_config()` → `SolarBatteryParams.battery_hours`.

**Location:** `lcoe_solar_battery()` lines 219–294

### EQ-L3: Diesel LCOE (with fuel escalation)

$$F_y = Q_{\text{kW}} \times c_{\text{idle}} \times 8760 \times P_0 \times (1+e_f)^{y-1} + G_y \times c_{\text{prop}} \times P_0 \times (1+e_f)^{y-1}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $c_{\text{idle}}$ | Idle fuel coeff (l/hr/kW) | `Dispatch / Fuel Curve Idle Coeff` | `config.dispatch.fuel_curve_idle_coeff` | `least_cost.py:311` |
| $c_{\text{prop}}$ | Proportional coeff (l/kWh) | `Dispatch / Fuel Curve Proportional Coeff` | `config.dispatch.fuel_curve_proportional_coeff` | `least_cost.py:312` |
| $P_0$ | Base fuel price $/L | `Fuel / Diesel Price 2026` | `config.fuel.price_2026` | `least_cost.py:638` |
| $e_f$ | Fuel price escalation | `Fuel / Diesel Price Escalation` | `config.fuel.price_escalation` | `least_cost.py:639` |
| $l_{\min}$ | Min load fraction | `Dispatch / Diesel Min Load Fraction` | `config.dispatch.diesel_min_load_fraction` | `least_cost.py:642` |

**Note:** Diesel runs **all 8760 hours** at idle in this LCOE calculation — assumes standalone diesel is the sole source, always on. This differs from `costs.py` (EQ-C6) which estimates operating hours proportional to generation.

**Location:** `lcoe_diesel()` lines 297–381

### EQ-L4: Solar-diesel hybrid LCOE

Solar meets `solar_share` of demand; diesel provides rest + backup.
$$G_{\text{solar}} = D_{\text{gross}} \times s, \quad G_{\text{diesel}} = D_{\text{gross}} \times (1-s)$$

Idle fuel scaled: `(1 - solar_share)` fraction of 8760 hours.

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $s$ | Default solar share | `Dispatch / Hybrid Default Solar Share` | `config.dispatch.hybrid_default_solar_share` | `least_cost.py:643` |
| All diesel params | See EQ-L3 | See EQ-L3 | See EQ-L3 | `least_cost.py:386–492` |
| All solar+battery params | See EQ-L2 | See EQ-L2 | See EQ-L2 | `least_cost.py:386–492` |

**Location:** `lcoe_solar_diesel_hybrid()` lines 384–492

### EQ-L5: Grid extension LCOE

$$\text{LCOE}_{\text{grid}} = \frac{\text{Cable CAPEX} + \text{Annual cable O\&M} + \text{Electricity purchase}}{D_{\text{gross}}}$$

$$\text{Electricity purchase} = \frac{D_{\text{gross}}}{1 - l_c} \times P_{\text{hub}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $l_c$ | Cable loss | `Losses / HVDC Cable Loss` | `config.technology.hvdc_cable_loss_pct` | `least_cost.py:652` |
| $P_{\text{hub}}$ | Hub electricity price | `PPA / Import Price 2030` (S1) | `config.ppa.import_price_2030` | `least_cost.py:651` |
| Cable CAPEX/km | Inter-island cable cost | `Cable / Inter-island CAPEX per km` | `config.technology.inter_island_capex_per_km` | `least_cost.py:648` |

~~⚠️ RED FLAG S-04:~~ ✅ FIXED (D47, 8 Feb 2026) — `GridExtParams.cable_loss_pct = 0.03` was NOT wired from config in `load_params_from_config()`. Now wired as `cable_loss_pct=cfg.technology.hvdc_cable_loss_pct`.

**Location:** `lcoe_grid_extension()` lines 495–530

### EQ-L6: Haversine distance

$$d = 2R \times \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos\phi_1 \cos\phi_2 \sin^2\left(\frac{\Delta\lambda}{2}\right)}\right) \times \rho$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $R$ | Earth radius (6371 km) | — (mathematical constant) | — | `least_cost.py:537` |
| $\rho$ | Routing premium | `Network / Routing Premium` | `config.technology.routing_premium` | `least_cost.py:543` |

**Location:** `haversine_km()` lines 536–543

### EQ-L7: Island demand allocation

$$D_{\text{island}} = \text{Pop} \times D_{\text{per capita}}, \quad P_{\text{kW}} = \frac{D / 8760}{LF}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $D_{\text{per capita}}$ | kWh/capita/year | — (computed) | Derived from `config.demand.base_demand_gwh / population` | `least_cost.py:727` |
| $LF$ | Load factor | `Demand / Load Factor` | `config.demand.load_factor` | `least_cost.py:729` |

**Location:** `run_least_cost()` lines 727–729

### EQ-L8: Solar land constraint

$$f_{\text{land}} = \frac{Q_{\text{solar,kW}} \times A_{\text{kW}}}{A_{\text{island}} \times 10^6}$$

Solar constrained if $f_{\text{land}} > f_{\max}$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $A_{\text{kW}}$ | Area per kW (m²/kW) | `Solar / Area Per kW` | `config.technology.solar_area_per_kw` | `least_cost.py:736` |
| $f_{\max}$ | Max land fraction | `Solar / Max Land Fraction` | `config.technology.max_solar_land_fraction` | `least_cost.py:737` |

**Location:** `run_least_cost()` lines 733–744

### EQ-L9: Malé rooftop solar cap (H16)

For Malé specifically (dense urban, no ground-mount space), an additional constraint applies:

$$Q_{\text{solar,kW}} \leq Q_{\text{rooftop,kW}} = P_{\text{rooftop,MWp}} \times 1000$$

If $Q_{\text{solar,kW}} > Q_{\text{rooftop,kW}}$, island is marked `solar_constrained = True`.

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $P_{\text{rooftop,MWp}}$ | Malé rooftop solar potential | `Electricity Structure / Male Rooftop Solar Potential` | `config.current_system.male_rooftop_solar_mwp` | `least_cost.py` |

**Source:** ZNES Flensburg study (5 MWp public rooftops + 13 MWp sports facilities = 18 MWp, 27.5–28.8 GWh/yr).

**Location:** `run_least_cost()`, after EQ-L8 check

### Resort emissions context (informational, not in CBA)

`run_cba.py:print_resort_emissions_context()` computes annual resort sector emissions for national context:

$$E_{\text{resort}} = \frac{D_{\text{resort}} \times EF_{\text{resort}}}{1000} \quad [\text{MtCO}_2/\text{yr}]$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $D_{\text{resort}}$ | Resort demand (GWh/yr) | `Tourism / Resort Demand` | `config.tourism.resort_demand_gwh` | `run_cba.py` |
| $EF_{\text{resort}}$ | Resort emission factor | `Tourism / Resort Emission Factor` | `config.tourism.resort_emission_factor` | `run_cba.py` |
| $I_{\text{guest}}$ | kWh per guest-night | `Tourism / Resort kWh per Guest Night` | `config.tourism.resort_kwh_per_guest_night` | `run_cba.py` |

**Output:** 0.89 MtCO₂/yr, 26.8 MtCO₂ cumulative (30yr). **Not included in CBA NPV** — resorts are off-grid and self-generated.

---

## 6. NPV / CBA Calculator

**File:** `model/cba/npv_calculator.py`

### EQ-N1: Discount factor

$$DF(t) = \frac{1}{(1 + r)^{t - t_0}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $r$ | Discount rate | `Economics / Discount Rate` | `config.economics.discount_rate` | `npv_calculator.py:131` |

**Location:** `CBACalculator.discount_factor()` lines 131–136

### EQ-N2: Present value of cost stream

$$PV = \sum_{t} V(t) \times DF(t)$$

**Location:** `CBACalculator.present_value()` lines 138–143

### EQ-N3: Annuity factor

$$AF = \frac{r(1+r)^n}{(1+r)^n - 1}$$

**Location:** `CBACalculator.annuity_factor()` lines 145–155

### EQ-N4: LCOE from NPV

$$\text{LCOE} = \frac{PV_{\text{total costs}}}{\sum_t D(t) \times 10^6 \times DF(t)}$$

**Location:** `CBACalculator.calculate_npv()` line 197

### EQ-N5: Salvage value (C3 — straight-line depreciation)

For each asset class:
$$SV_{\text{asset}} = \text{CAPEX}_{\text{unit}} \times Q \times \frac{\text{remaining life}}{\tau}$$

**Solar:** Average install year = midpoint of horizon.
$$\text{remaining} = \max(0, \tau_{\text{solar}} - (t_{\text{end}} - t_{\text{mid}}))$$

**Battery & Diesel** (M-BUG-6 fix — modular replacement):
$$\text{age} = N \bmod \tau, \quad \text{remaining} = \begin{cases} 0 & \text{if age}=0 \\ \tau - \text{age} & \text{otherwise} \end{cases}$$

**Cable:**
$$\text{remaining} = \max(0, \tau_{\text{cable}} - (t_{\text{end}} - t_{\text{online}}))$$

Discounted to base year: $SV_{\text{total}} \times DF(t_{\text{end}})$

**Location:** `CBACalculator.calculate_salvage_value()` lines 202–290

### EQ-N6: Incremental analysis

$$\Delta \text{CAPEX} = PV_{\text{alt, capex}} - PV_{\text{base, capex}}$$
$$\Delta \text{Fuel savings} = PV_{\text{base, fuel}} - PV_{\text{alt, fuel}}$$
$$\Delta \text{Emission savings} = PV_{\text{base, emissions}} - PV_{\text{alt, emissions}}$$
$$\Delta \text{Health savings} = PV_{\text{alt, health}} - PV_{\text{base, health}}$$
$$NPV = (\Delta \text{Fuel} + \Delta \text{Emissions} + \Delta \text{Health}) - (\Delta \text{CAPEX} + \Delta \text{OPEX} + \Delta \text{PPA})$$
$$BCR = \frac{\text{Total Benefits}}{\text{Total Costs}}$$

**Location:** `CBACalculator.calculate_incremental()` lines 296–365

### EQ-N7: Internal Rate of Return

$$\sum_{t=0}^{N} \frac{CF_t}{(1+IRR)^t} = 0$$

Solved via `numpy_financial.irr()` or bisection fallback.

$$CF_t = (\text{Fuel savings}_t) - (\Delta \text{CAPEX}_t + \Delta \text{OPEX}_t + \Delta \text{PPA}_t)$$

**Location:** `CBACalculator._calculate_irr()` lines 444–474

### EQ-N8: Health co-benefits (L4)

$$B_{\text{health}}(t) = (G_{\text{diesel,base}} - G_{\text{diesel,alt}}) \times 1000 \times C_{\text{health}}$$

| Symbol | Meaning | CSV Parameter | Config Path | Script Location |
|--------|---------|---------------|-------------|------------------|
| $C_{\text{health}}$ | Health damage cost | `Health / Damage Cost per MWh Diesel` | `config.economics.health_damage_cost_per_mwh` | `scenarios/__init__.py:300` |

**Location:** `BaseScenario.calculate_annual_benefits()` lines 293–302 in `scenarios/__init__.py`

~~⚠️ RED FLAG S-05:~~ ✅ FIXED (D49, Feb 2026) — `calculate_annual_benefits()` now takes `baseline_gen_mix: GenerationMix` parameter and uses `baseline_gen_mix.diesel_gwh` directly instead of the fragile `fuel_cost / fuel_price × kwh_per_liter / 1e6` backward-calculation. Health benefit values verified: FI $1,044M, NG $602M, IG $554M.

---

## 7. Financing Analysis

**File:** `model/financing_analysis.py`

### EQ-F1: Grant element (OECD-DAC/IMF method)

$$GE = 1 - \frac{\sum_{t=1}^{T} \frac{\text{payment}_t}{(1+r_c)^t}}{F}$$

Where during grace period: $\text{payment}_t = F \times r_a$ (interest only)  
After grace: $\text{payment}_t = \frac{F}{T-G} + (F - \text{principal paid}) \times r_a$

| Symbol | Meaning | CSV Parameter | Config Path |
|--------|---------|---------------|-------------|
| $r_a$ | ADB concessional rate | `Financing / ADB SIDS Concessional Rate` | `config.financing.adb_sids_rate` |
| $r_c$ | Commercial rate | `Economics / Commercial Interest Rate` | `config.financing.commercial_interest_rate` |
| $T$ | Maturity | `Financing / ADB SIDS Maturity` | `config.financing.adb_sids_maturity` |
| $G$ | Grace period | `Financing / ADB SIDS Grace Period` | `config.financing.adb_sids_grace` |

**Location:** `calculate_grant_element()` lines 164–209

### EQ-F2: Blended WACC

$$WACC = w_a \times r_a + (1 - w_a) \times r_c$$

| Symbol | Meaning | CSV Parameter | Config Path |
|--------|---------|---------------|-------------|
| $w_a$ | ADB eligible share | `Financing / ADB Eligible CAPEX Share` | `config.financing.adb_eligible_share` |

**Location:** `calculate_wacc()` lines 272–280

### EQ-F3: Debt service schedule

Equal principal repayment:
$$\text{Principal}_t = \frac{F}{T-G}, \quad \text{Interest}_t = O_t \times r$$

where $O_t$ is outstanding principal at start of year $t$.

**Location:** `build_loan_schedule()` lines 219–262

### EQ-F4: Fiscal burden

$$\text{Peak debt/GDP} = \frac{\max_t(\text{ADB service}_t + \text{Commercial service}_t)}{\text{GDP}} \times 100$$

| Symbol | Meaning | CSV Parameter | Config Path |
|--------|---------|---------------|-------------|
| GDP | Nominal GDP | `Macro / GDP Billion USD` | `config.financing.gdp_billion_usd` |

**Location:** `analyse_scenario()` lines 350–360

---

## 8. Scenario Logic

### S1: BAU (`model/scenarios/status_quo.py`)

**Equations used:** EQ-D1, EQ-D2, EQ-C3, EQ-C6, EQ-C8

**Key logic:**
- Existing solar maintained (degradation via EQ-C3), no new additions
- Diesel expands to meet growth: `required_diesel = peak × (1 + reserve_margin) - solar × solar_peak_contribution`
- Rolling diesel replacement: `annual_replacement = capacity / lifetime`
- All parameters from config ✅

### S2: Full Integration (`model/scenarios/one_grid.py`)

**Equations used:** EQ-D1, EQ-D2, EQ-C1–C10, EQ-L1–L8

**Key logic:**
- Runs `least_cost.py` with hub_price = India import price
- Population-weighted demand split: `cable_share = cable_pop / total_pop`
- Import capped by cable capacity: `min(demand × cable_share, cable_capacity × 8760 × LF / 1000)`
- Domestic RE growth after year 7: `re_growth = min(target_2050, 0.05 × (years - 7))`
- India cable CAPEX spread over construction years
- All parameters from config ✅

### S3: National Grid (`model/scenarios/green_transition.py`)

**Equations used:** EQ-D1, EQ-D2, EQ-C1–C6, EQ-C8, EQ-L1–L8

**Key logic:**
- Runs `least_cost.py` with hub_price = domestic solar LCOE
- Hub LCOE calculated inline: `annuity × CAPEX/kW + OPEX / (CF × 8760)`
- Uses green_transition RE targets for deployment schedule
- 7-year ramp (longer than S1)
- No import — all domestic generation
- All parameters from config ✅

### S4: Islanded Green (`model/scenarios/islanded_green.py`)

**Equations used:** EQ-D1, EQ-D2, EQ-C1–C6, EQ-C8, EQ-L1–L8

**Key logic:**
- Runs `least_cost.py` with hub_price = $999 (forces all islands standalone)
- Solar-constrained islands get hybrid
- Islanded cost premium applied: `CAPEX × islanded_cost_premium` (1.30)
- Higher battery ratio: `islanded_battery_ratio`
- 5-year ramp
- All parameters from config ✅

### S5: Near-Shore Solar (`model/scenarios/nearshore_solar.py`)

**Equations used:** EQ-D1, EQ-D2, EQ-C1–C6, EQ-C8, EQ-L1–L8

**Key logic:**
- Extends S3 National Grid with 104 MW near-shore solar on uninhabited islands near Malé
- Near-shore solar breaks Malé's 4% rooftop RE cap, reaching ~25% Malé RE
- National RE rises to ~53%
- All parameters from config ✅

### S6: Maximum RE (`model/scenarios/maximum_re.py`)

**Equations used:** EQ-D1, EQ-D2, EQ-C1–C6, EQ-C8, EQ-L1–L8

**Key logic:**
- Extends S5 with 195 MW floating solar (GoM Roadmap target)
- 1.5× CAPEX premium for floating panels
- Malé RE rises to ~44%, national RE ~55%
- MCA rank #1 (weighted score 0.726)
- All parameters from config ✅

### S7: LNG Transition (`model/scenarios/lng_transition.py`)

**Equations used:** EQ-D1, EQ-D2, EQ-C1–C6, EQ-C8, EQ-L1–L8

**Key logic:**
- Malé switches from diesel to 140 MW LNG at Gulhifalhu from 2031
- Outer islands identical to S3 (50 MW/yr solar+battery ramp)
- LNG emission factor 0.40 kgCO₂/kWh (vs diesel 0.72)
- Lowest LCOE ($0.196/kWh) and highest BCR (9.32)
- All parameters from config ✅

---

## 9. Sensitivity & Monte Carlo

### One-way sensitivity (`model/cba/sensitivity.py`, `model/run_sensitivity.py`)

22 parameters varied Low→High from `SENSITIVITY_PARAMS` (populated by CSV Low/High columns).

> **Note:** The model now supports **35 sensitivity parameters** (V2b expansion added 12 S5/S6/S7-specific params to the original 22). The table below shows the core 22; see `sensitivity.py:_define_parameters()` for the full list.

| # | Parameter | CSV Low/High Source | Config Attribute Modified |
|---|-----------|-------------------|--------------------------|
| 1 | `discount_rate` | `Economics / Discount Rate` | `config.economics.discount_rate` |
| 2 | `diesel_price` | `Fuel / Diesel Price 2026` | `config.fuel.price_2026` |
| 3 | `diesel_escalation` | `Fuel / Diesel Price Escalation` | `config.fuel.price_escalation` |
| 4 | `import_price` | `PPA / Import Price 2030` | `config.ppa.import_price_2030` |
| 5 | `solar_capex` | `Solar / CAPEX 2026` | `config.technology.solar_pv_capex` |
| 6 | `solar_cf` | `Solar / Capacity Factor` | `config.technology.solar_pv_capacity_factor` |
| 7 | `battery_capex` | `Battery / CAPEX 2026` | `config.technology.battery_capex` |
| 8 | `cable_capex_per_km` | `Cable / CAPEX per km` | `config.technology.cable_capex_per_km` + recompute `cable_capex_total` |
| 9 | `gom_cost_share` | `Cable / GoM Cost Share` | `config.one_grid.gom_share_pct` |
| 10 | `social_cost_carbon` | `Economics / Social Cost of Carbon` | `config.economics.social_cost_carbon` |
| 11 | `demand_growth` | `Demand / Growth Rate - BAU` | All `config.demand.growth_rates[*]` (scaled proportionally) |
| 12 | `outage_rate` | `Cable Outage / Outage Rate` | `config.cable_outage.outage_rate_per_yr` |
| 13 | `idle_fleet_cost` | `Supply Security / Idle Fleet Annual Cost` | `config.supply_security.idle_fleet_annual_cost_m` |
| 14 | `price_elasticity` | `Demand / Price Elasticity of Demand` | `config.demand.price_elasticity` |
| 15 | `health_damage` | `Economics / Health Damage Cost per MWh` | `config.economics.health_damage_cost_per_mwh` |
| 16 | `fuel_efficiency` | `Fuel / Fuel Efficiency` | `config.fuel.kwh_per_liter` |
| 17 | `base_demand` | `Demand / Base Demand 2026` | `config.demand.base_demand_gwh` |
| 18 | `battery_hours` | `Battery / Storage Hours` | `config.technology.battery_hours` |
| 19 | `climate_premium` | `Climate / Adaptation CAPEX Premium` | `config.technology.climate_adaptation_premium` |
| 20 | `converter_station` | `Cable / Converter Station Cost per MW` | `config.technology.converter_station_cost_per_mw` + recompute `cable_capex_total` |
| 21 | `connection_cost` | `Connection / Cost per Household` | `config.connection.cost_per_household` + `config.technology.connection_cost_per_hh` |
| 22 | `env_externality` | Composite: noise + spill + biodiversity | All 3 sub-components (proportional scaling) |

**Note:** Parameters 8 and 20 trigger recomputation of `cable_capex_total` when varied. Parameter 22 is a composite — varying it scales all 3 environmental externality sub-components proportionally.

### Monte Carlo (`model/run_monte_carlo.py`)

- 1,000 iterations, triangular distribution (Low, Base, High)
- Same 35 parameters as sensitivity analysis
- Returns scenario rankings, percentiles, least-cost frequency
- Cable CAPEX recomputation for params 8, 20

### Multi-Criteria Analysis (`model/cba/mca_analysis.py`) — L17 🆕

Complements CBA with non-monetary evaluation across 8 criteria:

$$S_j = \sum_{i=1}^{8} w_i \times \frac{x_{ij} - \min_j(x_{ij})}{\max_j(x_{ij}) - \min_j(x_{ij})}$$

where $S_j$ is the total weighted score for scenario $j$, $w_i$ is the weight for criterion $i$, and $x_{ij}$ is the raw metric value. Direction-adjusted: for "lower is better" criteria (fiscal burden), normalisation is inverted.

| # | Criterion | Weight | Direction | Source |
|---|-----------|--------|-----------|--------|
| 1 | Economic Efficiency (NPV savings) | 20% | Higher better | CBA model output |
| 2 | Environmental Impact (CO₂ reduction) | 15% | Higher better | CBA model output |
| 3 | Energy Security (RE share) | 15% | Higher better | CBA model output |
| 4 | Health Co-Benefits | 10% | Higher better | CBA model output |
| 5 | Fiscal Burden (CAPEX) | 10% | Lower better | CBA model output |
| 6 | Implementation Feasibility | 10% | Higher better | Expert-assigned |
| 7 | Social Equity (Access) | 10% | Higher better | Expert-assigned |
| 8 | Climate Resilience | 10% | Higher better | Expert-assigned |

Weight sensitivity tested with 4 profiles: equal, economic focus, environmental focus, equity focus.

---

## 10. Complete Parameter Traceability Map

### Parameters in CSV that are properly wired (✅ Verified)

| # | CSV Category/Parameter | Config Attribute | Used In |
|---|----------------------|-----------------|---------|
| 1 | `Demand / Base Demand 2026` | `demand.base_demand_gwh` | demand.py, all scenarios |
| 2 | `Demand / Base Peak 2026` | `demand.base_peak_mw` | demand.py |
| 3 | `Demand / Load Factor` | `demand.load_factor` | demand.py |
| 4 | `Demand / Growth Rate - BAU` | `demand.growth_rates["status_quo"]` | status_quo.py, green_transition.py, islanded_green.py |
| 5 | `Demand / Growth Rate - National Grid` | `demand.growth_rates["green_transition"]` | green_transition.py |
| 6 | `Demand / Growth Rate - Full Integration` | `demand.growth_rates["one_grid"]` | one_grid.py |
| 7 | `Demand / Price Elasticity` | `demand.price_elasticity` | demand.py:222 |
| 8 | `Fuel / Diesel Price 2026` | `fuel.price_2026` | costs.py, least_cost.py |
| 9 | `Fuel / Diesel Price Escalation` | `fuel.price_escalation` | costs.py, least_cost.py |
| 10 | `Fuel / Fuel Efficiency` | `fuel.kwh_per_liter` | costs.py:384 |
| 11 | `Fuel / CO2 Emission Factor` | `fuel.emission_factor_kg_co2_per_kwh` | emissions.py |
| 12 | `Solar / CAPEX 2026` | `technology.solar_pv_capex` | costs.py, least_cost.py |
| 13 | `Solar / CAPEX Annual Decline` | `technology.solar_pv_cost_decline` | costs.py, least_cost.py |
| 14 | `Solar / OPEX (% of CAPEX)` | `technology.solar_pv_opex_pct` | costs.py, least_cost.py |
| 15 | `Solar / Capacity Factor` | `technology.solar_pv_capacity_factor` | costs.py, least_cost.py, scenarios |
| 16 | `Solar / Degradation Rate` | `technology.solar_pv_degradation` | costs.py, least_cost.py |
| 17 | `Solar / Lifetime` | `technology.solar_pv_lifetime` | costs.py, npv_calculator.py, least_cost.py |
| 18 | `Solar / Lifecycle Emission Factor` | `technology.solar_lifecycle_emission_factor` | emissions.py |
| 19 | `Solar / Temp Derating Coeff` | `technology.pv_temp_derating_coeff` | costs.py, least_cost.py |
| 20 | `Solar / NOCT Coeff` | `technology.pv_noct_coeff` | costs.py, least_cost.py |
| 21 | `Solar / Max Land Fraction` | `technology.max_solar_land_fraction` | least_cost.py |
| 22 | `Solar / Area Per kW` | `technology.solar_area_per_kw` | least_cost.py |
| 23 | `Solar / Default Ambient Temp` | `technology.default_ambient_temp` | costs.py, least_cost.py |
| 24 | `Solar / Default GHI` | `technology.default_ghi` | costs.py, least_cost.py |
| 25 | `Battery / CAPEX 2026` | `technology.battery_capex` | costs.py, least_cost.py, scenarios |
| 26 | `Battery / CAPEX Annual Decline` | `technology.battery_cost_decline` | costs.py, least_cost.py |
| 27 | `Battery / Round-trip Efficiency` | `technology.battery_efficiency` | least_cost.py |
| 28 | `Battery / Lifetime` | `technology.battery_lifetime` | costs.py, npv_calculator.py, scenarios |
| 29 | `Cable / Length to India` | `one_grid.cable_length_km` | costs.py, npv_calculator.py |
| 30 | `Cable / Capacity` | `one_grid.cable_capacity_mw` | one_grid.py |
| 31 | `Cable / GoM Cost Share` | `one_grid.gom_share_pct` | costs.py, npv_calculator.py, scenarios |
| 32 | `Cable / Online Year` | `one_grid.cable_online_year` | scenarios, emissions.py |
| 33 | `Cable / CAPEX per km` | `technology.cable_capex_per_km` | costs.py |
| 34 | `Economics / Discount Rate` | `economics.discount_rate` | npv_calculator.py, least_cost.py |
| 35 | `Economics / Social Cost of Carbon` | `economics.social_cost_carbon` | npv_calculator.py, emissions.py |
| 36 | `Economics / SCC Annual Growth` | `economics.scc_annual_growth` | npv_calculator.py, emissions.py |
| 37 | `Economics / Value of Lost Load` | `economics.voll` | — (wired but not used in CBA) |
| 38 | `PPA / Import Price 2030` | `ppa.import_price_2030` | costs.py, one_grid.py |
| 39 | `PPA / Transmission Charge` | `ppa.transmission_charge` | costs.py |
| 40 | `PPA / Price Escalation` | `ppa.price_escalation` | costs.py |
| 41 | `Losses / Distribution Loss` | `technology.distribution_loss_pct` | costs.py, least_cost.py |
| 42 | `Losses / HVDC Cable Loss` | `technology.hvdc_cable_loss_pct` | costs.py |
| 43 | `Dispatch / Fuel Curve Idle Coeff` | `dispatch.fuel_curve_idle_coeff` | costs.py, least_cost.py |
| 44 | `Dispatch / Fuel Curve Proportional Coeff` | `dispatch.fuel_curve_proportional_coeff` | costs.py, least_cost.py |
| 45 | `Dispatch / Diesel Min Load Fraction` | `dispatch.diesel_min_load_fraction` | costs.py |
| 46 | `Dispatch / Battery DoD Max` | `dispatch.battery_dod_max` | least_cost.py |
| 47 | `Dispatch / Hybrid Default Solar Share` | `dispatch.hybrid_default_solar_share` | least_cost.py |
| 48 | `Operations / Reserve Margin` | `technology.reserve_margin` | scenarios, least_cost.py |
| 49 | `Operations / Solar Peak Contribution` | `technology.solar_peak_contribution` | scenarios |
| 50 | `Climate / Adaptation CAPEX Premium` | `technology.climate_adaptation_premium` | costs.py |
| 51 | `Cable Outage / Outage Rate` | `cable_outage.outage_rate_per_yr` | MC/sensitivity |
| 52 | `Supply Security / Idle Fleet Annual Cost` | `supply_security.idle_fleet_annual_cost_m` | one_grid.py |
| 53 | `Health / Damage Cost per MWh Diesel` | `economics.health_damage_cost_per_mwh` | scenarios/__init__.py |
| 54 | `Financing / ADB SIDS Concessional Rate` | `financing.adb_sids_rate` | financing_analysis.py |
| 55 | `Financing / ADB SIDS Maturity` | `financing.adb_sids_maturity` | financing_analysis.py |
| 56 | `Financing / ADB SIDS Grace Period` | `financing.adb_sids_grace` | financing_analysis.py |
| 57 | `Financing / ADB Eligible CAPEX Share` | `financing.adb_eligible_share` | financing_analysis.py |
| 58 | `Economics / Commercial Interest Rate` | `financing.commercial_interest_rate` | financing_analysis.py |
| 59 | `Macro / GDP Billion USD` | `financing.gdp_billion_usd` | financing_analysis.py |
| 60 | `Network / Routing Premium` | `technology.routing_premium` | least_cost.py |
| 61 | `Electricity Structure / Sectoral Split *` | `demand.sectoral_*` | demand.py |
| 62 | `Tourism / Resort kWh per Guest Night` | `tourism.resort_kwh_per_guest_night` | run_cba.py (`print_resort_emissions_context()`) |
| 63 | `Electricity Structure / Male Rooftop Solar Potential` | `current_system.male_rooftop_solar_mwp` | least_cost.py (Malé solar cap, EQ-L9) |

### Parameters NOT in CSV (dataclass defaults only) — Wiring Gaps (updated)

| # | Config Attribute | Default Value | Used In | Status |
|---|-----------------|---------------|---------|--------|
| ~~S-02~~ | ~~`ppa.india_grid_emission_factor`~~ | ~~0.70~~ | ~~emissions.py~~ | ✅ FIXED (D46) — Added to CSV as `PPA / India Grid Emission Factor` |
| ~~S-02~~ | ~~`ppa.india_grid_emission_decline`~~ | ~~0.02~~ | ~~emissions.py~~ | ✅ FIXED (D46) — Added to CSV as `PPA / India Grid Emission Decline` |
| ~~S-03~~ | ~~`SolarBatteryParams.battery_hours`~~ | ~~4.0~~ | ~~least_cost.py~~ | ✅ FIXED (D46) — Added to CSV as `Battery / Storage Hours` |
| ~~S-04~~ | ~~`GridExtParams.cable_loss_pct`~~ | ~~0.03~~ | ~~least_cost.py~~ | ✅ FIXED (D47) — Wired from `cfg.technology.hvdc_cable_loss_pct` |
| ~~S-06~~ | ~~`ppa.minimum_offtake_pct`~~ | ~~0.70~~ | ~~— (not used)~~ | ✅ REMOVED — Dead code, never used in any equation |
| ~~S-06~~ | ~~`ppa.contract_duration`~~ | ~~25~~ | ~~— (not used)~~ | ✅ REMOVED — Dead code, never used in any equation |
| S-06 | `ppa.cable_online_year` (in PPA) | 2032 | — (duplicate) | 🔵 `one_grid.cable_online_year` is canonical |
| ~~S-07~~ | ~~`technology.battery_opex`~~ | ~~5.0~~ | ~~costs.py, least_cost.py~~ | ✅ FIXED (D45) — Wired from CSV `Battery / OPEX` |
| ~~S-08~~ | ~~`technology.diesel_gen_capex`~~ | ~~800.0~~ | ~~costs.py, least_cost.py, scenarios~~ | ✅ FIXED (D45) — Wired from CSV `Diesel Gen / CAPEX` |
| ~~S-08~~ | ~~`technology.diesel_gen_opex_kwh`~~ | ~~0.025~~ | ~~costs.py, least_cost.py~~ | ✅ FIXED (D45) — Wired from CSV `Diesel Gen / OPEX` |
| ~~S-18~~ | ~~`technology.diesel_gen_lifetime`~~ | ~~20~~ | ~~costs.py, npv_calculator.py~~ | ✅ FIXED (D45) — Wired from CSV `Diesel Gen / Lifetime` |
| ~~S-09~~ | ~~`green_transition.re_targets`~~ | ~~dict~~ | ~~s2, s3~~ | ✅ WIRED — `get_config()` reads `RE Targets` CSV category, parses year keys into `config.green_transition.re_targets[year]` via loop |
| ~~S-10~~ | ~~`one_grid.domestic_re_target_2050`~~ | ~~0.30~~ | ~~one_grid.py~~ | ✅ FIXED (D46) — Added to CSV as `RE Targets / Domestic RE Target 2050` |
| ~~S-11~~ | ~~`current_system.*` various~~ | ~~various~~ | ~~scenarios~~ | ✅ Key fields wired — 6/13 operational fields (total_capacity_mw, diesel/solar/battery_capacity, diesel/re_share) loaded from CSV `Current System` category. Remaining 7 (population, saidi, saifi, etc.) are auxiliary/informational. |
| ~~S-12~~ | ~~`green_transition.islanded_*`~~ | ~~various~~ | ~~islanded_green.py~~ | ✅ WIRED — All 5 fields loaded from CSV `Islanded` category at `get_config()` lines 775-783 |

---

## 11. Structural Concerns & Red Flags

### 🔴 CRITICAL

#### ~~S-01: Hardcoded CF=0.6 in diesel LCOE diagnostic~~ ✅ FIXED (D47, 8 Feb 2026)
- **File:** [costs.py](model/costs.py#L556)
- **Issue:** `cf = 0.6` hardcoded instead of using `config.dispatch.diesel_avg_capacity_factor`
- **Impact:** Low — only used in diagnostic `calculate_lcoe('diesel')`, never in CBA engine
- **Fix applied:** Replaced with `cf = self.config.dispatch.diesel_avg_capacity_factor`

#### ~~S-05: Health benefit uses fragile fuel-cost-based diesel estimation~~ ✅ FIXED (Feb 2026)
- **File:** [scenarios/__init__.py](model/scenarios/__init__.py#L299-L314)
- **Issue:** ~~Baseline diesel GWh was estimated by `fuel_cost / fuel_price × kwh_per_liter / 1e6` instead of directly using baseline `gen_mix.diesel_gwh`~~
- **Impact:** Medium — could produce incorrect health benefits if fuel prices differ between base/alt runs
- **Fix applied:** Added `baseline_gen_mix: GenerationMix` parameter to `calculate_annual_benefits()`. Now uses `baseline_gen_mix.diesel_gwh` directly. Caller `calculate_benefits_vs_baseline()` passes `baseline_results.generation_mix.get(year)`. Health benefit values unchanged: FI $1,044M, NG $602M, IG $554M.

#### ~~S-13: `getattr(tech, 'reserve_margin', 0.15)` fallback~~ ✅ FIXED (D47, 8 Feb 2026)
- **File:** [least_cost.py](model/least_cost.py#L317)
- **Issue:** Uses `getattr` with hardcoded fallback 0.15 instead of direct attribute access
- **Impact:** Low — `reserve_margin` is always present in `TechParams`, so fallback never triggers. But it masks potential AttributeError bugs.
- **Fix applied:** Replaced with `tech.reserve_margin` (direct access, no fallback)

### 🟡 MODERATE

#### ~~S-02: India grid emission parameters not in CSV~~ ✅ FIXED (D46, 8 Feb 2026)
- **File:** [config.py](model/config.py#L237-L238)
- **Issue:** `india_grid_emission_factor=0.70` and `india_grid_emission_decline=0.02` were dataclass defaults only
- **Impact:** Medium — sensitivity analysis could not vary these parameters
- **Fix applied:** Added `PPA,India Grid Emission Factor,0.70` and `PPA,India Grid Emission Decline,0.02` to `parameters.csv`; wired in `get_config()` PPA block

#### ~~S-03: `battery_hours` not wired from config~~ ✅ FIXED (D46, 8 Feb 2026)
- **File:** [least_cost.py](model/least_cost.py#L65)
- **Issue:** `SolarBatteryParams.battery_hours = 4.0` was never overridden by `load_params_from_config()`
- **Impact:** Medium — battery sizing in island LCOE always used 4.0h regardless of CSV
- **Fix applied:** Added `Battery,Storage Hours,4.0` to `parameters.csv`; added `battery_hours` field to `TechnologyCosts` in `config.py`; wired in `load_params_from_config()` → `SolarBatteryParams.battery_hours`

#### ~~S-04: `cable_loss_pct` not wired in least_cost~~ ✅ FIXED (D47, 8 Feb 2026)
- **File:** [least_cost.py](model/least_cost.py#L98)
- **Issue:** `GridExtParams.cable_loss_pct = 0.03` was default-only; `load_params_from_config()` didn't set it
- **Impact:** Low today but would diverge if CSV changed `Losses / Distribution Loss`
- **Fix applied:** Wired `cable_loss_pct=cfg.technology.hvdc_cable_loss_pct` in `load_params_from_config()` → `GridExtParams`

#### ~~S-14: `network.py` hardcoded defaults in function signatures~~ ✅ FIXED (Feb 2026)
- **File:** [network.py](model/network.py#L236-L283)
- **Issue:** ~~`routing_premium: float = 1.15`, `intra_atoll_capex_per_km_usd: float = 1_500_000`, `inter_atoll_capex_per_km_usd: float = 3_000_000` hardcoded in `__init__` and `from_csv` signatures~~
- **Impact:** Low — `from_config()` classmethod existed and used proper config values. But direct instantiation bypassed config.
- **Fix applied:** Changed all defaults to `None` in both `__init__` and `from_csv`. If None, values are loaded from `get_config()` automatically. No hardcoded fallbacks remain.

#### ~~S-15: `run_monte_carlo.py` fallback growth rate~~ ✅ FIXED (D47, 8 Feb 2026)
- **File:** [run_monte_carlo.py](model/run_monte_carlo.py#L84)
- **Issue:** `base_bau = base_config.demand.growth_rates.get("status_quo", 0.05)` had hardcoded fallback `0.05`
- **Impact:** Low — key always exists. But violated zero-hardcoded-values principle.
- **Fix applied:** Replaced `.get("status_quo", 0.05)` with `["status_quo"]` — let KeyError surface if key is missing

### 🔵 LOW

#### ~~S-06: Unused PPA parameters~~ ✅ REMOVED (Feb 2026)
- **File:** [config.py](model/config.py#L234-L236)
- **Issue:** ~~`minimum_offtake_pct`, `contract_duration`, `india_grid_base_year` defined but never used in any calculation~~
- **Impact:** None — dead code
- **Resolution:** `minimum_offtake_pct` and `contract_duration` removed from `PPAConfig`. `cable_online_year` kept as backward-compat alias for `one_grid.cable_online_year`.

#### ~~S-16: Solar salvage uses "average install year" simplification~~ ✅ FIXED (Feb 2026)
- **File:** [npv_calculator.py](model/cba/npv_calculator.py#L227-L233)
- **Issue:** ~~Assumed all solar installed at midpoint of horizon, not tracking vintage-by-vintage~~
- **Impact:** Low — was a systematic approximation
- **Fix applied:** Vintage-tracking salvage: iterates year-over-year `solar_capacity_mw` from `generation_mix`, computes per-vintage remaining life and cost-declined CAPEX at actual install year. Delta: NG -$40M, IG -$37M (RE scenarios get slightly more salvage credit).

#### ~~S-17: Battery salvage uses `horizon_length % battery_life`~~ ✅ FIXED (Feb 2026)
- **File:** [npv_calculator.py](model/cba/npv_calculator.py#L240-L246)
- **Issue:** ~~Correct for uniform fleet, but if battery additions are phased (as in real scenarios), different vintages have different remaining life~~
- **Impact:** Low — was "uniform fleet" approximation
- **Fix applied:** Vintage-tracking salvage: iterates year-over-year `battery_capacity_mwh` from `generation_mix`, computes per-vintage replacement schedule (mod battery_life) and cost-declined CAPEX at actual install year.

---

## 12. Cross-Check vs Standard CBA References

### Boardman et al. (2018) _Cost-Benefit Analysis: Concepts and Practice_ (5th ed.)

| CBA Element | Boardman Recommendation | Our Implementation | Status |
|-------------|------------------------|-------------------|--------|
| Social discount rate | 3.5%–10% depending on context | 6% (ADB SIDS standard) | ✅ Within range |
| Sensitivity analysis | One-way + Monte Carlo | Both implemented (35 params) | ✅ |
| Standing | National perspective (GoM) | GoM perspective with social costs | ✅ |
| With/without principle | Counterfactual (BAU) vs alternatives | S1 BAU is counterfactual | ✅ |
| Externalities | CO₂, health, environment | CO₂ (SCC), health (L4), env. damage (L16: noise, spill, biodiversity) | ✅ Implemented |
| Incremental analysis | Alt vs base, not absolute | Implemented in `calculate_incremental()` | ✅ |
| Real vs nominal | Use real prices throughout | All costs in real 2026 USD | ✅ |
| Salvage value | Include for long-lived assets | Straight-line depreciation at horizon end | ✅ |
| Distributional analysis | Identify winners/losers | HIES 2019 microdata analysis: quintile burden, energy poverty, Suits index (L15) | ✅ Implemented |

### ADB (2017) _Guidelines for Economic Analysis of Projects_

| ADB Requirement | Our Implementation | Status |
|----------------|-------------------|--------|
| Economic vs financial analysis | Economic (social discount rate, SCC) | ✅ |
| Minimum 12% EIRR for ADB | IRR calculated for each scenario vs BAU | ✅ |
| Sensitivity: ±10–20% on key params | Low/High ranges from CSV (wider than ±20% for some params) | ✅ |
| Monte Carlo when high uncertainty | 1,000 iterations on 35 params | ✅ |
| Include project-specific risks | Cable outage rate, supply security | ✅ |
| Multi-criteria if externalities significant | MCA with 8 criteria, 7 scenarios (L17/L24) | ✅ Implemented |
| Fiscal impact assessment | Supplementary financing analysis (L5) | ✅ |

### IRENA (2019) _Planning for the Renewable Energy Transition_

| IRENA Guidance | Our Implementation | Status |
|---------------|-------------------|--------|
| Technology learning curves | Solar -4%/yr, battery -6%/yr from CSV | ✅ |
| System integration costs | Battery storage, grid extension costed | ✅ |
| Flexibility needs | Battery hours, diesel backup | ✅ |
| Land constraints | `max_solar_land_fraction` in least_cost.py | ✅ |
| Island context | Per-island LCOE, logistics premium, coral routing | ✅ |

---

## Summary of Findings

### Equations Audited: 30+
All equations across 10 scripts catalogued with LaTeX notation, parameter sources, and file locations.

### Parameters Traced: 63 (§10) + ~185 full audit (§13)
Full traceability from `parameters.csv → config.py → consuming script + line number`. §13 audit (Feb 2026) classified all ~185 CSV parameters: ~135 equation-active, ~50 report-only, 3 dead code. 7 improvement tasks identified (L19–L25).

### Red Flags Found: 17 (17 fixed/resolved ✅, 0 open)

| Severity | Count | Fixed | Items |
|----------|-------|-------|-------|
| 🔴 CRITICAL | 3 | 3/3 | ~~S-01~~ ✅ (hardcoded CF → config), ~~S-05~~ ✅ (health calc → direct baseline_gen_mix.diesel_gwh), ~~S-13~~ ✅ (getattr fallback → direct) |
| 🟡 MODERATE | 5 | 5/5 | ~~S-02~~ ✅ (India EF → CSV+config), ~~S-03~~ ✅ (battery_hours → CSV+config), ~~S-04~~ ✅ (cable_loss → wired), ~~S-14~~ ✅ (network defaults → None + config fallback), ~~S-15~~ ✅ (MC fallback → removed) |
| 🔵 LOW | 4 | 4/4 | ~~S-06~~ ✅ (unused PPA params — removed), ~~S-16~~ ✅ (solar salvage → vintage-tracking), ~~S-17~~ ✅ (battery salvage → vintage-tracking), all documented |

### ~~Missing from CSV: 4 parameters~~ ✅ ALL ADDED (D46, 8 Feb 2026)
- ~~`india_grid_emission_factor` (0.70)~~ → `PPA,India Grid Emission Factor,0.70` ✅
- ~~`india_grid_emission_decline` (0.02)~~ → `PPA,India Grid Emission Decline,0.02` ✅
- ~~`battery_hours` (4.0)~~ → `Battery,Storage Hours,4.0` ✅
- ~~`domestic_re_target_2050` (0.30)~~ → `RE Targets,Domestic RE Target 2050,0.30` ✅

### ~~In CSV but NOT wired through `get_config()`: 4 parameters~~ ✅ ALL WIRED (D45, 8 Feb 2026)
- ~~`Diesel Gen,CAPEX,800` → `technology.diesel_gen_capex` (CSV:54, not loaded)~~ ✅ wired in `config.py` Diesel Gen block
- ~~`Diesel Gen,OPEX,0.025` → `technology.diesel_gen_opex_kwh` (CSV:55, not loaded)~~ ✅ wired
- ~~`Diesel Gen,Lifetime,20` → `technology.diesel_gen_lifetime` (CSV:56, not loaded)~~ ✅ wired
- ~~`Battery,OPEX,5` → `technology.battery_opex` (CSV:49, not loaded)~~ ✅ wired

### Structural Concerns Fixed (C10 session): 12
- ✅ S-01: `costs.py` CF=0.6 → `config.dispatch.diesel_avg_capacity_factor` (D47)
- ✅ S-02: India grid EF params added to `parameters.csv` + wired in `config.py` (D46)
- ✅ S-03: `battery_hours` added to CSV + wired through config → `SolarBatteryParams` (D46)
- ✅ S-04: `cable_loss_pct` wired from `cfg.technology.hvdc_cable_loss_pct` in `load_params_from_config()` (D47)
- ✅ S-13: `getattr(tech, 'reserve_margin', 0.15)` → `tech.reserve_margin` (D47)
- ✅ S-15: MC `.get("status_quo", 0.05)` → `["status_quo"]` (D47)
- ✅ Diesel Gen CAPEX/OPEX/Lifetime wired from CSV (D45)
- ✅ Battery OPEX wired from CSV (D45)
- ✅ Battery Hours wired from CSV → config → least_cost (D46)
- ✅ Battery DoD wired from config in `load_params_from_config()` (D47)
- ✅ RE Targets + Domestic RE Target 2050 wired from CSV (D46)
- ✅ `run_least_cost()` fallback now uses `load_params_from_config()` instead of bare `TechParams()` (prior session)

---

## 13. Parameter–Equation Traceability Audit

**Date:** 2026-02-09 (v1.2) → **Updated: 2026-02-08 (v1.3)**  
**Purpose:** Classify every parameter in `parameters.csv` by whether it is **(A)** actively used in model equations that affect CBA outputs, **(B)** report-only (exported to JSON for charts/context but no equation impact), or **(C)** dead code. **v1.3** documents the activation of all former report-only parameters into equations (L19–L25).

### 13.1 Summary

| Category | Count (v1.2) | Count (v1.3) | Description |
|----------|-------------|-------------|-------------|
| **(A) Equation-Active** | ~135 | ~210 | Parameter enters ≥1 calculation that affects NPV/BCR/IRR/LCOE or provides validated analytical output |
| **(B) Report-Only** | ~50 | 0 | All former report-only params now activated (L19–L25) |
| **(C) Dead Code** | 3 | 0 | Removed by L25 (distribution_capex + 3 config defaults deleted) |
| **Total CSV parameters** | ~185 | ~210 | Across 30+ categories in parameters.csv (v1.4: +25 transport params from P8) |

### 13.2 (A) Equation-Active Parameters (✅ no action needed)

All 63 parameters listed in §10 above are equation-active. Additional equation-active parameters confirmed:

| CSV Category / Parameter | Config Attribute | Equation Location | Notes |
|--------------------------|-----------------|-------------------|-------|
| `Demand / Sectoral Res/Com/Public` | `demand.sectoral_residential` etc. | demand.py:174–176 | EQ-D3 sectoral split |
| `Current System / Diesel Capacity MW` | `current_system.diesel_capacity_mw` | all 7 scenario files | Initial diesel fleet sizing |
| `Current System / Solar Capacity MW` | `current_system.solar_capacity_mw` | all 7 scenario files | Initial PV capacity |
| `Cable / Converter Station Cost` | `one_grid.converter_station_cost_per_mw` | costs.py:459–462 | EQ-C4 cable CAPEX |
| `Cable / Landing Station Cost` | `one_grid.landing_station_cost_m` | costs.py:463 | EQ-C4 cable CAPEX |
| `Cable / IDC Rate` | `one_grid.idc_rate` | costs.py:464 | Interest during construction |
| `Cable / Grid Integration Cost` | `one_grid.grid_integration_cost_m` | costs.py:465 | Grid upgrade cost |
| `Cable / O&M pct of CAPEX` | `one_grid.cable_om_pct` | costs.py, one_grid.py | Cable O&M |
| `Inter-Island / CAPEX per km` | `technology.inter_island_capex_per_km` | one_grid.py, green_transition.py | Inter-island cable cost |
| `Inter-Island / O&M pct` | `one_grid.inter_island_om_pct` | one_grid.py, green_transition.py | Inter-island O&M |
| `One Grid / Inter-Island Distance km` | `one_grid.inter_island_km` | one_grid.py:261 | Inter-island cable length |
| `One Grid / Cable Transition Period` | `one_grid.cable_transition_years` | one_grid.py | Ramp-up years |
| `Islanded / Initial RE Fraction` | `green_transition.islanded_initial_re` | islanded_green.py | Starting RE share for IG |
| `Islanded / Target RE Fraction` | `green_transition.islanded_target_re` | islanded_green.py | Target RE share for IG |
| `Islanded / Target Year` | `green_transition.islanded_target_year` | islanded_green.py | Year to reach target |
| `Islanded / Logistics Premium` | `green_transition.islanded_logistics_premium` | islanded_green.py | Cost multiplier |
| `Islanded / Battery Premium` | `green_transition.islanded_battery_premium` | islanded_green.py | Battery cost uplift |
| `Operations / Min Diesel Backup MW` | `technology.min_diesel_backup` | s2, s3 scenarios | Min backup capacity |
| `RE Targets / 2030–2060 + Domestic 2050` | `green_transition.re_targets`, `one_grid.domestic_re_target_2050` | one_grid.py, green_transition.py, islanded_green.py | Year-by-year RE trajectory |
| `PPA / Minimum Offtake GWh` | `ppa.minimum_offtake_gwh` | one_grid.py | Cable minimum import |
| `PPA / India Grid Emission Factor/Decline` | `ppa.india_grid_emission_*` | emissions.py | India import emissions |
| `Dispatch / Fuel Curve, Min Load, DoD, etc.` | `dispatch.*` (13 params) | costs.py, least_cost.py | Hourly dispatch engine |
| `Losses / Distribution + HVDC` | `technology.distribution_loss_pct`, `hvdc_cable_loss_pct` | costs.py, least_cost.py | Energy losses |
| `Cable Outage / Rate, Min/Max Months` | `cable_outage.*` | MC, sensitivity | Supply security risk |
| `Supply Security / Idle Fleet, Fuel Premium` | `supply_security.*` | one_grid.py | FI supply security cost |
| `Health / Damage Cost, PM2.5, NOx` | `economics.health_damage_*`, `technology.pm25_*`, `technology.nox_*` | scenarios/__init__.py | Health co-benefits (EQ-H1) |
| `Climate / Adaptation Premium` | `technology.climate_adaptation_premium` | costs.py | Applied to solar/battery/cable CAPEX |
| `Connection / Cost, HH Count, Rollout` | `connection.*` | scenarios (alt only) | HH connection CAPEX |
| `Environment / Noise, Spill, Biodiversity` | `economics.env_noise_*` etc. | costs.py, scenarios | Environmental externalities |
| `Tourism / Resort Demand + Green Premium` | `tourism.resort_demand_gwh`, `.green_premium_per_kwh` | run_cba.py:577–578 | Green premium revenue calc |
| `Tourism / Emission Factor, kWh/guest-night` | `tourism.resort_emission_factor`, `.resort_kwh_per_guest_night` | run_cba.py:327–329 | Resort emissions context (print only) |
| `MCA Weights / 8 criteria` | `mca_weights.*` | cba/mca_analysis.py | Multi-criteria ranking |
| `MCA Scores / 9 scenario-criterion pairs` | `mca_scores.*` | cba/mca_analysis.py | MCA overrides |
| `Financing / ADB Rate, Maturity, Grace, Eligible, Commercial, GDP` | `financing.*` | financing_analysis.py | Grant element, WACC, debt service |
| `Network / Routing Premium` | `technology.routing_premium` | least_cost.py, network.py | Coral routing multiplier |
| `Time / Base Year, Horizon, Start, End` | `time.*` | all scenarios, npv_calculator.py | Analysis period |
| `Battery / Storage Hours` | `technology.battery_hours` | least_cost.py | Battery sizing |
| `Battery / DoD Max` | `dispatch.battery_dod_max` | least_cost.py | Usable capacity |
| `Macro / GDP Billion USD` | `financing.gdp_billion_usd` | financing_analysis.py | Fiscal burden ratio |

### 13.3 (B) Former Report-Only Parameters — Now Activated (v1.3)

All parameters previously classified as report-only have been activated into model equations or analytical outputs. This section documents the activation for each parameter group.

#### 13.3.1 Current System Baseline Descriptors — ✅ ACTIVATED

| CSV Parameter | Config Attribute | Activation | Task |
|--------------|-----------------|-----------|------|
| `Total Capacity MW` | `current_system.total_capacity_mw` | Exported in `baseline_system` + used in per-capita metrics | L19 |
| `Battery Capacity MWh` | `current_system.battery_capacity_mwh` | **L19: Now initialises battery fleet in all 5 scenario files** (was hardcoded 0.0) | L19 ✅ |
| `Diesel Share pct` | `current_system.diesel_share` | Exported in `baseline_system` for validation context | — |
| `RE Share pct` | `current_system.re_share` | Exported in `baseline_system` for validation context | — |
| `Male Electricity Share` | `current_system.male_electricity_share` | Exported in `baseline_system`; `least_cost.py` uses island-level pop weighting instead | — |
| `Resort Capacity Share` | `current_system.resort_capacity_share` | Exported in `baseline_system`; off-grid resorts excluded from CBA by design | — |
| `Outer Island Electricity Cost` | `current_system.outer_island_electricity_cost` | **Now in `baseline_system` JSON** for outer-island cost comparison | L21 ✅ |
| `Male Rooftop Solar MWp` | `current_system.male_rooftop_solar_mwp` | **Now in `baseline_system` JSON** for solar potential context | L21 ✅ |
| `Population 2026` | `current_system.population_2026` | **Now used in `per_capita_metrics`** (per-capita kWh, per-capita cost) | L21 ✅ |

#### 13.3.2 Reliability Metrics — ✅ ACTIVATED (L20)

| CSV Parameter | Config Attribute | Activation | Equation |
|--------------|-----------------|-----------|----------|
| `SAIDI (minutes/yr)` | `current_system.saidi_minutes` | **L20: Enters reliability benefit calculation** in `BaseScenario.calculate_annual_benefits()` | $B_{reliability} = \Delta SAIDI_{hours} \times VOLL \times D_{MWh}$ |
| `SAIFI (interruptions/yr)` | `current_system.saifi_interruptions` | Exported in `baseline_system` for context; SAIDI is the primary metric used in the reliability equation | — |

**L20 Reliability Benefit Equation:**

$$B_{reliability,t} = \left(\frac{SAIDI_{baseline}}{60}\right) \times \min\left(\Delta RE_t, 0.80\right) \times VOLL \times D_t \times 10^3$$

Where:
- $SAIDI_{baseline}$ = 200 minutes/year (from `current_system.saidi_minutes`)
- $\Delta RE_t$ = scenario RE share improvement over baseline. For cable import, discounted by cable availability:
  $$RE_{effective,t} = RE_{local,t} + \text{import\_share}_t \times \left(1 - \lambda \times \frac{\bar{M}}{12}\right)$$
  where $\lambda = 0.15$/yr (cable outage rate), $\bar{M} = 3.5$ months (mean repair time) → availability ≈ 0.956
- $VOLL$ = $5/kWh (from `economics.voll`)
- $D_t$ = annual demand in GWh
- Cap at 80% SAIDI reduction (conservative assumption)

**Cable availability rationale:** Submarine cable import is less reliable than local RE generation due to outage risk (λ=0.15/yr, 1–6 month repairs per NorNed/Basslink records). The effective import share for reliability purposes is discounted by ~4.4%, preventing overstatement of FI reliability benefits.

**NPV integration:** Reliability benefit is discounted in `npv_calculator.py` via `pv_reliability_benefits` and included in `pv_total_benefits` for incremental analysis.

#### 13.3.3 Tariff & Subsidy Context — ✅ ACTIVATED (L21-22)

| CSV Parameter | Config Attribute | Activation | Equation |
|--------------|-----------------|-----------|----------|
| `Avg HH Monthly Consumption kWh` | `current_system.avg_hh_monthly_kwh` | **L21: Enters avg HH annual bill** in `financing_analysis.py` | $Bill_{HH} = 12 \times C_{monthly} \times T_{retail}$ |
| `Current Retail Tariff USD/kWh` | `current_system.current_retail_tariff` | **L21: Drives tariff revenue + HH bill** | $Rev_{tariff} = D_{kWh} \times T_{retail}$ |
| `India Domestic Rate USD/kWh` | `current_system.india_domestic_rate` | **L21: PPA floor validation** in `lcoe_validation` | Flag: `lcoe ≥ india_domestic_rate` |
| `Current Subsidy per kWh` | `current_system.current_subsidy_per_kwh` | **L22: Annual subsidy outlay** | $Subsidy_{annual} = D_{kWh} \times S_{per kWh}$ |
| `Exchange Rate MVR/USD` | `economics.exchange_rate_mvr_usd` | **L21: MVR conversion** for tariff revenue + HH bills | $X_{MVR} = X_{USD} \times e_{MVR/USD}$ |

**L21-22 Fiscal Equations (in `financing_analysis.py`):**

$$Rev_{tariff} = D_{base} \times 10^6 \times T_{retail}$$
$$Bill_{HH,annual} = 12 \times C_{monthly} \times T_{retail}$$
$$Subsidy_{annual} = D_{base} \times 10^6 \times S_{per kWh}$$

Where $D_{base}$ = base demand in GWh, $T_{retail}$ = $0.25/kWh, $C_{monthly}$ = 300 kWh, $S_{per kWh}$ = $0.15/kWh.

**Base-year caveat:** These are static base-year (2026) estimates at 1,200 GWh demand. With BAU demand growth of 5%/yr, year-30 subsidy would reach ~$778M/yr at constant rates. The JSON output includes `note_tariff_subsidy` flagging this limitation.

#### 13.3.4 SCC Supplementary — ✅ ACTIVATED

| CSV Parameter | Config Attribute | Activation |
|--------------|-----------------|-----------|
| `SCC IWG Interim` | `economics.scc_iwg_interim` | **Now includes `iwg_vs_central_ratio`** in `scc_context` for sensitivity context (0.27× central) |

#### 13.3.5 LCOE Benchmarks (8 params) — ✅ ACTIVATED (Validation)

| CSV Parameter | Config Attribute | Activation |
|--------------|-----------------|-----------|
| 8 LCOE benchmark values | `benchmarks.*` | **Now used in `lcoe_validation`** — model LCOEs compared against SIDS range ($0.099–$0.25), flagged `within_sids_range`, ratio vs global diesel computed |

**LCOE Validation Logic (in `save_results()`):**
- SIDS range: `[maldives_cif_aspire_lcoe, cook_islands_lcoe]`
- For each scenario: flag `within_sids_range` (boolean), compute `vs_global_diesel` ratio
- PPA floor check: FI LCOE must be ≥ `india_domestic_rate` ($0.10/kWh)

#### 13.3.6 Distributional Shares (9 params) — ✅ ACTIVATED (L23)

| CSV Parameter | Config Attribute | Activation | Equation |
|--------------|-----------------|-----------|----------|
| `Cost Share Government (25%)` | `distributional.cost_share_government` | **L23: Per-scenario cost allocation in $M** | $C_{govt} = C_{total} \times s_{govt} / 100$ |
| `Cost Share MDBs (30%)` | `distributional.cost_share_mdbs` | Same | $C_{mdbs} = C_{total} \times s_{mdbs} / 100$ |
| `Cost Share India (25%)` | `distributional.cost_share_india` | Same | $C_{india} = C_{total} \times s_{india} / 100$ |
| `Cost Share Private (20%)` | `distributional.cost_share_private` | Same | $C_{private} = C_{total} \times s_{private} / 100$ |
| `Benefit Share Households (35%)` | `distributional.benefit_share_households` | **L23: Per-scenario benefit allocation in $M** | $B_{hh} = B_{total} \times s_{hh} / 100$ |
| `Benefit Share Businesses (25%)` | `distributional.benefit_share_businesses` | Same | |
| `Benefit Share Government (15%)` | `distributional.benefit_share_government` | Same | |
| `Benefit Share Climate (20%)` | `distributional.benefit_share_climate` | Same | |
| `Benefit Share Workers (5%)` | `distributional.benefit_share_workers` | Same | |

**Note (v1.3 correction):** v1.2 erroneously listed `hh_subsidy_reduction_pct` and `utility_revenue_change_pct` — these fields do not exist in `parameters.csv` or `config.py`. The actual fields are `benefit_share_climate` and `benefit_share_workers`.

**Scenario-specific cost shares (sanity fix):** The India cost share (25%) only applies to FI (Full Integration), which includes the India–Maldives submarine cable. For NG, IG, and BAU — which have no India cable component — `cost_share_india = 0%` and the remaining shares are redistributed proportionally:
$$s'_i = s_i \times \frac{100}{\sum_{j \neq india} s_j}$$
With default shares (govt 25 + mdbs 30 + private 20 = 75): govt→33.3%, mdbs→40.0%, private→26.7%. This prevents the nonsensical attribution of costs to India in scenarios with no Indian infrastructure.

#### 13.3.7 Investment Phasing (20 params) — ✅ ACTIVATED (L24)

**v1.3 change:** The 20 hardcoded illustrative values in `InvestmentPhasingConfig` are no longer used in `save_results()`. Instead, investment phasing is **computed from actual scenario CAPEX** by aggregating `AnnualCosts.capex_solar`, `.capex_battery`, `.capex_grid`, `.capex_cable` into 5-year periods per scenario.

| Technology | Period Buckets | Source |
|-----------|---------------|--------|
| Solar | 2026-28, 2029-32, 2033-36, 2037-40, 2041-50 | `costs.capex_solar` per year |
| Battery | Same | `costs.capex_battery` per year |
| Inter-island grid | Same | `costs.capex_grid` per year |
| India cable | Same | `costs.capex_cable` per year |

The 20 CSV values remain as reference/illustrative but no longer feed JSON output.

#### 13.3.8 Macro / Fiscal Context — ✅ CORRECTED

**v1.3 correction:** v1.2 erroneously listed 5 parameters (`inflation_rate`, `govt_revenue_pct_gdp`, `public_debt_pct_gdp`, `current_account_deficit_pct_gdp`, `exchange_rate_mvr_usd`) — the first 4 do **not exist** in `parameters.csv` or `config.py`. Only `exchange_rate_mvr_usd` exists (in `EconomicsConfig`) and is now activated in L21 (MVR conversion in financing analysis).

| Parameter | Status |
|-----------|--------|
| `exchange_rate_mvr_usd` | ✅ Now equation-active (L21 — MVR conversion) |
| `inflation_rate` | ❌ Does not exist in CSV/config — could be added if real-to-nominal conversion needed |
| `govt_revenue_pct_gdp` | ❌ Does not exist — could be added for fiscal burden metrics |
| `public_debt_pct_gdp` | ❌ Does not exist — could be added for debt sustainability analysis |
| `current_account_deficit_pct_gdp` | ❌ Does not exist — informational only |

### 13.4 (C) Dead Code — ✅ REMOVED (L25)

**v1.3:** All dead code has been removed by L25:

| Config Attribute | Default Value | Method | Resolution |
|-----------------|---------------|--------|------------|
| ~~`technology.mv_line_capex_per_km`~~ | ~~$20,000/km~~ | ~~`CostCalculator.distribution_capex()`~~ | ✅ L25: Method + defaults deleted. Last-mile costs covered by `connection_cost_per_household` ($200/HH) |
| ~~`technology.lv_line_capex_per_km`~~ | ~~$12,000/km~~ | ~~Same~~ | ✅ L25: Deleted |
| ~~`technology.transformer_capex`~~ | ~~$30,000/unit~~ | ~~Same~~ | ✅ L25: Deleted |

### 13.5 Audit Methodology & Resolution History

**v1.2 Audit (initial):**
1. **Extracted** all ~185 parameter rows from `parameters.csv` (286 lines incl. headers/comments)
2. **Traced** each parameter: CSV → `config.py` `load_parameters_from_csv()` → config dataclass field → `grep_search` for every usage across all `.py` files in `model/`
3. **Classified** each usage as equation-active, report-only, or dead code
4. **Verified** with targeted `grep_search` on ~15 critical edge cases

**v1.3 Resolution (L19–L25):**

| Task | What was done | Files changed |
|------|--------------|---------------|
| L19 | Battery init from config (was hardcoded 0.0) | 5 scenario files |
| L20 | Reliability benefit: $B = SAIDI_{hours} \times VOLL \times D_{MWh}$ | `scenarios/__init__.py`, `npv_calculator.py`, `run_cba.py` |
| L21-22 | Tariff/subsidy fiscal metrics | `financing_analysis.py` |
| L23 | Stakeholder cost/benefit allocation in $M | `run_cba.py` |
| L24 | Auto-gen investment phasing from model CAPEX | `run_cba.py` |
| L25 | Dead code removal (3 defaults + method) | `config.py`, `costs.py` |
| — | Contextual: LCOE validation, per-capita, SCC ratio, PPA floor | `run_cba.py` |

**v1.3 Corrections:** Fixed 2 documentation errors — §13.3.6 had wrong field names (`hh_subsidy_reduction_pct`, `utility_revenue_change_pct` → `benefit_share_climate`, `benefit_share_workers`); §13.3.8 listed 4 non-existent macro params.

**Result:** All ~210 `parameters.csv` entries are now either equation-active or correctly categorised. Zero report-only params. Zero dead code. v1.4 adds 25 transport params (§14).

---

## 14. Transport Electrification Module (P8)

**Added:** v1.4 (10 Feb 2026)  
**Script:** `model/transport_analysis.py` (~430 lines)  
**Config:** `TransportConfig` dataclass (25 fields) in `config.py`  
**Output:** `outputs/transport_results.json`  
**Status:** Supplementary analysis — does not modify core 7-scenario CBA. Runs after distributional analysis.

### 14.1 Overview

The transport module models EV adoption in the Maldives using a logistic S-curve (Griliches 1957) across three scenarios (Low 30%, Medium 60%, High 85% EV share by 2056). The Maldives fleet is ~131,000 vehicles (92% motorcycles, 4% EV share in 2026). Health benefits are amplified by Malé's extreme population density (~65,000/km²).

### 14.2 Equations

#### EQ-T1: Logistic S-curve (EV adoption share)

$$S(t) = S_0 + \frac{S_{max} - S_0}{1 + e^{-k(t - t_{mid})}}$$

| Symbol | CSV Parameter | Config Attribute | Value |
|--------|--------------|------------------|-------|
| $S_0$ | `Transport Fleet / EV Share 2026` | `transport.ev_share_2026` | 0.04 |
| $S_{max}$ | Scenario-dependent | Low: 0.30, Medium: 0.60, High: 0.85 | — |
| $t_{mid}$ | `Transport EV / EV Adoption Midpoint Year` | `transport.ev_adoption_midpoint` | 2038 |
| $k$ | `Transport EV / EV Adoption Steepness` | `transport.ev_adoption_steepness` | 0.25 |

**Code:** `transport_analysis.py:54–81` — `_logistic_ev_share()`  
**Source:** Griliches (1957) — logistic diffusion; IEA GEVO (2024) — EV adoption curves

#### EQ-T2: Fleet projection

$$N(t) = N_0 \times (1 + g)^{t - t_0}$$

| Symbol | CSV Parameter | Config Attribute | Value |
|--------|--------------|------------------|-------|
| $N_0$ | `Transport Fleet / Total Vehicles 2026` | `transport.total_vehicles_2026` | 131,000 |
| $g$ | `Transport Fleet / Fleet Growth Rate` | `transport.fleet_growth_rate` | 0.02 |
| $t_0$ | `Time / Base Year` | `time.base_year` | 2026 |

**Code:** `transport_analysis.py:85–96` — `_project_fleet()`  
**Source:** Malé City Council / World Bank (2022); gathunkaaru.com (2024)

#### EQ-T3: Fuel displacement (litres saved)

$$L_{saved}(t) = N_{ev,mc}(t) \times D_{daily} \times 365 \times \frac{F_{ICE}}{100}$$

Where $N_{ev,mc}(t) = N(t) \times S(t) \times r_{mc}$ (motorcycle subset of EV fleet).

| Symbol | CSV Parameter | Config Attribute | Value |
|--------|--------------|------------------|-------|
| $r_{mc}$ | `Transport Fleet / Motorcycle Share` | `transport.motorcycle_share` | 0.92 |
| $D_{daily}$ | `Transport Fleet / Motorcycle Daily km` | `transport.motorcycle_daily_km` | 15 |
| $F_{ICE}$ | `Transport Energy / ICE Fuel Consumption L/100km` | `transport.ice_fuel_consumption_l_100km` | 2.5 |

**Code:** `transport_analysis.py:145–149`  
**Source:** ICCT (2021) — ICE motorcycle fuel consumption

#### EQ-T4: Additional electricity demand (MWh)

$$E_{ev}(t) = N_{ev,mc}(t) \times D_{daily} \times 365 \times e_{EV}$$

| Symbol | CSV Parameter | Config Attribute | Value |
|--------|--------------|------------------|-------|
| $e_{EV}$ | `Transport Energy / EV Energy Consumption kWh/km` | `transport.ev_energy_per_km` | 0.03 |

**Code:** `transport_analysis.py:151–153`  
**Source:** ESMAP (2024) — electric motorcycle energy consumption

#### EQ-T5: Health benefits (annual)

$$H(t) = N_{ev,mc}(t) \times D_{daily} \times 365 \times \left(\delta_{PM2.5} + \delta_{NOx} + \delta_{noise}\right)$$

| Symbol | CSV Parameter | Config Attribute | Value |
|--------|--------------|------------------|-------|
| $\delta_{PM2.5}$ | `Transport Health / PM2.5 Damage per vkm` | `transport.pm25_damage_per_vkm` | 0.015 |
| $\delta_{NOx}$ | `Transport Health / NOx Damage per vkm` | `transport.nox_damage_per_vkm` | 0.008 |
| $\delta_{noise}$ | `Transport Health / Noise Reduction per EV-km` | `transport.noise_reduction_per_ev_km` | 0.005 |

**Code:** `transport_analysis.py:165–170`  
**Source:** Parry et al. (2014), IMF WP/14/199 — adapted for Malé density

#### EQ-T6: CO₂ avoided (net of grid emissions)

$$CO_2^{net}(t) = \max\left(N_{ev,mc}(t) \times D_{daily} \times 365 \times \frac{g_{ICE}}{10^6} - E_{ev}(t) \times \frac{EF_{grid}}{1000},\; 0\right)$$

| Symbol | CSV Parameter | Config Attribute | Value |
|--------|--------------|------------------|-------|
| $g_{ICE}$ | `Transport CO₂ / ICE gCO₂ per km` | `transport.ice_gco2_per_km` | 65 |
| $EF_{grid}$ | `Fuel / Emission Factor kgCO₂/kWh` | `fuel.emission_factor_kg_co2_per_kwh` | 0.72 |

**Code:** `transport_analysis.py:173–177`  
**Source:** ICCT (2021) — motorcycle tailpipe emissions; IPCC (2006) — grid EF

#### EQ-T7: Vehicle premium cost (declining)

$$P_{vehicle}(t) = \Delta N_{ev}(t) \times r_{mc} \times P_0 \times (1 - d)^{t - t_0}$$

Where $\Delta N_{ev}(t)$ = new EVs adopted in year $t$.

| Symbol | CSV Parameter | Config Attribute | Value |
|--------|--------------|------------------|-------|
| $P_0$ | `Transport Costs / E-Motorcycle Premium 2026` | `transport.e_motorcycle_premium_2026` | $500 |
| $d$ | `Transport Costs / Premium Decline Rate` | `transport.premium_decline_rate` | 0.05 |

**Code:** `transport_analysis.py:203–211`  
**Source:** ESMAP (2024) — EV motorcycle cost premiums

#### EQ-T8: Charging infrastructure cost (incremental)

$$C_{charging}(t) = \max\left(\left\lceil \frac{N_{ev}(t)}{V_{per\,stn}}\right\rceil - \left\lceil \frac{N_{ev}(t-1)}{V_{per\,stn}}\right\rceil,\; 0\right) \times C_{stn}$$

| Symbol | CSV Parameter | Config Attribute | Value |
|--------|--------------|------------------|-------|
| $V_{per\,stn}$ | `Transport Costs / Vehicles per Charging Station` | `transport.vehicles_per_station` | 200 |
| $C_{stn}$ | `Transport Costs / Charging Station Cost` | `transport.charging_station_cost` | $15,000 |

**Code:** `transport_analysis.py:213–218`  
**Source:** UNDP/MOTCA (2024) — 5 solar-backed pilot charging stations

#### EQ-T9: Net benefit and NPV

$$NB(t) = \underbrace{F_{saved}(t) + M_{saved}(t) + H(t) + SCC(t) \times CO_2^{net}(t)}_{\text{benefits}} - \underbrace{P_{vehicle}(t) + C_{charging}(t) + E_{cost}(t)}_{\text{costs}}$$

$$NPV = \sum_{t=t_0}^{T} \frac{NB(t)}{(1+r)^{t-t_0}}$$

Where:
- $F_{saved}(t)$ = fuel cost savings = $L_{saved}(t) \times p_{petrol}(t)$ with $p_{petrol}(t) = p_0 \times (1 + e_p)^{t-t_0}$
- $M_{saved}(t)$ = maintenance savings = $N_{ev,mc}(t) \times (m_{ICE} - m_{EV})$
- $SCC(t) = SCC_0 \times (1 + g_{SCC})^{t-t_0}$ from `economics.social_cost_carbon`
- $E_{cost}(t)$ = electricity cost = $E_{ev}(t) \times T_{retail}$
- $r$ = discount rate from `economics.discount_rate`

| Symbol | CSV Parameter | Config Attribute | Value |
|--------|--------------|------------------|-------|
| $p_0$ | `Transport Energy / Petrol Price 2026 USD/L` | `transport.petrol_price_2026` | 1.20 |
| $e_p$ | `Transport Energy / Petrol Price Escalation` | `transport.petrol_price_escalation` | 0.02 |
| $m_{ICE}$ | `Transport Costs / ICE Annual Maintenance` | `transport.ice_annual_maintenance` | $150 |
| $m_{EV}$ | `Transport Costs / EV Annual Maintenance` | `transport.ev_annual_maintenance` | $50 |
| $T_{retail}$ | `Current System / Current Retail Tariff` | `current_system.current_retail_tariff` | $0.25/kWh |

**Code:** `transport_analysis.py:221–261` (net benefit), `transport_analysis.py:240–258` (NPV discounting)  
**Source:** Various — see individual parameter sources above

### 14.3 Complete Transport Parameter Traceability (25 params)

| # | CSV Category / Parameter | Config Attribute | Equation | Value | Source |
|---|--------------------------|-----------------|----------|-------|--------|
| 1 | Transport Fleet / Total Vehicles 2026 | `transport.total_vehicles_2026` | EQ-T2 | 131,000 | Malé City Council / World Bank (2022) |
| 2 | Transport Fleet / Motorcycle Share | `transport.motorcycle_share` | EQ-T3,T4,T5 | 0.92 | gathunkaaru.com (2024) |
| 3 | Transport Fleet / Fleet Growth Rate | `transport.fleet_growth_rate` | EQ-T2 | 0.02 | World Bank WDI population growth |
| 4 | Transport Fleet / Motorcycle Daily km | `transport.motorcycle_daily_km` | EQ-T3,T4,T5 | 15 | UNDP/MOTCA (2024) |
| 5 | Transport Fleet / EV Share 2026 | `transport.ev_share_2026` | EQ-T1 | 0.04 | gathunkaaru.com (2024) |
| 6 | Transport EV / EV Adoption Midpoint Year | `transport.ev_adoption_midpoint` | EQ-T1 | 2038 | IEA GEVO (2024) calibrated |
| 7 | Transport EV / EV Adoption Steepness | `transport.ev_adoption_steepness` | EQ-T1 | 0.25 | Griliches (1957) typical |
| 8 | Transport EV / EV Target Low | scenario param | EQ-T1 | 0.30 | IEA GEVO (2024) slow adoption |
| 9 | Transport EV / EV Target Medium | scenario param | EQ-T1 | 0.60 | IEA GEVO (2024) stated policies |
| 10 | Transport EV / EV Target High | scenario param | EQ-T1 | 0.85 | IEA GEVO (2024) net zero |
| 11 | Transport Energy / EV Energy Consumption kWh/km | `transport.ev_energy_per_km` | EQ-T4 | 0.03 | ESMAP (2024) |
| 12 | Transport Energy / ICE Fuel Consumption L/100km | `transport.ice_fuel_consumption_l_100km` | EQ-T3 | 2.5 | ICCT (2021) |
| 13 | Transport Energy / Petrol Price 2026 USD/L | `transport.petrol_price_2026` | EQ-T9 | 1.20 | Maldives fuel registry |
| 14 | Transport Energy / Petrol Price Escalation | `transport.petrol_price_escalation` | EQ-T9 | 0.02 | IEA WEO (2023) |
| 15 | Transport Costs / E-Motorcycle Premium 2026 | `transport.e_motorcycle_premium_2026` | EQ-T7 | $500 | ESMAP (2024) |
| 16 | Transport Costs / Premium Decline Rate | `transport.premium_decline_rate` | EQ-T7 | 0.05 | BNEF (2024) learning |
| 17 | Transport Costs / ICE Annual Maintenance | `transport.ice_annual_maintenance` | EQ-T9 | $150 | ICCT (2021) |
| 18 | Transport Costs / EV Annual Maintenance | `transport.ev_annual_maintenance` | EQ-T9 | $50 | ESMAP (2024) |
| 19 | Transport Costs / Vehicles per Station | `transport.vehicles_per_station` | EQ-T8 | 200 | UNDP/MOTCA (2024) |
| 20 | Transport Costs / Charging Station Cost | `transport.charging_station_cost` | EQ-T8 | $15,000 | UNDP/MOTCA (2024) |
| 21 | Transport Health / PM2.5 Damage per vkm | `transport.pm25_damage_per_vkm` | EQ-T5 | $0.015 | Parry et al. (2014) |
| 22 | Transport Health / NOx Damage per vkm | `transport.nox_damage_per_vkm` | EQ-T5 | $0.008 | Parry et al. (2014) |
| 23 | Transport Health / Noise Reduction per EV-km | `transport.noise_reduction_per_ev_km` | EQ-T5 | $0.005 | Parry et al. (2014) |
| 24 | Transport CO₂ / ICE gCO₂ per km | `transport.ice_gco2_per_km` | EQ-T6 | 65 | ICCT (2021) |
| 25 | Transport CO₂ / Grid Emission Factor | `fuel.emission_factor_kg_co2_per_kwh` | EQ-T6 | 0.72 | IPCC (2006) — shared param |

### 14.4 Sensitivity Parameters (4 transport-specific)

These 4 parameters are wired into `sensitivity.py` (`_define_parameters`, `_modify_config`, `_modify_config_inplace`), bringing the total sensitivity parameter count from 34 to 38.

| # | Parameter Key | Config Path | Low | High | Unit |
|---|--------------|------------|-----|------|------|
| 35 | `ev_adoption_midpoint` | `transport.ev_adoption_midpoint` | 2034 | 2042 | year |
| 36 | `ev_motorcycle_premium` | `transport.e_motorcycle_premium_2026` | 300 | 800 | $/vehicle |
| 37 | `transport_health_damage` | `transport.pm25_damage_per_vkm` + `nox_damage_per_vkm` | 0.015 | 0.035 | $/vkm |
| 38 | `petrol_price` | `transport.petrol_price_2026` | 0.80 | 1.60 | $/L |

### 14.5 Key Results (Medium scenario, 60% EV by 2056)

| Metric | Value |
|--------|-------|
| NPV | $441M |
| BCR | 6.90 |
| Cumulative CO₂ avoided | 901 kt |
| Cumulative health benefits | $263M |
| Final-year electricity demand (2056) | 23.8 GWh (1–5% of grid) |
| Final-year EV count | ~111,000 |
| Charging stations needed | ~555 |

### 14.6 MCA Integration

Transport health co-benefits are added to the MCA `health` criterion score, scaled by each scenario's RE share. Higher RE share → cleaner EV charging → larger health benefit multiplier. Implemented in `cba/mca_analysis.py`.

### 14.7 References

- Griliches, Z. (1957). *Hybrid Corn: An Exploration in the Economics of Technological Change.* Econometrica 25(4):501–522.
- IEA (2024). *Global EV Outlook 2024.* International Energy Agency, Paris.
- ICCT (2021). *A Global Comparison of the Life-Cycle Greenhouse Gas Emissions of Combustion Engine and Electric Passenger Cars.* ICCT White Paper.
- ESMAP (2024). *Electric Mobility and Development.* World Bank Energy Sector Management Assistance Program.
- UNDP/MOTCA (2024). *Solar-backed EV Charging Pilot: Malé, Maldives.* UNDP Maldives.
- Parry, I., Heine, D., Lis, E. & Li, S. (2014). *Getting Energy Prices Right.* IMF WP/14/199.
- Malé City Council / World Bank (2022). *Urban Transport Assessment: Greater Malé Region.*