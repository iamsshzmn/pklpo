"""
Конфигурации для движка сигналов.
"""

from ..config import get_strategy_config
from .signal_engine import SignalEngine


def create_signal_engine(config: str = "balanced") -> SignalEngine:
    """
    Создает движок сигналов с предустановленной конфигурацией.

    Args:
        config: Название конфигурации ('balanced', 'conservative', 'aggressive')

    Returns:
        SignalEngine: Настроенный движок сигналов
    """
    strategy_config = get_strategy_config(config)

    return SignalEngine(
        weights=strategy_config.get("rule_weights"),
        min_score_for_buy=strategy_config.get("min_score_for_buy"),
        min_score_for_sell=strategy_config.get("min_score_for_sell"),
    )


def get_available_configs() -> dict[str, str]:
    """
    Возвращает список доступных конфигураций.

    Returns:
        Dict[str, str]: Словарь {название: описание}
    """
    return {
        "balanced": "Сбалансированная стратегия с равными весами",
        "conservative": "Консервативная стратегия с акцентом на трендовые индикаторы",
        "aggressive": "Агрессивная стратегия с акцентом на осцилляторы",
    }
