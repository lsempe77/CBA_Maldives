# COMPREHENSIVE AUDIT — Maldives Energy CBA Model (v2)

> **Date:** 10 February 2026  
> **Scope:** Full-depth professional audit — economic methodology, code correctness, parameter validity, wiring integrity, and structural soundness  
> **Designed for:** Multi-agent execution (7 independent audit workstreams)  
> **Prior audit:** `AUDIT_PROMPT_v1.md` / `AUDIT_REPORT_v1.md` — 30 findings, all fixed. This v2 audit is a clean-sheet re-examination.

---

## 1. Project Overview

### What This Model Does

A **social Cost-Benefit Analysis (CBA)** of energy transition pathways for the Maldives, comparing 7 scenarios over 2026–2056:

| Code | Scenario | Key Technology |
|------|----------|---------------|
| S1 | BAU (Status Quo) | ~94% diesel + ~6% existing solar (68.5 MW), no new investment |
| S2 | Full Integration | 700 km India–Maldives HVDC submarine cable + domestic RE |
| S3 | National Grid | Inter-island submarine cables + aggressive RE ramp |
| S4 | Islanded Green | Per-island solar+battery mini-grids (no interconnection) |
| S5 | Near-Shore Solar | Solar farms on uninhabited islands + cable to inhabited |
| S6 | Maximum RE | Floating solar (195 MW) + near-shore + ground-mount |
| S7 | LNG Transition | 140 MW LNG plant at Gulhifalhu + RE complement |

The model produces NPV, BCR, IRR, LCOE, emission trajectories, distributional impacts, sensitivity analysis, Monte Carlo simulation, and multi-criteria analysis for all 7 scenarios.

### Architecture

```
parameters.csv (405 rows)
    │
    ▼
config.py (23 dataclasses, ~2,000 lines)
    │  load_parameters_from_csv() → get_config()
    ▼
┌─────────────────────────────────────────────────┐
│  demand.py → costs.py → emissions.py            │
│  dispatch.py (hourly simulation)                 │
│  least_cost.py (176-island LCOE engine)          │
│  network.py (inter-island distances, MST)        │
│                                                  │
│  scenarios/                                      │
│    status_quo.py  one_grid.py                    │
│    green_transition.py  islanded_green.py        │
│    nearshore_solar.py  maximum_re.py             │
│    lng_transition.py                             │
│    __init__.py (BaseScenario, GenerationMix)     │
│                                                  │
│  cba/                                            │
│    npv_calculator.py (NPV, BCR, IRR, salvage)    │
│    sensitivity.py (38-param engine, MC)           │
│    mca_analysis.py (8-criteria weighted scoring)  │
│                                                  │
│  Runners:                                        │
│    run_cba.py  run_sensitivity.py                │
│    run_monte_carlo.py  run_multi_horizon.py      │
│                                                  │
│  Supplementary:                                  │
│    financing_analysis.py  distributional_analysis │
│    transport_analysis.py  sanity_checks.py       │
└─────────────────────────────────────────────────┘
    │
    ▼
outputs/*.json → report/REPORT...qmd
```

### Current Model Outputs (post-v1 audit fixes)

| Scenario | PV Total Cost ($B) | LCOE ($/kWh) | BCR | IRR | NPV Savings ($B) |
|----------|--------------------|--------------|-----|-----|-------------------|
| S1 BAU | 15.68 | 0.437 | — | — | — |
| S2 Full Integration | 9.35 | 0.211 | 2.70 | 16.3% | 9.28 |
| S3 National Grid | 9.22 | 0.293 | 11.89 | 33.9% | 10.19 |
| S4 Islanded Green | 10.00 | 0.318 | 8.61 | 27.7% | 9.32 |
| S5 Near-Shore Solar | 8.78 | 0.280 | 10.73 | 33.4% | 10.96 |
| S6 Maximum RE | 8.23 | 0.262 | 9.53 | 33.2% | 11.98 |
| S7 LNG Transition | 6.29 | 0.200 | 9.07 | 44.8% | 14.34 |

### Codebase Size

- **29 Python files** (excl. perplexity_lookup.py), **~16,400 lines**
- **405 rows** in parameters.csv
- **23 dataclasses** in config.py with ~300+ fields
- **38 sensitivity parameters**, 1,000 MC iterations
- **47 automated sanity checks**

---

## 2. Audit Design — Seven Workstreams

This audit is designed to be executed as **7 independent workstreams**, each producing its own findings report. Each workstream can be assigned to a separate subagent.

### Workstream Overview

