"""
MTF Pipeline Module

Интеграционный модуль для объединения Context, Triggers и Consensus компонентов
в единый pipeline обработки данных.
"""

# Инициализация логирования
from ..logging_config import get_pipeline_logger
from .builder import PipelineBuilder
from .engine import PipelineEngine
from .models import (
    PipelineConfig,
    PipelineMetrics,
    PipelineRequest,
    PipelineResult,
    PipelineStatus,
    ProcessingStage,
)

logger = get_pipeline_logger()
logger.info("Pipeline module initialized")

__all__ = [
    "PipelineBuilder",
    "PipelineEngine",
    "PipelineRequest",
    "PipelineResult",
    "PipelineMetrics",
    "PipelineConfig",
    "ProcessingStage",
    "PipelineStatus",
]
