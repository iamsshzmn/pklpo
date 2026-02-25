"""
Модуль торговых рекомендаций

Система для анализа score_results и генерации торговых рекомендаций
с расчётом параметров позиции (вход, стоп, тейк, объём).
"""

from .models import TradePosition, TradeRecommendation
from .position_model import calculate_position
from .recommend import recommend_for_score

__all__ = [
    "TradePosition",
    "TradeRecommendation",
    "calculate_position",
    "recommend_for_score",
]
