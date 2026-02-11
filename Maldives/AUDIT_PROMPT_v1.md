# AUDIT PROMPT — Maldives Energy CBA Model: Code, Equations, Parameters & Wiring

## Your Role

You are an expert energy economist and software auditor. Your job is to **systematically audit all Python code** in this project for correctness of equations, parameter wiring, unit consistency, cross-scenario consistency, and silent bugs. **Do NOT audit text/documentation/report files** — only `.py` source code and `parameters.csv`.

## Project Summary

This is a Cost-Benefit Analysis model comparing 7 energy transition scenarios for the Maldives (S1 BAU diesel, S2 India submarine cable, S3 National Grid, S4 Islanded Green, S5 Near-Shore Solar, S6 Maximum RE, S7 LNG Transition) over 2026–2056. The architecture is:

```
parameters.csv  →  config.py (load_parameters_from_csv)  →  get_config()  →  model code
```

Every numeric parameter must flow from `parameters.csv` → `config.py` dataclass → `get_config()` in consuming module. No hardcoded numeric literals except mathematical constants (π, 8760, 1000).

## Codebase Inventory (14,228 lines across 26 .py files)

### Core Engine
| File | Lines | Purpose |
|------|-------|---------|
| `model/config.py` | 1,961 | 23 dataclasses (314 fields), `load_parameters_from_csv()`, `get_config()` |
| `model/parameters.csv` | ~402 rows | Single source of truth: Category, Parameter, Value, Low, High, Unit, Source, Notes |
| `model/demand.py` | 361 | Compound demand growth, sectoral split, price elasticity, Malé share trajectory |
| `model/costs.py` | 869 | CAPEX/OPEX/generation calculations, learning curves, climate adjustment, LCOE |
| `model/emissions.py` | 271 | CO₂ emissions, SCC monetisation, India grid factor |
| `model/dispatch.py` | 404 | Hourly PV-diesel-battery dispatch simulation |

### Scenarios (each implements `calculate_annual_data()`, `calculate_generation_mix()`, `calculate_costs()`)
| File | Lines | Scenario |
|------|-------|----------|
| `model/scenarios/__init__.py` | 525 | Base classes: `GenerationMix`, `AnnualCosts`, `AnnualBenefits`, `BaseScenario` |
| `model/scenarios/status_quo.py` | 196 | S1 BAU (diesel-only) |
| `model/scenarios/one_grid.py` | 420 | S2 Full Integration (India cable + domestic RE) |
| `model/scenarios/green_transition.py` | 379 | S3 National Grid (inter-island + RE ramp) |
| `model/scenarios/islanded_green.py` | 319 | S4 Islanded Green (per-island hybrid mini-grids) |
| `model/scenarios/nearshore_solar.py` | 366 | S5 Near-Shore Solar (uninhabited island solar farms) |
| `model/scenarios/maximum_re.py` | 411 | S6 Maximum RE (floating solar + near-shore) |
| `model/scenarios/lng_transition.py` | 454 | S7 LNG Transition (140 MW Gulhifalhu plant) |

### CBA Engine
| File | Lines | Purpose |
|------|-------|---------|
| `model/cba/npv_calculator.py` | 817 | NPV, BCR, IRR, salvage value, incremental analysis, declining discount rate |
| `model/cba/sensitivity.py` | 985 | 38-parameter sensitivity engine, Monte Carlo, switching values |
| `model/cba/mca_analysis.py` | 513 | Multi-Criteria Analysis (8 criteria, weighted scoring) |

