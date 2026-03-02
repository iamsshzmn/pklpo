#!/usr/bin/env python3
"""
Тест для отладки result после update
"""

import os
import sys

import numpy as np
import pandas as pd

# Добавляем путь к проекту
sys.path.append(os.path.abspath("."))


def test_result_after_update():
    """Отладка result после всех update"""
    print("=== ОТЛАДКА RESULT ПОСЛЕ UPDATE ===")

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
    from src.features.indicator_groups.overlap import calc_overlap_indicators

    available_names = {"ema_8", "sma_20", "rsi_14"}

    # Симулируем _calculate_features
    result_df = df.copy()

    # Добавляем ts колонку
    result_df["ts"] = result_df["timestamp"].astype("int64") // 10**9

    print("\nИсходный result_df:")
    print(f"  Shape: {result_df.shape}")
    print(f"  Columns: {list(result_df.columns)}")

    # Тестируем каждую функцию отдельно
    result = {}

    print("\n1. Тестируем calc_overlap_indicators...")
    overlap_result = calc_overlap_indicators(result_df, available_names)
    print(f"  Overlap keys: {list(overlap_result.keys())}")
    for key, value in overlap_result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"    {key}: {non_null}/{len(value)} non-null")

    result.update(overlap_result)
    print(f"  Result после overlap: {len(result)} ключей")

    print("\n2. Тестируем calc_ma_indicators...")
    ma_result = calc_ma_indicators(result_df, available_names)
    print(f"  MA keys: {list(ma_result.keys())}")
    for key, value in ma_result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"    {key}: {non_null}/{len(value)} non-null")

    result.update(ma_result)
    print(f"  Result после MA: {len(result)} ключей")
    for key, value in result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"    {key}: {non_null}/{len(value)} non-null")

    print("\n3. Тестируем calc_oscillator_indicators...")
    osc_result = calc_oscillator_indicators(result_df, available_names)
    print(f"  Oscillator keys: {list(osc_result.keys())}")
    for key, value in osc_result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"    {key}: {non_null}/{len(value)} non-null")

    result.update(osc_result)
    print(f"  Result после oscillator: {len(result)} ключей")
    for key, value in result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            print(f"    {key}: {non_null}/{len(value)} non-null")

    # Проверяем конфликты ключей
    all_keys = (
        set(overlap_result.keys()) | set(ma_result.keys()) | set(osc_result.keys())
    )
    print(f"\nВсе ключи: {all_keys}")

    # Проверяем, есть ли конфликты
    overlap_keys = set(overlap_result.keys())
    ma_keys = set(ma_result.keys())
    osc_keys = set(osc_result.keys())

    conflicts = (
        (overlap_keys & ma_keys) | (overlap_keys & osc_keys) | (ma_keys & osc_keys)
    )
    print(f"Конфликты ключей: {conflicts}")


if __name__ == "__main__":
    test_result_after_update()
