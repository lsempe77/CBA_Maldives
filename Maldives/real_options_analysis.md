# Real Options Analysis: India–Maldives Submarine Cable (S2)

**Purpose:** Qualitative and illustrative quantitative real options framing of the Full Integration (S2) submarine cable investment, complementing the standard NPV analysis.

**Date:** February 2026  
**Task:** L10 / P3  
**Key reference:** Dixit, A. K., & Pindyck, R. S. (1994). *Investment Under Uncertainty*. Princeton University Press.

---

## Table of Contents

1. [Why Real Options Matter for the Cable Decision](#1-why-real-options-matter)
2. [Sources of Uncertainty](#2-sources-of-uncertainty)
3. [Option Value of Waiting](#3-option-value-of-waiting)
4. [Illustrative Numerical Example](#4-illustrative-numerical-example)
5. [Staging Strategy](#5-staging-strategy)
6. [Implications for Scenario Ranking](#6-implications-for-scenario-ranking)
7. [Limitations](#7-limitations)
8. [References](#8-references)

---

## 1. Why Real Options Matter for the Cable Decision

Standard NPV analysis assumes a **now-or-never** investment decision: either commit the full $2.95 billion cable CAPEX in the base year (2026) or never build it. This framework ignores three features of the real decision:

1. **Irreversibility** — A submarine cable is a sunk cost. Once installed, the cable cannot be redeployed or resold at meaningful value. Dixit & Pindyck (1994, Ch. 2) show that irreversibility creates an **option value of waiting** even when NPV > 0.

2. **Uncertainty** — Key parameters evolve over time:
   - Indian electricity export price (currently $0.08/kWh, but India's own demand is growing rapidly)
   - Solar PV and battery costs (declining 5–8%/yr, which improves local alternatives)
   - Fuel price volatility (affects the BAU counterfactual)
   - Geopolitical risk (India–Maldives relations have fluctuated; cable = permanent dependency)
   - Demand growth (5% BAU, but could be higher or lower)

3. **Ability to delay** — The government can **wait and learn** before committing. Each year of delay resolves some uncertainty: solar costs become clearer, India's export capacity and willingness are better known, demand trajectories are validated.

The combination of irreversibility + uncertainty + ability to delay means that the standard NPV decision rule ($\text{NPV} > 0 \Rightarrow \text{invest}$) is **insufficient**. The correct rule becomes:

$$\text{Invest when } \text{NPV} > \text{Option Value of Waiting}$$

or equivalently, when the "value of waiting for information" is less than the "cost of delay" (foregone benefits).

---

## 2. Sources of Uncertainty

### 2.1 Cost uncertainties (downside risk to cable NPV)

| Parameter | Base Value | Range | Direction of risk |
|-----------|-----------|-------|-------------------|
| Cable CAPEX/km | $3.0M | $2.0–5.0M | ↑ Deep ocean, seismic risk |
| Indian PPA price | $0.08/kWh | $0.06–0.12 | ↑ India's domestic demand growing |
| Cable outage rate | 0.15/yr | 0.05–0.30 | ↑ Anchoring, seismic risk |
| Cable outage duration | 1–6 months | — | ↑ Repair logistics for 700 km cable |
| Geopolitical risk | Low (current) | — | ↑ India–Maldives relations variable |
| Converter station cost/MW | $1.6M | $1.2–2.0M | ↑ Supply chain constraints |

### 2.2 Opportunity cost of waiting (improving alternatives)

| Parameter | Current (2026) | Projected (2031) | Annual decline |
|-----------|---------------|-----------------|----------------|
| Solar PV CAPEX | $1,500/kW | ~$1,100/kW | ~6%/yr (IRENA) |
| Battery CAPEX | $350/kWh | ~$220/kWh | ~8%/yr (BNEF) |
| Floating solar premium | 1.5× ground-mount | ~1.2× | Technology maturation |

As local RE costs decline, the **incremental value of the cable** (savings over the next-best alternative) shrinks. This is the core tension: **delay loses annual benefits** but **waiting reveals whether the cable is truly needed** once solar+battery become cheaper.

### 2.3 Demand uncertainty

| Scenario | Growth rate | 2036 demand (GWh) | Impact on cable value |
|----------|------------|--------------------|-----------------------|
| Low | 3%/yr | ~1,610 | Cable oversized; lower utilisation |
| Base | 5%/yr | ~1,955 | Cable well-utilised |
| High | 7%/yr | ~2,360 | Cable capacity may bind; expansion needed |

---

## 3. Option Value of Waiting

### 3.1 Conceptual framework

Following Dixit & Pindyck (1994, Ch. 5), consider a simple two-period model:

- **Period 0 (now):** The government can invest $K$ in the cable, earning perpetual annual benefits $B$ starting immediately. Or it can **wait one period**.
- **Period 1 (next period):** Uncertainty resolves. With probability $p$, benefits are high ($B_H$); with probability $(1-p)$, benefits are low ($B_L$).
- **If the government waits:** It invests in Period 1 only if $B_i / r > K$ (i.e., only in the high-benefit state).

The **option value** is the difference between the "invest now" NPV and the "optimal wait" NPV:

$$V_{\text{wait}} = p \cdot \max\left(\frac{B_H}{r} - K,\, 0\right) + (1-p) \cdot \max\left(\frac{B_L}{r} - K,\, 0\right) - \frac{1}{1+r}\left(\frac{E[B]}{r} - K\right)$$

Wait is preferred when $V_{\text{wait}} > 0$, i.e., the optionality of **not investing in the bad state** outweighs the one-period delay cost.

### 3.2 More realistic framing: multi-year delay

In practice, the government might delay 5 years (to 2031). During those 5 years:

- **Cost of delay:** Foregone net benefits of cable operation (fuel savings, emission reductions, PPA revenue minus O&M).
- **Benefit of delay:** (a) Information on solar/battery cost trajectory; (b) information on Indian PPA price stability; (c) reduced CAPEX if technology costs fall; (d) avoided sunk cost if the cable proves unnecessary.

The **option value of 5-year delay** can be approximated as:

$$\text{Option Value} \approx (1-p) \cdot K \cdot \frac{1}{(1+r)^5}$$

where $(1-p)$ is the probability that, after 5 years of information, the government would **choose not to build** (because local RE has become cheaper than the cable).

---

## 4. Illustrative Numerical Example

### Parameters (from CBA model)

| Parameter | Value | Source |
|-----------|-------|--------|
| Cable total CAPEX ($K$) | $2.95 billion | `config.py`: 700 km × $3M + converters + landing + IDC + grid |
| Annual net benefits ($B$) | $680 million/yr | S2 incremental NPV $9.34B ÷ 13.76 annuity factor (6%, 30yr) |
| Discount rate ($r$) | 6% | ADB SIDS concessional |
| Analysis period | 30 years | Base case |

### Scenario: 5-year delay to 2031

**Assumptions for illustration:**
- There is a 30% probability ($1-p = 0.30$) that by 2031, solar PV + battery + floating solar costs will have fallen enough that a local-only solution (e.g., S6 Maximum RE enhanced) achieves LCOE parity with the cable option — making the cable unnecessary.
- There is a 70% probability ($p = 0.70$) that the cable remains the preferred option in 2031.
- If built in 2031, the cable CAPEX may be 5% lower (construction cost learning), so $K_{2031} = 0.95 \times K = \$2.80\text{B}$.
- Annual benefits grow at 2%/yr (demand growth increases value of imports).

#### NPV of "invest now" (2026):

$$\text{NPV}_{\text{now}} = -K + \sum_{t=1}^{30} \frac{B}{(1+r)^t} = -2.95 + 9.34 = \$6.39\text{B}$$

(This is the incremental NPV from the standard CBA, discounted to 2026.)

#### NPV of "wait 5 years" (decide in 2031):

**If cable is built in 2031 (prob = 0.70):**

$$\text{NPV}_{\text{build, 2031}} = \frac{1}{(1+r)^5} \left[-K_{2031} + \sum_{t=1}^{25} \frac{B \cdot (1.02)^{t+5}}{(1+r)^t}\right]$$

- Lost: 5 years of benefits ($B \times \text{annuity factor for 5yr at 6\%}$)
- Gained: lower CAPEX, 25 years of (higher) benefits starting from 2031

Approximate values:
- Foregone benefits (2026–2030): $680M × 4.212 = $2,864M PV
- CAPEX saving: $(2.95 - 2.80) × \frac{1}{1.06^5}$ = $150M × 0.747 = $112M PV
- Net loss from delay: $2,864M − $112M = $2,752M PV
- NPV if built in 2031: $6,390M − $2,752M = $3,638M PV

**If cable is NOT built (prob = 0.30):**

$$\text{NPV}_{\text{no build}} = 0 + \text{NPV of local alternative}$$

The avoided sunk cost = $K × \frac{1}{(1+r)^5}$ = $2.95B × 0.747 = $2,204M PV (the CAPEX that would have been wasted if the cable turns out uneconomic).

But we must also account for the local alternative's NPV. Assume the government pursues S6 Maximum RE enhanced instead, with NPV savings vs BAU of approximately $7.46B (from the standard CBA, S6 NPV = $8.21B total cost vs BAU $15.68B, so savings ≈ $7.46B). In this state, the "no cable" option is not zero — it's the next-best alternative.

#### Expected NPV of waiting:

$$E[\text{NPV}_{\text{wait}}] = 0.70 \times \$3,638\text{M} + 0.30 \times \$0\text{M} = \$2,547\text{M}$$

(The $0 in the no-build state represents the *incremental* value of the cable decision — the government gets S6 benefits regardless.)

#### Option value:

$$\text{Option Value} = E[\text{NPV}_{\text{wait}}] - \text{NPV}_{\text{now if good state}} \times p$$

More precisely, the option value is the difference between the flexible strategy (wait → decide) and the inflexible strategy (invest now regardless):

$$\text{Option Value} = E[\text{NPV}_{\text{wait}}] - \text{NPV}_{\text{now}}$$
$$= \$2,547\text{M} - (-2,950 + 9,340) = \$2,547\text{M} - \$6,390\text{M}$$
$$= -\$3,843\text{M}$$

### Interpretation

The option value is **negative** in this illustration, meaning **immediate investment is preferred**. This is because:

1. The cable's NPV ($6.39B) is so large relative to the CAPEX ($2.95B) that foregone benefits during delay overwhelm the option value of waiting.
2. The probability of the cable becoming unnecessary (30%) is too low to justify giving up 5 years of $680M/yr benefits.
3. The BCR of 2.71 implies the cable is "deeply in the money" — the analogy to financial options is an option with a very high intrinsic value, where waiting sacrifices time value.

### Sensitivity: When would waiting be optimal?

The "wait" strategy becomes preferable when:

$$p < \frac{\text{NPV}_{\text{now}} - \text{Foregone benefits} \times (1-p)}{\text{NPV}_{\text{now}}}$$

Solving for the breakeven probability that the cable remains needed:

| $p$ (prob cable needed) | $1-p$ (prob unnecessary) | NPV wait | NPV now | Preferred |
|------------------------|-------------------------|----------|---------|-----------|
| 0.90 | 0.10 | $3,274M | $6,390M | Invest now |
| 0.70 | 0.30 | $2,547M | $6,390M | Invest now |
| 0.50 | 0.50 | $1,819M | $6,390M | Invest now |
| 0.30 | 0.70 | $1,091M | $6,390M | Invest now |
| 0.10 | 0.90 | $364M | $6,390M | Invest now |

**Result:** Even with a 90% probability that the cable becomes unnecessary, immediate investment is still preferred in this simplified framework. This is because the **annual benefits ($680M) are very large relative to the sunk CAPEX ($2.95B)**, making delay extremely costly. The cable's BCR of 2.71 means it would need to become truly value-destroying (NPV < 0) for waiting to be worthwhile.

### When would the result flip?

The option to wait becomes valuable when:
1. **Cable NPV is marginal** (BCR close to 1.0) — not the case here (BCR = 2.71)
2. **Uncertainty is extreme** — e.g., Indian PPA price could triple, making the cable uneconomic
3. **Delay cost is low** — e.g., if solar PV already provides most of the cable's benefits, so waiting doesn't sacrifice much
4. **Irreversibility premium is high** — e.g., if the cable has zero salvage value AND locks Maldives into unfavorable geopolitical dependency

In our model, the switching value analysis (P4) provides relevant context: the Indian PPA price would need to rise above ~$0.15–0.20/kWh before S2 loses its cost advantage — nearly double the current $0.08/kWh.

---

## 5. Staging Strategy

Even though immediate full investment is NPV-optimal, a **staged approach** can reduce risk without significantly sacrificing value:

### Phase 1 (2026–2028): Feasibility and commitment
- Detailed marine survey, route selection, environmental impact assessment
- Bilateral agreement with India on PPA terms, capacity rights, cost-sharing
- Estimated cost: $50–100M (2–3% of total CAPEX)
- **Option value:** Reveals construction risk, seabed conditions, political commitment. Government retains the option to abandon at low sunk cost.

### Phase 2 (2028–2031): Construction of 200 MW cable
- Full CAPEX commitment: remaining ~$2.85B
- 3-year construction period (typical for 700 km submarine cable)
- Commissioning by 2031

### Phase 3 (2035+): Capacity expansion (if needed)
- If demand growth exceeds 5%, consider second cable or cable upgrade
- India's export capacity evolves — renegotiate PPA terms based on revealed costs
- This is a **compound option**: the first cable creates the option to expand

### Value of staging

The feasibility phase (Phase 1) is itself an option: spend $50–100M to gain information, then decide whether to commit the remaining $2.85B. The option value of this small initial investment is:

$$V_{\text{feasibility}} = p \cdot \text{NPV}_{\text{full}} + (1-p) \cdot (-C_{\text{feasibility}})$$

With $p = 0.85$ (assuming 15% chance feasibility reveals a fatal flaw):

$$V_{\text{feasibility}} = 0.85 \times \$6,390\text{M} + 0.15 \times (-\$75\text{M}) = \$5,420\text{M}$$

This is lower than the "invest immediately" NPV ($6,390M) by only $970M — the expected value of avoiding a bad $2.95B investment 15% of the time.

**Recommendation:** The staging approach is prudent risk management even though full immediate investment has higher expected NPV. The government should pursue Phase 1 immediately while preserving the option on Phase 2.

---

## 6. Implications for Scenario Ranking

The real options analysis does **not change the overall scenario ranking** from the standard CBA:

| Rank | Standard CBA (NPV savings) | Real Options Adjustment |
|------|---------------------------|------------------------|
| 1 | S7 LNG Transition ($9.57B) | S7 — lowest irreversibility (modular, reversible fuel switch) |
| 2 | S3 National Grid ($10.35B) | S3 — incremental, low irreversibility |
| 3 | S2 Full Integration ($9.34B) | S2 — **highest irreversibility** but deeply in-the-money → staging recommended |
| 4 | S6 Maximum RE ($7.46B) | S6 — moderate irreversibility (modular solar/battery, but floating solar is novel) |
| 5 | S4 Islanded Green ($9.50B) | S4 — low irreversibility (modular, per-island) |
| 6 | S5 Near-Shore Solar ($6.91B) | S5 — moderate (uninhabited island infrastructure) |
| 7 | S1 BAU (baseline) | S1 — no new investment, but highest fuel price risk |

### Key insight

Real options analysis **strengthens the case for S7 (LNG) and S3 (National Grid)** relative to S2 (Full Integration):

- **S7 LNG** has the highest NPV savings AND lowest irreversibility — LNG infrastructure is modular, markets are liquid, and the switch can be reversed if RE costs fall faster than expected.
- **S3 National Grid** is incremental domestic investment with proven technology — each island's RE system can be individually scaled.
- **S2 Full Integration** has the third-highest NPV savings but the **highest irreversibility** — a single $2.95B commitment to a 40-year asset with geopolitical dependency.

In a real options framework, the **risk-adjusted ranking** slightly favours S7 > S3 > S2, even though S2 and S3 have comparable standard NPV. This aligns with the DDR analysis (P1), which also showed S2 rising in relative terms under lower long-term discount rates.

---

## 7. Limitations

1. **Simplified two-state model:** The numerical illustration uses a binary resolution of uncertainty (cable needed vs. not needed). Real uncertainty is continuous and multi-dimensional.

2. **No formal stochastic modelling:** A rigorous real options valuation would require:
   - Geometric Brownian motion for fuel prices and RE costs
   - Dynamic programming solution for optimal stopping time
   - Monte Carlo simulation of option exercise
   - This is a substantial modelling exercise beyond the scope of this CBA (estimated 2–4 weeks of additional work).

3. **Ignores strategic/geopolitical value:** The cable may have strategic value to India (power projection, connectivity) that creates additional political impetus beyond economic NPV. This is not captured in the real options framework.

4. **Assumes static alternatives:** The analysis assumes S6/S3 alternatives are fixed. In reality, the choice to delay the cable may trigger accelerated investment in local alternatives, changing the counterfactual.

5. **Correlated uncertainties:** Fuel prices, RE costs, and Indian PPA prices are correlated (all driven partly by global energy markets). The simplified model treats them as independent.

6. **No abandonment option:** Once the cable is built, it operates for 40 years. The model does not consider the option to abandon or repurpose the cable if it becomes uneconomic mid-life.

---

## 8. References

1. Dixit, A. K., & Pindyck, R. S. (1994). *Investment Under Uncertainty*. Princeton University Press. ISBN: 978-0-691-03410-2.

2. McDonald, R., & Siegel, D. (1986). The Value of Waiting to Invest. *Quarterly Journal of Economics*, 101(4), 707–727.

3. Trigeorgis, L. (1996). *Real Options: Managerial Flexibility and Strategy in Resource Allocation*. MIT Press.

4. Boomsma, T. K., Meade, N., & Fleten, S.-E. (2012). Renewable energy investments under different support schemes: A real options approach. *European Journal of Operational Research*, 220(1), 225–237.

5. Venetsanos, K., Angelopoulou, P., & Tsoutsos, T. (2002). Renewable energy sources project appraisal under uncertainty: the case of wind energy exploitation within a changing energy market environment. *Energy Policy*, 30(4), 293–307.

6. Fernandes, B., Cunha, J., & Ferreira, P. (2011). The use of real options approach in energy sector investments. *Renewable and Sustainable Energy Reviews*, 15(9), 4491–4497.

---

*This document fulfils tasks L10 (Real options / staging analysis) and P3 (Real options framing) in the IMPROVEMENT_PLAN.md.*
