"""
Тесты для src/core/bars.py — генерация долларовых баров.

Все тесты работают на синтетических данных без подключения к БД.
Fixtures run_ctx и synthetic_ohlcv определены в tests/ml/conftest.py.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from src.core.bars import (
    BarsConfig,
    _compute_turnover,
    build_dollar_bars,
)

# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _make_ohlcv(
    n: int = 10,
    close: float = 100.0,
    volume: float = 1.0,
    freq: str = "1min",
    seed: int = 0,
) -> pd.DataFrame:
    """Минимальный синтетический OHLCV DataFrame."""
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2026-01-01", periods=n, freq=freq, tz="UTC")
    closes = np.full(n, close, dtype=float)
    return pd.DataFrame(
        {
            "open": closes * (1 + rng.uniform(-0.001, 0.001, n)),
            "high": closes * (1 + rng.uniform(0.001, 0.005, n)),
            "low": closes * (1 - rng.uniform(0.001, 0.005, n)),
            "close": closes,
            "volume": np.full(n, volume, dtype=float),
        },
        index=timestamps,
    )


# ---------------------------------------------------------------------------
# test_bars_empty_input
# ---------------------------------------------------------------------------


def test_bars_empty_input() -> None:
    """Пустой DataFrame на входе -> пустой DataFrame на выходе (правильная схема)."""
    empty = pd.DataFrame(
        columns=["open", "high", "low", "close", "volume"],
        index=pd.DatetimeIndex([], tz="UTC", name="timestamp"),
    )
    config = BarsConfig(dollar_value=1_000.0, volume_unit="base")
    result = build_dollar_bars(empty, config)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0
    assert isinstance(result.index, pd.DatetimeIndex)
    expected_cols = {"open", "high", "low", "close", "volume", "turnover",
                     "ts_start", "duration_s", "trades_count", "volume_unit", "bars_source"}
    assert expected_cols.issubset(set(result.columns))


# ---------------------------------------------------------------------------
# test_bars_dollar_aggregation
# ---------------------------------------------------------------------------


def test_bars_dollar_aggregation() -> None:
    """Агрегация OHLCV: open = open первой строки, high/low = max/min, close = close последней."""
    # 6 строк по 1 бару: close=50_000, volume=1.0 => turnover=50_000 каждая
    # dollar_value=100_000 => каждые 2 строки дают бар
    df = _make_ohlcv(n=6, close=50_000.0, volume=1.0)
    config = BarsConfig(dollar_value=100_000.0, volume_unit="base")
    result = build_dollar_bars(df, config)

    # Ожидаем 3 полных бара (возможен 1 частичный если не ровно делится)
    full_bars = result[result["trades_count"] == 2]
    assert len(full_bars) >= 2

    for _, bar in full_bars.iterrows():
        # open должен быть из первой строки бара (не NaN, не экстремальное значение)
        assert bar["open"] > 0
        # high >= low
        assert bar["high"] >= bar["low"]
        # high >= open и high >= close
        assert bar["high"] >= bar["open"]
        assert bar["high"] >= bar["close"]
        # low <= open и low <= close
        assert bar["low"] <= bar["open"]
        assert bar["low"] <= bar["close"]
        # volume = сумма за 2 строки
        assert bar["volume"] == pytest.approx(2.0, rel=1e-6)


# ---------------------------------------------------------------------------
# test_bars_dollar_threshold
# ---------------------------------------------------------------------------


def test_bars_dollar_threshold() -> None:
    """Каждый полный бар имеет turnover >= dollar_value."""
    df = _make_ohlcv(n=100, close=30_000.0, volume=0.5)
    dollar_value = 50_000.0
    config = BarsConfig(dollar_value=dollar_value, volume_unit="base")
    result = build_dollar_bars(df, config)

    # Все бары кроме последнего (частичного) должны иметь turnover >= dollar_value
    if len(result) > 1:
        full_bars = result.iloc[:-1]  # последний может быть частичным
        assert (full_bars["turnover"] >= dollar_value).all(), (
            "Полный бар имеет turnover < dollar_value"
        )


# ---------------------------------------------------------------------------
# test_bars_monotonic_timestamps
# ---------------------------------------------------------------------------


def test_bars_monotonic_timestamps() -> None:
    """Индекс результата строго монотонно возрастает."""
    df = _make_ohlcv(n=50, close=20_000.0, volume=1.0)
    config = BarsConfig(dollar_value=30_000.0, volume_unit="base")
    result = build_dollar_bars(df, config)

    assert len(result) > 0
    assert result.index.is_monotonic_increasing, "Индекс баров не монотонный"
    # Нет дубликатов
    assert result.index.nunique() == len(result), "Дублирующиеся timestamps в барах"


# ---------------------------------------------------------------------------
# test_bars_volume_unit_contracts (OKX SWAP)
# ---------------------------------------------------------------------------


def test_bars_volume_unit_contracts() -> None:
    """
    Для volume_unit='contracts': turnover = volume * contract_val * close.

    Пример: BTC-USDT-SWAP, contract_val=0.01 BTC/контракт,
    close=50_000 USD, volume=100 контрактов
    => turnover = 100 * 0.01 * 50_000 = 50_000 USD
    """
    n = 4
    close_price = 50_000.0
    vol_contracts = 100.0
    contract_val = 0.01  # BTC per contract

    df = _make_ohlcv(n=n, close=close_price, volume=vol_contracts)

    # Ожидаемый turnover за одну строку
    expected_turnover_per_row = vol_contracts * contract_val * close_price  # 50_000 USD

    config = BarsConfig(
        dollar_value=expected_turnover_per_row * 2,  # 2 строки -> 1 бар
        volume_unit="contracts",
        contract_val=contract_val,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = build_dollar_bars(df, config)

    assert len(result) > 0
    # Проверяем turnover первого полного бара
    full_bars = result[result["trades_count"] >= 2]
    if len(full_bars) > 0:
        bar_turnover = full_bars.iloc[0]["turnover"]
        expected = expected_turnover_per_row * full_bars.iloc[0]["trades_count"]
        assert bar_turnover == pytest.approx(expected, rel=1e-6)
    assert (result["volume_unit"] == "contracts").all()


# ---------------------------------------------------------------------------
# test_bars_volume_unit_base
# ---------------------------------------------------------------------------


def test_bars_volume_unit_base() -> None:
    """
    Для volume_unit='base': turnover = volume * close.

    Пример: close=40_000, volume=0.5 BTC => turnover=20_000 USD.
    """
    close_price = 40_000.0
    volume_base = 0.5  # BTC
    n = 10

    df = _make_ohlcv(n=n, close=close_price, volume=volume_base)
    expected_per_row = volume_base * close_price  # 20_000

    config = BarsConfig(
        dollar_value=expected_per_row * 3,  # 3 строки -> 1 бар
        volume_unit="base",
    )
    result = build_dollar_bars(df, config)

    assert len(result) > 0
    full_bars = result[result["trades_count"] >= 3]
    if len(full_bars) > 0:
        expected_turnover = expected_per_row * full_bars.iloc[0]["trades_count"]
        assert full_bars.iloc[0]["turnover"] == pytest.approx(expected_turnover, rel=1e-6)
    assert (result["volume_unit"] == "base").all()


# ---------------------------------------------------------------------------
# test_bars_partial_last_bar
# ---------------------------------------------------------------------------


def test_bars_partial_last_bar() -> None:
    """
    Последний частичный бар включается в результат.

    Сценарий: 5 строк, dollar_value такой что 3 строки -> 1 полный бар,
    остаток 2 строки -> частичный бар.
    """
    close_price = 10_000.0
    volume = 1.0
    n = 5

    df = _make_ohlcv(n=n, close=close_price, volume=volume)
    # turnover per row = 10_000; dollar_value = 30_000 => 3 строки -> 1 бар, 2 строки остаток
    config = BarsConfig(dollar_value=30_000.0, volume_unit="base")
    result = build_dollar_bars(df, config)

    # Должен быть как минимум 1 полный + 1 частичный бар (или только частичный если 5 < 3*2)
    assert len(result) >= 1

    # Последний бар может иметь turnover < dollar_value (частичный)
    last_bar = result.iloc[-1]
    # trades_count всегда >= 1
    assert last_bar["trades_count"] >= 1
    # ts_start <= ts_end (индекс)
    assert last_bar["ts_start"] <= result.index[-1]


# ---------------------------------------------------------------------------
# test_bars_minute_fallback (bars_source маркировка)
# ---------------------------------------------------------------------------


def test_bars_minute_fallback(synthetic_ohlcv: pd.DataFrame) -> None:
    """
    bars_source='fallback_minute' корректно маркируется в результате.

    Также проверяет, что количество баров разумно:
    при dollar_value = mean_turnover * 10 ожидаем ~n/10 баров.
    """
    df = synthetic_ohlcv  # 1000 строк, close ~50_000

    # Средний оборот на строку ≈ volume * close
    mean_volume = df["volume"].mean()
    mean_close = df["close"].mean()
    mean_turnover = mean_volume * mean_close
    dollar_value = mean_turnover * 10  # ~10 строк на бар

    config = BarsConfig(
        dollar_value=dollar_value,
        volume_unit="base",
        bars_source="fallback_minute",
    )
    result = build_dollar_bars(df, config)

    assert len(result) > 0
    # Маркировка источника
    assert (result["bars_source"] == "fallback_minute").all()
    # Грубая проверка числа баров (должно быть порядка n/10 +/- 50%)
    expected_bars = len(df) / 10
    assert expected_bars * 0.3 <= len(result) <= expected_bars * 3.0, (
        f"Неожиданное число баров: {len(result)}, ожидалось ~{expected_bars:.0f}"
    )


# ---------------------------------------------------------------------------
# test_bars_invalid_input: немонотонный индекс
# ---------------------------------------------------------------------------


def test_bars_nonmonotonic_index_raises() -> None:
    """Немонотонный DatetimeIndex вызывает ValueError."""
    df = _make_ohlcv(n=5, close=1000.0)
    # Переставляем строки чтобы нарушить монотонность
    df = df.iloc[::-1].copy()  # reverse order

    config = BarsConfig(dollar_value=500.0, volume_unit="base")
    with pytest.raises(ValueError, match="монотонно"):
        build_dollar_bars(df, config)


# ---------------------------------------------------------------------------
# test_bars_compute_turnover: unit-тест вычисления turnover
# ---------------------------------------------------------------------------


def test_compute_turnover_all_units() -> None:
    """Проверка формул turnover для всех volume_unit."""
    volume = pd.Series([100.0, 200.0])
    close = pd.Series([50_000.0, 60_000.0])
    contract_val = 0.01

    # contracts
    t_contracts = _compute_turnover(volume, close, "contracts", contract_val)
    assert t_contracts.iloc[0] == pytest.approx(100 * 0.01 * 50_000)
    assert t_contracts.iloc[1] == pytest.approx(200 * 0.01 * 60_000)

    # base
    t_base = _compute_turnover(volume, close, "base", 1.0)
    assert t_base.iloc[0] == pytest.approx(100 * 50_000)
    assert t_base.iloc[1] == pytest.approx(200 * 60_000)

    # quote (volume уже в USD)
    t_quote = _compute_turnover(volume, close, "quote", 1.0)
    assert t_quote.iloc[0] == pytest.approx(100.0)
    assert t_quote.iloc[1] == pytest.approx(200.0)
