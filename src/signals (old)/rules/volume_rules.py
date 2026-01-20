"""
Правила объёмных индикаторов для генерации торговых сигналов.
"""

from decimal import Decimal


def rule_volume_obv_cmf(
    obv: Decimal | None, cmf: Decimal | None, obv_prev: Decimal | None = None
) -> tuple[int, str]:
    """
    OBV / CMF правило: OBV↑ и CMF > 0 для buy, OBV↓ и CMF < 0 для sell

    Args:
        obv: On Balance Volume
        cmf: Chaikin Money Flow
        obv_prev: Предыдущее значение OBV

    Returns:
        Tuple[int, str]: (сигнал, причина)
    """
    if any(x is None for x in [obv, cmf]):
        return 0, ""

    # Проверяем направление OBV
    obv_rising = False
    obv_falling = False

    if obv_prev is not None:
        if obv > obv_prev:
            obv_rising = True
        elif obv < obv_prev:
            obv_falling = True

    # Генерируем сигналы
    if obv_rising and cmf > Decimal("0"):
        return 1, "OBV rising and CMF > 0 (bullish volume)"
    if obv_falling and cmf < Decimal("0"):
        return -1, "OBV falling and CMF < 0 (bearish volume)"

    return 0, ""
