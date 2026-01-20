"""
Утилиты для очистки данных перед расчётом индикаторов
"""

import logging

import numpy as np
import pandas as pd


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
        # Более строгая очистка - убираем все проблемные значения
        open_clean = (
            df["open"]
            .replace([None, np.nan, float("inf"), float("-inf")], np.nan)
            .dropna()
        )
        high_clean = (
            df["high"]
            .replace([None, np.nan, float("inf"), float("-inf")], np.nan)
            .dropna()
        )
        low_clean = (
            df["low"]
            .replace([None, np.nan, float("inf"), float("-inf")], np.nan)
            .dropna()
        )
        close_clean = (
            df["close"]
            .replace([None, np.nan, float("inf"), float("-inf")], np.nan)
            .dropna()
        )

        # Проверяем минимальную длину
        min_available_length = min(
            len(open_clean), len(high_clean), len(low_clean), len(close_clean)
        )
        has_sufficient_data = min_available_length >= min_length

        if not has_sufficient_data:
            symbol_name = getattr(df, "name", "unknown")
            timeframe_name = getattr(df, "timeframe", "unknown")
            logging.warning(
                f"Insufficient data after cleaning for {symbol_name} {timeframe_name}: "
                f"need {min_length}+, got {min_available_length} (original: {len(df)})"
            )

        return open_clean, high_clean, low_clean, close_clean, has_sufficient_data

    except Exception as e:
        symbol_name = getattr(df, "name", "unknown")
        timeframe_name = getattr(df, "timeframe", "unknown")
        logging.error(f"Error cleaning data for {symbol_name} {timeframe_name}: {e}")
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
        # Более строгая очистка - убираем все проблемные значения
        close_clean = (
            df["close"]
            .replace([None, np.nan, float("inf"), float("-inf")], np.nan)
            .dropna()
        )

        # Дополнительная проверка - убираем строки где есть None в других колонках
        # Это может влиять на индексацию
        valid_indices = df.index[df["close"].notna() & (df["close"] is not None)]
        close_clean = close_clean.reindex(valid_indices)

        has_sufficient_data = len(close_clean) >= min_length

        if not has_sufficient_data:
            symbol_name = getattr(df, "name", "unknown")
            timeframe_name = getattr(df, "timeframe", "unknown")
            logging.warning(
                f"Insufficient close data after cleaning for {symbol_name} {timeframe_name}: "
                f"need {min_length}+, got {len(close_clean)} (original: {len(df)})"
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
