"""
Правила осцилляторов для генерации торговых сигналов.
"""

from decimal import Decimal

from src.signals.config import get_threshold


def rule_rsi14(
    rsi14: Decimal | None, rsi14_prev: Decimal | None = None
) -> tuple[int, str]:
    """
    RSI14 правило: Buy при RSI <= 30, Sell при RSI >= 70

    Args:
        rsi14: Текущее значение RSI14
        rsi14_prev: Предыдущее значение RSI14

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if rsi14 is None:
        return 0, ""

    rsi_buy_threshold = Decimal(str(get_threshold("rsi_buy", 30)))
    rsi_sell_threshold = Decimal(str(get_threshold("rsi_sell", 70)))

    if rsi14 <= rsi_buy_threshold:
        return 1, f"RSI14 oversold (≤{rsi_buy_threshold})"
    if rsi14 >= rsi_sell_threshold:
        return -1, f"RSI14 overbought (≥{rsi_sell_threshold})"

    return 0, ""


def rule_bollinger(
    close: Decimal | None,
    bb_upper: Decimal | None,
    bb_lower: Decimal | None,
    close_prev: Decimal | None = None,
    bb_upper_prev: Decimal | None = None,
    bb_lower_prev: Decimal | None = None,
) -> tuple[int, str]:
    """
    Bollinger Bands правило: Buy при close < BB_lower, Sell при close > BB_upper

    Args:
        close: Цена закрытия
        bb_upper: Верхняя полоса Боллинджера
        bb_lower: Нижняя полоса Боллинджера
        close_prev: Предыдущая цена закрытия
        bb_upper_prev: Предыдущая верхняя полоса
        bb_lower_prev: Предыдущая нижняя полоса

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if any(x is None for x in [close, bb_upper, bb_lower]):
        return 0, ""

    if close < bb_lower:
        return 1, "Close below BB lower band (oversold)"
    if close > bb_upper:
        return -1, "Close above BB upper band (overbought)"

    return 0, ""


def rule_stochastic(
    stoch_k: Decimal | None,
    stoch_d: Decimal | None,
    stoch_k_prev: Decimal | None = None,
    stoch_d_prev: Decimal | None = None,
) -> tuple[int, str]:
    """
    Stochastic правило: K пересекает D снизу в зоне перепроданности для buy,
    K пересекает D сверху в зоне перекупленности для sell

    Args:
        stoch_k: %K
        stoch_d: %D
        stoch_k_prev: Предыдущее значение %K
        stoch_d_prev: Предыдущее значение %D

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if any(x is None for x in [stoch_k, stoch_d]):
        return 0, ""

    # Проверяем пересечение только в экстремальных зонах
    if stoch_k_prev is not None and stoch_d_prev is not None:
        stoch_buy_threshold = Decimal(str(get_threshold("stoch_k_buy", 20)))
        stoch_sell_threshold = Decimal(str(get_threshold("stoch_k_sell", 80)))

        # K пересекает D снизу вверх в зоне перепроданности
        if (
            stoch_k_prev <= stoch_d_prev
            and stoch_k > stoch_d
            and stoch_k < stoch_buy_threshold
        ):
            return (
                1,
                f"Stoch K crosses above D in oversold zone (<{stoch_buy_threshold})",
            )
        # K пересекает D сверху вниз в зоне перекупленности
        if (
            stoch_k_prev >= stoch_d_prev
            and stoch_k < stoch_d
            and stoch_k > stoch_sell_threshold
        ):
            return (
                -1,
                f"Stoch K crosses below D in overbought zone (>{stoch_sell_threshold})",
            )

    # НЕ генерируем сигналы для текущего положения в экстремальных зонах
    # Это предотвращает множественные одинаковые сигналы
    return 0, ""


def rule_keltner(
    close: Decimal | None,
    kc_upper: Decimal | None,
    kc_lower: Decimal | None,
    close_prev: Decimal | None = None,
    kc_upper_prev: Decimal | None = None,
    kc_lower_prev: Decimal | None = None,
) -> tuple[int, str]:
    """
    Keltner Channel правило: Buy при close < KC_lower, Sell при close > KC_upper

    Args:
        close: Цена закрытия
        kc_upper: Верхняя полоса Келтнера
        kc_lower: Нижняя полоса Келтнера
        close_prev: Предыдущая цена закрытия
        kc_upper_prev: Предыдущая верхняя полоса
        kc_lower_prev: Предыдущая нижняя полоса

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if any(x is None for x in [close, kc_upper, kc_lower]):
        return 0, ""

    if close < kc_lower:
        return 1, "Close below KC lower band (oversold)"
    if close > kc_upper:
        return -1, "Close above KC upper band (overbought)"

    return 0, ""
