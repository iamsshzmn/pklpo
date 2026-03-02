"""
Consensus модуль для MTF системы
Обеспечивает агрегацию и консенсус между Context и Triggers модулями
"""

from ..logging_config import get_consensus_logger
from .algorithms import ConsensusAggregator, WeightCalculator
from .builder import ConsensusBuilder
from .config import ConsensusConfig as Config
from .engine import ConsensusEngine
from .models import (
    ConfidenceLevel,
    ConsensusConfig,
    ConsensusMetrics,
    ConsensusRequest,
    ConsensusResult,
    ConsensusType,
    ValidationResult,
    ValidationStatus,
)
from .validator import ConsensusValidator

logger = get_consensus_logger()
logger.info("Consensus module initialized")

__all__ = [
    "ConfidenceLevel",
    "Config",
    "ConsensusAggregator",
    "ConsensusBuilder",
    "ConsensusConfig",
    "ConsensusEngine",
    "ConsensusMetrics",
    "ConsensusRequest",
    "ConsensusResult",
    "ConsensusType",
    "ConsensusValidator",
    "ValidationResult",
    "ValidationStatus",
    "WeightCalculator",
]
