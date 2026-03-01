"""
Normalization functions for ta_safe module.

This module provides functions for normalizing indicator names and results
to match the project's naming conventions.
"""

import re

import pandas as pd

from .constants import RENAME_MAP


def _auto_rename(col: str) -> str:
    """
    Автоматическое переименование колонок по шаблонам.

    Args:
        col: Имя колонки для переименования

    Returns:
        Нормализованное имя колонки
    """
    # MACD
    m = re.fullmatch(r"MACD_(\d+)_(\d+)_(\d+)", col)
    if m:
        return "macd"
    m = re.fullmatch(r"MACDs_(\d+)_(\d+)_(\d+)", col)
    if m:
        return "macd_signal"
    m = re.fullmatch(r"MACDh_(\d+)_(\d+)_(\d+)", col)
    if m:
        return "macd_histogram"
    # BBANDS
    m = re.fullmatch(r"BBL_(\d+)_([0-9.]+)", col)
    if m:
        return "bb_lower"
    m = re.fullmatch(r"BBM_(\d+)_([0-9.]+)", col)
    if m:
        return "bb_middle"
    m = re.fullmatch(r"BBU_(\d+)_([0-9.]+)", col)
    if m:
        return "bb_upper"
    # RSI/ATR/ADX/AROON
    m = re.fullmatch(r"RSI_(\d+)", col)
    if m:
        return f"rsi_{m.group(1)}"
    m = re.fullmatch(r"ATRr?_(\d+)", col)
    if m:
        return f"atr_{m.group(1)}"
    m = re.fullmatch(r"ADX_(\d+)", col)
    if m:
        return f"adx_{m.group(1)}"
    m = re.fullmatch(r"DMP_(\d+)", col)
    if m:
        return "adx_pos_di"
    m = re.fullmatch(r"DMN_(\d+)", col)
    if m:
        return "adx_neg_di"
    m = re.fullmatch(r"AROONU_(\d+)", col)
    if m:
        return "aroon_up"
    m = re.fullmatch(r"AROOND_(\d+)", col)
    if m:
        return "aroon_down"
    # KC: KCL/KCM/KCU_20_2.0 или kcle/kcbe/kcue_20_2.0
    m = re.fullmatch(r"KCL[E]?_(\d+)_([0-9.]+)", col, re.IGNORECASE)
    if m:
        return "kc_lower"
    m = re.fullmatch(r"KCM_(\d+)_([0-9.]+)", col)
    if m:
        return "kc_middle"
    m = re.fullmatch(r"KCBE_(\d+)_([0-9.]+)", col, re.IGNORECASE)
    if m:
        return "kc_middle"
    m = re.fullmatch(r"KCU[E]?_(\d+)_([0-9.]+)", col, re.IGNORECASE)
    if m:
        return "kc_upper"
    # Ichimoku: ISA/ISB/ITS/IKS/ICS/IKH_X
    m = re.fullmatch(r"ISA_(\d+)", col)
    if m:
        return "ichimoku_senkou_a"
    m = re.fullmatch(r"ISB_(\d+)", col)
    if m:
        return "ichimoku_senkou_b"
    m = re.fullmatch(r"ITS_(\d+)", col)
    if m:
        return "ichimoku_tenkan"
    m = re.fullmatch(r"IKS_(\d+)", col)
    if m:
        return "ichimoku_kijun"
    m = re.fullmatch(r"ICS_(\d+)", col)
    if m:
        return "ichimoku_chikou"
    m = re.fullmatch(r"IKH_\w+", col)
    if m:
        return col.lower()
    # Supertrend: SUPERT_*, SUPERTd_*, SUPERTl_*, SUPERTs_*
    m = re.fullmatch(r"SUPERT_(\d+)_([0-9.]+)", col)
    if m:
        return "supertrend"
    m = re.fullmatch(r"SUPERTd_(\d+)_([0-9.]+)", col)
    if m:
        return "supertrend_direction"
    m = re.fullmatch(r"SUPERTl_(\d+)_([0-9.]+)", col)
    if m:
        return "supertrend_long"
    m = re.fullmatch(r"SUPERTs_(\d+)_([0-9.]+)", col)
    if m:
        return "supertrend_short"
    # PSAR: PSARl_*, PSARs_*, PSARaf_*, PSARr_*
    m = re.fullmatch(r"PSARl_([0-9.]+)_([0-9.]+)", col)
    if m:
        return "psar_long"
    m = re.fullmatch(r"PSARs_([0-9.]+)_([0-9.]+)", col)
    if m:
        return "psar_short"
    m = re.fullmatch(r"PSARaf_([0-9.]+)_([0-9.]+)", col)
    if m:
        return "psar_af"
    m = re.fullmatch(r"PSARr_([0-9.]+)_([0-9.]+)", col)
    if m:
        return "psar_reversal"
    # UO и WILLR
    if col.upper() == "UO":
        return "ultosc"
    if col.upper() == "WILLR" or col.upper().startswith("WILLR_"):
        return "willr"
    # по умолчанию
    return col.lower()


def _rename_like_specs(df_out: pd.DataFrame) -> pd.DataFrame:
    """
    Переименование колонок под наши specs.

    Args:
        df_out: DataFrame для переименования

    Returns:
        DataFrame с переименованными колонками
    """
    df_out.columns = [RENAME_MAP.get(c, _auto_rename(c)) for c in df_out.columns]
    return df_out


