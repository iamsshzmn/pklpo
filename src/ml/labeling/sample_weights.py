"""
Uniqueness-based sample weights (AFML Ch.4).

Концепция:
    Метки triple-barrier перекрываются по времени: метка i "живёт" от entry_i
    до t1_i. Чем больше меток перекрываются в данный момент, тем меньше
    уникальной информации несёт каждая из них.

Формула:
    concurrency_t = число меток со span [t0, t1], содержащим бар t
    uniqueness_i_t = 1 / concurrency_t   для каждого t в span_i
    weight_i      = mean(uniqueness_i_t  for t in span_i)

Опциональный time-decay:
    Более старым меткам присваивается меньший вес через линейный decay.
    decay_factor=1.0 — без decay.
    decay_factor=0.5 — самый старый образец получает 50% от uniqueness.

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.4
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _build_concurrency(t1: pd.Series, bars: pd.DatetimeIndex) -> pd.Series:
    """
    Вычисляет число одновременно "живых" меток на каждом баре.

    Args:
        t1:   Series[entry_timestamp -> exit_timestamp].
        bars: DatetimeIndex всех баров (из close.index).

    Returns:
        Series[bar_timestamp -> float] — счётчик concurrent меток на каждом баре.
    """
    concurrency = pd.Series(0.0, index=bars, dtype=float)
    for entry, exit_time in t1.items():
        # .items() сохраняет timezone-aware pd.Timestamp;
        # .values может терять tz-info в некоторых версиях pandas
        mask = (bars >= entry) & (bars <= exit_time)
        concurrency += mask.astype(float)
    return concurrency


def get_uniqueness_weights(
    t1: pd.Series,
    close: pd.Series,
    decay_factor: float = 1.0,
) -> pd.Series:
    """
    Вычисляет uniqueness-based sample weights для передачи в sklearn fit().

    Args:
        t1:           Series[entry_timestamp -> exit_timestamp].
                      Индекс — времена входа в позицию (entry times).
                      Значения — времена выхода (t1 из triple-barrier labeling).
                      Должен быть отсортирован хронологически (или будет отсортирован).
        close:        Ценовой ряд. Только индекс (DatetimeIndex баров) используется
                      для построения universe баров.
        decay_factor: Float в (0, 1]. При 1.0 decay не применяется.
                      При < 1.0 линейное снижение от decay_factor (старейший)
                      до 1.0 (новейший образец).

    Returns:
        pd.Series весов (float), индексированный по t1.index.
        Веса не нормализованы к сумме n — используются как-есть в
        ``model.fit(X, y, sample_weight=weights)``.

    Raises:
        ValueError: если decay_factor не в диапазоне (0, 1].

    Notes:
        Эффективность: O(n_labels * n_bars). Для 1000 меток и 10 000 баров
        это ~10M операций; приемлемо для типичных ML-датасетов.
        При n_labels > 10 000 рассмотрите векторизацию через событийный метод.
    """
    if not 0.0 < decay_factor <= 1.0:
        raise ValueError(
            f"decay_factor должен быть в диапазоне (0, 1], получен {decay_factor}"
        )

    if len(t1) == 0:
        return pd.Series(dtype=float)

    t1 = t1.sort_index()
    bars = close.index

    concurrency = _build_concurrency(t1, bars)

    weights = pd.Series(index=t1.index, dtype=float)
    for i, (entry, exit_time) in enumerate(t1.items()):
        span_mask = (bars >= entry) & (bars <= exit_time)
        span_concurrency = concurrency[span_mask]

        if len(span_concurrency) > 0 and span_concurrency.sum() > 0:
            weights.iloc[i] = (1.0 / span_concurrency).mean()
        else:
            # Нет баров в span (разрыв данных) — максимальный вес
            weights.iloc[i] = 1.0

    # Time decay: линейная интерполяция от decay_factor (первый) до 1.0 (последний)
    if decay_factor < 1.0:
        n = len(weights)
        decay = np.linspace(decay_factor, 1.0, n) if n > 1 else np.array([1.0])
        weights = weights * decay

    return weights
