"""
Volatility Indicators Module

Group: Volatility
Dependencies: OHLC, sometimes MA
Max Lookback: 100 bars
Output Fields: atr_14, atr_21, bb_upper, bb_middle, bb_lower, kc_upper, kc_middle, kc_lower, dc_upper, dc_lower

This module calculates volatility-based indicators including:
- ATR (Average True Range): Measures market volatility
- Bollinger Bands: Price envelopes based on standard deviation
- Keltner Channels: ATR-based price channels
- Donchian Channels: Highest high and lowest low over period
"""

import pandas as pd

from src.logging import get_logger

from ..ta_safe import safe_ta_with_fallback
from ..utils.indicator_utils import (
    _first_col_or_series,
    _get_col_by_prefix,
    _nan_series,
    check_min_length,
)

logger = get_logger(__name__)


def calc_volatility_indicators(
    df: pd.DataFrame, available: set[str]
) -> dict[str, pd.Series]:
    """Calculate Volatility indicators for risk and breakout analysis.

    Гарантирует: все значения Series, индекс == df.index, float dtype где применимо.

    Args:
        df: DataFrame with OHLC data (must have 'open', 'high', 'low', 'close' columns)
        available: Set of indicator names to calculate

    Returns:
        Dictionary mapping indicator names to pandas Series with calculated values

    Example:
        >>> vol_indicators = calc_volatility_indicators(df, {'atr_14', 'bb_upper', 'bb_lower'})
        >>> atr = vol_indicators['atr_14']
    """
    result: dict[str, pd.Series] = {}

    # Очистка данных один раз в начале
    df = df.copy()
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Bollinger Bands
    if "bb_upper" in available or "bb_middle" in available or "bb_lower" in available:
        try:
            if not check_min_length(df, "bb"):
                logger.warning("BBANDS: недостаточно данных (len<20), возвращаю NaN")
                for key in ["bb_upper", "bb_middle", "bb_lower"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
            else:
                bb_result = safe_ta_with_fallback(df, "bbands", length=20, std=2)
                logger.debug(
                    f"BBANDS result type: {type(bb_result)}, columns: {bb_result.columns if isinstance(bb_result, pd.DataFrame) else 'N/A'}"
                )
                if isinstance(bb_result, pd.DataFrame):
                    if "bb_upper" in available:
                        # Проверяем сначала каноническое имя, потом префикс
                        if "bb_upper" in bb_result.columns:
                            result["bb_upper"] = _first_col_or_series(
                                bb_result["bb_upper"], "bb_upper", df.index
                            )
                        else:
                            col_u = _get_col_by_prefix(bb_result, "BBU")
                            if col_u:
                                result["bb_upper"] = _first_col_or_series(
                                    bb_result[[col_u]], "bb_upper", df.index
                                )
                            else:
                                logger.warning(
                                    f"BBANDS: не найдена колонка bb_upper, доступные: {list(bb_result.columns)}"
                                )
                                result["bb_upper"] = _nan_series(df.index, "bb_upper")

                    if "bb_middle" in available:
                        # Проверяем сначала каноническое имя, потом префикс
                        if "bb_middle" in bb_result.columns:
                            result["bb_middle"] = _first_col_or_series(
                                bb_result["bb_middle"], "bb_middle", df.index
                            )
                        else:
                            col_m = _get_col_by_prefix(bb_result, "BBM")
                            if col_m:
                                result["bb_middle"] = _first_col_or_series(
                                    bb_result[[col_m]], "bb_middle", df.index
                                )
                            else:
                                logger.warning(
                                    f"BBANDS: не найдена колонка bb_middle, доступные: {list(bb_result.columns)}"
                                )
                                result["bb_middle"] = _nan_series(df.index, "bb_middle")

                    if "bb_lower" in available:
                        # Проверяем сначала каноническое имя, потом префикс
                        if "bb_lower" in bb_result.columns:
                            result["bb_lower"] = _first_col_or_series(
                                bb_result["bb_lower"], "bb_lower", df.index
                            )
                        else:
                            col_l = _get_col_by_prefix(bb_result, "BBL")
                            if col_l:
                                result["bb_lower"] = _first_col_or_series(
                                    bb_result[[col_l]], "bb_lower", df.index
                                )
                            else:
                                logger.warning(
                                    f"BBANDS: не найдена колонка bb_lower, доступные: {list(bb_result.columns)}"
                                )
                                result["bb_lower"] = _nan_series(df.index, "bb_lower")
                else:
                    for key in ["bb_upper", "bb_middle", "bb_lower"]:
                        if key in available:
                            result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта Bollinger Bands: {type(e).__name__}: {e}")
            for key in ["bb_upper", "bb_middle", "bb_lower"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # Keltner Channel
    if "kc_upper" in available or "kc_middle" in available or "kc_lower" in available:
        try:
            if not check_min_length(df, "kc"):
                logger.warning("KC: недостаточно данных (len<20), возвращаю NaN")
                for key in ["kc_upper", "kc_middle", "kc_lower"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
            else:
                kc_result = safe_ta_with_fallback(df, "kc", length=20, scalar=2)
                logger.debug(
                    f"KC result type: {type(kc_result)}, columns: {kc_result.columns if isinstance(kc_result, pd.DataFrame) else 'N/A'}"
                )
                if isinstance(kc_result, pd.DataFrame):
                    if "kc_upper" in available:
                        # Проверяем сначала каноническое имя, потом префикс
                        if "kc_upper" in kc_result.columns:
                            result["kc_upper"] = _first_col_or_series(
                                kc_result["kc_upper"], "kc_upper", df.index
                            )
                        else:
                            col_u = _get_col_by_prefix(kc_result, "KCU")
                            if not col_u:
                                col_u = _get_col_by_prefix(kc_result, "KCUE")
                            if not col_u:
                                col_u = _get_col_by_prefix(kc_result, "kcue")
                            if col_u:
                                result["kc_upper"] = _first_col_or_series(
                                    kc_result[[col_u]], "kc_upper", df.index
                                )
                            else:
                                logger.warning(
                                    f"KC: не найдена колонка kc_upper, доступные: {list(kc_result.columns)}"
                                )
                                result["kc_upper"] = _nan_series(df.index, "kc_upper")

                    if "kc_middle" in available:
                        # Проверяем сначала каноническое имя, потом префикс
                        if "kc_middle" in kc_result.columns:
                            result["kc_middle"] = _first_col_or_series(
                                kc_result["kc_middle"], "kc_middle", df.index
                            )
                        else:
                            col_m = _get_col_by_prefix(kc_result, "KCB")
                            if not col_m:
                                col_m = _get_col_by_prefix(kc_result, "KCBE")
                            if not col_m:
                                col_m = _get_col_by_prefix(kc_result, "kcbe")
                            if col_m:
                                result["kc_middle"] = _first_col_or_series(
                                    kc_result[[col_m]], "kc_middle", df.index
                                )
                            else:
                                logger.warning(
                                    f"KC: не найдена колонка kc_middle, доступные: {list(kc_result.columns)}"
                                )
                                result["kc_middle"] = _nan_series(df.index, "kc_middle")

                    if "kc_lower" in available:
                        # Проверяем сначала каноническое имя, потом префикс
                        if "kc_lower" in kc_result.columns:
                            result["kc_lower"] = _first_col_or_series(
                                kc_result["kc_lower"], "kc_lower", df.index
                            )
                        else:
                            col_l = _get_col_by_prefix(kc_result, "KCL")
                            if not col_l:
                                col_l = _get_col_by_prefix(kc_result, "KCLE")
                            if not col_l:
                                col_l = _get_col_by_prefix(kc_result, "kcle")
                            if col_l:
                                result["kc_lower"] = _first_col_or_series(
                                    kc_result[[col_l]], "kc_lower", df.index
                                )
                            else:
                                logger.warning(
                                    f"KC: не найдена колонка kc_lower, доступные: {list(kc_result.columns)}"
                                )
                                result["kc_lower"] = _nan_series(df.index, "kc_lower")
                else:
                    for key in ["kc_upper", "kc_middle", "kc_lower"]:
                        if key in available:
                            result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта Keltner Channels: {type(e).__name__}: {e}")
            for key in ["kc_upper", "kc_middle", "kc_lower"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # ATR
    if "atr_14" in available:
        try:
            atr_result = safe_ta_with_fallback(df, "atr", length=14)
            result["atr_14"] = _first_col_or_series(atr_result, "atr_14", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта ATR: {type(e).__name__}: {e}")
            result["atr_14"] = _nan_series(df.index, "atr_14")

    # NATR
    if "natr_14" in available:
        try:
            natr_result = safe_ta_with_fallback(df, "natr", length=14)
            result["natr_14"] = _first_col_or_series(natr_result, "natr_14", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта NATR: {type(e).__name__}: {e}")
            result["natr_14"] = _nan_series(df.index, "natr_14")

    # Donchian Channel
    if "dc_upper" in available or "dc_middle" in available or "dc_lower" in available:
        try:
            dc_result = safe_ta_with_fallback(df, "dc", length=20)
            if isinstance(dc_result, pd.DataFrame):
                if "dc_upper" in available:
                    col_u = _get_col_by_prefix(dc_result, "DCU")
                    result["dc_upper"] = _first_col_or_series(
                        (
                            dc_result[[col_u]]
                            if col_u
                            else (
                                dc_result.get("dc_upper")
                                if "dc_upper" in dc_result.columns
                                else None
                            )
                        ),
                        "dc_upper",
                        df.index,
                    )

                if "dc_middle" in available:
                    col_m = _get_col_by_prefix(dc_result, "DCM")
                    result["dc_middle"] = _first_col_or_series(
                        (
                            dc_result[[col_m]]
                            if col_m
                            else (
                                dc_result.get("dc_middle")
                                if "dc_middle" in dc_result.columns
                                else None
                            )
                        ),
                        "dc_middle",
                        df.index,
                    )

                if "dc_lower" in available:
                    col_l = _get_col_by_prefix(dc_result, "DCL")
                    result["dc_lower"] = _first_col_or_series(
                        (
                            dc_result[[col_l]]
                            if col_l
                            else (
                                dc_result.get("dc_lower")
                                if "dc_lower" in dc_result.columns
                                else None
                            )
                        ),
                        "dc_lower",
                        df.index,
                    )
            else:
                for key in ["dc_upper", "dc_middle", "dc_lower"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта Donchian Channels: {type(e).__name__}: {e}")
            for key in ["dc_upper", "dc_middle", "dc_lower"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # Parkinson Volatility
    if "parkinson_vol" in available:
        try:
            parkinson_result = safe_ta_with_fallback(df, "parkinson", length=14)
            result["parkinson_vol"] = _first_col_or_series(
                parkinson_result, "parkinson_vol", df.index
            )
        except Exception as e:
            logger.error(
                f"Ошибка расчёта Parkinson Volatility: {type(e).__name__}: {e}"
            )
            result["parkinson_vol"] = _nan_series(df.index, "parkinson_vol")

    # Mass Index
    if "massi" in available:
        try:
            massi_result = safe_ta_with_fallback(df, "massi")
            result["massi"] = _first_col_or_series(massi_result, "massi", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта Mass Index: {type(e).__name__}: {e}")
            result["massi"] = _nan_series(df.index, "massi")

    # Relative Volatility Index
    if "rvi" in available:
        try:
            rvi_result = safe_ta_with_fallback(df, "rvi")
            result["rvi"] = _first_col_or_series(rvi_result, "rvi", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта RVI: {type(e).__name__}: {e}")
            result["rvi"] = _nan_series(df.index, "rvi")

    # Ulcer Index
    if "ui" in available:
        try:
            ui_result = safe_ta_with_fallback(df, "ui")
            result["ui"] = _first_col_or_series(ui_result, "ui", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта Ulcer Index: {type(e).__name__}: {e}")
            result["ui"] = _nan_series(df.index, "ui")

    # Price Distance
    if "pdist" in available:
        try:
            pdist_result = safe_ta_with_fallback(df, "pdist")
            result["pdist"] = _first_col_or_series(pdist_result, "pdist", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта Price Distance: {type(e).__name__}: {e}")
            result["pdist"] = _nan_series(df.index, "pdist")

    # Bollinger Bands Width
    if "bb_width" in available:
        try:
            if not check_min_length(df, "bb"):
                result["bb_width"] = _nan_series(df.index, "bb_width")
            else:
                bb_result = safe_ta_with_fallback(df, "bbands", length=20, std=2)
                if isinstance(bb_result, pd.DataFrame):
                    col_u = _get_col_by_prefix(bb_result, "BBU")
                    col_l = _get_col_by_prefix(bb_result, "BBL")
                    col_m = _get_col_by_prefix(bb_result, "BBM")
                    if col_u and col_l and col_m:
                        bb_upper = _first_col_or_series(
                            bb_result[[col_u]], "bb_upper", df.index
                        )
                        bb_lower = _first_col_or_series(
                            bb_result[[col_l]], "bb_lower", df.index
                        )
                        bb_middle = _first_col_or_series(
                            bb_result[[col_m]], "bb_middle", df.index
                        )
                        result["bb_width"] = (bb_upper - bb_lower) / bb_middle
                    else:
                        result["bb_width"] = _nan_series(df.index, "bb_width")
                else:
                    result["bb_width"] = _nan_series(df.index, "bb_width")
        except Exception as e:
            logger.error(f"Ошибка расчёта BB Width: {type(e).__name__}: {e}")
            result["bb_width"] = _nan_series(df.index, "bb_width")

    # Bollinger Bands Percent
    if "bb_percent" in available:
        try:
            if not check_min_length(df, "bb"):
                result["bb_percent"] = _nan_series(df.index, "bb_percent")
            else:
                bb_result = safe_ta_with_fallback(df, "bbands", length=20, std=2)
                if isinstance(bb_result, pd.DataFrame):
                    col_u = _get_col_by_prefix(bb_result, "BBU")
                    col_l = _get_col_by_prefix(bb_result, "BBL")
                    if col_u and col_l:
                        bb_upper = _first_col_or_series(
                            bb_result[[col_u]], "bb_upper", df.index
                        )
                        bb_lower = _first_col_or_series(
                            bb_result[[col_l]], "bb_lower", df.index
                        )
                        close_series = pd.Series(df["close"], index=df.index)
                        result["bb_percent"] = (close_series - bb_lower) / (
                            bb_upper - bb_lower
                        )
                    else:
                        result["bb_percent"] = _nan_series(df.index, "bb_percent")
                else:
                    result["bb_percent"] = _nan_series(df.index, "bb_percent")
        except Exception as e:
            logger.error(f"Ошибка расчёта BB Percent: {type(e).__name__}: {e}")
            result["bb_percent"] = _nan_series(df.index, "bb_percent")

    # True Range исключён из пайплайна
    # ATR считает True Range внутри себя, отдельный trange не нужен

    # Гарантируем, что все значения - Series
    assert all(
        isinstance(v, pd.Series) for v in result.values()
    ), "Все значения должны быть Series"

    return result
