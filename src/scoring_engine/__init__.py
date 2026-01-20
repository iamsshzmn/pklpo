"""
Scoring Engine Module

Модуль для вычисления итогового score на основе индикаторов и комбинаций.
Объединяет расчёты в единый score_raw ∈ [0;1], калибрует его и сохраняет в БД.
Использует расширенную конфигурацию с 50+ индикаторами для максимальной точности.
"""

from .compute import ScoreResult, ScoringEngine, compute_score
from .models import ScoreResult as ScoreResultModel
from .processor import (
    ScoringProcessor,
    get_score_statistics,
    process_all_scores,
    process_symbol_scores,
)

__all__ = [
    "compute_score",
    "ScoreResult",
    "ScoreResultModel",
    "ScoringEngine",
    "process_all_scores",
    "process_symbol_scores",
    "get_score_statistics",
    "ScoringProcessor",
]
