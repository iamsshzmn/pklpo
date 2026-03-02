"""
Модуль для бэктестинга и оценки качества торговых сигналов.
"""

from .evaluate import SignalEvaluator
from .metrics import (
    calc_max_drawdown,
    calc_metrics,
    calc_pnl,
    calc_win_rate,
    deflated_sharpe_ratio,
    sharpe_ratio,
)

__all__ = [
    "SignalEvaluator",
    "calc_max_drawdown",
    "calc_metrics",
    "calc_pnl",
    "calc_win_rate",
    "deflated_sharpe_ratio",
    "sharpe_ratio",
]
