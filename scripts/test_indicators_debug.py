#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики проблем с расчетом индикаторов.
"""

import os
import sys

import numpy as np
import pandas as pd
import pandas_ta as ta

# Добавляем путь к проекту
sys.path.append(os.path.abspath("."))


def test_pandas_ta_basic():
    """Тестируем базовую функциональность pandas_ta"""
    print("=== ТЕСТ БАЗОВОЙ ФУНКЦИОНАЛЬНОСТИ PANDAS_TA ===")

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

    print("Тестовые данные:")
    print(f"  Shape: {df.shape}")
    print(f"  Close non-null: {df['close'].notna().sum()}/{len(df)}")
    print(f"  Close sample: {df['close'].head(3).tolist()}")
    print(f"  Close dtypes: {df['close'].dtype}")

    # Тестируем EMA
    print("\n--- Тестируем EMA ---")
    ema_result = ta.ema(df["close"], length=8)
    print(f"  EMA result type: {type(ema_result)}")
    if ema_result is not None:
        print(f"  EMA non-null: {ema_result.notna().sum()}/{len(ema_result)}")
        if ema_result.notna().sum() > 0:
            print(f"  EMA sample: {ema_result.dropna().head(3).tolist()}")
        else:
            print("  EMA all NaN!")
    else:
        print("  EMA result is None!")

    # Тестируем SMA
    print("\n--- Тестируем SMA ---")
    sma_result = ta.sma(df["close"], length=20)
    print(f"  SMA result type: {type(sma_result)}")
    if sma_result is not None:
        print(f"  SMA non-null: {sma_result.notna().sum()}/{len(sma_result)}")
        if sma_result.notna().sum() > 0:
            print(f"  SMA sample: {sma_result.dropna().head(3).tolist()}")
        else:
            print("  SMA all NaN!")
    else:
        print("  SMA result is None!")

    # Тестируем RSI
    print("\n--- Тестируем RSI ---")
    rsi_result = ta.rsi(df["close"], length=14)
    print(f"  RSI result type: {type(rsi_result)}")
    if rsi_result is not None:
        print(f"  RSI non-null: {rsi_result.notna().sum()}/{len(rsi_result)}")
        if rsi_result.notna().sum() > 0:
            print(f"  RSI sample: {rsi_result.dropna().head(3).tolist()}")
        else:
            print("  RSI all NaN!")
    else:
        print("  RSI result is None!")

    return df


def test_features_calculation():
    """Тестируем расчет индикаторов через features модуль"""
    print("\n=== ТЕСТ РАСЧЕТА ЧЕРЕЗ FEATURES МОДУЛЬ ===")

    try:
        from src.features.core import compute_features

        # Создаем тестовые данные
        df = test_pandas_ta_basic()

        # Тестируем расчет features
        print("\n--- Тестируем compute_features ---")

        # Берем только несколько индикаторов для теста
        test_specs = ["ema_8", "sma_20", "rsi_14", "atr_14", "macd"]

        result_df = compute_features(
            df_ohlcv=df, specs=test_specs, volatility_normalize=False
        )

        print(f"  Result shape: {result_df.shape}")
        print(f"  Result columns: {list(result_df.columns)}")

        # Проверяем результаты
        for spec in test_specs:
            if spec in result_df.columns:
                non_null = result_df[spec].notna().sum()
                print(f"  {spec}: {non_null}/{len(result_df)} non-null")
                if non_null > 0:
                    sample = result_df[spec].dropna().head(3).tolist()
                    print(f"    Sample: {sample}")
            else:
                print(f"  {spec}: NOT FOUND in result")

        return result_df

    except Exception as e:
        print(f"Ошибка при тестировании features: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_real_data():
    """Тестируем с реальными данными из базы"""
    print("\n=== ТЕСТ С РЕАЛЬНЫМИ ДАННЫМИ ===")

    try:
        import asyncio

        from src.database import create_session
        from src.features.infrastructure.database import fetch_ohlcv_df

        async def test_real():
            session = await create_session()
            try:
                # Получаем реальные данные
                df = await fetch_ohlcv_df(
                    session, symbol="BTC-USDT-SWAP", timeframe="1m", limit=100
                )

                if df is not None:
                    print(f"  Real data shape: {df.shape}")
                    print(f"  Real data columns: {list(df.columns)}")
                    print(f"  Close non-null: {df['close'].notna().sum()}/{len(df)}")

                    # Тестируем EMA на реальных данных
                    ema_result = ta.ema(df["close"], length=8)
                    print(
                        f"  EMA on real data: {ema_result.notna().sum()}/{len(ema_result)} non-null"
                    )

                    return df
                print("  Не удалось получить данные из базы")
                return None

            finally:
                await session.close()

        return asyncio.run(test_real())

    except Exception as e:
        print(f"Ошибка при тестировании реальных данных: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("ДИАГНОСТИКА ПРОБЛЕМ С ИНДИКАТОРАМИ")
    print("=" * 50)

    # Тест 1: Базовая функциональность pandas_ta
    df_synthetic = test_pandas_ta_basic()

    # Тест 2: Расчет через features модуль
    result_df = test_features_calculation()

    # Тест 3: Реальные данные
    real_df = test_real_data()

    print("\n" + "=" * 50)
    print("ДИАГНОСТИКА ЗАВЕРШЕНА")
