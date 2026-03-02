#!/usr/bin/env python3
"""
Тест для отладки result.update()
"""

import os
import sys

import numpy as np
import pandas as pd

# Добавляем путь к проекту
sys.path.append(os.path.abspath("."))


def test_result_update():
    """Тестируем result.update()"""
    print("=== ТЕСТ RESULT.UPDATE() ===")

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
    from src.features.indicator_groups.ma import calc_ma_indicators
    from src.features.indicator_groups.oscillators import calc_oscillator_indicators

    available_names = {"ema_8", "sma_20", "rsi_14"}

    # Тестируем calc_ma_indicators
    print("\nТестируем calc_ma_indicators...")
    ma_result = calc_ma_indicators(df, available_names)
    print(f"  MA result keys: {list(ma_result.keys())}")
    for key, value in ma_result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"  {key}: {non_null}/{len(value)} non-null")

    # Тестируем calc_oscillator_indicators
    print("\nТестируем calc_oscillator_indicators...")
    osc_result = calc_oscillator_indicators(df, available_names)
    print(f"  Oscillator result keys: {list(osc_result.keys())}")
    for key, value in osc_result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"  {key}: {non_null}/{len(value)} non-null")

    # Тестируем result.update()
    print("\nТестируем result.update()...")
    result = {}

    print(f"  До update: {len(result)} ключей")
    result.update(ma_result)
    print(f"  После ma_result: {len(result)} ключей")
    for key, value in result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"    {key}: {non_null}/{len(value)} non-null")

    result.update(osc_result)
    print(f"  После osc_result: {len(result)} ключей")
    for key, value in result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"    {key}: {non_null}/{len(value)} non-null")

    # Проверяем, есть ли конфликты ключей
    ma_keys = set(ma_result.keys())
    osc_keys = set(osc_result.keys())
    conflicts = ma_keys.intersection(osc_keys)
    print(f"\nКонфликты ключей: {conflicts}")

    if conflicts:
        print("  Проблема: одинаковые ключи в разных функциях!")
        for key in conflicts:
            print(
                f"    {key}: ma={ma_result[key].notna().sum() if isinstance(ma_result[key], pd.Series) else 'not Series'}, osc={osc_result[key].notna().sum() if isinstance(osc_result[key], pd.Series) else 'not Series'}"
            )


if __name__ == "__main__":
    test_result_update()
