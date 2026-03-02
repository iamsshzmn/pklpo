#!/usr/bin/env python3
"""
Детальная отладка core.py
"""

import os
import sys

import numpy as np
import pandas as pd

# Добавляем путь к проекту
sys.path.append(os.path.abspath("."))


def test_core_detailed():
    """Детальная отладка core.py"""
    print("=== ДЕТАЛЬНАЯ ОТЛАДКА CORE.PY ===")

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

    # Импортируем функции напрямую
    from src.features.core import _calculate_features
    from src.features.specs import FEATURE_SPECS

    # Получаем specs
    test_specs = ["ema_8", "sma_20", "rsi_14"]
    feature_specs = [
        FEATURE_SPECS[spec] for spec in test_specs if spec in FEATURE_SPECS
    ]
    available_names = {spec.name for spec in feature_specs}

    print("\nFeature specs:")
    print(f"  Specs: {test_specs}")
    print(f"  Available names: {available_names}")
    print(f"  Feature specs count: {len(feature_specs)}")

    # Тестируем _calculate_features напрямую
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

        # Тестируем сохранение в result_df
        print("\nТестируем сохранение в result_df...")
        result_df = df.copy()

        from src.features.name_mapping import normalize_indicator_name

        for name, values in result.items():
            target_name = normalize_indicator_name(name)
            should_process = len(available_names) == 0 or target_name in available_names

            print(f"\nОбрабатываем {name} -> {target_name}")
            print(f"  should_process: {should_process}")
            print(f"  available_names: {available_names}")
            print(f"  target_name in available_names: {target_name in available_names}")

            if should_process:
                if isinstance(values, pd.Series):
                    if len(values) == len(result_df):
                        new_series = pd.Series(values.values, index=result_df.index)
                    else:
                        new_series = values.reindex(result_df.index)

                    print(
                        f"  new_series non-null: {new_series.notna().sum()}/{len(new_series)}"
                    )
                    result_df[target_name] = new_series
                    print(f"  Добавлено в result_df: {target_name}")
                    print(
                        f"  Финальное значение non-null: {result_df[target_name].notna().sum()}/{len(result_df[target_name])}"
                    )

        print("\nФинальный result_df:")
        print(f"  Shape: {result_df.shape}")
        print(f"  Columns: {list(result_df.columns)}")

        # Проверяем индикаторы
        for spec in test_specs:
            if spec in result_df.columns:
                non_null = result_df[spec].notna().sum()
                print(f"  {spec}: {non_null}/{len(result_df)} non-null")
            else:
                print(f"  {spec}: NOT FOUND")

        return result_df

    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_core_detailed()
