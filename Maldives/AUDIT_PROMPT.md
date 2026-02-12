# COMPREHENSIVE AUDIT v2 — Maldives Energy CBA Model

> **Date:** 10 February 2026  
> **Scope:** Full-depth, clean-sheet professional audit — economic methodology, code correctness, parameter validity, wiring integrity, structural soundness, numerical reproducibility, and publication readiness  
> **Designed for:** Multi-agent execution (9 independent audit workstreams)  
> **Audit philosophy:** **ZERO TRUST.** This is a clean-sheet re-examination. Prior audits exist (`AUDIT_REPORT_v1.md`, `AUDIT_REPORT_v3.md`) but their conclusions are NOT assumed correct. Every aspect of the model is re-examined from first principles. Prior fixes may have introduced new bugs, may have been incomplete, or may have been wrong. Do not read prior audit reports before completing your own workstream — they are reference material for the cross-workstream integration check only.
>
> The goal is a **publication-quality** audit that an independent reviewer could trust as the definitive assessment of this model's correctness, regardless of what prior reviews found.

---

## 1. Project Overview

### What This Model Does

A **social Cost-Benefit Analysis (CBA)** of energy transition pathways for the Maldives, comparing 7 scenarios over 2026–2056:

| Code | Scenario | Key Technology | Key CAPEX |
|------|----------|---------------|-----------|
| S1 | BAU (Status Quo) | ~93% diesel + ~7% existing solar (68.5 MW), no new investment | Diesel replacement only |
| S2 | Full Integration | 700 km India–Maldives HVDC submarine cable + domestic RE | ~$2.5B cable + RE ramp |
| S3 | National Grid | Inter-island submarine cables + aggressive RE ramp | Inter-island cables + RE |
| S4 | Islanded Green | Per-island solar+battery mini-grids (no interconnection) | Distributed mini-grids |
| S5 | Near-Shore Solar | Solar farms on uninhabited islands + cable to inhabited | 104 MW near-shore + cables |
| S6 | Maximum RE | Floating solar (195 MW) + near-shore + ground-mount | Floating + near-shore + ground |
| S7 | LNG Transition | 140 MW LNG plant at Gulhifalhu + RE complement | LNG plant + RE ramp |

The model produces NPV, BCR, IRR, LCOE, emission trajectories, distributional impacts, sensitivity analysis (39 params), Monte Carlo simulation (1,000 iterations), multi-criteria analysis (8 criteria × 7 scenarios), financing analysis, and transport supplementary analysis.

### Architecture

```
parameters.csv (~420 parameter rows, 8 columns)
    │
    ▼
config.py (23 dataclasses, ~2,130 lines)
    │  load_parameters_from_csv() → get_config()
    ▼
┌──────────────────────────────────────────────────────┐
│  demand.py → costs.py → emissions.py                 │
│  dispatch.py (hourly simulation)                      │
│  least_cost.py (183-island LCOE engine)               │
│  network.py (inter-island distances, MST)             │
│                                                       │
│  scenarios/                                           │
│    __init__.py (BaseScenario, GenerationMix,           │
│                 AnnualCosts, AnnualBenefits)           │
│    status_quo.py  one_grid.py                         │
│    green_transition.py  islanded_green.py             │
│    nearshore_solar.py  maximum_re.py                  │
│    lng_transition.py                                  │
│                                                       │
│  cba/                                                 │
│    npv_calculator.py (NPV, BCR, IRR, salvage, DDR)    │
│    sensitivity.py (39-param engine, MC)                │
│    mca_analysis.py (8-criteria weighted scoring)       │
│                                                       │
│  Runners:                                             │
│    run_cba.py  run_sensitivity.py                     │
│    run_monte_carlo.py  run_multi_horizon.py           │
│                                                       │
│  Supplementary:                                       │
│    financing_analysis.py  distributional_analysis.py  │
│    transport_analysis.py  sanity_checks.py            │
└──────────────────────────────────────────────────────┘
    │
    ▼
outputs/*.json → report/REPORT...qmd
```

### Current Model Outputs (as of audit date)

| Scenario | PV Total Cost ($B) | LCOE ($/kWh) | BCR | IRR | NPV Savings vs BAU ($B) |
|----------|--------------------|--------------|-----|-----|------------------------|
| S1 BAU | 15.68 | 0.437 | — | — | — |
| S2 Full Integration | 9.29 | 0.210 | 4.06 | 16.3% | 6.39 |
| S3 National Grid | 9.22 | 0.293 | 7.32 | 33.9% | 6.46 |
| S4 Islanded Green | 10.00 | 0.318 | 5.54 | 27.7% | 5.68 |
| S5 Near-Shore Solar | 8.78 | 0.279 | 6.69 | 33.4% | 6.90 |
| S6 Maximum RE | 8.23 | 0.262 | 5.98 | 33.2% | 7.44 |
| S7 LNG Transition | 7.83 | 0.218 | 7.06 | 41.4% | 7.85 |

**Ranking by NPV savings:** S7 > S6 > S5 > S3 > S2 > S4 > S1

### Codebase Size

- **30 Python files**, **~15,900 lines** total
- **~420 parameter rows** in parameters.csv (8 columns: Category, Parameter, Value, Low, High, Unit, Source, Notes)
- **23 dataclasses** in config.py with ~320+ fields
- **39 sensitivity parameters** (35 core + 4 conditional transport), 1,000 MC iterations
- **48 automated sanity checks** (all currently passing)

---

## 2. Audit Design — Nine Workstreams

This audit uses **9 independent workstreams**, each examining a distinct dimension of the model. Each workstream is self-contained and should be executed without reference to the others.

### Workstream Overview

