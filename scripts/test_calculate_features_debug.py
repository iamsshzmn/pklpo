#!/usr/bin/env python3
"""
Тест для отладки _calculate_features
"""

import os
import sys

import numpy as np
import pandas as pd

# Добавляем путь к проекту
sys.path.append(os.path.abspath("."))


def test_calculate_features():
    """Тестируем _calculate_features с отладкой"""
    print("=== ТЕСТ _CALCULATE_FEATURES ===")

    # Создаем тестовые данные
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=100, freq="1min")
    close_prices = 100 + np.cumsum(np.random.randn(100) * 0.1)

    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": close_prices + np.random.randn(100) * 0.01,
            "high": close_prices + np.abs(np.random.randn(100) * 0.02),
            "low": close_prices - np.abs(np.random.randn(100) * 0.02),
            "close": close_prices,
            "volume": np.random.randint(100, 1000, 100),
        }
    )

    print("Входные данные:")
    print(f"  Shape: {df.shape}")

    # Импортируем функции
    from src.features.core import _calculate_features
    from src.features.specs import FEATURE_SPECS

    # Получаем specs
    test_specs = ["ema_8", "sma_20", "rsi_14"]
    feature_specs = [
        FEATURE_SPECS[spec] for spec in test_specs if spec in FEATURE_SPECS
    ]

    print("\nFeature specs:")
    print(f"  Specs: {test_specs}")
    print(f"  Feature specs count: {len(feature_specs)}")

    # Тестируем _calculate_features
    print("\nТестируем _calculate_features...")

    try:
        result = _calculate_features(df, feature_specs)

        print("\nРезультат _calculate_features:")
        print(f"  Количество ключей: {len(result)}")
        print(f"  Ключи: {list(result.keys())}")

        # Проверяем каждый индикатор
        for key, value in result.items():
            if isinstance(value, pd.Series):
                non_null = value.notna().sum()
                print(f"  {key}: {non_null}/{len(value)} non-null")
                if non_null > 0:
                    sample = value.dropna().head(3).tolist()
                    print(f"    Sample: {sample}")
            else:
                print(f"  {key}: {type(value)} - {value}")

        # Проверяем конкретно наши индикаторы
        print("\nПроверяем наши индикаторы:")
        for spec in test_specs:
            if spec in result:
                value = result[spec]
                if isinstance(value, pd.Series):
                    non_null = value.notna().sum()
                    print(f"  {spec}: {non_null}/{len(value)} non-null")
                    if non_null > 0:
                        sample = value.dropna().head(3).tolist()
                        print(f"    Sample: {sample}")
                else:
                    print(f"  {spec}: {type(value)} - {value}")
            else:
                print(f"  {spec}: NOT FOUND")

        return result

    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_calculate_features()
