"""
Distributional Analysis Module (L15)
=====================================

Analyses the distributional impact of energy transition scenarios using
HIES 2019 microdata (Household Income and Expenditure Survey).

Key outputs:
1. Baseline electricity expenditure burden by quintile × geography
2. Scenario tariff impact simulation (LCOE passthrough)
3. Poverty impact (energy poverty headcount shifts)
4. Geographic equity (atoll-level burden variation)
5. Fiscal incidence (who pays vs who benefits)

Data sources:
- HIES 2019: master_exp.dta (COICOP expenditures), CombinedIncome_HHLevel.dta
- Maldives Poverty Assessment 2022 (World Bank): poverty lines, atoll rates, Gini
- CBA model outputs: scenario LCOEs, costs, emissions

Author: CBA Model Team
Date: 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import warnings

import numpy as np

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from model.config import Config, get_config


# =============================================================================
# CONSTANTS (mathematical / definitional — not parameters)
# =============================================================================

# COICOP classification codes (international standard, not parameters)
COICOP_ELECTRICITY = 4510001  # "Electricity bill"
COICOP_GAS = 4521001          # "Gas" (cooking gas)
COICOP_KEROSENE = 4530001     # "Kerosene"

# HIES 2019 geography codes (survey-defined, not parameters)
GEO_MALE = 1   # maleatoll == 1 → Malé
GEO_ATOLL = 2  # maleatoll == 2 → Atolls

# Number of quintiles (methodological constant)
N_QUINTILES = 5


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """Compute weighted median. G-MO-01: ensures median uses survey weights."""
    if len(values) == 0:
        return 0.0
    sorted_indices = np.argsort(values)
    sorted_values = values[sorted_indices]
    sorted_weights = weights[sorted_indices]
    cumulative_weight = np.cumsum(sorted_weights)
    cutoff = sorted_weights.sum() / 2.0
    idx = np.searchsorted(cumulative_weight, cutoff)
    return float(sorted_values[min(idx, len(sorted_values) - 1)])


def _weighted_qcut(values: np.ndarray, weights: np.ndarray, n_quantiles: int) -> np.ndarray:
    """G-MO-02: Assign weighted quantile labels (1..n_quantiles).
    
    Unlike pd.qcut (which creates equal-count bins), this creates bins where
    each quantile represents an equal share of the *weighted* population.
    For HIES survey data with sampling weights, this ensures each quintile
    represents ~20% of the population, not ~20% of the sample.
    
    Args:
        values: Array of values to bin (e.g. per-capita expenditure)
        weights: Sampling weights for each observation
        n_quantiles: Number of quantile groups (5 for quintiles)
    
    Returns:
        Integer array of quantile labels (1-based)
    """
    sorted_indices = np.argsort(values)
    sorted_weights = weights[sorted_indices]
    cumulative_weight = np.cumsum(sorted_weights)
    total_weight = cumulative_weight[-1]
    
    # Assign each observation to a quantile based on weighted cumulative share
    labels = np.empty(len(values), dtype=int)
    for i, idx in enumerate(sorted_indices):
        share = cumulative_weight[i] / total_weight
        # Quantile 1 = bottom 20%, ..., quantile n = top 20%
        q = min(int(share * n_quantiles) + 1, n_quantiles)
        labels[idx] = q
    
    return labels


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class QuintileProfile:
    """Electricity expenditure profile for a single quintile."""
    quintile: int
    n_households: int
    n_with_electricity: int
    mean_monthly_bill_mvr: float
    median_monthly_bill_mvr: float
    mean_elec_share_pct: float       # electricity as % of total expenditure
    mean_energy_share_pct: float     # all energy as % of total expenditure
    mean_monthly_expenditure_mvr: float
    mean_annual_income_mvr: float


@dataclass
class GeoProfile:
    """Electricity expenditure profile for a geography (Malé vs Atolls)."""
    geography: str  # "Male" or "Atoll"
    n_households: int
    n_with_electricity: int
    mean_monthly_bill_mvr: float
    mean_elec_share_pct: float
    mean_annual_income_mvr: float
    quintile_profiles: List[QuintileProfile]


@dataclass
class AtollProfile:
    """Electricity expenditure profile for a specific atoll."""
    atoll_code: int
    atoll_name: str
    n_households: int
    mean_elec_share_pct: float
    mean_monthly_bill_mvr: float
    mean_annual_income_mvr: float
    poverty_rate_pct: Optional[float] = None  # From Poverty Assessment 2022


@dataclass
class GenderProfile:
    """Electricity expenditure profile disaggregated by sex of household head (P5)."""
    gender: str  # 'male_headed' or 'female_headed'
    n_households: int
    share_of_total_pct: float
    mean_monthly_bill_mvr: float
    mean_elec_share_pct: float
    mean_energy_share_pct: float
    mean_annual_income_mvr: float
    energy_poverty_pct: float  # >10% threshold
    has_solar_pct: float
    # By quintile within gender
    quintile_elec_shares: List[float]  # 5 values, Q1–Q5


@dataclass
class TariffImpact:
    """Simulated tariff change impact for a quintile."""
    quintile: int
    geography: str
    baseline_monthly_bill_mvr: float
    new_monthly_bill_mvr: float
    change_mvr: float
    change_pct: float
    new_elec_share_pct: float
    baseline_elec_share_pct: float


@dataclass
class DistributionalResults:
    """Complete distributional analysis results."""
    # Baseline (from HIES 2019)
    national_mean_elec_share_pct: float
    national_mean_energy_share_pct: float
    national_mean_monthly_bill_mvr: float
    n_households_total: int
    n_households_with_electricity: int
    electrification_rate_pct: float
    solar_adoption_pct: float

    # By quintile (expenditure-based)
    quintile_profiles: List[QuintileProfile]

    # By geography
    male_profile: GeoProfile
    atoll_profile: GeoProfile

    # By atoll
    atoll_profiles: List[AtollProfile]

    # By gender of household head (P5)
    gender_profiles: List[GenderProfile]
    gender_tariff_impacts: Dict[str, Dict[str, float]]  # scenario → {male: %, female: %}
    gender_energy_poverty: Dict[str, Dict[str, float]]  # scenario → {male: %, female: %}

    # Scenario impacts
    scenario_tariff_impacts: Dict[str, List[TariffImpact]]

    # Poverty impact
    energy_poverty_baseline_pct: float    # HH spending >10% on energy
    energy_poverty_by_scenario: Dict[str, float]

    # Progressivity metrics
    concentration_coefficient: float  # Electricity expenditure concentration
    suits_index_by_scenario: Dict[str, float]  # Suits index for tariff change

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dict."""
        return {
            "baseline": {
                "national_mean_elec_share_pct": round(self.national_mean_elec_share_pct, 2),
                "national_mean_energy_share_pct": round(self.national_mean_energy_share_pct, 2),
                "national_mean_monthly_bill_mvr": round(self.national_mean_monthly_bill_mvr, 0),
                "n_households_total": self.n_households_total,
                "n_households_with_electricity": self.n_households_with_electricity,
                "electrification_rate_pct": round(self.electrification_rate_pct, 1),
                "solar_adoption_pct": round(self.solar_adoption_pct, 1),
            },
            "by_quintile": [
                {
                    "quintile": qp.quintile,
                    "n_households": qp.n_households,
                    "n_with_electricity": qp.n_with_electricity,
                    "mean_monthly_bill_mvr": round(qp.mean_monthly_bill_mvr, 0),
                    "median_monthly_bill_mvr": round(qp.median_monthly_bill_mvr, 0),
                    "mean_elec_share_pct": round(qp.mean_elec_share_pct, 2),
                    "mean_energy_share_pct": round(qp.mean_energy_share_pct, 2),
                    "mean_monthly_expenditure_mvr": round(qp.mean_monthly_expenditure_mvr, 0),
                    "mean_annual_income_mvr": round(qp.mean_annual_income_mvr, 0),
                }
                for qp in self.quintile_profiles
            ],
            "by_geography": {
                "male": {
                    "n_households": self.male_profile.n_households,
                    "n_with_electricity": self.male_profile.n_with_electricity,
                    "mean_monthly_bill_mvr": round(self.male_profile.mean_monthly_bill_mvr, 0),
                    "mean_elec_share_pct": round(self.male_profile.mean_elec_share_pct, 2),
                    "mean_annual_income_mvr": round(self.male_profile.mean_annual_income_mvr, 0),
                    "by_quintile": [
                        {
                            "quintile": qp.quintile,
                            "mean_elec_share_pct": round(qp.mean_elec_share_pct, 2),
                            "mean_monthly_bill_mvr": round(qp.mean_monthly_bill_mvr, 0),
                            "n_households": qp.n_households,
                        }
                        for qp in self.male_profile.quintile_profiles
                    ],
                },
                "atoll": {
                    "n_households": self.atoll_profile.n_households,
                    "n_with_electricity": self.atoll_profile.n_with_electricity,
                    "mean_monthly_bill_mvr": round(self.atoll_profile.mean_monthly_bill_mvr, 0),
                    "mean_elec_share_pct": round(self.atoll_profile.mean_elec_share_pct, 2),
                    "mean_annual_income_mvr": round(self.atoll_profile.mean_annual_income_mvr, 0),
                    "by_quintile": [
                        {
                            "quintile": qp.quintile,
                            "mean_elec_share_pct": round(qp.mean_elec_share_pct, 2),
                            "mean_monthly_bill_mvr": round(qp.mean_monthly_bill_mvr, 0),
                            "n_households": qp.n_households,
                        }
                        for qp in self.atoll_profile.quintile_profiles
                    ],
                },
            },
            "by_atoll": [
                {
                    "atoll_code": ap.atoll_code,
                    "atoll_name": ap.atoll_name,
                    "n_households": ap.n_households,
                    "mean_elec_share_pct": round(ap.mean_elec_share_pct, 2),
                    "mean_monthly_bill_mvr": round(ap.mean_monthly_bill_mvr, 0),
                    "mean_annual_income_mvr": round(ap.mean_annual_income_mvr, 0),
                    "poverty_rate_pct": ap.poverty_rate_pct,
                }
                for ap in self.atoll_profiles
            ],
            "by_gender": [
                {
                    "gender": gp.gender,
                    "n_households": gp.n_households,
                    "share_of_total_pct": round(gp.share_of_total_pct, 1),
                    "mean_monthly_bill_mvr": round(gp.mean_monthly_bill_mvr, 0),
                    "mean_elec_share_pct": round(gp.mean_elec_share_pct, 2),
                    "mean_energy_share_pct": round(gp.mean_energy_share_pct, 2),
                    "mean_annual_income_mvr": round(gp.mean_annual_income_mvr, 0),
                    "energy_poverty_pct": round(gp.energy_poverty_pct, 1),
                    "has_solar_pct": round(gp.has_solar_pct, 1),
                    "quintile_elec_shares": [round(s, 2) for s in gp.quintile_elec_shares],
                }
                for gp in self.gender_profiles
            ],
            "gender_tariff_impacts": {
                sc: {k: round(v, 1) for k, v in vals.items()}
                for sc, vals in self.gender_tariff_impacts.items()
            },
            "gender_energy_poverty": {
                sc: {k: round(v, 1) for k, v in vals.items()}
                for sc, vals in self.gender_energy_poverty.items()
            },
            "scenario_tariff_impacts": {
                scenario: [
                    {
                        "quintile": ti.quintile,
                        "geography": ti.geography,
                        "baseline_monthly_bill_mvr": round(ti.baseline_monthly_bill_mvr, 0),
                        "new_monthly_bill_mvr": round(ti.new_monthly_bill_mvr, 0),
                        "change_mvr": round(ti.change_mvr, 0),
                        "change_pct": round(ti.change_pct, 1),
                        "baseline_elec_share_pct": round(ti.baseline_elec_share_pct, 2),
                        "new_elec_share_pct": round(ti.new_elec_share_pct, 2),
                    }
                    for ti in impacts
                ]
                for scenario, impacts in self.scenario_tariff_impacts.items()
            },
            "energy_poverty": {
                "baseline_pct": round(self.energy_poverty_baseline_pct, 2),
                "by_scenario": {
                    k: round(v, 2) for k, v in self.energy_poverty_by_scenario.items()
                },
            },
            "progressivity": {
                "concentration_coefficient": round(self.concentration_coefficient, 4),
                "suits_index_by_scenario": {
                    k: round(v, 4) for k, v in self.suits_index_by_scenario.items()
                },
            },
            "data_source": "HIES 2019 (NBS Maldives); Maldives Poverty Assessment 2022 (World Bank)",
            "methodology_notes": {
                "quintiles": "Per-capita expenditure quintiles computed from HIES 2019 master_exp.dta",
                "electricity": "COICOP 4510001 (Electricity bill) from master_exp.dta",
                "weights": "Survey sampling weights (wgt) applied to all estimates",
                "energy_poverty_threshold": "10% of total household expenditure on energy",
                "tariff_simulation": "Proportional LCOE change applied to baseline electricity bill",
            },
        }


