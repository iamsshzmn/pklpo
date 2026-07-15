"""
Numerical-equivalence tests for src/ml/labeling and src/ml/validation.

Верифицируют, что публичные функции возвращают ТОЧНЫЕ значения на
малых детерминированных датасетах, где ожидаемый результат рассчитан вручную.

Цель (Roadmap A2): гарантировать корректность реализации против известных
reference-значений (AFML Ch.3, Ch.4).

Все тесты:
  - работают на синтетических данных без подключения к БД;
  - не имеют зависимостей от numba (используют только _triple_barrier_scan);
  - детерминированы и независимы от seed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.ml.labeling.sample_weights import _build_concurrency, get_uniqueness_weights
from src.ml.labeling.triple_barrier import _triple_barrier_scan

# ---------------------------------------------------------------------------
# Triple-barrier: hand-computed reference
# ---------------------------------------------------------------------------
#
# Dataset (5 bars):
#   index: 0  1    2    3    4
#   close: 100 100  100  100  100  (flat reference price)
#   high:  100 103  100  100  100  → bar 1 triggers PT for bar 0
#   low:   100 100   98  100  100  → bar 2 triggers SL for bar 1
#
# Parameters: pt=0.02 (2%), sl=0.01 (1%), max_h=2
#
# Bar 0: pt_level=102, sl_level=99
#   j=1: high[1]=103 >= 102 → PT hit → label=+1, t1_idx=1
# Bar 1: pt_level=102, sl_level=99
#   j=2: high[2]=100 < 102; low[2]=98 <= 99 → SL hit → label=-1, t1_idx=2
# Bar 2: pt_level=102, sl_level=99, end_idx=min(4,4)=4
#   j=3: no hit; j=4: no hit → vertical → label=0, t1_idx=4
# Bar 3: end_idx=min(5,4)=4
#   j=4: no hit → vertical → label=0, t1_idx=4
# Bar 4: end_idx=min(6,4)=4
#   range(5,5) empty → vertical → label=0, t1_idx=4

_CLOSE = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
_HIGH = np.array([100.0, 103.0, 100.0, 100.0, 100.0])
_LOW = np.array([100.0, 100.0, 98.0, 100.0, 100.0])

_EXPECTED_LABELS = np.array([1, -1, 0, 0, 0], dtype=np.int64)
_EXPECTED_T1_IDX = np.array([1, 2, 4, 4, 4], dtype=np.int64)
_EXPECTED_BARRIER_CODE = np.array([1, -1, 0, 0, 0], dtype=np.int64)


def test_triple_barrier_labels_reference() -> None:
    """
    _triple_barrier_scan возвращает точные эталонные значения
    на 5-барном датасете с ручным расчётом.
    """
    labels, t1_idx, barrier_code = _triple_barrier_scan(
        _CLOSE, _HIGH, _LOW, pt=0.02, sl=0.01, max_h=2
    )

    np.testing.assert_array_equal(labels, _EXPECTED_LABELS)
    np.testing.assert_array_equal(t1_idx, _EXPECTED_T1_IDX)
    np.testing.assert_array_equal(barrier_code, _EXPECTED_BARRIER_CODE)


def test_triple_barrier_pt_triggers_before_sl() -> None:
    """
    Если PT и SL достижимы в одном и том же баре (high>=pt_level, low<=sl_level),
    PT имеет приоритет (консервативная конвенция, AFML Ch.3).

    Ожидание: label=+1 (PT выигрывает).
    """
    close = np.array([100.0, 100.0])
    high = np.array([100.0, 103.0])  # bar1 high >= 102 → PT
    low = np.array([100.0, 98.0])  # bar1 low  <= 99  → SL (тот же бар)

    labels, _t1_idx, barrier_code = _triple_barrier_scan(
        close, high, low, pt=0.02, sl=0.01, max_h=1
    )

    assert labels[0] == 1, "PT должен иметь приоритет над SL в одном баре"
    assert barrier_code[0] == 1


def test_triple_barrier_vertical_when_no_barrier_hit() -> None:
    """
    Если ни PT, ни SL не достигнуты в горизонте — вертикальный барьер (label=0).
    """
    close = np.array([100.0, 100.0, 100.0, 100.0])
    high = np.array([100.0, 100.5, 100.5, 100.5])  # < 102
    low = np.array([100.0, 99.5, 99.5, 99.5])  # > 99

    labels, _t1_idx, barrier_code = _triple_barrier_scan(
        close, high, low, pt=0.02, sl=0.01, max_h=3
    )

    np.testing.assert_array_equal(labels, [0, 0, 0, 0])
    np.testing.assert_array_equal(barrier_code, [0, 0, 0, 0])


def test_triple_barrier_exact_boundary_pt() -> None:
    """
    high[j] == pt_level (точно на границе) — PT должен сработать.
    """
    close = np.array([100.0, 100.0])
    high = np.array([100.0, 102.0])  # точно на 2% (pt_level = 100*1.02 = 102)
    low = np.array([100.0, 100.0])

    labels, _, _ = _triple_barrier_scan(close, high, low, pt=0.02, sl=0.01, max_h=1)
    assert labels[0] == 1, "Граничное значение high == pt_level должно давать PT"


def test_triple_barrier_exact_boundary_sl() -> None:
    """
    low[j] == sl_level (точно на границе) — SL должен сработать.
    """
    close = np.array([100.0, 100.0])
    high = np.array([100.0, 100.0])
    low = np.array([100.0, 99.0])  # точно на 1% (sl_level = 100*0.99 = 99)

    labels, _, _ = _triple_barrier_scan(close, high, low, pt=0.02, sl=0.01, max_h=1)
    assert labels[0] == -1, "Граничное значение low == sl_level должно давать SL"


# ---------------------------------------------------------------------------
# Sample weights: hand-computed reference (AFML Ch.4)
# ---------------------------------------------------------------------------
#
# Dataset: 5 баров [t0..t4], 2 метки с перекрытием:
#   t1 = { t0 → t2,   t1 → t3 }
#
# _build_concurrency:
#   t0 += 1 (от метки t0→t2)
#   t1 += 1 (от метки t0→t2) + 1 (от метки t1→t3) = 2
#   t2 += 1 (от метки t0→t2) + 1 (от метки t1→t3) = 2
#   t3 += 1 (от метки t1→t3)
#   t4 = 0
#   → concurrency = [1, 2, 2, 1, 0]
#
# weight_0 (span t0→t2): bars {t0,t1,t2}, concurrency [1,2,2]
#   → mean(1/1, 1/2, 1/2) = mean(1.0, 0.5, 0.5) = 2.0/3
#
# weight_1 (span t1→t3): bars {t1,t2,t3}, concurrency [2,2,1]
#   → mean(1/2, 1/2, 1/1) = mean(0.5, 0.5, 1.0) = 2.0/3


def _make_overlapping_t1_and_close() -> tuple[pd.Series, pd.Series]:
    """5 баров, 2 перекрывающихся метки."""
    bars = pd.date_range("2026-01-01", periods=5, freq="1h", tz="UTC")
    t1 = pd.Series(
        {bars[0]: bars[2], bars[1]: bars[3]},
        dtype="datetime64[ns, UTC]",
    )
    close = pd.Series(100.0, index=bars)
    return t1, close


def test_concurrency_overlapping_reference() -> None:
    """_build_concurrency возвращает точные счётчики на эталонном датасете."""
    t1, close = _make_overlapping_t1_and_close()
    bars = close.index

    conc = _build_concurrency(t1, bars)

    expected = pd.Series([1.0, 2.0, 2.0, 1.0, 0.0], index=bars)
    pd.testing.assert_series_equal(conc, expected)


def test_uniqueness_weights_overlapping_reference() -> None:
    """
    get_uniqueness_weights возвращает ≈ 2/3 для обеих меток
    в эталонном датасете с двумя перекрывающимися метками.
    """
    t1, close = _make_overlapping_t1_and_close()

    weights = get_uniqueness_weights(t1, close, decay_factor=1.0)

    assert weights.shape == (2,)
    np.testing.assert_allclose(weights.values, [2.0 / 3, 2.0 / 3], rtol=1e-10)


def test_uniqueness_weights_non_overlapping_equals_one() -> None:
    """
    Непересекающиеся метки → uniqueness = 1.0 (каждая метка уникальна).
    """
    bars = pd.date_range("2026-01-01", periods=6, freq="1h", tz="UTC")
    # [t0→t1], [t3→t4] — разделены пробелом t2
    t1 = pd.Series(
        {bars[0]: bars[1], bars[3]: bars[4]},
        dtype="datetime64[ns, UTC]",
    )
    close = pd.Series(100.0, index=bars)

    weights = get_uniqueness_weights(t1, close, decay_factor=1.0)

    np.testing.assert_allclose(weights.values, [1.0, 1.0], rtol=1e-10)


def test_uniqueness_weights_time_decay_monotone() -> None:
    """
    С decay_factor < 1.0 веса растут слева направо
    (старые метки дисконтируются).
    """
    bars = pd.date_range("2026-01-01", periods=8, freq="1h", tz="UTC")
    t1 = pd.Series(
        {bars[0]: bars[1], bars[2]: bars[3], bars[4]: bars[5]},
        dtype="datetime64[ns, UTC]",
    )
    close = pd.Series(100.0, index=bars)

    weights = get_uniqueness_weights(t1, close, decay_factor=0.5)

    # Каждый следующий вес >= предыдущего (monotone non-decreasing)
    diffs = np.diff(weights.values)
    assert (diffs >= -1e-12).all(), f"Decay должен быть монотонен: {weights.values}"


def test_uniqueness_weights_time_decay_exact() -> None:
    """
    Точные значения с decay_factor=0.5 для 3 непересекающихся меток.

    Без decay: все веса = 1.0
    Decay linspace(0.5, 1.0, 3) = [0.5, 0.75, 1.0]
    → ожидаемые веса = [0.5, 0.75, 1.0]
    """
    bars = pd.date_range("2026-01-01", periods=9, freq="1h", tz="UTC")
    t1 = pd.Series(
        {bars[0]: bars[1], bars[3]: bars[4], bars[6]: bars[7]},
        dtype="datetime64[ns, UTC]",
    )
    close = pd.Series(100.0, index=bars)

    weights = get_uniqueness_weights(t1, close, decay_factor=0.5)

    np.testing.assert_allclose(
        weights.values,
        [0.5, 0.75, 1.0],
        rtol=1e-10,
        err_msg="Decay=0.5 для 3 непересекающихся меток → linspace(0.5,1.0,3)",
    )
