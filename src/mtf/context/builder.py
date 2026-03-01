"""
Построитель контекста - основной класс для построения контекста
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..logging_config import create_log_context, get_context_logger, log_performance
from .config import ContextConfig
from .engine import ContextEngine
from .models import (
    ContextData,
    ContextMetrics,
    ContextRequest,
    ContextResult,
    RegimeType,
)
from .validator import ContextValidator

logger = get_context_logger()


class ContextBuilder:
    """Основной класс для построения контекста"""

    def __init__(self, config: ContextConfig | None = None):
        """Инициализация построителя контекста"""
        self.config = config or ContextConfig.default()
        self.engine = ContextEngine(self.config)
        self.validator = ContextValidator(self.config)

        # Настройка логирования
        if self.config.enable_logging:
            import logging

            logging.basicConfig(level=getattr(logging, self.config.log_level))

    @classmethod
    def from_config_file(cls, config_path: str | Path) -> "ContextBuilder":
        """Создание построителя из файла конфигурации"""
        config = ContextConfig.from_yaml(config_path)
        return cls(config)

    @classmethod
    def for_production(cls) -> "ContextBuilder":
        """Создание построителя для продакшена"""
        config = ContextConfig.for_production()
        return cls(config)

    @classmethod
    def for_development(cls) -> "ContextBuilder":
        """Создание построителя для разработки"""
        config = ContextConfig.for_development()
        return cls(config)

    @log_performance("context", "build_context")
    async def build_context(
        self,
        symbol: str,
        timeframes: list[str],
        features_data: dict[str, pd.DataFrame] | None = None,
        market_meta_data: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> ContextResult:
        """Построение контекста для символа и таймфреймов"""
        with create_log_context("context", f"build_context_{symbol}"):
            try:
                logger.info(
                    f"Building context for {symbol} with timeframes: {timeframes}"
                )

                # Создание запроса
                request = ContextRequest(
                    symbol=symbol,
                    timeframes=timeframes,
                    timestamp=timestamp,
                    features_data=features_data,
                    market_meta_data=market_meta_data,
                )

                # Построение контекста через движок
                result = await self.engine.build_context(request)

                logger.info(
                    f"Context built for {symbol}: {len(result.contexts)} timeframes, "
                    f"score: {result.overall_score:.3f}, regime: {result.dominant_regime.value}, "
                    f"valid: {result.valid}"
                )

                return result

            except Exception as e:
                logger.error(f"Error building context for {symbol}: {e}", exc_info=True)
                return ContextResult(
                    symbol=symbol,
                    timestamp=timestamp or datetime.now(),
                    contexts={},
                    overall_score=0.0,
                    dominant_regime=RegimeType.UNKNOWN,
                    confidence=0.0,
                    valid=False,
                    errors=[str(e)],
                )

    async def build_context_batch(
        self, requests: list[dict[str, Any]]
    ) -> dict[str, ContextResult]:
        """Пакетное построение контекста для нескольких символов"""
        results = {}

        try:
            # Создание задач для каждого запроса
            tasks = []
            for req_data in requests:
                symbol = req_data.get("symbol")
                timeframes = req_data.get("timeframes", [])
                features_data = req_data.get("features_data")
                market_meta_data = req_data.get("market_meta_data")
                timestamp = req_data.get("timestamp")

                task = asyncio.create_task(
                    self.build_context(
                        symbol=symbol,
                        timeframes=timeframes,
                        features_data=features_data,
                        market_meta_data=market_meta_data,
                        timestamp=timestamp,
                    )
                )
                tasks.append((symbol, task))

            # Ожидание завершения всех задач
            for symbol, task in tasks:
                try:
                    result = await asyncio.wait_for(
                        task, timeout=self.config.timeout_seconds
                    )
                    results[symbol] = result
                except TimeoutError:
                    logger.error(f"Timeout building context for {symbol}")
                    results[symbol] = ContextResult(
                        symbol=symbol,
                        timestamp=datetime.now(),
                        contexts={},
                        overall_score=0.0,
                        dominant_regime=RegimeType.UNKNOWN,
                        confidence=0.0,
                        valid=False,
                        errors=["Timeout"],
                    )
                except Exception as e:
                    logger.error(f"Error building context for {symbol}: {e}")
                    results[symbol] = ContextResult(
                        symbol=symbol,
                        timestamp=datetime.now(),
                        contexts={},
                        overall_score=0.0,
                        dominant_regime=RegimeType.UNKNOWN,
                        confidence=0.0,
                        valid=False,
                        errors=[str(e)],
                    )

            logger.info(
                f"Batch context building completed: {len(results)} symbols processed"
            )
            return results

        except Exception as e:
            logger.error(f"Error in batch context building: {e}")
            return results

    async def get_context_metrics(
        self, symbol: str, timeframes: list[str]
    ) -> ContextMetrics:
        """Получение метрик контекста"""
        return await self.engine.get_context_metrics(symbol, timeframes)

    def validate_context_data(self, context_data: ContextData) -> bool:
        """Валидация данных контекста"""
        validation_result = self.validator.validate_context_data(context_data)
        return validation_result.status.value == "valid"

    def validate_context_result(self, result: ContextResult) -> bool:
        """Валидация результата контекста"""
        validation_result = self.validator.validate_context_result(result)
        return validation_result.status.value == "valid"

    def get_context_summary(self, result: ContextResult) -> dict[str, Any]:
        """Получение сводки по контексту"""
        summary = {
            "symbol": result.symbol,
            "timestamp": result.timestamp,
            "overall_score": result.overall_score,
            "dominant_regime": result.dominant_regime.value,
            "confidence": result.confidence,
            "valid": result.valid,
            "timeframes_count": len(result.contexts),
            "valid_timeframes": len(result.valid_contexts),
            "has_errors": result.has_errors,
            "errors_count": len(result.errors),
        }

        # Детали по таймфреймам
        timeframe_details = {}
        for timeframe, context in result.contexts.items():
            timeframe_details[timeframe] = {
                "score": context.score,
                "regime": context.regime.value,
                "valid": context.valid,
                "reason_codes": [code.value for code in context.reason_codes],
            }

        summary["timeframe_details"] = timeframe_details

        # Распределение режимов
        regime_distribution = {}
        for context in result.contexts.values():
            regime = context.regime.value
            regime_distribution[regime] = regime_distribution.get(regime, 0) + 1

        summary["regime_distribution"] = regime_distribution

        # Распределение кодов причин
        reason_code_distribution = {}
        for context in result.contexts.values():
            for code in context.reason_codes:
                code_name = code.value
                reason_code_distribution[code_name] = (
                    reason_code_distribution.get(code_name, 0) + 1
                )

        summary["reason_code_distribution"] = reason_code_distribution

        return summary

    def get_context_by_timeframe(
        self, result: ContextResult, timeframe: str
    ) -> ContextData | None:
        """Получение контекста по таймфрейму"""
        return result.get_context_by_timeframe(timeframe)

    def get_regime_by_timeframe(
        self, result: ContextResult, timeframe: str
    ) -> RegimeType | None:
        """Получение режима по таймфрейму"""
        return result.get_regime_by_timeframe(timeframe)

    def get_score_by_timeframe(
        self, result: ContextResult, timeframe: str
    ) -> float | None:
        """Получение score по таймфрейму"""
        return result.get_score_by_timeframe(timeframe)

    def is_bullish_context(self, result: ContextResult) -> bool:
        """Проверка на бычий контекст"""
        return (
            result.overall_score > 0.1
            and result.dominant_regime == RegimeType.TREND_UP
            and result.confidence > 0.5
        )

    def is_bearish_context(self, result: ContextResult) -> bool:
        """Проверка на медвежий контекст"""
        return (
            result.overall_score < -0.1
            and result.dominant_regime == RegimeType.TREND_DOWN
            and result.confidence > 0.5
        )

    def is_neutral_context(self, result: ContextResult) -> bool:
        """Проверка на нейтральный контекст"""
        return (
            abs(result.overall_score) <= 0.1
            or result.dominant_regime == RegimeType.FLAT
            or result.confidence <= 0.5
        )

    def get_context_strength(self, result: ContextResult) -> str:
        """Получение силы контекста"""
        if not result.valid:
            return "invalid"

        abs_score = abs(result.overall_score)

        if abs_score >= 0.7:
            return "very_strong"
        if abs_score >= 0.5:
            return "strong"
        if abs_score >= 0.3:
            return "moderate"
        if abs_score >= 0.1:
            return "weak"
        return "very_weak"

    def get_context_direction(self, result: ContextResult) -> str:
        """Получение направления контекста"""
        if result.overall_score > 0.1:
            return "bullish"
        if result.overall_score < -0.1:
            return "bearish"
        return "neutral"

    def clear_cache(self) -> None:
        """Очистка кэша"""
        self.engine.clear_cache()

    def get_cache_stats(self) -> dict[str, Any]:
        """Получение статистики кэша"""
        return self.engine.get_cache_stats()

    def update_config(self, new_config: ContextConfig) -> None:
        """Обновление конфигурации"""
        self.config = new_config
        self.engine.update_config(new_config)
        self.validator = ContextValidator(new_config)

        # Обновление настроек логирования
        if new_config.enable_logging:
            import logging

            logging.basicConfig(level=getattr(logging, new_config.log_level))

        logger.info("Context builder configuration updated")

    def save_config(self, config_path: str | Path) -> None:
        """Сохранение конфигурации в файл"""
        self.config.to_yaml(config_path)
        logger.info(f"Configuration saved to {config_path}")

    def get_config(self) -> ContextConfig:
        """Получение текущей конфигурации"""
        return self.config

    def get_config_dict(self) -> dict[str, Any]:
        """Получение конфигурации в виде словаря"""
        return self.config.to_dict()

    def get_supported_timeframes(self) -> list[str]:
        """Получение поддерживаемых таймфреймов"""
        return list(self.config.timeframe_weights.keys())

    def get_timeframe_weight(self, timeframe: str) -> float:
        """Получение веса таймфрейма"""
        return self.config.get_timeframe_weight(timeframe)

    def is_timeframe_supported(self, timeframe: str) -> bool:
        """Проверка поддержки таймфрейма"""
        return timeframe in self.config.timeframe_weights

    def get_health_status(self) -> dict[str, Any]:
        """Получение статуса здоровья построителя"""
        cache_stats = self.get_cache_stats()

        return {
            "status": "healthy",
            "config_loaded": True,
            "cache_enabled": cache_stats.get("enabled", False),
            "cache_entries": cache_stats.get("total_entries", 0),
            "supported_timeframes": len(self.get_supported_timeframes()),
            "max_workers": self.config.max_workers,
            "timeout_seconds": self.config.timeout_seconds,
            "log_level": self.config.log_level,
        }

    async def health_check(self) -> bool:
        """Проверка здоровья построителя"""
        try:
            # Простая проверка - попытка построить контекст с минимальными данными
            test_data = pd.DataFrame(
                {
                    "close": [100.0, 101.0, 102.0],
                    "volume": [1000, 1100, 1200],
                    "ema_21": [99.5, 100.2, 101.0],
                    "rsi_14": [50.0, 52.0, 54.0],
                    "adx": [20.0, 22.0, 24.0],
                    "macd": [0.1, 0.2, 0.3],
                    "macd_signal": [0.05, 0.15, 0.25],
                    "atr": [1.0, 1.1, 1.2],
                }
            )

            result = await self.build_context(
                symbol="TEST", timeframes=["1H"], features_data={"1H": test_data}
            )

            return result is not None

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
