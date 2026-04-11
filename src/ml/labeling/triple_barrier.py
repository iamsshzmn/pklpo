"""
Triple-barrier маркировка (AFML Ch.3).

Каждый бар маркируется одной из трёх меток:
  +1  — достигнут верхний барьер (profit take, PT)
  -1  — достигнут нижний барьер (stop loss, SL)
   0  — достигнут вертикальный барьер (временной горизонт)

Если в одном баре одновременно срабатывают PT и SL, PT имеет приоритет
(консервативная convention; точное разрешение требует тиковых данных).

Реализует два варианта inner loop:
- _triple_barrier_scan : чистый Python/numpy (эталон для тестов; fallback без numba)
- _scan_jit            : JIT-ускоренная компиляция той же функции через numba

Публичная функция ``triple_barrier_labels()`` использует ``_scan_jit`` если
numba доступна, иначе — ``_triple_barrier_scan`` с RuntimeWarning.

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.3
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.ml.models import BarrierConfig

try:
    import numba as nb

    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False


def _triple_barrier_scan(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    pt: float,
    sl: float,
    max_h: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Pure Python/numpy inner loop для triple-barrier scan.

    Реализация намеренно написана в numba-совместимом стиле (без Python-объектов),
    чтобы её можно было JIT-компилировать без изменений через ``nb.njit``.

    Args:
        close:  Массив цен закрытия (float64), длина n.
        high:   Массив максимальных цен (float64), длина n.
        low:    Массив минимальных цен (float64), длина n.
        pt:     Profit take порог (доля цены, например 0.02 = 2%).
        sl:     Stop loss порог (доля цены, например 0.01 = 1%).
        max_h:  Максимальное число баров до вертикального барьера.

    Returns:
        Кортеж из трёх int64-массивов длины n:
          labels       — метка (-1, 0, +1) для каждого входного бара.
          t1_idx       — индекс бара, где сработал барьер.
          barrier_code — код барьера (1=pt, -1=sl, 0=vert).
    """
    n = len(close)
    labels = np.zeros(n, dtype=np.int64)
    t1_idx = np.zeros(n, dtype=np.int64)
    barrier_code = np.zeros(n, dtype=np.int64)

    for i in range(n):
        pt_level = close[i] * (1.0 + pt)
        sl_level = close[i] * (1.0 - sl)
        end_idx = min(i + max_h, n - 1)
        hit = False

        for j in range(i + 1, end_idx + 1):
            if high[j] >= pt_level:
                labels[i] = 1
                t1_idx[i] = j
                barrier_code[i] = 1
                hit = True
                break
            if low[j] <= sl_level:
                labels[i] = -1
                t1_idx[i] = j
                barrier_code[i] = -1
                hit = True
                break

        if not hit:
            # Вертикальный барьер: t1 = конец горизонта (или конец данных)
            t1_idx[i] = end_idx
            # labels[i] и barrier_code[i] остаются 0

    return labels, t1_idx, barrier_code


if _NUMBA_AVAILABLE:
    # JIT-компиляция эталонной функции. cache=True сохраняет скомпилированный
    # байткод на диск — повторные запуски не требуют перекомпиляции.
    _scan_jit = nb.njit(cache=True)(_triple_barrier_scan)
else:
    _scan_jit = _triple_barrier_scan


_BARRIER_CODE_TO_TYPE: dict[int, str] = {1: "pt", -1: "sl", 0: "vert"}


def triple_barrier_labels(
    df: pd.DataFrame,
    config: BarrierConfig,
) -> pd.DataFrame:
    """
    Маркировка баров методом triple-barrier (AFML Ch.3).

    Args:
        df:     DataFrame с колонками ``open, high, low, close, volume``.
                Индекс — DatetimeIndex, строго монотонно возрастающий.
        config: :class:`~src.ml.models.BarrierConfig` с параметрами
                ``profit_take``, ``stop_loss``, ``max_horizon``.

    Returns:
        DataFrame с колонками:
          ``label``        — int8, метка (+1, -1, 0).
          ``t1``           — Timestamp, время срабатывания барьера.
          ``barrier_type`` — str, тип барьера ("pt", "sl", "vert").
          ``vert_time``    — Timestamp, плановое время вертикального барьера
                             (независимо от того, был ли он достигнут).
        Индекс совпадает с входным ``df``.

    Raises:
        ValueError: если индекс ``df`` не монотонно возрастает.

    Notes:
        - Пропуски (gaps) во временном ряду не обрабатываются специальным образом:
          каждый следующий бар — это следующий элемент массива, вне зависимости
          от временного расстояния.
        - При совместном срабатывании PT и SL в одном баре PT имеет приоритет.
        - Последний бар всегда получает метку 0 (нет данных вперёд).
    """
    if not df.index.is_monotonic_increasing:
        raise ValueError(
            "df.index должен быть монотонно возрастающим. "
            "Проверьте корректность временного ряда."
        )

    if len(df) == 0:
        return pd.DataFrame(
            columns=["label", "t1", "barrier_type", "vert_time"],
            index=df.index,
        )

    close = df["close"].to_numpy(dtype=np.float64)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)

    if _NUMBA_AVAILABLE:
        scan_fn = _scan_jit
    else:
        warnings.warn(
            "numba недоступна; используется медленный Python fallback для triple-barrier. "
            "Установите numba для ~100x ускорения на больших датасетах.",
            RuntimeWarning,
            stacklevel=2,
        )
        scan_fn = _triple_barrier_scan

    labels, t1_idx, barrier_code = scan_fn(
        close, high, low, config.profit_take, config.stop_loss, config.max_horizon
    )

    timestamps = df.index
    n = len(df)

    t1 = pd.DatetimeIndex([timestamps[int(idx)] for idx in t1_idx])
    barrier_type = [_BARRIER_CODE_TO_TYPE[int(c)] for c in barrier_code]

    vert_idx = np.minimum(np.arange(n, dtype=np.int64) + config.max_horizon, n - 1)
    vert_time = pd.DatetimeIndex([timestamps[int(idx)] for idx in vert_idx])

    return pd.DataFrame(
        {
            "label": labels.astype(np.int8),
            "t1": t1,
            "barrier_type": barrier_type,
            "vert_time": vert_time,
        },
        index=df.index,
    )
