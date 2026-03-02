"""
Triggers Builder Module

Модуль для построения триггеров с вероятностным анализом.
Обеспечивает расчет p_up/p_down, acceleration, micro-фильтры и anti-noise.
"""

from ..logging_config import get_triggers_logger

# Инициализация логгера для модуля
logger = get_triggers_logger()
logger.info("Triggers module initialized")

__version__ = "1.0.0"
