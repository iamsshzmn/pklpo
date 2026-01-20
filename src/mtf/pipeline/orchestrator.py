"""
Основной оркестратор пайплайна
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from .config import PipelineConfig
from .coordinator import PipelineCoordinator
from .models import (
    BatchPipelineResult,
    ExecutionMetrics,
    PipelineResult,
    PipelineStatus,
)
from .monitor import PipelineMonitor


class PipelineOrchestrator:
    """Основной оркестратор пайплайна"""

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig.default()
        self.monitor = PipelineMonitor(self.config.enable_monitoring)
        self.coordinator = PipelineCoordinator(self.config, self.monitor)

    async def run_pipeline(
        self, symbol: str, run_id: str | None = None
    ) -> PipelineResult:
        """
        Запуск пайплайна для одного символа

        Args:
            symbol: Символ для анализа
            run_id: ID запуска (генерируется автоматически если не указан)

        Returns:
            PipelineResult: Результат выполнения пайплайна
        """
        if run_id is None:
            run_id = str(uuid.uuid4())

        start_time = datetime.now()
        self.monitor.start_monitoring(run_id, symbol)

        try:
            # Выполнение пайплайна с таймаутом
            stages_result = await asyncio.wait_for(
                self.coordinator.coordinate_full_pipeline(symbol, run_id),
                timeout=self.config.timeout_seconds,
            )

            context_result, triggers_result, consensus_result = stages_result

            # Определение общего статуса
            if all(stage.status.value == "completed" for stage in stages_result):
                status = PipelineStatus.COMPLETED
            elif any(stage.status.value == "failed" for stage in stages_result):
                status = PipelineStatus.FAILED
            else:
                status = PipelineStatus.COMPLETED  # Если есть completed и skipped

            # Сбор ошибок и предупреждений
            all_errors = []
            all_warnings = []
            for stage in stages_result:
                all_errors.extend(stage.errors)
                all_warnings.extend(stage.warnings)

            # Получение метрик выполнения
            execution_metrics = self.monitor.stop_monitoring(
                run_id, status, all_errors, all_warnings
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Создание результата
            return PipelineResult(
                run_id=run_id,
                symbol=symbol,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                stages={
                    "context": context_result,
                    "triggers": triggers_result,
                    "consensus": consensus_result,
                },
                context_result=context_result.metadata.get("context_result"),
                triggers_result=triggers_result.metadata.get("triggers_result"),
                consensus_result=consensus_result.metadata.get("consensus_result"),
                execution_metrics=execution_metrics,
                errors=all_errors,
                warnings=all_warnings,
                metadata={
                    "config": {
                        "context_timeframes": self.config.context_timeframes,
                        "trigger_timeframes": self.config.trigger_timeframes,
                        "consensus_horizons": self.config.consensus_horizons,
                    },
                    "stages_summary": {
                        stage.stage_name: {
                            "status": stage.status.value,
                            "duration": stage.duration_seconds,
                            "successful": stage.symbols_successful,
                            "failed": stage.symbols_failed,
                        }
                        for stage in stages_result
                    },
                },
            )

        except TimeoutError:
            # Обработка таймаута
            execution_metrics = self.monitor.stop_monitoring(
                run_id, PipelineStatus.FAILED, ["Pipeline timeout"], []
            )

            return PipelineResult(
                run_id=run_id,
                symbol=symbol,
                status=PipelineStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                stages={},
                context_result=None,
                triggers_result=None,
                consensus_result=None,
                execution_metrics=execution_metrics,
                errors=["Pipeline timeout"],
                warnings=[],
                metadata={},
            )

        except Exception as e:
            # Обработка других ошибок
            execution_metrics = self.monitor.stop_monitoring(
                run_id, PipelineStatus.FAILED, [str(e)], []
            )

            return PipelineResult(
                run_id=run_id,
                symbol=symbol,
                status=PipelineStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                stages={},
                context_result=None,
                triggers_result=None,
                consensus_result=None,
                execution_metrics=execution_metrics,
                errors=[str(e)],
                warnings=[],
                metadata={},
            )

    async def run_batch_pipeline(
        self, symbols: list[str], run_id: str | None = None
    ) -> BatchPipelineResult:
        """
        Запуск пайплайна для нескольких символов

        Args:
            symbols: Список символов
            run_id: ID запуска (генерируется автоматически если не указан)

        Returns:
            BatchPipelineResult: Результат выполнения пакетного пайплайна
        """
        if run_id is None:
            run_id = str(uuid.uuid4())

        start_time = datetime.now()

        try:
            # Выполнение пакетного пайплайна
            batch_results = await asyncio.wait_for(
                self.coordinator.coordinate_batch_pipeline(symbols, run_id),
                timeout=self.config.timeout_seconds
                * len(symbols),  # Увеличиваем таймаут для пакета
            )

            # Создание результатов для каждого символа
            individual_results = {}
            all_errors = []
            all_warnings = []

            for symbol, stages_result in batch_results.items():
                context_result, triggers_result, consensus_result = stages_result

                # Определение статуса для символа
                if all(stage.status.value == "completed" for stage in stages_result):
                    status = PipelineStatus.COMPLETED
                elif any(stage.status.value == "failed" for stage in stages_result):
                    status = PipelineStatus.FAILED
                else:
                    status = PipelineStatus.COMPLETED

                # Сбор ошибок и предупреждений
                symbol_errors = []
                symbol_warnings = []
                for stage in stages_result:
                    symbol_errors.extend(stage.errors)
                    symbol_warnings.extend(stage.warnings)

                all_errors.extend(symbol_errors)
                all_warnings.extend(symbol_warnings)

                # Создание результата для символа
                individual_results[symbol] = PipelineResult(
                    run_id=f"{run_id}_{symbol}",
                    symbol=symbol,
                    status=status,
                    start_time=start_time,
                    end_time=datetime.now(),
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    stages={
                        "context": context_result,
                        "triggers": triggers_result,
                        "consensus": consensus_result,
                    },
                    context_result=context_result.metadata.get("context_result"),
                    triggers_result=triggers_result.metadata.get("triggers_result"),
                    consensus_result=consensus_result.metadata.get("consensus_result"),
                    execution_metrics=ExecutionMetrics(
                        start_time=start_time,
                        end_time=datetime.now(),
                        duration_seconds=(datetime.now() - start_time).total_seconds(),
                        memory_usage_mb=0.0,
                        cpu_usage_percent=0.0,
                        symbols_processed=1,
                        symbols_successful=(
                            1 if status == PipelineStatus.COMPLETED else 0
                        ),
                        symbols_failed=1 if status == PipelineStatus.FAILED else 0,
                        errors_count=len(symbol_errors),
                        warnings_count=len(symbol_warnings),
                    ),
                    errors=symbol_errors,
                    warnings=symbol_warnings,
                    metadata={},
                )

            # Определение общего статуса пакета
            successful_count = sum(
                1
                for result in individual_results.values()
                if result.status == PipelineStatus.COMPLETED
            )

            if successful_count == len(symbols):
                batch_status = PipelineStatus.COMPLETED
            elif successful_count > 0:
                batch_status = PipelineStatus.COMPLETED  # Частичный успех
            else:
                batch_status = PipelineStatus.FAILED

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Создание результата пакета
            return BatchPipelineResult(
                run_id=run_id,
                symbols=symbols,
                status=batch_status,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                results=individual_results,
                execution_metrics=ExecutionMetrics(
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    memory_usage_mb=0.0,
                    cpu_usage_percent=0.0,
                    symbols_processed=len(symbols),
                    symbols_successful=successful_count,
                    symbols_failed=len(symbols) - successful_count,
                    errors_count=len(all_errors),
                    warnings_count=len(all_warnings),
                ),
                errors=all_errors,
                warnings=all_warnings,
                metadata={
                    "config": {
                        "context_timeframes": self.config.context_timeframes,
                        "trigger_timeframes": self.config.trigger_timeframes,
                        "consensus_horizons": self.config.consensus_horizons,
                        "parallel_processing": self.config.parallel_processing,
                        "max_workers": self.config.max_workers,
                    },
                    "summary": {
                        "total_symbols": len(symbols),
                        "successful_symbols": successful_count,
                        "failed_symbols": len(symbols) - successful_count,
                        "success_rate": (
                            successful_count / len(symbols) if symbols else 0.0
                        ),
                    },
                },
            )

        except TimeoutError:
            # Обработка таймаута пакета
            return BatchPipelineResult(
                run_id=run_id,
                symbols=symbols,
                status=PipelineStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                results={},
                execution_metrics=ExecutionMetrics(
                    start_time=start_time,
                    end_time=datetime.now(),
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    memory_usage_mb=0.0,
                    cpu_usage_percent=0.0,
                    symbols_processed=len(symbols),
                    symbols_successful=0,
                    symbols_failed=len(symbols),
                    errors_count=1,
                    warnings_count=0,
                ),
                errors=["Batch pipeline timeout"],
                warnings=[],
                metadata={},
            )

        except Exception as e:
            # Обработка других ошибок пакета
            return BatchPipelineResult(
                run_id=run_id,
                symbols=symbols,
                status=PipelineStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                results={},
                execution_metrics=ExecutionMetrics(
                    start_time=start_time,
                    end_time=datetime.now(),
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    memory_usage_mb=0.0,
                    cpu_usage_percent=0.0,
                    symbols_processed=len(symbols),
                    symbols_successful=0,
                    symbols_failed=len(symbols),
                    errors_count=1,
                    warnings_count=0,
                ),
                errors=[str(e)],
                warnings=[],
                metadata={},
            )

    def get_pipeline_health(self) -> Any:
        """Получение состояния здоровья пайплайна"""
        return self.monitor.get_pipeline_health()

    def get_execution_metrics(self, hours: int = 24) -> dict[str, Any]:
        """Получение метрик выполнения"""
        return self.monitor.get_execution_metrics(hours)

    def get_config(self) -> PipelineConfig:
        """Получение конфигурации"""
        return self.config

    def update_config(self, config: PipelineConfig) -> None:
        """Обновление конфигурации"""
        self.config = config
        self.coordinator = PipelineCoordinator(config, self.monitor)
