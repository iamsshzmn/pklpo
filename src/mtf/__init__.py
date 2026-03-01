"""
MTF (Multi-Timeframe) System

Система для анализа рынка на множественных таймфреймах.
Включает модули: Context, Triggers, Consensus, Pipeline, Integration, Control.

Pipeline: Features → Context → Triggers → Consensus → Integration
"""

from .logging_config import MTFLogger, get_main_logger
from .mtf_builder import MTFBuilder

# Инициализация основного логгера
logger = get_main_logger()
logger.info("MTF System initialized")

# Версия системы
__version__ = "3.0.0"

# Экспорт основных компонентов
__all__ = ["MTFBuilder", "MTFLogger", "__version__", "logger"]
