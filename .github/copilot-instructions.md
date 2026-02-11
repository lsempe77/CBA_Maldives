# Copilot Instructions — Maldives Energy CBA Project

## Master Plan

The file `Maldives/IMPROVEMENT_PLAN.md` is the **single source of truth** for all planned work on this project. Before starting any task, read it. After completing any task, update it.

## Project Context

This is a **Cost-Benefit Analysis (CBA) model** for energy transition scenarios in the Maldives. It compares diesel-based status quo against renewable energy, LNG, and India submarine cable alternatives across 7 scenarios (S1 BAU, S2 Full Integration, S3 National Grid, S4 Islanded Green, S5 Near-Shore Solar, S6 Maximum RE, S7 LNG Transition). The model is written in Python 3.12 with dataclass-driven configuration and a Quarto report.

### Architecture

```
parameters.csv  →  config.py (load_parameters_from_csv)  →  get_config()  →  model code
     ↓                                                                          ↓
 SINGLE SOURCE                                                            scenarios/*.py
 OF TRUTH for                                                             costs.py
 all numbers                                                              demand.py
                                                                          cba/npv_calculator.py
                                                                               ↓
                                                                          outputs/*.json
                                                                               ↓
                                                                          REPORT...qmd
```

### Key Principles (non-negotiable)

1. **Every parameter must live in `Maldives/model/parameters.csv`** — 7 columns: Category, Parameter, Value, Low, High, Unit, Source, Notes. No hardcoded values in `.py` or `.qmd` files.
2. **Every parameter must have a real, citable source** — not "assumed" or "estimated". If no source exists, **run `perplexity_lookup.py`** to search for it. Only flag as 🔍 HUMAN LOOKUP if Perplexity also cannot find a citable source.
3. **`config.py` loads from CSV** — all new parameters must be wired through `load_parameters_from_csv()` → appropriate dataclass → `get_config()`.
4. **Update `IMPROVEMENT_PLAN.md` after every change** — mark items ✅ Done, update the Decision Made column, note any new blockers discovered.

### ⛔ ZERO HARDCODED VALUES — Absolute Rule

**No numeric parameter may appear as a literal in any `.py` script, `.qmd` report, or any other file except `parameters.csv` and `config.py` defaults.** This is the #1 source of silent bugs — we already caught one where hardcoded defaults in a dataclass overrode CSV values for months (see D23 in IMPROVEMENT_PLAN.md).

#### In Python scripts (`.py`)

- **WRONG:** `solar_capex = 1500`, `discount_rate = 0.06`, `loss = 0.11`
- **RIGHT:** `cfg = get_config()` then `cfg.technology.solar_pv_capex`, `cfg.economics.discount_rate`, etc.
- Every model module must call `get_config()` to obtain parameter values. No magic numbers.
- Dataclass defaults in `config.py` must match `parameters.csv` — they exist only as a safety net, not as the source of truth.
- If you need a new parameter: **(1)** add row to `parameters.csv`, **(2)** wire it in `config.py` → `load_parameters_from_csv()`, **(3)** access it via `get_config()` in the consuming module. Never skip step 1.
- Exception: mathematical constants (π, 8760 hours/year, unit conversions like 1000 kg/tonne) are fine as literals.

#### In the Quarto report (`.qmd`)

- **WRONG:** Writing "Solar CAPEX is $1,500/kW" or "The discount rate is 6%" as plain text.
- **RIGHT:** Read values from `outputs/*.json` (which are produced by the model using `get_config()`) and render them with inline Python/OJS code blocks, e.g. `` `{python} f"${cfg.technology.solar_pv_capex:,.0f}/kW"` `` or reference the JSON outputs.
- If the report states a number, it must come from either the model outputs or a live read of `parameters.csv` / `config.py` — never typed by hand.
- This prevents the report from going stale when parameters change in the CSV.

#### Why this matters

- A single source of truth (`parameters.csv`) means changing a value once updates the entire model + report automatically.
- Hardcoded values create **silent divergence** — the CSV says one thing, the code uses another, and the bug is invisible until someone audits line by line.
- Sensitivity analysis and Monte Carlo only work correctly when every parameter flows through `get_config()` → the analysis engine can swap Low/High values. Hardcoded values bypass this entirely.