# =============================================================================
# HIES DATA LOADING
# =============================================================================

def _load_hies_data(config: Config) -> pd.DataFrame:
    """
    Load and merge HIES 2019 microdata for distributional analysis.
    
    Returns merged DataFrame with columns:
    - uqhh__id: household ID
    - atoll_code, atoll, maleatoll: geography
    - wgt: survey weight
    - totalIncome, hhsize, pci_quin: income
    - elec_annual, gas_annual, kerosene_annual: energy expenditure
    - total_annual_exp: total household expenditure
    - elec_share, energy_share: burden shares
    - pce, exp_quintile: per-capita expenditure and quintile
    - has_solar: whether HH uses solar (hh_usnslr == 1)
    """
    base = Path(__file__).parent.parent / "data" / "hies2019" / "Dataset" / "HIES2019_STATA format"
    
    if not base.exists():
        raise FileNotFoundError(
            f"HIES 2019 STATA data not found at {base}. "
            "Download from NBS Maldives and place in data/hies2019/Dataset/HIES2019_STATA format/"
        )
    
    # 1. Load expenditure data
    exp = pd.read_stata(str(base / "master_exp.dta"), convert_categoricals=False)
    
    # Extract electricity, gas, kerosene expenditure per household
    elec_hh = (
        exp[exp['coicop'] == COICOP_ELECTRICITY]
        .groupby('uqhh__id')
        .agg(elec_annual=('annexp', 'sum'), elec_monthly=('monthly_exp', 'sum'))
        .reset_index()
    )
    gas_hh = (
        exp[exp['coicop'] == COICOP_GAS]
        .groupby('uqhh__id')['annexp'].sum()
        .reset_index()
        .rename(columns={'annexp': 'gas_annual'})
    )
    kero_hh = (
        exp[exp['coicop'] == COICOP_KEROSENE]
        .groupby('uqhh__id')['annexp'].sum()
        .reset_index()
        .rename(columns={'annexp': 'kerosene_annual'})
    )
    total_exp = (
        exp.groupby('uqhh__id')['annexp'].sum()
        .reset_index()
        .rename(columns={'annexp': 'total_annual_exp'})
    )
    total_exp_m = (
        exp.groupby('uqhh__id')['monthly_exp'].sum()
        .reset_index()
        .rename(columns={'monthly_exp': 'total_monthly_exp'})
    )
    
    # 2. Load income data (has quintile assignments)
    inc = pd.read_stata(str(base / "CombinedIncome_HHLevel.dta"), convert_categoricals=False)
    
    # 3. Load household-level data (solar adoption)
    hh = pd.read_stata(str(base / "hhlevel.dta"), convert_categoricals=False)
    solar_flag = hh[['uqhh__id', 'hh_usnslr']].copy()
    solar_flag['has_solar'] = solar_flag['hh_usnslr'] == 1
    
    # 3b. Load sex of household head from Usualmembers (P5: gender disaggregation)
    try:
        um = pd.read_stata(str(base / "Usualmembers.dta"), convert_categoricals=False)
        heads = um[um['ishead'] == 1][['uqhh__id', 'Sex']].copy()
        heads.columns = ['uqhh__id', 'head_sex']
        # Sex: 1=male, 2=female (HIES 2019 standard coding)
        heads['female_headed'] = heads['head_sex'] == 2
    except (FileNotFoundError, KeyError):
        heads = pd.DataFrame({'uqhh__id': [], 'head_sex': [], 'female_headed': []})
        warnings.warn("Usualmembers.dta not found or missing Sex/ishead columns — gender analysis will be skipped")
    
    # 4. Merge everything
    m = inc.merge(elec_hh, on='uqhh__id', how='left')
    m = m.merge(gas_hh, on='uqhh__id', how='left')
    m = m.merge(kero_hh, on='uqhh__id', how='left')
    m = m.merge(total_exp, on='uqhh__id', how='left')
    m = m.merge(total_exp_m, on='uqhh__id', how='left')
    m = m.merge(solar_flag[['uqhh__id', 'has_solar']], on='uqhh__id', how='left')
    if len(heads) > 0:
        m = m.merge(heads[['uqhh__id', 'head_sex', 'female_headed']], on='uqhh__id', how='left')
        m['female_headed'] = m['female_headed'].fillna(False)
        m['head_sex'] = m['head_sex'].fillna(0)
    else:
        m['female_headed'] = False
        m['head_sex'] = 0
    
    # Fill NaN energy expenditures with 0 (HH that don't report these items)
    for col in ['elec_annual', 'elec_monthly', 'gas_annual', 'kerosene_annual']:
        m[col] = m[col].fillna(0)
    m['has_solar'] = m['has_solar'].fillna(False)
    
    # 5. Compute derived variables
    m['has_elec'] = m['elec_annual'] > 0
    m['energy_annual'] = m['elec_annual'] + m['gas_annual'] + m['kerosene_annual']
    
    # Shares (guard against zero expenditure)
    m['elec_share'] = np.where(
        m['total_annual_exp'] > 0,
        m['elec_annual'] / m['total_annual_exp'] * 100,
        0
    )
    m['energy_share'] = np.where(
        m['total_annual_exp'] > 0,
        m['energy_annual'] / m['total_annual_exp'] * 100,
        0
    )
    
    # Per-capita expenditure quintile (G-MO-02 fix: weighted quintiles)
    # Using unweighted pd.qcut assigns equal sample counts per quintile,
    # but HIES sampling weights mean each household represents a different
    # number of population units. Weighted quintiles ensure each quintile
    # represents 20% of the *population*, not 20% of the *sample*.
    m['pce'] = m['total_annual_exp'] / m['hhsize']
    m['exp_quintile'] = _weighted_qcut(m['pce'].values, m['wgt'].values, N_QUINTILES)
    
    # Geography label
    m['geo'] = m['maleatoll'].map({GEO_MALE: 'Male', GEO_ATOLL: 'Atoll'})
    
    return m


