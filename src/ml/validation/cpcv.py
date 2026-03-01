"""
Combinatorial Purged Cross-Validation (CPCV) (AFML Ch.12).

Обобщает PurgedKFold: вместо одного тестового фолда одновременно выбирается
n_test_groups из n_groups контигуальных групп. Это даёт C(n_groups, n_test_groups)
уникальных путей (train/test splits), что позволяет строить распределение метрик
(например, Sharpe) для оценки устойчивости стратегии.

Hard limit ``max_paths``:
    При C(n_groups, n_test_groups) > max_paths генерируется ValueError.
    Это предотвращает экспоненциальный рост времени выполнения.
    Рекомендуемые значения: n_groups=6, n_test_groups=2 → C(6,2) = 15 путей.

Использование::

    cv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2)
    for train_idx, test_idx in cv.split(X, y, groups=t1):
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        score = model.score(X.iloc[test_idx], y.iloc[test_idx])

    # Или для сбора распределения метрик:
    metrics_df = cv.get_path_metrics(model, X, y, scoring="accuracy")
    var_sr = metrics_df["score"].var()  # для DSR

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.12
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from math import comb
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.metrics import check_scoring
from sklearn.model_selection import BaseCrossValidator

from src.ml.validation.purged_kfold import _n_samples


class CombinatorialPurgedCV(BaseCrossValidator):
    """
    Combinatorial Purged Cross-Validation с embargo.

    Args:
        n_groups:      Число контигуальных групп (рекомендуется 6).
        n_test_groups: Число групп, выбираемых как тест в каждом пути (рекомендуется 2).
        embargo_pct:   Доля датасета для зоны embargo после каждого тестового сегмента.
        max_paths:     Hard limit на число путей C(n_groups, n_test_groups).
                       ValueError если превышен. По умолчанию 50.

    Raises:
        ValueError: при инициализации если n_test_groups >= n_groups или
                    при split() если C(n_groups, n_test_groups) > max_paths.
    """

    def __init__(
        self,
        n_groups: int = 6,
        n_test_groups: int = 2,
        embargo_pct: float = 0.01,
        max_paths: int = 50,
    ) -> None:
        super().__init__()
        if n_test_groups >= n_groups:
            raise ValueError(
                f"n_test_groups={n_test_groups} must be < n_groups={n_groups}"
            )
        if not 0.0 <= embargo_pct < 0.5:
            raise ValueError(f"embargo_pct must be in [0, 0.5), got {embargo_pct}")
        if max_paths < 1:
            raise ValueError(f"max_paths must be >= 1, got {max_paths}")
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.embargo_pct = embargo_pct
        self.max_paths = max_paths

    @property
    def n_paths(self) -> int:
        """Число путей C(n_groups, n_test_groups)."""
        return comb(self.n_groups, self.n_test_groups)

    def get_n_splits(
        self,
        X: object = None,
        y: object = None,
        groups: object = None,
    ) -> int:
        return self.n_paths

    def _iter_test_indices(
        self,
        X: object = None,
        y: object = None,
        groups: object = None,
    ):
        """Required by BaseCrossValidator. Yields test indices (no purging)."""
        n = _n_samples(X)
        group_indices = np.array_split(np.arange(n), self.n_groups)
        for test_gids in combinations(range(self.n_groups), self.n_test_groups):
            yield np.concatenate([group_indices[i] for i in test_gids])

    def split(
        self,
        X: object,
        y: object = None,
        groups: pd.Series | None = None,
    ):
        """
        Генерирует пары (train_indices, test_indices) для каждой комбинации.

        Args:
            X:      DataFrame с DatetimeIndex или ndarray. Длина n.
            y:      Метки (не используются для разбиения).
            groups: pd.Series[entry_ts -> exit_ts] — t1 из triple_barrier_labels().
                    Если None, purging не применяется.

        Yields:
            (train_indices, test_indices): np.ndarray[int64].

        Raises:
            ValueError: если n_paths > max_paths.
        """
        n_paths = self.n_paths
        if n_paths > self.max_paths:
            raise ValueError(
                f"C({self.n_groups}, {self.n_test_groups}) = {n_paths} > "
                f"max_paths={self.max_paths}. "
                f"Уменьшите n_groups или n_test_groups."
            )

        t1 = groups
        n = _n_samples(X)
        idx = np.arange(n)
        x_index = getattr(X, "index", None)
        n_embargo = int(np.ceil(self.embargo_pct * n))

        group_indices = np.array_split(idx, self.n_groups)

        for test_gids in combinations(range(self.n_groups), self.n_test_groups):
            # Тестовые индексы: объединение выбранных групп
            test_indices = np.sort(
                np.concatenate([group_indices[gid] for gid in test_gids])
            )

            # train_mask: изначально всё True
            train_mask = np.ones(n, dtype=bool)
            train_mask[test_indices] = False

            # Embargo + Purge для каждого тестового сегмента
            for gid in test_gids:
                g_idx = group_indices[gid]
                g_end = int(g_idx[-1]) + 1

                # Embargo: убрать n_embargo образцов после конца тестовой группы
                embargo_end = min(g_end + n_embargo, n)
                train_mask[g_end:embargo_end] = False

                # Purge: тренировочные образцы ДО этой группы с t1 >= начало группы
                if t1 is not None and x_index is not None:
                    g_start = int(g_idx[0])
                    if g_start > 0:
                        test_period_start = x_index[g_start]
                        t1_aligned = t1.reindex(x_index)
                        t1_before = t1_aligned.iloc[:g_start]
                        overlap = t1_before.notna() & (t1_before >= test_period_start)
                        purge_positions = np.where(overlap.values)[0]
                        train_mask[purge_positions] = False

            yield idx[train_mask], test_indices

    def get_path_metrics(
        self,
        estimator: BaseEstimator,
        X: pd.DataFrame,
        y: pd.Series,
        scoring: str | Callable[..., Any] = "accuracy",
        groups: pd.Series | None = None,
    ) -> pd.DataFrame:
        """
        Обучает и оценивает estimator на каждом CPCV-пути.

        Args:
            estimator: Обученный или не обученный sklearn-совместимый estimator.
                       Клонируется для каждого пути через sklearn.base.clone.
            X:         Матрица признаков.
            y:         Целевая переменная.
            scoring:   Строка ("accuracy", "roc_auc", ...) или callable scorer.
            groups:    t1 Series для purging (см. split()).

        Returns:
            DataFrame с колонками:
              path_id  — порядковый номер пути (0-based).
              score    — значение метрики на тестовой выборке пути.
              n_train  — размер тренировочной выборки.
              n_test   — размер тестовой выборки.

        Raises:
            ValueError: если число путей превышает max_paths (делегируется в split()).
        """
        scorer = check_scoring(estimator, scoring=scoring)
        records = []

        for path_id, (train_idx, test_idx) in enumerate(
            self.split(X, y, groups=groups)
        ):
            est = clone(estimator)
            X_train = X.iloc[train_idx] if hasattr(X, "iloc") else X[train_idx]
            y_train = y.iloc[train_idx] if hasattr(y, "iloc") else y[train_idx]
            X_test = X.iloc[test_idx] if hasattr(X, "iloc") else X[test_idx]
            y_test = y.iloc[test_idx] if hasattr(y, "iloc") else y[test_idx]

            est.fit(X_train, y_train)
            score = scorer(est, X_test, y_test)

            records.append(
                {
                    "path_id": path_id,
                    "score": float(score),
                    "n_train": len(train_idx),
                    "n_test": len(test_idx),
                }
            )

        return pd.DataFrame(records)
