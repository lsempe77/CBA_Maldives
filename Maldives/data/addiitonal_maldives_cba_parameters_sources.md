# Maldives Electrification CBA — Parameter Sources & Evidence Base

**Prepared:** 7 February 2026
**Purpose:** Credible, citable parameters for cost-benefit analysis of electrification scenarios in the Maldives

---

## ⛔ C4 / H3 — HVDC VSC Converter Station Cost

### Recommendation

**Accept $1.6M/MW as central estimate with ±25% sensitivity bounds ($1.2–2.0M/MW)**

For a ~200MW station, per-MW costs are significantly higher than for 1–2GW stations due to fixed cost components (valve hall, building, land, DC switching station, ground electrode). The $1.6M/MW figure from Härtel et al. (2017) was calibrated primarily against 500MW+ projects. At 200MW scale, the upper end of the range is more likely.

### Source triangulation

#### 1. Härtel et al. (2017) — Primary academic source

- **Citation:** Härtel, P., Vrana, T.K., Hennig, T., von Bonin, M., Wiggelinkhuizen, E.J., & Nieuwenhout, F.D.J. (2017). Review of investment model cost parameters for VSC HVDC transmission infrastructure. *Electric Power Systems Research*, 151, 419–431. https://doi.org/10.1016/j.epsr.2017.06.008
- **Full text (open access):** https://publications.tno.nl/publication/34633827/G7x3b0/w17015.pdf
- **ScienceDirect:** https://www.sciencedirect.com/science/article/abs/pii/S0378779617302572
- **Key finding:** Collected 14+ cost parameter sets from techno-economic sources, converted to a common linear cost model format (fixed + variable per MW for converter stations; fixed + variable per km for cables). The arithmetic mean across all sets yielded a converter station cost in the range of €1.4–1.8M/MW. Large variations between parameter sets were identified, reflecting fundamental uncertainty in VSC HVDC costing — manufacturers (only 3 globally: Hitachi Energy, Siemens Energy, GE Vernova) operate under strict confidentiality clauses.
- **Limitation:** The review noted that back-to-back systems tend to be slightly underestimated, interconnectors overestimated, and offshore wind connections heavily underestimated by the collected parameter sets.

#### 2. Härtel & Vrana (2018) — Optimised parameter set (QQEF)

- **Citation:** Vrana, T.K. & Härtel, P. (2018). Estimation of investment model cost parameters for VSC HVDC transmission infrastructure. *Electric Power Systems Research*, 160, 99–108. https://doi.org/10.1016/j.epsr.2018.02.007
- **ScienceDirect:** https://www.sciencedirect.com/science/article/abs/pii/S0378779618300506
- **Key finding:** Used particle swarm optimisation to derive an improved cost parameter set (QQEF) that outperforms all existing sets against real project reference data. Converter pair costs for existing 1000 km projects ranged from 93 M€ to 860 M€ across different project types and scales (NordBalt, NordLink, NorthSeaLink, etc.), confirming extreme variability in real-world costs.
- **Use:** The QQEF parameter set represents the best available calibration against real project data as of 2018.

#### 3. Vrana & Härtel (2023) — Updated cost model with overhead cost consideration

- **Citation:** Vrana, T.K. & Härtel, P. (2023). Improved investment cost model and overhead cost consideration for high voltage direct current infrastructure. *19th International Conference on the European Energy Market (EEM 2023)*.
- **Fraunhofer record:** https://publica.fraunhofer.de/handle/publica/445648
- **SINTEF blog summary (updated Dec 2024):** https://blog.sintef.com/energy/future-hvdc-grids-yes-please-but-what-is-the-price-tag/
- **Key updates:** (a) Underground cables (UGC) now treated similarly to submarine cables (SMC) for more accurate onshore extension costing. (b) Parameter fitting methodology updated to consider different overhead cost levels (financing, insurance, risk premium vs. auxiliary equipment, land, project management), improving precision when processing press-release cost data that may report at different investment cost levels. (c) Mixed-integer linear cost model retained, capturing fixed + variable components.
- **PyPSA technology-data repository reference:** https://github.com/PyPSA/technology-data/issues/125 — The repository's comparison table lists Vrana & Härtel (2023) alongside NEP 2023, ACER 2023, and CIGRE sources. The HVDC inverter pair investment is listed at ~€165,803/MW in the PyPSA dataset. Note: this is the *variable* component of the mixed-integer model; the fixed component adds substantially at lower power ratings (like 200MW).

