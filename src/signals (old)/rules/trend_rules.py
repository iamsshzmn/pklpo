"""
Трендовые правила для генерации торговых сигналов.
"""

from decimal import Decimal

from src.signals.config import get_threshold


def rule_ema21_sma50(
    close: Decimal | None,
    ema21: Decimal | None,
    sma50: Decimal | None,
    close_prev: Decimal | None = None,
    ema21_prev: Decimal | None = None,
    sma50_prev: Decimal | None = None,
) -> tuple[int, str]:
    """
    EMA21 vs SMA50 правило: Buy при close > EMA21 > SMA50, Sell при close < EMA21 < SMA50

    Args:
        close: Цена закрытия
        ema21: EMA21
        sma50: SMA50
        close_prev: Предыдущая цена закрытия
        ema21_prev: Предыдущее значение EMA21
        sma50_prev: Предыдущее значение SMA50

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if any(x is None for x in [close, ema21, sma50]):
        return 0, ""

    if close > ema21 > sma50:
        return 1, "Close > EMA21 > SMA50 (uptrend)"
    if close < ema21 < sma50:
        return -1, "Close < EMA21 < SMA50 (downtrend)"

    return 0, ""


def rule_sma50_sma200(
    sma50: Decimal | None,
    sma200: Decimal | None,
    sma50_prev: Decimal | None = None,
    sma200_prev: Decimal | None = None,
) -> tuple[int, str]:
    """
    SMA50 vs SMA200 правило: Золотой/мёртвый крест

    Args:
        sma50: SMA50
        sma200: SMA200
        sma50_prev: Предыдущее значение SMA50
        sma200_prev: Предыдущее значение SMA200

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if any(x is None for x in [sma50, sma200]):
        return 0, ""

    # Проверяем пересечение
    if sma50_prev is not None and sma200_prev is not None:
        # Золотой крест: SMA50 пересекает SMA200 снизу вверх
        if sma50_prev <= sma200_prev and sma50 > sma200:
            return 1, "Golden Cross: SMA50 crosses above SMA200"
        # Мёртвый крест: SMA50 пересекает SMA200 сверху вниз
        if sma50_prev >= sma200_prev and sma50 < sma200:
            return -1, "Death Cross: SMA50 crosses below SMA200"

    # Текущее положение (как в плане)
    if sma50 > sma200:
        return 1, "SMA50 > SMA200 (bullish)"
    if sma50 < sma200:
        return -1, "SMA50 < SMA200 (bearish)"

    return 0, ""


def rule_macd(
    macd: Decimal | None,
    macd_signal: Decimal | None,
    macd_prev: Decimal | None = None,
    macd_signal_prev: Decimal | None = None,
) -> tuple[int, str]:
    """
    MACD правило: пересечение MACD и Signal

    Args:
        macd: MACD
        macd_signal: MACD Signal
        macd_prev: Предыдущее значение MACD
        macd_signal_prev: Предыдущее значение MACD Signal

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if any(x is None for x in [macd, macd_signal]):
        return 0, ""

    # Проверяем пересечение
    if macd_prev is not None and macd_signal_prev is not None:
        # MACD пересекает Signal снизу вверх
        if macd_prev <= macd_signal_prev and macd > macd_signal:
            return 1, "MACD crosses above Signal (bullish)"
        # MACD пересекает Signal сверху вниз
        if macd_prev >= macd_signal_prev and macd < macd_signal:
            return -1, "MACD crosses below Signal (bearish)"

    # Текущее положение (как в плане)
    if macd > macd_signal:
        return 1, "MACD > Signal (bullish)"
    if macd < macd_signal:
        return -1, "MACD < Signal (bearish)"

    return 0, ""


def rule_adx14(
    adx14: Decimal | None,
    plus_di: Decimal | None,
    minus_di: Decimal | None,
    adx14_prev: Decimal | None = None,
    plus_di_prev: Decimal | None = None,
    minus_di_prev: Decimal | None = None,
) -> tuple[int, str]:
    """
    ADX14 правило: ADX > 25 и +DI > -DI для buy, ADX > 25 и -DI > +DI для sell

    Args:
        adx14: ADX14
        plus_di: +DI
        minus_di: -DI
        adx14_prev: Предыдущее значение ADX14
        plus_di_prev: Предыдущее значение +DI
        minus_di_prev: Предыдущее значение -DI

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if any(x is None for x in [adx14, plus_di, minus_di]):
        return 0, ""

    adx_threshold = Decimal(str(get_threshold("adx_threshold", 25)))

    if adx14 > adx_threshold:
        if plus_di > minus_di:
            return (
                1,
                f"ADX14 strong trend ({adx14} > {adx_threshold}) and +DI > -DI (bullish)",
            )
        if minus_di > plus_di:
            return (
                -1,
                f"ADX14 strong trend ({adx14} > {adx_threshold}) and -DI > +DI (bearish)",
            )

    return 0, ""


def rule_ichimoku(
    close: Decimal | None,
    kijun: Decimal | None,
    tenkan: Decimal | None,
    close_prev: Decimal | None = None,
    kijun_prev: Decimal | None = None,
    tenkan_prev: Decimal | None = None,
) -> tuple[int, str]:
    """
    Ichimoku правило: цена > Kijun и Tenkan > Kijun для buy, цена < Kijun и Tenkan < Kijun для sell

    Args:
        close: Цена закрытия
        kijun: Kijun-sen
        tenkan: Tenkan-sen
        close_prev: Предыдущая цена закрытия
        kijun_prev: Предыдущее значение Kijun
        tenkan_prev: Предыдущее значение Tenkan

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if any(x is None for x in [close, kijun, tenkan]):
        return 0, ""

    if close > kijun and tenkan > kijun:
        return 1, "Price > Kijun and Tenkan > Kijun (bullish)"
    if close < kijun and tenkan < kijun:
        return -1, "Price < Kijun and Tenkan < Kijun (bearish)"

    return 0, ""
