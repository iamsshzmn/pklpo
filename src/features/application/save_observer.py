"""Observability hooks for features save orchestration."""

from __future__ import annotations

from contextlib import ExitStack
from typing import TYPE_CHECKING

from src.logging import LogAggregator, LogCategory, set_log_context

from ..utils.memlog import memory_monitor

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    import pandas as pd


class SaveObservationSession:
    """Active observation scope around a single save operation."""

    def __init__(
        self,
        *,
        operation: str,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        log_memory: bool,
    ) -> None:
        self._operation = operation
        self._symbol = symbol
        self._timeframe = timeframe
        self._df = df
        self._log_memory = log_memory
        self._stack = ExitStack()
        self._agg: LogAggregator | None = None
        self._mem_log = None

    def __enter__(self) -> SaveObservationSession:
        self._stack.enter_context(
            set_log_context(symbol=self._symbol, timeframe=self._timeframe)
        )
        self._agg = self._stack.enter_context(
            LogAggregator(LogCategory.INSERT, self._operation)
        )
        self._mem_log = self._stack.enter_context(memory_monitor(self._operation))
        if self._log_memory:
            self._mem_log.log_dataframe_memory(self._df, "Batch DataFrame")
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self._stack.close()

    def record_success(self, *, rows_processed: int, rows_saved: int) -> None:
        if self._agg is None:
            return
        self._agg.set_extra("rows", rows_processed)
        self._agg.set_extra("saved", rows_saved)

    def record_error(self, error: Exception | str) -> None:
        if self._agg is None:
            return
        self._agg.add_error(str(error))


class DefaultFeatureSaveObserver:
    """Default observability adapter for save orchestration."""

    def observe(
        self,
        *,
        operation: str,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        log_memory: bool = False,
    ) -> AbstractContextManager[SaveObservationSession]:
        return SaveObservationSession(
            operation=operation,
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            log_memory=log_memory,
        )


def create_feature_save_observer() -> DefaultFeatureSaveObserver:
    """Factory to keep save orchestration injectable."""
    return DefaultFeatureSaveObserver()
