"""
Triple-barrier labeling (AFML Ch.3).

Each bar is labeled with one of three labels:
  +1  — upper barrier reached (profit take, PT)
  -1  — lower barrier reached (stop loss, SL)
   0  — vertical barrier reached (time horizon)

If PT and SL trigger simultaneously in one bar, PT takes priority
(conservative convention; precise resolution requires tick data).

Implements two variants of the inner loop:
- _triple_barrier_scan : pure Python/numpy (reference for tests; fallback without numba)
- _scan_jit            : JIT-compiled version of the same function via numba

The public function ``triple_barrier_labels()`` uses ``_scan_jit`` if
numba is available, otherwise falls back to ``_triple_barrier_scan`` with a RuntimeWarning.

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
    Pure Python/numpy inner loop for triple-barrier scan.

    Intentionally written in numba-compatible style (no Python objects)
    so it can be JIT-compiled without changes via ``nb.njit``.

    Args:
        close:  Array of closing prices (float64), length n.
        high:   Array of high prices (float64), length n.
        low:    Array of low prices (float64), length n.
        pt:     Profit take threshold (price fraction, e.g. 0.02 = 2%).
        sl:     Stop loss threshold (price fraction, e.g. 0.01 = 1%).
        max_h:  Maximum number of bars until the vertical barrier.

    Returns:
        Tuple of three int64 arrays of length n:
          labels       — label (-1, 0, +1) for each input bar.
          t1_idx       — index of the bar where the barrier was triggered.
          barrier_code — barrier code (1=pt, -1=sl, 0=vert).
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
            # Vertical barrier: t1 = end of horizon (or end of data)
            t1_idx[i] = end_idx
            # labels[i] and barrier_code[i] remain 0

    return labels, t1_idx, barrier_code


if _NUMBA_AVAILABLE:
    # JIT-compile the reference function. cache=True saves the compiled
    # bytecode to disk — subsequent runs do not require recompilation.
    _scan_jit = nb.njit(cache=True)(_triple_barrier_scan)
else:
    _scan_jit = _triple_barrier_scan


_BARRIER_CODE_TO_TYPE: dict[int, str] = {1: "pt", -1: "sl", 0: "vert"}


def triple_barrier_labels(
    df: pd.DataFrame,
    config: BarrierConfig,
) -> pd.DataFrame:
    """
    Labels bars using the triple-barrier method (AFML Ch.3).

    Args:
        df:     DataFrame with columns ``open, high, low, close, volume``.
                Index — DatetimeIndex, strictly monotonically increasing.
        config: :class:`~src.ml.models.BarrierConfig` with parameters
                ``profit_take``, ``stop_loss``, ``max_horizon``.

    Returns:
        DataFrame with columns:
          ``label``        — int8, label (+1, -1, 0).
          ``t1``           — Timestamp, time the barrier was triggered.
          ``barrier_type`` — str, barrier type ("pt", "sl", "vert").
          ``vert_time``    — Timestamp, scheduled vertical barrier time
                             (regardless of whether it was reached).
        Index matches the input ``df``.

    Raises:
        ValueError: if the index of ``df`` is not monotonically increasing.

    Notes:
        - Gaps in the time series are not handled specially:
          each subsequent bar is the next array element, regardless of
          the time distance between them.
        - When PT and SL trigger simultaneously in the same bar, PT takes priority.
        - The last bar always receives label 0 (no forward data).
    """
    if not df.index.is_monotonic_increasing:
        raise ValueError(
            "df.index must be monotonically increasing. "
            "Check the correctness of the time series."
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
            "numba is not available; using slow Python fallback for triple-barrier. "
            "Install numba for ~100x speedup on large datasets.",
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