# =============================================================================
# BASELINE PROFILE COMPUTATION
# =============================================================================

def _compute_quintile_profiles(
    df: pd.DataFrame,
    quintile_col: str = 'exp_quintile'
) -> List[QuintileProfile]:
    """Compute weighted electricity expenditure profiles by quintile."""
    profiles = []
    for q in range(1, N_QUINTILES + 1):
        sub = df[df[quintile_col] == q]
        sub_e = sub[sub['has_elec']]
        wgt = sub['wgt']
        
        # Weighted means
        w_elec_share = np.average(sub['elec_share'], weights=wgt) if len(sub) > 0 else 0
        w_energy_share = np.average(sub['energy_share'], weights=wgt) if len(sub) > 0 else 0
        w_monthly_exp = np.average(sub['total_monthly_exp'], weights=wgt) if len(sub) > 0 else 0
        w_income = np.average(sub['totalIncome'], weights=wgt) if len(sub) > 0 else 0
        
        # Bill stats (among those with electricity)
        if len(sub_e) > 0:
            w_bill = np.average(sub_e['elec_monthly'], weights=sub_e['wgt'])
            # G-MO-01 fix: Use weighted median instead of unweighted pandas .median()
            med_bill = _weighted_median(sub_e['elec_monthly'].values, sub_e['wgt'].values)
        else:
            w_bill = 0
            med_bill = 0
        
        profiles.append(QuintileProfile(
            quintile=q,
            n_households=len(sub),
            n_with_electricity=len(sub_e),
            mean_monthly_bill_mvr=w_bill,
            median_monthly_bill_mvr=med_bill,
            mean_elec_share_pct=w_elec_share,
            mean_energy_share_pct=w_energy_share,
            mean_monthly_expenditure_mvr=w_monthly_exp,
            mean_annual_income_mvr=w_income,
        ))
    
    return profiles


