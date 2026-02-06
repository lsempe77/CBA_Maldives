"""
Sensitivity Analysis
====================

One-way, two-way, and Monte Carlo sensitivity analysis for CBA results.

This module provides:
- One-way sensitivity (tornado diagrams)
- Switching value calculations
- Monte Carlo simulation
- Parameter impact rankings
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
import numpy as np
from copy import deepcopy

from ..config import Config, get_config, SENSITIVITY_PARAMS
from ..scenarios import ScenarioResults
from .npv_calculator import CBACalculator, CBAComparison, NPVResult


@dataclass
class SensitivityParameter:
    """
    Definition of a parameter for sensitivity analysis.
    """
    name: str
    base_value: float
    low_value: float
    high_value: float
    unit: str = ""
    description: str = ""
    
    @property
    def range_pct(self) -> Tuple[float, float]:
        """Return low/high as percentage change from base."""
        low_pct = (self.low_value - self.base_value) / self.base_value * 100 if self.base_value else 0
        high_pct = (self.high_value - self.base_value) / self.base_value * 100 if self.base_value else 0
        return (low_pct, high_pct)


@dataclass
class SensitivityResult:
    """
    Result of one-way sensitivity for a single parameter.
    """
    parameter: str
    base_value: float
    base_npv: float
    
    low_value: float
    low_npv: float
    
    high_value: float
    high_npv: float
    
    # Impact measures
    npv_range: float = 0.0  # |high_npv - low_npv|
    elasticity: float = 0.0  # % change in NPV / % change in parameter
    
    # Switching value (value at which NPV = 0)
    switching_value: Optional[float] = None
    switching_possible: bool = False


@dataclass
class TornadoData:
    """
    Data for tornado diagram visualization.
    """
    parameters: List[str]
    base_npv: float
    low_npvs: List[float]
    high_npvs: List[float]
    low_values: List[float]
    high_values: List[float]


@dataclass
class MonteCarloResult:
    """
    Results of Monte Carlo simulation.
    """
    n_iterations: int
    npv_mean: float
    npv_std: float
    npv_percentiles: Dict[int, float]  # {5: value, 25: value, 50: value, 75: value, 95: value}
    npv_distribution: List[float]
    
    # Probability metrics
    prob_positive_npv: float
    prob_bcr_greater_1: float
    
    # Value at Risk
    var_5pct: float  # 5th percentile NPV


class SensitivityAnalysis:
    """
    Comprehensive sensitivity analysis for CBA results.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        self.parameters = self._define_parameters()
    
    def _define_parameters(self) -> Dict[str, SensitivityParameter]:
        """
        Define parameters for sensitivity analysis with their ranges.
        Uses SENSITIVITY_PARAMS populated from parameters.csv.
        """
        params = {}
        sp = SENSITIVITY_PARAMS
        
        # Discount rate
        params["discount_rate"] = SensitivityParameter(
            name="Discount Rate",
            base_value=self.config.economics.discount_rate,
            low_value=sp['discount_rate']['low'],
            high_value=sp['discount_rate']['high'],
            unit="%",
            description="Social discount rate for NPV calculation",
        )
        
        # Diesel price
        params["diesel_price"] = SensitivityParameter(
            name="Diesel Price",
            base_value=self.config.fuel.price_2026,
            low_value=sp['diesel_price']['low'],
            high_value=sp['diesel_price']['high'],
            unit="USD/L",
            description="Base diesel fuel price",
        )
        
        # Diesel escalation
        params["diesel_escalation"] = SensitivityParameter(
            name="Diesel Price Escalation",
            base_value=self.config.fuel.price_escalation,
            low_value=sp['diesel_escalation']['low'],
            high_value=sp['diesel_escalation']['high'],
            unit="%/year",
            description="Annual diesel price increase",
        )
        
        # Solar CAPEX
        params["solar_capex"] = SensitivityParameter(
            name="Solar PV CAPEX",
            base_value=self.config.technology.solar_pv_capex,
            low_value=sp['solar_capex']['low'],
            high_value=sp['solar_capex']['high'],
            unit="USD/kW",
            description="Solar PV installed cost",
        )
        
        # Battery CAPEX
        params["battery_capex"] = SensitivityParameter(
            name="Battery CAPEX",
            base_value=self.config.technology.battery_capex,
            low_value=sp['battery_capex']['low'],
            high_value=sp['battery_capex']['high'],
            unit="USD/kWh",
            description="Battery storage installed cost",
        )
        
        # Cable CAPEX
        params["cable_capex"] = SensitivityParameter(
            name="Undersea Cable CAPEX",
            base_value=self.config.technology.cable_capex_per_km,
            low_value=sp['cable_capex_per_km']['low'],
            high_value=sp['cable_capex_per_km']['high'],
            unit="USD/km",
            description="Undersea cable cost per km",
        )
        
        # PPA price
        params["ppa_price"] = SensitivityParameter(
            name="Import PPA Price",
            base_value=self.config.ppa.import_price_2030,
            low_value=sp['import_price']['low'],
            high_value=sp['import_price']['high'],
            unit="USD/kWh",
            description="Electricity import price",
        )
        
        # Social Cost of Carbon
        params["scc"] = SensitivityParameter(
            name="Social Cost of Carbon",
            base_value=self.config.economics.social_cost_carbon,
            low_value=sp['social_cost_carbon']['low'],
            high_value=sp['social_cost_carbon']['high'],
            unit="USD/tCO2",
            description="Monetized cost of emissions",
        )
        
        # Demand growth
        params["demand_growth"] = SensitivityParameter(
            name="Demand Growth Rate",
            base_value=self.config.demand.growth_rates["status_quo"],
            low_value=sp['demand_growth']['low'],
            high_value=sp['demand_growth']['high'],
            unit="%/year",
            description="Annual demand growth rate",
        )
        
        # Solar capacity factor
        params["solar_cf"] = SensitivityParameter(
            name="Solar Capacity Factor",
            base_value=self.config.technology.solar_pv_capacity_factor,
            low_value=sp['solar_cf']['low'],
            high_value=sp['solar_cf']['high'],
            unit="%",
            description="Solar PV capacity factor",
        )
        
        # GoM cost share for cable
        params["gom_cost_share"] = SensitivityParameter(
            name="GoM Cable Cost Share",
            base_value=self.config.one_grid.gom_share_pct,
            low_value=sp['gom_cost_share']['low'],
            high_value=sp['gom_cost_share']['high'],
            unit="%",
            description="Government of Maldives share of cable costs",
        )
        
        return params
    
    def run_one_way(
        self,
        scenario_runner: Callable[[Config], ScenarioResults],
        parameter_name: str,
        base_npv: float,
    ) -> SensitivityResult:
        """
        Run one-way sensitivity analysis for a single parameter.
        
        Args:
            scenario_runner: Function that takes config and returns ScenarioResults
            parameter_name: Name of parameter to vary
            base_npv: Base case NPV for comparison
        
        Returns:
            SensitivityResult with NPVs at low, base, and high values
        """
        param = self.parameters[parameter_name]
        
        # Create modified configs
        config_low = self._modify_config(parameter_name, param.low_value)
        config_high = self._modify_config(parameter_name, param.high_value)
        
        # Run scenarios
        results_low = scenario_runner(config_low)
        results_high = scenario_runner(config_high)
        
        # Calculate NPVs
        calc_low = CBACalculator(config_low)
        calc_high = CBACalculator(config_high)
        
        npv_low = calc_low.calculate_npv(results_low).pv_total_costs
        npv_high = calc_high.calculate_npv(results_high).pv_total_costs
        
        # Calculate impact measures
        npv_range = abs(npv_high - npv_low)
        
        # Elasticity
        param_range = param.high_value - param.low_value
        if param.base_value != 0 and param_range != 0:
            param_pct_change = param_range / param.base_value
            npv_pct_change = (npv_high - npv_low) / base_npv if base_npv != 0 else 0
            elasticity = npv_pct_change / param_pct_change
        else:
            elasticity = 0
        
        result = SensitivityResult(
            parameter=parameter_name,
            base_value=param.base_value,
            base_npv=base_npv,
            low_value=param.low_value,
            low_npv=npv_low,
            high_value=param.high_value,
            high_npv=npv_high,
            npv_range=npv_range,
            elasticity=elasticity,
        )
        
        return result
    
    def _modify_config(self, parameter_name: str, value: float) -> Config:
        """
        Create a modified config with the specified parameter value.
        """
        config = deepcopy(self.config)
        
        # Map parameter names to config attributes
        if parameter_name == "discount_rate":
            config.economics.discount_rate = value
        elif parameter_name == "diesel_price":
            config.fuel.price_2026 = value
        elif parameter_name == "diesel_escalation":
            config.fuel.price_escalation = value
        elif parameter_name == "solar_capex":
            config.technology.solar_pv_capex = value
        elif parameter_name == "battery_capex":
            config.technology.battery_capex = value
        elif parameter_name == "cable_capex":
            config.technology.cable_capex_per_km = value
        elif parameter_name == "ppa_price":
            config.ppa.import_price_2030 = value
        elif parameter_name == "scc":
            config.economics.social_cost_carbon = value
        elif parameter_name == "demand_growth":
            for key in config.demand.growth_rates:
                config.demand.growth_rates[key] = value
        elif parameter_name == "solar_cf":
            config.technology.solar_pv_capacity_factor = value
        elif parameter_name == "gom_cost_share":
            config.one_grid.gom_share_pct = value
        
        return config
    
    def calculate_switching_value(
        self,
        scenario_runner: Callable[[Config], ScenarioResults],
        parameter_name: str,
        target_npv: float = 0,
        incremental: bool = True,
    ) -> Optional[float]:
        """
        Calculate the switching value - parameter value at which NPV = target.
        
        Uses bisection method to find the switching value.
        
        Args:
            scenario_runner: Function that takes config and returns ScenarioResults
            parameter_name: Name of parameter to vary
            target_npv: Target NPV value (default 0 for break-even)
            incremental: If True, compare to baseline scenario
        
        Returns:
            Switching value or None if not found in parameter range
        """
        param = self.parameters[parameter_name]
        
        # Check if target is achievable in range
        config_low = self._modify_config(parameter_name, param.low_value)
        config_high = self._modify_config(parameter_name, param.high_value)
        
        calc_low = CBACalculator(config_low)
        calc_high = CBACalculator(config_high)
        
        results_low = scenario_runner(config_low)
        results_high = scenario_runner(config_high)
        
        npv_low = calc_low.calculate_npv(results_low).pv_total_costs
        npv_high = calc_high.calculate_npv(results_high).pv_total_costs
        
        # Check if target is in range
        if not ((npv_low - target_npv) * (npv_high - target_npv) < 0):
            return None  # Target not in range
        
        # Bisection method
        low_val = param.low_value
        high_val = param.high_value
        tolerance = (high_val - low_val) * 0.001  # 0.1% tolerance
        
        max_iterations = 50
        for _ in range(max_iterations):
            mid_val = (low_val + high_val) / 2
            config_mid = self._modify_config(parameter_name, mid_val)
            calc_mid = CBACalculator(config_mid)
            results_mid = scenario_runner(config_mid)
            npv_mid = calc_mid.calculate_npv(results_mid).pv_total_costs
            
            if abs(npv_mid - target_npv) < tolerance * target_npv or abs(high_val - low_val) < tolerance:
                return mid_val
            
            if (npv_mid - target_npv) * (npv_low - target_npv) < 0:
                high_val = mid_val
                npv_high = npv_mid
            else:
                low_val = mid_val
                npv_low = npv_mid
        
        return (low_val + high_val) / 2
    
    def generate_tornado_data(
        self,
        results: Dict[str, SensitivityResult],
        top_n: int = 10,
    ) -> TornadoData:
        """
        Generate data for tornado diagram.
        
        Args:
            results: Dictionary of SensitivityResult by parameter name
            top_n: Number of top parameters to include
        
        Returns:
            TornadoData for visualization
        """
        # Sort by NPV range (descending)
        sorted_params = sorted(
            results.items(),
            key=lambda x: x[1].npv_range,
            reverse=True,
        )[:top_n]
        
        base_npv = sorted_params[0][1].base_npv if sorted_params else 0
        
        return TornadoData(
            parameters=[p[0] for p in sorted_params],
            base_npv=base_npv,
            low_npvs=[p[1].low_npv for p in sorted_params],
            high_npvs=[p[1].high_npv for p in sorted_params],
            low_values=[p[1].low_value for p in sorted_params],
            high_values=[p[1].high_value for p in sorted_params],
        )
    
    def run_monte_carlo(
        self,
        scenario_runner: Callable[[Config], ScenarioResults],
        n_iterations: int = 1000,
        seed: int = 42,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.
        
        Uses triangular distributions for all parameters.
        
        Args:
            scenario_runner: Function that takes config and returns ScenarioResults
            n_iterations: Number of Monte Carlo iterations
            seed: Random seed for reproducibility
        
        Returns:
            MonteCarloResult with distribution statistics
        """
        np.random.seed(seed)
        
        npv_distribution = []
        bcr_distribution = []
        
        for i in range(n_iterations):
            # Sample parameters from distributions
            config = deepcopy(self.config)
            
            for param_name, param in self.parameters.items():
                # Triangular distribution: (low, mode=base, high)
                sampled_value = np.random.triangular(
                    param.low_value,
                    param.base_value,
                    param.high_value,
                )
                config = self._modify_config_inplace(config, param_name, sampled_value)
            
            # Run scenario and calculate NPV
            try:
                results = scenario_runner(config)
                calc = CBACalculator(config)
                npv_result = calc.calculate_npv(results)
                npv_distribution.append(npv_result.pv_total_costs)
            except Exception as e:
                # Skip failed iterations
                continue
        
        if not npv_distribution:
            raise ValueError("All Monte Carlo iterations failed")
        
        npv_array = np.array(npv_distribution)
        
        return MonteCarloResult(
            n_iterations=len(npv_distribution),
            npv_mean=float(np.mean(npv_array)),
            npv_std=float(np.std(npv_array)),
            npv_percentiles={
                5: float(np.percentile(npv_array, 5)),
                25: float(np.percentile(npv_array, 25)),
                50: float(np.percentile(npv_array, 50)),
                75: float(np.percentile(npv_array, 75)),
                95: float(np.percentile(npv_array, 95)),
            },
            npv_distribution=npv_distribution,
            prob_positive_npv=float(np.mean(npv_array > 0)),
            prob_bcr_greater_1=0.0,  # Would need BCR calculation
            var_5pct=float(np.percentile(npv_array, 5)),
        )
    
    def _modify_config_inplace(self, config: Config, parameter_name: str, value: float) -> Config:
        """
        Modify config in place (for Monte Carlo efficiency).
        """
        if parameter_name == "discount_rate":
            config.economics.discount_rate = value
        elif parameter_name == "diesel_price":
            config.fuel.price_2026 = value
        elif parameter_name == "diesel_escalation":
            config.fuel.price_escalation = value
        elif parameter_name == "solar_capex":
            config.technology.solar_pv_capex = value
        elif parameter_name == "battery_capex":
            config.technology.battery_capex = value
        elif parameter_name == "cable_capex":
            config.technology.cable_capex_per_km = value
        elif parameter_name == "ppa_price":
            config.ppa.import_price_2030 = value
        elif parameter_name == "scc":
            config.economics.social_cost_carbon = value
        elif parameter_name == "demand_growth":
            for key in config.demand.growth_rates:
                config.demand.growth_rates[key] = value
        elif parameter_name == "solar_cf":
            config.technology.solar_pv_capacity_factor = value
        elif parameter_name == "gom_cost_share":
            config.one_grid.gom_share_pct = value
        
        return config
    
    def get_parameter_summary(self) -> str:
        """
        Get a summary of all sensitivity parameters.
        """
        lines = [
            "=" * 70,
            "SENSITIVITY PARAMETERS",
            "=" * 70,
            f"{'Parameter':<25} {'Base':>12} {'Low':>12} {'High':>12} {'Unit':>10}",
            "-" * 70,
        ]
        
        for name, param in self.parameters.items():
            lines.append(
                f"{param.name:<25} {param.base_value:>12.4g} {param.low_value:>12.4g} {param.high_value:>12.4g} {param.unit:>10}"
            )
        
        return "\n".join(lines)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SENSITIVITY ANALYSIS TEST")
    print("=" * 60)
    
    config = get_config()
    analysis = SensitivityAnalysis(config)
    
    # Print parameter summary
    print(analysis.get_parameter_summary())
    
    print("\n✓ Sensitivity Analysis module loaded successfully!")
