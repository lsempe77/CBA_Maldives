# Maldives Energy Transition — Cost-Benefit Analysis

> **A 30-year cost-benefit analysis of four electricity pathways for the Republic of Maldives (2026-2056).**
> Prepared by the International Initiative for Impact Evaluation (3ie).

---

## Quick Start

```bash
# 1. Activate the virtual environment
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# 2. Run the CBA model (all 4 scenarios, 30-year horizon)
cd Maldives/model
python run_cba.py

# 3. Run multi-horizon comparison (20 / 30 / 50 years)
python run_multi_horizon.py

# 4. Render the policy report (HTML with interactive map)
cd ../report
quarto render REPORT_Maldives_Energy_CBA.qmd --to html
```

---

## Project Structure

```
CBA_Maldives/
│
├── .venv/                          # Python 3.12 virtual environment
├── LICENSE
│
└── Maldives/                       # ← All project files live here
    │
    ├── data/                       # INPUT DATA
    │   ├── Maldives_GIS_Complete.csv       # Island-level data (coordinates, pop, solar)
    │   ├── geotiff/                        # Global Solar Atlas raster data
    │   │   ├── Maldives_GHI_*              # Global Horizontal Irradiance
    │   │   ├── Maldives_DNI_*              # Direct Normal Irradiance
    │   │   ├── Maldives_PVOUT_*            # Photovoltaic Output Potential
    │   │   └── Maldives_TEMP_*             # Temperature
    │   └── supplementary/                  # Hourly time-series data
    │       ├── GHI_hourly.csv
    │       └── Temperature_hourly.csv
    │
    ├── model/                      # CBA MODEL (Python)
    │   ├── config.py               # All model parameters & dataclasses
    │   ├── parameters.csv          # Editable CSV with all input parameters
    │   ├── demand.py               # Electricity demand projections
    │   ├── costs.py                # Cost calculations (CAPEX, OPEX, fuel)
    │   ├── emissions.py            # CO₂ emissions calculations
    │   ├── __init__.py
    │   │
    │   ├── scenarios/              # Scenario definitions
    │   │   ├── status_quo.py       # S1: BAU (diesel)
    │   │   ├── one_grid.py         # S2: Full Integration (India + grid + RE)
    │   │   ├── green_transition.py # S3: National Grid (grid + RE, no India)
    │   │   ├── islanded_green.py   # S4: Islanded Green (per-island solar+battery)
    │   │   └── __init__.py
    │   │
    │   ├── cba/                    # CBA engine
    │   │   ├── npv_calculator.py   # NPV, BCR, LCOE calculations
    │   │   ├── sensitivity.py      # One-way sensitivity analysis
    │   │   └── __init__.py
    │   │
    │   ├── run_cba.py              # ★ Main script: run all 4 scenarios
    │   ├── run_multi_horizon.py    # ★ Compare 20/30/50-year horizons
    │   ├── run_sensitivity.py      # ★ One-way sensitivity analysis
    │   └── run_monte_carlo.py      # ★ Monte Carlo uncertainty simulation
    │
    ├── report/                     # QUARTO REPORT
    │   ├── REPORT_Maldives_Energy_CBA.qmd  # ★ Source document (Quarto)
    │   ├── REPORT_Maldives_Energy_CBA.html  # Rendered: interactive map
    │   ├── REPORT_Maldives_Energy_CBA.pdf   # Rendered: static map
    │   ├── REPORT_Maldives_Energy_CBA.docx  # Rendered: static map
    │   └── references.bib                   # Bibliography
    │
    └── outputs/                    # MODEL OUTPUTS (auto-generated)
        ├── cba_results.json              # Main CBA results
        ├── multi_horizon_results.json    # 20/30/50-year comparison
        ├── sensitivity_results.json      # Sensitivity analysis
        ├── monte_carlo_results.json      # Monte Carlo simulation
        ├── scenario_summaries.json       # Scenario summary table
        └── *.png, *.html                 # Charts and maps
```

---

## Key Scripts — What Each One Does

### Running the Model

| Script | Purpose | Command |
|--------|---------|---------|
| `model/run_cba.py` | Runs all 4 scenarios for one time horizon. Outputs NPV, LCOE, emissions, BCR. | `python run_cba.py` |
| `model/run_multi_horizon.py` | Compares all 4 scenarios across 20, 30, and 50-year time horizons. | `python run_multi_horizon.py` |
| `model/run_sensitivity.py` | One-way sensitivity analysis on all key parameters. | `python run_sensitivity.py` |
| `model/run_monte_carlo.py` | 1,000-iteration Monte Carlo simulation for uncertainty analysis. | `python run_monte_carlo.py` |