def _compute_geo_profile(
    df: pd.DataFrame,
    geo_value: str,
) -> GeoProfile:
    """Compute weighted profile for a geography (Malé or Atoll)."""
    sub = df[df['geo'] == geo_value]
    sub_e = sub[sub['has_elec']]
    wgt = sub['wgt']
    
    w_elec_share = np.average(sub['elec_share'], weights=wgt) if len(sub) > 0 else 0
    w_bill = np.average(sub_e['elec_monthly'], weights=sub_e['wgt']) if len(sub_e) > 0 else 0
    w_income = np.average(sub['totalIncome'], weights=wgt) if len(sub) > 0 else 0
    
    # Quintile profiles within this geography
    quintile_profiles = _compute_quintile_profiles(sub)
    
    return GeoProfile(
        geography=geo_value,
        n_households=len(sub),
        n_with_electricity=len(sub_e),
        mean_monthly_bill_mvr=w_bill,
        mean_elec_share_pct=w_elec_share,
        mean_annual_income_mvr=w_income,
        quintile_profiles=quintile_profiles,
    )


def _compute_atoll_profiles(df: pd.DataFrame) -> List[AtollProfile]:
    """Compute weighted profile per atoll."""
    # Atoll-level poverty rates from World Bank Poverty Assessment 2022 (Table 1.6)
    # Source: "Maldives Poverty Assessment 2022", World Bank Group
    # These are fixed survey results, not model parameters
    POVERTY_RATES = {
        10: 0.9,    # Malé
        20: 12.5,   # HA (Haa Aliff)
        21: 12.9,   # HDh (Haa Daalu)
        22: 5.6,    # Sh (Shaviyani)
        24: 18.9,   # R (Raa)
        25: 1.7,    # B (Baa)
        26: None,    # Lh (Lhaviyani) — insufficient data in report
        27: 8.8,    # K (Kaafu)
        28: 14.2,   # AA (Alif Alif)
        29: 3.1,    # ADh (Alif Dhaal)
        30: 2.8,    # V (Vaavu)
        32: 7.1,    # F (Faafu)
        33: 2.7,    # Dh (Dhaalu)
        34: 14.4,   # Th (Thaa)
        35: 7.8,    # L (Laamu)
        36: 9.6,    # GA (Gaafu Alif)
        37: 15.6,   # GDh (Gaafu Daalu)
        39: 5.7,    # S (Addu/Seenu)
    }
    
    profiles = []
    for code in sorted(df['atoll_code'].dropna().unique()):
        sub = df[(df['atoll_code'] == code) & (df['has_elec'])]
        if len(sub) < 10:  # Skip atolls with too few observations
            continue
        
        w_share = np.average(sub['elec_share'], weights=sub['wgt'])
        w_bill = np.average(sub['elec_monthly'], weights=sub['wgt'])
        w_inc = np.average(sub['totalIncome'], weights=sub['wgt'])
        
        profiles.append(AtollProfile(
            atoll_code=int(code),
            atoll_name=str(sub['atoll'].iloc[0]),
            n_households=len(sub),
            mean_elec_share_pct=w_share,
            mean_monthly_bill_mvr=w_bill,
            mean_annual_income_mvr=w_inc,
            poverty_rate_pct=POVERTY_RATES.get(int(code)),
        ))
    
    # Sort by electricity burden (highest first)
    profiles.sort(key=lambda x: x.mean_elec_share_pct, reverse=True)
    return profiles


# =============================================================================
# GENDER-DISAGGREGATED ANALYSIS (P5)
# =============================================================================

