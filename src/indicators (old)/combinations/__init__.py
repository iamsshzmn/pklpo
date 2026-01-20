from .analyzer import SignalAnalyzer
from .calculator import (
    CombinationCalculator,
    CombinationResult,
    analyze_combination_performance,
)
from .pairs import PAIRS
from .performance import PerformanceAnalyzer
from .quartets import QUARTETS
from .recommendations import RecommendationGenerator
from .trios import TRIOS

COMBINATIONS = {**PAIRS, **TRIOS, **QUARTETS}

__all__ = [
    "PAIRS",
    "TRIOS",
    "QUARTETS",
    "COMBINATIONS",
    "CombinationCalculator",
    "CombinationResult",
    "analyze_combination_performance",
    "SignalAnalyzer",
    "RecommendationGenerator",
    "PerformanceAnalyzer",
]
