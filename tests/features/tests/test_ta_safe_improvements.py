"""
Тесты для улучшенного ta_safe фасада.
"""

import pandas as pd
import pytest

from src.features.ta_safe import FeatureCalcError, safe_ta, safe_ta_with_fallback


@pytest.fixture
def sample_ohlcv():
    """Тестовые OHLCV данные."""
    return pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104],
            "high": [105, 106, 107, 108, 109],
            "low": [95, 96, 97, 98, 99],
            "close": [102, 103, 104, 105, 106],
            "volume": [1000, 1100, 1200, 1300, 1400],
        }
    )


def test_safe_ta_always_df(sample_ohlcv):
    """Тест: всегда возвращается DataFrame."""
    for name in ("rsi", "atr", "macd", "bbands"):
        result = safe_ta_with_fallback(sample_ohlcv, name, length=14)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(sample_ohlcv)


def test_no_object_dtypes(sample_ohlcv):
    """Тест: нет object типов в результатах."""
    result = safe_ta_with_fallback(sample_ohlcv, "bbands", length=20, std=2)
    assert all(result[c].dtype == "float64" for c in result.columns)


def test_input_validation():
    """Тест: проверка входных данных."""
    # Неполные данные
    incomplete_df = pd.DataFrame({"close": [1, 2, 3]})

    with pytest.raises(FeatureCalcError, match="нет колонок"):
        safe_ta(incomplete_df, "rsi", length=14)

    # Пустой DataFrame
    empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    with pytest.raises(FeatureCalcError, match="пустой DataFrame"):
        safe_ta(empty_df, "rsi", length=14)


def test_column_naming_consistency(sample_ohlcv):
    """Тест: согласованность имен колонок."""
    # RSI должен иметь имя rsi_14
    rsi_result = safe_ta_with_fallback(sample_ohlcv, "rsi", length=14)
    assert "rsi_14" in rsi_result.columns

    # MACD должен иметь стандартные имена
    macd_result = safe_ta_with_fallback(sample_ohlcv, "macd")
    expected_cols = {"macd", "macd_signal", "macd_histogram"}
    assert set(macd_result.columns) == expected_cols

    # Bollinger Bands должны иметь стандартные имена
    bb_result = safe_ta_with_fallback(sample_ohlcv, "bbands", length=20, std=2)
    expected_cols = {"bb_upper", "bb_middle", "bb_lower"}
    assert set(bb_result.columns) == expected_cols


def test_index_preservation(sample_ohlcv):
    """Тест: сохранение индекса."""
    # Добавляем кастомный индекс
    sample_ohlcv.index = pd.date_range("2023-01-01", periods=5, freq="H")

    result = safe_ta_with_fallback(sample_ohlcv, "rsi", length=14)
    assert result.index.equals(sample_ohlcv.index)


def test_forbidden_functions(sample_ohlcv):
    """Тест: запрещенные функции."""
    with pytest.raises(FeatureCalcError, match="запрещён"):
        safe_ta(sample_ohlcv, "unknown_function")


def test_fallback_quality(sample_ohlcv):
    """Тест: качество fallback расчетов."""
    # RSI fallback должен давать разумные значения
    rsi_result = safe_ta_with_fallback(sample_ohlcv, "rsi", length=14)
    rsi_values = rsi_result["rsi_14"].dropna()

    # RSI должен быть в диапазоне 0-100
    assert rsi_values.min() >= 0
    assert rsi_values.max() <= 100

    # MACD fallback должен давать разумные значения
    macd_result = safe_ta_with_fallback(sample_ohlcv, "macd")
    macd_values = macd_result["macd"].dropna()

    # MACD не должен быть NaN для всех значений
    assert not macd_values.isna().all()


if __name__ == "__main__":
    # Простой тест без pytest
    df = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104],
            "high": [105, 106, 107, 108, 109],
            "low": [95, 96, 97, 98, 99],
            "close": [102, 103, 104, 105, 106],
            "volume": [1000, 1100, 1200, 1300, 1400],
        }
    )

    print("Тестируем улучшенный ta_safe...")

    # Тест 1: всегда DataFrame
    result = safe_ta_with_fallback(df, "rsi", length=14)
    print(f"✅ RSI result type: {type(result)}")
    print(f"✅ RSI columns: {list(result.columns)}")
    print(f"✅ RSI dtypes: {result.dtypes.to_dict()}")

    # Тест 2: типы данных
    assert all(result[c].dtype == "float64" for c in result.columns), (
        "❌ Object типы найдены"
    )
    print("✅ Все колонки имеют float64 тип")

    # Тест 3: индекс
    assert result.index.equals(df.index), "❌ Индекс не совпадает"
    print("✅ Индекс сохранен")

    print("🎯 Все тесты пройдены!")