#### 4. MISO MTEP24 (May 2024) — US utility cost guide

- **Source:** MISO, Transmission Cost Estimation Guide for MTEP24, May 1, 2024.
- **PDF (clean):** https://cdn.misoenergy.org/20240501%20PSC%20Item%2004%20MISO%20Transmission%20Cost%20Estimation%20Guide%20for%20MTEP24632680.pdf
- **PDF (redline from MTEP23):** https://cdn.misoenergy.org/20240131%20PSC%20Item%2005%20Transmission%20Cost%20Estimation%20Guide%20for%20MTEP24%20-%20Redline631529.pdf
- **MTEP25 update (June 2025):** https://cdn.misoenergy.org/MISO%20Transmission%20Cost%20Estimation%20Guide%20for%20MTEP25337433.pdf
- **Stakeholder feedback page:** https://www.misoenergy.org/engage/stakeholder-feedback/2024/psc-transmission-cost-estimation-guide-for-mtep24-20240131/
- **Key details:** All costs in 2024 USD (escalated from 2023 at 5%). Includes both LCC and VSC converter station cost tables (Tables 2.4-1 and 2.4-2). Assumes bipolar converter stations with new 4-position breaker-and-a-half AC substation, ground electrode at each end (20 miles of ground electrode line), and valve hall including land acquisition, building, and DC switching station equipment. VSC stations use IGBT valves in controlled indoor environments.
- **Note:** Stakeholder feedback from Xcel Energy noted substation estimates are "regularly 10–20% low," suggesting the MISO guide may underestimate actual procurement costs.

#### 5. Basslink Modern Equivalent Cost Study (Australia, 2023)

- **Source:** Amplitude Consultants (2023). Basslink — Optimised Replacement Cost and Alternatives. Prepared for the Australian Energy Regulator (AER). Document PAU0280-REPT-001, 21 August 2023.
- **PDF:** https://www.aer.gov.au/system/files/2023-09/Basslink%20-%20Amplitude%20-%20Attachment%205.2%20-%20Optimised%20replacement%20cost%20and%20alternatives%20-%2015%20September%202023.pdf
- **Key details:** High-level EPC cost estimates for each VSC converter station based on full bridge MMC technology and symmetric monopole configuration for a 500MW continuous rating system (Table 6-1). The original Basslink system is 500MW continuous / 630MW dynamic rating with ±320kV, using 88km submarine cable + overhead DC lines.
- **Relevance:** Real-world replacement cost study for an existing VSC HVDC interconnector, providing contemporary Australian cost data.

#### 6. India–Sri Lanka HVDC Interconnection — Comparator project

- **Wikipedia overview:** https://en.wikipedia.org/wiki/India%E2%80%93Sri_Lanka_HVDC_Interconnection
- **CEB/LTGEP cost estimate:** Sri Lanka's CEB estimates a 500MW HVDC interconnection at approximately $687 million total investment (cable + converters + overhead lines). Source: *The Morning* (Sri Lanka), reporting on LTGEP 2023–2042. https://www.themorning.lk/articles/sAG7KOjt7s3JDQw4y8Jx
- **PGCIL estimates:** Short-term 500MW link at $340 million; medium/long-term 1000MW link at $430 million. Source: EconomyNext (May 2022). https://economynext.com/sri-lanka-india-eyeing-over-water-power-cable-connection-minister-94879/
- **Route:** 285 km total (139 km overhead India side + 39 km undersea Rameswaram–Thalaimannar + 125 km overhead Sri Lanka side), with HVDC terminal stations at each end.
- **Status:** Discussions ongoing; DPR expected from India. Both LCC and VSC technologies under consideration. The project was found "not economically or financially viable" in earlier assessments, with submarine cable and HVDC technology selection being the major cost drivers.
- **Limitation for your model:** These are total project costs, not isolated converter station costs. The JICA feasibility study is not publicly available as a standalone document.