### Supplementary Modules
| File | Lines | Purpose |
|------|-------|---------|
| `model/run_cba.py` | 1,238 | Main entry point — runs all scenarios, outputs JSON |
| `model/run_sensitivity.py` | 647 | One-way sensitivity analysis driver |
| `model/run_monte_carlo.py` | 376 | Monte Carlo simulation driver (1000 iterations) |
| `model/run_multi_horizon.py` | 369 | Multi-horizon analysis (20/30/50 year) |
| `model/financing_analysis.py` | 491 | Grant element, WACC, debt service schedules |
| `model/distributional_analysis.py` | 1,094 | HIES 2019 microdata: quintile burden, energy poverty, Suits index |
| `model/transport_analysis.py` | 399 | EV adoption logistic S-curve, health benefits, fuel displacement |
| `model/sanity_checks.py` | 631 | 47 automated benchmark checks |
| `model/least_cost.py` | 912 | Per-island LCOE + technology assignment |
| `model/network.py` | 506 | Inter-island distance matrix, MST, routing |
| `model/grid_vs_standalone.py` | 279 | Grid-vs-standalone LCOE comparison |

## What To Audit (Checklist)

For **every** `.py` file, check the following systematically. Organise findings by severity: 🔴 CRITICAL (affects NPV/BCR/LCOE results), 🟡 MODERATE (could distort results under some conditions), 🔵 LOW (code quality, dead code, minor issues).

### A. HARDCODED VALUES (Zero Tolerance)

Search for **any numeric literal** in `.py` files that should come from `parameters.csv`. Allowed exceptions: mathematical constants (π, 8760 hours/year, 1000 kg/tonne, 1e6, 12 months, 365 days, 100 for percentages), array indices, loop counters.

**Red flags:**
- `solar_capex = 1500` or any dollar amount as literal
- `discount_rate = 0.06` or any rate as literal
- `loss = 0.11` or any loss percentage as literal
- `emission_factor = 0.72` as literal outside config.py
- Any `getattr(obj, field, <hardcoded_fallback>)` pattern
- Any `.get(key, <default_value>)` that masks missing config
- Default parameter values in function signatures that contain domain-specific numbers

### B. PARAMETER WIRING (CSV → config.py → get_config() → usage)

For every parameter in `parameters.csv`:
1. Is it loaded in `load_parameters_from_csv()`?
2. Is it assigned to the correct dataclass field?
3. Is the dataclass field actually used somewhere in model code?
4. Does the dataclass default match the CSV Value column? (defaults are safety nets, not source of truth — but they should match)
5. Are there any `bare except` or `try/except Exception` blocks in the loading that could silently swallow parsing errors and leave stale defaults in place?

For every `config.py` dataclass field:
1. Is there a corresponding row in `parameters.csv`?
2. Is the field used in at least one equation?
3. Could the field be dead code?

### C. EQUATION CORRECTNESS

For each equation in the model, verify:

1. **Demand module** (`demand.py`):
   - Compound growth: $D(t) = D_0 \times (1+g)^{t-t_0}$
   - Malé demand share trajectory: three-phase model (near-term taper, post-peak deceleration, long-run floor)
   - Sectoral split sums to 1.0 (residential + commercial + public)
   - Price elasticity: $\Delta D = \varepsilon \times \Delta P / P \times D$
   - Peak demand: $P = D / (LF \times 8760)$

