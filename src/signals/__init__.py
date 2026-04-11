"""
Signals Module (Фаза 4) - Система торговых сигналов

Основные компоненты:
- Decision: торговые решения с полным контрактом
- SignalCandidate: кандидаты на сигналы
- SignalLive: активные сигналы
- SignalHistory: история исполненных сигналов
- DecisionMaker: создание решений из MTF consensus
- SignalValidator: валидация сигналов
- PromoteWorkflow: управление жизненным циклом
"""

from .database.client import SignalsDatabaseClient
from .decision.maker import DecisionMaker
from .models import (
    Decision,
    SignalCandidate,
    SignalConfig,
    SignalHistory,
    SignalHorizon,
    SignalLive,
    SignalMetrics,
    SignalSide,
    SignalStatus,
    ValidationResult,
)
from .validation.validator import SignalValidator
from .workflow.promote import PromoteWorkflow

__version__ = "1.0.0"
__author__ = "PKLPO Team"

__all__ = [
    # Models
    "Decision",
    # Components
    "DecisionMaker",
    "PromoteWorkflow",
    "SignalCandidate",
    "SignalConfig",
    "SignalHistory",
    "SignalHorizon",
    "SignalLive",
    "SignalMetrics",
    "SignalSide",
    "SignalStatus",
    "SignalValidator",
    "SignalsDatabaseClient",
    "ValidationResult",
]
