"""Per-indicator TA-Lib adapters with unified DataFrame outputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ...domain.protocols import IndicatorAdapter


def _talib():
    import talib

    return talib


def rsi_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 14))
    result = _talib().RSI(df["close"].values, timeperiod=length)
    return pd.DataFrame(
        {"rsi_14" if length == 14 else f"rsi_{length}": result}, index=df.index
    )


def sma_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 20))
    result = _talib().SMA(df["close"].values, timeperiod=length)
    return pd.DataFrame(
        {"sma_20" if length == 20 else f"sma_{length}": result}, index=df.index
    )


def ema_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 14))
    result = _talib().EMA(df["close"].values, timeperiod=length)
    return pd.DataFrame(
        {"ema_14" if length == 14 else f"ema_{length}": result}, index=df.index
    )


def atr_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 14))
    result = _talib().ATR(
        df["high"].values, df["low"].values, df["close"].values, timeperiod=length
    )
    return pd.DataFrame(
        {"atr_14" if length == 14 else f"atr_{length}": result}, index=df.index
    )


def macd_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    fast = int(kwargs.get("fast", 12))
    slow = int(kwargs.get("slow", 26))
    signal = int(kwargs.get("signal", 9))
    macd, macd_signal, macd_hist = _talib().MACD(
        df["close"].values, fastperiod=fast, slowperiod=slow, signalperiod=signal
    )
    return pd.DataFrame(
        {"macd": macd, "macd_signal": macd_signal, "macd_histogram": macd_hist},
        index=df.index,
    )


def bbands_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 20))
    std = float(kwargs.get("std", 2.0))
    upper, middle, lower = _talib().BBANDS(
        df["close"].values, timeperiod=length, nbdevup=std, nbdevdn=std
    )
    return pd.DataFrame(
        {"bb_upper": upper, "bb_middle": middle, "bb_lower": lower},
        index=df.index,
    )


def aroon_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 14))
    aroon_down, aroon_up = _talib().AROON(
        df["high"].values, df["low"].values, timeperiod=length
    )
    return pd.DataFrame(
        {
            "aroon_up": aroon_up,
            "aroon_down": aroon_down,
            "aroon_osc": aroon_up - aroon_down,
        },
        index=df.index,
    )


def adx_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 14))
    talib = _talib()
    adx = talib.ADX(
        df["high"].values, df["low"].values, df["close"].values, timeperiod=length
    )
    pos = talib.PLUS_DI(
        df["high"].values, df["low"].values, df["close"].values, timeperiod=length
    )
    neg = talib.MINUS_DI(
        df["high"].values, df["low"].values, df["close"].values, timeperiod=length
    )
    return pd.DataFrame(
        {
            "adx_14" if length == 14 else f"adx_{length}": adx,
            "adx_pos_di": pos,
            "adx_neg_di": neg,
        },
        index=df.index,
    )


def stoch_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    talib = _talib()
    k_period = int(kwargs.get("k", kwargs.get("k_period", 14)))
    d_period = int(kwargs.get("d", kwargs.get("d_period", 3)))
    smooth = int(kwargs.get("smooth_k", 3))
    stoch_k, stoch_d = talib.STOCH(
        df["high"].values,
        df["low"].values,
        df["close"].values,
        fastk_period=k_period,
        slowk_period=smooth,
        slowd_period=d_period,
    )
    return pd.DataFrame({"stoch_k": stoch_k, "stoch_d": stoch_d}, index=df.index)


def cci_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 20))
    result = _talib().CCI(
        df["high"].values, df["low"].values, df["close"].values, timeperiod=length
    )
    return pd.DataFrame(
        {"cci_20" if length == 20 else f"cci_{length}": result}, index=df.index
    )


def willr_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", kwargs.get("lbp", 14)))
    result = _talib().WILLR(
        df["high"].values, df["low"].values, df["close"].values, timeperiod=length
    )
    return pd.DataFrame({"willr": result}, index=df.index)


def obv_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    result = _talib().OBV(df["close"].values, df["volume"].values)
    return pd.DataFrame({"obv": result}, index=df.index)


def mfi_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 14))
    result = _talib().MFI(
        df["high"].values,
        df["low"].values,
        df["close"].values,
        df["volume"].values,
        timeperiod=length,
    )
    return pd.DataFrame(
        {"mfi_14" if length == 14 else f"mfi_{length}": result}, index=df.index
    )


def natr_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 14))
    result = _talib().NATR(
        df["high"].values, df["low"].values, df["close"].values, timeperiod=length
    )
    return pd.DataFrame(
        {"natr_14" if length == 14 else f"natr_{length}": result}, index=df.index
    )


def roc_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 10))
    result = _talib().ROC(df["close"].values, timeperiod=length)
    return pd.DataFrame(
        {"roc_10" if length == 10 else f"roc_{length}": result}, index=df.index
    )


def mom_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 10))
    result = _talib().MOM(df["close"].values, timeperiod=length)
    return pd.DataFrame(
        {"mom_10" if length == 10 else f"mom_{length}": result}, index=df.index
    )


# ---------------------------------------------------------------------------
# MA group: additional adapters
# ---------------------------------------------------------------------------


def wma_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 20))
    result = _talib().WMA(df["close"].values, timeperiod=length)
    return pd.DataFrame({f"wma_{length}": result}, index=df.index)


def kama_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 10))
    result = _talib().KAMA(df["close"].values, timeperiod=length)
    return pd.DataFrame({f"kama_{length}": result}, index=df.index)


def tema_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 20))
    result = _talib().TEMA(df["close"].values, timeperiod=length)
    return pd.DataFrame({f"tema_{length}": result}, index=df.index)


def dema_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 20))
    result = _talib().DEMA(df["close"].values, timeperiod=length)
    return pd.DataFrame({f"dema_{length}": result}, index=df.index)


def trima_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 20))
    result = _talib().TRIMA(df["close"].values, timeperiod=length)
    return pd.DataFrame({f"trima_{length}": result}, index=df.index)


def t3_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 20))
    volume_factor = float(kwargs.get("volume_factor", 0.7))
    result = _talib().T3(
        df["close"].values,
        timeperiod=length,
        vfactor=volume_factor,
    )
    return pd.DataFrame({f"t3_{length}": result}, index=df.index)


def linreg_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 14))
    result = _talib().LINEARREG(df["close"].values, timeperiod=length)
    return pd.DataFrame({f"linreg_{length}": result}, index=df.index)


# ---------------------------------------------------------------------------
# Oscillators group: additional adapters
# ---------------------------------------------------------------------------


def stochrsi_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 14))
    fastk_period = int(kwargs.get("rsi_length", kwargs.get("fastk_period", 5)))
    fastd_period = int(kwargs.get("k", kwargs.get("fastd_period", 3)))
    talib = _talib()
    fastk, fastd = talib.STOCHRSI(
        df["close"].values,
        timeperiod=length,
        fastk_period=fastk_period,
        fastd_period=fastd_period,
    )
    return pd.DataFrame({"stochrsi_k": fastk, "stochrsi_d": fastd}, index=df.index)


def ppo_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    fast = int(kwargs.get("fast", 12))
    slow = int(kwargs.get("slow", 26))
    result = _talib().PPO(df["close"].values, fastperiod=fast, slowperiod=slow)
    return pd.DataFrame({"ppo": result}, index=df.index)


def apo_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    fast = int(kwargs.get("fast", 12))
    slow = int(kwargs.get("slow", 26))
    result = _talib().APO(df["close"].values, fastperiod=fast, slowperiod=slow)
    return pd.DataFrame({"apo": result}, index=df.index)


def bop_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    result = _talib().BOP(
        df["open"].values,
        df["high"].values,
        df["low"].values,
        df["close"].values,
    )
    return pd.DataFrame({"bop": result}, index=df.index)


def trix_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    length = int(kwargs.get("length", 18))
    result = _talib().TRIX(df["close"].values, timeperiod=length)
    return pd.DataFrame({f"trix_{length}": result}, index=df.index)


# ---------------------------------------------------------------------------
# Volume group: additional adapters
# ---------------------------------------------------------------------------


def ad_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    result = _talib().AD(
        df["high"].values,
        df["low"].values,
        df["close"].values,
        df["volume"].values,
    )
    return pd.DataFrame({"ad": result}, index=df.index)


def adosc_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    fast = int(kwargs.get("fast", 3))
    slow = int(kwargs.get("slow", 10))
    result = _talib().ADOSC(
        df["high"].values,
        df["low"].values,
        df["close"].values,
        df["volume"].values,
        fastperiod=fast,
        slowperiod=slow,
    )
    return pd.DataFrame({"adosc": result}, index=df.index)


def uo_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    fast = int(kwargs.get("fast", kwargs.get("short", 7)))
    medium = int(kwargs.get("medium", 14))
    slow = int(kwargs.get("slow", kwargs.get("long", 28)))
    result = _talib().ULTOSC(
        df["high"].values,
        df["low"].values,
        df["close"].values,
        timeperiod1=fast,
        timeperiod2=medium,
        timeperiod3=slow,
    )
    return pd.DataFrame({"uo": result}, index=df.index)


def psar_talib(df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    af = float(kwargs.get("af", 0.02))
    max_af = float(kwargs.get("max_af", 0.2))
    result = _talib().SAR(
        df["high"].values,
        df["low"].values,
        acceleration=af,
        maximum=max_af,
    )
    psar = pd.Series(result, index=df.index, name="psar")
    long_mask = df["close"] >= psar
    short_mask = ~long_mask
    return pd.DataFrame(
        {
            "psar": psar,
            "psar_long": psar.where(long_mask),
            "psar_short": psar.where(short_mask),
        },
        index=df.index,
    )


TALIB_DISPATCH: dict[str, IndicatorAdapter] = {
    # MA
    "sma": sma_talib,
    "ema": ema_talib,
    "wma": wma_talib,
    "kama": kama_talib,
    "tema": tema_talib,
    "dema": dema_talib,
    "t3": t3_talib,
    "trima": trima_talib,
    "linreg": linreg_talib,
    # Oscillators
    "rsi": rsi_talib,
    "macd": macd_talib,
    "stoch": stoch_talib,
    "stochrsi": stochrsi_talib,
    "cci": cci_talib,
    "mfi": mfi_talib,
    "roc": roc_talib,
    "mom": mom_talib,
    "willr": willr_talib,
    "apo": apo_talib,
    "bop": bop_talib,
    "ppo": ppo_talib,
    "trix": trix_talib,
    "uo": uo_talib,
    # Volatility
    "atr": atr_talib,
    "bbands": bbands_talib,
    "natr": natr_talib,
    # Volume
    "obv": obv_talib,
    "ad": ad_talib,
    "adosc": adosc_talib,
    # Trend
    "adx": adx_talib,
    "aroon": aroon_talib,
    "psar": psar_talib,
}
