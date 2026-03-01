"""
Fallback implementations for technical indicators.

This module provides fallback calculations for cases when pandas_ta is unavailable.
"""

import numpy as np
import pandas as pd

from src.logging import get_logger

logger = get_logger(__name__)


def safe_ta_fallback(
    df: pd.DataFrame, name: str, /, **kwargs: dict[str, object]
) -> pd.DataFrame:
    """
    Fallback расчеты для случаев, когда pandas_ta недоступен.

    Args:
        df: DataFrame с OHLCV данными
        name: Имя функции
        **kwargs: Параметры функции

    Returns:
        pd.DataFrame (всегда)
    """
    logger.warning(f"Используем fallback для ta.{name}")

    if name == "ema":
        close = df["close"]
        length = kwargs.get("length", 14)
        result = close.ewm(span=length, adjust=False).mean()
        return result.to_frame(f"ema_{length}")

    if name == "sma":
        close = df["close"]
        length = kwargs.get("length", 20)
        result = close.rolling(window=length).mean()
        return result.to_frame(f"sma_{length}")

    if name == "rsi":
        close = df["close"]
        length = kwargs.get("length", 14)
        delta = close.diff()
        # Wilder-версия RSI
        alpha = 1 / length
        gain = delta.clip(lower=0).ewm(alpha=alpha, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=alpha, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        result = (100 - 100 / (1 + rs)).fillna(50).astype("float64")
        return result.to_frame(f"rsi_{length}")

    if name == "atr":
        high, low, close = df["high"], df["low"], df["close"]
        length = kwargs.get("length", 14)
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        result = tr.ewm(alpha=1 / length, adjust=False).mean()
        return result.to_frame(f"atr_{length}")

    if name == "macd":
        close = df["close"]
        fast = kwargs.get("fast", 12)
        slow = kwargs.get("slow", 26)
        signal = kwargs.get("signal", 9)

        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return pd.DataFrame(
            {"macd": macd_line, "macd_signal": signal_line, "macd_histogram": histogram}
        )

    if name == "bbands":
        close = df["close"]
        length = kwargs.get("length", 20)
        std = kwargs.get("std", 2)

        sma = close.rolling(window=length).mean()
        std_dev = close.rolling(window=length).std()

        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)

        return pd.DataFrame({"bb_upper": upper, "bb_middle": sma, "bb_lower": lower})

    if name == "obv":
        close = df["close"]
        volume = df["volume"]
        # Исправляем fallback для OBV
        price_change = close.diff().fillna(0)
        price_direction = price_change.apply(
            lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
        )
        result = (price_direction * volume).cumsum()
        return result.to_frame("obv")

    if name == "aroon":
        high = df["high"]
        low = df["low"]
        length = kwargs.get("length", 14)
        # Упрощенный расчет Aroon
        high.rolling(window=length).max()
        low.rolling(window=length).min()
        aroon_up = (
            100
            * (
                length
                - (high.rolling(window=length).apply(lambda x: length - x.argmax() - 1))
            )
            / length
        )
        aroon_down = (
            100
            * (
                length
                - (low.rolling(window=length).apply(lambda x: length - x.argmin() - 1))
            )
            / length
        )
        aroon_osc = aroon_up - aroon_down
        return pd.DataFrame(
            {"aroon_up": aroon_up, "aroon_down": aroon_down, "aroon_osc": aroon_osc}
        )
    # trange, tr, cdl_doji, cdl_inside исключены из пайплайна
    # - tr/trange: ATR считает True Range внутри себя
    # - cdl_doji/cdl_inside: используют собственные реализации в candles.py
    if name == "ttm_trend":
        # Упрощенный TTM Trend fallback
        close = df["close"]
        length = kwargs.get("length", 14)
        sma = close.rolling(window=length).mean()
        trend = (close > sma).astype(int)
        return trend.to_frame("ttm_trend")

    if name == "parkinson":
        # Parkinson Volatility fallback
        high = df["high"]
        low = df["low"]
        length = kwargs.get("length", 14)

        # Parkinson Volatility = sqrt(1/(4*ln(2)) * sum(ln(high/low)^2) / n)
        # Упрощенная версия: sqrt(mean(ln(high/low)^2))
        log_hl = np.log(high / low)
        log_hl_squared = log_hl**2
        parkinson_vol = np.sqrt(log_hl_squared.rolling(window=length).mean())

        return parkinson_vol.to_frame("parkinson")

    if name == "dc":
        # Donchian Channel fallback
        high = df["high"]
        low = df["low"]
        length = kwargs.get("length", 20)

        dc_upper = high.rolling(window=length).max()
        dc_lower = low.rolling(window=length).min()
        dc_middle = (dc_upper + dc_lower) / 2

        return pd.DataFrame(
            {"dc_upper": dc_upper, "dc_middle": dc_middle, "dc_lower": dc_lower}
        )

    if name == "vwma":
        # Volume Weighted Moving Average fallback
        close = df["close"]
        volume = df["volume"]
        length = kwargs.get("length", 20)

        vwma = (close * volume).rolling(window=length).sum() / volume.rolling(
            window=length
        ).sum()
        return vwma.to_frame("vwma")

    if name == "vp":
        # Volume Profile fallback (упрощенная версия)
        close = df["close"]
        volume = df["volume"]

        # Упрощенная версия: используем VWAP как точку контроля
        vwap = (close * volume).cumsum() / volume.cumsum()

        # Простая версия Value Area
        price_range = close.max() - close.min()
        vah = vwap + price_range * 0.1  # 10% от диапазона выше VWAP
        val = vwap - price_range * 0.1  # 10% от диапазона ниже VWAP

        return pd.DataFrame(
            {
                "vpc": vwap,  # Point of Control
                "vah": vah,  # Value Area High
                "val": val,  # Value Area Low
            }
        )

    if name == "willr":
        # Williams %R fallback
        high = df["high"]
        low = df["low"]
        close = df["close"]
        lbp = kwargs.get("lbp", kwargs.get("length", 14))

        # Williams %R = -100 * (Highest High - Close) / (Highest High - Lowest Low)
        highest_high = high.rolling(window=lbp).max()
        lowest_low = low.rolling(window=lbp).min()
        willr = (
            -100
            * (highest_high - close)
            / (highest_high - lowest_low).replace(0, np.nan)
        )
        willr = willr.fillna(-50)  # Заполняем NaN средним значением

        return willr.to_frame("willr")

    if name == "uo":
        # Ultimate Oscillator fallback
        high = df["high"]
        low = df["low"]
        close = df["close"]
        short = kwargs.get("short", kwargs.get("short_length", 7))
        medium = kwargs.get("medium", kwargs.get("medium_length", 14))
        long_period = kwargs.get("long", kwargs.get("long_length", 28))

        # Buying Pressure = Close - min(Low, Previous Close)
        prev_close = close.shift(1)
        bp = close - pd.concat([low, prev_close], axis=1).min(axis=1)

        # True Range = max(High - Low, abs(High - Previous Close), abs(Low - Previous Close))
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Average7 = sum(BP, 7) / sum(TR, 7)
        # Average14 = sum(BP, 14) / sum(TR, 14)
        # Average28 = sum(BP, 28) / sum(TR, 28)
        avg7 = bp.rolling(window=short).sum() / tr.rolling(window=short).sum().replace(
            0, np.nan
        )
        avg14 = bp.rolling(window=medium).sum() / tr.rolling(
            window=medium
        ).sum().replace(0, np.nan)
        avg28 = bp.rolling(window=long_period).sum() / tr.rolling(
            window=long_period
        ).sum().replace(0, np.nan)

        # Ultimate Oscillator = 100 * (4 * Average7 + 2 * Average14 + Average28) / 7
        ultosc = 100 * (4 * avg7 + 2 * avg14 + avg28) / 7
        ultosc = ultosc.fillna(50)  # Заполняем NaN средним значением

        return ultosc.to_frame("uo")

    if name == "rsx":
        # Relative Strength X fallback (упрощенная версия RSI)
        close = df["close"]
        length = kwargs.get("length", 14)

        # Упрощенная версия RSX как модификация RSI
        delta = close.diff()
        alpha = 1 / length
        gain = delta.clip(lower=0).ewm(alpha=alpha, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=alpha, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        rsx = (100 - 100 / (1 + rs)).fillna(50)

        return rsx.to_frame("rsx")
    # trange исключён из пайплайна - ATR считает True Range внутри себя
    if name == "ichimoku":
        # Ichimoku Cloud fallback - расчёт всех 5 компонентов
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tenkan = kwargs.get("tenkan", 9)
        kijun = kwargs.get("kijun", 26)
        senkou = kwargs.get("senkou", 52)

        # Tenkan-sen (Conversion Line) = (9-period high + 9-period low) / 2
        tenkan_high = high.rolling(window=tenkan).max()
        tenkan_low = low.rolling(window=tenkan).min()
        ichimoku_tenkan = (tenkan_high + tenkan_low) / 2

        # Kijun-sen (Base Line) = (26-period high + 26-period low) / 2
        kijun_high = high.rolling(window=kijun).max()
        kijun_low = low.rolling(window=kijun).min()
        ichimoku_kijun = (kijun_high + kijun_low) / 2

        # Senkou Span A (Leading Span A) = (Tenkan + Kijun) / 2, сдвинуто на 26 периодов вперёд
        ichimoku_senkou_a = ((ichimoku_tenkan + ichimoku_kijun) / 2).shift(kijun)

        # Senkou Span B (Leading Span B) = (52-period high + 52-period low) / 2, сдвинуто на 26 периодов вперёд
        senkou_high = high.rolling(window=senkou).max()
        senkou_low = low.rolling(window=senkou).min()
        ichimoku_senkou_b = ((senkou_high + senkou_low) / 2).shift(kijun)

        # Chikou Span (Lagging Span) = Close, сдвинуто на 26 периодов назад
        ichimoku_chikou = close.shift(-kijun)

        return pd.DataFrame(
            {
                "ichimoku_tenkan": ichimoku_tenkan,
                "ichimoku_kijun": ichimoku_kijun,
                "ichimoku_senkou_a": ichimoku_senkou_a,
                "ichimoku_senkou_b": ichimoku_senkou_b,
                "ichimoku_chikou": ichimoku_chikou,
            }
        )

    if name == "vortex":
        # Vortex Indicator fallback - расчёт vortex_pos и vortex_neg
        high = df["high"]
        low = df["low"]
        close = df["close"]
        length = kwargs.get("length", 14)

        # True Range
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = np.abs(high - prev_close)
        tr3 = np.abs(low - prev_close)
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        # Positive Movement (VM+) = abs(high - prev_low)
        prev_low = low.shift(1)
        vm_pos = np.abs(high - prev_low)

        # Negative Movement (VM-) = abs(low - prev_high)
        prev_high = high.shift(1)
        vm_neg = np.abs(low - prev_high)

        # Vortex Positive = sum(VM+, length) / sum(TR, length)
        vortex_pos = (
            vm_pos.rolling(window=length).sum() / tr.rolling(window=length).sum()
        )

        # Vortex Negative = sum(VM-, length) / sum(TR, length)
        vortex_neg = (
            vm_neg.rolling(window=length).sum() / tr.rolling(window=length).sum()
        )

        # Общий Vortex = vortex_pos - vortex_neg
        vortex = vortex_pos - vortex_neg

        return pd.DataFrame(
            {
                "vortex_pos": vortex_pos,
                "vortex_neg": vortex_neg,
                "vortex": vortex,
            }
        )

    if name == "t3":
        # T3 Moving Average fallback (Tillson T3)
        close = df["close"]
        length = kwargs.get("length", 20)
        volume_factor = kwargs.get("volume_factor", 0.7)

        # T3 = GD(GD(GD(close))) где GD = GD(close) = EMA(EMA(close))
        # Упрощённая версия: тройная EMA
        ema1 = close.ewm(span=length, adjust=False).mean()
        ema2 = ema1.ewm(span=length, adjust=False).mean()
        ema3 = ema2.ewm(span=length, adjust=False).mean()
        ema4 = ema3.ewm(span=length, adjust=False).mean()
        ema5 = ema4.ewm(span=length, adjust=False).mean()
        ema6 = ema5.ewm(span=length, adjust=False).mean()

        # T3 = c1*GD6 + c2*GD5 + c3*GD4 + c4*GD3
        # где c1, c2, c3, c4 - коэффициенты на основе volume_factor
        c1 = -(volume_factor**3)
        c2 = 3 * volume_factor**2 + 3 * volume_factor**3
        c3 = -6 * volume_factor**2 - 3 * volume_factor - 3 * volume_factor**3
        c4 = 1 + 3 * volume_factor + volume_factor**3 + 3 * volume_factor**2

        t3 = c1 * ema6 + c2 * ema5 + c3 * ema4 + c4 * ema3

        return t3.to_frame("t3")

    # Для неизвестных индикаторов возвращаем NaN DataFrame
    close = df["close"]
    result = pd.Series([np.nan] * len(close), index=close.index)
    return result.to_frame(name)
