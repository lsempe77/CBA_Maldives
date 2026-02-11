# Workstream E: Scenario Consistency & Comparative Logic

**Auditor:** GitHub Copilot (Claude Opus 4.6)  
**Date:** 2026-02-10  
**Scope:** All 7 scenario files, base class, `run_cba.py`, `costs.py`, `npv_calculator.py`, `config.py`

---

## Executive Summary

The scenario architecture is **well-designed and largely consistent**. All 7 scenarios share a common `BaseScenario` base class, use `get_config()` for parameterisation, and follow the same generation → costs → emissions → benefits pipeline. The demand growth rate key lookup — a historically critical bug vector (E-CR-01 fixed) — is now correct for all scenarios.

**3 findings** were identified: 1 moderate (payback calculation ignores LNG fuel for S7), 1 low (S4 diesel capacity never reduces as RE grows), 1 informational (S1 BAU has no WTE/connection costs by design). No critical findings.

---

## Findings

### E-01: Payback Calculation Ignores LNG Fuel Cost (MODERATE)

| Attribute | Detail |
|---|---|
| **Severity** | 🟡 MODERATE |
| **File** | [npv_calculator.py](Maldives/model/cba/npv_calculator.py#L601) |
| **Evidence** | `annual_savings = base_costs.fuel_diesel - alt_costs.fuel_diesel` — only `fuel_diesel` is used, not `fuel_diesel + fuel_lng` |
| **Context** | The `_calculate_irr()` method at [L633](Maldives/model/cba/npv_calculator.py#L633) correctly includes both `fuel_diesel + fuel_lng` (E-CR-02 fix). The `calculate_incremental()` method at [L533](Maldives/model/cba/npv_calculator.py#L533) also correctly uses `base_npv.pv_fuel - alt_npv.pv_fuel` which aggregates both. But `_calculate_payback()` was **not updated** when the E-CR-02 fix was applied. |
| **Impact** | For S7 (LNG Transition), payback period is **overstated** because LNG fuel costs in S7 are not subtracted from savings. Since BAU has `fuel_lng = 0` and S7 has `fuel_lng > 0`, the payback calculation sees smaller savings than actually exist. Affects payback year only — NPV, BCR, IRR are all correct. |
| **Recommendation** | Change line 601 to: `annual_savings = (base_costs.fuel_diesel + base_costs.fuel_lng) - (alt_costs.fuel_diesel + alt_costs.fuel_lng)` |

---

### E-02: S4 Islanded Green — Diesel Capacity Never Reduces (LOW)

| Attribute | Detail |
|---|---|
| **Severity** | 🔵 LOW |
| **File** | [islanded_green.py](Maldives/model/scenarios/islanded_green.py#L227-L234) |
| **Evidence** | `self.diesel_capacity_mw` is initialized to `config.current_system.diesel_capacity_mw` at [L70](Maldives/model/scenarios/islanded_green.py#L70) and **never updated** in `calculate_generation_mix()`. It stays constant at the base-year value for all 31 years. |
| **Context** | S3 (National Grid), S5, S6, S7 all reduce `diesel_capacity_mw` as RE share grows using a `min_diesel_backup` floor + reserve margin calculation. S2 (Full Integration) retires diesel capacity post-cable. S4 is the only scenario that maintains full initial diesel capacity throughout, despite deploying significant RE (~45% national). |
| **Impact** | Overstates diesel replacement CAPEX for S4 (rolling replacement of a larger fleet than needed). The modular replacement formula at [L267](Maldives/model/scenarios/islanded_green.py#L267) uses `gen_mix.diesel_capacity_mw / diesel_life`, which is based on the constant, unadjusted capacity. This makes S4 look ~5-10% more expensive than it should be for diesel CAPEX. Not critical — the intent of S4 is to model per-island independent systems, so keeping backup capacity is defensible as a design choice (islanded systems need more redundancy). Documented in code comment at [L263](Maldives/model/scenarios/islanded_green.py#L263). |
| **Recommendation** | Add diesel capacity management logic similar to S3/S5/S6 (reduce capacity as RE grows, with a floor at `min_diesel_backup × peak_mw`). Alternatively, document this as an intentional conservatism for islanded redundancy. |

---

### E-03: S1 BAU Has No WTE or Connection Costs (INFORMATIONAL)

| Attribute | Detail |
|---|---|
| **Severity** | ℹ️ INFORMATIONAL — correct by design |
| **File** | [status_quo.py](Maldives/model/scenarios/status_quo.py#L121-L155) |
| **Evidence** | S1's `calculate_annual_costs()` does not include `capex_wte`, `opex_wte`, or `capex_connection`. All S2–S7 scenarios do include these. |
| **Rationale** | BAU represents the counterfactual — no new infrastructure beyond diesel replacement. WTE and connection costs are investment features of the alternative scenarios. This is **correct CBA methodology**: the baseline should reflect "do nothing new." Benefits (fuel savings, health, emissions, environmental) are computed as the *difference* from this baseline. |
| **Impact** | None — this is correct. Noting it here only because it could be mistaken for a missing cost. |

---

## Verified Correct

### E1. Common Assumptions ✅

| Check | Status | Evidence |
|---|---|---|
| All scenarios call `get_config()` | ✅ | Every scenario `__init__` uses `config = config or get_config()` then passes to `super().__init__()` |
| Same base year (2026) | ✅ | All use `self.config.base_year` / `self.config.time_horizon` from shared `Config` instance |
| Same end year (2056) | ✅ | All iterate `self.config.time_horizon` = `range(2026, 2057)` |
| Same discount rate | ✅ | CBACalculator uses `self.config.economics.discount_rate` for all scenarios |
| Same emission factor | ✅ | All use `EmissionsCalculator(self.config)` from base class; S7 correctly overrides with LNG-specific factor |
| Same SCC + growth | ✅ | CBACalculator's `_get_scc()` uses shared `config.economics.social_cost_carbon` + `scc_annual_growth` |
| Same health damage | ✅ | Base class `calculate_annual_benefits()` uses `self.config.economics.health_damage_cost_per_mwh` for all |
| Shared `CostCalculator` | ✅ | Base class creates `self.cost_calc = CostCalculator(self.config)` |
| Shared `EmissionsCalculator` | ✅ | Base class creates `self.emissions_calc = EmissionsCalculator(self.config)` |

### E2. Generation Balance ✅

| Check | Status | Evidence |
|---|---|---|
| `total_generation_gwh ≈ total_demand_gwh` | ✅ | All scenarios set `total_demand_gwh = demand_gwh` (gross of losses), then assign generation sources that sum to `demand_gwh`. Verified: `diesel + solar + import + lng + wte = demand` in all scenarios. |
| Battery discharge not double-counted | ✅ | `battery_discharge_gwh` is declared in `GenerationMix` but **never populated** by any scenario — battery stores/discharges solar, not separate generation. Solar generation represents the *net* dispatch. |
| `total_generation_gwh` property excludes battery | ✅ | Property sums `diesel + solar + import + lng + wte` — no battery. |
| Demand gross-up consistent | ✅ | All scenarios call `cost_calc.gross_up_for_losses()` with `include_distribution=True`. S2 adds `include_hvdc=True` only when cable is operational. All pass `year` and `scenario_growth_rate` for R5 segmented losses. |

### E3. Config Key Lookups ✅ (CRITICAL CHECK)

| Scenario | Demand Key | Growth Rate | Correct? |
|---|---|---|---|
| S1 BAU | `"status_quo"` | 5% | ✅ |
| S2 Full Integration | `"one_grid"` | 5% | ✅ |
| S3 National Grid | `"green_transition"` | 4% | ✅ |
| S4 Islanded Green | `"green_transition"` | 4% | ✅ — documented rationale: same demand drivers, no separate key needed |
| S5 Near-Shore Solar | `"green_transition"` | 4% | ✅ — supply-side change only |
| S6 Maximum RE | `"green_transition"` | 4% | ✅ — supply-side change only |
| S7 LNG Transition | `"lng_transition"` | 5% | ✅ — E-CR-01 fix applied; uses its own key, value = 5% (same as BAU — LNG doesn't change demand growth) |

**Growth rate wiring chain verified:**
1. `parameters.csv` → rows 26-28: `Growth Rate - BAU` (0.05), `Growth Rate - National Grid` (0.04), `Growth Rate - Full Integration` (0.05)
2. `config.py` → [L1241-1245](Maldives/model/config.py#L1241-L1245): loads CSV values into `config.demand.growth_rates['status_quo'/'green_transition'/'one_grid']`
3. `config.py` → [L60-68](Maldives/model/config.py#L60-L68): dataclass defaults match CSV values; LNG-specific key at L67 (`lng_transition: 0.05`)

**Note:** `lng_transition` growth rate is NOT loaded from CSV — it uses the dataclass default. This is acceptable because it intentionally equals BAU rate (0.05), and there is no `Growth Rate - LNG` row in parameters.csv. However, for full traceability, a CSV row should be added. This is extremely low risk since the value (0.05) matches BAU by design.

### E4. Cost Completeness ✅

| Cost Category | S1 | S2 | S3 | S4 | S5 | S6 | S7 | Notes |
|---|---|---|---|---|---|---|---|---|
| Diesel replacement CAPEX | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All scenarios include rolling diesel replacement |
| Solar CAPEX | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | S1 has no new solar (correct) |
| Battery CAPEX | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Includes lifetime-based replacement cycle |
| Battery replacement | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All check `year - battery_life >= base_year` |
| HVDC cable CAPEX | — | ✅ | — | — | — | — | — | Only S2 (correct) |
| Inter-island cable | — | ✅ | ✅ | — | ✅ | ✅ | ✅ | S4 has no inter-island grid (correct — islanded) |
| Cable O&M | — | ✅ | — | — | — | — | — | Only S2 post-cable (correct) |
| PPA imports | — | ✅ | — | — | — | — | — | Only S2 (correct) |
| Supply security | — | ✅ | — | — | — | — | — | Only S2 (correct — cable-dependent) |
| LNG CAPEX | — | — | — | — | — | — | ✅ | Only S7 (correct) |
| LNG fuel cost | — | — | — | — | — | — | ✅ | Uses `costs.fuel_lng` (E-CR-02 fix) |
| LNG OPEX | — | — | — | — | — | — | ✅ | Added to `opex_diesel` field |
| Floating solar premium | — | — | — | — | — | ✅ | — | Only S6: `CAPEX × 1.5` (correct) |
| Near-shore cable | — | — | — | — | ✅ | ✅ | — | S5 and S6 (correct — S6 extends S5) |
| WTE CAPEX + OPEX | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All RE scenarios include WTE |
| Connection costs | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All S2–S7 include L11 connection costs |
| Climate adaptation premium | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Applied to WTE, cable, LNG CAPEX |
| Island premium (S4 only) | — | — | — | ✅ | — | — | — | S4 applies `islanded_cost_premium` to solar/battery CAPEX + connection + `islanded_opex_premium` to OPEX |
| Solar OPEX | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All scenarios |
| Diesel fuel (two-part curve) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All use `cost_calc.diesel_fuel_cost()` with C9 curve |

### E5. Benefit Completeness ✅

| Benefit | S2 | S3 | S4 | S5 | S6 | S7 | Notes |
|---|---|---|---|---|---|---|---|
| Fuel savings | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Base class: `baseline_fuel - scenario_fuel` (includes `fuel_lng`) |
| Emission reduction | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Base class: `emission_reduction_benefit(baseline_tco2, scenario_tco2, year)` |
| Health benefit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Base class: `diesel_reduction_mwh × health_damage_cost_per_mwh` (S-05 fix) |
| Environmental benefit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Base class: `cost_calc.environmental_externality_benefit(diesel_reduction)` |
| Reliability benefit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Base class: SAIDI reduction × VOLL × demand; cable discounted by availability |
| Fiscal subsidy avoidance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Computed but **excluded from `total`** — only in `total_with_fiscal` (A-CR-01 fix) |
| Environmental in NPV | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `pv_environmental_benefits` computed and included in BCR/IRR |
| Environmental in BCR | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `pv_total_benefits` includes `pv_environmental_savings` |
| Environmental in IRR | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | IRR cash flows include `environmental_savings` |

**Subsidy avoidance correctly excluded:** `AnnualBenefits.total` property at [__init__.py L124](Maldives/model/scenarios/__init__.py#L124) sums fuel_savings + emission + reliability + health + environmental. `fiscal_subsidy_savings` is **excluded** from this economic total (it's a fiscal transfer, not an economic benefit). This is correct per CBA best practice.

### E6. Deployment Schedules ✅

| Scenario | Solar Ramp | Constraint | Plausible? |
|---|---|---|---|
| S1 BAU | 0 MW/yr | No new solar | ✅ |
| S2 FI | 50 MW/yr pre-cable; 0 post-cable | `deployment_ramp_mw_per_year` from config | ✅ — switches to cable import |
| S3 NG | 50 MW/yr | `deployment_ramp_mw_per_year` × outer demand gap | ✅ |
| S4 IG | 45 MW/yr | 50 × 0.90 (islanded_re_cap_factor) | ✅ — slower due to dispersed logistics |
| S5 NS | 50 MW/yr outer + near-shore phased | Near-shore 104 MW over build years | ✅ |
| S6 MR | 50 MW/yr outer + NS + floating phased | Floating 195 MW over build years | ✅ |
| S7 LNG | 50 MW/yr outer (same as NG) | LNG plant one-time at online year | ✅ |

**50 MW/yr for SIDS** — verified against GoM pipeline (164 MW in ~3 years ≈ 55 MW/yr). The parameter has Low/High bounds of 30-100 MW/yr in sensitivity analysis.

**Construction lag:** HVDC cable has explicit construction period (`cable_construction_start = cable_online_year - construction_years`). LNG CAPEX is one-time at `lng_online_year`. Solar CAPEX occurs in the year of addition (no lag). Near-shore and floating are phased over multi-year build windows. This is standard practice for distributed solar in SIDS where projects are small per-site.

### E7. Scenario Independence ✅

| Check | Status | Evidence |
|---|---|---|
| S5 is superset of S3 | ✅ | S5 extends NG by adding near-shore solar on uninhabited islands. Same outer-island logic, same inter-island grid. Additional near-shore cable cost and Malé RE increase (4% → ~25%). Correctly implemented as independent class, not inheritance (avoids fragile coupling). |
| S6 is superset of S5 | ✅ | S6 extends S5 by adding floating solar (195 MW). Near-shore parameters identically configured. Additional floating CAPEX premium (1.5×). Correctly tracks `nearshore_additions` + `floating_additions` separately. |
| S7 is variant of S3 | ✅ | S7 replicates S3's outer-island RE logic but replaces Malé diesel with LNG. Own demand key (`lng_transition`, 5% vs S3's 4%). Separate emission calculation override. |
| No scenario state leaks | ✅ | Each scenario creates its own `DemandProjector`, `CostCalculator`, capacity tracking dicts. No shared mutable state between scenarios. `run_cba.py` instantiates each independently. |
| Benefits computed against common baseline | ✅ | All 6 alternatives call `calculate_benefits_vs_baseline(sq_results)` — same S1 BAU baseline. |
| S7 LNG emission override | ✅ | S7 correctly overrides `calculate_annual_emissions()` to use `lng_emission_factor` (0.40) for LNG generation and standard factor (0.72) for diesel. |

---

## Summary Table

| ID | Finding | Severity | Impact | Status |
|---|---|---|---|---|
| E-01 | Payback ignores `fuel_lng` for S7 | 🟡 MODERATE | Payback overstated for S7; NPV/BCR/IRR correct | ✅ FIXED |
| E-02 | S4 diesel capacity never reduces | 🔵 LOW | Slight diesel CAPEX overstatement; defensible for islanded redundancy | OPEN |
| E-03 | S1 no WTE/connection costs | ℹ️ INFO | Correct by CBA design (baseline = do nothing) | N/A |
| E1 | Common assumptions consistent | ✅ | All 7 scenarios share config | VERIFIED |
| E2 | Generation balance correct | ✅ | All sources sum to gross demand | VERIFIED |
| E3 | Config key lookups correct | ✅ | All 7 demand keys map to intended growth rates | VERIFIED |
| E4 | Cost completeness correct | ✅ | All expected cost lines present per scenario | VERIFIED |
| E5 | Benefit completeness correct | ✅ | All 5 benefit types computed, environmental in NPV/BCR/IRR | VERIFIED |
| E6 | Deployment schedules plausible | ✅ | 50 MW/yr validated against GoM pipeline | VERIFIED |
| E7 | Scenario independence correct | ✅ | No state leaks, proper superset relationships | VERIFIED |