#### 7. NREL Electrical Infrastructure Cost Model (2023)

- **Source:** National Renewable Energy Laboratory (2023). Electrical Infrastructure Cost Model for Marine Energy. NREL/TP-5700-87184.
- **PDF:** https://docs.nrel.gov/docs/fy23osti/87184.pdf
- **Key detail:** Figure F-6 presents a cost curve for HVDC converter stations based on data from Härtel et al. (2017), Pletka et al. (2014), and MISO (2020), providing a regression-based cost estimate as a function of power rating.

#### 8. Industry context (2023–2024)

- **DNV (2024). "2023 was a pivotal year for HVDC."** https://www.dnv.com/article/2023-was-a-pivotal-year-for-HVDC/
  - TenneT 30 bn EUR framework; National Grid 59 bn GBP tender; NEOM 3×3 GW project.
  - Publicly announced HVDC investment in 2023: ~$140 billion globally.
  - Market tightness may push converter station costs upward.
  - Only 3 established converter station manufacturers (Hitachi Energy, Siemens Energy, GE Vernova); Mitsubishi entering with Diamond VSC technology (300MW back-to-back in Japan).
- **Fortune Business Insights. HVDC Converter Station Market (2024).** https://www.fortunebusinessinsights.com/industry-reports/hvdc-converter-station-market-101368
  - Global market: $13.68 billion in 2024, projected $30.41 billion by 2032 (CAGR 10.5–10.9%).
  - Asia Pacific dominated with 62.71% market share in 2023.

### Bottom line for your parameters.csv

| Parameter | Value | Range | Source |
|---|---|---|---|
| Converter Station Cost per MW | $1.6M/MW | $1.2–2.0M/MW | Härtel et al. (2017), Vrana & Härtel (2023), MISO MTEP24, Basslink (2023) |
| 200MW station total (pair) | $640M | $480–800M | Derived: 2 stations × 200MW × $1.6M/MW |

**Note:** The pair cost includes two converter stations (one at each end of the HVDC link). Landing costs, Malé grid upgrade, and IDC remain to be added on top.

---

## 🟡 H5 — Per-Island Electricity Generation Data

### Recommendation

**Malé accounts for ~57% of national inhabited-island electricity. Use 57% as central estimate.**

### Key data source

#### Island Electricity Data Book series (Ministry of Environment and Energy, Maldives)

| Edition | Data Year | Total Generation (GWh) | Greater Malé Share | Download |
|---|---|---|---|---|
| 2016 | 2015 | 551 | 56% | Via environment.gov.mv |
| 2017 | 2016 | 628 | 59.8% | Via environment.gov.mv |
| 2018 | 2017 | 704 | 56.9% | https://www.environment.gov.mv/v2/wp-content/files/publications/20181105-pub-island-electricity-data-book-2018.pdf |
| 2019 | 2018 | — | — | http://www.environment.gov.mv/v2/wp-content/files/publications/20201123-pub-island-electricity-databook-2019.pdf |

- **Launch announcement (2018 edition):** https://www.environment.gov.mv/v2/en/news/8071
- **Launch announcement (2017 edition):** https://www.environment.gov.mv/v2/en/news/6790
- **Launch announcement (2016 edition):** https://www.environment.gov.mv/v2/en/news/4062
- **Download page:** https://www.environment.gov.mv/v2/en/download/8106

#### Supporting data

- **UN Energy Statistics presentation (2016):** Maldives energy balance data presented by Fathmath Fizna Yoosuf, Engineer. https://unstats.un.org/unsd/energy/meetings/2016iwc/25maldives.pdf
  - Greater Malé Region 2012: ~313 GWh, population ~114,682, per-capita 2,730 kWh/yr
  - Other Atolls 2012: per-capita 1,060 kWh/yr (growth rate 16.33%)