2. **Cost module** (`costs.py`):
   - Solar CAPEX with exogenous decline + climate premium: $C(t) = C_0 \times (1-d)^{t-t_0} \times (1 + \alpha_{climate})$
   - Learning curve (Wright's Law): $C(t) = C_0 \times (Q(t)/Q_0)^{-\alpha}$ where $\alpha = \ln(1/(1-LR))/\ln(2)$
   - Battery CAPEX with exogenous decline + climate premium
   - Solar generation: $G = MW \times CF \times 8760 \times (1 - k_t \times \Delta T) \times (1 - d_{deg})^{age}$
   - Vintage-based degradation: sum over cohorts, each degraded from install year
   - Diesel fuel cost: two-part curve $F = (a + b \times load) \times capacity \times hours$
   - T&D loss gross-up: $G_{gross} = G_{net} / (1 - loss)$ — verify multiplicative not additive
   - Cable CAPEX: converter + landing + IDC + grid integration
   - LCOE calculation: verify discounting, fuel, O&M all included

3. **Emissions module** (`emissions.py`):
   - $E = G_{diesel} \times EF$ where EF = 0.72 kgCO₂/kWh from config
   - SCC growth: $SCC(t) = SCC_0 \times (1 + g_{SCC})^{t-t_0}$
   - India grid emission factor with annual decline
   - LNG emissions use separate emission factor (0.40 vs diesel 0.72)

4. **NPV calculator** (`cba/npv_calculator.py`):
   - $NPV = \sum_{t} \frac{CF_t}{(1+r)^{t-t_0}}$ — verify base year, discount factor formula
   - Declining discount rate: step function (3.5% yr 0–30, 3.0% yr 31–75, 2.5% yr 76–125)
   - Salvage value: straight-line depreciation of remaining asset life at terminal year
   - BCR = PV(benefits) / PV(incremental costs) — verify numerator/denominator
   - IRR bisection: verify convergence, sign convention
   - Incremental analysis: verify it's (scenario − BAU), not absolute

5. **Sensitivity engine** (`cba/sensitivity.py`):
   - Verify all 38 parameters are actually modified in `_modify_config()` AND `_modify_config_inplace()`
   - Verify Low/High values from SENSITIVITY_PARAMS match `parameters.csv` Low/High columns
   - Verify `_modify_config()` returns a *new* Config (no mutation of base config)
   - Verify `_modify_config_inplace()` correctly mutates (used in MC)
   - Switching value: linear interpolation correctness

6. **Scenario-specific checks** (all 7 scenario files):
   - All scenarios must use the same base year, discount rate, emission factors, demand projections
   - RE share calculation: $RE\% = (solar + wind + WTE) / total\_demand$ — verify denominator
   - WTE generation: present in S2-S7, absent from S1 BAU — verify
   - Generation balance: $demand = diesel + solar + import + wte$ (no double-counting, no gaps)
   - Cost completeness: CAPEX + OPEX + fuel = total costs (no missing components)
   - Health benefits: `$40/MWh × diesel_reduction_gwh` — verify diesel reduction vs BAU is correct
   - Fiscal subsidy savings: `diesel_reduction × $0.15/kWh` — verify
   - Reliability benefit: SAIDI-based formula — verify cable availability discount for S2
   - Connection cost: present in S2-S7, absent from S1 — verify
   - Climate premium: applied to solar/battery/cable CAPEX — verify

7. **Transport module** (`transport_analysis.py`):
   - Logistic S-curve: $S(t) = S_0 + (S_{max} - S_0)/(1 + e^{-k(t-t_{mid})})$
   - CO₂ net: ICE emissions displaced MINUS grid emissions for EV charging
   - Health benefits: PM2.5 + NOx + noise per vkm
   - Declining vehicle premium: verify can't go negative
   - Charging stations: incremental (not cumulative re-costing)

8. **MCA** (`cba/mca_analysis.py`):
   - Weights sum to 1.0
   - Normalisation: verify min-max or z-score is applied consistently
   - Higher-is-better vs lower-is-better: verify polarity is correct for each criterion
   - Transport health co-benefit scaling by RE share

### D. UNIT CONSISTENCY

Trace units through every calculation chain. Common unit mismatches to catch:
- **kW vs MW** (factor of 1000) — especially in CAPEX calculations
- **kWh vs MWh vs GWh** (factors of 1000) — especially in generation, fuel, emissions
- **$/kW vs $/MW** — in CAPEX parameters
- **$/kWh vs $/MWh** — in LCOE, tariff, health damage
- **kg vs tonnes vs Mt** — in emissions
- **per-year vs per-period vs cumulative** — in NPV discounting
- **litres vs ML** — in fuel consumption
- **$M vs $** — when mixing absolute and per-unit costs

### E. CROSS-SCENARIO CONSISTENCY

Verify that all 7 scenarios:
1. Use the same `get_config()` call (not stale cached configs)
2. Apply the same `gross_up_for_losses(year=year)` pattern (year-dependent weighted losses)
3. Use the same demand projections from `DemandProjector`
4. Apply climate adaptation premium consistently to solar/battery CAPEX
5. Include WTE in RE share calculation (for S2-S7)
6. Calculate health benefits against the **same BAU baseline**
7. Pass through the same NPV calculator with the same discount rate

### F. ERROR HANDLING & SILENT FAILURES

Search for:
- `except Exception` or `except:` without re-raise — these can mask data loading failures
- `getattr(obj, field, default)` where the default is a hardcoded number — if the attribute is missing, a stale default silently takes over
- `.get(key, default)` in dictionary lookups that could mask missing CSV rows
- Division by zero risks (e.g., when solar_mw=0, demand=0, or discount_rate=0)
- `min()` / `max()` on empty sequences
- Off-by-one errors in year indexing (is year 2026 index 0 or index 1?)

### G. SENSITIVITY / MONTE CARLO PATHS

There are **three** config-modification code paths that must be kept in sync:
1. `sensitivity.py: _modify_config()` — creates new Config for one-way sensitivity
2. `sensitivity.py: _modify_config_inplace()` — mutates Config for Monte Carlo
3. `run_sensitivity.py: modify_config()` — wrapper for the sensitivity runner

Verify:
- All 38 parameters appear in all three paths
- The parameter names match between `SENSITIVITY_PARAMS` dict keys and `_define_parameters()` keys
- Low/High ranges are symmetric where expected
- The switching value calculation correctly interpolates between scenarios

## Output Format

Organise your findings as:

```
## File: model/<filename>.py

### 🔴 CRITICAL — Finding C-XX
**Line(s):** <line numbers>
**Issue:** <description>
**Impact:** <what goes wrong — quantify if possible>
**Fix:** <specific code change>

### 🟡 MODERATE — Finding M-XX
...

### 🔵 LOW — Finding L-XX
...

### ✅ VERIFIED — <aspect checked>
<brief confirmation that X is correct>
```

Number findings sequentially (C-01, C-02, ... M-01, M-02, ... L-01, L-02, ...). At the end, provide a **Summary Table** with counts by severity and a **Priority Fix List** (top 5 most impactful bugs).

## What NOT To Audit

- `.md` files (IMPROVEMENT_PLAN, SCENARIO_GUIDE, CBA_METHODOLOGY, AUDIT_REPORT, README) — these are documentation, audited separately
- `.qmd` files (Quarto report) — audited separately
- `_archive/` directory — historical, read-only
- `perplexity_lookup.py` — standalone utility, not part of model
- Code style, naming conventions, type hints — only flag if they cause actual bugs
- Performance — not relevant for a 30-year annual model

## Key Reference Values (for sanity-checking your audit)

These are the verified model outputs. If your audit finds a bug, recalculate the impact on these:

| Metric | BAU (S1) | Full Int (S2) | Nat Grid (S3) | Isl Green (S4) | Near-Shore (S5) | Max RE (S6) | LNG (S7) |
|--------|----------|---------------|----------------|-----------------|-----------------|-------------|----------|
| Total Cost ($M) | ~44,900 | ~15,200 | ~22,700 | ~24,000 | ~25,900 | ~24,600 | ~15,300 |
| LCOE ($/kWh) | ~0.437 | ~0.211 | ~0.295 | ~0.318 | ~0.281 | ~0.240 | ~0.199 |
| BCR | — | ~6.51 | ~7.71 | ~5.61 | ~5.50 | ~6.90 | ~10.25 |
| RE Share 2050 | ~1.5% | ~39% | ~41% | ~41% | ~48% | ~55% | ~50% |
| Emissions (MtCO₂) | ~66.6 | ~19.1 | ~26.2 | ~27.2 | ~23.3 | ~20.9 | ~22.8 |

Transport (supplementary): Medium scenario NPV $441M, BCR 6.90, 901 kt CO₂.

## Start the Audit

Read every `.py` file in `Maldives/model/` (including subdirectories) and `Maldives/model/parameters.csv`. Work file by file, starting with `config.py` and `parameters.csv` (the foundation), then `costs.py`, `demand.py`, `emissions.py`, then scenarios, then CBA engine, then supplementary modules. Be thorough. Miss nothing.
