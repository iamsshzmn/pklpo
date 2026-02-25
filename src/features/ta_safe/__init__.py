"""
Universal facade for pandas_ta with strict validation.

This package provides a safe interface for calling pandas_ta functions
with automatic fallback to alternative implementations when needed.

Public API:
    - safe_ta_with_fallback: Main function with automatic fallback support
    - safe_ta: Direct pandas_ta call (no fallback)
    - safe_ta_fallback: Fallback implementations
    - FeatureCalcError: Exception class for calculation errors
"""

import logging

import pandas as pd

try:
    import pandas_ta  # type: ignore[import-untyped]
    _PANDAS_TA_AVAILABLE = True
except ImportError:
    _PANDAS_TA_AVAILABLE = False

from .backend import _get_available_functions, safe_ta
from .bridge import _talib_bridge
from .constants import ALLOW, BACKEND
from .errors import FeatureCalcError
from .fallback import safe_ta_fallback
from .normalization import _normalize_to_df
from .validation import _validate_allowlist

logger = logging.getLogger(__name__)

# Проверяем доступность функций при загрузке модуля
_validate_allowlist(ALLOW)

# Инициализируем доступные функции
_AVAILABLE_FUNCTIONS = _get_available_functions()


def safe_ta_with_fallback(
    df: pd.DataFrame, name: str, /, **kwargs: dict[str, object]
) -> pd.DataFrame:
    """
    Безопасный вызов с поддержкой разных бэкендов и автоматическим fallback.

    Исключённые функции: tr, trange, cdl_doji, cdl_inside
    - tr/trange: ATR считает True Range внутри себя
    - cdl_doji/cdl_inside: используют собственные реализации в candles.py

    Args:
        df: DataFrame с OHLCV данными
        name: Имя функции pandas_ta
        **kwargs: Параметры функции

    Returns:
        pd.DataFrame с результатами расчёта

    Raises:
        FeatureCalcError: При ошибках расчёта
    """
    # Исключаем функции, которые не участвуют в расчётах других индикаторов
    EXCLUDED_FUNCS = {"tr", "trange", "cdl_doji", "cdl_inside", "true_range"}
    if name in EXCLUDED_FUNCS:
        logger.debug(f"Функция {name} исключена из пайплайна")
        # Возвращаем пустой DataFrame вместо None для совместимости с типом возврата
        return pd.DataFrame(index=df.index)

    # Обработка алиасов (только для неисключённых функций)
    alias_map: dict[str, str] = {}
    if name in alias_map:
        name = alias_map[name]

    # Проверяем, доступна ли функция
    if name not in _AVAILABLE_FUNCTIONS and BACKEND != "fallback":
        logger.warning(f"Function {name} not available, using fallback")
        out = safe_ta_fallback(df, name, **kwargs)
        return _normalize_to_df(out, name, df, **kwargs)

    # Пробуем pandas_ta
    if BACKEND in ("pandas_ta", "auto"):
        try:
            return safe_ta(df, name, **kwargs)
        except Exception as e:
            if BACKEND == "pandas_ta":
                raise FeatureCalcError(f"pandas_ta failed for {name}: {e}") from e
            logger.warning(f"pandas_ta.{name} failed: {e}, trying fallback")

    # Пробуем TA-Lib (если доступен)
    if BACKEND in ("talib", "auto"):
        try:
            return _talib_bridge(df, name, **kwargs)
        except Exception as e:
            if BACKEND == "talib":
                raise FeatureCalcError(f"TA-Lib failed for {name}: {e}") from e
            logger.warning(f"TA-Lib.{name} failed: {e}, trying fallback")

    # Fallback как последний уровень
    logger.warning(f"Using fallback for {name}")
    out = safe_ta_fallback(df, name, **kwargs)
    return _normalize_to_df(out, name, df, **kwargs)


# Re-export public API
__all__ = [
    "FeatureCalcError",
    "safe_ta",
    "safe_ta_fallback",
    "safe_ta_with_fallback",
]
