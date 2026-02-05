"""
Configuration Module
====================

Central configuration for all model parameters, paths, and assumptions.
All values can be overridden by loading from parameters.yaml.

Note: Values marked with # ESTIMATE need validation from experts/data sources.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import yaml
import csv


# =============================================================================
# TIME HORIZON
# =============================================================================

BASE_YEAR = 2026
END_YEAR_20 = 2046  # 20-year horizon
END_YEAR_30 = 2056  # 30-year horizon (default)
END_YEAR_50 = 2076  # 50-year horizon

# Default to 30-year horizon
END_YEAR = END_YEAR_30
TIME_HORIZON = list(range(BASE_YEAR, END_YEAR + 1))  # 31 years

# Available horizons
TIME_HORIZONS = {
    20: list(range(BASE_YEAR, END_YEAR_20 + 1)),
    30: list(range(BASE_YEAR, END_YEAR_30 + 1)),
    50: list(range(BASE_YEAR, END_YEAR_50 + 1)),
}


# =============================================================================
# PATHS
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT
RESULTS_DIR = PROJECT_ROOT / "Results"
CONFIG_DIR = PROJECT_ROOT / "config"


# =============================================================================
# SCENARIO DEFINITIONS
# =============================================================================

SCENARIOS = {
    "status_quo": {
        "name": "BAU (Diesel)",
        "description": "Minimal RE growth, ~7% solar maintained, no new grid investments",
        "demand_growth_rate": 0.035,  # 3.5%/year
    },
    "green_transition": {
        "name": "National Grid", 
        "description": "Inter-island grid + aggressive RE deployment (70% by 2050)",
        "demand_growth_rate": 0.028,  # 2.8%/year (efficiency gains)
        "re_target_2028": 0.33,
        "re_target_2050": 0.70,
    },
    "one_grid": {
        "name": "Full Integration",
        "description": "India cable + inter-island grid + RE deployment",
        "demand_growth_rate": 0.038,  # 3.8%/year (induced demand)
        "cable_online_year": 2030,  # ESTIMATE - need OSOWOG data
    },
}


# =============================================================================
# BASELINE DEMAND (2024)
# =============================================================================

@dataclass
class DemandConfig:
    """Electricity demand parameters."""
    
    base_year: int = 2026
    base_demand_gwh: float = 1100.0  # IRENA 2022 (1025 GWh) + 5% growth
    base_peak_mw: float = 200.0  # STELCO data + growth
    
    # Growth rates by scenario (can be overridden)
    growth_rates: Dict[str, float] = field(default_factory=lambda: {
        "status_quo": 0.05,  # 5%/yr - UNDP/ISA/STELCO
        "green_transition": 0.04,  # 4%/yr with efficiency gains
        "one_grid": 0.055,  # 5.5%/yr induced demand
    })
    
    # Load factor (peak to average demand ratio)
    load_factor: float = 0.63  # Calculated: 1100 GWh / (200 MW * 8760h)
    
    # Induced demand elasticity (for One Grid lower prices)
    price_elasticity: float = -0.3


# =============================================================================
# TECHNOLOGY COSTS
# =============================================================================

@dataclass
class TechnologyCosts:
    """Capital and operating costs for all technologies."""
    
    # Solar PV (utility scale) - IRENA RPGC 2024
    solar_pv_capex: float = 750.0  # USD/kW - Global <$600, +25-50% island premium
    solar_pv_opex_pct: float = 0.015  # 1.5% of CAPEX/year
    solar_pv_lifetime: int = 30  # years - Industry standard 2025
    solar_pv_degradation: float = 0.005  # 0.5%/year
    solar_pv_capacity_factor: float = 0.175  # World Bank/Solargis Maldives Atlas
    
    # Solar PV cost decline trajectory
    solar_pv_cost_decline: float = 0.04  # 4%/year - IRENA learning rates
    
    # Battery storage (Li-ion LFP) - BNEF Dec 2025
    battery_capex: float = 150.0  # USD/kWh - Pack $70 + system $117-125 + island premium
    battery_opex: float = 5.0  # USD/kWh/year - Ember LCOS model 2025
    battery_lifetime: int = 15  # years - LFP 6000+ cycles
    battery_efficiency: float = 0.88  # round-trip - Modern LFP 87-92%
    battery_cost_decline: float = 0.06  # 6%/year - BNEF/NREL (slowing)
    
    # Diesel generators
    diesel_gen_capex: float = 800.0  # USD/kW - Industry estimates
    diesel_gen_opex_kwh: float = 0.025  # USD/kWh O&M
    diesel_gen_lifetime: int = 20  # years
    diesel_gen_efficiency: float = 0.35  # thermal efficiency
    
    # Undersea HVDC cable (One Grid) - Recent benchmarks
    cable_capex_per_km: float = 3_000_000.0  # USD/km - Deep ocean crossing
    cable_length_km: float = 700.0  # Direct ~600 km + 15-20% routing
    cable_capacity_mw: float = 200.0  # OSOWOG proposal
    cable_opex_pct: float = 0.02  # 2% of CAPEX/year
    cable_lifetime: int = 40  # years
    cable_losses_pct: float = 0.03  # 3% transmission losses
    
    # Inter-island MV submarine cable
    inter_island_capex_per_km: float = 1_500_000.0  # USD/km - Reef navigation complexity
    
    # Distribution infrastructure
    mv_line_capex_per_km: float = 20_000.0  # USD/km
    lv_line_capex_per_km: float = 12_000.0  # USD/km
    transformer_capex: float = 30_000.0  # USD/unit (average)
    td_losses_pct: float = 0.12  # 12% T&D losses
    
    # Connection costs
    connection_cost_per_hh: float = 150.0  # USD/household


# =============================================================================
# FUEL PARAMETERS
# =============================================================================

@dataclass
class FuelConfig:
    """Diesel fuel parameters."""
    
    price_2026: float = 0.90  # USD/liter - STO retail pricing 2024-25
    price_escalation: float = 0.02  # 2%/year real escalation
    
    # Generator efficiency
    kwh_per_liter: float = 3.5  # kWh generated per liter diesel
    
    # Emissions
    emission_factor_kg_co2_per_kwh: float = 0.72  # kgCO2/kWh - IPCC 2006
    emission_factor_kg_co2_per_liter: float = 2.68  # kgCO2/liter diesel
    
    def get_price(self, year: int) -> float:
        """Get diesel price for a given year with escalation."""
        years_from_base = year - 2026
        return self.price_2026 * ((1 + self.price_escalation) ** years_from_base)


# =============================================================================
# POWER PURCHASE AGREEMENT (ONE GRID)
# =============================================================================

@dataclass
class PPAConfig:
    """Power Purchase Agreement parameters for One Grid scenario."""
    
    import_price_2030: float = 0.06  # USD/kWh - India wholesale + cable premium
    transmission_charge: float = 0.01  # USD/kWh - cross-border wheeling
    price_escalation: float = 0.01  # 1%/year
    minimum_offtake_pct: float = 0.70  # 70% of cable capacity
    contract_duration: int = 25  # years
    cable_online_year: int = 2032  # Realistic timeline (5-7 years from decision)
    
    # India grid emission factor
    india_grid_emission_factor: float = 0.70  # kgCO2/kWh - improving over time
    india_grid_emission_decline: float = 0.02  # 2%/year improvement
    
    def get_price(self, year: int) -> float:
        """Get total import price (wholesale + transmission) for a given year."""
        if year < self.cable_online_year:
            return None  # Cable not online yet
        years_from_start = year - self.cable_online_year
        base_price = self.import_price_2030 + self.transmission_charge
        return base_price * ((1 + self.price_escalation) ** years_from_start)
    
    def get_india_emission_factor(self, year: int) -> float:
        """Get India grid emission factor for a given year."""
        years_from_2024 = year - 2024
        return self.india_grid_emission_factor * ((1 - self.india_grid_emission_decline) ** years_from_2024)


# =============================================================================
# ECONOMIC PARAMETERS
# =============================================================================

@dataclass
class EconomicsConfig:
    """Economic and CBA parameters."""
    
    # Discount rate
    discount_rate: float = 0.06  # 6% real - ADB standard for SIDS
    discount_rate_low: float = 0.03  # sensitivity
    discount_rate_high: float = 0.10  # sensitivity
    
    # Social cost of carbon - EPA 2023; Rennert et al. 2022 Nature
    social_cost_carbon: float = 190.0  # USD/tCO2 - Central estimate at 2% discount
    scc_low: float = 80.0  # sensitivity (old estimate)
    scc_high: float = 300.0  # sensitivity
    
    # Value of lost load (reliability)
    voll: float = 5.0  # USD/kWh - Island tourism-dependent economy
    
    # Health co-benefits from reduced diesel
    health_benefit_per_kwh_diesel: float = 0.01  # USD/kWh - ESTIMATE
    
    # Currency
    exchange_rate_mvr_usd: float = 15.4  # MVR per USD


# =============================================================================
# CURRENT SYSTEM STATE (2024)
# =============================================================================

@dataclass 
class CurrentSystemConfig:
    """
    Current electricity system parameters (2024 baseline from GoM Energy Roadmap).
    
    Data sources:
    - Total capacity: 600 MW (GoM Energy Roadmap Nov 2024)
    - Solar PV: 68.5 MW (+164 MW under construction Dec 2025)
    - Battery: 8 MWh installed; 80 MWh under ADB/WB contracts
    - Generation mix: 93% diesel, 6% solar (IRENA/Ember 2023)
    """
    
    # Generation capacity (2024 baseline)
    total_capacity_mw: float = 600.0  # GoM Energy Roadmap Nov 2024
    diesel_capacity_mw: float = 531.5  # Derived (600 - 68.5)
    solar_capacity_mw: float = 68.5  # +164 MW in pipeline
    battery_capacity_mwh: float = 8.0  # 80 MWh under contract
    
    # Generation mix (2024)
    diesel_share: float = 0.93  # IRENA/Ember 2023
    re_share: float = 0.06  # GoM Energy Roadmap
    
    # Consumption
    total_demand_gwh: float = 1100.0  # IRENA 2022 + growth
    
    # Reliability
    saidi_minutes: float = 200.0  # ESTIMATE - minutes/year
    saifi_interruptions: float = 10.0  # ESTIMATE - interruptions/year
    
    # Number of connections
    total_connections: int = 160_000  # ESTIMATE
    
    # Population
    population_2026: int = 545_000  # ESTIMATE
    household_size: float = 3.5  # people per household


# =============================================================================
# GREEN TRANSITION DEPLOYMENT SCHEDULE
# =============================================================================

@dataclass
class GreenTransitionConfig:
    """Solar PV and battery deployment schedule for Green Transition."""
    
    # Target RE shares by year (realistic trajectory from parameter_review_summary.md)
    re_targets: Dict[int, float] = field(default_factory=lambda: {
        2024: 0.06,  # Baseline
        2026: 0.10,  # 90 MW pipeline contributes
        2028: 0.20,  # Adjusted from GoM 33% target
        2030: 0.33,  # GoM target (delayed)
        2035: 0.42,
        2040: 0.50,  # Gradual increase with storage
        2050: 0.70,  # Achievable with mature storage
        2056: 0.75,  # 30-year horizon
        2076: 0.80,  # 50-year horizon
    })
    
    # Battery storage as % of solar capacity (MWh per MW solar)
    battery_ratio: float = 3.0  # 3 MWh storage per MW solar - modern BESS sizing
    
    # Inter-island grid development
    inter_island_grid: bool = True
    inter_island_km: float = 200.0  # km of submarine cable
    inter_island_build_end: int = 2030  # 3-year phased construction


# =============================================================================
# ONE GRID CONFIGURATION
# =============================================================================

@dataclass
class OneGridConfig:
    """Undersea cable and import configuration for One Grid scenario."""
    
    # Cable parameters
    cable_online_year: int = 2032  # Realistic: 5-7 years from decision
    cable_capacity_mw: float = 200.0  # OSOWOG proposal
    cable_length_km: float = 700.0  # Direct ~600 km + 15-20% routing
    cable_capex_total: float = None  # Calculated
    
    # GoM cost share
    gom_share_pct: float = 0.30  # 30% Maldives / 70% India
    
    # Complementary domestic RE
    domestic_re_target_2050: float = 0.30  # 30% from domestic solar
    
    def __post_init__(self):
        if self.cable_capex_total is None:
            self.cable_capex_total = self.cable_length_km * 3_000_000  # $3M/km


# =============================================================================
# SENSITIVITY ANALYSIS RANGES
# =============================================================================

SENSITIVITY_PARAMS = {
    "discount_rate": {"low": 0.03, "base": 0.06, "high": 0.10},
    "diesel_price": {"low": 0.70, "base": 0.90, "high": 1.20},
    "import_price": {"low": 0.05, "base": 0.07, "high": 0.10},
    "solar_capex": {"low": 600, "base": 750, "high": 1000},
    "battery_capex": {"low": 100, "base": 150, "high": 250},
    "cable_capex_per_km": {"low": 2_000_000, "base": 3_000_000, "high": 4_000_000},
    "social_cost_carbon": {"low": 80, "base": 190, "high": 300},
    "demand_growth": {"low": 0.035, "base": 0.05, "high": 0.065},
}


# =============================================================================
# MAIN CONFIG CLASS
# =============================================================================

@dataclass
class Config:
    """Main configuration container."""
    
    # Time
    base_year: int = BASE_YEAR
    end_year: int = END_YEAR
    time_horizon: List[int] = field(default_factory=lambda: TIME_HORIZON)
    
    # Sub-configs
    demand: DemandConfig = field(default_factory=DemandConfig)
    technology: TechnologyCosts = field(default_factory=TechnologyCosts)
    fuel: FuelConfig = field(default_factory=FuelConfig)
    ppa: PPAConfig = field(default_factory=PPAConfig)
    economics: EconomicsConfig = field(default_factory=EconomicsConfig)
    current_system: CurrentSystemConfig = field(default_factory=CurrentSystemConfig)
    green_transition: GreenTransitionConfig = field(default_factory=GreenTransitionConfig)
    one_grid: OneGridConfig = field(default_factory=OneGridConfig)
    
    # Paths
    project_root: Path = PROJECT_ROOT
    data_dir: Path = DATA_DIR
    results_dir: Path = RESULTS_DIR
    
    @classmethod
    def load(cls, yaml_path: Path = None) -> "Config":
        """Load configuration from YAML file, with defaults."""
        config = cls()
        
        if yaml_path and yaml_path.exists():
            with open(yaml_path, "r") as f:
                overrides = yaml.safe_load(f)
            # TODO: Apply overrides to config
            
        return config
    
    def save(self, yaml_path: Path) -> None:
        """Save current configuration to YAML file."""
        # TODO: Implement serialization
        pass
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of warnings."""
        warnings = []
        
        if self.demand.base_demand_gwh <= 0:
            warnings.append("Base demand must be positive")
            
        if self.economics.discount_rate <= 0 or self.economics.discount_rate > 0.20:
            warnings.append("Discount rate should be between 0 and 20%")
            
        if self.fuel.price_2026 <= 0:
            warnings.append("Diesel price must be positive")
            
        return warnings


