"""
Main MTF Builder - Главный интерфейс для MTF системы
Использует строгий pipeline: Features → Context → Triggers → Consensus → Integration
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .control.builder import ControlBuilder
from .control.models import ControlConfig
from .database.client import MTFDatabaseClient
from .database.migrations import MTFDatabaseMigrations
from .database.models import (
    MTFConsensusRecord,
    MTFContextRecord,
    MTFPipelineRecord,
    MTFTriggersRecord,
)
from .logging_config import create_log_context, get_mtf_logger

if TYPE_CHECKING:
    from .integration.builder import IntegrationBuilder
    from .pipeline.builder import PipelineBuilder


class MTFBuilder:
    """Главный построитель MTF системы"""

    def __init__(
        self, config: ControlConfig | None = None, database_url: str | None = None
    ):
        self.logger = get_mtf_logger()

        # Инициализация конфигурации
        self.config = config or ControlConfig.default()

        # Инициализация компонентов
        self.control_builder: ControlBuilder | None = None
        self.pipeline_builder: PipelineBuilder | None = None
        self.integration_builder: IntegrationBuilder | None = None

        # База данных
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "postgresql://user:password@localhost/pklpo"
        )
        self.db_client: MTFDatabaseClient | None = None
        self.db_migrations: MTFDatabaseMigrations | None = None

        # Состояние системы
        self.is_initialized = False
        self.is_running = False

        self.logger.info("MTFBuilder initialized")

    async def initialize(self) -> None:
        """Инициализация всей MTF системы"""
        with create_log_context("mtf_builder", "initialize"):
            try:
                self.logger.info("Initializing MTF system...")

                # 1. Инициализация базы данных
                await self._initialize_database()

                # 2. Инициализация Control системы
                self.control_builder = ControlBuilder(self.config)
                await self.control_builder.initialize()
                self.logger.info("Control system initialized")

                # 3. Запуск системы через Control
                control_result = await self.control_builder.start_system()
                if not control_result.success:
                    raise Exception(f"Failed to start system: {control_result.message}")

                # 3. Получение инициализированных компонентов
                self.pipeline_builder = self.control_builder.engine.pipeline_builder
                self.integration_builder = (
                    self.control_builder.engine.integration_builder
                )

                self.is_initialized = True
                self.is_running = True

                self.logger.info("MTF system initialized successfully")

            except Exception as e:
                self.logger.error(f"Failed to initialize MTF system: {e}")
                raise

    async def _initialize_database(self) -> None:
        """Инициализация базы данных MTF"""
        try:
            # Проверяем, нужно ли инициализировать БД
            if (
                not self.database_url
                or self.database_url == "postgresql://user:password@localhost/pklpo"
            ):
                self.logger.info(
                    "Database URL not provided or default, skipping database initialization"
                )
                self.db_client = None
                self.db_migrations = None
                return

            # Инициализация клиента базы данных
            self.db_client = MTFDatabaseClient(self.database_url)
            await self.db_client.initialize()

            # Запуск миграций
            self.db_migrations = MTFDatabaseMigrations(self.database_url)
            await self.db_migrations.run_migrations()

            self.logger.info("MTF database initialized successfully")

        except Exception as e:
            self.logger.warning(f"Failed to initialize MTF database: {e}")
            self.logger.info("Continuing without database support")
            self.db_client = None
            self.db_migrations = None

    async def process_symbol(
        self,
        symbol: str,
        timeframes: list[str],
        features_data: dict[str, Any] | None = None,
        request_id: str | None = None,
        use_real_data: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Обработка одного символа через строгий pipeline

        Pipeline: Features → Context → Triggers → Consensus → Integration
        """
        with create_log_context("mtf_builder", "process_symbol"):
            if not self.is_initialized or not self.is_running:
                raise Exception("MTF system not initialized or not running")

            request_id = request_id or str(uuid.uuid4())
            start_time = datetime.now()

            try:
                self.logger.info(
                    f"Processing symbol {symbol} with timeframes {timeframes}"
                )

                # Получение данных features из БД если не переданы
                if features_data is None and use_real_data and self.db_client:
                    features_data = await self.db_client.get_features_data(
                        symbol, timeframes
                    )
                    if not features_data:
                        self.logger.warning(
                            f"No features data found for {symbol}, using test data"
                        )
                        features_data = self._create_test_features_data(
                            symbol, timeframes
                        )
                elif features_data is None:
                    features_data = self._create_test_features_data(symbol, timeframes)

                # Этап 1: Features → Context → Triggers → Consensus (Pipeline)
                pipeline_result = await self.pipeline_builder.process_single(
                    symbol=symbol,
                    timeframes=timeframes,
                    features_data=features_data,
                    request_id=request_id,
                    **kwargs,
                )

                if not pipeline_result.is_successful:
                    raise Exception(
                        f"Pipeline processing failed: {pipeline_result.errors}"
                    )

                # Сохранение результатов в БД
                if self.db_client:
                    await self._save_pipeline_results(
                        symbol, timeframes, pipeline_result, start_time
                    )

                # Этап 2: Integration (сохранение и уведомления)
                integration_result = await self.integration_builder.process_single(
                    symbol=symbol,
                    timeframes=timeframes,
                    data_sources=["cache"],  # Используем кэш для быстрой обработки
                    notification_types=["log"],  # Только логирование
                    request_id=request_id,
                    pipeline_result=pipeline_result,  # Передаем полный результат pipeline
                )

                # Формирование результата
                result = {
                    "request_id": request_id,
                    "symbol": symbol,
                    "timeframes": timeframes,
                    "success": True,
                    "processing_time_seconds": (
                        datetime.now() - start_time
                    ).total_seconds(),
                    "pipeline_result": {
                        "context": pipeline_result.context_result,
                        "triggers": pipeline_result.triggers_result,
                        "consensus": pipeline_result.consensus_result,
                        "status": pipeline_result.status.value,
                        "processing_stage": pipeline_result.processing_stage.value,
                    },
                    "integration_result": {
                        "status": integration_result.status.value,
                        "successful": integration_result.is_successful,
                    },
                    "metadata": {
                        "start_time": start_time.isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "mtf_version": "3.0.0",
                    },
                }

                self.logger.info(
                    f"Symbol {symbol} processed successfully in {result['processing_time_seconds']:.3f}s"
                )
                return result

            except Exception as e:
                self.logger.error(f"Failed to process symbol {symbol}: {e}")
                return {
                    "request_id": request_id,
                    "symbol": symbol,
                    "timeframes": timeframes,
                    "success": False,
                    "error": str(e),
                    "processing_time_seconds": (
                        datetime.now() - start_time
                    ).total_seconds(),
                    "metadata": {
                        "start_time": start_time.isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "mtf_version": "3.0.0",
                    },
                }

    async def process_batch(
        self,
        symbols: list[str],
        timeframes: list[str],
        features_data: dict[str, dict[str, Any]] | None = None,
        max_concurrent: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Пакетная обработка символов через строгий pipeline
        """
        with create_log_context("mtf_builder", "process_batch"):
            if not self.is_initialized or not self.is_running:
                raise Exception("MTF system not initialized or not running")

            batch_id = str(uuid.uuid4())
            start_time = datetime.now()

            try:
                self.logger.info(f"Processing batch of {len(symbols)} symbols")

                # Ограничение параллельности
                max_concurrent = max_concurrent or self.config.max_workers
                semaphore = asyncio.Semaphore(max_concurrent)

                async def process_single_with_semaphore(symbol: str) -> dict[str, Any]:
                    async with semaphore:
                        symbol_features = (
                            features_data.get(symbol) if features_data else None
                        )
                        return await self.process_symbol(
                            symbol=symbol,
                            timeframes=timeframes,
                            features_data=symbol_features,
                            **kwargs,
                        )

                # Параллельная обработка символов
                tasks = [process_single_with_semaphore(symbol) for symbol in symbols]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Обработка результатов
                processed_results = {}
                successful_count = 0
                failed_count = 0

                for i, result in enumerate(results):
                    symbol = symbols[i]

                    if isinstance(result, Exception):
                        processed_results[symbol] = {
                            "success": False,
                            "error": str(result),
                            "symbol": symbol,
                        }
                        failed_count += 1
                    else:
                        processed_results[symbol] = result
                        if result.get("success", False):
                            successful_count += 1
                        else:
                            failed_count += 1

                # Формирование результата пакета
                batch_result = {
                    "batch_id": batch_id,
                    "symbols": symbols,
                    "timeframes": timeframes,
                    "total_symbols": len(symbols),
                    "successful_symbols": successful_count,
                    "failed_symbols": failed_count,
                    "success_rate": successful_count / len(symbols) if symbols else 0.0,
                    "processing_time_seconds": (
                        datetime.now() - start_time
                    ).total_seconds(),
                    "results": processed_results,
                    "metadata": {
                        "start_time": start_time.isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "mtf_version": "3.0.0",
                        "max_concurrent": max_concurrent,
                    },
                }

                self.logger.info(
                    f"Batch processed: {successful_count}/{len(symbols)} successful"
                )
                return batch_result

            except Exception as e:
                self.logger.error(f"Failed to process batch: {e}")
                return {
                    "batch_id": batch_id,
                    "symbols": symbols,
                    "timeframes": timeframes,
                    "success": False,
                    "error": str(e),
                    "processing_time_seconds": (
                        datetime.now() - start_time
                    ).total_seconds(),
                    "metadata": {
                        "start_time": start_time.isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "mtf_version": "3.0.0",
                    },
                }

    async def get_system_status(self) -> dict[str, Any]:
        """Получение статуса системы"""
        if not self.control_builder:
            return {"status": "not_initialized", "message": "System not initialized"}

        control_result = await self.control_builder.get_system_status()
        return control_result.component_results or {}

    async def health_check(self) -> dict[str, Any]:
        """Проверка здоровья системы"""
        if not self.control_builder:
            return {"healthy": False, "message": "System not initialized"}

        control_result = await self.control_builder.health_check()
        return control_result.component_results or {}

    async def get_metrics(self) -> dict[str, Any]:
        """Получение метрик системы"""
        if not self.control_builder:
            return {"error": "System not initialized"}

        control_result = await self.control_builder.get_metrics()
        return control_result.component_results or {}

    async def configure_system(self, config_updates: dict[str, Any]) -> bool:
        """Конфигурация системы"""
        if not self.control_builder:
            return False

        control_result = await self.control_builder.configure_system(config_updates)
        return control_result.success

    async def restart_system(self) -> bool:
        """Перезапуск системы"""
        if not self.control_builder:
            return False

        control_result = await self.control_builder.restart_system()
        return control_result.success

    async def stop_system(self) -> bool:
        """Остановка системы"""
        if not self.control_builder:
            return True

        control_result = await self.control_builder.stop_system()
        self.is_running = False
        return control_result.success

    async def cleanup(self) -> None:
        """Очистка ресурсов"""
        try:
            if self.control_builder:
                await self.control_builder.cleanup()

            self.is_initialized = False
            self.is_running = False

            self.logger.info("MTF system cleaned up successfully")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def _create_test_features_data(
        self, symbol: str, timeframes: list[str]
    ) -> dict[str, Any]:
        """Создание тестовых данных features"""
        import numpy as np
        import pandas as pd

        features_data = {}

        for timeframe in timeframes:
            # Создаем тестовые данные OHLCV
            dates = pd.date_range(start="2024-01-01", periods=100, freq="15min")
            np.random.seed(42)  # Для воспроизводимости

            # Генерируем реалистичные OHLCV данные
            base_price = 50000 if "BTC" in symbol else 3000
            returns = np.random.normal(0, 0.02, 100)
            prices = [base_price]

            for ret in returns[1:]:
                prices.append(prices[-1] * (1 + ret))

            df = pd.DataFrame(
                {
                    "timestamp": dates,
                    "open": prices,
                    "high": [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
                    "low": [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
                    "close": prices,
                    "volume": np.random.uniform(1000, 10000, 100),
                }
            )

            # Добавляем технические индикаторы
            df["rsi"] = 50 + np.random.normal(0, 15, 100)
            df["rsi_14"] = df["rsi"]  # Дублируем для совместимости
            df["macd"] = np.random.normal(0, 100, 100)
            df["bb_upper"] = df["close"] * 1.02
            df["bb_lower"] = df["close"] * 0.98
            df["atr"] = df["close"] * 0.01

            features_data[timeframe] = df

        return features_data

    async def _save_pipeline_results(
        self,
        symbol: str,
        timeframes: list[str],
        pipeline_result: Any,
        start_time: datetime,
    ) -> None:
        """Сохранение результатов pipeline в базу данных"""
        try:
            processing_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            # Сохранение Context результатов
            context_id = None
            if pipeline_result.context_result:
                context_record = MTFContextRecord(
                    symbol=symbol,
                    timeframe=timeframes[0],  # Берем первый таймфрейм
                    timestamp=datetime.now(),
                    dominant_regime=pipeline_result.context_result.dominant_regime,
                    regime_confidence=pipeline_result.context_result.regime_confidence,
                    overall_score=pipeline_result.context_result.overall_score,
                    timeframe_results=pipeline_result.context_result.timeframe_results,
                    valid=pipeline_result.context_result.valid,
                    errors=pipeline_result.context_result.errors,
                    processing_time_ms=pipeline_result.context_result.processing_time_ms,
                )
                context_id = await self.db_client.save_context_result(context_record)

            # Сохранение Triggers результатов
            triggers_id = None
            if pipeline_result.triggers_result:
                triggers_record = MTFTriggersRecord(
                    symbol=symbol,
                    timeframe=timeframes[0],
                    timestamp=datetime.now(),
                    overall_p_up=pipeline_result.triggers_result.overall_p_up,
                    overall_p_down=pipeline_result.triggers_result.overall_p_down,
                    acceleration_type=pipeline_result.triggers_result.acceleration_type,
                    acceleration_strength=pipeline_result.triggers_result.acceleration_strength,
                    micro_ok=pipeline_result.triggers_result.micro_ok,
                    micro_filter_score=pipeline_result.triggers_result.micro_filter_score,
                    timeframe_results=pipeline_result.triggers_result.timeframe_results,
                    valid=pipeline_result.triggers_result.valid,
                    errors=pipeline_result.triggers_result.errors,
                    processing_time_ms=pipeline_result.triggers_result.processing_time_ms,
                )
                triggers_id = await self.db_client.save_triggers_result(triggers_record)

            # Сохранение Consensus результатов
            consensus_id = None
            if pipeline_result.consensus_result:
                consensus_record = MTFConsensusRecord(
                    symbol=symbol,
                    timeframes=timeframes,
                    timestamp=datetime.now(),
                    consensus_type=pipeline_result.consensus_result.consensus_type,
                    confidence_level=pipeline_result.consensus_result.confidence_level,
                    consensus_score=pipeline_result.consensus_result.consensus_score,
                    context_weight=pipeline_result.consensus_result.context_weight,
                    triggers_weight=pipeline_result.consensus_result.triggers_weight,
                    coverage_ratio=pipeline_result.consensus_result.coverage_ratio,
                    disagreement_ratio=pipeline_result.consensus_result.disagreement_ratio,
                    veto_applied=pipeline_result.consensus_result.veto_applied,
                    veto_reasons=pipeline_result.consensus_result.veto_reasons,
                    timeframe_consensus=pipeline_result.consensus_result.timeframe_consensus,
                    evidence_summary=pipeline_result.consensus_result.evidence_summary,
                    valid=pipeline_result.consensus_result.valid,
                    errors=pipeline_result.consensus_result.errors,
                    processing_time_ms=pipeline_result.consensus_result.processing_time_ms,
                )
                consensus_id = await self.db_client.save_consensus_result(
                    consensus_record
                )

            # Сохранение Pipeline результатов
            pipeline_record = MTFPipelineRecord(
                symbol=symbol,
                timeframes=timeframes,
                timestamp=datetime.now(),
                status=pipeline_result.status,
                processing_stage=pipeline_result.processing_stage,
                context_id=context_id,
                triggers_id=triggers_id,
                consensus_id=consensus_id,
                total_processing_time_ms=processing_time_ms,
                errors=pipeline_result.errors,
                warnings=pipeline_result.warnings,
            )
            await self.db_client.save_pipeline_result(pipeline_record)

            self.logger.debug(f"Pipeline results saved for {symbol}")

        except Exception as e:
            self.logger.error(f"Failed to save pipeline results for {symbol}: {e}")

    # Методы для работы с данными

    async def get_latest_results(self, symbols: list[str] | None = None) -> list[Any]:
        """Получение последних результатов MTF анализа"""
        if not self.db_client:
            raise Exception("Database client not initialized")

        return await self.db_client.get_latest_results(symbols)

    async def get_statistics(self, hours: int = 24) -> list[dict[str, Any]]:
        """Получение статистики MTF системы"""
        if not self.db_client:
            raise Exception("Database client not initialized")

        return await self.db_client.get_statistics(hours)

    async def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """Очистка старых данных"""
        if not self.db_migrations:
            raise Exception("Database migrations not initialized")

        await self.db_migrations.cleanup_old_data(days_to_keep)

    def is_system_ready(self) -> bool:
        """Проверка готовности системы"""
        return self.is_initialized and self.is_running

    def get_supported_timeframes(self) -> list[str]:
        """Получение поддерживаемых таймфреймов"""
        return ["1m", "5m", "15m", "1H", "4H", "1D", "1W", "1M"]

    def get_supported_symbols(self) -> list[str]:
        """Получение поддерживаемых символов (пример)"""
        return ["BTC-USDT", "ETH-USDT", "BNB-USDT", "ADA-USDT", "SOL-USDT"]

    def get_system_info(self) -> dict[str, Any]:
        """Получение информации о системе"""
        return {
            "mtf_version": "3.0.0",
            "is_initialized": self.is_initialized,
            "is_running": self.is_running,
            "supported_timeframes": self.get_supported_timeframes(),
            "supported_symbols": self.get_supported_symbols(),
            "pipeline_flow": "Features → Context → Triggers → Consensus → Integration",
            "components": {
                "control": self.control_builder is not None,
                "pipeline": self.pipeline_builder is not None,
                "integration": self.integration_builder is not None,
            },
        }

    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        await self.cleanup()
