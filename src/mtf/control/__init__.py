"""
MTF Control Panel Module

Модуль управления MTF системой:
- Управление конфигурацией
- Мониторинг состояния
- Управление запуском/остановкой
- Управление ресурсами
- Алерты и уведомления
"""

# Инициализация логирования
from ..logging_config import get_control_logger
from .builder import ControlBuilder
from .engine import ControlEngine
from .models import (
    ComponentStatus,
    ControlAction,
    ControlConfig,
    ControlMetrics,
    ControlRequest,
    ControlResult,
    SystemStatus,
)

logger = get_control_logger()
logger.info("Control module initialized")

__all__ = [
    "ControlBuilder",
    "ControlEngine",
    "ControlRequest",
    "ControlResult",
    "ControlMetrics",
    "ControlConfig",
    "SystemStatus",
    "ComponentStatus",
    "ControlAction",
]
