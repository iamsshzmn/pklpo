"""
Oscillator Indicators Module

Group: Oscillators
Dependencies: close, sometimes MA
Max Lookback: 100 bars
Output Fields: rsi_14, macd, macd_signal, macd_histogram, stoch_k, stoch_d, cci_14, mfi, etc.

This module calculates momentum oscillators and mean-reversion indicators including:
- RSI (Relative Strength Index): Overbought/oversold conditions
- MACD (Moving Average Convergence Divergence): Trend changes
- Stochastic: Price momentum relative to range
- CCI (Commodity Channel Index): Price deviation from average
- MFI (Money Flow Index): Volume-weighted RSI
- Williams %R, ROC, PPO, TRIX, and more
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
from .debug_utils import log_group_results, log_group_start

logger = get_logger(__name__)


def calc_oscillator_indicators(
    df: pd.DataFrame, available: set[str]
) -> dict[str, pd.Series]:
    """Calculate Oscillator indicators for momentum and mean-reversion analysis.

    Гарантирует: все значения Series, индекс == df.index, float dtype где применимо.

    Args:
        df: DataFrame with OHLC data (must have 'open', 'high', 'low', 'close', 'volume' columns)
        available: Set of indicator names to calculate

    Returns:
        Dictionary mapping indicator names to pandas Series with calculated values

    Example:
        >>> osc_indicators = calc_oscillator_indicators(df, {'rsi_14', 'macd', 'stoch_k'})
        >>> rsi = osc_indicators['rsi_14']
    """
    log_group_start("OSCILLATORS", df, available)
    result: dict[str, pd.Series] = {}

    # Очистка данных один раз в начале
    df = df.copy()
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # RSI
    if "rsi_14" in available:
        try:
            rsi_result = safe_ta_with_fallback(df, "rsi", length=14)
            result["rsi_14"] = _first_col_or_series(rsi_result, "rsi_14", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта RSI: {type(e).__name__}: {e}")
            result["rsi_14"] = _nan_series(df.index, "rsi_14")

    # Stochastic
    if "stoch_k" in available or "stoch_d" in available:
        try:
            stoch_result = safe_ta_with_fallback(df, "stoch", k=14, d=3)
            if isinstance(stoch_result, pd.DataFrame):
                if "stoch_k" in available:
                    col_k = _get_col_by_prefix(stoch_result, "STOCHk")
                    if col_k:
                        result["stoch_k"] = _first_col_or_series(
                            stoch_result[[col_k]], "stoch_k", df.index
                        )
                    elif len(stoch_result.columns) > 0:
                        result["stoch_k"] = _first_col_or_series(
                            stoch_result.iloc[:, [0]], "stoch_k", df.index
                        )
                    else:
                        result["stoch_k"] = _nan_series(df.index, "stoch_k")

                if "stoch_d" in available:
                    col_d = _get_col_by_prefix(stoch_result, "STOCHd")
                    if col_d:
                        result["stoch_d"] = _first_col_or_series(
                            stoch_result[[col_d]], "stoch_d", df.index
                        )
                    elif len(stoch_result.columns) > 1:
                        result["stoch_d"] = _first_col_or_series(
                            stoch_result.iloc[:, [1]], "stoch_d", df.index
                        )
                    else:
                        result["stoch_d"] = _nan_series(df.index, "stoch_d")
            else:
                for key in ["stoch_k", "stoch_d"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта Stochastic: {type(e).__name__}: {e}")
            for key in ["stoch_k", "stoch_d"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # MACD
    if (
        "macd" in available
        or "macd_signal" in available
        or "macd_histogram" in available
    ):
        try:
            macd_result = safe_ta_with_fallback(df, "macd", fast=12, slow=26, signal=9)
            if isinstance(macd_result, pd.DataFrame):
                if "macd" in available:
                    col_macd = _get_col_by_prefix(macd_result, "MACD")
                    if (
                        col_macd
                        and not col_macd.startswith("MACDs")
                        and not col_macd.startswith("MACDh")
                    ):
                        result["macd"] = _first_col_or_series(
                            macd_result[[col_macd]], "macd", df.index
                        )
                    elif len(macd_result.columns) > 0:
                        result["macd"] = _first_col_or_series(
                            macd_result.iloc[:, [0]], "macd", df.index
                        )
                    else:
                        result["macd"] = _nan_series(df.index, "macd")

                if "macd_signal" in available:
                    col_signal = _get_col_by_prefix(macd_result, "MACDs")
                    if col_signal:
                        result["macd_signal"] = _first_col_or_series(
                            macd_result[[col_signal]], "macd_signal", df.index
                        )
                    elif len(macd_result.columns) > 1:
                        result["macd_signal"] = _first_col_or_series(
                            macd_result.iloc[:, [1]], "macd_signal", df.index
                        )
                    else:
                        result["macd_signal"] = _nan_series(df.index, "macd_signal")

                # Рассчитываем histogram, если он запрошен ИЛИ если запрошены и macd, и macd_signal
                should_calc_histogram = "macd_histogram" in available or (
                    "macd" in available and "macd_signal" in available
                )
                if should_calc_histogram:
                    col_hist = _get_col_by_prefix(macd_result, "MACDh")
                    if col_hist:
                        result["macd_histogram"] = _first_col_or_series(
                            macd_result[[col_hist]], "macd_histogram", df.index
                        )
                    elif len(macd_result.columns) > 2:
                        result["macd_histogram"] = _first_col_or_series(
                            macd_result.iloc[:, [2]], "macd_histogram", df.index
                        )
                    else:
                        # Вычисляем histogram как macd - macd_signal
                        if "macd" in result and "macd_signal" in result:
                            result["macd_histogram"] = (
                                result["macd"] - result["macd_signal"]
                            )
                        else:
                            result["macd_histogram"] = _nan_series(
                                df.index, "macd_histogram"
                            )
            else:
                for key in ["macd", "macd_signal", "macd_histogram"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта MACD: {type(e).__name__}: {e}")
            for key in ["macd", "macd_signal", "macd_histogram"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # CCI
    for period in [14, 20]:
        key = f"cci_{period}"
        if key in available:
            try:
                cci_result = safe_ta_with_fallback(df, "cci", length=period)
                result[key] = _first_col_or_series(cci_result, key, df.index)
            except Exception as e:
                logger.error(f"Ошибка расчёта CCI_{period}: {type(e).__name__}: {e}")
                result[key] = _nan_series(df.index, key)

    # MFI
    if "mfi" in available:
        try:
            mfi_result = safe_ta_with_fallback(df, "mfi", length=14)
            result["mfi"] = _first_col_or_series(mfi_result, "mfi", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта MFI: {type(e).__name__}: {e}")
            result["mfi"] = _nan_series(df.index, "mfi")

    # ROC
    for period in [10]:
        key = f"roc_{period}"
        if key in available:
            try:
                roc_result = safe_ta_with_fallback(df, "roc", length=period)
                result[key] = _first_col_or_series(roc_result, key, df.index)
            except Exception as e:
                logger.error(f"Ошибка расчёта ROC_{period}: {type(e).__name__}: {e}")
                result[key] = _nan_series(df.index, key)

    # PPO
    if "ppo" in available:
        try:
            ppo_result = safe_ta_with_fallback(df, "ppo", fast=12, slow=26)
            result["ppo"] = _first_col_or_series(ppo_result, "ppo", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта PPO: {type(e).__name__}: {e}")
            result["ppo"] = _nan_series(df.index, "ppo")

    # TRIX
    if "trix" in available:
        try:
            trix_result = safe_ta_with_fallback(df, "trix", length=14)
            result["trix"] = _first_col_or_series(trix_result, "trix", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта TRIX: {type(e).__name__}: {e}")
            result["trix"] = _nan_series(df.index, "trix")

    # Williams %R
    if "willr" in available:
        try:
            willr_result = safe_ta_with_fallback(df, "willr", lbp=14)
            result["willr"] = _first_col_or_series(willr_result, "willr", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта Williams %R: {type(e).__name__}: {e}")
            result["willr"] = _nan_series(df.index, "willr")

    # Awesome Oscillator
    if "ao" in available:
        try:
            ao_result = safe_ta_with_fallback(df, "ao")
            result["ao"] = _first_col_or_series(ao_result, "ao", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта Awesome Oscillator: {type(e).__name__}: {e}")
            result["ao"] = _nan_series(df.index, "ao")

    # Absolute Price Oscillator
    if "apo" in available:
        try:
            apo_result = safe_ta_with_fallback(df, "apo", fast=12, slow=26)
            result["apo"] = _first_col_or_series(apo_result, "apo", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта APO: {type(e).__name__}: {e}")
            result["apo"] = _nan_series(df.index, "apo")

    # Bias
    if "bias" in available:
        try:
            bias_result = safe_ta_with_fallback(df, "bias")
            result["bias"] = _first_col_or_series(bias_result, "bias", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта Bias: {type(e).__name__}: {e}")
            result["bias"] = _nan_series(df.index, "bias")

    # Balance of Power
    if "bop" in available:
        try:
            bop_result = safe_ta_with_fallback(df, "bop")
            result["bop"] = _first_col_or_series(bop_result, "bop", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта BOP: {type(e).__name__}: {e}")
            result["bop"] = _nan_series(df.index, "bop")

    # BRAR
    if "brar" in available:
        try:
            brar_result = safe_ta_with_fallback(df, "brar")
            result["brar"] = _first_col_or_series(brar_result, "brar", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта BRAR: {type(e).__name__}: {e}")
            result["brar"] = _nan_series(df.index, "brar")

    # Chande Forecast Oscillator
    if "cfo" in available:
        try:
            cfo_result = safe_ta_with_fallback(df, "cfo")
            result["cfo"] = _first_col_or_series(cfo_result, "cfo", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта CFO: {type(e).__name__}: {e}")
            result["cfo"] = _nan_series(df.index, "cfo")

    # Center of Gravity
    if "cg" in available:
        try:
            cg_result = safe_ta_with_fallback(df, "cg")
            result["cg"] = _first_col_or_series(cg_result, "cg", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта CG: {type(e).__name__}: {e}")
            result["cg"] = _nan_series(df.index, "cg")

    # Coppock Curve
    if "coppock" in available:
        try:
            coppock_result = safe_ta_with_fallback(df, "coppock")
            result["coppock"] = _first_col_or_series(
                coppock_result, "coppock", df.index
            )
        except Exception as e:
            logger.error(f"Ошибка расчёта Coppock: {type(e).__name__}: {e}")
            result["coppock"] = _nan_series(df.index, "coppock")

    # Efficiency Ratio
    if "er" in available:
        try:
            er_result = safe_ta_with_fallback(df, "er")
            result["er"] = _first_col_or_series(er_result, "er", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта ER: {type(e).__name__}: {e}")
            result["er"] = _nan_series(df.index, "er")

    # Elder Ray Index
    if "eri" in available:
        try:
            eri_result = safe_ta_with_fallback(df, "eri")
            result["eri"] = _first_col_or_series(eri_result, "eri", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта ERI: {type(e).__name__}: {e}")
            result["eri"] = _nan_series(df.index, "eri")

    # Fisher Transform
    if "fisher" in available:
        try:
            fisher_result = safe_ta_with_fallback(df, "fisher")
            result["fisher"] = _first_col_or_series(fisher_result, "fisher", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта Fisher: {type(e).__name__}: {e}")
            result["fisher"] = _nan_series(df.index, "fisher")

    # Inertia
    if "inertia" in available:
        try:
            inertia_result = safe_ta_with_fallback(df, "inertia")
            result["inertia"] = _first_col_or_series(
                inertia_result, "inertia", df.index
            )
        except Exception as e:
            logger.error(f"Ошибка расчёта Inertia: {type(e).__name__}: {e}")
            result["inertia"] = _nan_series(df.index, "inertia")

    # KDJ indicators
    if "kdj_k" in available:
        try:
            if not check_min_length(df, "kdj"):
                logger.warning("KDJ: недостаточно данных (len<9), возвращаю NaN")
                result["kdj_k"] = _nan_series(df.index, "kdj_k")
            else:
                kdj_k_result = safe_ta_with_fallback(df, "kdj", k=9, d=3)
                col_k = (
                    _get_col_by_prefix(kdj_k_result, "KDJk")
                    if isinstance(kdj_k_result, pd.DataFrame)
                    else None
                )
                if col_k:
                    result["kdj_k"] = _first_col_or_series(
                        kdj_k_result[[col_k]], "kdj_k", df.index
                    )
                else:
                    result["kdj_k"] = _first_col_or_series(
                        kdj_k_result, "kdj_k", df.index
                    )
        except Exception as e:
            logger.error(f"Ошибка расчёта KDJ K: {type(e).__name__}: {e}")
            result["kdj_k"] = _nan_series(df.index, "kdj_k")

    if "kdj_d" in available:
        try:
            if not check_min_length(df, "kdj"):
                logger.warning("KDJ: недостаточно данных (len<9), возвращаю NaN")
                result["kdj_d"] = _nan_series(df.index, "kdj_d")
            else:
                kdj_d_result = safe_ta_with_fallback(df, "kdj", k=9, d=3)
                col_d = (
                    _get_col_by_prefix(kdj_d_result, "KDJd")
                    if isinstance(kdj_d_result, pd.DataFrame)
                    else None
                )
                if col_d:
                    result["kdj_d"] = _first_col_or_series(
                        kdj_d_result[[col_d]], "kdj_d", df.index
                    )
                else:
                    result["kdj_d"] = _first_col_or_series(
                        kdj_d_result, "kdj_d", df.index
                    )
        except Exception as e:
            logger.error(f"Ошибка расчёта KDJ D: {type(e).__name__}: {e}")
            result["kdj_d"] = _nan_series(df.index, "kdj_d")

    # Pretty Good Oscillator
    if "pgo" in available:
        try:
            pgo_result = safe_ta_with_fallback(df, "pgo")
            result["pgo"] = _first_col_or_series(pgo_result, "pgo", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта PGO: {type(e).__name__}: {e}")
            result["pgo"] = _nan_series(df.index, "pgo")

    # Percentage Scale
    if "psl" in available:
        try:
            psl_result = safe_ta_with_fallback(df, "psl")
            result["psl"] = _first_col_or_series(psl_result, "psl", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта PSL: {type(e).__name__}: {e}")
            result["psl"] = _nan_series(df.index, "psl")

    # Percentage Volume Oscillator
    if "pvo" in available:
        try:
            pvo_result = safe_ta_with_fallback(df, "pvo")
            result["pvo"] = _first_col_or_series(pvo_result, "pvo", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта PVO: {type(e).__name__}: {e}")
            result["pvo"] = _nan_series(df.index, "pvo")

    # Relative Strength X
    if "rsx" in available:
        try:
            rsx_result = safe_ta_with_fallback(df, "rsx")
            result["rsx"] = _first_col_or_series(rsx_result, "rsx", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта RSX: {type(e).__name__}: {e}")
            result["rsx"] = _nan_series(df.index, "rsx")

    # Jurik RSX
    if "rsx_14" in available:
        try:
            rsx_14_result = safe_ta_with_fallback(df, "rsx", length=14)
            result["rsx_14"] = _first_col_or_series(rsx_14_result, "rsx_14", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта RSX_14: {type(e).__name__}: {e}")
            result["rsx_14"] = _nan_series(df.index, "rsx_14")

    # Relative Vigor Index
    if "rvgi" in available:
        try:
            rvgi_result = safe_ta_with_fallback(df, "rvgi")
            result["rvgi"] = _first_col_or_series(rvgi_result, "rvgi", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта RVGI: {type(e).__name__}: {e}")
            result["rvgi"] = _nan_series(df.index, "rvgi")

    # Slope
    if "slope_20" in available:
        try:
            slope_result = safe_ta_with_fallback(df, "slope", length=20)
            result["slope_20"] = _first_col_or_series(
                slope_result, "slope_20", df.index
            )
        except Exception as e:
            logger.error(f"Ошибка расчёта Slope: {type(e).__name__}: {e}")
            result["slope_20"] = _nan_series(df.index, "slope_20")

    # Stochastic Momentum Index
    if "smi" in available:
        try:
            smi_result = safe_ta_with_fallback(df, "smi")
            result["smi"] = _first_col_or_series(smi_result, "smi", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта SMI: {type(e).__name__}: {e}")
            result["smi"] = _nan_series(df.index, "smi")

    # True Strength Index
    if "tsi" in available:
        try:
            tsi_result = safe_ta_with_fallback(df, "tsi")
            result["tsi"] = _first_col_or_series(tsi_result, "tsi", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта TSI: {type(e).__name__}: {e}")
            result["tsi"] = _nan_series(df.index, "tsi")

    # Ultimate Oscillator
    if "uo" in available:
        try:
            uo_result = safe_ta_with_fallback(df, "uo")
            result["uo"] = _first_col_or_series(uo_result, "uo", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта Ultimate Oscillator: {type(e).__name__}: {e}")
            result["uo"] = _nan_series(df.index, "uo")

    # Stochastic RSI
    if "stochrsi_k" in available or "stochrsi_d" in available:
        try:
            if not check_min_length(df, "stochrsi"):
                logger.warning("STOCHRSI: недостаточно данных (len<14), возвращаю NaN")
                for key in ["stochrsi_k", "stochrsi_d"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
            else:
                stochrsi_result = safe_ta_with_fallback(
                    df, "stochrsi", length=14, rsi_length=14, k=3, d=3
                )

                if isinstance(stochrsi_result, pd.DataFrame):
                    if "stochrsi_k" in available:
                        col_k = _get_col_by_prefix(stochrsi_result, "STOCHRSIk")
                        if col_k:
                            result["stochrsi_k"] = _first_col_or_series(
                                stochrsi_result[[col_k]], "stochrsi_k", df.index
                            )
                        elif len(stochrsi_result.columns) > 0:
                            result["stochrsi_k"] = _first_col_or_series(
                                stochrsi_result.iloc[:, [0]], "stochrsi_k", df.index
                            )
                        else:
                            result["stochrsi_k"] = _nan_series(df.index, "stochrsi_k")

                    if "stochrsi_d" in available:
                        col_d = _get_col_by_prefix(stochrsi_result, "STOCHRSId")
                        if col_d:
                            result["stochrsi_d"] = _first_col_or_series(
                                stochrsi_result[[col_d]], "stochrsi_d", df.index
                            )
                        elif len(stochrsi_result.columns) > 1:
                            result["stochrsi_d"] = _first_col_or_series(
                                stochrsi_result.iloc[:, [1]], "stochrsi_d", df.index
                            )
                        else:
                            result["stochrsi_d"] = _nan_series(df.index, "stochrsi_d")
                else:
                    for key in ["stochrsi_k", "stochrsi_d"]:
                        if key in available:
                            result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта Stochastic RSI: {type(e).__name__}: {e}")
            for key in ["stochrsi_k", "stochrsi_d"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # Гарантируем, что все значения - Series
    assert all(
        isinstance(v, pd.Series) for v in result.values()
    ), "Все значения должны быть Series"

    log_group_results("OSCILLATORS", result)
    return result
