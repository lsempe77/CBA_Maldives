# Workstream G: Supplementary Modules & Outputs

## Executive Summary

Audited five supplementary modules: distributional analysis, financing analysis, transport analysis, MCA, and sanity checks. Found **3 moderate** and **5 low-severity** issues. The most consequential finding is **MCA double-counting**: the "economic efficiency" criterion (NPV savings) already internalises emissions via SCC and health benefits, yet MCA also scores these separately as "environmental impact" and "health benefits" — inflating the weight of green scenarios. The distributional module is well-crafted but constructs quintiles without survey weights (uses unweighted `pd.qcut`). The transport module uses identical S-curve shape parameters (midpoint & steepness) for all three scenarios — only the target differs — limiting the information value of the scenario spread. Overall the supplementary modules are well-isolated, sourced, and documented.

**Severity summary:** 0 Critical, 3 Moderate, 5 Low

---

## Findings

### G-MO-01 [MODERATE] — MCA double-counts emissions and health already in NPV

**File:** [cba/mca_analysis.py](Maldives/model/cba/mca_analysis.py#L128-L193)

**Evidence:**
- `economic_efficiency` criterion uses `inc.get("npv_savings")` which is `IncrementalResult.npv` — defined at [npv_calculator.py#L555](Maldives/model/cba/npv_calculator.py#L555) as `pv_total_benefits - incremental_costs`.
- `pv_total_benefits` ([npv_calculator.py#L544-L548](Maldives/model/cba/npv_calculator.py#L544-L548)) = `pv_fuel_savings + pv_emission_savings + pv_health_savings + pv_reliability_savings + pv_environmental_savings`.
- The MCA then separately scores `environmental_impact` (physical CO₂ reduction, [line 136](Maldives/model/cba/mca_analysis.py#L136)) and `health_benefits` (`pv_health_benefits`, [line 142](Maldives/model/cba/mca_analysis.py#L142)).
- This means the **same** emission and health benefits are weighted twice: once inside the NPV savings criterion (20% weight) and again as standalone criteria (15% + 10% = 25% weight).

**Impact:** Scenarios with large emission reductions and health gains (S6, S4, S5) receive an artificially inflated composite score. The double-counting overstates the gap between green and fossil-heavy scenarios. With 8 criteria at the current weights, the effective weight on emissions-related performance is ~35% (20% × portion in NPV + 15% standalone), not the intended ~15%.

**Recommendation:** Either:
1. **Preferred:** Redefine `economic_efficiency` as NPV savings **excluding** SCC and health (`pv_fuel_savings - incremental_costs`) — i.e. pure financial merit.
2. **Alternative:** Note prominently in the output that MCA criteria are partially collinear and interpret rankings accordingly.

---

### G-MO-02 [MODERATE] — Quintile construction ignores survey weights

**File:** [distributional_analysis.py#L429-L431](Maldives/model/distributional_analysis.py#L429-L431)

**Evidence:**
```python
m['pce'] = m['total_annual_exp'] / m['hhsize']
m['exp_quintile'] = pd.qcut(m['pce'], N_QUINTILES, labels=range(1, N_QUINTILES + 1))
```
`pd.qcut` splits by count of observations, not by survey weight. In a stratified survey like HIES 2019 (with oversampling of Malé and small atolls), each household represents a different number of population units. The correct procedure is to compute weighted quintile boundaries — i.e., find PCE thresholds such that each quintile contains ~20% of the **weighted** population.

Downstream statistics (quintile means, energy poverty by quintile, Suits index) all use `wgt` correctly, but the quintile *assignment* itself is unweighted.

**Impact:** Quintile boundaries are mis-placed. Malé households (oversampled) are over-represented in the raw count, pulling Q5 thresholds upward. The poorest quintile (Q1) may contain too few real-population households, biasing burden and energy-poverty statistics within quintiles.

**Recommendation:** Replace `pd.qcut(m['pce'], N_QUINTILES, ...)` with a weighted quantile function:
```python
m = m.sort_values('pce')
cumwgt = m['wgt'].cumsum() / m['wgt'].sum()
m['exp_quintile'] = pd.cut(cumwgt, bins=5, labels=range(1, 6))
```
Or use `np.searchsorted` on weighted cumulative distribution for exact boundaries.

---

### G-MO-03 [MODERATE] — Transport S-curve: same midpoint & steepness for all three scenarios

**File:** [transport_analysis.py#L147-L148](Maldives/model/transport_analysis.py#L147-L148)

**Evidence:**
```python
ev_share = _logistic_ev_share(
    year, tr.ev_share_2026, ev_target, tr.ev_adoption_midpoint, tr.ev_adoption_steepness
)
```
All three EV scenarios (Low 30% / Medium 60% / High 85%) use the **identical** `ev_adoption_midpoint` (2038) and `ev_adoption_steepness` (0.25). Only the asymptotic target `s_max` varies. This means:
- All three curves inflect at the same year.
- The "Low" scenario is just a compressed version of "High" — no policy/market mechanism differentiates the adoption pathway.
- In real-world diffusion modelling (Bass 1969, Griliches 1957), different market conditions imply different midpoints and growth rates.

**Impact:** The scenario spread understates uncertainty in adoption timing. A "Low" scenario plausibly has a later midpoint (e.g. 2043) and lower steepness (e.g. 0.15), while "High" could have an earlier midpoint (e.g. 2035) and steepness 0.35. Current parameterisation makes all three scenarios converge to the same early-adoption pattern, differing only in ceiling.

**Recommendation:** Add per-scenario midpoint and steepness parameters to `parameters.csv` and `TransportConfig`:
- Low: `t_mid=2043, k=0.18`
- Medium: `t_mid=2038, k=0.25` (current)
- High: `t_mid=2034, k=0.30`

---

### G-LO-01 [LOW] — Energy poverty threshold (10%) not validated for Maldives

**File:** [distributional_analysis.py#L790-L800](Maldives/model/distributional_analysis.py#L790-L800)

**Evidence:** The 10% threshold (Boardman 1991; Hills 2012) is a UK-origin metric designed for temperate climates with heating needs. Maldives has no heating requirement — energy poverty manifests as inability to afford electricity for lighting, cooling, and refrigeration. The IEA and ESMAP use multidimensional energy poverty indices (MEPI) for tropical SIDS.

**Impact:** The absolute headcount may be misleading. In Maldives, where average electricity expenditure share is ~4-6%, a 10% threshold may capture only extreme outliers, while a 5% threshold would be more policy-relevant. The relative comparisons across scenarios remain valid regardless of threshold.

**Recommendation:** Add a footnote/caveat in outputs. Optionally compute a secondary threshold at 5% or use the OECD "twice the median" relative threshold. The current 10% threshold is acceptable for cross-country comparability.

---

### G-LO-02 [LOW] — Financing: ADB loan extends beyond model horizon (40yr > 30yr)

**File:** [financing_analysis.py#L265-L285](Maldives/model/financing_analysis.py#L265-L285)

**Evidence:** The ADB SIDS loan has 40-year maturity with 10-year grace. The CBA model horizon is 30 years (2026-2056). The financing module correctly builds the full 40-year amortisation schedule ([line 254](Maldives/model/financing_analysis.py#L254): `for t in range(1, maturity_years + 1)`), so debt service is computed for years 2027-2066. The fiscal metrics (peak service % GDP) correctly include years beyond 2056.

**Impact:** No error — the financing module handles this correctly. Noted for completeness: peak debt service year may fall in 2037-2046 (during amortisation after grace), which is within the 30-year CBA horizon. The grant element calculation is self-contained and unaffected by the CBA horizon.

**Recommendation:** No action needed. Correctly handled.

---

### G-LO-03 [LOW] — Financing: GDP denominator grows over time (correctly)

**File:** [financing_analysis.py#L334-L340](Maldives/model/financing_analysis.py#L334-L340)

**Evidence:**
```python
# G-MO-02: Use year-specific GDP — project GDP forward from base year
gdp_at_peak = gdp * (1 + gdp_growth) ** max(years_forward, 0)
```
The code projects GDP forward from the base year at `gdp_growth_rate` (5% from parameters.csv, sourced from IMF Article IV 2024). Peak debt service as % GDP uses the projected GDP for the peak year.

**Impact:** Correctly implemented. The label `G-MO-02` in the code suggests this was a prior audit fix that has been applied.

**Recommendation:** No action needed. Verified correct.

---

### G-LO-04 [LOW] — Transport: grid emissions for EV charging use static BAU diesel EF

**File:** [transport_analysis.py#L197-L203](Maldives/model/transport_analysis.py#L197-L203)

**Evidence:**
```python
# NOTE (MR-06): Uses static diesel EF for grid emissions. This is conservative —
# as RE share increases, the actual grid EF declines. Since transport analysis
# is a supplementary module (not linked to scenario RE trajectories), the
# static assumption avoids coupling complexity and overstates EV grid CO₂.
co2_grid = ev_elec_mwh * config.fuel.emission_factor_kg_co2_per_kwh / 1000
```
The EV charging CO₂ is computed at the full diesel emission factor (0.72 kgCO₂/kWh) rather than the scenario-specific grid EF that declines as RE penetrates.

**Impact:** This is conservative — it understates the net CO₂ benefit of EVs. The model already notes this (MR-06 comment). Since the transport module is supplementary and not linked to specific energy scenarios, this is an acceptable simplification. The direction of bias is clearly stated.

**Recommendation:** Document in outputs that CO₂ savings are conservative lower bounds. Optionally accept a scenario RE share trajectory as input to compute time-varying grid EF.

---

### G-LO-05 [LOW] — Sanity checks: missing generation balance and temporal monotonicity checks

**File:** [sanity_checks.py](Maldives/model/sanity_checks.py)

**Evidence:** The 47 checks cover LCOE, costs, emissions, fuel, demand, solar, NPV, BCR, RE shares, health, cable, WTE, LNG, and consistency. Missing checks include:
1. **Generation = demand + losses** — no check that total generation across all sources equals demand × (1 + losses).
2. **Temporal monotonicity** — no check that BAU demand is monotonically increasing (at 5% growth, it should never decrease).
3. **Cost summation** — no check that `pv_total_costs = pv_capex + pv_opex + pv_fuel + pv_emission_costs - salvage`.
4. **Cross-scenario demand consistency** — no check that all scenarios serve the same demand trajectory (with elasticity adjustments).

**Impact:** These are structural invariants that would catch future regression bugs. Not a current error but a coverage gap.

**Recommendation:** Add 4 additional sanity checks for generation balance, demand monotonicity, cost identity, and cross-scenario demand consistency.

---

### G-LO-06 [LOW] — Sanity check ranges partially arbitrary

**File:** [sanity_checks.py](Maldives/model/sanity_checks.py) (throughout)

**Evidence:** Each `SanityCheck` has a `source` field citing the benchmark origin (IRENA, ADB, IEA, etc.), which is good. However, some ranges are generous enough that they would pass even with significant errors:
- BAU diesel LCOE: $0.25–$0.55/kWh (2.2× range)
- BAU per-capita costs: $15k–$45k (3× range)
- Solar CAPEX: $800–$2,500/kWh (3.1× range)

Additionally, the WARN zone is defined as `0.8 × low` to `1.2 × high` ([line 48-52](Maldives/model/sanity_checks.py#L48-L52)) — so even a value 20% outside the range only gets WARN, not FAIL. This effectively makes the acceptable band 40% wider than stated.

**Impact:** Overly wide ranges reduce the diagnostic power of the checks. A 2× error in solar CAPEX would still pass.

**Recommendation:** Tighten ranges where firmer benchmarks exist. Consider replacing the symmetric WARN buffer with asymmetric bounds tailored to each parameter. Not critical — these are guardrail checks, not precision tests.

---

## Verified Correct

| Item | Module | Detail |
|------|--------|--------|
| Survey weights for means | `distributional_analysis.py` | All `np.average(..., weights=wgt)` calls use `wgt` column. Mean bills, shares, income — all weighted. ✅ |
| Weighted median | `distributional_analysis.py` | `_weighted_median()` function at [line 60](Maldives/model/distributional_analysis.py#L60) — correctly implements weighted median using cumulative weight. G-MO-01 fix applied. ✅ |
| Gender analysis uses weights | `distributional_analysis.py` | `_compute_gender_profiles()` uses `np.average(..., weights=wgt)` for bill, share, income. Energy poverty computed as weighted headcount ratio. Solar adoption uses weighted share. Share of total uses `wgt.sum() / df['wgt'].sum()` (G-LO-01 fix). ✅ |
| Missing data handling | `distributional_analysis.py` | Energy expenditures filled with 0 for non-reporters ([line 410-412](Maldives/model/distributional_analysis.py#L410-L412)). `has_solar` filled with False. Gender fallback if Usualmembers.dta missing. `has_elec` derived from `elec_annual > 0`. ✅ |
| Grant element formula | `financing_analysis.py` | Standard OECD-DAC/IMF method: `1 - PV(debt service at commercial rate) / face value` ([line 182-210](Maldives/model/financing_analysis.py#L182-L210)). Grace period → interest-only; amortisation → equal principal. Discounted at commercial rate (11.55%). ✅ |
| ADB terms → GE = 82.8% | `financing_analysis.py` | With 1%/40yr/10yr grace at 11.55% commercial → GE ≈ 82.8%. Formula verified manually. ✅ |
| MCA weights sum validated | `cba/mca_analysis.py` | `_validate_weights()` at [line 66-72](Maldives/model/cba/mca_analysis.py#L66-L72) raises `ValueError` if `abs(sum - 1.0) > 0.001`. Defaults sum to 1.00 (0.20+0.15+0.15+0.10+0.10+0.10+0.10+0.10). ✅ |
| MCA normalisation polarity | `cba/mca_analysis.py` | `CRITERION_DIRECTION` at [line 201-210](Maldives/model/cba/mca_analysis.py#L201-L210): `fiscal_burden` → `"lower_better"`, all others → `"higher_better"`. Normalisation at [line 231-239](Maldives/model/cba/mca_analysis.py#L231-L239) inverts for `lower_better`: `norm = (v_max - raw) / spread`. ✅ |
| All 6 alternative scenarios scored | `cba/mca_analysis.py` | `scenarios_alt` list at [line 126](Maldives/model/cba/mca_analysis.py#L126) includes all 6 alternatives (S2-S7). BAU excluded as baseline. ✅ |
| Transport isolation from CBA | `transport_analysis.py` + `run_cba.py` | Transport runs after CBA at [run_cba.py#L1243-L1244](Maldives/model/run_cba.py#L1243-L1244), does not feed back into NPV. Output saved separately. Docstring confirms isolation. ✅ |
| Transport: motorcycle-calibrated | `transport_analysis.py` | Fleet × `motorcycle_share` (0.92) applied to all per-vehicle calculations (fuel, health, premium). Car/van remainder ignored with documented note (LW-05). ✅ |
| 131k vehicles, 92% motorcycles | `config.py` + `parameters.csv` | `total_vehicles_2026 = 131_000`, `motorcycle_share = 0.92`. Sourced from Malé City Council/World Bank 2022 and gathunkaaru.com 2024. ✅ |
| Financing: debt service beyond 30yr | `financing_analysis.py` | Full 40-year schedule built; fiscal metrics use all years. GDP projected forward for peak-year % GDP. ✅ |
| Suits index implementation | `distributional_analysis.py` | Lorenz-curve-based Suits index at [line 871-908](Maldives/model/distributional_analysis.py#L871-L908): sorted by PCE, weighted cumulative shares, trapezoidal integration, `S = 1 - 2 × area`. Correct per Suits (1977). ✅ |
| Concentration coefficient | `distributional_analysis.py` | Kakwani (1977) method at [line 838-868](Maldives/model/distributional_analysis.py#L838-L868): weighted covariance of electricity share and fractional rank. ✅ |
| Weight sensitivity profiles | `cba/mca_analysis.py` | Four profiles tested (equal, economic, environmental, equity) at [line 409-450](Maldives/model/cba/mca_analysis.py#L409-L450). All sum to 1.0. ✅ |
| Sanity check coverage | `sanity_checks.py` | 47 checks across 13 categories: LCOE (6), System Costs (3), Emissions (5), Fuel (2), Demand (3), Solar (3), NPV (14), RE Share (2), Health (1), Cable (2), WTE (2), LNG (2), Consistency (4). ✅ |
| Sanity checks sourced | `sanity_checks.py` | Every check has a `source` field citing IRENA, ADB, IEA, IPCC, or cross-referenced model identity. ✅ |

---

## Summary Table

| ID | Severity | Module | Finding | Recommendation |
|----|----------|--------|---------|----------------|
| G-MO-01 | 🟡 MODERATE | MCA | Double-counting: NPV savings includes SCC + health, then scored again as separate criteria | Redefine economic_efficiency as pure financial NPV (excl. SCC/health) |
| G-MO-02 | 🟡 MODERATE | Distributional | Quintile construction uses unweighted `pd.qcut` — ignores survey weights | Use weighted quantile boundaries |
| G-MO-03 | 🟡 MODERATE | Transport | Same S-curve midpoint & steepness for Low/Medium/High — only target varies | Add per-scenario midpoint and steepness parameters |
| G-LO-01 | 🔵 LOW | Distributional | 10% energy poverty threshold not validated for tropical SIDS | Add caveat; optionally compute 5% threshold |
| G-LO-02 | 🔵 LOW | Financing | ADB 40yr loan extends beyond 30yr model horizon | Verified correct — full schedule built |
| G-LO-03 | 🔵 LOW | Financing | GDP denominator grows over time | Verified correct — G-MO-02 fix applied |
| G-LO-04 | 🔵 LOW | Transport | Grid EF for EV charging uses static diesel EF, not scenario-specific | Conservative; document in outputs |
| G-LO-05 | 🔵 LOW | Sanity Checks | Missing: generation balance, temporal monotonicity, cost identity, cross-scenario demand | Add 4 structural invariant checks |
| G-LO-06 | 🔵 LOW | Sanity Checks | Benchmark ranges 2-3× wide; WARN buffer adds 20% | Tighten where firmer benchmarks exist |
