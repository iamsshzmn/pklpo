"""
Модуль расчета размеров позиций (Sizing)

Основные компоненты:
- PositionSizeCalculator: расчет размера позиции с учетом рисков
- PositionSizeValidator: валидация параметров расчета
- RiskAwareSizing: интеграция с существующими модулями
"""

from .calculator import PositionSizeCalculator
from .models import PositionSizeRequest, PositionSizeResult
from .validators import PositionSizeValidator

__all__ = [
    "PositionSizeCalculator",
    "PositionSizeRequest",
    "PositionSizeResult",
    "PositionSizeValidator",
]
