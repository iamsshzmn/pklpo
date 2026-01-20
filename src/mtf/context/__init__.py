"""
Context Builder Module

Модуль для построения контекста рынка с regime detection.
Обеспечивает расчет trend score, определение режимов рынка и валидацию данных.
"""

from ..logging_config import get_context_logger
from .algorithms import RegimeDetector
from .builder import ContextBuilder
from .config import ContextConfig
from .engine import ContextEngine
from .models import ContextResult, ValidationResult
from .validator import ContextValidator

# Инициализация логгера для модуля
logger = get_context_logger()
logger.info("Context module initialized")

__all__ = [
    "ContextBuilder",
    "ContextEngine",
    "ContextValidator",
    "ContextResult",
    "ValidationResult",
    "RegimeDetector",
    "ContextConfig",
]

__version__ = "1.0.0"