def _normalize_to_df(
    out: pd.DataFrame | pd.Series | None,
    name: str,
    df: pd.DataFrame,
    **kwargs: dict[str, object],
) -> pd.DataFrame:
    """
    Нормализует результат к DataFrame с правильными именами и индексом.

    Специальная обработка для BB и Ichimoku для правильного unpack.

    Args:
        out: Результат расчёта (DataFrame, Series или None)
        name: Имя индикатора
        df: Исходный DataFrame
        **kwargs: Дополнительные параметры

    Returns:
        Нормализованный DataFrame

    Raises:
        FeatureCalcError: Если длина результата не совпадает с входом или есть object-колонки
    """
    import numpy as np

    from .errors import FeatureCalcError

    # Если библиотека вернула None/пусто — возвращаем NaN-столбец нужной длины
    if out is None or callable(out):
        return pd.Series([np.nan] * len(df), index=df.index).to_frame(name)

    if isinstance(out, pd.Series):
        col = out.name or name
        out = out.to_frame(col)
    elif not isinstance(out, pd.DataFrame):
        return pd.Series([np.nan] * len(df), index=df.index).to_frame(name)

    # Специальная обработка для BB: явный unpack в именованные колонки
    if name == "bbands":
        # Если pandas_ta вернул DataFrame с нестандартными именами, переименовываем
        cols = list(out.columns)
        if len(cols) >= 3:
            # Ожидаем порядок: lower, middle, upper
            # Или ищем по префиксам
            col_lower = next(
                (c for c in cols if "BBL" in c.upper() or "lower" in c.lower()), None
            )
            col_middle = next(
                (c for c in cols if "BBM" in c.upper() or "middle" in c.lower()), None
            )
            col_upper = next(
                (c for c in cols if "BBU" in c.upper() or "upper" in c.lower()), None
            )

            if col_lower and col_middle and col_upper:
                out = out[[col_lower, col_middle, col_upper]].copy()
                out.columns = ["bb_lower", "bb_middle", "bb_upper"]
            elif len(cols) == 3:
                # Если 3 колонки без явных имён, предполагаем порядок lower, middle, upper
                out.columns = ["bb_lower", "bb_middle", "bb_upper"]
        else:
            # Fallback: создаём пустые колонки
            out = pd.DataFrame(
                {
                    "bb_lower": [np.nan] * len(df),
                    "bb_middle": [np.nan] * len(df),
                    "bb_upper": [np.nan] * len(df),
                },
                index=df.index,
            )

    # Специальная обработка для Ichimoku: явный unpack в 5 компонентов
    elif name == "ichimoku":
        # Если pandas_ta вернул tuple или list, берём первый элемент
        if isinstance(out, list | tuple):
            out = out[0] if len(out) > 0 else pd.DataFrame()

        # Если вернулся DataFrame с нестандартными именами, переименовываем
        if isinstance(out, pd.DataFrame):
            cols = list(out.columns)
            # Маппинг возможных имён pandas_ta на наши
            ichimoku_mapping = {
                "ITS_9": "ichimoku_tenkan",
                "IKS_26": "ichimoku_kijun",
                "ISA_9": "ichimoku_senkou_a",
                "ISB_26": "ichimoku_senkou_b",
                "ICS_26": "ichimoku_chikou",
            }
            # Переименовываем найденные колонки
            rename_dict = {}
            for col in cols:
                for ta_name, our_name in ichimoku_mapping.items():
                    if ta_name in col or col.startswith(ta_name):
                        rename_dict[col] = our_name
                        break

            if rename_dict:
                out = out.rename(columns=rename_dict)

            # Если после переименования не все колонки есть, добавляем недостающие
            required_cols = [
                "ichimoku_tenkan",
                "ichimoku_kijun",
                "ichimoku_senkou_a",
                "ichimoku_senkou_b",
                "ichimoku_chikou",
            ]
            missing_cols = set(required_cols) - set(out.columns)
            if missing_cols:
                for col in missing_cols:
                    out[col] = np.nan
            # Оставляем только нужные колонки в правильном порядке
            out = out[required_cols].copy()
        else:
            # Fallback: создаём пустые колонки
            out = pd.DataFrame(
                {
                    "ichimoku_tenkan": [np.nan] * len(df),
                    "ichimoku_kijun": [np.nan] * len(df),
                    "ichimoku_senkou_a": [np.nan] * len(df),
                    "ichimoku_senkou_b": [np.nan] * len(df),
                    "ichimoku_chikou": [np.nan] * len(df),
                },
                index=df.index,
            )

    # Имена под specs (для остальных индикаторов)
    if name not in ("bbands", "ichimoku"):
        out = _rename_like_specs(out)

    # Если после нормализации колонок ничего не осталось — вернём NaN-столбец
    if out.shape[1] == 0:
        return pd.Series([np.nan] * len(df), index=df.index).to_frame(name)

    # Индекс строго как у входа
    if not out.index.equals(df.index):
        out = out.reindex(df.index, fill_value=np.nan)

    # Жёсткая проверка длины после reindex
    if len(out) != len(df):
        raise FeatureCalcError(f"длина результата != входу: {len(out)} != {len(df)}")

    # Типы числовые (не понижаем bool)
    num = out.select_dtypes(include=["number"]).columns.difference(
        out.select_dtypes(include=["bool"]).columns
    )
    # Явное приведение типов перед присваиванием для избежания FutureWarning
    # Используем pd.to_numeric для безопасного преобразования
    for col in num:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")
    bad = [c for c in out.columns if out[c].dtype == "object"]
    if bad:
        raise FeatureCalcError(f"object-колонки недопустимы: {bad}")

    return out
