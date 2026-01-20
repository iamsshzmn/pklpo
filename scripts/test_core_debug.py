#!/usr/bin/env python3
"""
Тест для отладки core.py
"""

import os
import sys

import numpy as np
import pandas as pd

# Добавляем путь к проекту
sys.path.append(os.path.abspath("."))


def test_core_processing():
    """Тестируем обработку в core.py"""
    print("=== ТЕСТ CORE.PY ОБРАБОТКИ ===")

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
    from src.features.name_mapping import normalize_indicator_name

    # Тестируем calc_ma_indicators
    available_names = {"ema_8", "sma_20", "ema_12", "ema_21"}
    result = calc_ma_indicators(df, available_names)

    print("\nРезультат calc_ma_indicators:")
    print(f"  Количество ключей: {len(result)}")
    print(f"  Ключи: {list(result.keys())}")

    # Тестируем name mapping
    print("\nТестируем name mapping:")
    for name in result.keys():
        target_name = normalize_indicator_name(name)
        print(f"  {name} -> {target_name}")

    # Тестируем создание result_df
    result_df = df.copy()
    print("\nИсходный result_df:")
    print(f"  Shape: {result_df.shape}")
    print(f"  Columns: {list(result_df.columns)}")

    # Симулируем обработку как в core.py
    print("\nОбработка индикаторов:")
    for name, values in result.items():
        target_name = normalize_indicator_name(name)
        print(f"\nОбрабатываем {name} -> {target_name}")
        print(f"  Values type: {type(values)}")

        if isinstance(values, pd.Series):
            print(f"  Values non-null: {values.notna().sum()}/{len(values)}")
            print(f"  Values index: {values.index}")
            print(f"  Result_df index: {result_df.index}")

            # Проверяем выравнивание
            if len(values) == len(result_df):
                new_series = pd.Series(values.values, index=result_df.index)
                print(
                    f"  Aligned series non-null: {new_series.notna().sum()}/{len(new_series)}"
                )
            else:
                new_series = values.reindex(result_df.index)
                print(
                    f"  Reindexed series non-null: {new_series.notna().sum()}/{len(new_series)}"
                )

            # Добавляем в result_df
            result_df[target_name] = new_series
            print(f"  Добавлено в result_df: {target_name}")
            print(
                f"  Финальное значение non-null: {result_df[target_name].notna().sum()}/{len(result_df[target_name])}"
            )

    print("\nФинальный result_df:")
    print(f"  Shape: {result_df.shape}")
    print(f"  Columns: {list(result_df.columns)}")

    # Проверяем индикаторы
    for col in ["ema_8", "sma_20", "ema_12", "ema_21"]:
        if col in result_df.columns:
            non_null = result_df[col].notna().sum()
            print(f"  {col}: {non_null}/{len(result_df)} non-null")
        else:
            print(f"  {col}: NOT FOUND")


if __name__ == "__main__":
    test_core_processing()
