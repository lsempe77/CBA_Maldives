# Copilot Instructions — Maldives Energy CBA Project

## Architecture

A **Cost-Benefit Analysis model** comparing 7 energy-transition scenarios for the Maldives (2026–2056). Python 3.12, dataclass config, Quarto book report.

```
parameters.csv → config.py (load_parameters_from_csv → dataclasses) → get_config() → model code
                                                                           ↓
                                                               scenarios/*.py  →  cba/npv_calculator.py
                                                               costs.py            ↓
                                                               demand.py       outputs/*.json
                                                               emissions.py        ↓
                                                                              report/*.qmd (Quarto book)
```

**Scenarios:** S1 BAU (`status_quo.py`), S2 Full Integration (`one_grid.py`), S3 National Grid (`green_transition.py`), S4 Islanded Green (`islanded_green.py`), S5 Near-Shore Solar (`nearshore_solar.py`), S6 Maximum RE (`maximum_re.py`), S7 LNG (`lng_transition.py`).

## ⛔ #1 Rule: Zero Hardcoded Values

Every numeric parameter flows from `parameters.csv` → `config.py` → `get_config()`. No exceptions.

- **WRONG:** `solar_capex = 1500` or writing "6% discount rate" in `.qmd`
- **RIGHT:** `cfg = get_config(); cfg.technology.solar_pv_capex` / read from `outputs/*.json`
- **Only allowed literals:** math constants (π, 8760 hrs/yr, 1000 kg/tonne)
- **Why:** Sensitivity/Monte Carlo swap Low/High values via config — hardcoded values bypass this silently. We caught a bug (D23) where dataclass defaults overrode CSV values for months.

## Adding a New Parameter (3-step rule)

1. **Add row to `Maldives/model/parameters.csv`** — columns: `Category, Parameter, Value, Low, High, Unit, Source, Notes`. Source must be a real citation (use `perplexity_lookup.py` to find one).
2. **Wire in `config.py`** — add field to the appropriate dataclass (e.g., `TechnologyCosts`), then add an `if 'Param Name' in category_dict:` block inside `load_parameters_from_csv()`. ⚠️ CSV `Parameter` string must **exactly match** the key checked — typo = silently ignored, falls back to default.
3. **Access via `get_config()`** in consuming module — e.g., `cfg.technology.new_field`.
4. **If sensitivity-relevant:** also add to `SENSITIVITY_PARAMS` dict in `config.py`, add mapping tuple in `_define_parameters()` in `cba/sensitivity.py`, and add branch in `_modify_config()`.

## Scenario Interface

Every scenario extends `BaseScenario` (in `scenarios/base_scenario.py`) and must implement:

```python
def _init_demand_projector(self) -> DemandProjector
def calculate_generation_mix(self, year: int) -> GenerationMix
def calculate_annual_costs(self, year: int, gen_mix: GenerationMix) -> AnnualCosts
```

Call `scenario.run()` first (populates yearly data), then `scenario.calculate_benefits(baseline)` separately — benefits require a baseline comparison and are **not** computed automatically.

## Key Commands

```bash
# Run full model (all 7 scenarios + financing + MCA + distributional + transport)
cd Maldives/model && python run_cba.py

# Run analyses separately
python run_sensitivity.py      # Tornado diagrams (38 params × 7 scenarios)
python run_monte_carlo.py      # 1000-iteration Monte Carlo
python run_multi_horizon.py    # 20/30/50-year comparison

# Validate outputs (47 benchmark checks, exit code 0/1)
python -m model.sanity_checks

# Render Quarto report (must run model first — report reads outputs/*.json)
cd ../report && quarto render

# Research a parameter source
python perplexity_lookup.py "What is the LCOE of diesel in Pacific SIDS?"
python perplexity_lookup.py --id H1   # lookup specific IMPROVEMENT_PLAN item
```

## Critical Gotchas

- **No test suite exists.** Validation is via `sanity_checks.py` (47 post-hoc benchmark checks on output JSONs) and `if __name__ == "__main__":` blocks in scenario files.
- **`get_config()` re-reads CSV every call** — no caching. Each scenario constructor calls it if no config passed.
- **`SENSITIVITY_PARAMS` is a mutable global** in `config.py` — updated in-place by `load_parameters_from_csv()`. The sensitivity module imports it at module level.
- **Scenario dict keys ≠ filenames:** `"one_grid"` → S2 Full Integration, `"green_transition"` → S3 National Grid.
- **Financing is deliberately excluded from economic NPV** — `financing_analysis.py` is supplementary only (CBA methodology choice A-CR-01).
- **Report `_common.py` runs at import time** — loads all 11 JSON output files. Model must run before report renders.
- **Never use bare `except Exception`** — it silently swallows config loading errors (root cause of D23 bug).
- **`distributional_analysis.py` requires HIES 2019 microdata** in `data/hies2019/` — gracefully skips if missing.

## After Every Change

1. **Run the model:** `python Maldives/model/run_cba.py` to confirm nothing breaks.
2. **Update `Maldives/IMPROVEMENT_PLAN.md`** — mark items ✅, update Decision Log.
3. **Update `Maldives/AUDIT_REPORT.md`** — mark bugs fixed or add new findings.
4. **Check `Maldives/CBA_METHODOLOGY.md`** — update equations/traces if formulas changed.

## Reference Docs

| Doc | Purpose |
|-----|---------|
| `Maldives/IMPROVEMENT_PLAN.md` | Master roadmap — read before tasks, update after. Decision Log (D1–D73) has all resolved parameter choices. |
| `Maldives/CBA_METHODOLOGY.md` | 30+ LaTeX equations, ~185 parameter traces (`CSV → config field → script:line`), 17 structural concerns (all fixed). |
| `Maldives/AUDIT_REPORT.md` | Living bug/wiring audit — mark findings ✅ FIXED when resolved, add new issues when discovered. |

## Config Dataclass Structure

`Config` contains ~20 sub-configs: `demand: DemandConfig`, `technology: TechnologyCosts`, `fuel: FuelConfig`, `economics: EconomicsConfig`, `one_grid: OneGridConfig`, `nearshore: NearShoreConfig`, `lng: LNGConfig`, `dispatch: DispatchConfig`, `cable_outage: CableOutageConfig`, `financing: FinancingConfig`, `mca: MCAConfig`, `transport: TransportConfig`, etc. Browse `config.py` dataclass definitions to find the right home for a new parameter.

## Quarto Report Pattern

Each `.qmd` chapter starts with `from _common import *`, which provides:

- All 11 JSON outputs as dicts (e.g., `cba_results`, `sensitivity_results`)
- `params_df` — full `parameters.csv` as DataFrame
- `param("Growth Rate - BAU")` — case-insensitive parameter lookup
- `fmt` dict for number formatting helpers

Inline values use `` `{python} f"${value:,.0f}"` `` — never hand-typed numbers.

## What NOT to Do

- ⛔ Never hardcode numeric parameters anywhere except `parameters.csv` + `config.py` defaults
- ⛔ Never add params to `config.py` without a corresponding `parameters.csv` row
- ⛔ Never use bare `except Exception` — catch specific exceptions only
- ⛔ Never create `config.yaml` — this project uses CSV, not YAML
- ⛔ Never guess parameter values — run `perplexity_lookup.py` first, then flag 🔍 HUMAN LOOKUP if unresolved
- ⛔ Never rewrite archived OnSSET code in `_archive/` — it's read-only reference
