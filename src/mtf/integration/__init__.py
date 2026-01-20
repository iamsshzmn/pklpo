"""
MTF Integration Module

Модуль для интеграции с внешними системами:
- OKX API для получения рыночных данных
- База данных для хранения результатов
- Система уведомлений (Slack, Email)
- Мониторинг и алерты
"""

# Инициализация логирования
from ..logging_config import get_integration_logger
from .builder import IntegrationBuilder
from .engine import IntegrationEngine
from .models import (
    DataSource,
    IntegrationConfig,
    IntegrationMetrics,
    IntegrationRequest,
    IntegrationResult,
    IntegrationStatus,
    NotificationType,
)

logger = get_integration_logger()
logger.info("Integration module initialized")

__all__ = [
    "IntegrationBuilder",
    "IntegrationEngine",
    "IntegrationRequest",
    "IntegrationResult",
    "IntegrationMetrics",
    "IntegrationConfig",
    "DataSource",
    "NotificationType",
    "IntegrationStatus",
]
