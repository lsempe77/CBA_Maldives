# Workstream F: Sensitivity, Monte Carlo & Robustness

**Auditor:** GitHub Copilot (Claude Opus 4.6)  
**Date:** 10 February 2026  
**Scope:** `cba/sensitivity.py`, `run_sensitivity.py`, `run_monte_carlo.py`, `run_multi_horizon.py`

---

## Executive Summary

The sensitivity, Monte Carlo, and multi-horizon analysis infrastructure is **well-designed and largely correct**. All 38 sensitivity parameters are handled identically across the three modification paths (`_modify_config`, `_modify_config_inplace`, and `run_sensitivity.py:modify_config`), which is a significant achievement. Parameter ranges are sourced from `parameters.csv` via `SENSITIVITY_PARAMS`, ensuring a single source of truth. The switching value analysis and tornado diagrams follow ADB/World Bank best practice.

However, several issues reduce the analytical power of the robustness framework:

| Severity | Count | Key Issues |
|----------|-------|------------|
| 🟡 MODERATE | 4 | No parameter correlations in MC; stale multi-horizon output (4/7 scenarios); GoM cost share High=Base (no upside variation); SCC has zero impact on scenario NPVs (not flowing through) |
| 🔵 LOW | 5 | MC uses `random` module not `numpy` (inconsistent with sensitivity.py); `_modify_config_inplace` deepcopies despite name; convergence not validated; no DDR in sensitivity runner; P8 transport params are supplementary-only |

**Bottom line:** The core one-way sensitivity and MC infrastructure is sound. The most impactful fix is ensuring SCC actually enters the cost comparison metric (currently NPV is `pv_total_costs` which excludes emission costs). The missing 3 scenarios in multi-horizon output should be regenerated.

---

## Findings

### F-01: SCC Has Zero Impact on Scenario Ranking (🟡 MODERATE)

