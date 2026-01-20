import logging

import pandas as pd
import pandas_ta as ta

from .data_cleaner import clean_close_data, clean_ohlcv_data, create_nan_series


def calc_oscillator_indicators(df: pd.DataFrame, available: set) -> dict:
    result = {}
    # RSI
    if "rsi14" in available:
        close_clean, has_sufficient_data = clean_close_data(df, min_length=14)
        if has_sufficient_data:
            rsi_series = ta.rsi(close_clean, length=14)
            result["rsi14"] = (
                rsi_series if rsi_series is not None else create_nan_series(df)
            )
        else:
            result["rsi14"] = create_nan_series(df)
    # Stochastic
    if "stoch_k" in available or "stoch_d" in available:
        open_clean, high_clean, low_clean, close_clean, has_sufficient_data = (
            clean_ohlcv_data(df, min_length=14)
        )
        if has_sufficient_data:
            stoch = ta.stoch(high_clean, low_clean, close_clean, k=14, d=3)
            if stoch is not None:
                if "stoch_k" in available and "STOCHk_14_3_3" in stoch:
                    result["stoch_k"] = stoch["STOCHk_14_3_3"]
                if "stoch_d" in available and "STOCHd_14_3_3" in stoch:
                    result["stoch_d"] = stoch["STOCHd_14_3_3"]
            else:
                if "stoch_k" in available:
                    result["stoch_k"] = create_nan_series(df)
                if "stoch_d" in available:
                    result["stoch_d"] = create_nan_series(df)
        else:
            if "stoch_k" in available:
                result["stoch_k"] = create_nan_series(df)
            if "stoch_d" in available:
                result["stoch_d"] = create_nan_series(df)
    # MACD
    if (
        "macd" in available
        or "macd_signal" in available
        or "macd_histogram" in available
    ):
        close_clean, has_sufficient_data = clean_close_data(df, min_length=26)
        if has_sufficient_data:
            try:
                # Дополнительная проверка - убеждаемся что нет None значений
                if close_clean.isnull().any() or (close_clean is None).any():
                    symbol_name = getattr(df, "name", "unknown")
                    timeframe_name = getattr(df, "timeframe", "unknown")
                    logging.warning(
                        f"MACD skipped for {symbol_name} {timeframe_name}: still contains None/NaN after cleaning"
                    )
                    if "macd" in available:
                        result["macd"] = create_nan_series(df)
                    if "macd_signal" in available:
                        result["macd_signal"] = create_nan_series(df)
                    if "macd_histogram" in available:
                        result["macd_histogram"] = create_nan_series(df)
                else:
                    macd = ta.macd(close_clean, fast=12, slow=26, signal=9)
                # Проверяем, что это DataFrame и нет None внутри
                if (
                    macd is not None
                    and isinstance(macd, pd.DataFrame)
                    and all(macd[c].dtype.kind in "fi" for c in macd.columns)
                    and not macd.isnull().all().all()
                ):
                    if "macd" in available and "MACD_12_26_9" in macd:
                        result["macd"] = macd["MACD_12_26_9"]
                    if "macd_signal" in available and "MACDs_12_26_9" in macd:
                        result["macd_signal"] = macd["MACDs_12_26_9"]
                    if "macd_histogram" in available and "MACDh_12_26_9" in macd:
                        result["macd_histogram"] = macd["MACDh_12_26_9"]
                else:
                    logging.warning(
                        "MACD not computed or contains None/NaN (len=%s). Symbol=%s timeframe=%s",
                        len(df),
                        getattr(df, "name", "?"),
                        getattr(df, "timeframe", "?"),
                    )
                    if "macd" in available:
                        result["macd"] = create_nan_series(df)
                    if "macd_signal" in available:
                        result["macd_signal"] = create_nan_series(df)
                    if "macd_histogram" in available:
                        result["macd_histogram"] = create_nan_series(df)
            except Exception as e:
                # Более детальное логирование ошибки MACD
                symbol_name = getattr(df, "name", "unknown")
                timeframe_name = getattr(df, "timeframe", "unknown")
                logging.warning(
                    f"MACD calculation error for {symbol_name} {timeframe_name}: {e} (data length: {len(df)})"
                )
                if "macd" in available:
                    result["macd"] = create_nan_series(df)
                if "macd_signal" in available:
                    result["macd_signal"] = create_nan_series(df)
                if "macd_histogram" in available:
                    result["macd_histogram"] = create_nan_series(df)
        else:
            if "macd" in available:
                result["macd"] = create_nan_series(df)
            if "macd_signal" in available:
                result["macd_signal"] = create_nan_series(df)
            if "macd_histogram" in available:
                result["macd_histogram"] = create_nan_series(df)
    # ADX
    if "adx14" in available or "adx_pos_di" in available or "adx_neg_di" in available:
        open_clean, high_clean, low_clean, close_clean, has_sufficient_data = (
            clean_ohlcv_data(df, min_length=14)
        )
        if has_sufficient_data:
            adx = ta.adx(high_clean, low_clean, close_clean, length=14)
            if adx is not None:
                if "adx14" in available and "ADX_14" in adx:
                    result["adx14"] = adx["ADX_14"]
                if "adx_pos_di" in available and "DMP_14" in adx:
                    result["adx_pos_di"] = adx["DMP_14"]
                if "adx_neg_di" in available and "DMN_14" in adx:
                    result["adx_neg_di"] = adx["DMN_14"]
            else:
                if "adx14" in available:
                    result["adx14"] = create_nan_series(df)
                if "adx_pos_di" in available:
                    result["adx_pos_di"] = create_nan_series(df)
                if "adx_neg_di" in available:
                    result["adx_neg_di"] = create_nan_series(df)
        else:
            if "adx14" in available:
                result["adx14"] = create_nan_series(df)
            if "adx_pos_di" in available:
                result["adx_pos_di"] = create_nan_series(df)
            if "adx_neg_di" in available:
                result["adx_neg_di"] = create_nan_series(df)
    return result
