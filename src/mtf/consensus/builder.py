"""
Построитель консенсуса для MTF системы
"""

from datetime import datetime
from typing import Any

from ..logging_config import create_log_context, get_consensus_logger, log_performance
from .config import ConsensusConfig as Config
from .engine import ConsensusEngine
from .models import (
    ConsensusConfig,
    ConsensusMetrics,
    ConsensusRequest,
    ConsensusResult,
)
from .validator import ConsensusValidator

logger = get_consensus_logger()


class ConsensusBuilder:
    """Построитель консенсуса между Context и Triggers модулями"""

    def __init__(self, config: ConsensusConfig | None = None):
        self.config = config or Config()
        self.engine = ConsensusEngine(self.config)
        self.validator = ConsensusValidator(self.config)
        logger.info(f"ConsensusBuilder initialized with config: {self.config.__dict__}")

    @log_performance("consensus", "build_consensus")
    async def build_consensus(
        self,
        symbol: str,
        timeframes: list[str],
        context_data: dict[str, Any] | None = None,
        triggers_data: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> ConsensusResult:
        """Построение консенсуса для символа и таймфреймов"""
        with create_log_context(
            "consensus",
            f"build_consensus_{symbol}",
            symbol=symbol,
            timeframes=timeframes,
        ):
            logger.info(
                f"Building consensus for {symbol} with timeframes: {timeframes}"
            )

            # Создание запроса
            request = ConsensusRequest(
                symbol=symbol,
                timeframes=timeframes,
                context_data=context_data,
                triggers_data=triggers_data,
                timestamp=timestamp,
            )

            # Построение консенсуса через движок
            result = await self.engine.build_consensus(request)

            # Логирование результата
            logger.info(
                f"Consensus built for {symbol}: {result.consensus_type.value}, "
                f"confidence: {result.confidence_level.value}, "
                f"score: {result.final_score:.3f}"
            )

            return result

    def get_supported_timeframes(self) -> list[str]:
        """Получение поддерживаемых таймфреймов"""
        return list(self.config.timeframe_weights.keys())

    def get_config_summary(self) -> dict[str, Any]:
        """Получение сводки конфигурации"""
        return {
            "context_weight": self.config.context_weight,
            "triggers_weight": self.config.triggers_weight,
            "strong_bullish_threshold": self.config.strong_bullish_threshold,
            "bullish_threshold": self.config.bullish_threshold,
            "bearish_threshold": self.config.bearish_threshold,
            "strong_bearish_threshold": self.config.strong_bearish_threshold,
            "conflict_threshold": self.config.conflict_threshold,
            "min_confidence_for_consensus": self.config.min_confidence_for_consensus,
            "timeframe_weights": self.config.timeframe_weights,
            "cache_enabled": self.config.cache_enabled,
            "enable_timeframe_aggregation": self.config.enable_timeframe_aggregation,
            "enable_confidence_boost": self.config.enable_confidence_boost,
        }

    def get_health_status(self) -> dict[str, Any]:
        """Получение статуса здоровья"""
        return self.engine.get_health_status()

    def get_metrics(self) -> ConsensusMetrics:
        """Получение метрик"""
        return self.engine.get_metrics()

    def get_cache_stats(self) -> dict[str, Any]:
        """Получение статистики кэша"""
        return self.engine.get_cache_stats()

    def clear_cache(self):
        """Очистка кэша"""
        self.engine.clear_cache()
        logger.info("Consensus cache cleared")

    def update_config(self, **kwargs) -> ConsensusConfig:
        """Обновление конфигурации"""
        # Создаем новую конфигурацию с обновленными параметрами
        config_dict = self.config.__dict__.copy()
        config_dict.update(kwargs)

        new_config = ConsensusConfig(**config_dict)
        self.config = new_config
        self.engine.update_config(new_config)
        self.validator = ConsensusValidator(new_config)

        logger.info(f"Consensus configuration updated: {kwargs}")
        return new_config

    def validate_consensus_result(self, result: ConsensusResult) -> dict[str, Any]:
        """Валидация результата консенсуса"""
        validation_result = self.validator.validate_result(result)

        return {
            "is_valid": validation_result.status.value == "valid",
            "status": validation_result.status.value,
            "message": validation_result.message,
            "details": validation_result.details,
        }

    def get_consensus_summary(self, result: ConsensusResult) -> dict[str, Any]:
        """Получение сводки консенсуса"""
        return {
            "symbol": result.symbol,
            "consensus_type": result.consensus_type.value,
            "confidence_level": result.confidence_level.value,
            "final_score": result.final_score,
            "net_score": result.net_score,
            "is_bullish": result.is_bullish,
            "is_bearish": result.is_bearish,
            "is_neutral": result.is_neutral,
            "is_conflicted": result.is_conflicted,
            "context_weight": result.context_weight,
            "triggers_weight": result.triggers_weight,
            "supporting_evidence_count": len(result.supporting_evidence),
            "conflicting_evidence_count": len(result.conflicting_evidence),
            "warnings_count": len(result.warnings),
            "is_valid": result.is_valid,
            "timestamp": result.timestamp.isoformat(),
        }