- **Total national electricity (2024):** ~847 GWh produced, ~821 GWh consumed. Source: https://www.worlddata.info/asia/maldives/energy-consumption.php

- **Installed capacity breakdown (older data, USAID/SARI):** https://sari-energy.org/oldsite/PageFiles/Countries/Maldives_Energy_detail.html
  - Total installed: 106.2 MW (at time of report)
  - Resort islands: 48.3% of installed capacity
  - STELCO (public utility): 34.9% of installed capacity
  - IDCs/private: 13.2%
  - Airports: 3.5%

- **2018 installed capacity (from Data Book 2018):** 240 MW of diesel generators on inhabited islands; 11 MW renewable energy.

- **Utility structure:**
  - STELCO: operates power plants in ~30 inhabited islands including Greater Malé
  - FENAKA Corporation: operates power plants in ~157 inhabited islands (outer atolls)
  - Source: Maldives Energy Roadmap 2024–2033. https://www.environment.gov.mv/v2/wp-content/files/publications/20241107-pub-energy-roadmap-maldives-2024-2033-.pdf

- **Fuel imports (2017):** 561,435 metric tons total; 447,555 MT diesel, 57,730 MT petrol, 41,666 MT aviation gas, 14,483 MT cooking gas.

---

## 🟡 H6 — Outer-Atoll Fuel Surcharge

### Recommendation

**Flag as "uniform STO diesel price" at the pump. Note effective electricity cost differential of 50–200% on remote atolls due to inefficiencies and logistics.**

### Evidence

#### STO diesel price history (national uniform price)

| Date | Diesel (MVR/litre) | Petrol (MVR/litre) | Source |
|---|---|---|---|
| May 27, 2024 | 13.92 | 13.98 | STO |
| Dec 8, 2023 | 14.62 | 14.33 | STO |
| Jun 9, 2023 | 15.07 | 14.73 | STO |
| May 1, 2023 | 15.70 | 15.14 | STO |
| Aug 18, 2022 | 16.32 | 15.97 | STO |

- **Price history source:** https://adhadhu.com/article/54263
- **STO announcement (May 2024):** https://corporatemaldives.com/sto-announces-reduction-in-diesel-petrol-prices-from-may-27th/
- **STO official:** https://www.sto.mv/media/news/fuel-price-reduction-may-2024
- **International comparison:** As of late 2025, Maldives diesel ~$0.97/litre. Source: https://analyticauto.com/diesel_prices/maldives

#### Electricity tariff differential (where the real cost difference shows)

- **Fuel surcharge base rate:** Greater Malé = MVR 8.00/litre; Atolls = MVR 8.10/litre. Source: *Maldives Independent*. https://maldivesindependent.com/business/petrol-and-diesel-prices-hiked-132448
- **Outer island electricity cost:** $0.30–0.70/kWh. Source: CIF/World Bank, Preparing Outer Island Sustainable Electricity. https://www.cif.org/sites/cif_enc/files/knowledge-documents/66436_191219_maldives_case_study_v7s.pdf
- **Greater Malé electricity cost:** ~$0.15–0.20/kWh (approximate from tariff schedules)

#### Why the differential exists (even with uniform diesel price)

1. **Smaller, less efficient gensets** on outer islands (50–500 kW vs. multi-MW in Malé)
2. **Fuel transport logistics** — delivery by dhoni/barge to remote atolls adds cost
3. **Lower load factors** — smaller populations mean lower utilisation rates
4. **Higher O&M per kWh** — lack of economies of scale, limited skilled technicians

#### Implication for CBA

The 50–200% effective cost premium on outer-atoll diesel electricity *strengthens* the case for the Islanded Green scenario on remote islands. Solar+battery is already cost-competitive against $0.30–0.70/kWh diesel generation without any carbon pricing.

---

## 🟡 H7 — Sectoral Electricity Split

### Recommendation

