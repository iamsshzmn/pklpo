"""
Построитель триггеров - основной публичный интерфейс
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..logging_config import create_log_context, get_triggers_logger, log_performance
from .config import TriggersConfig
from .engine import TriggersEngine
from .models import AccelerationType, TriggersMetrics, TriggersRequest, TriggersResult
from .validator import TriggersValidator

logger = get_triggers_logger()


class TriggersBuilder:
    """Построитель триггеров - основной публичный интерфейс"""

    def __init__(self, config: TriggersConfig):
        self.config = config
        self.engine = TriggersEngine(config)
        self.validator = TriggersValidator(config)
        logger.info(f"TriggersBuilder initialized with config: {config.to_dict()}")

    @classmethod
    def from_config_file(cls, config_path: str | Path) -> "TriggersBuilder":
        """Создание построителя из файла конфигурации"""
        config = TriggersConfig.from_yaml(config_path)
        return cls(config)

    @classmethod
    def for_development(cls) -> "TriggersBuilder":
        """Создание построителя для разработки"""
        config = TriggersConfig.for_development()
        return cls(config)

    @classmethod
    def for_production(cls) -> "TriggersBuilder":
        """Создание построителя для продакшена"""
        config = TriggersConfig.for_production()
        return cls(config)

    @log_performance("triggers", "build_triggers")
    async def build_triggers(
        self,
        symbol: str,
        timeframes: list[str],
        features_data: dict[str, pd.DataFrame] | None = None,
        context_data: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> TriggersResult:
        """
        Построение триггеров для заданного символа и таймфреймов.

        Args:
            symbol: Торговый символ (например, 'BTC-USDT')
            timeframes: Список таймфреймов (например, ['1H', '4H'])
            features_data: Данные индикаторов по таймфреймам
            context_data: Данные контекста (опционально)
            timestamp: Временная метка (по умолчанию текущее время)

        Returns:
            TriggersResult: Результат построения триггеров
        """
        with create_log_context(
            "triggers", f"build_triggers_{symbol}", symbol=symbol, timeframes=timeframes
        ):
            logger.info(f"Building triggers for {symbol} with timeframes: {timeframes}")

            # Создание запроса
            request = TriggersRequest(
                symbol=symbol,
                timeframes=timeframes,
                timestamp=timestamp or datetime.now(),
                features_data=features_data,
                context_data=context_data,
            )

            # Построение триггеров через движок
            result = await self.engine.build_triggers(request)

            # Валидация результата
            validation_result = self.validator.validate_triggers_result(result)
            if validation_result.status.value == "error":
                logger.error(
                    f"Triggers result validation failed for {symbol}: {validation_result.errors}"
                )
                result.valid = False
                result.errors.extend(validation_result.errors)
            elif validation_result.status.value == "warning":
                logger.warning(
                    f"Triggers result has warnings for {symbol}: {validation_result.warnings}"
                )

            logger.info(
                f"Triggers built for {symbol}: {len(result.triggers)} timeframes, "
                f"p_up: {result.overall_p_up:.3f}, p_down: {result.overall_p_down:.3f}, "
                f"valid: {result.valid}"
            )
            return result

    async def build_triggers_batch(
        self, requests: list[dict[str, Any]]
    ) -> list[TriggersResult]:
        """
        Пакетное построение триггеров для нескольких символов.

        Args:
            requests: Список запросов, каждый содержит symbol, timeframes, features_data

        Returns:
            List[TriggersResult]: Список результатов построения триггеров
        """
        logger.info(f"Building triggers batch for {len(requests)} requests")

        tasks = []
        for req in requests:
            task = self.build_triggers(
                symbol=req["symbol"],
                timeframes=req["timeframes"],
                features_data=req.get("features_data"),
                context_data=req.get("context_data"),
                timestamp=req.get("timestamp"),
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обработка результатов
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error in batch request {i}: {result}")
                # Создание пустого результата для ошибки
                empty_result = TriggersResult(
                    symbol=requests[i].get("symbol", "UNKNOWN"),
                    timestamp=datetime.now(),
                    triggers={},
                    overall_p_up=0.0,
                    overall_p_down=0.0,
                    dominant_acceleration=AccelerationType.NEUTRAL,
                    micro_filter_passed=False,
                    noise_filter_effectiveness=0.0,
                    valid=False,
                    errors=[str(result)],
                )
                processed_results.append(empty_result)
            else:
                processed_results.append(result)

        logger.info(f"Batch triggers build completed: {len(processed_results)} results")
        return processed_results

    def get_triggers_summary(self, result: TriggersResult) -> dict[str, Any]:
        """
        Получение сводки по результату построения триггеров.

        Args:
            result: Результат построения триггеров

        Returns:
            Dict[str, Any]: Сводка с ключевыми метриками
        """
        summary = {
            "symbol": result.symbol,
            "timestamp": result.timestamp.isoformat(),
            "valid": result.valid,
            "timeframes_count": len(result.triggers),
            "overall_p_up": result.overall_p_up,
            "overall_p_down": result.overall_p_down,
            "net_probability": result.net_probability,
            "dominant_direction": result.dominant_direction,
            "dominant_acceleration": result.dominant_acceleration.value,
            "micro_filter_passed": result.micro_filter_passed,
            "noise_filter_effectiveness": result.noise_filter_effectiveness,
            "has_errors": result.has_errors,
            "errors_count": len(result.errors),
        }

        # Детали по таймфреймам
        timeframe_details = {}
        for timeframe, trigger_data in result.triggers.items():
            timeframe_details[timeframe] = {
                "p_up": trigger_data.p_up,
                "p_down": trigger_data.p_down,
                "net_probability": trigger_data.net_probability,
                "acceleration": trigger_data.accel.value,
                "micro_ok": trigger_data.micro_ok,
                "anti_noise_score": trigger_data.anti_noise_score,
                "confidence": trigger_data.confidence,
                "valid": trigger_data.valid,
            }

        summary["timeframe_details"] = timeframe_details
        return summary

    def get_metrics(self) -> TriggersMetrics:
        """Получение метрик построителя"""
        return self.engine.get_metrics()

    def get_health_status(self) -> dict[str, Any]:
        """
        Получение статуса здоровья построителя.

        Returns:
            Dict[str, Any]: Статус здоровья с различными показателями
        """
        try:
            # Проверка конфигурации
            config_validation = self.validator.validate_config(self.config)

            # Проверка кэша
            cache_stats = self.engine.get_cache_stats()

            # Проверка движка
            engine_healthy = True
            try:
                # Простая проверка - создание тестового запроса
                TriggersRequest(
                    symbol="TEST", timeframes=["1H"], timestamp=datetime.now()
                )
                # Не выполняем, просто проверяем создание
            except Exception as e:
                engine_healthy = False
                logger.error(f"Engine health check failed: {e}")

            return {
                "status": (
                    "healthy"
                    if engine_healthy and config_validation.status.value == "valid"
                    else "unhealthy"
                ),
                "timestamp": datetime.now().isoformat(),
                "config_valid": config_validation.status.value == "valid",
                "config_warnings": (
                    len(config_validation.warnings) if config_validation.warnings else 0
                ),
                "engine_healthy": engine_healthy,
                "cache_enabled": cache_stats["enabled"],
                "cache_size": cache_stats["size"],
                "supported_timeframes": list(self.config.timeframe_weights.keys()),
            }

        except Exception as e:
            logger.error(f"Error checking health status: {e}")
            return {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    def get_cache_stats(self) -> dict[str, Any]:
        """Получение статистики кэша"""
        return self.engine.get_cache_stats()

    def update_config(self, new_config: TriggersConfig):
        """Обновление конфигурации построителя"""
        logger.info("Updating TriggersBuilder configuration")
        self.config = new_config
        self.engine.update_config(new_config)
        self.validator = TriggersValidator(new_config)
        logger.info("TriggersBuilder configuration updated")

    def save_config(self, config_path: str | Path):
        """Сохранение текущей конфигурации в файл"""
        config_path = Path(config_path)
        self.config.to_yaml(config_path)
        logger.info(f"Configuration saved to {config_path}")

    def get_supported_timeframes(self) -> list[str]:
        """Получение списка поддерживаемых таймфреймов"""
        return list(self.config.timeframe_weights.keys())

    def get_config_summary(self) -> dict[str, Any]:
        """Получение сводки по конфигурации"""
        return {
            "min_probability_threshold": self.config.min_probability_threshold,
            "max_probability_threshold": self.config.max_probability_threshold,
            "acceleration_threshold": self.config.acceleration_threshold,
            "micro_filter_threshold": self.config.micro_filter_threshold,
            "noise_filter_threshold": self.config.noise_filter_threshold,
            "supported_timeframes": self.get_supported_timeframes(),
            "timeframe_weights": self.config.timeframe_weights,
            "cache_enabled": self.config.cache_enabled,
            "cache_ttl_seconds": self.config.cache_ttl_seconds,
        }