# =============================================================================
# DEFAULT CONFIG INSTANCE
# =============================================================================

# Path to parameters CSV
PARAMETERS_CSV = Path(__file__).parent / "parameters.csv"


def load_parameters_from_csv(csv_path: Path = PARAMETERS_CSV) -> Dict[str, Dict[str, any]]:
    """
    Load parameters from CSV file.
    
    Returns dict organized by Category -> Parameter -> Value
    """
    params = {}
    
    if not csv_path.exists():
        print(f"Warning: Parameters CSV not found at {csv_path}")
        return params
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip comment rows
            if not row.get('Category') or row['Category'].startswith('#'):
                continue
            
            category = row['Category'].strip()
            param = row['Parameter'].strip()
            value_str = row['Value'].strip()
            
            # Parse value
            try:
                # Try float first
                if '.' in value_str:
                    value = float(value_str)
                else:
                    value = int(value_str)
            except ValueError:
                value = value_str  # Keep as string
            
            if category not in params:
                params[category] = {}
            params[category][param] = value
    
    return params


def get_config(load_from_csv: bool = True) -> Config:
    """
    Get configuration instance.
    
    Args:
        load_from_csv: If True, override defaults with values from parameters.csv
    """
    config = Config()
    
    if load_from_csv and PARAMETERS_CSV.exists():
        params = load_parameters_from_csv()
        
        # Apply CSV values to config
        if 'Current System' in params:
            cs = params['Current System']
            if 'Total Installed Capacity' in cs:
                config.current_system.total_capacity_mw = float(cs['Total Installed Capacity'])
            if 'Diesel Capacity' in cs:
                config.current_system.diesel_capacity_mw = float(cs['Diesel Capacity'])
            if 'Solar PV Capacity' in cs:
                config.current_system.solar_capacity_mw = float(cs['Solar PV Capacity'])
            if 'Battery Storage' in cs:
                config.current_system.battery_capacity_mwh = float(cs['Battery Storage'])
            if 'Diesel Generation Share' in cs:
                config.current_system.diesel_share = float(cs['Diesel Generation Share'])
            if 'RE Generation Share' in cs:
                config.current_system.re_share = float(cs['RE Generation Share'])
        
        if 'Demand' in params:
            d = params['Demand']
            if 'Base Demand 2026' in d:
                config.demand.base_demand_gwh = float(d['Base Demand 2026'])
            if 'Base Peak 2026' in d:
                config.demand.base_peak_mw = float(d['Base Peak 2026'])
            if 'Load Factor' in d:
                config.demand.load_factor = float(d['Load Factor'])
            if 'Growth Rate - BAU' in d:
                config.demand.growth_rates['status_quo'] = float(d['Growth Rate - BAU'])
            if 'Growth Rate - National Grid' in d:
                config.demand.growth_rates['green_transition'] = float(d['Growth Rate - National Grid'])
            if 'Growth Rate - Full Integration' in d:
                config.demand.growth_rates['one_grid'] = float(d['Growth Rate - Full Integration'])
        
        if 'Fuel' in params:
            f = params['Fuel']
            if 'Diesel Price 2026' in f:
                config.fuel.price_2026 = float(f['Diesel Price 2026'])
            if 'Diesel Price Escalation' in f:
                config.fuel.price_escalation = float(f['Diesel Price Escalation'])
            if 'Fuel Efficiency' in f:
                config.fuel.kwh_per_liter = float(f['Fuel Efficiency'])
            if 'CO2 Emission Factor' in f:
                config.fuel.emission_factor_kg_co2_per_kwh = float(f['CO2 Emission Factor'])
        
        if 'Solar' in params:
            s = params['Solar']
            if 'CAPEX 2026' in s:
                config.technology.solar_pv_capex = float(s['CAPEX 2026'])
            if 'CAPEX Annual Decline' in s:
                config.technology.solar_pv_cost_decline = float(s['CAPEX Annual Decline'])
            if 'OPEX (% of CAPEX)' in s:
                config.technology.solar_pv_opex_pct = float(s['OPEX (% of CAPEX)'])
            if 'Capacity Factor' in s:
                config.technology.solar_pv_capacity_factor = float(s['Capacity Factor'])
        
        if 'Battery' in params:
            b = params['Battery']
            if 'CAPEX 2026' in b:
                config.technology.battery_capex = float(b['CAPEX 2026'])
            if 'CAPEX Annual Decline' in b:
                config.technology.battery_cost_decline = float(b['CAPEX Annual Decline'])
            if 'Round-trip Efficiency' in b:
                config.technology.battery_efficiency = float(b['Round-trip Efficiency'])
        
        if 'Cable' in params:
            c = params['Cable']
            if 'Length to India' in c:
                config.one_grid.cable_length_km = float(c['Length to India'])
            if 'Capacity' in c:
                config.one_grid.cable_capacity_mw = float(c['Capacity'])
            if 'GoM Cost Share' in c:
                config.one_grid.gom_share_pct = float(c['GoM Cost Share'])
            if 'Online Year' in c:
                config.one_grid.cable_online_year = int(c['Online Year'])
            if 'CAPEX per km' in c:
                config.technology.cable_capex_per_km = float(c['CAPEX per km'])
        
        if 'Economics' in params:
            e = params['Economics']
            if 'Discount Rate' in e:
                config.economics.discount_rate = float(e['Discount Rate'])
            if 'Social Cost of Carbon' in e:
                config.economics.social_cost_carbon = float(e['Social Cost of Carbon'])
            if 'Value of Lost Load' in e:
                config.economics.voll = float(e['Value of Lost Load'])
        
        if 'PPA' in params:
            p = params['PPA']
            if 'Import Price 2030' in p:
                config.ppa.import_price_2030 = float(p['Import Price 2030'])
            if 'Transmission Charge' in p:
                config.ppa.transmission_charge = float(p['Transmission Charge'])
            if 'Price Escalation' in p:
                config.ppa.price_escalation = float(p['Price Escalation'])
        
        if 'Islanded' in params:
            i = params['Islanded']
            # These could be used by IslandedGreenScenario
            pass
    
    return config