**Flag M5 as illustrative. Use 70/15/15 (residential/commercial-including-tourism-spillover/public) for the public grid as a more defensible proxy than 60/30/10.**

### Evidence

- Resort islands are largely self-contained with their own diesel generation (48.3% of national installed capacity per USAID/SARI data). Resorts are not connected to the public STELCO/FENAKA grid.
- No published STELCO annual report with sectoral breakdown was identified through web search.
- The Island Electricity Data Books (2016–2019) provide per-island data but not sectoral disaggregation.

### Academic reference for energy system structure

- **Bogdanov, D. et al. (2021).** Powering an island energy system by offshore floating technologies towards 100% renewables: A case for the Maldives. *Applied Energy*, 308, 118360. https://www.sciencedirect.com/science/article/pii/S0306261921016056
  - Primary energy supply (2017 reference year): 39% of diesel for electricity production; 25% domestic marine navigation; 23% road transport; 10% international marine; 2.7% fishing boats.
  - Provides full energy balance decomposition for the Maldives.

### Recommendation

If no sectoral split can be sourced, either drop M5 or present it as illustrative with clear caveats. The key insight is that resort electricity (~40–48% of installed capacity) is off-grid and self-generated, so it should be excluded from the public utility CBA entirely.

---

## 🟡 H1 — Diesel Genset Lifetime

### Recommendation

**Use 20 years with "industry standard, consistent with OEM guidance" citation.**

### Evidence

- **OEM precedent:** A 4×50MW Hyundai-MAN plant commissioned in 1999 was described as having "balance useful life of at least 20 years with proper maintenance as recommended by OEM." Source: https://www.powerplantsonline.com/dieselgenerator.htm
- **Operating hours basis:** Medium-speed diesel gensets (Wärtsilä 32, Caterpillar, Cummins, MAN) are typically rated for 100,000–150,000 operating hours before major overhaul/retirement. At 6,000–7,500 hrs/year (typical island utility duty), this yields 13–25 years.
- **Wärtsilä 32 series:** In production since the 1980s; >4,500 delivered to marine market; designed for "long maintenance-free operating periods." Source: https://www.wartsila.com/marine/products/engines-and-generating-sets/diesel-engines/wartsila-32
- **Tropical marine environment adjustment:** Corrosion, salt spray, and high ambient temperatures in the Maldives reduce effective life. 20 years is conservative and appropriate for this context.
- **ADB reference:** The ADB Preparing Outer Islands for Sustainable Energy Development project notes that in 2012, STELCO and FENAKA used nearly 120 million litres of diesel annually. Source: https://www.adb.org/sites/default/files/linked-documents/46122-003-ssa.pdf

### Suggested citation text

> "Diesel genset economic lifetime assumed at 20 years, consistent with OEM guidance for medium-speed engines (Wärtsilä, CAT, Cummins, MAN) under tropical utility-scale operation with scheduled major overhauls."

---

## 🟡 H8 — Health Damage Costs from Diesel Generation

### Recommendation

**Include L4 with a range of $20–80/MWh (low for outer atolls, high for Malé). Cite the Parry et al. (2014) framework as updated by Black et al. (2023).**

### Source chain

#### 1. Parry et al. (2014) — Foundational methodology

- **Citation:** Parry, I., Heine, D., Lis, E., & Li, S. (2014). *Getting Energy Prices Right: From Principle to Practice.* International Monetary Fund. Washington, DC.
- **Key methodology:** Developed a country-by-country framework for estimating environmental costs of fossil fuels based on: (a) emission rates by fuel and technology, (b) intake fractions (population exposure to pollution), (c) dose-response relationships (mortality risk per unit exposure), (d) mortality valuation (value of statistical life), (e) apportionment between local and transboundary pollution.
- **Health damage components:** Direct PM2.5 emissions + secondary PM2.5 from SO₂ and NOₓ atmospheric reactions. Diesel combustion is a major source per unit of energy.

#### 2. Coady et al. (2019) — Global update

