#!/usr/bin/env python3
"""
Тест для отладки compute_features
"""

import os
import sys

import numpy as np
import pandas as pd

# Добавляем путь к проекту
sys.path.append(os.path.abspath("."))


def test_compute_features():
    """Тестируем compute_features с отладкой"""
    print("=== ТЕСТ COMPUTE_FEATURES ===")

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

    # Импортируем compute_features
    from src.features.core import compute_features

    # Тестируем с небольшим набором индикаторов
    test_specs = ["ema_8", "sma_20", "rsi_14"]

    print(f"\nТестируем compute_features с specs: {test_specs}")

    try:
        result_df = compute_features(
            df_ohlcv=df, specs=test_specs, volatility_normalize=False
        )

        print("\nРезультат compute_features:")
        print(f"  Shape: {result_df.shape}")
        print(f"  Columns: {list(result_df.columns)}")

        # Проверяем индикаторы
        for spec in test_specs:
            if spec in result_df.columns:
                non_null = result_df[spec].notna().sum()
                print(f"  {spec}: {non_null}/{len(result_df)} non-null")
                if non_null > 0:
                    sample = result_df[spec].dropna().head(3).tolist()
                    print(f"    Sample: {sample}")
            else:
                print(f"  {spec}: NOT FOUND")

        return result_df

    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_compute_features()