## Before Starting Any Task

1. **Read `Maldives/IMPROVEMENT_PLAN.md`** — specifically the Execution Roadmap tables (Tier 1: C1–C10, Tier 2: M1–M7, Tier 3: L1–L25, Tier 4: V1–V8, Tier 5: R1–R15).
2. **Check the Done column** to see what's already completed.
3. **Check the Dependency Graph** to see if the task has prerequisites.
4. **Check the 🔍 HUMAN LOOKUP table** (H1–H17) to see if the task is blocked on human-sourced data.
5. **Check the Decision Log** (D1–D72) for any decisions already made about parameter values and sources.

## When You Hit a 🔍 HUMAN LOOKUP — Use Perplexity First

The file `Maldives/model/perplexity_lookup.py` automates web research via the Perplexity Sonar API. **Before flagging anything as HUMAN LOOKUP, try Perplexity.**

### How to use it

```bash
# Look up a specific H-item from the IMPROVEMENT_PLAN
python Maldives/model/perplexity_lookup.py --id H1

# Run all pending lookups
python Maldives/model/perplexity_lookup.py --all

# Free-form research question
python Maldives/model/perplexity_lookup.py "What is the LCOE of diesel generation on Pacific SIDS?"

# Save results
python Maldives/model/perplexity_lookup.py --all --output lookup_results.md

# List all H-items
python Maldives/model/perplexity_lookup.py --list
```

### Workflow when a parameter needs a source

1. **Run** `perplexity_lookup.py --id H<n>` (or a free-form query)
2. **Evaluate** the answer — does it provide a specific value + **recent citable source** (author, year, title, publisher)?
3. **If yes (VERDICT: RESOLVED):**
   - Update `parameters.csv` (Value + Source column with full citation)
   - Update `IMPROVEMENT_PLAN.md` → H-table: mark as ~~struck~~ ✅ with citation
   - Update `IMPROVEMENT_PLAN.md` → Decision Log: update status to ✅ with citation
   - **Verify the citation URL/DOI actually exists** — Perplexity can hallucinate sources
4. **If no (VERDICT: UNRESOLVED):**
   - Keep the item in 🔍 HUMAN LOOKUP table
   - **Add a note** in the H-table: "Perplexity searched YYYY-MM-DD — no citable source found. Closest finding: [brief summary]"
   - Update Decision Log with what Perplexity found (partial data, leads, etc.)
   - Human must search primary sources listed in H-table
5. **Citation requirements:**
   - Every value must have: Author(s), Year, Title, Publisher/Journal, page/section
   - Prefer sources from 2018–2026. Reject pre-2015 unless canonical (e.g., IPCC 2006)
   - Institutional sources preferred: IRENA, IEA, ADB, World Bank, CIGRÉ, IMF, WHO
   - **Never use a Perplexity answer without verifying the citation exists**

### API key

The key is embedded in `perplexity_lookup.py`. It can also be overridden via:
```bash
set PERPLEXITY_API_KEY=pplx-...
```

### Available H-items (H1–H17)

See the 🔍 HUMAN LOOKUP table in `IMPROVEMENT_PLAN.md` for the full list. Each H-item has a pre-written research query optimised for Perplexity.

## After Completing Any Task

1. **Update `IMPROVEMENT_PLAN.md`**:
   - Set the Done column to ✅ for completed items.
   - Update the Decision Made column if you resolved a parameter value.
   - Add new decisions to the Decision Log with source and ✅/⚠️/⛔ status.
   - If you discover new blockers, add them to the 🔍 HUMAN LOOKUP table.
   - If you discover new tasks, add them to the appropriate tier.
