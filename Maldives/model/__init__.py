"""
Maldives Energy CBA Model
=========================

A Cost-Benefit Analysis framework for comparing energy pathways:
- Scenario 1: Status Quo (diesel continuation)
- Scenario 2: Green Transition (RE acceleration per GoM roadmap)
- Scenario 3: One Grid (undersea cable to India)

Usage:
    from model import get_config
    from model.scenarios import StatusQuoScenario, GreenTransitionScenario, OneGridScenario
    from model.cba import CBACalculator
    
    config = get_config()
    sq = StatusQuoScenario(config)
    results = sq.run()

Or run from command line:
    python -m model.run_cba

For full CBA with all three scenarios:
    from model.run_cba import main
    main()
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