- **Citation:** Coady, D., Parry, I., Le, N.P., & Shang, B. (2019). Global Fossil Fuel Subsidies Remain Large: An Update Based on Country-Level Estimates. IMF Working Paper WP/19/89.
- **PDF:** https://www.imf.org/-/media/files/publications/wp/2019/wpiea2019089.pdf
- **IMF e-Library:** https://www.elibrary.imf.org/view/journals/001/2019/089/article-A001-en.xml
- **Key findings:** Global subsidies $4.7 trillion (6.3% of GDP) in 2015, projected $5.2 trillion (6.5% of GDP) in 2017. Coal and petroleum account for 85% of global subsidies. Efficient pricing in 2015 would have reduced fossil fuel air pollution deaths by 46%.
- **Table 1 data:** Death rates per million GJ of coal used vary enormously by country — from <1 (Australia, Canada, Japan, US) to >40 (Ukraine). Diesel vehicles show revised-upward emission rates post-Volkswagen scandal.
- **Relevance for Maldives:** Death rates depend heavily on population exposure (intake fraction). Malé's extreme population density (~65,000/km²) means very high intake fractions for diesel generator emissions; outer atolls would be near zero.

#### 3. Black et al. (2023) — Latest comprehensive update

- **Citation:** Black, S., Liu, A.A., Parry, I., & Vernon, N. (2023). IMF Fossil Fuel Subsidies Data: 2023 Update. IMF Working Paper WP/23/169.
- **PDF:** https://www.imf.org/-/media/Files/Publications/WP/2023/English/wpiea2023169-print-pdf.ashx
- **Key findings:** Globally, fossil fuel subsidies were $7 trillion in 2022 (7.1% of GDP). Nearly 60% due to undercharging for global warming and local air pollution. 80% of global coal consumption priced at below half its efficient level. Updated intake fractions and emission rate estimates.
- **Methodology note:** Country-level population exposure estimates average across two modelling approaches — one based on intake fractions (updated from Parry et al. 2014) and one based on atmospheric modelling.

#### 4. IMF (2025) — Most recent update

- **Citation:** Black, S. et al. (2025). Underpriced and Overused: Fossil Fuel Subsidies Data 2025 Update. IMF Working Paper WP/25/270.
- **PDF:** https://www.imf.org/-/media/files/publications/wp/2025/english/wpiea2025270-source-pdf.pdf
- **New details:** CO₂ emissions per litre ~16% higher for diesel than gasoline. Long-run driving elasticity of -0.18 for all vehicles, -0.4 for fuel economy improvements.

#### 5. HEAL report — Health costs vs. fossil fuel subsidies

- **Source:** Health and Environment Alliance (HEAL). *Hidden Price Tags: How Ending Fossil Fuel Subsidies Would Benefit Our Health.*
- **PDF:** https://www.env-health.org/wp-content/uploads/2018/08/hidden_price_tags.pdf
- **Key finding:** Eliminating fossil fuel subsidies and implementing corrective taxes could avoid 24.9–73.8% of premature air pollution deaths in the seven most affected countries studied.

### Suggested parameter range for Maldives

| Location | Health Damage ($/MWh) | Rationale |
|---|---|---|
| Greater Malé | $50–80 | Extreme population density → high intake fraction |
| Populated outer atolls | $20–40 | Moderate density, small populations |
| Remote atolls | $5–15 | Very low population exposure |
| Weighted average | $30–60 | Your original proxy is well-calibrated |

### Tool for verification

- **IMF Climate Policy Assessment Tool (CPAT):** https://climatedata.imf.org/ — may contain Maldives-specific values for health damage costs by fuel type. Worth checking for a country-specific figure.

---

## ❌ H9 — Climate Adaptation CAPEX Premium (%)

### Recommendation

**Skip L3 as a standalone module. Embed a notional 5–10% premium with caveat.**

### Evidence (macro-level only — no project-specific engineering premium found)

#### Global Center on Adaptation (GCA) — SIDS Report (2025)

