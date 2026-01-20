"""
Анализ пустых (null) индикаторов в JSON экспорте.

Проверяет JSON файл и выводит список всех null значений с группировкой по категориям.
"""

import json
import sys
from pathlib import Path

# Маппинг человекочитаемых имен на канонические имена БД
HUMAN_TO_CANONICAL = {
    "Macd Histogram": "macd_histogram",
    "Aroon 14": "aroon_14",
    "Psar": "psar",
    "Trix 14": "trix_14",
    "Bb Upper": "bb_upper",
    "Bb Middle": "bb_middle",
    "Bb Lower": "bb_lower",
    "Kc Upper": "kc_upper",
    "Kc Middle": "kc_middle",
    "Kc Lower": "kc_lower",
    "Accbands Upper": "accbands_upper",
    "Accbands Middle": "accbands_middle",
    "Accbands Lower": "accbands_lower",
    "Ichimoku Senkou A": "ichimoku_senkou_a",
    "Ichimoku Senkou B": "ichimoku_senkou_b",
    "Ichimoku Tenkan": "ichimoku_tenkan",
    "Ichimoku Kijun": "ichimoku_kijun",
    "Ttm Squeeze On": "ttm_squeeze_on",
    "Ttm Squeeze Hist": "ttm_squeeze_hist",
    "Ttm Squeeze Value": "ttm_squeeze_value",
    "Dpo 20": "dpo_20",
    "Dpo": "dpo",
    "Kst": "kst",
    "Mom 10": "mom_10",
    "Ppo Signal": "ppo_signal",
    "Ppo Histogram": "ppo_histogram",
    "Qqe": "qqe",
    "Aberration": "aberration",
    "Efi": "efi",
    "Eom": "eom",
    "Chop": "chop",
    "Decay": "decay",
    "Decreasing": "decreasing",
    "Increasing": "increasing",
    "Long Run": "long_run",
    "Short Run": "short_run",
    "Tsf": "tsf",
    "Qstick": "qstick",
    "Hl2": "hl2",
    "Hlc3": "hlc3",
    "Ohlc4": "ohlc4",
    "Supertrend": "supertrend",
    "Supertrend Direction": "supertrend_direction",
    "Supertrend Short": "supertrend_short",
    "Psar Direction": "psar_direction",
    "Psar Short": "psar_short",
    "Max Drawdown 20": "max_drawdown_20",
    "Volatility 20": "volatility_20",
    "Returns 20": "returns_20",
    "Sharpe 20": "sharpe_20",
}

# Группировка по категориям
CATEGORIES = {
    "overlap": ["hl2", "hlc3", "ohlc4"],
    "volatility": [
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "kc_upper",
        "kc_middle",
        "kc_lower",
        "accbands_upper",
        "accbands_middle",
        "accbands_lower",
    ],
    "trend": [
        "ichimoku_tenkan",
        "ichimoku_kijun",
        "ichimoku_senkou_a",
        "ichimoku_senkou_b",
        "supertrend",
        "supertrend_direction",
        "supertrend_short",
        "psar",
        "psar_direction",
        "psar_short",
        "aroon_14",
    ],
    "oscillators": ["macd_histogram", "trix_14", "ppo_signal", "ppo_histogram", "qqe"],
    "volume": ["efi", "eom"],
    "momentum": ["dpo_20", "dpo", "kst", "mom_10"],
    "squeeze": ["ttm_squeeze_on", "ttm_squeeze_hist", "ttm_squeeze_value"],
    "trend_helpers": [
        "chop",
        "decay",
        "decreasing",
        "increasing",
        "long_run",
        "short_run",
        "qstick",
        "tsf",
    ],
    "performance": ["max_drawdown_20", "volatility_20", "returns_20", "sharpe_20"],
    "aberration": ["aberration"],
}


def analyze_json(json_path: Path) -> dict[str, list[str]]:
    """Анализирует JSON файл и возвращает пустые индикаторы по категориям."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    if not data or len(data) == 0:
        print("JSON файл пуст")
        return {}

    row = data[0]
    null_indicators = []

    for key, value in row.items():
        # Пропускаем служебные поля
        if key in [
            "Symbol",
            "Timeframe",
            "Timestamp",
            "Calculated At",
            "Run ID",
            "Params Hash",
            "Data Quality Status",
            "Nan Count",
            "Valid Rate",
            "Schema Version",
            "Algo Version",
            "Updated At",
        ]:
            continue

        # Проверяем на null или пустую строку
        if value is None or value == "":
            canonical = HUMAN_TO_CANONICAL.get(key, key.lower().replace(" ", "_"))
            null_indicators.append((key, canonical))

    # Группируем по категориям
    categorized: dict[str, list[str]] = {}
    uncategorized = []

    for human_name, canonical in null_indicators:
        found = False
        for category, indicators in CATEGORIES.items():
            if canonical in indicators:
                if category not in categorized:
                    categorized[category] = []
                categorized[category].append(f"{human_name} ({canonical})")
                found = True
                break
        if not found:
            uncategorized.append(f"{human_name} ({canonical})")

    if uncategorized:
        categorized["uncategorized"] = uncategorized

    return categorized


def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python analyze_null_indicators.py <json_file>")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"Файл не найден: {json_path}")
        sys.exit(1)

    categorized = analyze_json(json_path)

    print("=" * 80)
    print("АНАЛИЗ ПУСТЫХ ИНДИКАТОРОВ В JSON")
    print("=" * 80)
    print()

    total_null = sum(len(v) for v in categorized.values())
    print(f"Всего пустых индикаторов: {total_null}")
    print()

    for category, indicators in sorted(categorized.items()):
        print(f"{category.upper()}: {len(indicators)}")
        for ind in sorted(indicators):
            print(f"  - {ind}")
        print()

    # Критичные проблемы
    critical = []
    if "overlap" in categorized:
        critical.extend(categorized["overlap"])
    if "volatility" in categorized and any(
        "bb_" in ind or "kc_" in ind for ind in categorized["volatility"]
    ):
        critical.extend(
            [ind for ind in categorized["volatility"] if "bb_" in ind or "kc_" in ind]
        )
    if "trend" in categorized and any(
        "ichimoku" in ind or "supertrend" in ind or "psar" in ind
        for ind in categorized["trend"]
    ):
        critical.extend(
            [
                ind
                for ind in categorized["trend"]
                if "ichimoku" in ind or "supertrend" in ind or "psar" in ind
            ]
        )

    if critical:
        print("=" * 80)
        print("КРИТИЧНЫЕ ПРОБЛЕМЫ (должны быть рассчитаны):")
        print("=" * 80)
        for ind in sorted(critical):
            print(f"  - {ind}")
        print()


if __name__ == "__main__":
    main()