| # | Workstream | Focus | Key Files | What It Should Catch |
|---|-----------|-------|-----------|---------------------|
| **A** | **Economic Methodology & CBA Framework** | Is the CBA structurally sound as economics? | All scenario files, npv_calculator.py, run_cba.py, CBA_METHODOLOGY.md | Wrong counterfactual, missing cost/benefit categories, incorrect discounting logic, BCR/IRR definition errors, appraisal framework violations |
| **B** | **Parameter Validity & Empirical Grounding** | Are the ~200 key parameters defensible? | parameters.csv, config.py, literature_benchmarks.md | Outdated sources, implausible values, missing uncertainty ranges, geographic mismatches, citation quality |
| **C** | **Code Correctness & Equation Fidelity** | Does every equation in code match its mathematical specification? | costs.py, demand.py, emissions.py, dispatch.py, npv_calculator.py, sensitivity.py | Unit mismatches, sign errors, off-by-one, wrong formula implementation, numerical instability |
| **D** | **Config Wiring & Data Pipeline Integrity** | Does every parameter flow correctly from CSV → config → consumption? | parameters.csv, config.py, all consuming .py files | Broken wiring, stale defaults masking CSV, hardcoded values, dead params, silent exception swallowing |
| **E** | **Scenario Consistency & Comparative Logic** | Are the 7 scenarios internally consistent and the comparisons fair? | All 7 scenario files, scenarios/__init__.py | Different base assumptions across scenarios, missing cost/benefit categories in some but not all, unfair comparisons, double-counting |
| **F** | **Sensitivity, Monte Carlo & Robustness** | Is the uncertainty analysis methodologically sound? | sensitivity.py, run_sensitivity.py, run_monte_carlo.py, run_multi_horizon.py | Parameter ranges too narrow/wide, missing correlations, distribution assumptions, 3-path sync issues, switching value logic |
| **G** | **Supplementary Modules & Outputs** | Are the supporting analyses (distributional, financing, transport, MCA) correct? | distributional_analysis.py, financing_analysis.py, transport_analysis.py, mca_analysis.py, sanity_checks.py | Microdata handling errors, grant element formula, MCA weight/polarity issues, transport S-curve problems |

---

## 3. Workstream A — Economic Methodology & CBA Framework

### Objective
Assess whether this CBA follows established social cost-benefit analysis principles (Boardman et al. 2018 *Cost-Benefit Analysis: Concepts and Practice*; ADB 2017 *Guidelines for the Economic Analysis of Projects*; HM Treasury 2026 *Green Book*).

### What to Read
1. `model/cba/npv_calculator.py` — the entire NPV/BCR/IRR/salvage engine
2. `model/scenarios/__init__.py` — `AnnualCosts`, `AnnualBenefits`, `GenerationMix` dataclasses
3. `model/run_cba.py` — how scenarios are run and compared
4. `Maldives/CBA_METHODOLOGY.md` — the existing equation catalogue (cross-check code against it)
5. `Maldives/SCENARIO_GUIDE.md` — scenario definitions and design rationale

### Questions to Answer

#### A1. Counterfactual Design
- Is the BAU (S1) a credible "without project" scenario? Does it assume zero investment (including zero replacement of retiring diesel generators), or does it include necessary reinvestment to maintain current service levels?
- Is the BAU demand growth trajectory realistic? 5% compound for 30 years means 4.3× demand by 2056 — is this plausible for a 515k-population SIDS?
- Does the BAU correctly include diesel replacement CAPEX (generators have 20-year life), or does it only count fuel + O&M? If no replacement CAPEX, all alternatives look artificially better.

#### A2. Cost-Benefit Accounting
- **Completeness:** Are all relevant cost and benefit categories included? Check against ADB (2017) Table 6.1:
  - Costs: CAPEX, O&M, fuel, replacement, connection, supply security, environmental damage
  - Benefits: avoided fuel, avoided O&M, avoided environmental damage, health, reliability, subsidy savings, carbon
- **Transfer payments:** Are subsidies, taxes, and tariffs correctly excluded from the economic (social) analysis? The model includes "subsidy avoidance" as a benefit — is this double-counting with the avoided cost of diesel? (The subsidy is a fiscal transfer, not an economic cost.)
- **Consumer surplus:** Does the model account for consumer surplus changes from price changes (via price elasticity)? Or is welfare measured only on the producer/cost side?
- **Residual value:** Is salvage value calculated correctly at the terminal year? Does it use economic depreciation or accounting depreciation?

#### A3. Discounting
- The base discount rate is 6%. Is this appropriate for a SIDS? ADB recommends 9-12% for developing countries. HM Treasury uses 3.5%. What is the opportunity cost of capital in the Maldives?
- The DDR schedule (3.5% → 3.0% → 2.5%) is from HM Treasury — is it appropriate for a Maldives context? Should it be applied to the 6% rate (i.e., 6% → 5% → 4%) rather than replacing it?
- Is the discount factor formula `1/(1+r)^t` applied with t=0 for the base year (costs at base year undiscounted)?

#### A4. Incremental Analysis
- Is the incremental analysis (scenario minus BAU) correctly structured? Specifically:
  - BCR = PV(incremental benefits) / PV(incremental costs)? What is in the numerator vs denominator?
  - Are "benefits" defined as avoided BAU costs + external benefits (health, carbon, reliability)?
  - Are "costs" the CAPEX + incremental O&M of the alternative?
- Is the IRR calculated on the incremental cash flow (not the absolute)?

#### A5. Key Structural Concerns
- **S2 (India cable) cost-sharing:** The model assumes 100% GoM financing of a $2.5B cable. Is this realistic? If India pays 70%, the BCR changes fundamentally. How is this handled?
- **Subsidy avoidance as benefit:** `$0.15/kWh × diesel_reduction_GWh` — this is the fiscal subsidy currently paid by GoM. But if diesel is eliminated, the subsidy disappears regardless. Is this a real benefit or a transfer? In economic CBA, transfers are excluded. Only include if the alternative scenario retains a subsidy mechanism.
- **Health benefits:** $40/MWh applied to ALL diesel reduction. But health damages are highly location-specific — Malé (65,000/km²) is very different from an outer atoll (50/km²). Is a single national average defensible?
- **Reliability benefits:** SAIDI-based formula — does it correctly value the willingness-to-pay for reliability, or does it just monetise outage hours at average tariff?