def print_loaded_parameters():
    """Print all parameters loaded from CSV for verification."""
    params = load_parameters_from_csv()
    print("\n" + "="*60)
    print("PARAMETERS LOADED FROM CSV")
    print("="*60)
    for category, values in params.items():
        print(f"\n[{category}]")
        for param, value in values.items():
            print(f"  {param}: {value}")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Test configuration
    print("Testing parameter loading from CSV...")
    
    # Print what's in the CSV
    print_loaded_parameters()
    
    # Load config with CSV values
    config = get_config(load_from_csv=True)
    
    print("\nConfig values after loading:")
    print(f"  Time horizon: {config.base_year} - {config.end_year}")
    print(f"  Available horizons: 20yr (2026-2046), 30yr (2026-2056), 50yr (2026-2076)")
    print(f"  Base demand: {config.demand.base_demand_gwh} GWh")
    print(f"  Current solar capacity: {config.current_system.solar_capacity_mw} MW")
    print(f"  Current RE share: {config.current_system.re_share:.1%}")
    print(f"  Diesel price 2026: ${config.fuel.price_2026}/L")
    print(f"  Diesel price 2036: ${config.fuel.get_price(2036):.2f}/L")
    print(f"  Discount rate: {config.economics.discount_rate:.1%}")
    print(f"  Solar CAPEX: ${config.technology.solar_pv_capex}/kW")
    print(f"  Cable length: {config.one_grid.cable_length_km} km")
    
    warnings = config.validate()
    if warnings:
        print(f"\nWarnings: {warnings}")
    else:
        print("\n✓ Configuration valid!")
