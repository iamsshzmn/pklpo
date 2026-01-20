"""
Утилиты для очистки данных перед расчётом индикаторов
"""

import logging

import numpy as np
import pandas as pd


def _clean_series(series: pd.Series) -> pd.Series:
    """Универсальная очистка серии от проблемных значений"""
    return series.replace([None, np.nan, float("inf"), float("-inf")], np.nan).dropna()


def _log_insufficient_data(
    symbol_name: str,
    timeframe_name: str,
    min_length: int,
    actual_length: int,
    original_length: int,
):
    """Универсальное логирование недостатка данных"""
    logging.warning(
        f"Insufficient data after cleaning for {symbol_name} {timeframe_name}: need {min_length}+, got {actual_length} (original: {original_length})"
    )


def clean_ohlcv_data(
    df: pd.DataFrame, min_length: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, bool]:
    """
    Очищает OHLCV данные от None и NaN значений

    Args:
        df: DataFrame с OHLCV данными
        min_length: минимальная длина данных для расчёта индикаторов

    Returns:
        tuple: (open_clean, high_clean, low_clean, close_clean, has_sufficient_data)
    """
    try:
        open_clean = _clean_series(df["open"])
        high_clean = _clean_series(df["high"])
        low_clean = _clean_series(df["low"])
        close_clean = _clean_series(df["close"])

        # Проверяем минимальную длину
        min_available_length = min(
            len(open_clean), len(high_clean), len(low_clean), len(close_clean)
        )
        has_sufficient_data = min_available_length >= min_length

        if not has_sufficient_data:
            symbol_name = getattr(df, "name", "unknown")
            timeframe_name = getattr(df, "timeframe", "unknown")
            _log_insufficient_data(
                symbol_name, timeframe_name, min_length, min_available_length, len(df)
            )

        return open_clean, high_clean, low_clean, close_clean, has_sufficient_data

    except Exception as e:
        symbol_name = getattr(df, "name", "unknown")
        timeframe_name = getattr(df, "timeframe", "unknown")
        logging.error(
            f"Error cleaning OHLCV data for {symbol_name} {timeframe_name}: {e}"
        )
        return pd.Series(), pd.Series(), pd.Series(), pd.Series(), False


def clean_close_data(df: pd.DataFrame, min_length: int = 14) -> tuple[pd.Series, bool]:
    """
    Очищает только close данные для простых индикаторов (RSI, MACD)

    Args:
        df: DataFrame с OHLCV данными
        min_length: минимальная длина данных для расчёта индикаторов

    Returns:
        tuple: (close_clean, has_sufficient_data)
    """
    try:
        close_clean = _clean_series(df["close"])

        # Дополнительная проверка индексации
        valid_indices = df.index[df["close"].notna() & (df["close"] is not None)]
        close_clean = close_clean.reindex(valid_indices)

        has_sufficient_data = len(close_clean) >= min_length

        if not has_sufficient_data:
            symbol_name = getattr(df, "name", "unknown")
            timeframe_name = getattr(df, "timeframe", "unknown")
            _log_insufficient_data(
                symbol_name, timeframe_name, min_length, len(close_clean), len(df)
            )

        return close_clean, has_sufficient_data

    except Exception as e:
        symbol_name = getattr(df, "name", "unknown")
        timeframe_name = getattr(df, "timeframe", "unknown")
        logging.error(
            f"Error cleaning close data for {symbol_name} {timeframe_name}: {e}"
        )
        return pd.Series(), False


def create_nan_series(df: pd.DataFrame, length: int | None = None) -> pd.Series:
    """
    Создаёт серию с NaN значениями той же длины что и исходный DataFrame

    Args:
        df: исходный DataFrame
        length: длина серии (если не указана, берётся длина df)

    Returns:
        pd.Series с NaN значениями
    """
    if length is None:
        length = len(df)
    return pd.Series([np.nan] * length, index=df.index)
