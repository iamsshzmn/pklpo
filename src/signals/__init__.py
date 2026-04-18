"""
Signals Module (Phase 4) - Trading signal system.

Components:
- Decision: trade decisions with full contract
- SignalCandidate: signal candidates
- SignalLive: active signals
- SignalHistory: executed signal history
- DecisionMaker: creates decisions from MTF consensus
- SignalValidator: signal validation
- PromoteWorkflow: lifecycle management
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
