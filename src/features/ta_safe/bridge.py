"""
TA-Lib bridge for technical indicators.

This module provides a bridge to TA-Lib functions as an alternative backend.
"""

import pandas as pd

from .errors import FeatureCalcError


def _talib_bridge(
    df: pd.DataFrame, name: str, **kwargs: dict[str, object]
) -> pd.DataFrame:
    """
    Мост для TA-Lib функций.

    Args:
        df: DataFrame с OHLCV данными
        name: Имя функции
        **kwargs: Параметры функции

    Returns:
        pd.DataFrame

    Raises:
        FeatureCalcError: Если TA-Lib недоступен или функция не найдена
    """
    try:
        import talib
    except ImportError as err:
        raise FeatureCalcError("TA-Lib not available") from err

    # Маппинг функций pandas_ta на TA-Lib
    talib_mapping = {
        # trange, tr, cdl_doji, cdl_inside исключены из пайплайна
        "ttm_trend": "TTM_TREND",
        "rsi": "RSI",
        "sma": "SMA",
        "ema": "EMA",
        "atr": "ATR",
        "macd": "MACD",
        "bbands": "BBANDS",
        "aroon": "AROON",
    }

    if name not in talib_mapping:
        raise FeatureCalcError(f"TA-Lib mapping not found for {name}")

    talib_func = getattr(talib, talib_mapping[name])

    # Вызываем TA-Lib функцию
    # trange, tr, cdl_doji, cdl_inside исключены из пайплайна
    if name == "rsi":
        length = kwargs.get("length", 14)
        result = talib_func(df["close"].values, timeperiod=length)
    elif name == "sma":
        length = kwargs.get("length", 20)
        result = talib_func(df["close"].values, timeperiod=length)
    elif name == "ema":
        length = kwargs.get("length", 14)
        result = talib_func(df["close"].values, timeperiod=length)
    elif name == "atr":
        length = kwargs.get("length", 14)
        result = talib_func(
            df["high"].values, df["low"].values, df["close"].values, timeperiod=length
        )
    elif name == "macd":
        fast = kwargs.get("fast", 12)
        slow = kwargs.get("slow", 26)
        signal = kwargs.get("signal", 9)
        macd, macd_signal, macd_hist = talib_func(
            df["close"].values, fastperiod=fast, slowperiod=slow, signalperiod=signal
        )
        return pd.DataFrame(
            {"macd": macd, "macd_signal": macd_signal, "macd_histogram": macd_hist},
            index=df.index,
        )
    elif name == "bbands":
        length = kwargs.get("length", 20)
        std = kwargs.get("std", 2.0)
        upper, middle, lower = talib_func(
            df["close"].values, timeperiod=length, nbdevup=std, nbdevdn=std
        )
        return pd.DataFrame(
            {"bb_upper": upper, "bb_middle": middle, "bb_lower": lower}, index=df.index
        )
    elif name == "aroon":
        length = kwargs.get("length", 14)
        aroon_down, aroon_up = talib_func(
            df["high"].values, df["low"].values, timeperiod=length
        )
        aroon_osc = aroon_up - aroon_down
        return pd.DataFrame(
            {"aroon_up": aroon_up, "aroon_down": aroon_down, "aroon_osc": aroon_osc},
            index=df.index,
        )
    else:
        raise FeatureCalcError(f"TA-Lib implementation not available for {name}")

    # Для простых функций возвращаем Series
    return pd.DataFrame({name: result}, index=df.index)