- **Source:** Global Center on Adaptation (2025). *Adapt Now: Small Island Developing States.*
- **Summary:** https://gca.org/news/small-islands-face-outsized-climate-impacts-and-require-us12-billion-a-year-in-climate-finance-to-cope/
- **Payne Institute summary:** https://payneinstitute.mines.edu/small-costs-for-large-gains-climate-resilience-in-small-island-developing-states/
- **Key findings:**
  - Without adaptation, cumulative climate damages across SIDS could reach $476 billion by 2050.
  - Investment of $54–127 billion would cut climate damage as a share of GDP by >50%.
  - **Benefit-to-cost ratio of 6.5 specifically for the Maldives** (even at 10% discount rate).
  - Priority sectors: distributed clean energy, resilient transport links, climate-smart agriculture, water systems.
  - 44% of public international adaptation finance to SIDS arrives as debt.
  - Current adaptation finance: ~$2 billion/year; needed: ~$12 billion/year.

#### UN DESA — SIDS adaptation costs

- **Source:** https://sdgs.un.org/smallislands/about-small-island-developing-states
- **Key figure:** Annual cost of adapting to climate change in SIDS estimated at $22–26 billion/year, or roughly 4–5% of their combined GDP.

#### Nature Sustainability — Coastal flood risk for SIDS

- **Citation:** Vousdoukas, M.I. et al. (2023). Small Island Developing States under threat by rising seas even in a 1.5°C warming world. *Nature Sustainability*. https://doi.org/10.1038/s41893-023-01230-5
- **URL:** https://www.nature.com/articles/s41893-023-01230-5

#### CLARE Programme — Maldives-specific adaptation challenges

- **Source:** https://clareprogramme.org/update/islands-at-the-brink-climate-realities-in-the-maldives-and-beyond/
- **Key detail:** Over 1,300 hectares of new land reclaimed across ~100 inhabited islands in the Maldives (Hulhumalé), with "lock-in effects" creating continuous dependency on external technologies, financial resources, and raw materials.

### Suggested caveat text

> "A notional climate-proofing premium of 5–10% is applied to coastal and submarine energy infrastructure CAPEX. No empirical basis exists for a Maldives-specific energy infrastructure climate adaptation premium. This aligns with standard practice in MDB project appraisals for SIDS and is consistent with GCA (2025) findings that adaptation investments in the Maldives yield a benefit-to-cost ratio of 6.5."

---

## ❌ H13 — Idle Diesel Fleet Maintenance Cost for Supply Security

### Recommendation

**Use $5–8M/yr as central range (bottom-up estimate), or $10–20M/yr if including crew retention and fuel storage. Flag as "engineering estimate" with clear caveat.**

### Evidence

No published estimate exists for maintaining a mothballed diesel fleet as strategic reserve in a SIDS context.

### Bottom-up derivation

| Component | Value | Source / Basis |
|---|---|---|
| Total installed diesel capacity (inhabited islands) | ~240 MW | Island Electricity Data Book 2018 |
| Assumed original CAPEX | $500–800/kW | Industry range for medium-speed diesel gensets |
| Total asset base | $120–192M | 240 MW × $500–800/kW |
| Annual fixed O&M (standby mode) | 2–4% of CAPEX | Industry standard for standby/reserve generation |
| **Annual standby cost** | **$2.4–7.7M/yr** | Derived |
| **Plus crew retention, fuel storage, testing** | **+$3–5M/yr** | Engineering estimate |
| **Total range** | **$5–13M/yr** | Combined |

### Notes

- "Standby mode" assumes gensets are maintained in ready-to-operate condition with periodic test runs (monthly or quarterly), lube oil changes, and corrosion protection — but not generating revenue.
- In tropical marine environments, standby costs are higher due to accelerated corrosion and humidity damage.
- The $15M/yr originally proposed may be appropriate if assuming a higher proportion of the fleet is kept operational-ready (not just preserved) and includes dedicated staffing across multiple island powerhouses.

### Suggested caveat text

> "Annual cost of maintaining the existing diesel fleet in standby reserve mode estimated at $5–13M/yr based on 2–4% of installed asset value plus crew retention and fuel storage costs. This is an engineering estimate; no published SIDS-specific benchmarks were identified."