#### A6. Perspective and Scope
- Is this an economic CBA (social perspective, shadow prices) or a financial CBA (private investor perspective)? The discount rate (6%) and inclusion of externalities suggest economic — but is this consistently applied?
- Are traded goods (fuel, equipment) valued at border prices or domestic prices? For a 100%-fuel-importing country like Maldives, does this matter?
- Is there a standard conversion factor or shadow exchange rate applied?

### Severity Classification
- 🔴 **CRITICAL:** Would change the sign of NPV, reverse scenario rankings, or violate fundamental CBA principles
- 🟡 **MODERATE:** Could change BCR by >10%, misrepresent a benefit/cost category, or deviate from best practice
- 🔵 **LOW:** Minor methodological refinements, documentation gaps

---

## 4. Workstream B — Parameter Validity & Empirical Grounding

### Objective
Verify that every key parameter in the model is (a) plausible, (b) sourced from a credible reference, (c) appropriate for the Maldives context, and (d) has reasonable uncertainty bounds.

### What to Read
1. `model/parameters.csv` — all 405 rows, especially the Source and Notes columns
2. `model/config.py` — dataclass defaults and CSV loading logic
3. `Maldives/literature_benchmarks.md` — existing literature comparison
4. `Maldives/data/addiitonal_maldives_cba_parameters_sources.md` — additional sources

### Parameters to Scrutinise (Priority Order)

#### B1. Demand Parameters (high leverage — compound over 30 years)
| Parameter | Current Value | Question |
|-----------|--------------|----------|
| `base_demand_gwh` | 1,200 | Is this utility-only? Does it match IRENA (2022), Island Electricity Data Book (2018)? What was actual 2024/2025 demand? |
| `demand_growth_rate` (BAU) | 5.0% | IRENA CAGR 5.1% was historical. IMF projects GDP growth ~5-6%. But demand elasticity to GDP in SIDS is typically 0.8-1.2, and population growth is <2%. Is 5% sustained for 30 years defensible? |
| `load_factor` | 0.68 | From 2018 Island Electricity Data Book. Has it changed? Urban vs rural? |
| `price_elasticity` | -0.3 | From Wolfram et al. (2012) and Burke et al. (2015). These are global estimates — Maldives-specific data? |

#### B2. Technology Cost Parameters (drive LCOE and NPV)
| Parameter | Current Value | Question |
|-----------|--------------|----------|
| `solar_pv_capex` | $1,500/kW | From AIIB Maldives Solar (2021). But global utility-scale is now $400-600/kW. Is $1,500 still right for SIDS island installation in 2026? IRENA RPGC 2024 shows $800-1,200 for off-grid SIDS. |
| `solar_capex_decline_rate` | 4%/yr | Exogenous decline. Historical has been 7-10%/yr globally. Is 4% conservative enough, or too conservative? |
| `battery_capex_kwh` | $350/kWh | BNEF 2025 global average is ~$140/kWh for utility-scale Li-ion. Island premium justifies some uplift, but 2.5×? IRENA (2024) shows $200-300 for island systems. |
| `battery_capex_decline_rate` | 6%/yr | Reasonable per BNEF trajectory. |
| `cable_capex_per_km` | $3.0M/km | For 700km HVDC. NordLink was €1.6B/623km = €2.6M/km. NorNed was ~$3.1M/km. Deep-water Indian Ocean may be higher. Cross-check against CIGRÉ TB 610. |
| `diesel_fuel_price_usd_per_litre` | $1.00/L | This is the import price. What is the 2025 actual? IMF WEO projections? Sensitivity range? |
| `diesel_fuel_escalation_rate` | 2%/yr | Real escalation. IEA WEO 2024 projects real oil prices rising 0-2%/yr to 2050. Defensible. |

#### B3. Economic Parameters
| Parameter | Current Value | Question |
|-----------|--------------|----------|
| `discount_rate` | 6% | See A3 above. ADB typical for Pacific SIDS is 10%. Philippines uses 15%. Is 6% justified? |
| `social_cost_carbon` | $50/tonne | EPA 2024 central estimate. But SIDS often argue for higher SCC due to existential climate risk. Stern-Stiglitz Commission recommends $50-100. |
| `scc_annual_growth` | 2%/yr | Consistent with Nordhaus DICE model. |
| `health_damage_cost_per_mwh` | $40/MWh | From Parry et al. (2014). Is this a Maldives-specific estimate or a global average? Population density varies 100× between Malé and outer atolls. |

#### B4. Geographic Appropriateness
- How many parameters are derived from **global averages** vs **Maldives-specific data**? Flag any parameter where a Maldives-specific value exists but a global value is used.
- Are solar resource assumptions (GHI, temperature) validated against the Global Solar Atlas data in `data/geotiff/`?
- Is the 11% distribution loss (World Bank WDI) a Maldives-specific value or a global average? STELCO annual reports may have actual losses.

