"""
Валидация ML-моделей без look-ahead bias.

Модули:
    purged_kfold — PurgedKFold + Embargo, совместимый со scikit-learn.
    cpcv         — Combinatorial Purged Cross-Validation.
    lookahead    — Детектор look-ahead bias для CI gate (Блок G).
"""

from src.ml.validation.cpcv import CombinatorialPurgedCV
from src.ml.validation.lookahead import LookaheadResult, check_lookahead
from src.ml.validation.purged_kfold import PurgedKFold

__all__ = ["CombinatorialPurgedCV", "LookaheadResult", "PurgedKFold", "check_lookahead"]