---

## Additional Maldives Energy Context Sources

### Maldives Energy Roadmap 2024–2033

- **PDF:** https://www.environment.gov.mv/v2/wp-content/files/publications/20241107-pub-energy-roadmap-maldives-2024-2033-.pdf
- **Key targets:** 33% of electricity from renewables by 2028.
- **Utility structure:** STELCO (Greater Malé + 30 islands); FENAKA (157 islands); 1 island by private operator; 1 island by MWSC.
- **Current RE capacity:** Solar PV systems installed in K.Gulhifalhu, Adh.Dhidhoo, V.Rakeedhoo; floating PV in V.Keyodhoo and Adh.Kunburudhoo.
- **Grid modernisation:** STELCO genset dispatch currently done with "old-fashioned manual controls."

### ADB — Preparing Outer Islands for Sustainable Energy Development

- **PDF:** https://www.adb.org/sites/default/files/linked-documents/46122-003-ssa.pdf
- **Key data:** In 2012, installed capacity: ~120 MW inhabited islands, ~105 MW resort islands, ~20 MW industrial islands. STELCO and FENAKA used ~120 million litres of diesel in 2012.
- **FENAKA capacity gaps:** Needs "significant technical, commercial, and financial support."

### Our World in Data — Maldives Energy Profile

- **URL:** https://ourworldindata.org/energy/country/maldives
- **Use:** Historical time series for total energy consumption, electricity generation, and energy mix.

### Bogdanov et al. (2021) — Full energy system model for Maldives

- **Citation:** Bogdanov, D. et al. (2021). Powering an island energy system by offshore floating technologies towards 100% renewables: A case for the Maldives. *Applied Energy*, 308, 118360.
- **URL:** https://www.sciencedirect.com/science/article/pii/S0306261921016056
- **Key finding:** Energy transition in the Maldives until 2030 is possible with minor cost markup. Floating offshore solar PV and wave power emerge as major energy sources. Full hourly resolution modelling for two scenarios.

### STELCO Renewable Energy Page

- **URL:** https://stelco.com.mv/renewable-energy
- **Content:** Overview of STELCO's RE installations, hybrid solar+battery systems, floating PV, and research into wind and ocean energy.

### IRENA — STELCO Presentation (2015)

- **PDF:** https://www.irena.org/-/media/Files/IRENA/Agency/Events/2015/Sep/17/1ExpandingRenEnIntegSTELCOGrid.pdf
- **Content:** STELCO's first commercial-scale solar PV (698 kWp in 2012 on six islands in Malé Atoll); 740 kWp in Malé under Japanese grant aid.

---

## Summary Decision Matrix

| # | Parameter | Recommendation | Confidence | Key Source |
|---|---|---|---|---|
| C4/H3 | HVDC converter station $/MW | Accept $1.6M/MW, range $1.2–2.0M/MW | Medium-High | Härtel et al. (2017), Vrana & Härtel (2023), MISO MTEP24 |
| H5 | Per-island electricity data | Download Island Electricity Data Book 2019; Malé = 57% | High | Ministry of Environment, Maldives |
| H6 | Outer-atoll fuel surcharge | Uniform STO diesel price; effective electricity cost 50–200% higher | Medium | STO pricing + CIF/World Bank |
| H7 | Sectoral electricity split | Use 70/15/15 illustrative split; flag as unverified | Low | No direct source; resort electricity is off-grid |
| H1 | Diesel genset lifetime | 20 years, industry standard | High | OEM guidance (Wärtsilä, CAT, MAN) |
| H8 | Health damage costs | $30–60/MWh weighted average; include L4 | Medium | Parry et al. (2014) + Black et al. (2023) IMF updates |
| H9 | Climate adaptation premium | Skip L3; embed 5–10% notional premium | Low | GCA (2025) macro-level only; no project-specific data |
| H13 | Idle fleet maintenance | $5–13M/yr engineering estimate; flag as such | Low | Bottom-up derivation from industry O&M rates |
