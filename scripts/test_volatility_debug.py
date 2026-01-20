#!/usr/bin/env python3
"""
Тест для отладки volatility_normalize_features
"""

import os
import sys

import numpy as np
import pandas as pd

# Добавляем путь к проекту
sys.path.append(os.path.abspath("."))


def test_volatility_normalization():
    """Тестируем volatility_normalize_features"""
    print("=== ТЕСТ VOLATILITY NORMALIZATION ===")

    # Создаем тестовые данные с индикаторами
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

    # Добавляем индикаторы
    df["ema_8"] = df["close"].ewm(span=8).mean()
    df["sma_20"] = df["close"].rolling(window=20).mean()
    df["rsi_14"] = 50 + np.random.randn(100) * 10  # Имитация RSI

    print("Исходные данные:")
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {list(df.columns)}")
    print(f"  ema_8 non-null: {df['ema_8'].notna().sum()}/{len(df)}")
    print(f"  sma_20 non-null: {df['sma_20'].notna().sum()}/{len(df)}")
    print(f"  rsi_14 non-null: {df['rsi_14'].notna().sum()}/{len(df)}")

    # Импортируем функцию
    from src.features.utils import volatility_normalize_features

    print("\nПрименяем volatility normalization...")

    try:
        result_df = volatility_normalize_features(df, window=20, method="rolling_std")

        print("\nРезультат после normalization:")
        print(f"  Shape: {result_df.shape}")
        print(f"  Columns: {list(result_df.columns)}")
        print(f"  ema_8 non-null: {result_df['ema_8'].notna().sum()}/{len(result_df)}")
        print(
            f"  sma_20 non-null: {result_df['sma_20'].notna().sum()}/{len(result_df)}"
        )
        print(
            f"  rsi_14 non-null: {result_df['rsi_14'].notna().sum()}/{len(result_df)}"
        )

        # Проверяем значения
        if result_df["ema_8"].notna().sum() > 0:
            print(f"  ema_8 sample: {result_df['ema_8'].dropna().head(3).tolist()}")
        if result_df["sma_20"].notna().sum() > 0:
            print(f"  sma_20 sample: {result_df['sma_20'].dropna().head(3).tolist()}")
        if result_df["rsi_14"].notna().sum() > 0:
            print(f"  rsi_14 sample: {result_df['rsi_14'].dropna().head(3).tolist()}")

        return result_df

    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_volatility_normalization()