#### B5. Uncertainty Ranges
- For each parameter with Low/High values in the CSV: are the ranges symmetric? If so, is that justified?
- Are any parameters missing Low/High values entirely? These cannot be included in sensitivity/MC analysis.
- Are the ranges wide enough? A common error is making ranges too narrow (±10% when ±50% is realistic), which makes results appear more robust than they are.

### Method
- For each parameter category, check the Source column against the actual reference. Verify the value matches what the source says.
- Flag any source older than 2020 (except canonical standards like IPCC 2006, IEC 61215).
- Flag any source marked "assumed", "estimated", "illustrative", or similar.
- Cross-check against IRENA RPGC 2024, IEA WEO 2024, BNEF 2025, Lazard LCOE/LCOS 2024.

---

## 5. Workstream C — Code Correctness & Equation Fidelity

### Objective
Verify that every mathematical formula implemented in Python correctly matches its intended equation, with correct units, signs, and edge-case handling.

### What to Read
Every `.py` file in `model/` and `model/cba/` and `model/scenarios/`. Cross-reference against `CBA_METHODOLOGY.md` (equation catalogue).

### Systematic Checks

#### C1. Demand Module (`demand.py`, ~362 lines)
- Compound growth: $D(t) = D_0 \times (1+g)^{t-t_0}$ — verify exponent base, units (GWh)
- Malé demand share trajectory: three-phase model — verify the piecewise function, transition points, and that shares sum correctly with outer islands
- Price elasticity: $\Delta D = \varepsilon \times (\Delta P / P) \times D$ — verify sign convention (negative elasticity + price decrease = demand increase), verify $\Delta P$ calculation
- Sectoral split: verify `residential_share + commercial_share + public_share == 1.0` is enforced
- Peak demand: $P = D \times 10^3 / (8760 \times LF)$ — verify GWh→MW conversion, units

#### C2. Cost Module (`costs.py`, ~881 lines)
- **Solar CAPEX with decline:**  
  $C(t) = C_0 \times (1-d)^{t-t_0} \times (1 + \alpha_{climate})$  
  Verify: (a) base year is correct, (b) decline compounds from correct year, (c) climate premium is multiplicative not additive, (d) units are $/kW
