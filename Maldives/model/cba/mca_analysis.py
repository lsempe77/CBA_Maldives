"""
Multi-Criteria Analysis (MCA) Framework for Maldives Energy CBA.

Complements the CBA by evaluating scenarios across multiple dimensions
that are not fully captured by NPV/BCR alone. Uses normalised scoring
(0-1) across 8 criteria with configurable weights.

L17 — Multi-criteria analysis framework.

References:
    - Boardman et al. (2018), Cost-Benefit Analysis, Ch. 2
    - ADB (2017), Guidelines for Economic Analysis of Projects, §6.4
    - IRENA (2019), Planning and Prospects for Renewable Power: 
      West Africa (MCA methodology appendix)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from model.config import Config, get_config


# ── Criteria definitions ────────────────────────────────────────────

@dataclass
class CriterionScore:
    """Score for a single criterion for one scenario."""
    raw_value: float           # Original metric value (e.g., NPV in $M)
    normalised: float          # 0-1 normalised score (1 = best)
    weighted: float            # normalised × weight
    direction: str             # "higher_better" or "lower_better"


@dataclass
class ScenarioMCAResult:
    """Full MCA result for a single scenario."""
    scenario_key: str
    scenario_label: str
    criterion_scores: Dict[str, CriterionScore]
    total_weighted_score: float
    rank: int = 0


# ── Default criteria and weights ────────────────────────────────────

def _get_default_weights(config: Config) -> Dict[str, float]:
    """Build criteria weights dict from config (loaded from parameters.csv).
    
    With 10 criteria, default weights are rebalanced to sum to 1.0.
    The original 8 criteria weights are scaled down proportionally,
    and the 2 new criteria (job_creation, forex_savings) get 5% each.
    """
    # Original 8 weights from config
    orig = {
        "economic_efficiency":   config.mca.w_economic_efficiency,
        "environmental_impact":  config.mca.w_environmental_impact,
        "energy_security":       config.mca.w_energy_security,
        "health_benefits":       config.mca.w_health_benefits,
        "fiscal_burden":         config.mca.w_fiscal_burden,
        "implementation_ease":   config.mca.w_implementation_ease,
        "social_equity":         config.mca.w_social_equity,
        "climate_resilience":    config.mca.w_climate_resilience,
    }
    # Scale original 8 down to make room for 2 new criteria at 5% each
    new_weight = 0.05  # 5% each for job_creation and forex_savings
    scale = 1.0 - 2 * new_weight  # = 0.90
    weights = {k: v * scale for k, v in orig.items()}
    weights["job_creation"] = new_weight
    weights["forex_savings"] = new_weight
    return weights


def _validate_weights(weights: Dict[str, float]) -> None:
    """Ensure weights sum to 1.0 (within tolerance)."""
    total = sum(weights.values())
    if abs(total - 1.0) > 0.001:
        raise ValueError(
            f"MCA weights must sum to 1.0 (got {total:.4f}). "
            f"Weights: {weights}"
        )


# ── Metric extraction ──────────────────────────────────────────────

def _estimate_transport_health_mca(config: Config, re_share: float) -> float:
    """
    Estimate transport health co-benefits for MCA, scaled by scenario RE share.
    
    Higher RE share means EV charging uses cleaner electricity → larger net
    health gain from avoided ICE emissions (PM2.5, NOx, noise).
    Uses the Medium EV adoption scenario as reference, prorated by RE share.
    
    Returns:
        Transport health co-benefits in $M (cumulative undiscounted, indicative).
    """
    tr = config.transport
    years = config.end_year - config.base_year + 1
    
    # Approximate average fleet over horizon (midpoint growth)
    avg_fleet = tr.total_vehicles_2026 * (1 + tr.fleet_growth_rate) ** (years / 2)
    avg_ev_share = tr.ev_target_medium * 0.5  # Rough average of S-curve
    avg_ev_mc = avg_fleet * avg_ev_share * tr.motorcycle_share
    
    annual_km = tr.motorcycle_daily_km * 365
    damage_per_vkm = tr.pm25_damage_per_vkm + tr.nox_damage_per_vkm + tr.noise_reduction_per_ev_km
    
    # Annual health benefit × years × RE share scaling
    annual_health = avg_ev_mc * annual_km * damage_per_vkm
    cumulative_health_m = annual_health * years / 1e6
    
    # Scale by RE share: 100% RE → full benefit; 0% RE → ~30% benefit
    # (EVs still avoid tailpipe PM2.5/NOx regardless, but grid CO₂ matters for net)
    re_scale = 0.3 + 0.7 * re_share
    return round(cumulative_health_m * re_scale, 1)


def _estimate_job_years(capex_m: float, scenario_key: str) -> float:
    """
    Estimate construction + O&M job-years from CAPEX.
    
    Uses IRENA (2020) "Renewable Energy and Jobs" multipliers:
      - Solar PV: ~25 jobs/MW (construction) + 0.3 jobs/MW/yr (O&M)
      - Submarine cable: ~10 jobs per $M CAPEX
      - LNG terminal: ~8 jobs per $M CAPEX
    Simplified to composite rate: ~12 direct job-years per $M CAPEX.
    
    Source: IRENA (2020), Renewable Energy and Jobs – Annual Review;
            IRENA (2022), World Energy Transitions Outlook.
    """
    # Composite multiplier (direct jobs-per-$M CAPEX)
    # Solar-heavy scenarios get higher multiplier (more labor-intensive)
    solar_heavy = {"islanded_green", "nearshore_solar", "maximum_re", "national_grid"}
    multiplier = 15.0 if scenario_key in solar_heavy else 10.0
    return round(capex_m * multiplier, 0)


def _estimate_forex_savings(scenario_summary: dict, bau_summary: dict) -> float:
    """
    Estimate cumulative forex savings from reduced diesel imports ($M).
    
    Maldives imports 100% of diesel fuel. Each GWh of diesel replaced
    saves ~270 kL of diesel import (at 3.3 kWh/L) × ~$0.85/L.
    
    Returns:
        Cumulative forex savings in $M (higher = better).
    """
    bau_diesel_gwh = bau_summary.get("total_diesel_gwh", 0.0)
    s_diesel_gwh = scenario_summary.get("total_diesel_gwh", bau_diesel_gwh)
    diesel_reduction_gwh = bau_diesel_gwh - s_diesel_gwh
    # Each GWh = 1e6 kWh; at 3.3 kWh/L → ~303,000 L = 303 kL
    # At $0.85/L → ~$257k/GWh ≈ $0.257M/GWh
    forex_per_gwh_m = 0.257  # $M per GWh of diesel avoided
    return round(diesel_reduction_gwh * forex_per_gwh_m, 1)


def _extract_metrics(
    cba_results: dict,
    scenario_summaries: dict,
    config: Config,
) -> Dict[str, Dict[str, float]]:
    """
    Extract raw metric values for each scenario from CBA outputs.
    
    Returns:
        {scenario_key: {criterion_name: raw_value, ...}, ...}
    """
    scenarios_alt = ["full_integration", "national_grid", "islanded_green", "nearshore_solar", "maximum_re", "lng_transition"]
    metrics: Dict[str, Dict[str, float]] = {}
    
    # BAU baseline values for comparison
    bau_summary = scenario_summaries.get("bau", {})
    bau_emissions = bau_summary.get("total_emissions_mtco2", 0.0)
    
    for s_key in scenarios_alt:
        inc = cba_results.get("incremental_vs_bau", {}).get(s_key, {})
        npv_result = cba_results.get("npv_results", {}).get(s_key, {})
        summary = scenario_summaries.get(s_key, {})
        
        # Economic efficiency: NPV savings vs BAU ($M)
        npv_savings_m = inc.get("npv_savings", 0.0) / 1e6
        
        # Environmental: cumulative CO₂ reduction vs BAU (MtCO₂)
        s_emissions = summary.get("total_emissions_mtco2", bau_emissions)
        co2_reduction = bau_emissions - s_emissions
        
        # Energy security: final year RE share (0-1)
        re_share = summary.get("final_re_share", 0.0)
        
        # Health benefits: diesel GWh displaced (physical metric)
        # G-MO-01 fix: Previously used monetised PV health benefits ($M) which
        # double-counts with economic_efficiency (NPV savings already includes
        # health co-benefits). Changed to physical metric: cumulative diesel GWh
        # avoided vs BAU. This is truly independent of the NPV calculation and
        # captures the health-relevant driver (less diesel = less PM2.5/NOx).
        bau_diesel_gwh = bau_summary.get("total_diesel_gwh", 0.0)
        s_diesel_gwh = summary.get("total_diesel_gwh", bau_diesel_gwh)
        diesel_gwh_avoided = bau_diesel_gwh - s_diesel_gwh
        
        # Fiscal burden: total CAPEX ($M) — lower is better
        capex_m = summary.get("total_capex_million", 0.0)
        
        # Implementation ease: qualitative score from parameters.csv
        implementation_scores = {
            "full_integration": config.mca.fi_implementation,
            "national_grid":    config.mca.ng_implementation,
            "islanded_green":   config.mca.ig_implementation,
            "nearshore_solar":  config.mca.ns_implementation,
            "maximum_re":       config.mca.mx_implementation,
            "lng_transition":   config.mca.lng_implementation,
        }
        impl_score = implementation_scores[s_key]  # LW-04: no silent fallback
        
        # Social equity: qualitative score from parameters.csv
        equity_scores = {
            "full_integration": config.mca.fi_equity,
            "national_grid":    config.mca.ng_equity,
            "islanded_green":   config.mca.ig_equity,
            "nearshore_solar":  config.mca.ns_equity,
            "maximum_re":       config.mca.mx_equity,
            "lng_transition":   config.mca.lng_equity,
        }
        equity_score = equity_scores[s_key]  # LW-04: no silent fallback
        
        # Climate resilience: qualitative score from parameters.csv
        resilience_scores = {
            "full_integration": config.mca.fi_resilience,
            "national_grid":    config.mca.ng_resilience,
            "islanded_green":   config.mca.ig_resilience,
            "nearshore_solar":  config.mca.ns_resilience,
            "maximum_re":       config.mca.mx_resilience,
            "lng_transition":   config.mca.lng_resilience,
        }
        resilience_score = resilience_scores[s_key]  # LW-04: no silent fallback
        
        metrics[s_key] = {
            "economic_efficiency":  npv_savings_m,
            "environmental_impact": co2_reduction,
            "energy_security":      re_share,
            "health_benefits":      diesel_gwh_avoided,
            "fiscal_burden":        capex_m,
            "implementation_ease":  impl_score,
            "social_equity":        equity_score,
            "climate_resilience":   resilience_score,
            # Item-5: two additional criteria
            "job_creation":         _estimate_job_years(capex_m, s_key),
            "forex_savings":        _estimate_forex_savings(summary, bau_summary),
        }
    
    return metrics


# ── Normalisation ───────────────────────────────────────────────────

# Direction: for each criterion, is higher better or lower better?
CRITERION_DIRECTION = {
    "economic_efficiency":   "higher_better",
    "environmental_impact":  "higher_better",
    "energy_security":       "higher_better",
    "health_benefits":       "higher_better",
    "fiscal_burden":         "lower_better",
    "implementation_ease":   "higher_better",
    "social_equity":         "higher_better",
    "climate_resilience":    "higher_better",
    "job_creation":          "higher_better",
    "forex_savings":         "higher_better",
}


def _normalise_metrics(
    metrics: Dict[str, Dict[str, float]],
) -> Dict[str, Dict[str, Tuple[float, float]]]:
    """
    Min-max normalise each criterion across scenarios to [0, 1].
    
    Returns:
        {scenario_key: {criterion: (raw, normalised), ...}, ...}
    """
    criteria = list(next(iter(metrics.values())).keys())
    scenarios = list(metrics.keys())
    
    result: Dict[str, Dict[str, Tuple[float, float]]] = {
        s: {} for s in scenarios
    }
    
    for criterion in criteria:
        values = [metrics[s][criterion] for s in scenarios]
        v_min = min(values)
        v_max = max(values)
        spread = v_max - v_min
        
        direction = CRITERION_DIRECTION.get(criterion, "higher_better")
        
        for s in scenarios:
            raw = metrics[s][criterion]
            if spread == 0:
                norm = 1.0  # All equal → all get perfect score
            elif direction == "higher_better":
                norm = (raw - v_min) / spread
            else:  # lower_better
                norm = (v_max - raw) / spread
            
            result[s][criterion] = (raw, norm)
    
    return result


# ── Main MCA engine ─────────────────────────────────────────────────

SCENARIO_LABELS = {
    "full_integration": "S2: India Cable (Full Integration)",
    "national_grid":    "S3: National Grid (Progressive)",
    "islanded_green":   "S4: Islanded Green (All Solar)",
    "nearshore_solar":  "S5: Near-Shore Solar",
    "maximum_re":       "S6: Maximum RE (80%+)",
    "lng_transition":   "S7: LNG Transition",
}

CRITERION_LABELS = {
    "economic_efficiency":   "Economic Efficiency (NPV savings)",
    "environmental_impact":  "Environmental Impact (CO₂ reduction)",
    "energy_security":       "Energy Security (RE share)",
    "health_benefits":       "Health Co-Benefits (Diesel GWh Avoided)",
    "fiscal_burden":         "Fiscal Burden (CAPEX)",
    "implementation_ease":   "Implementation Feasibility",
    "social_equity":         "Social Equity (Access)",
    "climate_resilience":    "Climate Resilience",
    "job_creation":          "Job Creation (job-years)",
    "forex_savings":         "Forex Savings (reduced imports)",
}

CRITERION_UNITS = {
    "economic_efficiency":   "$M",
    "environmental_impact":  "MtCO₂",
    "energy_security":       "%",
    "health_benefits":       "GWh",
    "fiscal_burden":         "$M",
    "implementation_ease":   "score",
    "social_equity":         "score",
    "climate_resilience":    "score",
    "job_creation":          "job-years",
    "forex_savings":         "$M",
}


def run_mca(
    cba_results: dict,
    scenario_summaries: dict,
    config: Optional[Config] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, any]:
    """
    Run Multi-Criteria Analysis across all alternative scenarios.
    
    Args:
        cba_results: Loaded cba_results.json
        scenario_summaries: Loaded scenario_summaries.json
        config: Model config (uses get_config() if None)
        weights: Optional custom weights dict (must sum to 1.0)
    
    Returns:
        Full MCA results dict suitable for JSON serialisation.
    """
    if config is None:
        config = get_config()
    
    if weights is None:
        weights = _get_default_weights(config)
    
    _validate_weights(weights)
    
    # Extract and normalise metrics
    raw_metrics = _extract_metrics(cba_results, scenario_summaries, config)
    normalised = _normalise_metrics(raw_metrics)
    
    # Build scored results
    scenario_results: List[ScenarioMCAResult] = []
    
    for s_key in normalised:
        criterion_scores: Dict[str, CriterionScore] = {}
        total_weighted = 0.0
        
        for criterion, (raw, norm) in normalised[s_key].items():
            w = weights.get(criterion, 0.0)
            weighted = norm * w
            total_weighted += weighted
            
            criterion_scores[criterion] = CriterionScore(
                raw_value=raw,
                normalised=round(norm, 4),
                weighted=round(weighted, 4),
                direction=CRITERION_DIRECTION.get(criterion, "higher_better"),
            )
        
        scenario_results.append(ScenarioMCAResult(
            scenario_key=s_key,
            scenario_label=SCENARIO_LABELS.get(s_key, s_key),
            criterion_scores=criterion_scores,
            total_weighted_score=round(total_weighted, 4),
        ))
    
    # Rank scenarios by total weighted score (highest = rank 1)
    scenario_results.sort(key=lambda r: r.total_weighted_score, reverse=True)
    for i, result in enumerate(scenario_results):
        result.rank = i + 1
    
    # Build output dict
    output = _build_output(scenario_results, weights)
    
    # G-LO-01: Add methodological note about criterion independence
    output["methodology_notes"] = {
        "criterion_independence": (
            "The MCA uses 10 criteria, of which 'economic_efficiency' (NPV savings) "
            "already includes monetised emission savings, health co-benefits, "
            "reliability benefits, and environmental externalities. The separate "
            "'environmental_impact' criterion uses physical units (MtCO2 avoided, "
            "NOT monetised), providing a genuinely independent dimension. "
            "'health_benefits' uses physical diesel GWh avoided (not monetised), "
            "providing a genuinely independent dimension that captures the "
            "health-relevant driver (less diesel combustion = less PM2.5/NOx "
            "exposure) without overlapping with NPV. "
            "'job_creation' uses IRENA (2020) employment multipliers applied to "
            "CAPEX (job-years). 'forex_savings' estimates import substitution "
            "from reduced diesel purchases ($M). Both are independent of NPV. "
            "Users should interpret MCA rankings as complementary to, not a "
            "substitute for, the ENPV analysis."
        ),
        "normalisation": "Min-max normalisation to [0, 1] across scenarios",
        "aggregation": "Linear additive weighted sum (MCDM standard)",
    }
    return output


def _build_output(
    results: List[ScenarioMCAResult],
    weights: Dict[str, float],
) -> dict:
    """Convert MCA results to a JSON-serialisable dict."""
    scenarios_out = {}
    ranking = []
    
    for r in results:
        criteria_out = {}
        for crit_name, score in r.criterion_scores.items():
            criteria_out[crit_name] = {
                "label": CRITERION_LABELS.get(crit_name, crit_name),
                "unit": CRITERION_UNITS.get(crit_name, ""),
                "raw_value": round(score.raw_value, 2),
                "normalised": score.normalised,
                "weight": weights.get(crit_name, 0.0),
                "weighted_score": score.weighted,
                "direction": score.direction,
            }
        
        scenarios_out[r.scenario_key] = {
            "label": r.scenario_label,
            "criteria": criteria_out,
            "total_weighted_score": r.total_weighted_score,
            "rank": r.rank,
        }
        
        ranking.append({
            "rank": r.rank,
            "scenario": r.scenario_key,
            "label": r.scenario_label,
            "score": r.total_weighted_score,
        })
    
    return {
        "method": "Multi-Criteria Analysis (MCA)",
        "normalisation": "min-max (0-1)",
        "weights": {k: round(v, 4) for k, v in weights.items()},
        "note": (
            "MCA complements CBA by evaluating non-monetary dimensions. "
            "Qualitative criteria (implementation_ease, social_equity, "
            "climate_resilience) use expert-assigned scores. "
            "Quantitative criteria are derived from CBA model outputs."
        ),
        "ranking": ranking,
        "scenarios": scenarios_out,
    }


# ── Sensitivity to weights ──────────────────────────────────────────

def weight_sensitivity(
    cba_results: dict,
    scenario_summaries: dict,
    config: Optional[Config] = None,
) -> Dict[str, any]:
    """
    Test how ranking changes under different weight profiles.
    Includes rank reversal analysis.
    
    Returns results for 5 profiles:
        - equal:       All weights equal (10% each)
        - economic:    Heavy economic focus (35% efficiency)
        - environment: Heavy environmental focus (25% environment)
        - equity:      Heavy equity focus (25% equity + 15% implementation)
        - jobs_forex:  Heavy employment/forex focus (25% jobs + 20% forex)
    
    Also returns rank_reversal_analysis: identifies scenario pairs whose
    relative ranking flips under different weight profiles.
    """
    all_criteria = list(CRITERION_DIRECTION.keys())  # 10 criteria
    n_criteria = len(all_criteria)
    
    profiles = {
        "equal": {k: 1.0 / n_criteria for k in all_criteria},
        "economic_focus": {
            "economic_efficiency":   0.35,
            "environmental_impact":  0.08,
            "energy_security":       0.08,
            "health_benefits":       0.04,
            "fiscal_burden":         0.12,
            "implementation_ease":   0.05,
            "social_equity":         0.05,
            "climate_resilience":    0.08,
            "job_creation":          0.05,
            "forex_savings":         0.10,
        },
        "environmental_focus": {
            "economic_efficiency":   0.08,
            "environmental_impact":  0.25,
            "energy_security":       0.12,
            "health_benefits":       0.15,
            "fiscal_burden":         0.05,
            "implementation_ease":   0.05,
            "social_equity":         0.05,
            "climate_resilience":    0.15,
            "job_creation":          0.05,
            "forex_savings":         0.05,
        },
        "equity_focus": {
            "economic_efficiency":   0.08,
            "environmental_impact":  0.05,
            "energy_security":       0.08,
            "health_benefits":       0.08,
            "fiscal_burden":         0.08,
            "implementation_ease":   0.15,
            "social_equity":         0.25,
            "climate_resilience":    0.05,
            "job_creation":          0.13,
            "forex_savings":         0.05,
        },
        "jobs_forex_focus": {
            "economic_efficiency":   0.08,
            "environmental_impact":  0.05,
            "energy_security":       0.05,
            "health_benefits":       0.05,
            "fiscal_burden":         0.07,
            "implementation_ease":   0.05,
            "social_equity":         0.05,
            "climate_resilience":    0.05,
            "job_creation":          0.30,
            "forex_savings":         0.25,
        },
    }
    
    results = {}
    all_rankings = {}  # profile -> {scenario: rank}
    for profile_name, weights in profiles.items():
        mca_result = run_mca(
            cba_results, scenario_summaries, config, weights
        )
        ranking = mca_result["ranking"]
        results[profile_name] = {
            "weights": weights,
            "ranking": ranking,
        }
        all_rankings[profile_name] = {
            entry["scenario"]: entry["rank"] for entry in ranking
        }
    
    # --- Rank Reversal Analysis ---
    # For each pair of scenarios, check if their relative ranking
    # flips under any weight profile
    scenarios = list(next(iter(all_rankings.values())).keys())
    reversals = []
    for i, s_a in enumerate(scenarios):
        for s_b in scenarios[i+1:]:
            rank_comparisons = {}
            for profile, ranks in all_rankings.items():
                # True if s_a ranks better (lower number) than s_b
                rank_comparisons[profile] = ranks[s_a] < ranks[s_b]
            
            # Check if there's a reversal: s_a beats s_b in some profiles
            # but s_b beats s_a in others
            values = list(rank_comparisons.values())
            if any(values) and not all(values):
                a_wins = [p for p, v in rank_comparisons.items() if v]
                b_wins = [p for p, v in rank_comparisons.items() if not v]
                reversals.append({
                    "scenario_a": s_a,
                    "scenario_b": s_b,
                    "a_ranked_higher_under": a_wins,
                    "b_ranked_higher_under": b_wins,
                })
    
    results["rank_reversal_analysis"] = {
        "reversals_found": len(reversals),
        "details": reversals,
        "interpretation": (
            f"{len(reversals)} rank reversal(s) detected across {len(profiles)} "
            f"weight profiles and {len(scenarios)} scenarios. "
            "Rank reversals indicate sensitivity to stakeholder priorities "
            "and should be disclosed in the report."
        ),
    }
    
    return results


# ── Console display ─────────────────────────────────────────────────

def print_mca_results(mca_output: dict) -> None:
    """Pretty-print MCA results to console."""
    print("\n" + "=" * 80)
    print("MULTI-CRITERIA ANALYSIS (MCA)")
    print("=" * 80)
    
    # Print weights
    weights = mca_output.get("weights", {})
    print("\n  Criteria Weights:")
    for crit, w in weights.items():
        label = CRITERION_LABELS.get(crit, crit)
        print(f"    {label:<40s} {w:>6.1%}")
    
    # Print ranking
    print("\n  " + "-" * 76)
    print(f"  {'Rank':<6} {'Scenario':<40s} {'Score':>8}")
    print("  " + "-" * 76)
    for entry in mca_output.get("ranking", []):
        print(f"  {entry['rank']:<6} {entry['label']:<40s} {entry['score']:>8.4f}")
    
    # Print detailed scores
    for s_key, s_data in mca_output.get("scenarios", {}).items():
        print(f"\n  {'─' * 76}")
        print(f"  {s_data['label']}  (Rank #{s_data['rank']}, Score: {s_data['total_weighted_score']:.4f})")
        print(f"  {'─' * 76}")
        print(f"    {'Criterion':<35s} {'Raw':>10} {'Norm':>6} {'Wt':>6} {'W×N':>8}")
        for crit_name, crit_data in s_data.get("criteria", {}).items():
            raw_str = f"{crit_data['raw_value']:,.1f}" if abs(crit_data['raw_value']) >= 1 else f"{crit_data['raw_value']:.3f}"
            unit = crit_data.get("unit", "")
            if unit == "%" :
                raw_str = f"{crit_data['raw_value']*100:.1f}%"
            print(
                f"    {CRITERION_LABELS.get(crit_name, crit_name):<35s} "
                f"{raw_str:>10} "
                f"{crit_data['normalised']:>6.3f} "
                f"{crit_data['weight']:>6.2f} "
                f"{crit_data['weighted_score']:>8.4f}"
            )
    
    print()


# ── Standalone runner ───────────────────────────────────────────────

def main():
    """Run MCA as standalone script."""
    # Load CBA outputs
    outputs_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "outputs"
    )
    
    cba_path = os.path.join(outputs_dir, "cba_results.json")
    summaries_path = os.path.join(outputs_dir, "scenario_summaries.json")
    
    if not os.path.exists(cba_path):
        print(f"ERROR: {cba_path} not found. Run run_cba.py first.")
        return
    if not os.path.exists(summaries_path):
        print(f"ERROR: {summaries_path} not found. Run run_cba.py first.")
        return
    
    with open(cba_path, "r") as f:
        cba_results = json.load(f)
    with open(summaries_path, "r") as f:
        scenario_summaries = json.load(f)
    
    config = get_config()
    
    # Run MCA with default weights
    mca_output = run_mca(cba_results, scenario_summaries, config)
    print_mca_results(mca_output)
    
    # Run weight sensitivity
    print("\n" + "=" * 80)
    print("WEIGHT SENSITIVITY ANALYSIS")
    print("=" * 80)
    ws = weight_sensitivity(cba_results, scenario_summaries, config)
    for profile, data in ws.items():
        if profile == "rank_reversal_analysis":
            # Print rank reversal results
            rr = data
            print(f"\n  Rank Reversals: {rr['reversals_found']} found")
            for rev in rr.get("details", []):
                print(f"    {rev['scenario_a']} vs {rev['scenario_b']}:")
                print(f"      A ranked higher under: {', '.join(rev['a_ranked_higher_under'])}")
                print(f"      B ranked higher under: {', '.join(rev['b_ranked_higher_under'])}")
            continue
        print(f"\n  Profile: {profile}")
        for entry in data["ranking"]:
            print(f"    #{entry['rank']}  {entry['label']:<40s}  {entry['score']:.4f}")
    
    # Save results
    mca_output["weight_sensitivity"] = ws
    out_path = os.path.join(outputs_dir, "mca_results.json")
    with open(out_path, "w") as f:
        json.dump(mca_output, f, indent=2)
    print(f"\n  MCA results saved to {out_path}")


if __name__ == "__main__":
    main()