2. **Verify `parameters.csv`** — confirm any new parameters are added with all 7 columns filled.
3. **Verify `config.py`** — confirm new parameters are wired through to the config dataclasses.
4. **Run the model** — `python Maldives/model/run_cba.py` to confirm nothing is broken.
5. **Update `AUDIT_REPORT.md`** — this is the living record of all wiring, formula, and data integrity issues:
   - **When fixing a bug:** Mark the finding as ✅ FIXED with date and details of the fix. Do not delete findings — strike them through or mark resolved.
   - **When adding new code:** Check that new formulas, config wiring, and data flows are consistent with the audit standards (no hardcoded values, config loaded from CSV, units match).
   - **When discovering a new issue:** Add it to the appropriate severity section (🔴 CRITICAL / 🟡 MODERATE / 🔵 LOW) with file paths, code snippets, impact assessment, and recommended fix.
   - **Sections to maintain:** Summary table (update counts), Critical/Moderate/Low findings, Config Wiring Audit table (CSV param → config field → code usage), Cross-Scenario Consistency checks.
   - **Why:** The audit report prevents regression — bugs we've caught before must stay documented so they aren't reintroduced. It also serves as onboarding documentation for new contributors.

## Roadmap Summary (quick reference)

### Tier 1 — CRITICAL (do now)
- C1 ✅ Emission factor typo fixed
- C2 ✅ T&D losses activated (distribution 11% + HVDC 4%)
- C3 ✅ Salvage value added to NPV
- C4 ✅ Cable cost breakdown (converter $320M + landing $80M + IDC 15% + grid $75M = $2,492M FI CAPEX)
- C5 ✅ Cost-share callout in report
- C6 ✅ requirements.txt created
- C7 ✅ PV temperature derating
- C8 ✅ PV degradation (0.5%/yr)
- C9 ✅ Diesel two-part fuel curve
- C10 ✅ CBA methodology audit (CBA_METHODOLOGY.md)

### Tier 2 — MODERATE (architecture changes)
- M1 ✅ Island-level demand allocation (master dataset + intensity multipliers: Urban ×1.8, Secondary ×1.2, Rural ×0.6)
- M2 ✅ Inter-island distance matrix + MST + grid-vs-standalone
- M2b ✅ Least-cost electrification engine
- M3 ✅ Scenario refactor (S1–S7 with progressive tranches)
- M4 ✅ Hourly dispatch validation
- M5 ✅ Sectoral demand split (52/24/24 — SAARC 2005 Energy Balance)
- M6 ✅ CAPEX updated to realistic island costs ($1500/kW solar, $350/kWh battery)
- M7 ✅ Solar land constraint in least-cost engine

