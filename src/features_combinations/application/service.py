"""Сервис для расчёта и сохранения комбинаций фичей (numeric-only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..logging_config import get_combinations_logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime
    from logging import Logger

    import pandas as pd

    from ..domain.models import CombinationRow
    from ..infrastructure.repository import CombinationRepository
    from .ports import CombinationCalculator, IndicatorProvider


@dataclass(slots=True)
class CombinationService:
    """Сервис для расчёта и сохранения комбинаций фичей."""

    provider: IndicatorProvider
    calculator: CombinationCalculator
    repository: CombinationRepository

    def __post_init__(self) -> None:
        # Logger инициализируется через property при первом обращении
        pass

    @property
    def logger(self) -> Logger:
        """Логгер для сервиса."""
        return get_combinations_logger("service")

    def _log_df_debug(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        stage: str,
    ) -> None:
        """Логирование состояния DataFrame."""
        if df.empty:
            self.logger.warning(
                "Empty DF at stage=%s symbol=%s timeframe=%s",
                stage,
                symbol,
                timeframe,
            )
            return

        self.logger.debug(
            "DF at stage=%s symbol=%s timeframe=%s rows=%d cols=%d",
            stage,
            symbol,
            timeframe,
            len(df),
            len(df.columns),
        )
        self.logger.debug("Columns: %s", df.columns.tolist())
        self.logger.debug("Dtypes:\n%s", df.dtypes)

    async def compute_for_df(
        self,
        symbol: str,
        timeframe: str,
        df_indicators: pd.DataFrame,
    ) -> list[CombinationRow]:
        """
        Рассчитать комбинации фичей для DataFrame индикаторов.

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм
            df_indicators: DataFrame с индикаторами

        Returns:
            Список CombinationRow с числовыми фичами
        """
        if df_indicators.empty:
            self.logger.info(
                "No indicators for symbol=%s timeframe=%s – skip combinations",
                symbol,
                timeframe,
            )
            return []

        self._log_df_debug(df_indicators, symbol, timeframe, "compute_for_df:input")

        rows_iter: Iterable[CombinationRow] = self.calculator.calculate_for_df(
            symbol=symbol,
            timeframe=timeframe,
            df_indicators=df_indicators,
        )
        rows = list(rows_iter)

        self.logger.info(
            "Computed combination rows: symbol=%s timeframe=%s count=%d",
            symbol,
            timeframe,
            len(rows),
        )
        return rows

    async def compute_and_save_for_range(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None,
        end: datetime | None,
        limit: int | None = None,
    ) -> int:
        """
        Рассчитать и сохранить комбинации за период.

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм
            start: Начало периода
            end: Конец периода
            limit: Максимальное количество строк

        Returns:
            Количество сохранённых строк
        """
        self.logger.info(
            "Start combinations symbol=%s timeframe=%s start=%s end=%s limit=%s",
            symbol,
            timeframe,
            start,
            end,
            limit,
        )

        # Преобразуем datetime в timestamp_ms для провайдера
        start_ts = int(start.timestamp() * 1000) if start else None
        end_ts = int(end.timestamp() * 1000) if end else None

        df_indicators = await self.provider.load_indicators(
            symbol=symbol,
            timeframe=timeframe,
            start=start_ts,
            end=end_ts,
            limit=limit,
        )

        self._log_df_debug(
            df_indicators, symbol, timeframe, "compute_and_save:load_indicators"
        )

        if df_indicators.empty:
            self.logger.warning(
                "No indicators loaded for symbol=%s timeframe=%s start=%s end=%s – skip",
                symbol,
                timeframe,
                start,
                end,
            )
            return 0

        rows = await self.compute_for_df(symbol, timeframe, df_indicators)
        if not rows:
            self.logger.warning(
                "No combination rows produced for symbol=%s timeframe=%s",
                symbol,
                timeframe,
            )
            return 0

        saved = await self.repository.upsert_batch(rows)
        self.logger.info(
            "Combination rows saved: symbol=%s timeframe=%s saved=%d",
            symbol,
            timeframe,
            saved,
        )
        return saved

    async def compute_and_save_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> int:
        """
        Рассчитать и сохранить последние N комбинаций.

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм
            limit: Количество последних строк

        Returns:
            Количество сохранённых строк
        """
        return await self.compute_and_save_for_range(
            symbol=symbol,
            timeframe=timeframe,
            start=None,
            end=None,
            limit=limit,
        )
