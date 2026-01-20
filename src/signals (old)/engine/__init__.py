"""
Пакет с движком сигналов.
"""

from .configs import create_signal_engine
from .signal_engine import SignalEngine

__all__ = ["SignalEngine", "create_signal_engine"]
