"""
Purged K-Fold Cross-Validation with Embargo (AFML Ch.7).

Prevents look-ahead bias via two mechanisms:

1. **Purging**: removes training samples whose label-span (t1) overlaps
   with the test period. These samples "know the future" of the test period.

2. **Embargo**: removes n_embargo training samples immediately after the
   test set. They may be correlated with the test period through serial
   correlation or look-ahead in the data.

scikit-learn compatibility:
    PurgedKFold inherits BaseCrossValidator and can be passed to
    cross_val_score, cross_validate, GridSearchCV, etc.

    The t1 parameter is passed via the groups argument:
        cross_val_score(model, X, y, cv=PurgedKFold(n_splits=5), groups=t1)

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.7
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from sklearn.model_selection import BaseCrossValidator

if TYPE_CHECKING:
    import pandas as pd


def _n_samples(X: Any) -> int:
    """Number of samples for a DataFrame, ndarray, or any __len__ object."""
    if hasattr(X, "shape"):
        return int(X.shape[0])
    return len(X)


class PurgedKFold(BaseCrossValidator):
    """
    Purged K-Fold cross-validator with embargo.

    Splits a time series into n_splits contiguous folds. For each fold
    as the test set:
      - Purge: training samples with t1 >= test_start are removed.
      - Embargo: n_embargo samples immediately after the test are removed.

    Args:
        n_splits:    Number of folds (>= 2).
        embargo_pct: Fraction of the entire dataset for the embargo zone (e.g. 0.01 = 1%).

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
        Generates (train_indices, test_indices) pairs with purge and embargo.

        Args:
            X:      DataFrame with DatetimeIndex or ndarray. Length n.
            y:      Labels (not used for splitting).
            groups: pd.Series[entry_ts -> exit_ts] — t1 from triple_barrier_labels().
                    If None, purging is not applied (regular time-based KFold).

        Yields:
            (train_indices, test_indices): np.ndarray[int64].

        Raises:
            ValueError: if n_splits > n_samples.
        """
        t1 = groups
        n = _n_samples(X)

        if self.n_splits > n:
            raise ValueError(
                f"n_splits={self.n_splits} > n_samples={n}. "
                "Reduce n_splits or increase the dataset size."
            )

        # Contiguous time-based folds
        fold_sizes = np.full(self.n_splits, n // self.n_splits, dtype=int)
        fold_sizes[: n % self.n_splits] += 1

        x_index = getattr(X, "index", None)
        n_embargo = int(np.ceil(self.embargo_pct * n))

        current = 0
        for fold_size in fold_sizes:
            test_start = current
            test_end = current + fold_size
            test_indices = np.arange(test_start, test_end)

            # Embargo: exclude n_embargo samples immediately after the test
            embargo_end = min(test_end + n_embargo, n)

            train_mask = np.ones(n, dtype=bool)
            train_mask[test_start:embargo_end] = False

            # Purge: training samples BEFORE the test with t1 overlapping the test
            if t1 is not None and x_index is not None and test_start > 0:
                test_period_start = x_index[test_start]
                t1_aligned = t1.reindex(x_index)

                # Vectorized purge over samples before the test fold
                t1_before = t1_aligned.iloc[:test_start]
                overlap = t1_before.notna() & (t1_before >= test_period_start)
                purge_positions = np.where(overlap.values)[0]
                train_mask[purge_positions] = False

            yield np.where(train_mask)[0], test_indices
            current = test_end