def _compute_gender_profiles(df: pd.DataFrame) -> List[GenderProfile]:
    """
    Compute electricity expenditure profiles by sex of household head.
    
    Uses HIES 2019 Usualmembers.dta: Sex=1 (male), Sex=2 (female).
    Disaggregates burden, energy poverty, solar adoption, and quintile
    distributions by gender of household head.
    
    Reference: Clancy et al. (2012) "Gender equity in access to and benefits 
    from modern energy"; ESMAP (2020) "Gender and Energy".
    """
    if 'female_headed' not in df.columns or df['head_sex'].sum() == 0:
        return []
    
    profiles = []
    for is_female, label in [(False, 'male_headed'), (True, 'female_headed')]:
        sub = df[df['female_headed'] == is_female]
        if len(sub) == 0:
            continue
        
        wgt = sub['wgt']
        sub_e = sub[sub['has_elec']]
        total_n = len(df)
        
        # Weighted means
        w_bill = np.average(sub_e['elec_monthly'], weights=sub_e['wgt']) if len(sub_e) > 0 else 0
        w_elec_share = np.average(sub['elec_share'], weights=wgt) if len(sub) > 0 else 0
        w_energy_share = np.average(sub['energy_share'], weights=wgt) if len(sub) > 0 else 0
        w_income = np.average(sub['totalIncome'], weights=wgt) if len(sub) > 0 else 0
        
        # Energy poverty (>10% threshold, weighted)
        poor = sub['energy_share'] > 10.0
        total_weight = wgt.sum()
        poor_weight = sub.loc[poor, 'wgt'].sum()
        ep_pct = (poor_weight / total_weight * 100) if total_weight > 0 else 0
        
        # Solar adoption (G-MO-03 fix: use survey weights)
        solar_pct = (sub.loc[sub['has_solar'], 'wgt'].sum() / wgt.sum() * 100) if wgt.sum() > 0 else 0
        
        # Quintile-level electricity shares within this gender group
        q_shares = []
        for q in range(1, N_QUINTILES + 1):
            sq = sub[sub['exp_quintile'] == q]
            if len(sq) > 0:
                q_shares.append(float(np.average(sq['elec_share'], weights=sq['wgt'])))
            else:
                q_shares.append(0.0)
        
        profiles.append(GenderProfile(
            gender=label,
            n_households=len(sub),
            # G-LO-01 fix: use survey weights for population share
            share_of_total_pct=(wgt.sum() / df['wgt'].sum() * 100) if df['wgt'].sum() > 0 else 0,
            mean_monthly_bill_mvr=w_bill,
            mean_elec_share_pct=w_elec_share,
            mean_energy_share_pct=w_energy_share,
            mean_annual_income_mvr=w_income,
            energy_poverty_pct=ep_pct,
            has_solar_pct=solar_pct,
            quintile_elec_shares=q_shares,
        ))
    
    return profiles


def _simulate_gender_tariff_impacts(
    df: pd.DataFrame,
    scenario_lcoes: Dict[str, float],
    bau_lcoe: float,
) -> Dict[str, Dict[str, float]]:
    """
    Simulate electricity burden change by gender of household head under 
    each scenario's LCOE.
    
    Returns: {scenario: {male_headed: new_share%, female_headed: new_share%}}
    """
    if 'female_headed' not in df.columns or df['head_sex'].sum() == 0:
        return {}
    
    results = {}
    for scenario, lcoe in scenario_lcoes.items():
        if scenario == 'bau':
            continue
        
        lcoe_ratio = lcoe / bau_lcoe if bau_lcoe > 0 else 1.0
        
        gender_impacts = {}
        for is_female, label in [(False, 'male_headed'), (True, 'female_headed')]:
            sub = df[(df['female_headed'] == is_female) & (df['has_elec'])]
            if len(sub) == 0:
                gender_impacts[label] = 0.0
                continue
            
            w_bill = np.average(sub['elec_monthly'], weights=sub['wgt'])
            w_total = np.average(sub['total_monthly_exp'], weights=sub['wgt'])
            new_bill = w_bill * lcoe_ratio
            new_share = (new_bill / w_total * 100) if w_total > 0 else 0
            gender_impacts[label] = new_share
        
        results[scenario] = gender_impacts
    
    return results


def _simulate_gender_energy_poverty(
    df: pd.DataFrame,
    scenario_lcoes: Dict[str, float],
    bau_lcoe: float,
    threshold_pct: float = 10.0,
) -> Dict[str, Dict[str, float]]:
    """
    Simulate energy poverty headcount by gender under each scenario's LCOE.
    
    Returns: {scenario: {male_headed: poverty%, female_headed: poverty%}}
    """
    if 'female_headed' not in df.columns or df['head_sex'].sum() == 0:
        return {}
    
    results = {}
    for scenario, lcoe in scenario_lcoes.items():
        if scenario == 'bau':
            continue
        
        lcoe_ratio = lcoe / bau_lcoe if bau_lcoe > 0 else 1.0
        
        gender_poverty = {}
        for is_female, label in [(False, 'male_headed'), (True, 'female_headed')]:
            sub = df[df['female_headed'] == is_female]
            if len(sub) == 0:
                gender_poverty[label] = 0.0
                continue
            
            sim_elec = sub['elec_annual'] * lcoe_ratio
            sim_energy = sim_elec + sub['gas_annual'] + sub['kerosene_annual']
            sim_share = np.where(
                sub['total_annual_exp'] > 0,
                sim_energy / sub['total_annual_exp'] * 100,
                0
            )
            
            poor = sim_share > threshold_pct
            total_weight = sub['wgt'].sum()
            poor_weight = sub.loc[poor, 'wgt'].sum()
            gender_poverty[label] = (poor_weight / total_weight * 100) if total_weight > 0 else 0
        
        results[scenario] = gender_poverty
    
    return results


# =============================================================================
# SCENARIO TARIFF IMPACT SIMULATION
# =============================================================================

def _simulate_tariff_impacts(
    df: pd.DataFrame,
    scenario_lcoes: Dict[str, float],
    bau_lcoe: float,
    config: Config,
) -> Dict[str, List[TariffImpact]]:
    """
    Simulate electricity bill changes under each scenario.
    
    Methodology:
    - LCOE ratio = scenario_LCOE / BAU_LCOE
    - New bill = baseline bill × LCOE ratio
    - Assumes proportional passthrough (same % change applies to tariff)
    
    This is a first-order approximation. In reality, tariff structures 
    (block pricing, subsidies) mediate the passthrough, but LCOE ratio
    gives the economic cost change signal.
    """
    exchange_rate = config.economics.exchange_rate_mvr_usd
    
    impacts = {}
    for scenario, lcoe in scenario_lcoes.items():
        if scenario == 'bau':
            continue
        
        lcoe_ratio = lcoe / bau_lcoe if bau_lcoe > 0 else 1.0
        
        scenario_impacts = []
        for geo in ['Male', 'Atoll']:
            for q in range(1, N_QUINTILES + 1):
                sub = df[(df['geo'] == geo) & (df['exp_quintile'] == q) & (df['has_elec'])]
                if len(sub) == 0:
                    continue
                
                w_bill = np.average(sub['elec_monthly'], weights=sub['wgt'])
                w_share = np.average(sub['elec_share'], weights=sub['wgt'])
                w_total_monthly = np.average(sub['total_monthly_exp'], weights=sub['wgt'])
                
                new_bill = w_bill * lcoe_ratio
                change = new_bill - w_bill
                change_pct = (lcoe_ratio - 1) * 100
                
                # New electricity share
                # Monthly total expenditure stays same; only elec bill changes
                new_share = (new_bill / w_total_monthly * 100) if w_total_monthly > 0 else 0
                
                scenario_impacts.append(TariffImpact(
                    quintile=q,
                    geography=geo,
                    baseline_monthly_bill_mvr=w_bill,
                    new_monthly_bill_mvr=new_bill,
                    change_mvr=change,
                    change_pct=change_pct,
                    baseline_elec_share_pct=w_share,
                    new_elec_share_pct=new_share,
                ))
        
        impacts[scenario] = scenario_impacts
    
    return impacts


