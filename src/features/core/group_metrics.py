"""
Group Metrics Recorder (SRP: metrics only).

This module handles recording of metrics for indicator calculations
without calculation or persistence concerns. It follows the Single
Responsibility Principle by focusing solely on metrics recording.

Part of Phase 1.2 refactoring: Split GroupCalculator into SRP components.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.logging import LogCategory, get_category_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd


__all__ = ["GroupMetricsRecorder"]

# Columns to exclude from feature calculations (OHLCV + timestamp)
OHLCV_COLUMNS = frozenset({"ts", "timestamp", "open", "high", "low", "close", "volume"})


class GroupMetricsRecorder:
    """
    Metrics recorder for indicator groups (SRP: metrics only).

    This class is responsible solely for recording metrics about
    calculated features. It does not handle calculation or persistence.
    """

    def __init__(
        self,
        fill_rate_recorder: Callable[[str, float], None] | None = None,
    ):
        """Initialize the metrics recorder.

        Args:
            fill_rate_recorder: Callback to record fill rate metrics.
                Injected from application layer to avoid core→observability coupling.
        """
        self._logger = get_category_logger(LogCategory.PERF)
        self._record_fill_rate = fill_rate_recorder or (lambda _name, _rate: None)

    def record_group_metrics(
        self,
        df: pd.DataFrame,
        group_name: str,
        result: dict[str, pd.Series],
    ) -> float:
        """
        Record metrics for a group calculation.

        Args:
            df: Original DataFrame (for context)
            group_name: Name of the group
            result: Calculated features

        Returns:
            Fill rate for the group
        """
        if not result:
            return 0.0

        # Calculate fill rate
        import pandas as pd

        group_df = pd.DataFrame(result)
        fill_rate = group_df.notna().mean().mean()

        # Record to metrics system
        self._record_fill_rate(group_name, fill_rate)

        return fill_rate

    def record_dataframe_metrics(
        self,
        df: pd.DataFrame,
        group_name: str,
    ) -> float:
        """
        Record metrics from a full DataFrame.

        Args:
            df: DataFrame with calculated features
            group_name: Name of the group

        Returns:
            Fill rate for the group features
        """
        # Exclude OHLCV columns from fill rate calculation
        feature_cols = [col for col in df.columns if col not in OHLCV_COLUMNS]

        if not feature_cols:
            return 0.0

        group_df = df[feature_cols]
        fill_rate = group_df.notna().mean().mean()

        # Record to metrics system
        self._record_fill_rate(group_name, fill_rate)

        return fill_rate

    def record_overall_metrics(
        self,
        df: pd.DataFrame,
        failed_groups: list[str] | None = None,
    ) -> dict[str, float]:
        """
        Record overall calculation metrics.

        Args:
            df: DataFrame with all calculated features
            failed_groups: List of groups that failed

        Returns:
            Dictionary with overall metrics
        """
        # Exclude OHLCV columns
        feature_cols = [col for col in df.columns if col not in OHLCV_COLUMNS]

        metrics = {
            "total_features": len(feature_cols),
            "total_rows": len(df),
        }

        if feature_cols:
            feature_df = df[feature_cols]
            metrics["overall_fill_rate"] = feature_df.notna().mean().mean()
            metrics["features_with_data"] = (feature_df.notna().any()).sum()
        else:
            metrics["overall_fill_rate"] = 0.0
            metrics["features_with_data"] = 0

        if failed_groups:
            metrics["failed_groups"] = len(failed_groups)

        return metrics
