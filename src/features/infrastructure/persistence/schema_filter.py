"""
Schema filtering helpers for prepared batch records.
"""

from __future__ import annotations

from typing import Any

from src.logging import get_logger

logger = get_logger(__name__)


def filter_batch_by_schema(
    batch_data: list[dict[str, Any]], db_cols: set[str], base_keys: list[str]
) -> list[dict[str, Any]]:
    """
    Filter batch data to match database schema.

    Base key validation is performed once on the first record.
    """
    from .validator import validate_record_base_keys

    if not batch_data:
        return []

    first_input_record = batch_data[0]
    try:
        validate_record_base_keys(first_input_record, base_keys)
    except ValueError:
        logger.warning("First record missing base keys, returning empty batch")
        logger.debug("First record keys: %s", list(first_input_record.keys()))
        return []

    total_fields = 0
    filtered_fields = 0
    safe_batch_data: list[dict[str, Any]] = []

    for record in batch_data:
        total_fields += len(record)
        safe_record = {k: v for k, v in record.items() if k in db_cols}
        filtered_fields += len(record) - len(safe_record)
        safe_batch_data.append(safe_record)

    if filtered_fields > 0:
        logger.info(
            "Filtered out %d fields from %d total fields (not in DB schema)",
            filtered_fields,
            total_fields,
        )

    first_record = safe_batch_data[0]
    missing_after_filter = [k for k in base_keys if k not in first_record]
    if missing_after_filter:
        logger.error("Base keys missing after filtering: %s", missing_after_filter)
        logger.error("Available keys after filtering: %s", list(first_record.keys()))
        raise ValueError(f"Base keys missing after filtering: {missing_after_filter}")

    logger.info(
        "All %d records passed schema filter with required base keys: %s",
        len(safe_batch_data),
        base_keys,
    )
    return safe_batch_data