### Tier 3 — LESS IMPORTANT (research or polish)
- L1 ✅ Literature review & SIDS CBA benchmarking (10 papers in literature_benchmarks.md)
- L2 ✅ Supply security Monte Carlo (idle fleet, outage rate, fuel premium)
- L3 ✅ Climate adaptation cost overlay (7.5% premium applied to solar/battery/cable CAPEX)
- L4 ✅ Health co-benefits wired into NPV ($40/MWh)
- L5 ✅ Supplementary financing analysis (standalone, grant element 82.8%, WACC 5.22%)
- L6 ✅ Tourism demand module (resort emissions context in run_cba.py + Malé 18 MWp solar cap in least_cost.py)
- L7 ✅ Report polish (hardcoded values removed)
- L8 ✅ Price elasticity activated (-0.3, induced demand in FI)
- L9 🔧 Limitations section + README + GIS cleanup (partial)
- L10 ✅ Real options / staging analysis (real_options_analysis.md, Dixit & Pindyck 1994)
- L11 ✅ Connection cost per household ($200/HH × 100k = $20M over 5yr)
- L12 ⛔ Report remake (blocked on L9 only; L1 ✅, L10 ✅)
- L13 ✅ Script audit (AUDIT_REPORT.md, 15/15 bugs fixed)
- L14 ✅ MC/sensitivity expanded (14→22→34→38 params)
- L15 ✅ Distributional analysis (HIES 2019 microdata, 4,817 HH, energy poverty, Suits index)
- L16 ✅ Environmental externalities ($10/MWh: noise $5 + spill $3 + biodiversity $2)
- L17 ✅ MCA framework (8 criteria, S6 #1, weights in parameters.csv)
- L18 ✅ S-05 fix: health benefit diesel estimation (direct baseline_gen_mix.diesel_gwh)
- L19 ✅ Near-Shore Solar scenario (S5: 104 MW uninhabited islands)
- L20 ✅ Maximum RE scenario (S6: floating solar 195 MW + near-shore)
- L21 ✅ LNG Transition scenario (S7: 140 MW Gulhifalhu from 2031)
- L22 ✅ WTE cost module (14 MW, $112M CAPEX, 98 GWh/yr)
- L23 ✅ Subsidy avoidance benefit ($0.15/kWh, R8)
- L24 ✅ MCA framework expanded (8 criteria × 7 scenarios)
- L25 ✅ Sanity checks (47 automated benchmark checks)

### Tier 4 — VALIDATION (V1–V8)
- V1 ✅ Scenario realism & GIS audit (code done, floating solar aligned with Roadmap 195 MW — D73)
- V2 ✅ Sensitivity/MC/financing/distributional → all 7 scenarios
- V2b ✅ Sensitivity expanded 22→34→38 params (12 S5/S6/S7-specific + 4 transport)
- V3 ✅ LCOE comparison analysis
- V4 ✅ Equation sanity checks with benchmarks (47 checks)
- V5 ✅ Island master dataset validation (183 islands)
- V6 ✅ Interconnection pipeline verification (14 km)
- V7 ✅ Demand model validation (three-phase Malé trajectory)
- V8 ✅ All outputs extended to 7 scenarios

### Tier 5 — REFINEMENT (R1–R15, GoM Roadmap alignment)
- R1–R9 ✅ All Roadmap calibration tasks complete
- R10 ✅ POISED/ASSURE cross-check (D66)
- R11 ✅ Roadmap vs model cost comparison (D66)
- R12–R14 ✅ Interconnection, floating solar, citations (D66)
- R15 ✅ 33% target feasibility assessment (D65)

### Tier 6 — SOTA ENHANCEMENTS (P1–P8, publication-quality upgrades)
- P1 ✅ Declining discount rate sensitivity (DDR 3.5%→3.0%→2.5%, HM Treasury Green Book / Drupp et al. 2018 / Weitzman 2001)
- P2 ✅ Literature benchmarking (= L1, 10 papers in literature_benchmarks.md)
- P3 ✅ Real options framing (= L10, real_options_analysis.md, Dixit & Pindyck 1994)
- P4 ✅ Switching value analysis (6 scenario pairs × 34 params in run_sensitivity.py)
- P5 ✅ Gender-disaggregated distributional analysis (HIES 2019 Usualmembers.dta: 2,130 male-headed 44.2%, 2,687 female-headed 55.8%; male burden 5.4%, female 4.7%)
- P6 ✅ Endogenous learning curves (Wright's Law: solar 20%/battery 18% per doubling; endogenous costs higher than exogenous by 2056)
- P7 ✅ Climate damage scenarios RCP 4.5/8.5 (GHI −2%/−5%, Temp +1.5/+3.0°C by 2050; cumulative loss 0.4%/0.8% — solar robust to climate)
- P8 ✅ Transport electrification module (supplementary: 131k vehicles, 92% motorcycles, logistic S-curve Low/Medium/High; Medium NPV $441M, BCR 6.90, 901 kt CO₂; 38 sensitivity params)

## File Map

| File | Purpose | When to touch |
|---|---|---|
| `Maldives/IMPROVEMENT_PLAN.md` | Master plan — read first, update last | Every task |
| `Maldives/CBA_METHODOLOGY.md` | Complete equation catalogue, parameter traceability map, structural concerns | Before changing any formula, parameter, or config wiring |
| `Maldives/AUDIT_REPORT.md` | Living record of all bugs, wiring audits, formula checks | When fixing bugs or discovering issues |
| `Maldives/model/parameters.csv` | All parameter values + sources | When adding/changing any number |
| `Maldives/model/config.py` | Loads CSV → dataclasses → `get_config()` | When adding new parameter categories |
| `Maldives/model/costs.py` | CAPEX, OPEX, generation calculations | C2, C7, C8, C9, C4 |
| `Maldives/model/demand.py` | Demand projection + sectoral split | L8, M5 |
| `Maldives/model/emissions.py` | Emission calculations (CO₂, SCC growth) | C1 |
| `Maldives/model/dispatch.py` | Hourly PV-diesel-battery dispatch simulation | M4 |
| `Maldives/model/cba/npv_calculator.py` | NPV, BCR, IRR, incremental analysis, salvage | C3, L4 |
| `Maldives/model/cba/sensitivity.py` | Sensitivity engine (`_modify_config`, `_define_parameters`) | L14 |
| `Maldives/model/scenarios/*.py` | Scenario definitions: `status_quo.py` (S1 BAU), `one_grid.py` (S2 FI), `green_transition.py` (S3 NG), `islanded_green.py` (S4 IG), `nearshore_solar.py` (S5 NS), `maximum_re.py` (S6 MR), `lng_transition.py` (S7 LNG) | M3, L19–L21 |
| `Maldives/model/run_cba.py` | Main entry point — runs all scenarios + financing | After any model change |
| `Maldives/model/run_sensitivity.py` | One-way sensitivity analysis (tornado diagrams) | L14 |
| `Maldives/model/run_monte_carlo.py` | Monte Carlo simulation (1000 iterations, 38 params) | L14, V2b |
| `Maldives/model/run_multi_horizon.py` | Multi-horizon analysis (20/30/50 year) | After model changes |
| `Maldives/model/financing_analysis.py` | Supplementary fiscal analysis (grant element, WACC, debt service) | L5 — standalone, does not affect economic CBA |
| `Maldives/model/distributional_analysis.py` | Distributional impact analysis using HIES 2019 microdata | L15 — electricity burden, energy poverty, Suits index |
| `Maldives/model/sanity_checks.py` | 47 automated benchmark checks (LCOE, costs, emissions, NPV, etc.) | V4 — CI-ready |
| `Maldives/model/transport_analysis.py` | P8: Transport electrification supplementary module (logistic S-curve, 3 EV scenarios) | P8 — standalone |
| `Maldives/model/cba/mca_analysis.py` | Multi-Criteria Analysis (8 criteria, weighted scoring, 7 scenarios) | L17, L24 |
| `Maldives/model/least_cost.py` | Per-island LCOE + technology assignment engine | M2b, M6, M7 |
| `Maldives/model/network.py` | Inter-island distance matrix, MST, routing premium | M2 |
| `Maldives/model/grid_vs_standalone.py` | Grid-vs-standalone analysis per island | M2 |
| `Maldives/model/perplexity_lookup.py` | Perplexity API research for 🔍 HUMAN LOOKUP items | When a parameter needs a source |
| `Maldives/report/REPORT_Maldives_Energy_CBA.qmd` | Quarto report | C1, C5, L7, L12 |
| `Maldives/data/islands_master.csv` | 183-island master dataset (GDB + Census + Solar Atlas) | M1, M2, L9, V5 |
| `Maldives/data/Maldives_GIS_Complete.csv` | OLD 40-island GIS data (superseded by islands_master.csv) | — |
| `Maldives/data/supplementary/GHI_hourly.csv` | Hourly solar data | M4 |
| `Maldives/data/supplementary/Temperature_hourly.csv` | Hourly temperature data | M4 |
| `Maldives/data/maldives_island_electricity_2018_clean_corrected.csv` | Cleaned 2018 Island Electricity Data Book (115 islands) | Demand validation (D34) |
| `Maldives/data/Census_2022_P5.xlsx` | 2022 Census population by island | M1, demand weighting |
| `Maldives/outputs/cba_results.json` | Main CBA results (NPV, BCR, IRR per scenario) | Report rendering |
| `Maldives/outputs/scenario_summaries.json` | Per-scenario cost/generation breakdown | Report rendering |
| `Maldives/outputs/sensitivity_results.json` | Tornado diagram data (38 params × 7 scenarios) | Report rendering |
| `Maldives/outputs/monte_carlo_results.json` | MC simulation results (1000 iterations) | Report rendering |
| `Maldives/outputs/financing_analysis.json` | Grant element, WACC, debt service analysis | L5 standalone |
| `Maldives/outputs/distributional_results.json` | Distributional analysis (HIES 2019): quintile burden, energy poverty, Suits index | L15 |
| `Maldives/outputs/multi_horizon_results.json` | 20/30/50 year horizon comparison | Report rendering |
| `Maldives/outputs/mca_results.json` | MCA scores and rankings per scenario | L17 |
| `Maldives/outputs/learning_curve_results.json` | P6: Exogenous vs endogenous (Wright's Law) cost trajectory comparison | P6 |
| `Maldives/outputs/climate_scenario_results.json` | P7: Solar generation under baseline/RCP 4.5/RCP 8.5 | P7 |
| `Maldives/outputs/transport_results.json` | P8: Transport EV adoption analysis (Low/Medium/High) — NPV, CO₂, health | P8 |
| `Maldives/_archive/onsset_files/onsset.py` | Archived OnSSET (source for dispatch params) | M3, M4 (read-only reference) |
| `Maldives/_archive/onsset_files/onsset_maldives.py` | Archived Maldives OnSSET adaptation | Read-only reference |

## Verified Parameter Sources (do not re-research)

These decisions are final — see Decision Log in IMPROVEMENT_PLAN.md for full citations:

- Distribution loss: **11%** (World Bank WDI) ✅
- HVDC cable loss: **4%** (Skog et al., CIGRÉ 2010 B1-106) ✅
- Solar lifetime: **30yr** (IRENA RPGC 2024) ✅
- Battery lifetime: **15yr** (BNEF 2025) ✅
- Battery DoD: **0.8** (OnSSET L194) ✅
- Battery RT efficiency: **0.88** (BNEF 2025) ✅
- Diesel min load: **0.40** (OnSSET L259) ✅
- Fuel curve: **0.08145 + 0.246** (OnSSET L266, Mandelli 2016) ✅
- PV temp derating: **k_t=0.005** (IEC 61215) ✅
- NOCT coeff: **25.6** (OnSSET L247) ✅
- Cable outage rate: **λ=0.15/yr** (NorNed + Basslink records) ✅
- Cable outage duration: **1–6 months** (NorNed + Basslink records) ✅
- ADB SIDS rate: **1%, 40yr, 10yr grace** (ADB Lending Policies 2026) ✅
- PV degradation: **0.5%/yr** (Jordan & Kurtz 2013, IRENA RPGC 2024) ✅
- Emission factor: **0.72 kgCO₂/kWh** (IPCC 2006) ✅
- Base demand 2026: **1,200 GWh** (IRENA 2022 × 1.05^4; Island Electricity Data Book 2018) ✅
- Load factor: **0.68** (2018 Island Electricity Data Book, 115 islands: national LF=0.685) ✅
- Fuel efficiency: **3.3 kWh/L** (2018 Island Electricity Data Book, mean=3.31, median=3.15) ✅
- BAU growth rate: **5%** (IRENA CAGR=5.1%; STELCO MD confirms national ~5%) ✅
- Base peak 2026: **200 MW** (PNG 107 MW Malé+Hulhumalé + outer islands; growth trajectory) ✅
- Price elasticity: **-0.3** (Wolfram et al. 2012, Burke et al. 2015) ✅
- Commercial interest rate: **11.55%** (World Bank WDI 2024) ✅
- Health damage cost: **$40/MWh** (Parry et al. 2014, IMF WP/14/199) ✅
- Climate adaptation premium: **7.5%** (GCA 2025; 5–15% sensitivity; Maldives-specific study needed) ✅
- Grant element (ADB SIDS): **82.8%** (OECD-DAC/IMF method) ✅
- Sectoral split: **52/24/24** (residential/commercial/public, SAARC 2005 Energy Balance) ✅
- Resort electricity intensity: **60 kWh/guest-night** (Komandoo 58.3, Crown & Champa 53, Sun Siyam ~198) ✅
- Idle fleet maintenance: **$8M/yr** (engineering estimate, cross-checked vs STELCO financials $2.6–5.2M active) ✅
- Malé rooftop solar: **18 MWp** (ZNES Flensburg: 5 public + 13 sports; ~28 GWh/yr) ✅

## CBA Methodology Audit — `Maldives/CBA_METHODOLOGY.md`

The file `Maldives/CBA_METHODOLOGY.md` is the **complete equation and parameter audit** for the model. **Consult it before modifying any calculation, formula, or parameter.**

### What it contains

- **30+ equations in LaTeX** — every formula across all 10+ model scripts (demand, costs, emissions, least-cost, NPV, financing, dispatch, sensitivity, Monte Carlo)
- **~185 parameter traces** — full traceability chain: `parameters.csv → config.py field → consuming script + line number`
- **17 structural concerns (S-01 to S-18)** — hardcoded values, wiring gaps, dead code, design-choice limitations. All 17 fixed ✅.
- **Cross-check tables** — compliance vs Boardman (2018), ADB (2017), IRENA (2019) standards

### When to consult it

1. **Before changing any formula:** Check the equation catalogue (§2–§7) to understand the full mathematical context and every parameter that feeds into the formula. Verify units match (USD vs $M, kW vs MW, kWh vs GWh, per-year vs per-period).
2. **Before adding a parameter:** Check the Parameter Traceability Map (§10) — it may already exist. If adding new, follow the 3-step wiring rule: (1) `parameters.csv`, (2) `config.py`, (3) `get_config()` in the consuming module.
3. **Before modifying config wiring:** Check the traceability table to ensure you don’t break an existing CSV → config → script chain. The Summary section lists all currently wired parameters.
4. **When hunting for hardcoded values:** The Structural Concerns section (§11) documents every known pattern of bypassing `parameters.csv`. All 17 concerns are now ✅ FIXED. Use `grep_search` for numeric literals in `.py` files.
5. **When validating math:** Cross-check your implementation against the LaTeX equations. Ensure the code implements exactly what the equation says — no sign errors, no missing terms, no unit mismatches.

### Mandatory checks for any model code change

- ✅ **Formula correctness:** Does the code match the equation in CBA_METHODOLOGY.md?
- ✅ **Parameter traceability:** Every numeric value flows from `parameters.csv → config.py → get_config()` — no hardcoded literals (see ⛔ ZERO HARDCODED VALUES above)
- ✅ **Structural integrity:** No `getattr(obj, field, hardcoded_fallback)`, no `.get(key, default)` that masks missing config, no bare `except Exception`
- ✅ **Unit consistency:** Check that inputs and outputs have matching units across the entire calculation chain
- ✅ **Cross-scenario consistency:** All scenarios use the same discount rate, base year, emission factors, and demand projections (no copy-paste divergence)
- ✅ **Update the audit:** If you fix a bug or add a formula, update `CBA_METHODOLOGY.md` to keep it current

## What NOT to Do

- ⛔ **NEVER hardcode numeric parameters** in `.py`, `.qmd`, or any file. Every number flows from `parameters.csv` → `config.py` → `get_config()`. This includes the report — no hand-typed values like "$1,500/kW" or "6% discount rate". If a number appears in the report, it must be read programmatically from model outputs or config. See the **⛔ ZERO HARDCODED VALUES** section above.
- **Do not guess parameter values.** Run `perplexity_lookup.py` first. If that fails, add to 🔍 HUMAN LOOKUP.
- **Do not add parameters to `config.py` without also adding them to `parameters.csv`.**
- **Do not use bare `except Exception` blocks** — they silently swallow real errors (see D23 bug). Catch specific exceptions only.
- **Do not forget to update `AUDIT_REPORT.md`** — when fixing bugs, adding code, or discovering issues. The audit report is a living document, not a one-time snapshot. All 15/15 original findings are resolved.
- **Do not create config.yaml** — the project uses `parameters.csv`, not YAML.
- **Do not rewrite archived OnSSET code** — key features already extracted into `dispatch.py`, `costs.py`, `least_cost.py`. Use archive as read-only reference.
- **Do not forget to update `IMPROVEMENT_PLAN.md`** after every change.
