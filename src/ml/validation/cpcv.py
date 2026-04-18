"""
Combinatorial Purged Cross-Validation (CPCV) (AFML Ch.12).

Generalizes PurgedKFold: instead of a single test fold, n_test_groups
out of n_groups contiguous groups are selected simultaneously. This yields
C(n_groups, n_test_groups) unique paths (train/test splits), enabling
construction of a metric distribution (e.g., Sharpe) to assess strategy robustness.

Hard limit ``max_paths``:
    A ValueError is raised if C(n_groups, n_test_groups) > max_paths.
    This prevents exponential growth in execution time.
    Recommended values: n_groups=6, n_test_groups=2 -> C(6,2) = 15 paths.

Usage::

    cv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2)
    for train_idx, test_idx in cv.split(X, y, groups=t1):
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        score = model.score(X.iloc[test_idx], y.iloc[test_idx])

    # Or to collect a metric distribution:
    metrics_df = cv.get_path_metrics(model, X, y, scoring="accuracy")
    var_sr = metrics_df["score"].var()  # for DSR

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.12
"""

from __future__ import annotations

from itertools import combinations
from math import comb
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.metrics import check_scoring
from sklearn.model_selection import BaseCrossValidator

from src.ml.validation.purged_kfold import _n_samples

if TYPE_CHECKING:
    from collections.abc import Callable


class CombinatorialPurgedCV(BaseCrossValidator):
    """
    Combinatorial Purged Cross-Validation with embargo.

    Args:
        n_groups:      Number of contiguous groups (recommended: 6).
        n_test_groups: Number of groups selected as test in each path (recommended: 2).
        embargo_pct:   Fraction of the dataset for the embargo zone after each test segment.
        max_paths:     Hard limit on the number of paths C(n_groups, n_test_groups).
                       ValueError if exceeded. Default is 50.

    Raises:
        ValueError: at initialization if n_test_groups >= n_groups, or
                    at split() if C(n_groups, n_test_groups) > max_paths.
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
        """Number of paths C(n_groups, n_test_groups)."""
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
        Generates (train_indices, test_indices) pairs for each combination.

        Args:
            X:      DataFrame with DatetimeIndex or ndarray. Length n.
            y:      Labels (not used for splitting).
            groups: pd.Series[entry_ts -> exit_ts] — t1 from triple_barrier_labels().
                    If None, purging is not applied.

        Yields:
            (train_indices, test_indices): np.ndarray[int64].

        Raises:
            ValueError: if n_paths > max_paths.
        """
        n_paths = self.n_paths
        if n_paths > self.max_paths:
            raise ValueError(
                f"C({self.n_groups}, {self.n_test_groups}) = {n_paths} > "
                f"max_paths={self.max_paths}. "
                f"Reduce n_groups or n_test_groups."
            )

        t1 = groups
        n = _n_samples(X)
        idx = np.arange(n)
        x_index = getattr(X, "index", None)
        n_embargo = int(np.ceil(self.embargo_pct * n))

        group_indices = np.array_split(idx, self.n_groups)

        for test_gids in combinations(range(self.n_groups), self.n_test_groups):
            # Test indices: union of selected groups
            test_indices = np.sort(
                np.concatenate([group_indices[gid] for gid in test_gids])
            )

            # train_mask: initially all True
            train_mask = np.ones(n, dtype=bool)
            train_mask[test_indices] = False

            # Embargo + Purge for each test segment
            for gid in test_gids:
                g_idx = group_indices[gid]
                g_end = int(g_idx[-1]) + 1

                # Embargo: remove n_embargo samples after the end of the test group
                embargo_end = min(g_end + n_embargo, n)
                train_mask[g_end:embargo_end] = False

                # Purge: training samples BEFORE this group with t1 >= group start
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
        Trains and evaluates the estimator on each CPCV path.

        Args:
            estimator: Trained or untrained sklearn-compatible estimator.
                       Cloned for each path via sklearn.base.clone.
            X:         Feature matrix.
            y:         Target variable.
            scoring:   String ("accuracy", "roc_auc", ...) or callable scorer.
            groups:    t1 Series for purging (see split()).

        Returns:
            DataFrame with columns:
              path_id  — sequential path number (0-based).
              score    — metric value on the test set for the path.
              n_train  — training set size.
              n_test   — test set size.

        Raises:
            ValueError: if the number of paths exceeds max_paths (delegated to split()).
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
