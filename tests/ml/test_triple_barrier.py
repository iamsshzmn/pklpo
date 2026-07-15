"""
Тесты для src/ml/labeling/triple_barrier.py.

Все тесты работают на синтетических данных без подключения к БД.
Fixtures определены в tests/ml/conftest.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ml.labeling.triple_barrier import (
    _NUMBA_AVAILABLE,
    _scan_jit,
    _triple_barrier_scan,
    triple_barrier_labels,
)
from src.ml.models import BarrierConfig

# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _make_ohlcv(
    n: int = 50,
    close: float = 100.0,
    high_mult: float = 1.03,
    low_mult: float = 0.97,
    freq: str = "1min",
) -> pd.DataFrame:
    """Синтетический OHLCV с постоянными множителями high/low."""
    timestamps = pd.date_range("2026-01-01", periods=n, freq=freq, tz="UTC")
    closes = np.full(n, close, dtype=float)
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes * high_mult,
            "low": closes * low_mult,
            "close": closes,
            "volume": np.ones(n),
        },
        index=timestamps,
    )


# ---------------------------------------------------------------------------
# test_triple_barrier_numba_vs_loop
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _NUMBA_AVAILABLE, reason="numba not installed")
def test_triple_barrier_numba_vs_loop(synthetic_ohlcv: pd.DataFrame) -> None:
    """Numba JIT и Python loop дают идентичные результаты на синтетических данных."""
    close = synthetic_ohlcv["close"].to_numpy(dtype=np.float64)
    high = synthetic_ohlcv["high"].to_numpy(dtype=np.float64)
    low = synthetic_ohlcv["low"].to_numpy(dtype=np.float64)

    pt, sl, max_h = 0.02, 0.01, 48

    # Warm up numba JIT (первый вызов компилирует)
    labels_jit, t1_jit, bc_jit = _scan_jit(close, high, low, pt, sl, max_h)
    labels_loop, t1_loop, bc_loop = _triple_barrier_scan(
        close, high, low, pt, sl, max_h
    )

    np.testing.assert_array_equal(
        labels_jit, labels_loop, err_msg="labels не совпадают"
    )
    np.testing.assert_array_equal(t1_jit, t1_loop, err_msg="t1_idx не совпадают")
    np.testing.assert_array_equal(bc_jit, bc_loop, err_msg="barrier_code не совпадают")


# ---------------------------------------------------------------------------
# test_triple_barrier_all_pt
# ---------------------------------------------------------------------------


def test_triple_barrier_all_pt() -> None:
    """
    Если high всегда превышает PT порог в следующем баре,
    все метки (кроме последней) = +1, barrier_type = 'pt'.
    """
    pt = 0.02
    # high = close * 1.05 > close * 1.02 = pt_level → PT всегда срабатывает в баре i+1
    df = _make_ohlcv(n=50, close=100.0, high_mult=1.05, low_mult=0.99)
    config = BarrierConfig(profit_take=pt, stop_loss=0.01, max_horizon=10)

    result = triple_barrier_labels(df, config)

    assert len(result) == 50
    # Все бары кроме последнего должны иметь метку +1
    interior = result.iloc[:-1]
    assert (interior["label"] == 1).all(), (
        f"Ожидались все +1, получено:\n{interior['label'].value_counts()}"
    )
    assert (interior["barrier_type"] == "pt").all()
    # t1 = следующий бар
    for i in range(len(interior)):
        assert result["t1"].iloc[i] == df.index[i + 1], (
            f"Бар {i}: ожидался t1={df.index[i + 1]}, получен {result['t1'].iloc[i]}"
        )

    # Последний бар — вертикальный (нет данных вперёд)
    assert result["label"].iloc[-1] == 0
    assert result["barrier_type"].iloc[-1] == "vert"


# ---------------------------------------------------------------------------
# test_triple_barrier_all_sl
# ---------------------------------------------------------------------------


def test_triple_barrier_all_sl() -> None:
    """
    Если low всегда ниже SL порога в следующем баре,
    все метки (кроме последней) = -1, barrier_type = 'sl'.
    """
    sl = 0.01
    # low = close * 0.95 < close * (1 - 0.01) = sl_level → SL срабатывает в баре i+1
    df = _make_ohlcv(n=50, close=100.0, high_mult=1.001, low_mult=0.95)
    config = BarrierConfig(profit_take=0.02, stop_loss=sl, max_horizon=10)

    result = triple_barrier_labels(df, config)

    assert len(result) == 50
    interior = result.iloc[:-1]
    assert (interior["label"] == -1).all(), (
        f"Ожидались все -1, получено:\n{interior['label'].value_counts()}"
    )
    assert (interior["barrier_type"] == "sl").all()
    # t1 = следующий бар
    for i in range(len(interior)):
        assert result["t1"].iloc[i] == df.index[i + 1]

    # Последний бар — вертикальный
    assert result["label"].iloc[-1] == 0
    assert result["barrier_type"].iloc[-1] == "vert"


# ---------------------------------------------------------------------------
# test_triple_barrier_vertical
# ---------------------------------------------------------------------------


def test_triple_barrier_vertical() -> None:
    """
    Если движение цены мало (< PT и < SL), все метки = 0, barrier_type = 'vert'.
    """
    pt, sl = 0.02, 0.01
    # high только +0.1% выше close → не достигает PT (2%)
    # low только -0.1% ниже close → не достигает SL (1%)
    df = _make_ohlcv(n=30, close=100.0, high_mult=1.001, low_mult=0.999)
    config = BarrierConfig(profit_take=pt, stop_loss=sl, max_horizon=5)

    result = triple_barrier_labels(df, config)

    assert len(result) == 30
    assert (result["label"] == 0).all(), (
        f"Ожидались все 0, получено:\n{result['label'].value_counts()}"
    )
    assert (result["barrier_type"] == "vert").all()


# ---------------------------------------------------------------------------
# test_triple_barrier_edge_bars
# ---------------------------------------------------------------------------


def test_triple_barrier_edge_bars() -> None:
    """
    Корректность на краях данных:
    - Последний бар: label=0 (vert), t1=последний timestamp.
    - Все бары имеют корректные метки (-1, 0, +1).
    - t1 timestamps >= entry timestamps.
    """
    n = 20
    max_h = 5
    df = _make_ohlcv(n=n, close=100.0, high_mult=1.03, low_mult=0.97)
    config = BarrierConfig(profit_take=0.02, stop_loss=0.01, max_horizon=max_h)

    result = triple_barrier_labels(df, config)

    assert len(result) == n

    # Все метки допустимы
    assert result["label"].isin([-1, 0, 1]).all()

    # Все barrier_type допустимы
    assert result["barrier_type"].isin(["pt", "sl", "vert"]).all()

    # t1 >= entry для каждого бара
    for i, (entry, t1) in enumerate(zip(result.index, result["t1"], strict=True)):
        assert t1 >= entry, f"Бар {i}: t1={t1} < entry={entry}"

    # t1 <= последний timestamp в данных
    last_ts = df.index[-1]
    assert (result["t1"] <= last_ts).all()

    # Последний бар — вертикальный (нет форвардных данных)
    assert result["label"].iloc[-1] == 0
    assert result["barrier_type"].iloc[-1] == "vert"
    assert result["t1"].iloc[-1] == df.index[-1]

    # vert_time не выходит за пределы данных
    assert (result["vert_time"] <= last_ts).all()


# ---------------------------------------------------------------------------
# test_triple_barrier_gaps
# ---------------------------------------------------------------------------


def test_triple_barrier_gaps() -> None:
    """
    Нерегулярный DatetimeIndex (gaps) не вызывает ошибок.
    Реализация работает по индексам массива, не по временным разницам.
    """
    # Смешиваем минутные и часовые интервалы
    timestamps = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-01 00:00", tz="UTC"),
            pd.Timestamp("2026-01-01 00:01", tz="UTC"),
            pd.Timestamp("2026-01-01 01:00", tz="UTC"),  # gap 59 минут
            pd.Timestamp("2026-01-01 01:01", tz="UTC"),
            pd.Timestamp("2026-01-01 06:00", tz="UTC"),  # gap 5 часов
            pd.Timestamp("2026-01-01 06:01", tz="UTC"),
            pd.Timestamp("2026-01-01 06:02", tz="UTC"),
            pd.Timestamp("2026-01-01 06:03", tz="UTC"),
            pd.Timestamp("2026-01-01 06:04", tz="UTC"),
            pd.Timestamp("2026-01-01 06:05", tz="UTC"),
        ]
    )
    n = len(timestamps)
    close = np.full(n, 100.0)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": np.ones(n),
        },
        index=timestamps,
    )

    config = BarrierConfig(profit_take=0.02, stop_loss=0.01, max_horizon=3)

    result = triple_barrier_labels(df, config)

    assert len(result) == n
    assert result["label"].isin([-1, 0, 1]).all()
    assert result["barrier_type"].isin(["pt", "sl", "vert"]).all()

    # t1 <= последний timestamp
    assert (result["t1"] <= timestamps[-1]).all()


# ---------------------------------------------------------------------------
# test_triple_barrier_empty_input
# ---------------------------------------------------------------------------


def test_triple_barrier_empty_input() -> None:
    """Пустой DataFrame на входе → пустой DataFrame с правильными колонками."""
    empty = pd.DataFrame(
        columns=["open", "high", "low", "close", "volume"],
        index=pd.DatetimeIndex([], tz="UTC"),
    )
    config = BarrierConfig(profit_take=0.02, stop_loss=0.01, max_horizon=10)

    result = triple_barrier_labels(empty, config)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0
    assert {"label", "t1", "barrier_type", "vert_time"}.issubset(set(result.columns))


# ---------------------------------------------------------------------------
# test_triple_barrier_nonmonotonic_raises
# ---------------------------------------------------------------------------


def test_triple_barrier_nonmonotonic_raises() -> None:
    """Немонотонный индекс вызывает ValueError."""
    df = _make_ohlcv(n=5)
    df = df.iloc[::-1].copy()  # reverse

    config = BarrierConfig(profit_take=0.02, stop_loss=0.01, max_horizon=3)
    with pytest.raises(ValueError, match="monotonically increasing"):
        triple_barrier_labels(df, config)


# ---------------------------------------------------------------------------
# test_triple_barrier_output_schema
# ---------------------------------------------------------------------------


def test_triple_barrier_output_schema(synthetic_ohlcv: pd.DataFrame) -> None:
    """
    Структура выходного DataFrame:
    - Индекс совпадает с входным.
    - label: int8 в {-1, 0, +1}.
    - t1: DatetimeIndex с timezone UTC.
    - barrier_type: строки в {"pt", "sl", "vert"}.
    - vert_time: DatetimeIndex с timezone UTC.
    """
    config = BarrierConfig(profit_take=0.02, stop_loss=0.01, max_horizon=24)
    result = triple_barrier_labels(synthetic_ohlcv, config)

    assert len(result) == len(synthetic_ohlcv)
    assert result.index.equals(synthetic_ohlcv.index)

    # label dtype и допустимые значения
    assert result["label"].dtype == np.int8
    assert result["label"].isin([-1, 0, 1]).all()

    # barrier_type — строки
    assert result["barrier_type"].dtype == object
    assert result["barrier_type"].isin(["pt", "sl", "vert"]).all()

    # t1 и vert_time — timezone-aware
    assert isinstance(
        result["t1"], pd.DatetimeIndex
    ) or pd.api.types.is_datetime64_any_dtype(result["t1"])
    assert result["t1"].dt.tz is not None

    # vert_time не выходит за пределы данных
    assert (result["vert_time"] <= synthetic_ohlcv.index[-1]).all()


# ---------------------------------------------------------------------------
# test_triple_barrier_single_bar
# ---------------------------------------------------------------------------


def test_triple_barrier_single_bar() -> None:
    """DataFrame из одного бара → label=0, vert (нет данных вперёд)."""
    timestamps = pd.DatetimeIndex([pd.Timestamp("2026-01-01", tz="UTC")])
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [100.0],
            "volume": [1.0],
        },
        index=timestamps,
    )
    config = BarrierConfig(profit_take=0.02, stop_loss=0.01, max_horizon=5)

    result = triple_barrier_labels(df, config)

    assert len(result) == 1
    assert result["label"].iloc[0] == 0
    assert result["barrier_type"].iloc[0] == "vert"
    assert result["t1"].iloc[0] == timestamps[0]
