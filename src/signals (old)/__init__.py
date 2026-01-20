"""
Пакет для генерации торговых сигналов на основе технических индикаторов.
"""

from .calculator import SignalCalculator
from .engine import SignalEngine, create_signal_engine
from .rules import RULES

__all__ = ["RULES", "SignalEngine", "create_signal_engine", "SignalCalculator"]