# =============================================================================
# ENERGY POVERTY ANALYSIS
# =============================================================================

def _compute_energy_poverty(
    df: pd.DataFrame,
    threshold_pct: float = 10.0,
) -> float:
    """
    Compute energy poverty headcount: share of HH spending >threshold% 
    of total expenditure on energy (electricity + gas + kerosene).
    
    Uses the international "10% rule" (Boardman 1991; Hills 2012).
    """
    poor = df['energy_share'] > threshold_pct
    # Weighted headcount
    total_weight = df['wgt'].sum()
    poor_weight = df.loc[poor, 'wgt'].sum()
    return (poor_weight / total_weight * 100) if total_weight > 0 else 0


def _simulate_energy_poverty_by_scenario(
    df: pd.DataFrame,
    scenario_lcoes: Dict[str, float],
    bau_lcoe: float,
    threshold_pct: float = 10.0,
) -> Dict[str, float]:
    """Simulate energy poverty headcount under each scenario's LCOE."""
    results = {}
    for scenario, lcoe in scenario_lcoes.items():
        if scenario == 'bau':
            continue
        
        lcoe_ratio = lcoe / bau_lcoe if bau_lcoe > 0 else 1.0
        
        # Simulate new energy expenditure (scale electricity by LCOE ratio)
        sim_elec = df['elec_annual'] * lcoe_ratio
        sim_energy = sim_elec + df['gas_annual'] + df['kerosene_annual']
        sim_share = np.where(
            df['total_annual_exp'] > 0,
            sim_energy / df['total_annual_exp'] * 100,
            0
        )
        
        poor = sim_share > threshold_pct
        total_weight = df['wgt'].sum()
        poor_weight = df.loc[poor, 'wgt'].sum()
        results[scenario] = (poor_weight / total_weight * 100) if total_weight > 0 else 0
    
    return results


# =============================================================================
# PROGRESSIVITY METRICS
# =============================================================================

def _compute_concentration_coefficient(df: pd.DataFrame) -> float:
    """
    Compute the concentration coefficient of electricity expenditure
    relative to total expenditure ranking.
    
    CC = 2 × cov(electricity_share, cumulative_pop_rank) / mean(electricity_share)
    
    A negative CC means electricity spending is concentrated among the poor
    (regressive consumption pattern). CC=0 means proportional.
    
    Reference: Kakwani (1977); O'Donnell et al. (2008) "Analyzing Health Equity".
    """
    # Sort by per-capita expenditure
    sorted_df = df.sort_values('pce').copy()
    
    # Weighted fractional rank
    cumwgt = sorted_df['wgt'].cumsum()
    total_wgt = sorted_df['wgt'].sum()
    sorted_df['frac_rank'] = cumwgt / total_wgt
    
    # Concentration coefficient
    mean_share = np.average(sorted_df['elec_share'], weights=sorted_df['wgt'])
    if mean_share == 0:
        return 0.0
    
    cov = np.average(
        sorted_df['elec_share'] * sorted_df['frac_rank'],
        weights=sorted_df['wgt']
    ) - mean_share * np.average(sorted_df['frac_rank'], weights=sorted_df['wgt'])
    
    cc = 2 * cov / mean_share
    return cc


