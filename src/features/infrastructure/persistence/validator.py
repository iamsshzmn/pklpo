"""Validation functions for indicator data before insertion."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.logging import get_logger

from ...storage_contract import IndicatorStorageContract

logger = get_logger(__name__)

REQUIRED_FIELDS = IndicatorStorageContract.identity_fields_set()


def validate_dataframe(ind_df: pd.DataFrame | None) -> bool:
    """Validate that DataFrame is not None and not empty."""
    if ind_df is None or len(ind_df) == 0:
        logger.warning("Empty DataFrame provided for insertion")
        return False
    return True


def validate_required_fields(ind_df: pd.DataFrame) -> None:
    """Validate that all required fields are present in DataFrame."""
    missing = [c for c in REQUIRED_FIELDS if c not in ind_df.columns]
    if missing:
        logger.error("Missing required fields: %s", missing)
        logger.error("Available columns: %s", list(ind_df.columns))
        raise ValueError(f"Missing required fields: {missing}")

    logger.info("All required fields present: %s", REQUIRED_FIELDS)


def validate_record_base_keys(record: dict[str, Any], base_keys: list[str]) -> None:
    """Validate that record contains all base keys."""
    missing = [k for k in base_keys if k not in record]
    if missing:
        logger.error("Record missing base keys: %s", missing)
        logger.debug("Record keys: %s", list(record.keys()))
        raise ValueError(f"Record missing base keys: {missing}")


def validate_timestamp(timestamp_ms: Any, row_idx: Any) -> bool:
    """Validate timestamp value."""
    if pd.isna(timestamp_ms):
        logger.warning("Row %s: NaN timestamp, skipping", row_idx)
        return False

    if timestamp_ms < 1000000000000:
        logger.warning(
            "Row %s: Suspicious timestamp %s, skipping", row_idx, timestamp_ms
        )
        return False

    return True
