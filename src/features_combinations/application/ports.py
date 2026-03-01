"""Порты (интерфейсы) для application layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pandas as pd

    from ..domain.models import CombinationRow


class IndicatorProvider(Protocol):
    """Провайдер для загрузки индикаторов из БД."""

    async def load_indicators(
        self,
        symbol: str,
        timeframe: str,
        start: int | None = None,  # timestamp_ms
        end: int | None = None,  # timestamp_ms
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Загрузить индикаторы из БД.

        Returns:
            DataFrame с колонками timestamp и индикаторами
        """
        ...


class CombinationCalculator(Protocol):
    """Калькулятор комбинаций фичей (numeric-only)."""

    def calculate_for_df(
        self,
        symbol: str,
        timeframe: str,
        df_indicators: pd.DataFrame,
    ) -> Iterable[CombinationRow]:
        """
        Рассчитать комбинации фичей для DataFrame индикаторов.

        Все "направления", "силы", "режимы" кодируются числами в .features,
        например:
        {
            "direction_num": 1.0,          # 1 = up, -1 = down, 0 = flat
            "trend_score": 0.78,
            "vol_regime": 2.0,             # 0/1/2 — кластеры волатильности
        }

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм
            df_indicators: DataFrame с индикаторами (должен содержать timestamp)

        Yields:
            CombinationRow с числовыми фичами
        """
        ...
