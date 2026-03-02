"""
Name normalization for batch records before DB insertion.
"""

from __future__ import annotations

from typing import Any

from src.logging import get_logger

from ...schema.name_aliases import NAME_ALIASES

logger = get_logger(__name__)


def normalize_record_names(
    batch_data: list[dict[str, Any]], db_cols: set[str]
) -> list[dict[str, Any]]:
    """
    Normalize record field names using central alias mapping.
    """
    pk = {"symbol", "timeframe", "timestamp"}
    filtered_batch: list[dict[str, Any]] = []

    for record in batch_data:
        normalized_record: dict[str, Any] = {}
        for key, value in record.items():
            normalized_key = NAME_ALIASES.get(key, key)
            if normalized_key in db_cols or normalized_key in pk:
                normalized_record[normalized_key] = value
            else:
                logger.debug(
                    "Filtering out field '%s' -> '%s' (not in DB schema)",
                    key,
                    normalized_key,
                )
        filtered_batch.append(normalized_record)

    if not filtered_batch:
        logger.error("No valid fields after normalization")
        raise ValueError("No valid fields after schema filtering")

    safe_batch_data = []
    for record in filtered_batch:
        safe_record = {k: v for k, v in record.items() if k in db_cols}
        safe_batch_data.append(safe_record)

    if not safe_batch_data:
        logger.error("No safe data after filtering")
        raise ValueError("No safe data for insertion")

    return safe_batch_data
