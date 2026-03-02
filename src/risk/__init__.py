"""
Модуль управления рисками и предохранителями (Фаза 5)

Основные компоненты:
- Sizing: расчет размеров позиций
- Limits: управление лимитами риска
- Guards: предохранители (circuit breaker, killswitch, DQ guards)
- Database: схемы и клиент БД
- CLI: интерфейс командной строки

Интеграция с существующими модулями:
- positions/ - расширение расчета позиций
- trade_recommender/ - добавление risk-aware логики
- signals/ - интеграция с валидацией
- market_meta/ - использование валидаторов
"""

from .models import (
    CircuitBreakerState,
    KillSwitchState,
    PositionSizeRequest,
    PositionSizeResult,
    RiskConfig,
    RiskLimit,
    RiskViolation,
)
from .sizing.calculator import PositionSizeCalculator

# from .limits.manager import RiskLimitsManager
# from .guards.circuit_breaker import CircuitBreaker
# from .guards.killswitch import KillSwitch
# from .guards.dq_guards import DQGuard
# from .guards.sla_guards import SLAGuard

__version__ = "1.0.0"
__author__ = "PKLPO Team"

__all__ = [
    # Models
    "RiskConfig",
    "RiskLimit",
    "CircuitBreakerState",
    "KillSwitchState",
    "PositionSizeRequest",
    "PositionSizeResult",
    "RiskViolation",
    # Core components
    "PositionSizeCalculator",
    # "RiskLimitsManager",
    # "CircuitBreaker",
    # "KillSwitch",
    # "DQGuard",
    # "SLAGuard",
]
