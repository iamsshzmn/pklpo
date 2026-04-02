"""
Debug utilities for feature calculation.

This module provides helper functions for debug logging and mode checking.
"""

import os

import pandas as pd

from src.logging import get_features_logger

logger = get_features_logger(__name__)


def _is_debug_mode(debug: bool | None = None) -> bool:
    """Check if debug mode is enabled explicitly or via environment variable."""
    if debug is not None:
        return debug
    return os.getenv("FEATURES_DEBUG", "false").lower() == "true"


def _debug_log_dataframe_info(
    df: pd.DataFrame,
    label: str,
    *,
    debug: bool | None = None,
) -> None:
    """
    Log detailed DataFrame information for debugging.

    Args:
        df: DataFrame to log information about
        label: Label for the log entry
    """
    if not _is_debug_mode(debug):
        return

    logger.debug(f"{label}: shape={df.shape}, columns={list(df.columns)}")
    logger.debug(f"{label}: dtypes={df.dtypes.to_dict()}")
    logger.debug(
        f"{label}: memory_usage={df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
    )
