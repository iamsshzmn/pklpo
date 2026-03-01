"""
Validation functions for indicator data before insertion.
"""

from typing import Any

import pandas as pd

from src.logging import get_logger

logger = get_logger(__name__)

# Константы
REQUIRED_FIELDS = {"timestamp", "symbol", "timeframe"}


def validate_dataframe(ind_df: pd.DataFrame | None) -> bool:
    """
    Validate that DataFrame is not None and not empty.

    Args:
        ind_df: DataFrame to validate

    Returns:
        True if DataFrame is valid, False otherwise
    """
    if ind_df is None or len(ind_df) == 0:
        logger.warning("Empty DataFrame provided for insertion")
        return False
    return True


def validate_required_fields(ind_df: pd.DataFrame) -> None:
    """
    Validate that all required fields are present in DataFrame.

    Args:
        ind_df: DataFrame to validate

    Raises:
        ValueError: If required fields are missing
    """
    missing = [c for c in REQUIRED_FIELDS if c not in ind_df.columns]
    if missing:
        logger.error(f"Missing required fields: {missing}")
        logger.error(f"Available columns: {list(ind_df.columns)}")
        raise ValueError(f"Missing required fields: {missing}")

    logger.info(f"✅ All required fields present: {REQUIRED_FIELDS}")


def validate_record_base_keys(record: dict[str, Any], base_keys: list[str]) -> None:
    """
    Validate that record contains all base keys.

    Args:
        record: Record to validate
        base_keys: List of required base keys

    Raises:
        ValueError: If base keys are missing
    """
    missing = [k for k in base_keys if k not in record]
    if missing:
        logger.error(f"Record missing base keys: {missing}")
        logger.debug(f"Record keys: {list(record.keys())}")
        raise ValueError(f"Record missing base keys: {missing}")


def validate_timestamp(timestamp_ms: Any, row_idx: Any) -> bool:
    """
    Validate timestamp value.

    Args:
        timestamp_ms: Timestamp value to validate
        row_idx: Row index for logging

    Returns:
        True if timestamp is valid, False otherwise
    """
    import pandas as pd

    if pd.isna(timestamp_ms):
        logger.warning(f"Row {row_idx}: NaN timestamp, skipping")
        return False

    # Дополнительная проверка: timestamp должен быть разумным
    if timestamp_ms < 1000000000000:  # Меньше 2001 года - подозрительно
        logger.warning(f"Row {row_idx}: Suspicious timestamp {timestamp_ms}, skipping")
        return False

    return True