### Model Components

| File | What It Contains |
|------|------------------|
| `model/config.py` | All model parameters as Python dataclasses. Loads from `parameters.csv`. |
| `model/parameters.csv` | **The single input file** — edit this to change any model assumption. |
| `model/demand.py` | Demand projection logic (base demand × growth rate). |
| `model/costs.py` | CAPEX, OPEX, fuel cost calculations with technology learning curves. |
| `model/emissions.py` | CO₂ emissions from diesel generation. |

### Scenarios

| File | Scenario |
|------|----------|
| `model/scenarios/status_quo.py` | **S1 — BAU**: Continued diesel, ~7% RE. |
| `model/scenarios/one_grid.py` | **S2 — Full Integration**: India HVDC cable + inter-island grid + RE. |
| `model/scenarios/green_transition.py` | **S3 — National Grid**: Inter-island grid + RE (no India cable). |
| `model/scenarios/islanded_green.py` | **S4 — Islanded Green**: Per-island solar + battery (no cables). |

### Report

| File | Format | Notes |
|------|--------|-------|
| `report/REPORT_Maldives_Energy_CBA.qmd` | Quarto source | Edit this to change the report. |
| `report/REPORT_Maldives_Energy_CBA.html` | HTML | **Best version**: interactive Leaflet map. |
| `report/REPORT_Maldives_Energy_CBA.pdf` | PDF | Static matplotlib map (for printing). |
| `report/REPORT_Maldives_Energy_CBA.docx` | Word | Static matplotlib map (for editing/comments). |

> **Dynamic report:** The `.qmd` report reads all figures and narrative values
> from the JSON files in `outputs/`. Change a parameter in `parameters.csv`,
> re-run the model, and the report updates automatically when rendered.

---

## The Four Scenarios

| # | Scenario | India Cable | Inter-Island Grid | RE Target | Result |
|---|----------|-------------|--------------------|-----------:|--------|
| S1 | BAU (Diesel) | ✗ | ✗ | 7% | Most expensive ($10.5B) |
| S2 | Full Integration | ✓ | ✓ | 30% | **Least cost ($4.9B)** |
| S3 | National Grid | ✗ | ✓ | 70% | Second best ($5.5B) |
| S4 | Islanded Green | ✗ | ✗ | 65% | Third best ($5.7B) |

> **Note:** Results are PV total costs in billions USD at 6% discount rate.
> RE targets reflect final-year shares as modeled. Full Integration's 30% RE share
> refers to domestic solar; the remaining supply comes from India grid imports
> (which are largely non-diesel but not classified as renewable in our model).

---

## Key Parameters (from `model/parameters.csv`)

| Parameter | Value | Source |
|-----------|-------|--------|
| Base Year | 2026 | — |
| Discount Rate | 6% | World Bank SIDS guidance |
| Solar PV CAPEX | $750/kW | IRENA RPGC 2024 |
| Battery CAPEX | $120/kWh | BNEF Dec 2025 |
| Diesel Price | $0.85/L | Platts Dec 2025 |
| India Import Price | $0.06/kWh | India Energy Exchange |
| Social Cost of Carbon | $190/tCO₂ | US EPA 2023 |
| Base Demand | 1,100 GWh/yr | IRENA/STELCO |
| Demand Growth | 5%/yr | UNDP/STELCO |
| Cable Cost | $3M/km | Industry estimates |

To change any parameter, edit `model/parameters.csv` — the model reads from it automatically.

---

## Data Sources

| Dataset | File | Source |
|---------|------|--------|
| Island GIS data | `data/Maldives_GIS_Complete.csv` | Global Solar Atlas + STELCO |
| Solar irradiance rasters | `data/geotiff/` | [Global Solar Atlas](https://globalsolaratlas.info) |
| Hourly GHI | `data/supplementary/GHI_hourly.csv` | SolarGIS / HelioClim |
| Hourly temperature | `data/supplementary/Temperature_hourly.csv` | SolarGIS / ERA5 |

---

## Dependencies

```
Python 3.12
numpy
pandas
matplotlib
folium          # Interactive Leaflet maps (HTML report only)
branca          # Colormap support for folium
quarto          # Report rendering (install separately)
```

Install with: `pip install numpy pandas matplotlib folium branca`


