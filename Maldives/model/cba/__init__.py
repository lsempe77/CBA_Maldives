"""
CBA Package
===========

Cost-Benefit Analysis components for scenario comparison.
"""

from .npv_calculator import (
    CBACalculator,
    NPVResult,
    IncrementalResult,
    CBAComparison,
)

from .sensitivity import (
    SensitivityAnalysis,
    SensitivityParameter,
    SensitivityResult,
    TornadoData,
    MonteCarloResult,
)

__all__ = [
    # NPV Calculator
    "CBACalculator",
    "NPVResult",
    "IncrementalResult",
    "CBAComparison",
    # Sensitivity Analysis
    "SensitivityAnalysis",
    "SensitivityParameter",
    "SensitivityResult",
    "TornadoData",
    "MonteCarloResult",
]
