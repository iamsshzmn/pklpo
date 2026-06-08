#!/usr/bin/env python3

"""
Тест для отладки проблемы с циклом мерджа в _calculate_features.
"""

import logging
import os
import sys

import pandas as pd

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.features.core import compute_features

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
os.environ["FEATURES_VERBOSE"] = "true"


def test_merge_issue():
    """Тест для отладки проблемы с циклом мерджа."""

    print("ТЕСТИРОВАНИЕ ПРОБЛЕМЫ С ЦИКЛОМ МЕРДЖА")
    print("=" * 60)

    # Создаём тестовые данные
    data = {
        "open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        "high": [105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
        "low": [95, 96, 97, 98, 99, 100, 101, 102, 103, 104],
        "close": [102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
        "volume": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900],
        "timestamp": pd.date_range("2023-01-01", periods=10, freq="H"),
    }
    df = pd.DataFrame(data)

    print("Тестовые данные:")
    print(f"Размер: {len(df)} строк")
    print(f"Колонки: {list(df.columns)}")
    print(
        f"OHLCV non-null: {df[['open', 'high', 'low', 'close', 'volume']].notna().sum().to_dict()}"
    )
    print()

    # Запускаем расчёт
    print("Запуск compute_features...")
    try:
        result = compute_features(df, volatility_normalize=False)
        print("compute_features завершился успешно")
    except Exception as e:
        print(f"Ошибка в compute_features: {e}")
        return None

    print()
    print("РЕЗУЛЬТАТЫ:")
    print(f"Размер результата: {len(result)} строк, {len(result.columns)} колонок")

    # Проверяем ключевые индикаторы
    key_indicators = ["hlc3", "ema_8", "sma_20", "rsi_14", "atr_14", "macd", "obv"]

    print("\nПроверка ключевых индикаторов:")
    for indicator in key_indicators:
        if indicator in result.columns:
            fill_rate = result[indicator].notna().sum() / len(result[indicator]) * 100
            print(f"  {indicator}: {fill_rate:.1f}% заполнено")
            if fill_rate > 0:
                print(f"    Первые значения: {result[indicator].head(3).tolist()}")
        else:
            print(f"  {indicator}: НЕТ в результате")

    # Проверяем все колонки
    print(f"\nВсе колонки ({len(result.columns)}):")
    feature_cols = [
        col
        for col in result.columns
        if col not in ["open", "high", "low", "close", "volume", "ts", "timestamp"]
    ]
    print(f"  Индикаторы: {len(feature_cols)}")

    # Статистика заполненности
    print("\nСтатистика заполненности:")
    for col in feature_cols[:10]:  # Первые 10 индикаторов
        fill_rate = result[col].notna().sum() / len(result[col]) * 100
        print(f"  {col}: {fill_rate:.1f}%")

    if len(feature_cols) > 10:
        print(f"  ... и ещё {len(feature_cols) - 10} индикаторов")

    # Проверяем, есть ли хотя бы один заполненный индикатор
    filled_indicators = []
    for col in feature_cols:
        if result[col].notna().sum() > 0:
            filled_indicators.append(col)

    print(f"\nЗаполненные индикаторы: {len(filled_indicators)}")
    if filled_indicators:
        print(f"  Примеры: {filled_indicators[:5]}")
    else:
        print("  НЕТ ЗАПОЛНЕННЫХ ИНДИКАТОРОВ!")

    return result


if __name__ == "__main__":
    test_merge_issue()
