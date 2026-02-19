"""
Модуль для бэктестинга и оценки качества торговых сигналов.
"""

from .evaluate import SignalEvaluator
from .metrics import (
    calc_max_drawdown,
    calc_pnl,
    calc_sharpe_ratio,
    calc_win_rate,
    sharpe_ratio,
)

__all__ = [
    "SignalEvaluator",
    "calc_max_drawdown",
    "calc_pnl",
    "calc_sharpe_ratio",  # deprecated wrapper
    "calc_win_rate",
    "sharpe_ratio",
]
