"""
Вспомогательные утилиты для расчёта индикаторов.

Содержит централизованные минимальные длины окон и проверку входных данных
на достаточность длины перед вызовами ta-библиотек, чтобы избежать
неконсистентных падений и 0%-заполнения из-за прогрева окон.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.logging import get_logger

logger = get_logger(__name__)

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

# =============================================================================
# ТОЧНЫЕ МАППИНГИ КОЛОНОК pandas_ta
# =============================================================================
# Версия pandas_ta: 0.3.14b
# Формат: "PREFIX" -> ["exact_col_1", "exact_col_2", ...]
# Порядок важен: первый подходящий будет использован

PANDAS_TA_COLUMN_EXACT: dict[str, list[str]] = {
    # MACD (12, 26, 9)
    "MACD": ["MACD_12_26_9"],
    "MACDs": ["MACDs_12_26_9"],
    "MACDh": ["MACDh_12_26_9"],
    # Stochastic (14, 3, 3)
    "STOCHk": ["STOCHk_14_3_3"],
    "STOCHd": ["STOCHd_14_3_3"],
    # StochRSI (14, 14, 3, 3)
    "STOCHRSIk": ["STOCHRSIk_14_14_3_3"],
    "STOCHRSId": ["STOCHRSId_14_14_3_3"],
    # KDJ (9, 3)
    "KDJk": ["KDJk_9_3", "K_9_3"],
    "KDJd": ["KDJd_9_3", "D_9_3"],
    "KDJj": ["KDJj_9_3", "J_9_3"],
    # Bollinger Bands (20, 2)
    "BBU": ["BBU_20_2.0", "BBU_20_2"],
    "BBM": ["BBM_20_2.0", "BBM_20_2"],
    "BBL": ["BBL_20_2.0", "BBL_20_2"],
    "BBB": ["BBB_20_2.0", "BBB_20_2"],
    "BBP": ["BBP_20_2.0", "BBP_20_2"],
    # Keltner Channels (20, 2)
    "KCU": ["KCUe_20_2", "KCU_20_2", "KCUe_20_2.0"],
    "KCUE": ["KCUe_20_2", "KCUe_20_2.0"],
    "KCB": ["KCBe_20_2", "KCB_20_2", "KCBe_20_2.0"],
    "KCBE": ["KCBe_20_2", "KCBe_20_2.0"],
    "KCL": ["KCLe_20_2", "KCL_20_2", "KCLe_20_2.0"],
    "KCLE": ["KCLe_20_2", "KCLe_20_2.0"],
    # Donchian Channels (20)
    "DCU": ["DCU_20_20", "DCU_20"],
    "DCM": ["DCM_20_20", "DCM_20"],
    "DCL": ["DCL_20_20", "DCL_20"],
    # Supertrend (7, 3)
    "SUPERT_": ["SUPERT_7_3.0", "SUPERT_7_3"],
    "SUPERTd_": ["SUPERTd_7_3.0", "SUPERTd_7_3"],
    "SUPERTl_": ["SUPERTl_7_3.0", "SUPERTl_7_3"],
    "SUPERTs_": ["SUPERTs_7_3.0", "SUPERTs_7_3"],
    # Chande Kroll Stop
    "CKSPU_": ["CKSPu_10_3_20", "CKSPu_10_3"],
    "CKSPL_": ["CKSPl_10_3_20", "CKSPl_10_3"],
    # Parabolic SAR
    "PSARl_": ["PSARl_0.02_0.2", "PSARl_0.02_0.02_0.2"],
    "PSARs_": ["PSARs_0.02_0.2", "PSARs_0.02_0.02_0.2"],
    "PSARaf_": ["PSARaf_0.02_0.2"],
    "PSARr_": ["PSARr_0.02_0.2"],
    # Aroon (14)
    "AROONU": ["AROONU_14"],
    "AROOND": ["AROOND_14"],
    "AROONOSC": ["AROONOSC_14"],
    # ADX (14)
    "ADX": ["ADX_14"],
    "DMP": ["DMP_14"],
    "DMN": ["DMN_14"],
    # Ichimoku (9, 26, 52)
    "ISA": ["ISA_9", "ITS_9"],
    "ISB": ["ISB_26", "IKS_26"],
    "ITS": ["ITS_9"],
    "IKS": ["IKS_26"],
    "ICS": ["ICS_26"],
}

# Fallback: если точный маппинг не сработал, использовать prefix
PANDAS_TA_FALLBACK_ENABLED = True


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
    """
    Находит колонку DataFrame по точному маппингу или префиксу.

    Стратегия поиска:
    1. Проверяет точные имена из PANDAS_TA_COLUMN_EXACT
    2. Если не найдено и PANDAS_TA_FALLBACK_ENABLED=True, ищет по префиксу

    Args:
        df: DataFrame для поиска
        prefix: Префикс/ключ для поиска

    Returns:
        Имя колонки или None, если не найдено
    """
    # 1. Попробуем точный маппинг
    exact_candidates = PANDAS_TA_COLUMN_EXACT.get(prefix, [])
    for exact_col in exact_candidates:
        if exact_col in df.columns:
            return exact_col

    # 2. Fallback на поиск по префиксу
    if PANDAS_TA_FALLBACK_ENABLED:
        col = next((c for c in df.columns if c.startswith(prefix)), None)
        if col is not None:
            # Логируем предупреждение - возможно нужно добавить в маппинг
            logger.debug(
                f"Column found by prefix fallback: '{prefix}' -> '{col}'. "
                f"Consider adding to PANDAS_TA_COLUMN_EXACT."
            )
        return col

    return None


def get_column_safe(
    df: pd.DataFrame,
    exact_name: str,
    prefix: str | None = None,
) -> str | None:
    """
    Безопасно получить имя колонки с точным соответствием и опциональным fallback.

    Args:
        df: DataFrame для поиска
        exact_name: Точное имя колонки
        prefix: Опциональный префикс для fallback

    Returns:
        Имя колонки или None
    """
    # Сначала пробуем точное имя
    if exact_name in df.columns:
        return exact_name

    # Затем пробуем через маппинг
    if prefix:
        return _get_col_by_prefix(df, prefix)

    return None
