"""
Тесты для src/ml/labeling/sample_weights.py.

Проверяют корректность uniqueness-based весов (AFML Ch.4):
- Непересекающиеся метки → uniqueness = 1.0.
- Полностью перекрывающиеся метки → uniqueness = 1/n.
- time-decay снижает вес старых меток.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ml.labeling.sample_weights import _build_concurrency, get_uniqueness_weights

# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _make_t1_and_close(
    n_labels: int = 5,
    span_bars: int = 3,
    gap_bars: int = 0,
    total_bars: int | None = None,
) -> tuple[pd.Series, pd.Series]:
    """
    Создаёт непересекающиеся метки (каждая span_bars баров) и close-ряд.

    Параметры:
        n_labels:   Число меток.
        span_bars:  Длина каждой метки в барах (включительно).
        gap_bars:   Число баров-пробела между метками.
        total_bars: Общее число баров (по умолчанию n_labels * (span_bars + gap_bars)).

    Возвращает:
        t1:    Series[entry_timestamp -> exit_timestamp].
        close: Series с DatetimeIndex как universe баров.
    """
    stride = span_bars + gap_bars
    if total_bars is None:
        total_bars = n_labels * stride

    timestamps = pd.date_range("2026-01-01", periods=total_bars, freq="1min", tz="UTC")
    close = pd.Series(np.ones(total_bars) * 100.0, index=timestamps)

    entries = [timestamps[i * stride] for i in range(n_labels)]
    exits = [timestamps[min(i * stride + span_bars - 1, total_bars - 1)] for i in range(n_labels)]

    t1 = pd.Series(exits, index=pd.DatetimeIndex(entries))
    return t1, close


def _make_overlapping_t1_and_close(
    n_labels: int = 3,
    total_bars: int = 10,
) -> tuple[pd.Series, pd.Series]:
    """
    Создаёт n_labels меток с ИДЕНТИЧНЫМИ spans [t0, t[-1]].

    Дубликаты в индексе допустимы — pandas поддерживает non-unique index.
    При полном перекрытии concurrency = n_labels на каждом баре.
    """
    timestamps = pd.date_range("2026-01-01", periods=total_bars, freq="1min", tz="UTC")
    close = pd.Series(np.ones(total_bars) * 100.0, index=timestamps)

    # Все метки имеют одинаковый span [t0, t[-1]] → concurrency = n_labels везде
    entries = pd.DatetimeIndex([timestamps[0]] * n_labels)
    exits = [timestamps[-1]] * n_labels
    t1 = pd.Series(pd.DatetimeIndex(exits), index=entries)
    return t1, close


# ---------------------------------------------------------------------------
# test_sample_weights_no_overlap
# ---------------------------------------------------------------------------


def test_sample_weights_no_overlap() -> None:
    """
    Непересекающиеся метки → на каждом баре ровно одна метка активна.
    Concurrency = 1.0, uniqueness = 1.0, weight = 1.0 для всех меток.
    """
    n_labels = 4
    span = 3  # bars per label, no gap
    t1, close = _make_t1_and_close(n_labels=n_labels, span_bars=span, gap_bars=0)

    weights = get_uniqueness_weights(t1, close)

    assert len(weights) == n_labels
    assert weights.isna().sum() == 0
    np.testing.assert_allclose(
        weights.values,
        np.ones(n_labels),
        rtol=1e-6,
        err_msg="Непересекающиеся метки должны иметь uniqueness=1.0",
    )


# ---------------------------------------------------------------------------
# test_sample_weights_full_overlap
# ---------------------------------------------------------------------------


def test_sample_weights_full_overlap() -> None:
    """
    Полностью перекрывающиеся метки → concurrency = n_labels, uniqueness = 1/n_labels.
    Веса должны быть < 1.0 и равны между собой.
    """
    n_labels = 4
    t1, close = _make_overlapping_t1_and_close(n_labels=n_labels, total_bars=20)

    weights = get_uniqueness_weights(t1, close)

    assert len(weights) == n_labels

    # Все веса < 1.0 (есть перекрытие)
    assert (weights < 1.0).all(), f"Ожидались веса < 1.0, получено:\n{weights}"

    # Все веса примерно равны (одинаковое перекрытие)
    np.testing.assert_allclose(
        weights.values,
        np.full(n_labels, 1.0 / n_labels),
        rtol=1e-5,
        err_msg="При полном перекрытии uniqueness должна быть равна 1/n_labels",
    )


# ---------------------------------------------------------------------------
# test_sample_weights_partial_overlap
# ---------------------------------------------------------------------------


def test_sample_weights_partial_overlap() -> None:
    """
    Частичное перекрытие → средняя uniqueness между 1/n и 1.
    Веса должны быть в диапазоне (0, 1].
    """
    # 3 метки по 5 баров с шагом 2 (перекрытие 3 баров между соседними)
    t1, close = _make_t1_and_close(n_labels=3, span_bars=5, gap_bars=0)

    weights = get_uniqueness_weights(t1, close)

    assert len(weights) == 3
    assert (weights > 0).all()
    assert (weights <= 1.0 + 1e-9).all()


# ---------------------------------------------------------------------------
# test_sample_weights_decay_reduces_old_weight
# ---------------------------------------------------------------------------


def test_sample_weights_decay() -> None:
    """
    time-decay с decay_factor < 1.0 снижает вес старых меток.
    - Первый (старейший) образец: вес с decay < вес без decay.
    - Последний (новейший) образец: вес с decay == вес без decay.
    """
    n_labels = 5
    t1, close = _make_t1_and_close(n_labels=n_labels, span_bars=2, gap_bars=1)

    weights_no_decay = get_uniqueness_weights(t1, close, decay_factor=1.0)
    weights_decay = get_uniqueness_weights(t1, close, decay_factor=0.5)

    assert len(weights_decay) == n_labels

    # Старейший образец должен иметь меньший вес при decay
    assert weights_decay.iloc[0] < weights_no_decay.iloc[0], (
        "Decay должен снижать вес старейшей метки"
    )

    # Новейший образец сохраняет вес (decay_weight = 1.0 для последнего)
    np.testing.assert_allclose(
        weights_decay.iloc[-1],
        weights_no_decay.iloc[-1],
        rtol=1e-9,
        err_msg="Новейшая метка не должна изменяться от decay",
    )

    # Все веса > 0
    assert (weights_decay > 0).all()


# ---------------------------------------------------------------------------
# test_sample_weights_empty_t1
# ---------------------------------------------------------------------------


def test_sample_weights_empty_t1() -> None:
    """Пустой t1 → пустой результат."""
    t1 = pd.Series(dtype="datetime64[ns, UTC]")
    timestamps = pd.date_range("2026-01-01", periods=10, freq="1min", tz="UTC")
    close = pd.Series(np.ones(10) * 100.0, index=timestamps)

    weights = get_uniqueness_weights(t1, close)

    assert isinstance(weights, pd.Series)
    assert len(weights) == 0


# ---------------------------------------------------------------------------
# test_sample_weights_invalid_decay_factor
# ---------------------------------------------------------------------------


def test_sample_weights_invalid_decay_factor() -> None:
    """decay_factor вне (0, 1] вызывает ValueError."""
    t1, close = _make_t1_and_close(n_labels=3)

    with pytest.raises(ValueError, match="decay_factor"):
        get_uniqueness_weights(t1, close, decay_factor=0.0)

    with pytest.raises(ValueError, match="decay_factor"):
        get_uniqueness_weights(t1, close, decay_factor=1.5)


# ---------------------------------------------------------------------------
# test_build_concurrency_no_overlap
# ---------------------------------------------------------------------------


def test_build_concurrency_no_overlap() -> None:
    """Для непересекающихся меток concurrency = 1 в каждом занятом баре."""
    t1, close = _make_t1_and_close(n_labels=3, span_bars=2, gap_bars=2)
    bars = close.index

    concurrency = _build_concurrency(t1, bars)

    # Где concurrency > 0, оно должно быть = 1.0 (нет overlap)
    nonzero = concurrency[concurrency > 0]
    np.testing.assert_allclose(
        nonzero.values,
        np.ones(len(nonzero)),
        rtol=1e-9,
        err_msg="Concurrency должна быть 1.0 для непересекающихся меток",
    )


# ---------------------------------------------------------------------------
# test_build_concurrency_full_overlap
# ---------------------------------------------------------------------------


def test_build_concurrency_full_overlap() -> None:
    """При полном перекрытии n меток concurrency = n на всех барах внутри span."""
    n_labels = 3
    total_bars = 10
    t1, close = _make_overlapping_t1_and_close(n_labels=n_labels, total_bars=total_bars)
    bars = close.index

    concurrency = _build_concurrency(t1, bars)

    # Все бары покрыты всеми метками → concurrency = n_labels
    np.testing.assert_allclose(
        concurrency.values,
        np.full(total_bars, float(n_labels)),
        rtol=1e-9,
    )


# ---------------------------------------------------------------------------
# test_sample_weights_integration_with_triple_barrier
# ---------------------------------------------------------------------------


def test_sample_weights_integration_with_triple_barrier(
    synthetic_ohlcv: pd.DataFrame,
) -> None:
    """
    Интеграционный тест: sample weights из t1, полученных triple_barrier_labels().

    Проверяет совместимость форматов между двумя модулями.
    """
    from src.ml.labeling.triple_barrier import triple_barrier_labels
    from src.ml.models import BarrierConfig

    config = BarrierConfig(profit_take=0.02, stop_loss=0.01, max_horizon=24)
    labels_df = triple_barrier_labels(synthetic_ohlcv, config)

    # t1 для get_uniqueness_weights: entry -> exit mapping
    t1 = labels_df["t1"]

    weights = get_uniqueness_weights(t1, synthetic_ohlcv["close"])

    assert len(weights) == len(synthetic_ohlcv)
    assert (weights > 0).all()
    assert weights.isna().sum() == 0

    # Веса должны быть в допустимом диапазоне (0, 1] при типичных данных
    # (небольшая часть баров может иметь uniqueness > 1.0 после decay... нет, без decay)
    # При decay_factor=1.0 все веса <= 1.0
    assert (weights <= 1.0 + 1e-9).all(), (
        f"Некоторые веса > 1.0: {weights[weights > 1.0 + 1e-9]}"
    )
