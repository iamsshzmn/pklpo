"""
Вспомогательные утилиты для расчёта индикаторов.

Содержит централизованные минимальные длины окон и проверку входных данных
на достаточность длины перед вызовами ta-библиотек, чтобы избежать
неконсистентных падений и 0%-заполнения из-за прогрева окон.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Минимально необходимая длина ряда для расчёта групп индикаторов
MIN_LENGTHS: dict[str, int] = {
    "bb": 20,
    "kc": 20,
    "kdj": 9,
    "stochrsi": 14,
    "psar": 5,
    "ichimoku": 52,
    "vp": 50,
    "ttm_squeeze": 20,
}


def check_min_length(df: pd.DataFrame, key: str) -> bool:
    """Проверяет, достаточно ли длины ряда для индикатора группы.

    Args:
        df: Входной DataFrame с OHLCV данными
        key: Ключ группы индикаторов (см. MIN_LENGTHS)

    Returns:
        True, если длины достаточно; иначе False
    """
    required = MIN_LENGTHS.get(key, 0)
    return len(df) >= required


def _nan_series(index: pd.Index, name: str) -> pd.Series:
    """Создаёт Series с NaN значениями заданной длины.

    Args:
        index: Индекс для Series
        name: Имя Series

    Returns:
        Series с NaN значениями
    """
    return pd.Series(np.nan, index=index, name=name, dtype="float64")


def _first_col_or_series(
    obj: pd.Series | pd.DataFrame | None, name: str, index: pd.Index
) -> pd.Series:
    """Приводит результат TA-функции к Series с нормализованным индексом.

    Args:
        obj: Результат TA-функции (Series, DataFrame или None)
        name: Имя результирующего Series
        index: Целевой индекс для нормализации

    Returns:
        Series с нормализованным индексом и dtype float64
    """
    if obj is None:
        return _nan_series(index, name)
    if isinstance(obj, pd.Series):
        return obj.reindex(index).astype("float64").rename(name)
    if isinstance(obj, pd.DataFrame):
        if len(obj.columns) == 0:
            return _nan_series(index, name)
        s = obj.iloc[:, 0]
        return s.reindex(index).astype("float64").rename(name)
    return _nan_series(index, name)


def _get_col_by_prefix(df: pd.DataFrame, prefix: str) -> str | None:
    """Находит первую колонку DataFrame, начинающуюся с префикса.

    Args:
        df: DataFrame для поиска
        prefix: Префикс для поиска

    Returns:
        Имя колонки или None, если не найдено
    """
    return next((c for c in df.columns if c.startswith(prefix)), None)
