"""
Модуль для расчёта позиций на SWAP инструментах.

Содержит:
- Калькулятор позиций с учётом всех обязательных данных
- Валидатор обязательных полей
- Модели данных для позиций
- Конфигурацию по умолчанию
"""

from .calculator import PositionCalculationResult, PositionCalculator
from .models import PositionCalculation, SwapMetadata, UserSettings
from .validator import PositionDataValidator

__all__ = [
    "PositionCalculation",
    "PositionCalculationResult",
    "PositionCalculator",
    "PositionDataValidator",
    "SwapMetadata",
    "UserSettings",
]
