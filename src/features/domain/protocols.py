"""
Domain protocols (абстракции) для расчета индикаторов.

Вводим минимальный протокол без изменения текущего поведения
и без обязательной имплементации существующими модулями.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@runtime_checkable
class IndicatorCalculator(Protocol):
    """Абстракция вычислителя одного индикатора.

    Реализации могут опираться на pandas_ta или кастомную логику.
    """

    def calculate(self, df_ohlcv: pd.DataFrame, **params) -> pd.Series: ...


@runtime_checkable
class BatchIndicatorCalculator(Protocol):
    """Абстракция пакетного вычислителя множества индикаторов.

    Совместима с текущим API: принимает df и множество имен индикаторов,
    возвращает dict[name -> Series] или DataFrame.
    """

    def calculate_many(
        self, df_ohlcv: pd.DataFrame, names: set[str], **params
    ) -> dict[str, pd.Series] | pd.DataFrame: ...
