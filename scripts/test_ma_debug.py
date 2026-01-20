#!/usr/bin/env python3
"""
Тест для отладки calc_ma_indicators
"""

import os
import sys

import numpy as np
import pandas as pd

# Добавляем путь к проекту
sys.path.append(os.path.abspath("."))


def test_ma_indicators():
    """Тестируем calc_ma_indicators напрямую"""
    print("=== ТЕСТ CALC_MA_INDICATORS ===")

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
    print(f"  Close non-null: {df['close'].notna().sum()}/{len(df)}")

    # Импортируем функцию
    from src.features.indicator_groups.ma import calc_ma_indicators

    # Тестируем
    available_names = {"ema_8", "sma_20", "ema_12", "ema_21"}
    result = calc_ma_indicators(df, available_names)

    print("\nРезультат calc_ma_indicators:")
    print(f"  Количество ключей: {len(result)}")
    print(f"  Ключи: {list(result.keys())}")

    for key, value in result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"  {key}: {non_null}/{len(value)} non-null")
            if non_null > 0:
                sample = value.dropna().head(3).tolist()
                print(f"    Sample: {sample}")
        else:
            print(f"  {key}: {type(value)} - {value}")


if __name__ == "__main__":
    test_ma_indicators()