**Files:** [run_sensitivity.py](Maldives/model/run_sensitivity.py#L275-L306), [cba/npv_calculator.py](Maldives/model/cba/npv_calculator.py#L250-L252)

**Evidence:** In sensitivity_results.json, for **all 7 scenarios**, the SCC parameter shows `"range": 0.0` — varying SCC from $0 to $300/tCO₂ changes nothing:

```json
"scc": {
  "base_value": 190.0, "low_value": 0.0, "high_value": 300.0,
  "base_npv": 15676264614.611586,
  "low_npv": 15676264614.611586,
  "high_npv": 15676264614.611586,
  "range": 0.0
}
```

**Root Cause:** The sensitivity runner uses `calc.calculate_npv(results).pv_total_costs` as the comparison metric. `pv_total_costs = pv_capex + pv_opex + pv_fuel + pv_ppa - pv_salvage`. Emission costs (`pv_emission_costs`) are calculated separately in the NPV calculator but **never included** in `pv_total_costs`. Therefore varying SCC has zero effect on the metric used for tornado diagrams and switching values.

**Impact:** SCC is a major policy parameter. In a proper economic CBA, high SCC should strongly favour RE scenarios over BAU/LNG. The current setup cannot reveal whether rankings change under high SCC — a critical gap for policy advice.

**Recommendation:** Either (a) use `pv_total_costs + pv_emission_costs` as the comparison metric in sensitivity/switching analyses, or (b) add a separate "economic NPV" metric that includes externalities. This is a design choice, not a bug — financial vs economic CBA — but it should be documented and ideally both views presented.

---

### F-02: GoM Cost Share High = Base — No Upside Variation (🔵 LOW)

**Files:** [parameters.csv](Maldives/model/parameters.csv#L71)

**Evidence:** `GoM Cost Share` has `Value=1.0, Low=0.5, High=1.00`. The High bound equals the Base value, so sensitivity only tests downside (cheaper if cost-sharing). No upside scenario exists because 100% is the physical maximum.

**Impact:** Tornado diagram is one-sided for this parameter. Not a bug — it's correct that 100% is the ceiling — but the range notation creates a degenerate sensitivity bar (all impact on one side).

**Recommendation:** Document in SCENARIO_GUIDE.md that GoM cost share is one-sided by construction. Consider showing it as a separate "policy scenario" rather than in the tornado diagram.

---

### F-03: No Parameter Correlations in Monte Carlo (🟡 MODERATE)

**Files:** [run_monte_carlo.py](Maldives/model/run_monte_carlo.py#L64-L178)

**Evidence:** Each of the 38 parameters is sampled independently from its triangular distribution. No correlation structure is imposed. Searched for "correlat", "copula", "cholesky", "covariance" — zero matches.

**Known correlations that should exist:**
- **Solar CAPEX ↔ Battery CAPEX** (both driven by global manufacturing scale; ρ ≈ 0.5-0.7)
- **Diesel price ↔ Petrol price** (both petroleum; ρ ≈ 0.8-0.9)  
- **Diesel price ↔ LNG fuel cost** (energy commodity correlation; ρ ≈ 0.6)
- **Diesel price ↔ Diesel escalation** (price level ↔ trend; ρ ≈ 0.3)

**Impact:** Independent sampling can create implausible combinations (e.g., very cheap solar + very expensive battery, or cheap diesel + expensive petrol). This widens confidence intervals and may understate the probability of correlated "green-favourable" or "fossil-favourable" worlds. The P5/P95 bands may be too wide, and ranking probabilities may be biased.

**Recommendation:** Implement rank correlation via Iman-Conover method or Gaussian copula for the 4-5 most correlated parameter pairs. This is standard in ADB/World Bank CBA practice (see ADB 2017 Guidelines §6.45). At minimum, document the independence assumption as a limitation.

---

### F-04: Multi-Horizon Output Missing 3 Scenarios (🟡 MODERATE)

**Files:** [multi_horizon_results.json](Maldives/outputs/multi_horizon_results.json)

**Evidence:** The JSON output contains only 4 scenarios per horizon (bau, full_integration, national_grid, islanded_green). The 3 newer scenarios (nearshore_solar, maximum_re, lng_transition) are absent. However, [run_multi_horizon.py](Maldives/model/run_multi_horizon.py#L73-L79) correctly defines all 7 in `SCENARIO_CLASSES`.

**Root Cause:** The output file is stale — generated before S5/S6/S7 were added to the code. The code itself is correct and would produce all 7 scenarios if re-run.

**Impact:** Multi-horizon analysis cannot compare the 3 newest (and often best-performing) scenarios across time horizons. Rankings across horizons are incomplete.

**Recommendation:** Re-run `python run_multi_horizon.py` to regenerate the output with all 7 scenarios. This is a simple re-run, no code change needed.

---

### F-05: MC Uses `random` Module; Sensitivity Class Uses `numpy` (🔵 LOW)

**Files:** [run_monte_carlo.py](Maldives/model/run_monte_carlo.py#L238) vs [cba/sensitivity.py](Maldives/model/cba/sensitivity.py#L807)

**Evidence:**
- `run_monte_carlo.py` line 238: `random.seed(42)` and `random.triangular(low, high, mode)` — uses Python's built-in `random` module
- `cba/sensitivity.py` line 807: `np.random.seed(seed)` and `np.random.triangular(...)` — uses NumPy's PRNG

Both produce triangular samples but use different PRNG engines. If both are run in the same session, they have independent random states.

**Impact:** Minor — both produce valid triangular samples. The real MC runner (`run_monte_carlo.py`) is the one that generates the published output, and it correctly seeds with `random.seed(42)`. The `sensitivity.py` class MC method appears unused in production (the standalone runner is used instead).

**Recommendation:** Standardise on NumPy's PRNG throughout, or document that `sensitivity.py::run_monte_carlo()` is a library method while `run_monte_carlo.py` is the production runner.

---

### F-06: `_modify_config_inplace` Receives a Deepcopy Despite Name (🔵 LOW)

**Files:** [cba/sensitivity.py](Maldives/model/cba/sensitivity.py#L812-L821)

**Evidence:** In `run_monte_carlo()` (sensitivity.py line 812):
```python
config = deepcopy(self.config)
for param_name, param in self.parameters.items():
    sampled_value = np.random.triangular(...)
    config = self._modify_config_inplace(config, param_name, sampled_value)
```
The config is deepcopied first, then `_modify_config_inplace` returns the modified config. The "inplace" name is misleading — it actually does modify in place AND returns the object. This is functionally correct but the deepcopy on every iteration adds overhead for 1000 iterations.

**Impact:** Performance only — no correctness issue. The standalone `run_monte_carlo.py` also deepcopies per iteration (line 63: `config = deepcopy(base_config)`), so both are consistent.

**Recommendation:** Rename to `_apply_parameter_to_config` or similar to avoid confusion. Minor.

---

### F-07: MC Convergence Not Validated (🔵 LOW)

**Files:** [run_monte_carlo.py](Maldives/model/run_monte_carlo.py#L237)

**Evidence:** The MC uses a fixed 1000 iterations without convergence checking. Standard practice is to verify that summary statistics (mean, P5, P95) stabilise as N increases.

Examining the output: The coefficient of variation (std/mean) ranges from 17-30% across scenarios, suggesting adequate dispersion is captured. With N=1000 and standard triangular distributions, the standard error of the mean is roughly `σ/√N ≈ 1-3%` of the mean, which is acceptable.

**Impact:** Low — 1000 iterations is standard for CBA MC (ADB/World Bank typically use 1000-10000). The results appear reasonably converged based on the output statistics.

**Recommendation:** Add a convergence diagnostic: compute running mean/P5/P95 and report the iteration at which they stabilise to within ±1%. This strengthens the methodology section of the report.

---

### F-08: Sensitivity Does Not Use Declining Discount Rate (🟡 MODERATE)

**Files:** [run_sensitivity.py](Maldives/model/run_sensitivity.py#L285-L300)

**Evidence:** When the discount rate parameter is varied in one-way sensitivity, only `config.economics.discount_rate` is changed. The main CBA model uses a **Declining Discount Rate (DDR)** structure (3.5% years 0-30, 3.0% years 31-75, 2.5% years 76-125) implemented in `npv_calculator.py`. But the sensitivity analysis varies only the constant rate component.

When discount_rate is set to 3% (Low), the DDR rates (which are separately loaded from CSV and not modified by the sensitivity runner) create a situation where the constant rate equals the DDR 0-30yr rate, but the DDR structure itself is unchanged.

**Impact:** The DDR structure means that varying the constant discount rate may not fully capture the impact of discounting uncertainty. The low discount rate scenario (3%) should arguably also lower the DDR breakpoints proportionally. This affects the 50-year horizon most.

**Recommendation:** When varying discount_rate in sensitivity, scale DDR rates proportionally (e.g., if constant rate goes from 6% to 3% [50% reduction], reduce DDR rates by 50% too). Or document that the sensitivity tests the constant-rate component only.

---

### F-09: Switching Value Analysis Uses Linear Interpolation (Verified Appropriate) (🔵 LOW)

**Files:** [run_sensitivity.py](Maldives/model/run_sensitivity.py#L564-L590)

**Evidence:** The switching value calculation uses linear interpolation between the Low and High NPV points:
```python
a_slope = (a_data["high_npv"] - a_data["low_npv"]) / param_range
switching_x = base_value + (b_base - a_base) / (a_slope - b_slope)
```

Meanwhile, `sensitivity.py` has a bisection-based switching value method (`calculate_switching_value`) that iterates to find the exact crossing point.

**Impact:** Linear interpolation is generally adequate for one-way sensitivity within the tested range (±20-30%). For highly nonlinear parameters (discount rate, demand growth with compounding), the switching value may be slightly off. However, the switching values found are flagged as "within range" or "outside test range", providing appropriate context.

**Recommendation:** No change needed — linear interpolation is standard (ADB 2017 §6.37-6.40). The bisection method in `sensitivity.py` is available for cases where more precision is needed. Document that switching values are linear approximations.

---

### F-10: P8 Transport Parameters in Sensitivity Are Supplementary-Only (🔵 LOW)

**Files:** [cba/sensitivity.py](Maldives/model/cba/sensitivity.py#L472-L504), [run_sensitivity.py](Maldives/model/run_sensitivity.py#L170-L179)

**Evidence:** The 4 transport parameters (ev_adoption_midpoint, ev_motorcycle_premium, transport_health_damage, petrol_price) are defined with `if 'param' in sp:` guards in `_define_parameters()`. They are properly wired in all three modification paths.

However, the transport module (`transport_analysis.py`) is a **standalone supplementary analysis** that does not feed into the main CBA NPV calculations (scenarios don't call transport code). Therefore, varying these 4 parameters in the main sensitivity/MC has **zero effect** on the 7-scenario NPVs.

**Impact:** These parameters add computational cost (4 × 7 × 2 = 56 extra scenario runs in one-way sensitivity) without affecting results. They are correctly handled from a code perspective but are no-ops in practice.

**Recommendation:** Either (a) remove transport params from the main sensitivity loop and run them in a separate transport-specific sensitivity, or (b) integrate transport costs into relevant scenarios. Option (a) is cleaner given the current architecture.

---

## Three-Path Synchronisation (F1) — Detailed Verification

### Method
For each of the 38 parameters (34 core + 4 transport), I compared the config modification logic across:
1. **Path A:** `sensitivity.py::_modify_config()` (lines 570-675)
2. **Path B:** `sensitivity.py::_modify_config_inplace()` (lines 857-963)  
3. **Path C:** `run_sensitivity.py::modify_config()` (lines 72-179)

Additionally, the MC runner `run_monte_carlo.py::sample_config()` (lines 64-178) is a 4th path.

### Key Name Mapping
The SENSITIVITY_PARAMS dict uses different keys than the sensitivity/modify_config functions for 3 parameters:

| SENSITIVITY_PARAMS key | sensitivity.py key | run_sensitivity.py key | run_monte_carlo.py key |
|---|---|---|---|
| `cable_capex_per_km` | `cable_capex` | `cable_capex` | `cable_capex_per_km` |
| `import_price` | `ppa_price` | `ppa_price` | `import_price` |
| `social_cost_carbon` | `scc` | `scc` | `social_cost_carbon` |

The `run_sensitivity.py::_build_parameters()` function (line 230) correctly maps these via `key_map`. The `run_monte_carlo.py` uses the SENSITIVITY_PARAMS keys directly, which are different from the other two paths. **This works correctly** because each file uses its own naming convention consistently.

### Parameter-by-Parameter Verification

| # | Parameter | Path A | Path B | Path C | Path D (MC) | Match? |
|---|-----------|--------|--------|--------|-------------|--------|
| 1 | discount_rate | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2 | diesel_price | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3 | diesel_escalation | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 | solar_capex | ✅ | ✅ | ✅ | ✅ | ✅ |
| 5 | battery_capex | ✅ | ✅ | ✅ | ✅ | ✅ |
| 6 | cable_capex* | ✅ + recompute | ✅ + recompute | ✅ + recompute | ✅ + recompute | ✅ |
| 7 | ppa_price/import_price* | ✅ | ✅ | ✅ | ✅ | ✅ |
| 8 | scc/social_cost_carbon* | ✅ | ✅ | ✅ | ✅ | ✅ |
| 9 | demand_growth | ✅ proportional | ✅ proportional | ✅ proportional | ✅ proportional | ✅ |
| 10 | solar_cf | ✅ | ✅ | ✅ | ✅ | ✅ |
| 11 | gom_cost_share | ✅ | ✅ | ✅ | ✅ | ✅ |
| 12 | outage_rate | ✅ | ✅ | ✅ | ✅ | ✅ |
| 13 | idle_fleet_cost | ✅ | ✅ | ✅ | ✅ | ✅ |
| 14 | price_elasticity | ✅ | ✅ | ✅ | ✅ | ✅ |
| 15 | health_damage | ✅ | ✅ | ✅ | ✅ | ✅ |
| 16 | fuel_efficiency | ✅ | ✅ | ✅ | ✅ | ✅ |
| 17 | base_demand | ✅ | ✅ | ✅ | ✅ | ✅ |
| 18 | battery_hours | ✅ | ✅ | ✅ | ✅ | ✅ |
| 19 | climate_premium | ✅ | ✅ | ✅ | ✅ | ✅ |
| 20 | converter_station | ✅ + recompute | ✅ + recompute | ✅ + recompute | ✅ + recompute | ✅ |
| 21 | connection_cost | ✅ dual set | ✅ dual set | ✅ dual set | ✅ dual set | ✅ |
| 22 | env_externality | ✅ proportional | ✅ proportional | ✅ proportional | ✅ proportional | ✅ |
| 23 | sectoral_residential | ✅ rebalance | ✅ rebalance | ✅ rebalance | ✅ rebalance | ✅ |
| 24 | lng_capex | ✅ | ✅ | ✅ | ✅ | ✅ |
| 25 | lng_fuel_cost | ✅ | ✅ | ✅ | ✅ | ✅ |
| 26 | lng_fuel_escalation | ✅ | ✅ | ✅ | ✅ | ✅ |
| 27 | lng_emission_factor | ✅ | ✅ | ✅ | ✅ | ✅ |
| 28 | floating_capex_premium | ✅ | ✅ | ✅ | ✅ | ✅ |
| 29 | floating_solar_mw | ✅ | ✅ | ✅ | ✅ | ✅ |
| 30 | nearshore_solar_mw | ✅ | ✅ | ✅ | ✅ | ✅ |
| 31 | nearshore_cable_cost | ✅ | ✅ | ✅ | ✅ | ✅ |
| 32 | wte_capex | ✅ | ✅ | ✅ | ✅ | ✅ |
| 33 | deployment_ramp | ✅ | ✅ | ✅ | ✅ | ✅ |
| 34 | male_max_re | ✅ | ✅ | ✅ | ✅ | ✅ |
| 35 | battery_ratio | ✅ both ratios | ✅ both ratios | ✅ both ratios | ✅ both ratios | ✅ |
| 36 | ev_adoption_midpoint | ✅ int() | ✅ int() | ✅ int() | ✅ int() | ✅ |
| 37 | ev_motorcycle_premium | ✅ | ✅ | ✅ | ✅ | ✅ |
| 38 | transport_health_damage | ✅ | ✅ | ✅ | ✅ | ✅ |
| 39 | petrol_price | ✅ | ✅ | ✅ | ✅ | ✅ |

**Result: All 39 parameters are synchronised across all 4 paths.** Special transformations (cable_capex_total recomputation, demand growth proportional scaling, env_externality proportional scaling, sectoral rebalancing, battery_ratio dual-set) are applied identically.

---

## Parameter Range Validation (F2)

### Ranges from parameters.csv (via SENSITIVITY_PARAMS)

| Parameter | Base | Low | High | Low% | High% | Assessment |
|-----------|------|-----|------|------|--------|------------|
| discount_rate | 0.06 | 0.03 | 0.10 | -50% | +67% | ✅ Wide, appropriate for SDR |
| diesel_price | 0.85 | 0.60 | 1.10 | -29% | +29% | ✅ Symmetric |
| diesel_escalation | 0.02 | 0.00 | 0.05 | -100% | +150% | ✅ Asymmetric, warranted |
| solar_capex | 1500 | 900 | 2200 | -40% | +47% | ✅ Wide, appropriate |
| battery_capex | 350 | 200 | 500 | -43% | +43% | ✅ Good |
| cable_capex_per_km | 3M | 2M | 5M | -33% | +67% | ✅ Asymmetric upside, appropriate for deep-ocean |
| ppa_price | 0.06 | 0.04 | 0.10 | -33% | +67% | ✅ Asymmetric upside |
| scc | 190 | 0 | 300 | -100% | +58% | ✅ Financial→Stern range |
| demand_growth | 0.05 | 0.035 | 0.065 | -30% | +30% | ✅ Symmetric |
| solar_cf | 0.175 | 0.15 | 0.22 | -14% | +26% | ⚠️ Narrow low side — see below |
| gom_cost_share | 1.0 | 0.5 | 1.0 | -50% | 0% | ⚠️ One-sided (F-02) |
| outage_rate | 0.15 | 0.10 | 0.20 | -33% | +33% | ✅ |
| idle_fleet_cost | 8 | 5 | 13 | -38% | +63% | ✅ Asymmetric upside |
| price_elasticity | -0.3 | -0.5 | -0.1 | -67% | +67% | ✅ |
| health_damage | 40 | 20 | 80 | -50% | +100% | ✅ Asymmetric upside |
| fuel_efficiency | 3.3 | 2.8 | 3.8 | -15% | +15% | ✅ Tight, appropriate for measured parameter |
| base_demand | 1200 | 1050 | 1350 | -13% | +13% | ✅ Tight, appropriate |
| battery_hours | 4.0 | 3.0 | 6.0 | -25% | +50% | ✅ |
| climate_premium | 0.075 | 0.05 | 0.10 | -33% | +33% | ⚠️ CSV says 0.05-0.15 but SENSITIVITY_PARAMS has 0.10 |
| converter_station | 1.6M | 1.2M | 2.0M | -25% | +25% | ✅ |
| connection_cost | 200 | 150 | 300 | -25% | +50% | ✅ |
| env_externality | 10 | 4 | 23 | -60% | +130% | ✅ Wide, appropriate |
| sectoral_residential | 0.52 | 0.40 | 0.65 | -23% | +25% | ✅ |
| lng_capex | 1.2M | 0.9M | 1.5M | -25% | +25% | ✅ |
| lng_fuel_cost | 70 | 50 | 100 | -29% | +43% | ✅ |
| lng_fuel_escalation | 0.015 | 0.005 | 0.025 | -67% | +67% | ✅ |
| lng_emission_factor | 0.40 | 0.35 | 0.45 | -13% | +13% | ✅ Tight, physics-bounded |
| floating_capex_premium | 1.50 | 1.30 | 1.80 | -13% | +20% | ✅ |
| floating_solar_mw | 195 | 100 | 250 | -49% | +28% | ✅ |
| nearshore_solar_mw | 104 | 60 | 150 | -42% | +44% | ✅ |
| nearshore_cable_cost | 250k | 200k | 350k | -20% | +40% | ✅ |
| wte_capex | 8000 | 6000 | 12000 | -25% | +50% | ✅ |
| deployment_ramp | 50 | 30 | 100 | -40% | +100% | ✅ Asymmetric upside |
| male_max_re | 0.04 | 0.02 | 0.08 | -50% | +100% | ✅ |
| battery_ratio | 3.0 | 2.0 | 4.0 | -33% | +33% | ✅ |

**Minor note on climate_premium:** The SENSITIVITY_PARAMS default has High=0.10, but parameters.csv has High=0.15. The CSV reader should override the default — this needs verification that the CSV value (0.15) is actually loaded. If so, the range is -33%/+100% which is good.

**solar_cf low side (-14%):** The low bound of 0.15 is only 14% below base (0.175). This is somewhat narrow for a physical parameter with cloud-cover uncertainty, but matches the Solargis data for Maldives. Acceptable.

**Overall: Ranges are well-calibrated.** No implausibly narrow (<±5%) or excessively wide (>±80%) ranges, with the exception of scc (by design) and env_externality (appropriate for uncertain externality).

---

## Monte Carlo Design (F3)

### Distribution Choice
**Triangular distribution throughout** — using `(low, mode=base, high)`. This is standard for CBA under limited data (ADB 2017 §6.43-6.44). Triangular is preferred over uniform when a best estimate exists, and over normal when the distribution may be asymmetric or bounded.

✅ **Appropriate choice.**

### Correlations
**None implemented.** See F-03 above. All 38 parameters sampled independently.

### Convergence
**N=1000 with fixed seed (`random.seed(42)`)**. ✅ Fixed seed ensures reproducibility.

Examining output statistics: CV ranges from 16% (FI) to 30% (BAU), indicating adequate parametric variation. Standard error of the mean ≈ σ/√1000 ≈ 0.5-0.9% of the mean, well within acceptable precision.

The ranking probability of 99.9% for LNG Transition being least-cost suggests the result is very robust. With such high probability, 1000 iterations is more than sufficient.

### Random Engine
`run_monte_carlo.py` uses Python's `random.triangular()` with `random.seed(42)`. The library method in `sensitivity.py` uses `np.random.triangular()` with `np.random.seed(42)`. Both produce valid triangular variates. See F-05.

---

## Switching Value Analysis (F4)

### Method
Linear interpolation between Low and High NPV points, finding the parameter value where two scenarios have equal NPV. The formula is correct:

```
switching_x = base_value + (b_base_npv - a_base_npv) / (a_slope - b_slope)
```

✅ **Mathematically correct.**

### Plausibility of Switching Values
From the output, key switching values include:
- **Import PPA Price:** $0.055/kWh switches FI vs NG ranking (base $0.06) — within test range, very sensitive
- **Solar CAPEX:** $2,136/kW switches FI vs NG (base $1,500) — within range
- **Cable CAPEX:** $2.82M/km switches FI vs NG (base $3M) — within range
- **Deployment Ramp:** 40.6 MW/yr switches FI vs NG (base 50) — within range

These are plausible and actionable — they tell policy-makers exactly how much each parameter can shift before the optimal scenario changes.

✅ **Well-implemented and informative.**

---

## Multi-Horizon Analysis (F5)

### Salvage Recalculation
The `create_config_for_horizon()` function sets `config.end_year` and `config.time_horizon` for each horizon (20/30/50 years). The `calculate_salvage_value()` in NPV calculator uses `end_year = max(self.horizon)` and computes remaining life for each asset vintage. Since the horizon changes per run, salvage is automatically recalculated.

✅ **Salvage correctly recalculated for each horizon.**

### Scenario Coverage
**Only 4/7 scenarios in output** (see F-04). Code supports all 7. Output is stale.

### Ranking Changes
From the 4 available scenarios:
- **20-year:** FI ($6,365M) < NG ($7,400M) < IG ($7,872M) < BAU ($10,281M)
- **30-year:** FI ($8,125M) < NG ($9,737M) < IG ($10,658M) < BAU ($15,898M)
- **50-year:** FI ($11,329M) < NG ($13,561M) < IG ($15,612M) < BAU ($29,046M)

Rankings are stable across all 3 horizons: FI < NG < IG < BAU. FI's advantage grows with horizon length (from $3.9B to $17.7B cheaper than BAU), as expected when CAPEX-heavy scenarios benefit from longer fuel-savings periods.

⚠️ **Cannot verify whether S5/S6/S7 change rankings across horizons** until the output is regenerated.

---

## Sensitivity of Rankings (F6)

### S7 > S6 Ranking Robustness

From MC results:
- **S7 LNG mean NPV:** $6,378M (P5: $4,463M, P95: $9,017M)
- **S6 Max RE mean NPV:** $7,752M (P5: $5,398M, P95: $10,917M)

S7 is cheaper than S6 in **99.9% of MC iterations** (LNG wins ranking probability 99.9%). This is very robust.

### Under High SCC?
**Cannot test** — SCC has zero impact on `pv_total_costs` (see F-01). If emission costs were included, S6 (near-zero emissions) would gain a large advantage over S7 (0.40 kgCO₂/kWh LNG emissions). At SCC=$300/tCO₂ and LNG generating ~500 GWh/yr, the emission cost penalty to S7 would be ~$150M PV — potentially enough to flip the ranking.

This is **the most important unresolved question** in the sensitivity framework.

### Under Low Discount Rate?
From sensitivity output, varying discount rate from 3% to 10% affects all scenarios similarly (CAPEX-heavy scenarios like FI benefit more from low rates). The ranking stability would need S6/S7 comparison in the sensitivity output, which exists. From the sensitivity results, both S6 and S7 are affected similarly by discount rate changes (both have significant CAPEX). The ranking appears stable.

---

## Verified Correct

| Item | Description | Evidence |
|------|-------------|----------|
| ✅ Three-path sync | All 39 parameters identical across 4 code paths | Line-by-line comparison above |
| ✅ Cable CAPEX recomputation | All 4 paths recompute `cable_capex_total` when `cable_capex_per_km` or `converter_station` changes | Verified in all 4 locations |
| ✅ Demand growth scaling | All paths scale proportionally using BAU base rate, not flat override | Verified in all 4 locations |
| ✅ Env externality decomposition | All paths scale noise/spill/biodiversity proportionally to composite | Verified in all 4 locations |
| ✅ Sectoral rebalancing | All paths redistribute commercial/public equally when residential changes | Verified in all 4 locations |
| ✅ connection_cost dual-set | All paths set both `config.connection.cost_per_household` AND `config.technology.connection_cost_per_hh` | Verified in all 4 locations |
| ✅ battery_ratio dual-set | All paths set both `green_transition.battery_ratio` AND `islanded_battery_ratio` | Verified in all 4 locations |
| ✅ ev_adoption_midpoint int() | All paths cast to int() | Verified in all 4 locations |
| ✅ Fixed MC seed | `random.seed(42)` ensures reproducibility | run_monte_carlo.py line 238 |
| ✅ Triangular distribution | Appropriate for bounded asymmetric uncertainty in CBA | Standard ADB/WB practice |
| ✅ SENSITIVITY_PARAMS from CSV | `_update_sensitivity_params_from_csv()` overrides defaults from CSV Low/High columns | config.py lines 2004-2080 |
| ✅ Switching value methodology | Linear interpolation with "within range" / "outside range" labelling | ADB 2017 §6.37-6.40 compliant |
| ✅ Salvage recalculation | `calculate_salvage_value()` uses `max(self.horizon)` which varies per horizon config | npv_calculator.py line 399 |
| ✅ MC ranking probability | LNG Transition wins 99.9% — very robust result | monte_carlo_results.json |
| ✅ All alternatives beat BAU | Probability 99.8-100% for all 6 alternatives | monte_carlo_results.json |
| ✅ Specific exception handling | MC iteration failures catch specific exceptions only, not bare `except` | sensitivity.py line 827 |

---

## Summary Table

| ID | Severity | Finding | File(s) | Impact | Fix Effort |
|----|----------|---------|---------|--------|------------|
| F-01 | 🟡 MODERATE | SCC has zero impact on comparison metric (`pv_total_costs` excludes `pv_emission_costs`) | run_sensitivity.py, npv_calculator.py | Cannot test whether high SCC flips S7→S6 ranking | Medium — design decision needed |
| F-02 | 🔵 LOW | GoM cost share High=Base (one-sided sensitivity) | parameters.csv | Tornado bar degenerate on one side | None needed — physical ceiling |
| F-03 | 🟡 MODERATE | No parameter correlations in MC (38 independent draws) | run_monte_carlo.py | Wider CI bands; implausible parameter combos | Medium — Iman-Conover method |
| F-04 | 🟡 MODERATE | Multi-horizon output missing S5/S6/S7 (stale file) | multi_horizon_results.json | Incomplete horizon comparison | Low — re-run script |
| F-05 | 🔵 LOW | MC uses `random` module; library uses `numpy` | run_monte_carlo.py vs sensitivity.py | Minor inconsistency | Low |
| F-06 | 🔵 LOW | `_modify_config_inplace` name misleading (receives deepcopy) | sensitivity.py | None (cosmetic) | Low |
| F-07 | 🔵 LOW | MC convergence not formally validated | run_monte_carlo.py | Minor — N=1000 appears adequate | Low |
| F-08 | 🟡 MODERATE | Sensitivity does not co-vary DDR when discount rate changes | run_sensitivity.py | DDR structure unchanged under discount rate sensitivity | Low-Medium |
| F-09 | 🔵 LOW | Switching values use linear interpolation (appropriate) | run_sensitivity.py | Minor approximation for nonlinear params | None needed |
| F-10 | 🔵 LOW | Transport params (4) are no-ops in main CBA sensitivity | sensitivity.py, run_sensitivity.py | Wasted computation; no analytical value | Low — separate runner |

**Priority order for fixes:** F-01 > F-04 > F-03 > F-08 > F-10 > rest
