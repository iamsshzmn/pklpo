"""
Модуль для бэктестинга и оценки качества торговых сигналов.
"""

from .evaluate import SignalEvaluator
from .metrics import calc_max_drawdown, calc_pnl, calc_sharpe_ratio, calc_win_rate

__all__ = [
    "calc_pnl",
    "calc_sharpe_ratio",
    "calc_max_drawdown",
    "calc_win_rate",
    "SignalEvaluator",
]
