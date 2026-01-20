"""
Модуль предохранителей риска (Guards)

Основные компоненты:
- CircuitBreaker: автоматическое отключение при превышении порогов
- KillSwitch: экстренное отключение системы
- DQGuard: защита от плохого качества данных
- SLAGuard: защита от нарушения SLA
- HealthGuard: мониторинг здоровья системы
"""

from .circuit_breaker import CircuitBreaker
from .dq_guards import DQGuard
from .health_guards import HealthGuard
from .killswitch import KillSwitch
from .sla_guards import SLAGuard

__all__ = ["CircuitBreaker", "KillSwitch", "DQGuard", "SLAGuard", "HealthGuard"]
