"""
Look-Ahead Bias Detector (AFML quality gate).

Detects look-ahead bias in a pipeline using a deterministic test:

Algorithm:
  1. Run pipeline on the full dataset df_full -> result_A.
  2. Run pipeline on the trimmed dataset df_full.iloc[:-n_trim] -> result_B.
  3. Find the intersection of timestamps.
  4. Compare results on shared timestamps — they must match within atol.

If the results differ: the pipeline uses future data (look-ahead bias).

Usage in CI:
  - Mark tests with @pytest.mark.lookahead
  - Add a ``pytest -m lookahead`` step as a mandatory gate before deployment

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.7, 12
           (discussion of the need for look-ahead checks in production systems)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class LookaheadResult:
    """
    Result of a look-ahead bias check.

    Attributes:
        passed:    True if the pipeline has no look-ahead bias.
        max_diff:  Maximum absolute difference between result_A and result_B
                   on shared timestamps. 0.0 if they match exactly.
        n_compared: Number of timestamps used for comparison.
        details:   Dictionary with additional diagnostics.
    """

    passed: bool
    max_diff: float
    n_compared: int
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"LookaheadResult({status}, "
            f"max_diff={self.max_diff:.2e}, "
            f"n_compared={self.n_compared})"
        )


def check_lookahead(
    pipeline_fn: Callable[[pd.DataFrame], pd.Series | pd.DataFrame],
    df_full: pd.DataFrame,
    n_trim: int = 100,
    atol: float = 1e-6,
) -> LookaheadResult:
    """
    Checks the pipeline for the absence of look-ahead bias.

    Runs the pipeline twice — on full and trimmed data — and compares
    results on shared timestamps.

    Args:
        pipeline_fn: Callable[[df], result] — pipeline to check.
                     Accepts pd.DataFrame (OHLCV or features),
                     returns pd.Series or pd.DataFrame with DatetimeIndex.
        df_full:     Full dataset. Must have a DatetimeIndex.
        n_trim:      Number of rows trimmed from the end in the second run.
                     Must be < len(df_full).
        atol:        Absolute tolerance for numerical comparison.

    Returns:
        LookaheadResult with passed=True if no bias is detected.

    Raises:
        ValueError: if n_trim >= len(df_full) or < 1.
        ValueError: if pipeline_fn returns an object without DatetimeIndex.

    Example::

        def my_pipeline(df: pd.DataFrame) -> pd.Series:
            return df["close"].rolling(20).mean()

        result = check_lookahead(my_pipeline, df_ohlcv, n_trim=50)
        assert result.passed, str(result)
    """
    n = len(df_full)
    if not 1 <= n_trim < n:
        raise ValueError(
            f"n_trim={n_trim} must be in [1, {n - 1}] (len(df_full)={n})."
        )

    # Step 1: run on full data
    result_a: pd.Series | pd.DataFrame = pipeline_fn(df_full)

    # Step 2: run on trimmed data
    df_trimmed = df_full.iloc[:-n_trim]
    result_b: pd.Series | pd.DataFrame = pipeline_fn(df_trimmed)

    # Type check
    if not isinstance(result_a.index, pd.DatetimeIndex):
        raise ValueError(
            "pipeline_fn must return an object with pd.DatetimeIndex. "
            f"Got: {type(result_a.index).__name__}"
        )

    # Step 3: intersection of timestamps
    common_idx = result_a.index.intersection(result_b.index)
    n_compared = len(common_idx)

    if n_compared == 0:
        return LookaheadResult(
            passed=False,
            max_diff=float("inf"),
            n_compared=0,
            details={"reason": "No shared timestamps for comparison."},
        )

    # Step 4: compare on shared timestamps
    a_aligned = result_a.loc[common_idx]
    b_aligned = result_b.loc[common_idx]

    max_diff = _compute_max_diff(a_aligned, b_aligned)
    passed = max_diff <= atol

    details: dict[str, Any] = {
        "n_full": n,
        "n_trimmed": n - n_trim,
        "n_common": n_compared,
        "atol": atol,
    }
    if not passed:
        details["max_diff_location"] = _find_diff_location(a_aligned, b_aligned, atol)

    return LookaheadResult(
        passed=passed,
        max_diff=max_diff,
        n_compared=n_compared,
        details=details,
    )


def _compute_max_diff(
    a: pd.Series | pd.DataFrame,
    b: pd.Series | pd.DataFrame,
) -> float:
    """
    Computes the maximum absolute difference between a and b.

    NaN rules:
      - Both NaN -> difference = 0 (both "unknown" — agreement).
      - One NaN, the other not -> difference = inf (complete disagreement;
        the pipeline on full data obtained a value where the pipeline
        on trimmed data could not — a sign of look-ahead).
    """
    if isinstance(a, pd.Series):
        a_vals = a.to_numpy(dtype=float, na_value=np.nan)
        b_vals = b.to_numpy(dtype=float, na_value=np.nan)
        diff = np.abs(a_vals - b_vals)
        # Both NaN -> not a difference
        both_nan = np.isnan(a_vals) & np.isnan(b_vals)
        diff[both_nan] = 0.0
        # Exactly one NaN -> complete difference (inf)
        one_nan = np.isnan(a_vals) ^ np.isnan(b_vals)
        diff[one_nan] = np.inf
        if len(diff) == 0:
            return 0.0
        finite_max = float(np.nanmax(np.where(np.isinf(diff), np.nan, diff)))
        return float("inf") if np.any(one_nan) else finite_max
    # DataFrame: check numeric columns
    a_df = a.select_dtypes(include=[np.number])
    b_df = b.select_dtypes(include=[np.number])
    if a_df.empty:
        return 0.0
    diff = (a_df - b_df).abs()
    return float(diff.max().max())


def _find_diff_location(
    a: pd.Series | pd.DataFrame,
    b: pd.Series | pd.DataFrame,
    atol: float,
) -> dict[str, Any]:
    """Returns the first timestamp with a difference > atol."""
    if isinstance(a, pd.Series):
        a_vals = a.to_numpy(dtype=float, na_value=np.nan)
        b_vals = b.to_numpy(dtype=float, na_value=np.nan)
        diff = np.abs(a_vals - b_vals)
        diff = np.nan_to_num(diff, nan=0.0)
        where_bad = np.where(diff > atol)[0]
        if len(where_bad) > 0:
            idx = where_bad[0]
            ts = a.index[idx]
            return {
                "first_diff_ts": str(ts),
                "a_value": float(a_vals[idx]),
                "b_value": float(b_vals[idx]),
                "diff": float(diff[idx]),
            }
    return {}