- **Learning curves (Wright's Law):**  
  $C(t) = C_0 \times (Q(t)/Q_0)^{-\alpha}$, where $\alpha = \ln(1/(1-LR))/\ln(2)$  
  Verify: (a) cumulative deployment $Q(t)$ grows correctly, (b) learning rate applied correctly, (c) both solar and battery curves exist
- **Solar generation:**  
  $G = MW \times 10^3 \times CF \times 8760 \times (1 - k_t \times (T_{cell} - 25)) \times (1 - d_{deg})^{age}$  
  Where $T_{cell} = T_{amb} + 25.6 \times GHI_{kW/m^2}$  
  Verify: (a) MW→kW conversion, (b) GHI units (kWh/m²/day → kW/m²), (c) degradation compounds from install year per vintage, (d) units come out as kWh or MWh consistently
- **Diesel fuel cost:**  
  Two-part curve: $F_{litres} = C_{kW} \times a + G_{kWh} \times b$  
  Verify: (a) idle consumption coefficient $a$ units, (b) proportional coefficient $b$ units, (c) result in litres
- **T&D loss gross-up:**  
  $G_{gross} = G_{net} / \prod_{i}(1 - loss_i)$  
  Verify: (a) multiplicative not additive, (b) distribution + HVDC cable losses applied correctly, (c) weighted loss function uses correct Malé/outer shares
- **Cable CAPEX:**  
  $Total = (submarine + converters + landing) \times (1 + IDC) + grid$  
  Verify: (a) each component correct, (b) IDC applied before grid integration, (c) total matches expected ~$2.1-2.5B range
- **LCOE:**  
  $LCOE = \frac{\sum_t \frac{Cost_t}{(1+r)^t}}{\sum_t \frac{Gen_t}{(1+r)^t}}$  
  Verify: (a) costs include CAPEX + fuel + O&M, (b) generation includes degradation, (c) discount rate matches CBA rate

#### C3. Emissions Module (`emissions.py`, ~276 lines)
- $E_{diesel} = G_{diesel,GWh} \times 10^6 \times EF_{kg/kWh} / 10^3$ — verify GWh→kWh→tonnes conversion chain
- $E_{solar,lifecycle} = G_{solar,GWh} \times 10^6 \times EF_{lifecycle,kg/kWh} / 10^3$ — same check (v1 found a 1000× error here)
- SCC monetisation: $Benefit_t = (E_{BAU,t} - E_{alt,t}) \times SCC_t$ — verify sign, verify SCC in $/tonne and emissions in tonnes
- India grid EF: verify declining trajectory matches config, correct units

#### C4. Dispatch Module (`dispatch.py`, ~408 lines)
- Hourly PV-diesel-battery simulation — verify:
  - Battery SOC tracking: charge limited by capacity and efficiency, discharge limited by DoD and SOC
  - Diesel min-load constraint (40%): generator runs at minimum even when not needed
  - Curtailment: excess PV beyond demand + battery headroom
  - LPSP: hours with unmet demand / total hours
  - Fuel consumption: two-part curve per hour (not just per year)
  - Self-discharge: verify rate and accumulation
  - Battery cycling: verify counting is per full equivalent cycle

#### C5. NPV Calculator (`npv_calculator.py`, ~820 lines)
- Discount factor: $DF_t = 1/(1+r)^{t-t_0}$ — verify base year treatment (DF at t₀ = 1.0)
- Declining discount rate: step function at years 30 and 75 — verify cumulative product of discount factors, not just rate substitution
- Salvage value: $SV = (remaining\_life / total\_life) \times original\_cost \times DF_{terminal}$ — verify for each asset type (solar, battery, diesel, cable)
- IRR bisection: verify convergence criteria, search bounds, max iterations, and that it solves the correct equation (NPV of incremental cash flow = 0)

#### C6. Sensitivity Engine (`sensitivity.py`, ~992 lines)
- Verify `_modify_config()` creates a deep copy (not shallow) — mutation of the copy should not affect the original
- Verify all 38 parameters are modified in both `_modify_config()` and `_modify_config_inplace()`
- Verify that cable_capex_total is recomputed when cable_capex_per_km changes (v1 found this was missing)
- Verify demand growth rates are scaled proportionally, not replaced with flat values

### Edge Cases to Test Mentally
- What happens when solar_mw = 0? (S1 BAU in early years)
- What happens when diesel_gwh = 0? (S2/S6 in late years)
- What happens when discount_rate = 0? (should not divide by zero)
- What happens at year 2056 exactly? (is it included or excluded from the sum?)

---

## 6. Workstream D — Config Wiring & Data Pipeline Integrity

### Objective
Verify that every parameter flows correctly through the pipeline: `parameters.csv` → `load_parameters_from_csv()` → dataclass field → `get_config()` → consuming module. No breaks, no stale defaults, no silent failures.

### What to Read
1. `model/parameters.csv` — every row
2. `model/config.py` — every dataclass, every field, the entire `load_parameters_from_csv()` function
3. Every consuming `.py` file — every `config.xxx.yyy` access

### Systematic Checks

#### D1. CSV → Config Loading
For each row in `parameters.csv`:
1. Is the Parameter name matched in `load_parameters_from_csv()`?
2. Is it assigned to the correct dataclass and field?
3. Is the parsing correct (float vs int vs string)?
4. Is there error handling? If parsing fails, does it silently use the default or raise?
5. Is the CSV `Value` column consistent with the dataclass default? (They should match — the default is a safety net, not the source of truth.)

#### D2. Dead Parameters
For each dataclass field in `config.py`:
1. Is it actually used by any consuming module? Search for `config.xxx.field_name` across all `.py` files.
2. If not used, is it documented as "informational only" or is it genuinely dead code?
3. List all dead parameters.

#### D3. Hardcoded Value Sweep
Search every `.py` file (excluding config.py and parameters.csv) for numeric literals that should be parameters. Pay special attention to:
- Dollar amounts (anything with 3+ digits)
- Percentages (0.xx patterns)
- Years (2026, 2030, 2031, 2050, 2056)
- Capacity values (MW, kW, GWh)
- Any `getattr(obj, field, numeric_default)` pattern
- Any `.get(key, numeric_default)` pattern

#### D4. Silent Failure Patterns
Search for:
- `except Exception:` or `except:` (bare except)
- `try/except` blocks in config loading that could swallow CSV parsing errors
- Default parameter values in function signatures that contain domain-specific numbers
- `if hasattr(config, 'field'):` patterns that silently skip missing fields

#### D5. Cross-Check: Config Fields vs CSV Rows
Generate two lists:
1. All unique `Parameter` values in `parameters.csv`
2. All field names across all dataclasses in `config.py`
Flag: (a) CSV rows with no matching config field, (b) config fields with no matching CSV row (and no clear derivation logic).

---

## 7. Workstream E — Scenario Consistency & Comparative Logic

### Objective
Verify that the 7 scenarios are internally consistent with each other and that the CBA comparison is methodologically fair.

### What to Read
All 8 files in `model/scenarios/`:
- `__init__.py` (base classes)
- `status_quo.py`, `one_grid.py`, `green_transition.py`, `islanded_green.py`
- `nearshore_solar.py`, `maximum_re.py`, `lng_transition.py`

Plus `model/run_cba.py` (how they're compared).

### Systematic Checks

#### E1. Common Assumptions (must be identical across all 7)
| Assumption | Should Be | Check |
|------------|-----------|-------|
| Base year | 2026 | Same in all scenarios? |
| End year | 2056 | Same in all scenarios? |
| Discount rate | 6% | Applied identically? |
| Base demand (2026) | 1,200 GWh | Same starting point? |
| Emission factor (diesel) | 0.72 kg/kWh | Same in all? |
| SCC | $50/t + 2%/yr growth | Same in all? |
| Climate adaptation premium | 7.5% | Applied to same asset types? |
| Health damage | $40/MWh | Applied to same baseline? |

#### E2. Generation Balance
For each scenario and each year, verify: $D_{gross} = G_{diesel} + G_{solar} + G_{import} + G_{LNG} + G_{WTE}$  
- No double-counting (same GWh counted in two categories)
- No gaps (demand not met without being flagged as unmet)
- WTE present in S2–S7, absent from S1
- Import (cable) present only in S2
- LNG present only in S7

#### E3. Cost Completeness
For each scenario, verify these cost categories are either included or explicitly excluded with justification:

| Cost Category | S1 | S2 | S3 | S4 | S5 | S6 | S7 |
|--------------|----|----|----|----|----|----|-----|
| Diesel CAPEX (replacement) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Diesel fuel | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Diesel O&M | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Solar CAPEX | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Solar O&M | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Battery CAPEX | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Battery replacement | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Battery O&M | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cable CAPEX | — | ✓ | ✓ | — | ✓ | ✓ | — |
| Cable O&M | — | ✓ | ✓ | — | ✓ | ✓ | — |
| Import electricity cost | — | ✓ | — | — | — | — | — |
| LNG plant CAPEX | — | — | — | — | — | — | ✓ |
| LNG fuel | — | — | — | — | — | — | ✓ |
| WTE CAPEX/OPEX | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Connection cost | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Grid integration | — | ✓ | ✓ | — | ✓ | ✓ | — |
| Supply security (idle fleet) | — | ✓ | — | — | — | — | — |

#### E4. Benefit Completeness
Same check for benefits:

| Benefit Category | How Calculated | Applied to Which Scenarios? |
|-----------------|----------------|---------------------------|
| Avoided fuel cost | BAU fuel − Alt fuel | S2–S7 |
| Carbon benefit | (BAU emissions − Alt emissions) × SCC | S2–S7 |
| Health benefit | Diesel reduction × $40/MWh | S2–S7 |
| Reliability benefit | SAIDI-based formula | S2–S7 |
| Subsidy avoidance | Diesel reduction × $0.15/kWh | S2–S7 |
| Connection benefit | New connections × WTP | S2–S7 |

Verify each is calculated against the **same BAU baseline**.

#### E5. Deployment Schedule Plausibility
- S2: 700 km HVDC cable built in what timeframe? Is this physically feasible?
- S3: Inter-island cables + RE ramp — what MW/year? Maximum historical deployment rate for comparison?
- S4: 176 islands each getting mini-grids — logistics, shipping, installation workforce?
- S5/S6: Near-shore and floating solar — what is the Maldives' experience with these technologies?
- S7: 140 MW LNG plant by 2031 — feasible timeline? Has Gulhifalhu been approved?

#### E6. Scenario Rankings
- Does the ranking (S7 > S6 > S5 > S3 > S2 > S4 > S1 by NPV savings) make intuitive sense?
- Why does S7 (LNG, a fossil fuel) dominate S6 (maximum RE)? Is this because LNG costs are too low, RE costs are too high, or carbon pricing is too low?
- Is the model sensitive to the carbon price assumption? At what SCC does S6 overtake S7?

---

## 8. Workstream F — Sensitivity, Monte Carlo & Robustness

### Objective
Verify that the uncertainty analysis is methodologically sound and that all three config-modification paths are synchronised.

### What to Read
1. `model/cba/sensitivity.py` — the engine (~992 lines)
2. `model/run_sensitivity.py` — the runner (~662 lines)
3. `model/run_monte_carlo.py` — MC simulation (~376 lines)
4. `model/run_multi_horizon.py` — multi-horizon (~375 lines)

### Systematic Checks

#### F1. Three-Path Synchronisation
There are three code paths that modify config for sensitivity/MC. They **must** handle the same 38 parameters identically:

| Path | Function | Used By |
|------|----------|---------|
| Path 1 | `sensitivity.py:_modify_config()` | Class-based one-way sensitivity |
| Path 2 | `sensitivity.py:_modify_config_inplace()` | Monte Carlo simulation |
| Path 3 | `run_sensitivity.py:modify_config()` | Runner-based sensitivity (produces JSON) |

For each of the 38 parameters, verify:
- All 3 paths handle it (no missing `elif` branches)
- All 3 paths apply the **same transformation** (especially for growth rates — proportional scaling, not flat replacement)
- Cable CAPEX total is recomputed in all 3 paths when `cable_capex` changes
- No path mutates the base config when it shouldn't

#### F2. Parameter Ranges
For each of the 38 sensitivity parameters:
- Do Low/High values come from `parameters.csv` or are they hardcoded in `_define_parameters()`?
- Are the ranges symmetric? If asymmetric, is there justification?
- Are any ranges too narrow (±5%) making results appear artificially robust?
- Are any ranges too wide (±90%) making results appear artificially uncertain?
- Cross-check critical ranges: discount rate (3-12%), solar CAPEX (±30%), fuel price (±50%), demand growth (±40%)

#### F3. Monte Carlo Design
- Distribution: are parameters sampled uniformly or normally? Uniform between Low/High is standard for CBA sensitivity but may not capture tail risks.
- Correlations: are parameters sampled independently? In reality, solar CAPEX and battery CAPEX are correlated (both decline with RE deployment). Oil price and LNG price are correlated. Is independent sampling biasing the results?
- Iterations: 1,000 iterations — is this enough for convergence? Check: does the mean NPV stabilise by iteration 500?
- Seed: is the random seed fixed for reproducibility?

#### F4. Switching Value Analysis
- `calculate_switching_values()` in `run_sensitivity.py` — does it correctly find the parameter value at which two scenarios have equal NPV?
- Is the linear interpolation between Low and High values appropriate, or could the NPV function be non-linear in the parameter?
- Are all 6 scenario pairs sensible comparisons?

#### F5. Multi-Horizon Analysis
- Does the 20/30/50-year analysis change which scenario is optimal?
- Is the salvage value recalculated for each horizon?
- Are all 7 scenarios included? (v1 found only 4 were included — verify the fix)

---

## 9. Workstream G — Supplementary Modules & Outputs

### Objective
Verify the correctness of supporting analyses that complement the core CBA.

### G1. Distributional Analysis (`distributional_analysis.py`, ~1,099 lines)
- **Data source:** HIES 2019 microdata — is the sample size adequate (4,817 HH)? Are weights applied?
- **Energy burden:** electricity expenditure / household income — is this the right metric? Should it be total energy (including transport fuel)?
- **Energy poverty:** threshold at 10% of income — is this the standard for SIDS? UK uses 10% but developing countries often use different thresholds.
- **Quintile construction:** by per-capita income or total household income? Are quintile boundaries correct?
- **Tariff impact simulation:** how does it translate LCOE changes into tariff changes? Is there a passthrough assumption?
- **Gender analysis:** head of household gender — is this a meaningful proxy for gender equity in the Maldives context?
- **Suits index:** verify formula and sign convention (negative = progressive, positive = regressive)

### G2. Financing Analysis (`financing_analysis.py`, ~498 lines)
- **Grant element:** OECD-DAC/IMF formula — verify against the standard definition
  $GE = 1 - \frac{PV(\text{debt service})}{Face Value}$ discounted at commercial rate
- **WACC calculation:** verify weights (ADB share × ADB rate + commercial share × commercial rate)
- **ADB terms:** 1% interest, 40-year maturity, 10-year grace — are these current ADB SIDS terms?
- **Debt service schedule:** verify equal principal amortisation after grace period
- **Fiscal burden:** debt service as % of GDP — is the GDP denominator growing?

### G3. Transport Analysis (`transport_analysis.py`, ~410 lines)
- **Logistic S-curve:** $S(t) = S_0 + (S_{max} - S_0)/(1 + e^{-k(t-t_{mid})})$ — verify parameters, verify overflow protection
- **Fleet projection:** 131,000 vehicles growing at what rate? 92% motorcycles — source?
- **EV electricity demand:** verify kWh/km × annual km × fleet size — units check
- **CO₂ displacement:** ICE emissions − grid emissions for EV charging — verify both sides
- **Health benefits:** PM2.5 + NOx + noise per vehicle-km — are damage factors Maldives-specific or global?
- **This is a standalone supplementary module** — verify it does NOT feed back into the main CBA NPV

### G4. Multi-Criteria Analysis (`mca_analysis.py`, ~513 lines)
- **Weights:** do all weight profiles sum to 1.0?
- **Normalisation:** min-max across scenarios — verify direction (higher-is-better vs lower-is-better for each criterion)
- **Polarity:** `fiscal_burden` should be "lower is better" — is it correctly inverted?
- **Criteria list:** 8 criteria — are they independent (no double-counting NPV + LCOE which are related)?
- **Sensitivity to weights:** does the ranking change significantly with different weight profiles?

### G5. Sanity Checks (`sanity_checks.py`, ~631 lines)
- Do the 47 checks cover the right things?
- Are the expected ranges sourced or arbitrary?
- Are there important checks missing? (e.g., demand at 2056, solar capacity at 2056, diesel share at 2056)
- Do any checks use hardcoded values instead of config?

---

## 10. Output Format

Each workstream produces a standalone findings report structured as:

```markdown
## Workstream [A-G]: [Title]

### Executive Summary
- X CRITICAL findings, Y MODERATE, Z LOW
- Top concern: [one-sentence summary of the most important finding]

### Findings

#### 🔴 CRITICAL — [ID]: [Title]
**File(s):** [file paths with line numbers]
**Issue:** [clear description]
**Evidence:** [code snippet or calculation showing the problem]
**Impact:** [quantified where possible — what changes in the output?]
**Recommendation:** [specific fix]

#### 🟡 MODERATE — [ID]: [Title]
[same structure]

#### 🔵 LOW — [ID]: [Title]
[same structure]

### Verified Correct
[List of things explicitly checked and confirmed correct — this is as important as the findings]

### Summary Table
| ID | Severity | File | Impact | Fix Effort |
|----|----------|------|--------|-----------|
```

### Finding ID Format
- `A-CR-01`, `A-CR-02` for Workstream A criticals
- `B-MR-01` for Workstream B moderates
- `G-LW-03` for Workstream G lows

---

## 11. Cross-Workstream Integrity Checks

After all 7 workstreams complete, a final integration check should verify:

1. **No contradictions** between workstream findings (e.g., Workstream B says a parameter is correct but Workstream C finds it's used wrong)
2. **Coverage completeness** — every `.py` file has been read by at least one workstream
3. **Impact assessment** — rank all CRITICAL findings by quantified impact on model outputs
4. **Fix sequencing** — which fixes should be applied first (dependencies)
5. **Cumulative impact** — if all fixes were applied simultaneously, what is the estimated change in NPV rankings?

---

## 12. Reference Standards

Auditors should benchmark against:

| Standard | Use |
|----------|-----|
| Boardman, Greenberg, Vining & Weimer (2018) *Cost-Benefit Analysis: Concepts and Practice*, 5th ed. | CBA framework, discounting, standing |
| ADB (2017) *Guidelines for the Economic Analysis of Projects* | Developing country CBA, EIRR thresholds, shadow pricing |
| HM Treasury (2026) *The Green Book* | Declining discount rates, intergenerational equity |
| IRENA (2024) *Renewable Power Generation Costs* | Technology cost benchmarks |
| IEA (2024) *World Energy Outlook* | Fuel price projections, demand trajectories |
| IPCC (2006, 2019) *Guidelines for GHG Inventories* | Emission factors |
| Drupp, Freeman, Groom & Nesje (2018) *AEJ: Economic Policy* 10(4) | Expert survey on discount rates |
| Parry, Heine, Lis & Li (2014) IMF WP/14/199 | Health damage costs of fossil fuels |
| CIGRÉ Technical Brochures 610, 852 | Submarine cable costs and lifetime |
| Lazard (2024) *LCOE* and *LCOS* | Technology cost cross-checks |

---

## 13. Files to Audit (Complete List)

### Core Model (audit every line)
| File | Lines | Workstreams |
|------|-------|------------|
| `model/config.py` | 1,978 | D |
| `model/parameters.csv` | 405 rows | B, D |
| `model/demand.py` | 362 | C, E |
| `model/costs.py` | 881 | B, C, E |
| `model/emissions.py` | 276 | C, E |
| `model/dispatch.py` | 408 | C |
| `model/scenarios/__init__.py` | 560 | A, C, E |
| `model/scenarios/status_quo.py` | 197 | E |
| `model/scenarios/one_grid.py` | 416 | E |
| `model/scenarios/green_transition.py` | 373 | E |
| `model/scenarios/islanded_green.py` | 317 | E |
| `model/scenarios/nearshore_solar.py` | 361 | E |
| `model/scenarios/maximum_re.py` | 406 | E |
| `model/scenarios/lng_transition.py` | 445 | E |
| `model/cba/npv_calculator.py` | 820 | A, C |
| `model/cba/sensitivity.py` | 992 | C, F |
| `model/cba/mca_analysis.py` | 513 | G |
| `model/run_cba.py` | 1,238 | A, E |
| `model/run_sensitivity.py` | 662 | F |
| `model/run_monte_carlo.py` | 376 | F |
| `model/run_multi_horizon.py` | 375 | F |

### Supplementary (audit for correctness)
| File | Lines | Workstreams |
|------|-------|------------|
| `model/financing_analysis.py` | 498 | G |
| `model/distributional_analysis.py` | 1,099 | G |
| `model/transport_analysis.py` | 410 | G |
| `model/sanity_checks.py` | 631 | G |
| `model/least_cost.py` | 912 | C, E |
| `model/network.py` | 509 | C |
| `model/grid_vs_standalone.py` | 279 | C |

### Reference Documents (read for context, do not audit)
| File | Purpose |
|------|---------|
| `CBA_METHODOLOGY.md` | Equation catalogue — cross-check code against this |
| `SCENARIO_GUIDE.md` | Scenario design rationale |
| `IMPROVEMENT_PLAN.md` | Decision log with verified parameter sources |
| `literature_benchmarks.md` | 10-paper SIDS CBA literature review |
| `AUDIT_REPORT_v1.md` | Prior audit — 30 findings, all fixed |
| `SOTA_CBA_ASSESSMENT.md` | State-of-the-art gap analysis |
| `real_options_analysis.md` | Real options framing for cable investment |

### Do NOT Audit
- `_archive/` — historical code, read-only
- `perplexity_lookup.py` — standalone utility
- `data/` files — data inputs, not model logic
- `report/` — Quarto report, separate audit
- `.md` files (as code) — documentation only

---

## 14. Execution Instructions

### For the Orchestrating Agent

1. **Launch 7 subagents**, one per workstream (A through G).
2. Each subagent receives:
   - This full audit prompt (for context)
   - Its specific workstream section (for focus)
   - Access to read all files listed in §13
3. Each subagent returns a structured findings report per §10.
4. After all 7 complete, run the cross-workstream integrity check (§11).
5. Compile into a single `AUDIT_REPORT.md` with:
   - Executive summary (total findings by severity)
   - Per-workstream findings (grouped)
   - Cross-workstream checks
   - Priority fix list (top 10 by impact)
   - Appendix: verified-correct items

### Quality Standards
- **Every finding must have evidence** — a code snippet, a calculation, or a specific line reference
- **Every finding must have a quantified impact estimate** where possible (e.g., "changes NPV by ~$X00M", "changes LCOE by ~X¢/kWh", "reverses S6 vs S7 ranking")
- **Every finding must have a specific, actionable recommendation** — not just "fix this" but "change line X from Y to Z"
- **False positives are acceptable** (better to flag and confirm correct than to miss a bug) but should be minimised through careful analysis
- **The prior v1 audit found and fixed 30 issues** — this v2 audit should assume those fixes are in place but may verify them. Focus effort on **new findings** and **deeper analysis** that v1 didn't cover (especially economic methodology, parameter validity, and big-picture concerns).