def _compute_suits_index(
    df: pd.DataFrame,
    scenario_lcoe: float,
    bau_lcoe: float,
) -> float:
    """
    Compute the Suits index for a tariff change.
    
    Suits index measures the progressivity of a tax/tariff change:
    - S > 0: progressive (rich pay proportionally more)
    - S = 0: proportional
    - S < 0: regressive (poor pay proportionally more)
    
    Reference: Suits (1977) "Measurement of Tax Progressivity".
    
    For a tariff reduction (scenario LCOE < BAU LCOE), we measure the
    progressivity of the *benefit* (bill reduction).
    """
    lcoe_ratio = scenario_lcoe / bau_lcoe if bau_lcoe > 0 else 1.0
    
    # Bill change per household
    bill_change = df['elec_annual'] * (lcoe_ratio - 1)
    
    # Sort by per-capita expenditure
    sorted_df = df.sort_values('pce').copy()
    sorted_df['bill_change'] = bill_change.loc[sorted_df.index]
    
    # Weighted cumulative shares
    total_wgt = sorted_df['wgt'].sum()
    total_change = np.abs((sorted_df['bill_change'] * sorted_df['wgt']).sum())
    
    if total_change == 0:
        return 0.0
    
    cumwgt = sorted_df['wgt'].cumsum() / total_wgt
    cum_change = (np.abs(sorted_df['bill_change']) * sorted_df['wgt']).cumsum() / total_change
    
    # Suits index = 1 - 2 × area under Lorenz curve of bill changes
    # Approximate area under curve using trapezoidal rule
    # np.trapezoid (NumPy >=2.0) replaces deprecated np.trapz
    trapz_fn = getattr(np, 'trapezoid', None) or np.trapz
    area = trapz_fn(cum_change, cumwgt)
    suits = 1 - 2 * area
    
    return suits


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run_distributional_analysis(
    config: Config,
    cba_results: dict,
    scenario_summaries: dict,
) -> DistributionalResults:
    """
    Run the full distributional analysis.
    
    Args:
        config: Model configuration (from get_config())
        cba_results: Output from CBA (with npv_results containing LCOEs)
        scenario_summaries: Scenario summary dict (total costs, emissions, etc.)
    
    Returns:
        DistributionalResults with all analysis outputs
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required for distributional analysis. Install with: pip install pandas")
    
    print("\n" + "=" * 70)
    print("  DISTRIBUTIONAL ANALYSIS (L15)")
    print("  Data source: HIES 2019 (NBS Maldives)")
    print("=" * 70)
    
    # 1. Load HIES microdata
    print("  Loading HIES 2019 microdata...")
    df = _load_hies_data(config)
    print(f"    ✓ {len(df):,} households loaded ({df['has_elec'].sum():,} with electricity)")
    
    # 2. Extract scenario LCOEs from CBA results
    npv_results = cba_results.get('npv_results', {})
    scenario_lcoes = {}
    scenario_name_map = {
        'bau': 'bau',
        'full_integration': 'full_integration',
        'national_grid': 'national_grid',
        'islanded_green': 'islanded_green',
        'nearshore_solar': 'nearshore_solar',
        'maximum_re': 'maximum_re',
        'lng_transition': 'lng_transition',
    }
    for key, label in scenario_name_map.items():
        if key in npv_results and 'lcoe' in npv_results[key]:
            scenario_lcoes[label] = npv_results[key]['lcoe']
    
    if 'bau' not in scenario_lcoes:
        raise KeyError(
            "BAU LCOE not found in CBA results. "
            "Ensure 'bau' scenario was run and its LCOE is in npv_results."
        )
    bau_lcoe = scenario_lcoes['bau']
    print(f"    BAU LCOE: ${bau_lcoe:.3f}/kWh")
    for sc, lcoe in scenario_lcoes.items():
        if sc != 'bau':
            ratio = lcoe / bau_lcoe if bau_lcoe > 0 else 0
            print(f"    {sc}: ${lcoe:.3f}/kWh ({ratio:.1%} of BAU)")
    
    # 3. Compute baseline profiles
    print("  Computing baseline expenditure profiles...")
    quintile_profiles = _compute_quintile_profiles(df)
    male_profile = _compute_geo_profile(df, 'Male')
    atoll_profile = _compute_geo_profile(df, 'Atoll')
    atoll_profiles = _compute_atoll_profiles(df)
    
    # National statistics
    wgt = df['wgt']
    national_elec_share = np.average(df['elec_share'], weights=wgt)
    national_energy_share = np.average(df['energy_share'], weights=wgt)
    national_bill = np.average(df.loc[df['has_elec'], 'elec_monthly'], 
                                weights=df.loc[df['has_elec'], 'wgt'])
    solar_pct = df.loc[df['has_solar'], 'wgt'].sum() / wgt.sum() * 100
    elec_rate = df.loc[df['has_elec'], 'wgt'].sum() / wgt.sum() * 100
    
    print(f"    National electricity share: {national_elec_share:.1f}% of expenditure")
    print(f"    National energy share: {national_energy_share:.1f}%")
    print(f"    Electrification rate: {elec_rate:.1f}%")
    print(f"    Solar adoption: {solar_pct:.1f}%")
    
    # 4. Tariff impact simulation
    print("  Simulating tariff impacts by scenario...")
    tariff_impacts = _simulate_tariff_impacts(df, scenario_lcoes, bau_lcoe, config)
    
    for scenario, impacts in tariff_impacts.items():
        q1_atoll = [ti for ti in impacts if ti.quintile == 1 and ti.geography == 'Atoll']
        q5_male = [ti for ti in impacts if ti.quintile == 5 and ti.geography == 'Male']
        if q1_atoll:
            print(f"    {scenario}: Atoll Q1 bill change = {q1_atoll[0].change_pct:+.1f}%")
        if q5_male:
            print(f"    {scenario}: Male Q5 bill change = {q5_male[0].change_pct:+.1f}%")
    
    # 5. Energy poverty
    print("  Computing energy poverty headcounts...")
    energy_poverty_baseline = _compute_energy_poverty(df)
    energy_poverty_scenarios = _simulate_energy_poverty_by_scenario(
        df, scenario_lcoes, bau_lcoe
    )
    
    print(f"    Baseline energy poverty (>10% threshold): {energy_poverty_baseline:.1f}%")
    for sc, pov in energy_poverty_scenarios.items():
        print(f"    {sc}: {pov:.1f}%")
    
    # 6. Progressivity metrics
    print("  Computing progressivity metrics...")
    concentration_coeff = _compute_concentration_coefficient(df)
    suits_indices = {}
    for sc, lcoe in scenario_lcoes.items():
        if sc != 'bau':
            suits_indices[sc] = _compute_suits_index(df, lcoe, bau_lcoe)
    
    print(f"    Concentration coefficient: {concentration_coeff:.4f}")
    for sc, si in suits_indices.items():
        label = "progressive" if si > 0 else "regressive"
        print(f"    Suits index ({sc}): {si:.4f} ({label})")
    
    # 7. Gender-disaggregated analysis (P5)
    print("  Computing gender-disaggregated profiles (P5)...")
    gender_profiles = _compute_gender_profiles(df)
    gender_tariff = _simulate_gender_tariff_impacts(df, scenario_lcoes, bau_lcoe)
    gender_poverty = _simulate_gender_energy_poverty(df, scenario_lcoes, bau_lcoe)
    
    if gender_profiles:
        for gp in gender_profiles:
            print(f"    {gp.gender}: {gp.n_households:,} HH ({gp.share_of_total_pct:.1f}%), "
                  f"burden {gp.mean_elec_share_pct:.1f}%, energy poverty {gp.energy_poverty_pct:.1f}%")
    else:
        print("    ⚠ Gender data not available — skipping")
    
    # 8. Build results
    results = DistributionalResults(
        national_mean_elec_share_pct=national_elec_share,
        national_mean_energy_share_pct=national_energy_share,
        national_mean_monthly_bill_mvr=national_bill,
        n_households_total=len(df),
        n_households_with_electricity=int(df['has_elec'].sum()),
        electrification_rate_pct=elec_rate,
        solar_adoption_pct=solar_pct,
        quintile_profiles=quintile_profiles,
        male_profile=male_profile,
        atoll_profile=atoll_profile,
        atoll_profiles=atoll_profiles,
        gender_profiles=gender_profiles,
        gender_tariff_impacts=gender_tariff,
        gender_energy_poverty=gender_poverty,
        scenario_tariff_impacts=tariff_impacts,
        energy_poverty_baseline_pct=energy_poverty_baseline,
        energy_poverty_by_scenario=energy_poverty_scenarios,
        concentration_coefficient=concentration_coeff,
        suits_index_by_scenario=suits_indices,
    )
    
    print("  ✓ Distributional analysis complete")
    return results


def print_distributional_summary(results: DistributionalResults) -> None:
    """Print a formatted summary of distributional analysis results."""
    print("\n" + "=" * 70)
    print("  DISTRIBUTIONAL IMPACT SUMMARY")
    print("=" * 70)
    
    # Baseline burden
    print("\n  BASELINE ELECTRICITY BURDEN (HIES 2019)")
    print("  " + "-" * 55)
    print(f"  {'Quintile':>8} {'Bill (MVR)':>12} {'Elec %':>8} {'Energy %':>10} {'N':>6}")
    for qp in results.quintile_profiles:
        print(f"  {'Q' + str(qp.quintile):>8} {qp.mean_monthly_bill_mvr:>12,.0f} "
              f"{qp.mean_elec_share_pct:>7.1f}% {qp.mean_energy_share_pct:>9.1f}% "
              f"{qp.n_households:>6}")
    
    ratio = (results.quintile_profiles[0].mean_elec_share_pct / 
             results.quintile_profiles[-1].mean_elec_share_pct)
    print(f"\n  Q1/Q5 burden ratio: {ratio:.1f}× (electricity is regressive)")
    
    # Geographic gap
    print(f"\n  GEOGRAPHIC DISPARITY")
    print("  " + "-" * 55)
    print(f"  Malé:  {results.male_profile.mean_elec_share_pct:.1f}% of expenditure "
          f"(bill: {results.male_profile.mean_monthly_bill_mvr:,.0f} MVR)")
    print(f"  Atoll: {results.atoll_profile.mean_elec_share_pct:.1f}% of expenditure "
          f"(bill: {results.atoll_profile.mean_monthly_bill_mvr:,.0f} MVR)")
    geo_ratio = results.atoll_profile.mean_elec_share_pct / results.male_profile.mean_elec_share_pct
    print(f"  Atoll/Malé burden ratio: {geo_ratio:.1f}×")
    
    # Top 5 burdened atolls
    print(f"\n  MOST BURDENED ATOLLS (electricity share of expenditure)")
    print("  " + "-" * 55)
    for ap in results.atoll_profiles[:5]:
        pov_str = f" (poverty: {ap.poverty_rate_pct:.1f}%)" if ap.poverty_rate_pct is not None else ""
        print(f"  {ap.atoll_name:>4}: {ap.mean_elec_share_pct:.1f}% "
              f"(bill: {ap.mean_monthly_bill_mvr:,.0f} MVR){pov_str}")
    
    # Scenario impacts
    print(f"\n  SCENARIO TARIFF IMPACT (bill change vs BAU)")
    print("  " + "-" * 55)
    for scenario, impacts in results.scenario_tariff_impacts.items():
        q1_impacts = [ti for ti in impacts if ti.quintile == 1]
        if q1_impacts:
            avg_change = np.mean([ti.change_pct for ti in q1_impacts])
            print(f"  {scenario:>25}: Q1 avg bill change = {avg_change:+.1f}%")
    
    # Energy poverty
    print(f"\n  ENERGY POVERTY (>10% of expenditure on energy)")
    print("  " + "-" * 55)
    print(f"  Baseline: {results.energy_poverty_baseline_pct:.1f}%")
    for sc, pov in results.energy_poverty_by_scenario.items():
        change = pov - results.energy_poverty_baseline_pct
        print(f"  {sc:>25}: {pov:.1f}% ({change:+.1f}pp)")
    
    # Gender-disaggregated analysis (P5)
    if results.gender_profiles:
        print(f"\n  GENDER OF HOUSEHOLD HEAD (P5)")
        print("  " + "-" * 55)
        print(f"  {'Group':>16} {'N':>6} {'Share':>7} {'Bill':>10} {'Burden':>8} {'Poverty':>9} {'Solar':>7}")
        for gp in results.gender_profiles:
            label = 'Male-headed' if gp.gender == 'male_headed' else 'Female-headed'
            print(f"  {label:>16} {gp.n_households:>6} {gp.share_of_total_pct:>6.1f}% "
                  f"{gp.mean_monthly_bill_mvr:>9,.0f} {gp.mean_elec_share_pct:>7.1f}% "
                  f"{gp.energy_poverty_pct:>8.1f}% {gp.has_solar_pct:>6.1f}%")
        
        # Gender gap in burden
        male = next((gp for gp in results.gender_profiles if gp.gender == 'male_headed'), None)
        female = next((gp for gp in results.gender_profiles if gp.gender == 'female_headed'), None)
        if male and female:
            gap = female.mean_elec_share_pct - male.mean_elec_share_pct
            income_ratio = female.mean_annual_income_mvr / male.mean_annual_income_mvr if male.mean_annual_income_mvr > 0 else 0
            print(f"\n  Female/Male burden gap: {gap:+.2f}pp")
            print(f"  Female/Male income ratio: {income_ratio:.2f}")
            print(f"  Female/Male energy poverty gap: {female.energy_poverty_pct - male.energy_poverty_pct:+.1f}pp")
        
        # Gender energy poverty by scenario
        if results.gender_energy_poverty:
            print(f"\n  ENERGY POVERTY BY GENDER & SCENARIO")
            print("  " + "-" * 55)
            for sc, gp in results.gender_energy_poverty.items():
                m_pov = gp.get('male_headed', 0)
                f_pov = gp.get('female_headed', 0)
                print(f"  {sc:>25}: Male {m_pov:.1f}% | Female {f_pov:.1f}% (gap: {f_pov - m_pov:+.1f}pp)")
    
    print()


def save_distributional_results(results: DistributionalResults, output_dir: str) -> None:
    """Save distributional analysis results to JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    filepath = output_path / "distributional_results.json"
    
    class _NumpyEncoder(json.JSONEncoder):
        """Handle numpy types that aren't natively JSON serializable."""
        def default(self, obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super().default(obj)
    
    with open(filepath, "w") as f:
        json.dump(results.to_dict(), f, indent=2, cls=_NumpyEncoder)
    
    print(f"  Distributional results saved to {filepath}")
