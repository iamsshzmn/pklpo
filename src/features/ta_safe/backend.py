"""
Backend functions for pandas_ta integration.

This module provides functions for detecting available pandas_ta functions
and safely calling them with proper error handling.
"""

import warnings

import pandas as pd

from src.logging import get_logger

from .constants import ALLOW
from .errors import FeatureCalcError
from .normalization import _normalize_to_df
from .validation import _ensure_input

logger = get_logger(__name__)

# Автодетект доступных функций
_AVAILABLE_FUNCTIONS: set[str] | None = None


def _detect_available_functions() -> set[str]:
    """
    Автоматическое определение доступных функций.

    Returns:
        Множество доступных имён функций pandas_ta
    """
    available: set[str] = set()

    # Проверяем pandas_ta
    try:
        df_test = pd.DataFrame(
            {
                "open": [1, 2, 3],
                "high": [2, 3, 4],
                "low": [1, 2, 3],
                "close": [2, 3, 4],
                "volume": [100, 200, 300],
            }
        )

        for func in ALLOW:
            if hasattr(df_test.ta, func):
                try:
                    # Пробуем вызвать функцию
                    result = getattr(df_test.ta, func)()
                    if result is not None:
                        available.add(func)
                except Exception as e:
                    logger.debug(f"Function {func} not available: {e}")
    except Exception as e:
        logger.debug(f"Failed to detect available functions: {e}")

    return available


def _get_available_functions() -> set[str]:
    """
    Получить множество доступных функций (с ленивой инициализацией).

    Returns:
        Множество доступных имён функций pandas_ta
    """
    global _AVAILABLE_FUNCTIONS
    if _AVAILABLE_FUNCTIONS is None:
        _AVAILABLE_FUNCTIONS = _detect_available_functions()
        logger.info(
            f"Available functions detected: {len(_AVAILABLE_FUNCTIONS)}/{len(ALLOW)}"
        )
    return _AVAILABLE_FUNCTIONS


def safe_ta(
    df: pd.DataFrame, name: str, /, **kwargs: dict[str, object]
) -> pd.DataFrame:
    """
    Универсальный безопасный вызов pandas_ta функций с нормализацией к DataFrame.

    Args:
        df: DataFrame с OHLCV данными
        name: Имя функции pandas_ta
        **kwargs: Параметры функции

    Returns:
        pd.DataFrame (всегда)

    Raises:
        FeatureCalcError: При любой ошибке
    """
    _ensure_input(df)

    if name not in ALLOW:
        raise FeatureCalcError(f"ta.{name} запрещён")

    try:
        accessor = df.ta
        func = getattr(accessor, name)
    except Exception as e:
        raise FeatureCalcError("pandas_ta недоступен или ta.{name} не найден") from e

    try:
        # Подавляем FutureWarning о несовместимых типах внутри pandas_ta
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=FutureWarning, message=".*incompatible dtype.*"
            )
            out = func(**kwargs)
        # Приводим типы сразу после получения результата, чтобы избежать FutureWarning
        # pandas_ta может возвращать DataFrame с int64 колонками, которые потом заполняются float значениями
        if isinstance(out, pd.DataFrame):
            # Создаём копию и приводим все числовые колонки к float64
            out = out.copy()
            for col in out.columns:
                if out[col].dtype in ["int64", "int32", "int16", "int8"]:
                    out[col] = pd.to_numeric(out[col], errors="coerce").astype(
                        "float64"
                    )
        elif isinstance(out, pd.Series):
            # Для Series тоже приводим тип
            if out.dtype in ["int64", "int32", "int16", "int8"]:
                out = pd.to_numeric(out, errors="coerce").astype("float64")
        # Нормализуем результат с явным приведением типов
        normalized = _normalize_to_df(out, name, df, **kwargs)
        # Дополнительная проверка типов для избежания FutureWarning
        # Приводим все числовые колонки к float64 до присваивания
        needs_copy = any(
            normalized[col].dtype in ["int64", "int32", "int16", "int8", "object"]
            for col in normalized.columns
        )
        if needs_copy:
            normalized = normalized.copy()
            for col in normalized.columns:
                if normalized[col].dtype in [
                    "int64",
                    "int32",
                    "int16",
                    "int8",
                    "object",
                ]:
                    normalized[col] = pd.to_numeric(
                        normalized[col], errors="coerce"
                    ).astype("float64")
        return normalized
    except Exception as e:
        raise FeatureCalcError(f"ta.{name} упал: {e}") from e
