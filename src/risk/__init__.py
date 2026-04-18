"""
Risk management and circuit breakers module (Phase 5).

Components:
- Sizing: position size calculation
- Limits: risk limit management
- Guards: circuit breaker, killswitch, DQ guards
- Database: schemas and DB client
- CLI: command-line interface

Integration with existing modules:
- positions/ - extended position calculation
- trade_recommender/ - risk-aware logic
- signals/ - validation integration
- market_meta/ - validator usage
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
    "CircuitBreakerState",
    "KillSwitchState",
    # Core components
    "PositionSizeCalculator",
    "PositionSizeRequest",
    "PositionSizeResult",
    # Models
    "RiskConfig",
    "RiskLimit",
    "RiskViolation",
    # "RiskLimitsManager",
    # "CircuitBreaker",
    # "KillSwitch",
    # "DQGuard",
    # "SLAGuard",
]
