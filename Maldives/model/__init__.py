"""
Maldives Energy CBA Model
=========================

A Cost-Benefit Analysis framework comparing 7 energy pathways for the Maldives:
- S1 BAU: Diesel continuation (status quo counterfactual)
- S2 Full Integration: India submarine cable + progressive grid
- S3 National Grid: Progressive domestic grid (no India cable)
- S4 Islanded Green: Per-island solar+battery
- S5 Near-Shore Solar: Uninhabited island solar farms
- S6 Maximum RE: Rooftop + nearshore + floating solar
- S7 LNG Transition: 140 MW LNG plant on Gulhifalhu

Usage:
    from model import get_config
    from model.scenarios import StatusQuoScenario, NationalGridScenario
    from model.cba import CBACalculator

    config = get_config()
    sq = StatusQuoScenario(config)
    results = sq.run()

Or run from command line:
    python -m model.run_cba
"""

from .config import Config, get_config
from .demand import DemandProjector, MultiScenarioDemand
from .costs import CostCalculator, AnnualCosts
from .emissions import EmissionsCalculator

__version__ = "0.1.0"

__all__ = [
    # Configuration
    "Config",
    "get_config",
    # Demand
    "DemandProjector",
    "MultiScenarioDemand",
    # Costs
    "CostCalculator",
    "AnnualCosts",
    # Emissions
    "EmissionsCalculator",
]
