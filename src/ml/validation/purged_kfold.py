"""
Purged K-Fold Cross-Validation с Embargo (AFML Ch.7).

Предотвращает look-ahead bias двумя механизмами:

1. **Purging**: удаляет тренировочные образцы, чей label-span (t1) перекрывается
   с периодом тестовой выборки. Эти образцы «знают будущее» тестового периода.

2. **Embargo**: удаляет n_embargo тренировочных образцов, идущих сразу после
   тестовой выборки. Они могут быть зависимы от тестового периода через сериальную
   корреляцию или look-ahead в данных.

Совместимость со scikit-learn:
    PurgedKFold наследует BaseCrossValidator и может быть передан в
    cross_val_score, cross_validate, GridSearchCV и т.д.

    Параметр t1 передаётся через аргумент groups:
        cross_val_score(model, X, y, cv=PurgedKFold(n_splits=5), groups=t1)

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.7
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import BaseCrossValidator


def _n_samples(X: Any) -> int:
    """Число образцов для DataFrame, ndarray или любого __len__-объекта."""
    if hasattr(X, "shape"):
        return int(X.shape[0])
    return len(X)


class PurgedKFold(BaseCrossValidator):
    """
    Purged K-Fold cross-validator с embargo.

    Делит временной ряд на n_splits контигуальных фолдов. Для каждого
    фолда как тестовой выборки:
      - Purge: тренировочные образцы с t1 >= test_start удаляются.
      - Embargo: n_embargo образцов сразу после теста удаляются.

    Args:
        n_splits:    Число фолдов (>= 2).
        embargo_pct: Доля от всего датасета для зоны embargo (e.g. 0.01 = 1%).

    Example::

        t1 = labels_df["t1"]            # exit timestamps from triple_barrier_labels
        cv  = PurgedKFold(n_splits=5, embargo_pct=0.01)
        cross_val_score(model, X, y, cv=cv, groups=t1)
    """

    def __init__(self, n_splits: int = 5, embargo_pct: float = 0.01) -> None:
        super().__init__()
        if n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {n_splits}")
        if not 0.0 <= embargo_pct < 0.5:
            raise ValueError(f"embargo_pct must be in [0, 0.5), got {embargo_pct}")
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct

    def get_n_splits(
        self,
        X: object = None,
        y: object = None,
        groups: object = None,
    ) -> int:
        return self.n_splits

    def _iter_test_indices(
        self,
        X: object = None,
        y: object = None,
        groups: object = None,
    ):
        """Required by BaseCrossValidator. Yields test indices (no purging)."""
        n = _n_samples(X)
        idx = np.arange(n)
        fold_sizes = np.full(self.n_splits, n // self.n_splits, dtype=int)
        fold_sizes[: n % self.n_splits] += 1
        current = 0
        for fold_size in fold_sizes:
            yield idx[current : current + fold_size]
            current += fold_size

    def split(
        self,
        X: object,
        y: object = None,
        groups: pd.Series | None = None,
    ):
        """
        Генерирует пары (train_indices, test_indices) с purge и embargo.

        Args:
            X:      DataFrame с DatetimeIndex или ndarray. Длина n.
            y:      Метки (не используются для разбиения).
            groups: pd.Series[entry_ts -> exit_ts] — t1 из triple_barrier_labels().
                    Если None, purging не применяется (обычный KFold по времени).

        Yields:
            (train_indices, test_indices): np.ndarray[int64].

        Raises:
            ValueError: если n_splits > n_samples.
        """
        t1 = groups
        n = _n_samples(X)

        if self.n_splits > n:
            raise ValueError(
                f"n_splits={self.n_splits} > n_samples={n}. "
                "Уменьшите n_splits или увеличьте датасет."
            )

        # Контигуальные фолды по времени
        fold_sizes = np.full(self.n_splits, n // self.n_splits, dtype=int)
        fold_sizes[: n % self.n_splits] += 1

        x_index = getattr(X, "index", None)
        n_embargo = int(np.ceil(self.embargo_pct * n))

        current = 0
        for fold_size in fold_sizes:
            test_start = current
            test_end = current + fold_size
            test_indices = np.arange(test_start, test_end)

            # Embargo: исключить n_embargo образцов сразу после теста
            embargo_end = min(test_end + n_embargo, n)

            train_mask = np.ones(n, dtype=bool)
            train_mask[test_start:embargo_end] = False

            # Purge: тренировочные образцы ДО теста с t1, перекрывающим тест
            if t1 is not None and x_index is not None and test_start > 0:
                test_period_start = x_index[test_start]
                t1_aligned = t1.reindex(x_index)

                # Векторизованный purge по образцам до тестового фолда
                t1_before = t1_aligned.iloc[:test_start]
                overlap = t1_before.notna() & (t1_before >= test_period_start)
                purge_positions = np.where(overlap.values)[0]
                train_mask[purge_positions] = False

            yield np.where(train_mask)[0], test_indices
            current = test_end
