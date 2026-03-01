"""
Debug utilities for indicator group modules.

Provides reusable logging functions for debugging feature calculations.
"""

import os

import pandas as pd

from src.logging import get_logger

logger = get_logger(__name__)


def is_debug_enabled() -> bool:
    """Check if debug mode is enabled."""
    return os.getenv("FEATURES_DEBUG", "false").lower() == "true"


def log_group_start(group_name: str, df: pd.DataFrame, available: set):
    """
    Log the start of a group calculation with input statistics.

    Args:
        group_name: Name of the indicator group
        df: Input DataFrame
        available: Set of requested indicators
    """
    if not is_debug_enabled():
        return

    logger.debug(f"[{group_name}] Starting calculation")
    logger.debug(f"[{group_name}] Input shape: {df.shape}")
    logger.debug(f"[{group_name}] Input columns: {list(df.columns)}")
    logger.debug(f"[{group_name}] Requested indicators: {sorted(available)}")

    # Log input data quality
    if not df.empty:
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                non_null = df[col].notna().sum()
                total = len(df[col])
                pct = (non_null / total * 100) if total > 0 else 0
                logger.debug(
                    f"[{group_name}] Input.{col}: {non_null}/{total} ({pct:.1f}%)"
                )


def log_group_results(group_name: str, result: dict[str, pd.Series]):
    """
    Log the results of a group calculation.

    Args:
        group_name: Name of the indicator group
        result: Dictionary of calculated indicators
    """
    if not is_debug_enabled():
        return

    logger.debug(f"[{group_name}] Completed: {len(result)} indicators calculated")

    # Log each indicator's quality
    for name, series in result.items():
        if isinstance(series, pd.Series):
            non_null = series.notna().sum()
            total = len(series)
            pct = (non_null / total * 100) if total > 0 else 0

            # Calculate NaN percentage
            nan_pct = series.isna().mean() * 100

            logger.debug(
                f"[{group_name}] {name}: {non_null}/{total} ({pct:.1f}%), NaN: {nan_pct:.1f}%"
            )

            # Sample values (first 3 non-null)
            sample = series.dropna().head(3).tolist() if non_null > 0 else []
            if sample:
                logger.debug(f"[{group_name}] {name} sample: {sample}")
        else:
            logger.debug(f"[{group_name}] {name}: unexpected type {type(series)}")


def log_indicator_calculation(
    group_name: str, indicator_name: str, success: bool, error: str | None = None
):
    """
    Log individual indicator calculation result.

    Args:
        group_name: Name of the indicator group
        indicator_name: Name of the specific indicator
        success: Whether calculation succeeded
        error: Error message if failed
    """
    if not is_debug_enabled():
        return

    if success:
        logger.debug(f"[{group_name}] ✓ {indicator_name} calculated successfully")
    else:
        logger.debug(f"[{group_name}] ✗ {indicator_name} failed: {error}")


def log_dataframe_stats(df: pd.DataFrame, label: str):
    """
    Log detailed DataFrame statistics.

    Args:
        df: DataFrame to analyze
        label: Label for the log messages
    """
    if not is_debug_enabled():
        return

    logger.debug(f"[{label}] Shape: {df.shape}")
    logger.debug(f"[{label}] Columns: {list(df.columns)}")

    if not df.empty:
        # Overall NaN percentage
        nan_pct = df.isna().mean().mean() * 100
        logger.debug(f"[{label}] Overall NaN%: {nan_pct:.2f}%")

        # Memory usage
        memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
        logger.debug(f"[{label}] Memory: {memory_mb:.2f} MB")
