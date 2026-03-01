"""
Единый маппинг имён индикаторов для устранения рассинхронизации.

Этот модуль обеспечивает консистентность имён между:
- pandas_ta именами
- нашими каноническими именами
- именами в схеме БД
"""

# Маппинг pandas_ta имён на канонические
PANDAS_TA_TO_CANONICAL = {
    # Bollinger Bands
    "BBL_20_2.0": "bb_lower",
    "BBM_20_2.0": "bb_middle",
    "BBU_20_2.0": "bb_upper",
    "bbands_upper": "bb_upper",
    "bbands_middle": "bb_middle",
    "bbands_lower": "bb_lower",
    # Overlap
    "hl_2": "hl2",
    "ohlc_4": "ohlc4",
    "typical_price": "hlc3",
    "midpoint": "hl2",
    "midprice": "hl2",
    # Ichimoku
    "ITS_9": "ichimoku_tenkan",
    "IKS_26": "ichimoku_kijun",
    "ISA_9": "ichimoku_senkou_a",
    "ISB_26": "ichimoku_senkou_b",
    "ICS_26": "ichimoku_chikou",
    # Keltner Channel
    "KCU_20_2.0": "kc_upper",
    "KCBE_20_2.0": "kc_middle",
    "KCL_20_2.0": "kc_lower",
    "kcue_20_2.0": "kc_upper",
    "kcbe_20_2.0": "kc_middle",
    "kcle_20_2.0": "kc_lower",
    # Donchian Channel
    "DCU_20": "dc_upper",
    "DCM_20": "dc_middle",
    "DCL_20": "dc_lower",
    # MACD
    "MACD_12_26_9": "macd",
    "MACDs_12_26_9": "macd_signal",
    "MACDh_12_26_9": "macd_histogram",
    # Stochastic
    "STOCHk_14_3_3": "stoch_k",
    "STOCHd_14_3_3": "stoch_d",
    # ADX
    "ADX_14": "adx_14",
    "DMP_14": "adx_pos_di",
    "DMN_14": "adx_neg_di",
    # Aroon
    "AROONU_14": "aroon_up",
    "AROOND_14": "aroon_down",
    "AROONOSC_14": "aroon_osc",
    # Supertrend
    "SUPERT_10_3.0": "supertrend",
    "SUPERTd_10_3.0": "supertrend_direction",
    "SUPERTl_10_3.0": "supertrend_long",
    "SUPERTs_10_3.0": "supertrend_short",
    # PSAR
    "PSARl_0.02_0.2": "psar_long",
    "PSARs_0.02_0.2": "psar_short",
}

# Обратный маппинг (канонические -> возможные варианты)
CANONICAL_ALIASES = {
    "bb_upper": ["bbands_upper", "BBU_20_2.0"],
    "bb_middle": ["bbands_middle", "BBM_20_2.0"],
    "bb_lower": ["bbands_lower", "BBL_20_2.0"],
    "hl2": ["hl_2", "midpoint", "midprice"],
    "hlc3": ["typical_price"],
    "ohlc4": ["ohlc_4"],
    "ichimoku_tenkan": ["ITS_9"],
    "ichimoku_kijun": ["IKS_26"],
    "ichimoku_senkou_a": ["ISA_9"],
    "ichimoku_senkou_b": ["ISB_26"],
    "ichimoku_chikou": ["ICS_26", "ics_26"],
    "kc_upper": ["KCU_20_2.0", "kcue_20_2.0"],
    "kc_middle": ["KCBE_20_2.0", "kcbe_20_2.0"],
    "kc_lower": ["KCL_20_2.0", "kcle_20_2.0"],
    "dc_upper": ["DCU_20"],
    "dc_middle": ["DCM_20"],
    "dc_lower": ["DCL_20"],
}

# Критические поля, которые должны сохраняться даже с NaN
CRITICAL_ALWAYS_SAVE = {
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "hl2",
    "hlc3",
    "ohlc4",
    "ichimoku_tenkan",
    "ichimoku_kijun",
    "ichimoku_senkou_a",
    "ichimoku_senkou_b",
    "ichimoku_chikou",
    "ics_26",
    "t3_20",
    "rma_20",
}


def normalize_name(name: str) -> str:
    """
    Нормализует имя индикатора к каноническому виду.

    Args:
        name: Имя индикатора (может быть из pandas_ta или другое)

    Returns:
        Каноническое имя индикатора
    """
    # Сначала проверяем прямой маппинг
    if name in PANDAS_TA_TO_CANONICAL:
        return PANDAS_TA_TO_CANONICAL[name]

    # Если имя уже каноническое, возвращаем как есть
    if name in CANONICAL_ALIASES or name in CRITICAL_ALWAYS_SAVE:
        return name

    # Проверяем по префиксам для BB
    if (
        name.startswith("BBL_")
        or name.startswith("bbands_lower")
        or name.startswith("bb_lower")
    ):
        return "bb_lower"
    if (
        name.startswith("BBM_")
        or name.startswith("bbands_middle")
        or name.startswith("bb_middle")
    ):
        return "bb_middle"
    if (
        name.startswith("BBU_")
        or name.startswith("bbands_upper")
        or name.startswith("bb_upper")
    ):
        return "bb_upper"

    # Для остальных возвращаем как есть (lowercase)
    return name.lower().replace(" ", "_")