| # | Workstream | Focus | Key Files | What It Should Catch |
|---|-----------|-------|-----------|---------------------|
| **A** | **Economic Methodology & CBA Framework** | Is the CBA structurally sound as economics? | npv_calculator.py, scenarios/__init__.py, run_cba.py | Wrong counterfactual, missing cost/benefit categories, discounting errors, BCR/IRR definition errors, welfare measurement gaps, standing issues, double-counting |
| **B** | **Parameter Validity & Empirical Grounding** | Are the ~420 parameters defensible? | parameters.csv, config.py, literature_benchmarks.md | Outdated sources, wrong values, fabricated citations, missing uncertainty ranges, geographic mismatches, internal inconsistencies |
| **C** | **Code Correctness & Equation Fidelity** | Does every equation in code match its mathematical specification? | costs.py, demand.py, emissions.py, dispatch.py, npv_calculator.py, sensitivity.py | Unit mismatches, sign errors, off-by-one, wrong formula, vintage/cohort bugs, numerical instability, edge cases |
| **D** | **Config Wiring & Data Pipeline Integrity** | Does every parameter flow correctly from CSV → config → code? | parameters.csv, config.py, all consuming .py | Broken wiring, stale defaults masking CSV, hardcoded values, dead params, silent exception swallowing, type coercion errors |
| **E** | **Scenario Consistency & Comparative Logic** | Are the 7 scenarios internally consistent and comparisons fair? | All 7 scenario files, scenarios/__init__.py | Different base assumptions, missing cost/benefit categories, config key mismatches, generation imbalance, unfair comparisons, deployment infeasibility |
| **F** | **Sensitivity, Monte Carlo & Robustness** | Is the uncertainty analysis methodologically sound? | sensitivity.py, run_sensitivity.py, run_monte_carlo.py, run_multi_horizon.py | Parameter path desync, ranges too narrow/wide, missing correlations, non-convergence, missing scenarios, switching value errors |
| **G** | **Supplementary Modules & Outputs** | Are the supporting analyses correct? | distributional, financing, transport, mca, sanity_checks | Microdata handling errors, grant element formula, MCA polarity/weight issues, transport S-curve problems, sanity check coverage |
| **H** | **Numerical Stability & Reproducibility** | Is the model deterministic, stable, and reproducible? | All model code, outputs/*.json | Floating-point edge cases, IRR non-convergence, random seed, platform dependence, data loading errors |
| **I** | **Publication Readiness & Output Integrity** | Do outputs match code, and report match outputs? | outputs/*.json, run_cba.py, REPORT.qmd | JSON output gaps, report hardcoded values, documentation inconsistencies, claim verification, plausibility checks |

---

## 3. Workstream A — Economic Methodology & CBA Framework

### Objective
Assess CBA structural soundness against Boardman et al. (2018), ADB (2017), HM Treasury (2026), and IRENA (2019).

### What to Read
1. `model/cba/npv_calculator.py` — full NPV/BCR/IRR/salvage/DDR engine
2. `model/scenarios/__init__.py` — `AnnualCosts`, `AnnualBenefits`, `GenerationMix`, `BaseScenario`
3. `model/run_cba.py` — scenario execution and comparison
4. `CBA_METHODOLOGY.md` — equation catalogue
5. `SCENARIO_GUIDE.md` — design rationale

### A1. Counterfactual Design
- **BAU diesel replacement CAPEX:** Does S1 include the cost of replacing aging diesel generators (20-year life)? Generators installed 2006–2026 would need replacement 2026–2046. If BAU omits replacement CAPEX, all alternatives are artificially advantaged. Verify `status_quo.py` includes diesel CAPEX additions.
- **BAU frozen technology:** Does BAU assume zero technological progress? Zero policy change? Is this the right "most likely without project" or a straw-man?
- **BAU demand ceiling:** At 5%/yr for 30 years, demand reaches 5,188 GWh (2056). For 515,000 people, this is ~10,000 kWh/capita — approaching OECD average. Is there a saturation mechanism? Does the Malé three-phase trajectory provide this? Does the outer-island trajectory have one?
- **BAU grid losses:** Does BAU include grid losses that worsen over time (aging infrastructure without investment)?
- **BAU environmental baseline:** Does BAU include the cost of environmental damage from diesel (SCC, health)? If yes, this inflates the BAU cost baseline, making all alternatives look better. In strict CBA, the counterfactual should NOT include externalities unless they are already being paid. Verify whether BAU includes `emission_costs` and `health_benefits` — it should include emission externality costs but NOT health benefits (those are benefits of the alternative, not costs of the status quo).

### A2. Cost-Benefit Accounting
- **Subsidy avoidance:** The model includes `fiscal_subsidy_savings` as a benefit ($0.15/kWh × diesel displaced). Subsidies are fiscal transfers, not economic costs (Boardman Ch. 4). Verify: is subsidy included or excluded from `AnnualBenefits.total`? Is it included in BCR/NPV? If included, this is double-counting with avoided fuel cost (the subsidy IS part of the fuel cost to government). Check both the `total` property and any `total_with_fiscal` variant.
- **Environmental externalities:** The model monetises environmental damage at $10/MWh (noise $5 + spill $3 + biodiversity $2). Verify: (a) is this properly discounted in the NPV calculation or just accumulated undiscounted? (b) is it included in BCR and IRR, or only NPV? (c) is there overlap with emission benefits (SCC covers climate damage — does the $10/MWh environmental damage also include climate components? If so, double-counting).
- **Fuel savings definition:** `fuel_savings = BAU_fuel − scenario_fuel`. But BAU fuel cost includes the subsidy component. If BAU pays $0.85/L and the subsidy makes it $1.00/L to government, which price is used? Verify economic (resource) cost, not financial cost.
- **Standing:** Whose costs and benefits count? (Boardman Ch. 2). Is this a national standing (only Maldives residents) or global standing (including India's costs for S2 cable)? The answer affects whether India's infrastructure costs should be included.
- **Double discounting risk:** Environmental benefits use SCC which has its own internal discount rate (EPA uses 2%). The CBA then discounts these at 6%. Is this double discounting? Check whether the SCC is a present-value-equivalent or a year-specific damage.
- **Benefit stream completeness:** Enumerate every benefit stream the model calculates. Then check: is each one (a) correctly discounted, (b) included in PV total benefits, (c) included in BCR numerator, (d) included in IRR cash flow? A common bug is calculating a benefit but forgetting to wire it into the NPV/BCR/IRR aggregation. (Cross-reference with E5 for per-scenario verification.)

### A3. Discounting
- **DDR implementation:** The model includes a Declining Discount Rate (DDR) sensitivity path using HM Treasury Green Book rates (3.5%→ 3.0%→2.5%). But the model’s base rate is 6%, not 3.5%. Verify: does the DDR path use HM Treasury rates directly (replacing the 6% base), or does it scale the base rate downward proportionally? If it replaces 6% with 3.5%, that’s a 42% reduction in discount rate — enormous and potentially inappropriate for a developing-country CBA.
- **Base year convention:** What year is t=0? If 2026 is the base year, costs in 2026 should have DF=1.0, costs in 2027 should have DF=1/(1.06). Verify this is implemented correctly — off-by-one here compounds over 30 years.
- **Constant vs. declining prices:** Are all costs in constant 2026 USD? If fuel escalates at 2%/yr real, this is already in real terms. But if some costs are in nominal terms and others in real terms, the discounting framework breaks.
- **Discount rate sensitivity:** The model uses 6%. ADB recommends 9–12% for developing countries. At 12%, long-run benefits (years 20–30) are discounted 5× more than at 6%. Does the sensitivity analysis test discount rate at 9% and 12%?

### A4. Incremental Analysis
- **BCR definition:** BCR = PV(total benefits) / PV(total costs) OR BCR = PV(net benefits) / PV(investment costs)? The former includes fuel savings in benefits; the latter treats fuel savings as reduced costs. Both are valid but give different numbers. Which does the model use? Verify consistency with ADB (2017) definition.
- **IRR cash flow content:** Which benefit streams are included in the IRR calculation? Check line by line — is it only fuel savings, or does it also include emission/health/reliability/environmental benefits? Missing streams understate IRR; including transfers (subsidy) overstates it.
- **IRR sign convention:** Benefits should be positive in the IRR cash flow, CAPEX/costs negative. Verify this is correct. A sign error here would produce nonsensical IRR values.
- **Switching value plausibility:** `run_sensitivity.py` computes switching values (parameter value where two scenarios tie). Verify: (a) linear interpolation is appropriate (NPV is often nonlinear in parameters), (b) switching values are within physically plausible ranges.

### A5. Structural Concerns
- **S2 cost-sharing:** At 100% GoM financing, the India cable has BCR 4.06. If India pays 50%, GoM BCR roughly doubles. The model should present BCR under multiple cost-sharing assumptions (0%/50%/70% India share). Does `run_cba.py` do this?
- **Technology lock-in:** The model treats each scenario as a single 30-year commitment. But in reality, S3 (National Grid) can evolve toward S2 (Full Integration) if circumstances change. Is this option value captured anywhere? (See SOTA assessment G2 — real options.)
- **Sunk cost treatment:** S1 BAU includes the existing 68.5 MW of solar. This is a sunk cost. Do alternatives also include this as sunk (not re-costed)?
- **Replacement cycles:** Solar (30yr), battery (15yr), diesel (20yr). Over a 30-year horizon, batteries need one replacement. Is this replacement CAPEX included in all scenarios? Is battery replacement at year 15 costed at the year-15 price (with decline) or the year-0 price?
- **Terminal year treatment:** Year 2056 is the final year. Is generation in 2056 included in cumulative calculations? Is salvage value computed at end of 2056 or beginning of 2057?

### A6. Welfare Measurement
- **No consumer surplus:** The model measures costs and externalities but not consumer surplus changes. If RE lowers electricity prices, consumer surplus increases. For a 30-year analysis where prices may change significantly, this is a meaningful omission. Quantify: if RE LCOE is $0.20/kWh vs. BAU $0.44/kWh, and demand is 2,000 GWh, the consumer surplus triangle ≈ ½ × ΔP × ΔQ ≈ $120M/yr. Over 30 years discounted, this could be $1B+.
- **No producer surplus:** STELCO's profitability under different scenarios. Does the model include stranded asset losses for STELCO's diesel fleet?
- **Distributional weighting:** Does the NPV apply distributional weights (higher weight for benefits to poor households)? Boardman (2018) Ch. 17 recommends this. The distributional analysis module exists but is it integrated into the NPV calculation?

---

## 4. Workstream B — Parameter Validity & Empirical Grounding

### Objective
Verify every key parameter is (a) plausible, (b) sourced from a credible recent reference, (c) appropriate for Maldives, (d) has reasonable uncertainty bounds, and (e) matches what the cited source actually says.

### What to Read
1. `model/parameters.csv` — all ~420 parameter rows
2. `model/config.py` — dataclass defaults
3. `Maldives/literature_benchmarks.md`
4. `Maldives/data/addiitonal_maldives_cba_parameters_sources.md`
5. `Maldives/data/maldives_cba_parameters_sources_batch2.md`

### B1. Source Verification (Spot-Check Top 30 Parameters)
For the **top 30 most impactful parameters** (those that appear in sensitivity analysis), verify that the **cited source actually says what the model claims**:
- Read the source (or abstract). Does it give the exact value used?
- Is the value for the correct geography (Maldives, SIDS, global)?
- Is the value for the correct year (2020+ unless canonical)?
- Is the value in the correct units (convert if needed)?
- Is it the central estimate, or a bound?

Priority parameters for source verification:
| Parameter | Value | Cited Source | Verify |
|-----------|-------|-------------|--------|
| `solar_pv_capex` | $1,500/kW | AIIB Maldives Solar (2021) | Is $1,500 what AIIB actually quotes? Has it been updated? |
| `battery_capex_kwh` | $350/kWh | BNEF 2025 | Is $350 the BNEF figure for island systems, or is it lower? |
| `health_damage_cost_per_mwh` | $40/MWh | Parry et al. (2014) | Does the IMF WP give $40/MWh specifically, or is this derived? |
| `social_cost_carbon` | $51/tCO₂ | EPA IWG 2023 | Is $51 the 3% or 2% discount rate figure? Which scenario? |
| `diesel_emission_factor` | 0.72 kg/kWh | IPCC 2006 | Does IPCC give 0.72 for diesel generators specifically? |
| `cable_capex_per_km` | $3.0M/km | Multiple (8 refs) | Do the 8 references support $3.0M/km for Indian Ocean depths? |
| `discount_rate` | 6% | ADB SIDS standard | Does ADB actually recommend 6% for SIDS, or is it higher? |
| `base_demand_gwh` | 1,200 GWh | IRENA 2022 × growth | What was actual 2024/2025 demand? Is 1,200 GWh correct for 2026? |
| `demand_growth_rate` | 5% | IRENA CAGR | Was IRENA's 5.1% for 2010–2020? Is it appropriate to extrapolate? |
| `Diesel Price 2026` | $0.85/L | Average Maldives import | What was actual 2024/2025 import price? |

### B2. Temporal Validity
- Flag every parameter source older than 2020 that is NOT a canonical standard (IPCC 2006, IEC 61215).
- For technology costs (solar, battery, cable), sources from 2021 may be significantly outdated by 2026. IRENA RPGC 2024 and BNEF 2025 should be the primary references.
- For demand data, the base is Island Electricity Data Book 2018. That is 8 years old. Has demand data been updated?

### B3. Maldives-Specificity Scoring
Rate each parameter on a 3-point scale:
- **M** (Maldives-specific): Value comes from Maldives data/studies
- **S** (SIDS-generic): Value from SIDS literature but not Maldives-specific
- **G** (Global): Value from global average or non-SIDS context

Flag any parameter rated **G** where a **M** or **S** value is available.

### B4. Uncertainty Range Adequacy
For each of the 39 sensitivity parameters:
- Is the Low/High range derived from the source or assumed?
- Is the range symmetric? If so, is asymmetry warranted? (e.g., solar CAPEX has more room to fall than rise → asymmetric Low wider than High)
- Common problems: ±10% when ±50% is realistic; ±50% when ±10% is the actual empirical variation
- Special attention: discount rate (Low 3%, High 12%?), SCC (Low $51, High $190 — but could be higher under Stern), fuel price (±50% volatility is historical)

### B5. Internal Consistency Between Parameters
Check that related parameters are consistent:
- `base_demand_gwh` (1,200 GWh) ÷ `base_peak_demand_mw` (200 MW) = 6,000 hours. At 8,760 hrs/yr, LF = 0.685. Does this match `load_factor` (0.68)?
- `diesel_fuel_price` ($0.85/L) × `diesel_fuel_efficiency` (3.3 kWh/L) = $0.258/kWh fuel cost. Combined with O&M, does BAU LCOE come out to ~$0.44/kWh?
- `solar_pv_capex` ($1,500/kW) / `solar_lifetime` (30 yr) = $50/kW/yr. At 17.5% CF → 1,533 kWh/kW/yr. Levelised CAPEX = $32.6/MWh. Plus O&M ($10/kW/yr = $6.5/MWh). Total ~$39/MWh solar LCOE. Does this match the model's solar LCOE?
- `cable_capex_total` should equal `cable_length × cable_capex_per_km + converters + landing + IDC + grid`. Verify the calculation.

### B6. Recently Added Parameters
Check whether any parameters appear to have been added as patches rather than being part of the original design. Signs of patch parameters:
- Source column says "estimated", "assumed", or cites a very broad source
- Low/High bounds are round numbers suggesting guesswork (e.g., exactly ±50%)
- Parameter is only used in one place (may have been added to fix a specific issue)
- Parameter duplicates or overlaps with an existing parameter

Specific parameters to scrutinise:
- Reliability parameters (SAIDI, SAIFI) — are these sourced from Maldives data or generic?
- Exchange rate (MVR/USD) — is it used anywhere in the model, or is it dead?
- GDP growth rate — is it used for financing analysis? Does it match IMF projections?
- MCA scores for individual scenarios — are these evidence-based or subjective?
- WTE emission factor bounds — is zero a plausible lower bound for waste-to-energy?

---

## 5. Workstream C — Code Correctness & Equation Fidelity

### Objective
Verify every mathematical formula matches its intended equation with correct units, signs, and edge-case handling.

### What to Read
Every `.py` file in `model/` and `model/cba/` and `model/scenarios/`. Cross-reference against `CBA_METHODOLOGY.md`.

### C1. Demand Module (`demand.py`)
- **Compound growth:** $D(t) = D_0 \times (1+g)^{t-t_0}$
  - Verify exponent uses `t - base_year`, not `t - 1`
  - Verify units are GWh throughout
  - Does growth apply BEFORE or AFTER sectoral split?
- **Malé three-phase trajectory:**
  - Phase 1 (near-term): verify taper rate
  - Phase 2 (post-peak): verify deceleration
  - Phase 3 (long-run floor): verify it's applied
  - Does Malé share + outer share = 1.0 for every year?
- **Price elasticity:**
  - $\Delta D = \varepsilon \times (\Delta P / P) \times D$
  - Verify sign: ε = −0.3, price decrease → demand increase (positive ΔD for negative ΔP)
  - Applied only to S2 (Full Integration)? Verify this is intentional.
- **Sectoral split:**
  - `residential_share + commercial_share + public_share == 1.0`?
  - Is this enforced at load time or just assumed?

### C2. Cost Module (`costs.py`)
- **Solar CAPEX with decline + climate:**
  $C(t) = C_0 \times (1-d)^{t-t_0} \times (1 + \alpha_{climate})$
  - Verify: is there a method that computes year-specific solar CAPEX? Or is CAPEX only calculated at base year?
  - Verify: climate premium is applied ONCE (not compounded with learning curves)
  - Verify: CAPEX decline compounds from the correct base year
  - Verify: units are $/kW throughout
- **Vintage-based degradation (CRITICAL — most complex formula):**
  - Sum over cohorts: $G_{total}(t) = \sum_{v} MW_v \times CF \times 8760 \times (1 - k_t \Delta T) \times (1 - d_{deg})^{t-v}$
  - Where $v$ is the installation year of each cohort
  - Verify: each cohort degrades from ITS install year, not from the base year
  - Verify: the OPEX calculation — if OPEX is per-kW, the denominator when converting from total to per-kW must be correct (should be `/ 1000` to convert MW to kW, NOT `/ (mw * 1000)` which would make per-kW OPEX inversely proportional to fleet size)
  - Verify: total solar generation across vintages matches expectations (rough check: 100 MW × 0.175 CF × 8760 = 153 GWh)
- **Battery LCOE in least_cost.py:**
  - The `_discounted_lcoe()` function calculates technology LCOE for per-island screening
  - Verify: does the battery LCOE calculation include generation degradation in its denominator? Or does it use undegraded generation (which would understate battery LCOE)?
  - Conceptual question: the generation degradation is a SOLAR effect (PV panel degradation). When computing battery LCOE as part of a solar+battery system, the denominator should use the DEGRADED solar generation. Verify this is the case.
- **Diesel two-part fuel curve:**
  $F_{litres} = C_{kW} \times a + G_{kWh} \times b$
  - Verify $a = 0.08145$ L/kW (idle consumption) and $b = 0.246$ L/kWh (proportional)
  - Verify units: result should be in litres per hour (or per year if annualised)
  - At min load 40%: fuel = (a + b × 0.4 × rated) × rated. Verify this matches dispatch.py
- **T&D loss gross-up:**
  - Multiplicative: $G_{gross} = G_{net} / \prod(1 - loss_i)$
  - Year-dependent: Malé share changes over time → weighted average loss changes
  - Verify the weighting is correct: higher Malé share → lower loss (Malé has better grid)
  - Verify HVDC cable loss (4%) is applied only to S2 (cable import scenarios)
- **Learning curves (Wright's Law) in costs.py:**
  - $C(t) = C_0 \times (Q(t)/Q_0)^{-\alpha}$
  - Verify: solar learning rate 20%, battery 18% per doubling
  - Verify: $\alpha = \ln(1/(1-LR))/\ln(2)$ — solar α=0.322, battery α=0.286
  - Verify: cumulative deployment Q(t) grows correctly (global + Maldives?)
  - Are exogenous and endogenous (learning curve) cost trajectories both available and correctly toggled?

### C3. Emissions Module (`emissions.py`)
- **Unit chain:** GWh × 10⁶ kWh/GWh × EF (kg/kWh) / 10³ (kg/tonne) = tonnes CO₂
  - Verify: no 1000× error (v1 found one in lifecycle emissions)
  - Verify: LNG emission factor (0.40 kgCO₂/kWh) is distinct from diesel (0.72)
- **SCC with growth:**
  $SCC(t) = SCC_0 \times (1 + g_{SCC})^{t-t_0}$
  - At 2%/yr growth: SCC(2056) = $51 × 1.02³⁰ = $92.5/tCO₂
  - Verify: is this applied to the emission REDUCTION (scenario vs BAU), not absolute emissions?
- **India grid emission factor decline:**
  - Starting EF 0.70, declining 2%/yr: EF(2056) = 0.70 × 0.98³⁰ = 0.38 kgCO₂/kWh
  - Verify: this makes India imports increasingly clean over time (correct trend)
  - Verify: this is applied only to S2

### C4. Dispatch Module (`dispatch.py`)
- **Battery SOC tracking:**
  - Charge: $SOC_{t+1} = SOC_t + P_{charge} \times \eta_{charge}$, capped at capacity
  - Discharge: $SOC_{t+1} = SOC_t - P_{discharge} / \eta_{discharge}$, floored at $(1-DoD) \times capacity$
  - Verify: round-trip efficiency 88% is correctly split (√0.88 each way, or asymmetric?)
  - Verify: self-discharge rate is applied hourly
- **Diesel minimum load:**
  - 40% minimum when generator is ON
  - Can the generator be OFF (when solar + battery meet 100% of demand)?
  - Verify: when generator is ON at min load, excess generation is curtailed (not stored)
- **Solar output per hour:**
  - GHI profile from `data/supplementary/GHI_hourly.csv`
  - Temperature profile from `data/supplementary/Temperature_hourly.csv`
  - Cell temperature: $T_{cell} = T_{amb} + 25.6 \times GHI_{kW/m²}$
  - Verify: GHI units match between hourly file and formula (kWh/m²/day vs kW/m²)
- **LPSP calculation:**
  - $LPSP = \sum \text{unmet\_hours} / 8760$
  - Verify: unmet energy (kWh not served) would be more informative than unmet hours

### C5. NPV Calculator (`npv_calculator.py`)
- **Discount factor at base year:**
  - $DF(t_0) = 1.0$ (costs at base year are undiscounted)
  - Verify: is year 0 the base year or year 1?
- **DDR implementation (CRITICAL):** (Cross-reference A3 for economic assessment of DDR appropriateness.)
  - HM Treasury schedule: 3.5% for years 0–30, 3.0% for years 31–75, 2.5% for 76+
  - For this model (30-year horizon), only the 3.5% step applies
  - Verify: the DDR discount factor is a CUMULATIVE PRODUCT, not a simple rate substitution
  - $DF_{DDR}(t) = \prod_{s=1}^{t} \frac{1}{1+r(s)}$ where $r(s)$ depends on the step
  - But wait: if the project is only 30 years, does the DDR ever kick in? Only in multi-horizon (50yr)?
- **Salvage value:**
  - $SV_{asset} = \frac{remaining\_life}{total\_life} \times original\_cost$
  - Discounted at terminal year: $SV_{total} = \sum_{assets} SV_{asset} \times DF(T)$
  - Verify: battery installed at year 15 has 0 years remaining at year 30 (exact lifetime match — no salvage)
  - Verify: solar installed at year 0 has 0 years remaining at year 30 (exact match — no salvage)
  - Verify: solar installed at year 5 has 5 years remaining at year 30 → salvage = 5/30 × cost
  - What about diesel generators? Are they included in salvage?
- **IRR bisection:**
  - Verify: the cash flow used for IRR — which benefit streams are included? Are ALL benefit streams (fuel, emission, health, reliability, environmental) present, or only a subset?
  - Verify: convergence tolerance is appropriate (±0.01% or better)
  - Verify: search bounds [-50%, +200%] are wide enough for all scenarios
  - Verify: what happens when IRR doesn't converge? Is there a fallback (e.g., `numpy_financial.irr`)?

### C6. Sensitivity Engine (`sensitivity.py`)
- **Config deep copy:** Verify `_modify_config()` uses `copy.deepcopy()` — not `dataclasses.replace()` which is shallow
- **Growth rate modification:** Are growth rates scaled proportionally (base ± X%) or replaced with absolute values? Proportional is correct.
- **Cable CAPEX recomputation:** When `cable_capex_per_km` changes in sensitivity, is `cable_capex_total` recalculated?
- **Transport parameters:** Are all 4 transport parameters (`ev_adoption_rate`, `ev_premium_pct`, `ev_electricity_kwh_per_km`, `transport_health_benefit_per_km`) included in the sensitivity engine? Are they in all 3 modification paths (`_modify_config`, `_define_parameters`, parameter list)?

---

## 6. Workstream D — Config Wiring & Data Pipeline Integrity

### Objective
Verify the complete parameter pipeline from CSV to consumption.

### What to Read
1. `model/parameters.csv` — every row
2. `model/config.py` — every dataclass, `load_parameters_from_csv()`, `get_config()`
3. All consuming `.py` files

### D1. Category Validation
- Does `load_parameters_from_csv()` validate that expected CSV categories are present?
- If a category is missing or misspelled in the CSV, does the loading fail loudly or silently use defaults?
- List all unique `Category` values in parameters.csv. Are they consistent (no typos, no duplicates with different spellings)?
- Is there any validation at load time that critical parameters were successfully loaded? Or could a corrupt/truncated CSV produce a config with all-default values silently?

### D2. Dead Parameter Census (Systematic)
For EVERY field in EVERY dataclass in config.py:
1. Search for `config.xxx.field_name` across all `.py` files
2. If not found, is it used indirectly (e.g., `getattr(config.xxx, param_name)`)?
3. If genuinely unused, list it as dead code

Known suspects (verify each): `maintenance_vessel_annual`, `who_mortality_rate_per_gwh`, `initial_re_share_outer`, `battery_discharge_gwh`. Are there more?

### D3. Hardcoded Value Sweep (Expanded)
Search EVERY `.py` file for:
- **Dollar amounts:** `\d{3,}` (3+ digit numbers) that look like costs
- **Percentages:** `0\.\d{2,}` patterns that look like rates
- **Years:** `20[2-5]\d` patterns that should come from config
- **Capacity:** values followed by MW, kW, GWh comments
- **getattr with fallback:** `getattr\(.*,\s*\d+` patterns
- **.get with default:** `\.get\(.*,\s*\d+` patterns

Known exceptions: mathematical constants (8760, 1000, 1e6, 100, 365, 12, 24, π)

### D4. CSV↔Config Field Alignment
Generate two lists:
1. All `Parameter` values in parameters.csv
2. All field names across all 23 dataclasses

Flag:
- CSV rows that have NO matching field in any dataclass
- Config fields that have NO matching CSV row AND no clear derivation
- Fields where the CSV `Value` column does NOT match the dataclass default

### D5. Silent Failure Patterns
Search for patterns that could mask loading errors:
- `except Exception:` or `except:` (bare except) — these swallow ALL errors including CSV parsing failures
- `try/except` blocks in config loading that catch too broadly
- `getattr(obj, field, numeric_default)` — if the attribute is missing, a hardcoded fallback silently takes over
- `.get(key, numeric_default)` in dictionary lookups that mask missing CSV rows
- Default parameter values in function signatures with domain-specific numbers
- `if hasattr(config, 'field'):` patterns that silently skip missing fields

For every `except` block found: what specific exception should it catch instead? Is there logging of the caught error?

### D6. Config Field Type Safety
- Are all numeric fields in dataclasses typed as `float` (not `str`)? Could a CSV parsing error leave a string in a numeric field?
- Are there any `int` fields that should be `float` (or vice versa)?
- Is `load_parameters_from_csv()` using `float()` conversion consistently?

---

## 7. Workstream E — Scenario Consistency & Comparative Logic

### Objective
Verify 7 scenarios are internally consistent and comparisons are fair.

### What to Read
1. All 7 scenario files in `model/scenarios/` + `model/scenarios/__init__.py`
2. `model/run_cba.py` — scenario execution and comparison
3. `model/costs.py` — cost calculation functions called by scenarios
4. `SCENARIO_GUIDE.md` — design rationale for each scenario

### E1. Common Assumptions
Every scenario must use identical:
- Base year (2026), end year (2056)
- Discount rate (6%)
- Base demand (1,200 GWh)
- Diesel emission factor (0.72 kgCO₂/kWh)
- SCC ($51/t + 2%/yr)
- Climate adaptation premium (7.5%)
- Health damage ($40/MWh)

**Test:** Read each scenario's `__init__` or `calculate_annual_data` method. Do they all call `get_config()` once and use the same config object?

### E2. Generation Balance Identity (Year by Year)
For each scenario and year: $Demand_{gross} = G_{diesel} + G_{solar} + G_{import} + G_{LNG} + G_{WTE} + G_{curtailed}$
- Run the model and extract year-by-year generation mix from outputs
- Verify the identity holds (tolerance: ±0.1 GWh per year)
- Check specifically at boundary years: 2026 (start), 2031 (LNG online in S7), 2040 (mid), 2056 (end)

### E3. Config Key Lookups Per Scenario
Each scenario uses a config key to look up its growth rate and other parameters. Verify for EVERY scenario:
- What config key does it use for demand growth? (e.g., `"status_quo"`, `"green_transition"`, `"lng_transition"`)
- Does the key match the scenario's identity? (A past bug had S7 LNG using S3’s growth rate key)
- Does the growth rate retrieved match the expected value?
- Are there ANY other config lookups (not just growth rate) that could use wrong keys?
- Specifically check: `_scenario_growth_rate()`, `_init_demand_projector()`, and any comment/docstring that says one scenario name but the code references another

### E4. Cost Completeness Matrix
Verify each cost category is present where expected:

| Cost | S1 | S2 | S3 | S4 | S5 | S6 | S7 |
|------|----|----|----|----|----|----|-----|
| Diesel replacement CAPEX | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Diesel fuel | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Solar CAPEX | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Battery CAPEX + replacement | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| HVDC cable | — | ✓ | — | — | — | — | — |
| Inter-island cables | — | — | ✓ | — | ✓ | ✓ | — |
| Near-shore cables | — | — | — | — | ✓ | ✓ | — |
| Import electricity (PPA) | — | ✓ | — | — | — | — | — |
| LNG plant CAPEX | — | — | — | — | — | — | ✓ |
| LNG fuel | — | — | — | — | — | — | ✓ |
| WTE | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Connection cost | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Floating solar premium | — | — | — | — | — | ✓ | — |

### E5. Benefit Completeness
(Cross-reference A2 for economic correctness of benefit definitions; this section verifies per-scenario implementation.)
Verify each benefit stream exists and uses correct BAU baseline:
- **Fuel savings:** (BAU fuel − scenario fuel). Does this include LNG fuel for S7? Or is LNG fuel a separate field?
- **Emission benefit:** (BAU emissions − scenario emissions) × SCC(t). Verify sign and units.
- **Health benefit:** diesel_gwh_reduction × $40/MWh. What exactly is “diesel_gwh_reduction” calculated against? Is it the BAU diesel GWh, or the scenario’s own prior-year diesel?
- **Reliability benefit:** SAIDI-based. Is there a cable availability discount for S2 (HVDC cable can fail)?
- **Environmental benefit:** $10/MWh. Verify: is this calculated, discounted, and included in NPV/BCR/IRR? Or calculated but not wired into the aggregation?
- **Subsidy avoidance:** Is it included or excluded from the economic NPV? It should be EXCLUDED (fiscal transfer). Verify.
- **Connection benefit:** New connections × WTP. Present in S2–S7?

### E6. Deployment Schedules
For each scenario, extract the RE deployment trajectory (MW solar by year, MW battery by year):
- Is the ramp-up physically plausible? (Historical SIDS maximum ~20 MW/yr)
- Do any scenarios deploy faster than the local construction workforce can support?
- Is there a lag between CAPEX spending and generation (construction period)?

### E7. Scenario Interaction / Independence
- S5 (Near-Shore) and S6 (Maximum RE) both include near-shore solar. If implemented sequentially, S5 is a subset of S6. Is this handled? Or are they independent alternatives?
- S3 (National Grid) and S4 (Islanded Green) represent opposite ends of a centralisation spectrum. Can the model represent hybrid approaches?

---

## 8. Workstream F — Sensitivity, Monte Carlo & Robustness

### Objective
Verify uncertainty analysis is methodologically sound.

### What to Read
1. `model/cba/sensitivity.py` (~1,011 lines)
2. `model/run_sensitivity.py` (~697 lines)
3. `model/run_monte_carlo.py` (~385 lines)
4. `model/run_multi_horizon.py` (~375 lines)

### F1. Three-Path Synchronisation
The 39 sensitivity parameters must be handled identically in:
- `sensitivity.py:_modify_config()` — for one-way sensitivity
- `sensitivity.py:_modify_config_inplace()` — for Monte Carlo
- `run_sensitivity.py:modify_config()` — for the runner

**Test:** For each of the 39 parameters, verify all 3 paths handle it with the same transformation.

### F2. Parameter Range Validation
For each of the 39 sensitivity parameters, check:
- Do Low/High match `parameters.csv` Low/High columns?
- Are ranges symmetric? If so, is asymmetry warranted?
- Are any ranges implausibly narrow (<±5%)?
- Are any ranges implausibly wide (>±80%)?

### F3. Monte Carlo Design
- **Distribution:** Triangular (Low/Base/High)? Uniform (Low/High)? Verify which is used.
- **Correlations:** Are parameters sampled independently? Key correlated pairs:
  - Solar CAPEX ↔ Battery CAPEX (both decline with RE deployment)
  - Oil price ↔ LNG price (commodity correlation)
  - Demand growth ↔ GDP growth
  - Solar CAPEX ↔ Solar decline rate
- **Convergence:** With 1,000 iterations, does the mean NPV stabilise? Check: is standard error of mean < 1% of mean?
- **Random seed:** Is it fixed for reproducibility? If not, results change between runs.

### F4. Switching Value Analysis
- Linear interpolation between Low/High: is NPV approximately linear in the parameter?
- For nonlinear parameters (discount rate, demand growth), linear interpolation may miss the true switching value
- Are switching values reported for all relevant scenario pairs?

### F5. Multi-Horizon Analysis
- 20/30/50-year horizons: verify salvage value recalculated for each
- All 7 scenarios included in all 3 horizons?
- At 20-year horizon, many investments haven't been fully amortised — does this affect the ranking?
- Do any scenarios switch ranking between horizons? (This is important information)

### F6. Sensitivity of Rankings
Beyond one-way sensitivity of NPV, check:
- Does the S7>S6 ranking reverse under high SCC ($190/tCO₂)?
- Does the S7>S6 ranking reverse under low discount rate (3.5%)?
- Does the S2 ranking improve under India cost-sharing (50%)?
- What single parameter change would most change the ranking?

---

## 9. Workstream G — Supplementary Modules & Outputs

### Objective
Verify correctness of supporting analyses.

### What to Read
1. `model/distributional_analysis.py` — HIES 2019 microdata analysis
2. `model/financing_analysis.py` — grant element, WACC, debt service
3. `model/transport_analysis.py` — EV adoption S-curve
4. `model/cba/mca_analysis.py` — multi-criteria analysis
5. `model/sanity_checks.py` — automated benchmark checks
6. `data/hies2019/` — source microdata for distributional analysis

### G1. Distributional Analysis (`distributional_analysis.py`)
- **Survey weights:** HIES 2019 uses sampling weights (`wgt` column). Verify: are ALL summary statistics (means, medians, shares, totals) computed using survey weights? Or are some computed as unweighted counts/averages? Unweighted statistics on survey data are biased.
- **Gender analysis:** If gender of household head is used, verify: is the gender share computed as weighted share (`wgt.sum()` for gender group / total `wgt.sum()`), or as unweighted count ratio? The latter would be incorrect for survey data.
- **Energy poverty threshold:** 10% of income — is this the right threshold for Maldives? International standard varies (10% UK, 6% France, 2× median share Germany)
- **Quintile construction:** By per-capita income or household income?
- **Tariff impact:** How does the model translate LCOE reductions into tariff reductions? Is there a passthrough assumption?
- **Missing data handling:** How are households with zero income or zero electricity expenditure treated?

### G2. Financing Analysis (`financing_analysis.py`)
- **Fiscal burden denominator:** `peak_pct_gdp` divides peak debt service by GDP. Is the GDP denominator a FIXED base-year value, or does it grow over time at a GDP growth rate? If fixed, this overstates fiscal burden for years 20+ because GDP will have grown significantly. If growing, verify the growth rate source and that it’s wired from parameters.csv.
- **Grant element formula:**
  $GE = 1 - \frac{PV(\text{debt service})}{\text{Face Value}}$
  discounted at commercial rate (11.55%)
  - Verify: ADB terms (1%, 40yr, 10yr grace) give GE = 82.8%
  - Calculate manually: PV of 40-year annuity at 1% discounted at 11.55% ≈ 17.2% of face value → GE = 82.8% ✓
- **WACC:** Verify weights and rates are correct
- **Debt service beyond model horizon:** The model runs 30 years (2026–2056) but ADB loan is 40 years. How is this handled?

### G3. Transport Analysis (`transport_analysis.py`)
- **S-curve parameters:** Verify the 3 scenarios (Low/Medium/High) have distinct adoption rates
- **Grid emissions for EV charging:** Are these calculated from the SCENARIO's generation mix (which includes RE) or from BAU (all diesel)?
- **Double-counting check:** Transport health benefits (PM2.5, NOx, noise) are NOT included in the main CBA NPV — verify this isolation
- **Fleet projection:** 131,000 vehicles growing at what rate? Source?
- **Motorcycle dominance (92%):** Motorcycles have very different EV economics than cars. Are EV premiums and kWh/km calibrated for motorcycles?

### G4. MCA (`mca_analysis.py`)
- **Weight validation:** Do MCA weights sum to 1.0? Is this enforced at load time or just assumed? If weights come from parameters.csv, what happens if they don’t sum correctly due to a typo?
- **Normalisation direction:** For each of the 8 criteria, verify polarity:
  - NPV: higher = better ✓
  - LCOE: lower = better → inverted? ✓
  - Emissions: lower = better → inverted? ✓
  - Health: higher avoided = better ✓
  - Fiscal burden: lower = better → inverted? ✓
  - Feasibility: higher = better ✓
  - Equity: higher = better ✓
  - Climate resilience: higher = better ✓
- **MCA-NPV independence:** MCA includes NPV as a criterion. But NPV already incorporates most other criteria (emissions via SCC, health via damage cost). Is this double-counting?
- **MCA score sources:** Are the MCA scores for ALL 7 scenarios present in parameters.csv? Are any scenarios missing scores (which would cause the MCA to fail or use defaults)?

### G5. Sanity Checks (`sanity_checks.py`)
- **Coverage:** Do the 48 checks cover:
  - BAU LCOE in plausible range ($0.30–0.60/kWh for SIDS)?
  - RE scenario LCOE in plausible range ($0.15–0.35/kWh)?
  - BCR > 0 for all RE scenarios?
  - Total demand 2056 in plausible range?
  - Diesel share 2050 in expected range per scenario?
  - Total emissions cumulative in expected range?
  - NPV savings positive for all RE vs BAU?
- **Hardcoded ranges:** Are the expected ranges sourced or arbitrary? If arbitrary, they may be too wide (never fail) or too narrow (false alarms)
- **Missing checks:** Verify generation balance (demand = supply), cost summation (CAPEX + OPEX + fuel = total), and temporal monotonicity (RE share should increase over time in all scenarios)

---

## 10. Workstream H — Numerical Stability & Reproducibility

### Objective
Verify that model outputs are deterministic, numerically stable, and reproducible across environments.

### H1. Determinism
- Run `run_cba.py` twice in succession. Do `cba_results.json` outputs match exactly?
- Is there any source of randomness in the main CBA pipeline? (Random should only be in Monte Carlo)
- Check for dictionary iteration order dependence (Python 3.7+ guarantees insertion order, but verify)

### H2. Monte Carlo Reproducibility
- Does `run_monte_carlo.py` use a fixed random seed?
- If the seed is fixed, do results match exactly across runs?
- If not, flag as a reproducibility issue

### H3. Floating-Point Edge Cases
- **Very large/small numbers:** Total costs are ~$15B = 1.5e10. Discount factors at year 30 at 6% = 0.174. Product = 2.6e9. Are there any calculations where large and small numbers are added (catastrophic cancellation)?
- **Division by zero:** What happens in scenarios where `diesel_gwh = 0` (no diesel remaining)? Or `solar_mw = 0` (early BAU years)?
- **Negative values:** Can any intermediate calculation go negative when it shouldn't? (e.g., salvage value for fully depreciated assets, emission reduction when emissions increase)
- **Overflow:** Compound growth at 5%/yr for 30 years = 4.32×. At 10%/yr = 17.45×. No overflow risk. But LNG scenario compound costs? Verify.

### H4. Convergence Diagnostics
- **IRR bisection:** How many iterations does it take to converge for each scenario? Is there a scenario where it fails to converge? What's the fallback?
- **Least-cost engine:** The 183-island LCOE calculation — does it converge? Are there islands where no technology meets demand?
- **Monte Carlo:** Plot (mentally) the running mean of NPV vs. iteration count. Does it stabilise by iteration 500?

### H5. Platform Independence
- Does the model use any Windows-specific paths (backslashes)?
- Does it depend on any non-standard Python libraries beyond those in `requirements.txt`?
- Would it produce the same results on Linux/macOS?
- Read `requirements.txt`: are version pins appropriate?

### H6. Data Pipeline Integrity
- Is `islands_master.csv` (183 islands) loaded correctly? No truncation?
- Are hourly CSV files (`GHI_hourly.csv`, `Temperature_hourly.csv`) 8,760 rows (non-leap year)?
- Is HIES microdata (`hies2019/`) complete? No missing values in key fields?
- Are population data (`Census_2022_P5.xlsx`) loaded correctly?

---

## 11. Workstream I — Publication Readiness & Output Integrity

### Objective
Verify that model outputs (JSON files) match what the code produces, that the Quarto report accurately represents the outputs, and that all claims in documentation are supported.

### I1. JSON Output Integrity
- Load `outputs/cba_results.json`: do the values match the table in §1 above?
- Load `outputs/scenario_summaries.json`: are all 7 scenarios present with complete annual data?
- Load `outputs/sensitivity_results.json`: are all 39 parameters present for all 7 scenarios?
- Load `outputs/monte_carlo_results.json`: are there 1,000 iterations with complete data?
- Load `outputs/mca_results.json`: are all 8 criteria × 7 scenarios present?
- Load `outputs/distributional_results.json`: are all quintiles + gender analysis present?
- Load `outputs/financing_analysis.json`: is grant element, WACC, debt service present?
- Load `outputs/transport_results.json`: are all 3 EV scenarios present?
- Load `outputs/learning_curve_results.json`: are exogenous and endogenous curves present?
- Load `outputs/climate_scenario_results.json`: are RCP 4.5 and 8.5 present?
- Load `outputs/multi_horizon_results.json`: are 20/30/50 year results present?

### I2. Report-to-Output Traceability
For every number stated in the Quarto report (`report/REPORT_Maldives_Energy_CBA.qmd`):
- Is it read programmatically from an output JSON file, or hardcoded?
- If hardcoded, flag as a zero-tolerance violation (see copilot-instructions.md §⛔)
- If programmatic, does the rendering match the JSON value?

### I3. Documentation Consistency
Verify these documents are consistent with each other and the code:
- `CBA_METHODOLOGY.md` equation numbers match code implementation
- `SCENARIO_GUIDE.md` scenario descriptions match scenario code
- `IMPROVEMENT_PLAN.md` task statuses match reality
- `SOTA_CBA_ASSESSMENT.md` feature checklist matches actual model capabilities
- `AUDIT_REPORT.md` / `AUDIT_REPORT_v1.md` — if any findings were marked "fixed", verify the fix is actually in the code

### I4. Output Plausibility Checks
Beyond sanity_checks.py, verify:
- **LCOE ordering:** BAU > Islanded Green > National Grid > Near-Shore > Max RE > LNG ≈ Full Integration. Does this make economic sense? (Islanded Green is expensive due to per-island battery redundancy; Full Integration benefits from Indian grid import at low cost.)
- **BCR consistency:** Higher BCR should correlate with lower PV total costs (since benefits are similar across RE scenarios). Verify.
- **IRR plausibility:** IRR of 41.4% for S7 and 16.3% for S2. S7's high IRR reflects low CAPEX + high fuel savings. S2's low IRR reflects massive CAPEX. Are these reasonable?
- **Emissions totals:** BAU cumulative ~66 MtCO₂ over 30 years. At 1,200 GWh growing at 5%/yr, average demand ~2,600 GWh/yr. At 0.72 kgCO₂/kWh = 1.87 MtCO₂/yr average. Over 30 years = 56 Mt. But with compound growth, the integral is higher. Does 66 Mt check out?
- **S7 superiority:** S7 (LNG) ranks #1 by NPV savings despite being a fossil fuel. This is because LNG is cheap ($0.50/L) with lower emission factor (0.40 vs 0.72). At what carbon price does S6 (Maximum RE) overtake S7?

### I5. Claim Verification
Specific claims in documentation that should be verified against code/outputs:
- "Model satisfies 100% of ADB (2017), Boardman (2018), and IRENA (2019) requirements" — is this supportable?
- "183-island spatial resolution" — count islands in `islands_master.csv`
- "39 sensitivity parameters" — count in `sensitivity.py`
- "48 sanity checks pass" — run and confirm
- "Grant element 82.8%" — verify calculation
- "S7 costs are ~$7.8B" — verify by running the model and checking S7 total cost output

---

## 12. Cross-Workstream Integrity Checks

After all 9 workstreams complete:

### 12.1 No Contradictions
- E.g., Workstream B says solar CAPEX is correctly sourced, but Workstream C finds it's applied wrong
- Workstream A says subsidy is correctly excluded, but Workstream G finds MCA still uses it

### 12.2 Coverage Completeness
Every `.py` file audited by at least one workstream:

| File | Workstreams |
|------|------------|
| config.py | D |
| parameters.csv | B, D |
| demand.py | C, E |
| costs.py | B, C, E |
| emissions.py | C, E |
| dispatch.py | C, H |
| scenarios/__init__.py | A, C, E |
| status_quo.py | E |
| one_grid.py | E |
| green_transition.py | E |
| islanded_green.py | E |
| nearshore_solar.py | E |
| maximum_re.py | E |
| lng_transition.py | E |
| cba/__init__.py | A, E |
| npv_calculator.py | A, C, H |
| sensitivity.py | C, F |
| mca_analysis.py | G |
| run_cba.py | A, E, I |
| run_sensitivity.py | F |
| run_monte_carlo.py | F, H |
| run_multi_horizon.py | F |
| financing_analysis.py | G |
| distributional_analysis.py | G |
| transport_analysis.py | G |
| sanity_checks.py | G, I |
| least_cost.py | C, E |
| network.py | C |
| grid_vs_standalone.py | C |

### 12.3 Cumulative Impact Assessment
If all findings were fixed simultaneously:
- Would the scenario ranking change?
- Would any NPV change sign?
- What is the estimated magnitude of changes?

### 12.4 Regression Risk
Do any proposed fixes risk breaking other parts of the model? Identify dependencies between findings.

---

## 13. Severity Classification

- 🔴 **CRITICAL:** Would change the sign of NPV, reverse scenario rankings, violate fundamental CBA principles, or produce mathematically incorrect outputs
- 🟡 **MODERATE:** Could change BCR by >10%, misrepresent a benefit/cost category, deviate from best practice, or create hard-to-detect errors under specific conditions
- 🔵 **LOW:** Minor methodological refinements, documentation gaps, code quality improvements, cosmetic issues

---

## 14. Output Format

Each workstream produces a standalone findings report:

```markdown
## Workstream [A-I]: [Title]

### Executive Summary
- X CRITICAL, Y MODERATE, Z LOW
- Top concern: [one-sentence summary]

### Findings

#### 🔴 CRITICAL — [ID]: [Title]
**File(s):** [file paths with line numbers]
**Issue:** [clear description with evidence]
**Impact:** [quantified — what changes in NPV/BCR/LCOE/ranking?]
**Recommendation:** [specific code change]

#### 🟡 MODERATE — [ID]: [Title]
[same structure]

#### 🔵 LOW — [ID]: [Title]
[same structure]

### Verified Correct
[List of things explicitly checked and confirmed correct]

### Summary Table
| ID | Severity | File | Impact | Fix Effort |
|----|----------|------|--------|-----------|
```

### Finding ID Format
- `A-CR-01` for Workstream A critical #1
- `H-MO-03` for Workstream H moderate #3
- `I-LO-02` for Workstream I low #2

---

## 15. Reference Standards

| Standard | Use |
|----------|-----|
| Boardman, Greenberg, Vining & Weimer (2018) *CBA: Concepts and Practice*, 5th ed. | CBA framework, discounting, standing, welfare |
| ADB (2017) *Guidelines for the Economic Analysis of Projects* | EIRR thresholds, shadow pricing, developing country CBA |
| HM Treasury (2026) *The Green Book* | Declining discount rates, intergenerational equity |
| IRENA (2024) *Renewable Power Generation Costs* | Technology cost benchmarks |
| IEA (2024) *World Energy Outlook* | Fuel price projections, demand |
| BNEF (2025) *New Energy Outlook* | Battery cost trajectories |
| IPCC (2006, 2019) *Guidelines for GHG Inventories* | Emission factors |
| Lazard (2024) *LCOE* and *LCOS* | Technology cost cross-checks |
| CIGRÉ TB 610, 852 | Submarine cable costs |
| Parry et al. (2014) IMF WP/14/199 | Health damage costs |
| Drupp et al. (2018) AEJ: Economic Policy 10(4) | Expert survey on discount rates |
| EPA IWG (2023) | Social cost of carbon |
| Dixit & Pindyck (1994) | Real options framework |
| Morgan & Henrion (2006) | Uncertainty characterisation |
| Suits (1977) | Suits index for progressivity |

---

## 16. High-Risk Areas Requiring Extra Scrutiny

Based on the complexity profile of the codebase, these areas have the highest probability of containing errors:

### 16.1 Scenario Growth Rate Keys
Each scenario looks up its demand growth rate using a string key. If the key is wrong, the scenario silently uses another scenario's growth rate. **For every scenario (S1–S7)**, trace the growth rate from config key → config dictionary → actual value used. Confirm each scenario uses its own rate.

### 16.2 Vintage/Cohort Solar Calculations
The vintage-based solar generation code in `costs.py` is the most mathematically complex part of the model. Every cohort has its own installation year, degradation trajectory, and OPEX calculation. Errors in the degradation base year, the cohort iteration, or the per-kW conversion denominator would silently corrupt all scenario costs. Audit this function line-by-line.

### 16.3 Benefit Stream Aggregation
The NPV calculator aggregates multiple benefit streams (fuel savings, emission benefits, health benefits, reliability, environmental, subsidy avoidance, connection benefits). **For each stream:** (1) Is it calculated? (2) Is it discounted? (3) Is it included in `total`? (4) Is it included in the IRR cash flow? A benefit that is calculated but not aggregated is a silent omission.

### 16.4 Config Field Presence
If code accesses a config attribute that doesn't exist (e.g., `cfg.technology.new_field`), Python raises `AttributeError` — unless the code uses `getattr(cfg, 'field', fallback)` or `hasattr()` to silently fall back. Search for these patterns and assess whether the fallback masks a missing CSV→config wiring.

### 16.5 LNG-Specific Fields
S7 (LNG) introduced new cost fields (`fuel_lng`, LNG CAPEX/OPEX). These fields must propagate through the entire chain: `costs.py` → `AnnualCosts` dataclass → `__init__.py` → `npv_calculator.py`. If any link is missing, LNG costs are silently zero.

### 16.6 Fiscal vs Economic NPV Separation
Subsidy avoidance is a fiscal transfer, not an economic benefit. It should appear in a separate `total_with_fiscal` aggregate but NOT in the primary economic `total`. Verify this separation is correctly implemented.

### 16.7 Year Boundary Transitions
The model spans 2026–2056 with critical transition years:
- **2026:** Base year. Are initial CAPEX investments correctly placed here?
- **2031:** LNG plant comes online (S7), submarine cable operational (S2). Are costs and generation correctly phased?
- **2041:** Battery replacement year (15-year lifetime from 2026). Is replacement CAPEX added?
- **2056:** Terminal year. Is salvage value calculated correctly for assets with remaining life?

Verify that transitions at each boundary produce expected discontinuities in cost/generation profiles.

---

## 17. Files to Audit (Complete List)

### Core Model (audit every line)
| File | ~Lines | Workstreams |
|------|--------|------------|
| `model/config.py` | 2,130 | D |
| `model/parameters.csv` | ~420 rows | B, D |
| `model/demand.py` | 362 | C, E |
| `model/costs.py` | 909 | B, C, E |
| `model/emissions.py` | 272 | C, E |
| `model/dispatch.py` | 408 | C, H |
| `model/scenarios/__init__.py` | 570 | A, C, E |
| `model/scenarios/status_quo.py` | 197 | E |
| `model/scenarios/one_grid.py` | 416 | E |
| `model/scenarios/green_transition.py` | 373 | E |
| `model/scenarios/islanded_green.py` | 317 | E |
| `model/scenarios/nearshore_solar.py` | 361 | E |
| `model/scenarios/maximum_re.py` | 406 | E |
| `model/scenarios/lng_transition.py` | 444 | E |
| `model/cba/__init__.py` | ~35 | A, E |
| `model/cba/npv_calculator.py` | 881 | A, C, H |
| `model/cba/sensitivity.py` | 1,011 | C, F |
| `model/cba/mca_analysis.py` | 513 | G |
| `model/run_cba.py` | 1,284 | A, E, I |
| `model/run_sensitivity.py` | 667 | F |
| `model/run_monte_carlo.py` | 385 | F, H |
| `model/run_multi_horizon.py` | 375 | F |

### Supplementary (audit for correctness)
| File | ~Lines | Workstreams |
|------|--------|------------|
| `model/financing_analysis.py` | 507 | G |
| `model/distributional_analysis.py` | 1,185 | G |
| `model/transport_analysis.py` | 410 | G |
| `model/sanity_checks.py` | 631 | G, I |
| `model/least_cost.py` | 914 | C, E |
| `model/network.py` | 509 | C |
| `model/grid_vs_standalone.py` | 279 | C |

### Reference Documents (read for context, do not audit)
| File | Purpose |
|------|---------|
| `CBA_METHODOLOGY.md` | Equation catalogue — cross-check code |
| `SCENARIO_GUIDE.md` | Scenario design rationale |
| `IMPROVEMENT_PLAN.md` | Decision log |
| `literature_benchmarks.md` | 10-paper SIDS CBA review |
| `AUDIT_REPORT_v3.md` | Prior audit — reference only, do not assume conclusions are correct |
| `SOTA_CBA_ASSESSMENT.md` | Gap analysis |
| `real_options_analysis.md` | Real options framing |

### Do NOT Audit
- `_archive/` — historical code, read-only
- `perplexity_lookup.py` — standalone utility
- `data/` files — data inputs, not model logic (but verify they load correctly in H6)
- `report/` — Quarto report (verify in I2 only for hardcoded values)
- `.md` files as code — documentation only

---

## 18. Execution Instructions

### For the Orchestrating Agent

1. **Launch 9 subagents**, one per workstream (A through I).
2. Each subagent receives this full audit prompt + its specific workstream section.
3. Each subagent must work **independently** — do not share findings between workstreams during execution.
4. Each subagent returns structured findings per §14.
5. After all 9 complete, run cross-workstream checks (§12).
6. Compile into `AUDIT_REPORT_v4.md`.

### Quality Standards
- **Every finding must have evidence** — code snippet, calculation, or line reference
- **Every finding must have a quantified impact estimate** where possible
- **Every finding must have a specific, actionable recommendation**
- **Zero trust** — do NOT assume any part of the code is correct because it "looks reasonable" or because documentation says it was verified. Read the actual code and verify independently.
- **Cross-cutting integration issues** are highest priority — individual functions may be correct in isolation but interact incorrectly
- **Trace end-to-end** — for critical calculations (NPV, LCOE, IRR, emissions), trace from `parameters.csv` → `config.py` → consuming module → output JSON. Every link in the chain must be verified.

### Priority Focus Areas
These areas are inherently high-risk due to their complexity and the severity of errors they could harbour:
1. **Growth rate key lookups** — string-based config lookups are fragile; a typo is invisible
2. **Vintage/cohort calculations** — the most mathematically complex code; denominator errors compound over 30 years
3. **Benefit stream aggregation** — a benefit that is calculated but not included in the total is a silent omission worth potentially billions in NPV
4. **Config field wiring** — every `parameters.csv` row must reach the code that uses it; breaks in the chain mean the model silently uses defaults
5. **JSON output completeness** — do the output JSONs capture everything the model computes? Or are some results computed and discarded?
6. **Year boundary effects** — transitions at 2026/2031/2041/2056 are where phasing errors hide
7. **Unit consistency** — kW↔MW, kWh↔GWh, $/kW↔$M, per-year↔per-period mismatches compound silently
8. **Sign conventions** — benefits should be positive, costs negative (or vice versa) — inconsistent signs cause subtraction instead of addition

---

*End of AUDIT_PROMPT_v2.md — 10 February 2026*
