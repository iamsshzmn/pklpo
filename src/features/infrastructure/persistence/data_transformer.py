"""
Data transformation utilities for indicator persistence.

This module handles type conversions and data normalization before UPSERT:
- Timestamp conversion to int64
- Numeric value normalization (str -> float, numpy -> python)
- Record filtering by schema

Extracted from inserter.py (Stage 2 refactoring).
"""

from typing import Any

import numpy as np

from src.logging import get_logger

logger = get_logger(__name__)


def convert_timestamps_to_int64(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert timestamp field to int64 for all records.

    PostgreSQL BIGINT requires int64, not float or numpy types.

    Args:
        records: List of record dictionaries

    Returns:
        Records with converted timestamps

    Raises:
        ValueError: If timestamp cannot be converted
    """
    for i, record in enumerate(records):
        if "timestamp" not in record or record["timestamp"] is None:
            continue

        ts_value = record["timestamp"]
        try:
            if isinstance(ts_value, int | np.integer | float):
                record["timestamp"] = int(ts_value)
            else:
                record["timestamp"] = int(float(ts_value))
        except (ValueError, TypeError, OverflowError) as e:
            raise ValueError(
                f"Row {i}: Invalid timestamp value: {ts_value}"
            ) from e

    return records


def normalize_numeric_values(
    records: list[dict[str, Any]],
    numeric_columns: set[str],
) -> list[dict[str, Any]]:
    """
    Normalize numeric values for database insertion.

    Handles:
    - String to float conversion
    - Numpy types to Python types
    - Invalid values to None

    Args:
        records: List of record dictionaries
        numeric_columns: Set of column names that should be numeric

    Returns:
        Records with normalized numeric values
    """
    for record in records:
        for key in numeric_columns:
            if key not in record:
                continue

            value = record[key]
            if value is None:
                continue

            # String -> float
            if isinstance(value, str):
                try:
                    record[key] = float(value)
                except (ValueError, TypeError):
                    record[key] = None
                continue

            # Numpy types -> Python float
            if isinstance(value, np.number):
                record[key] = float(value)
                continue

            # Other non-numeric types -> try conversion or None
            if not isinstance(value, int | float):
                try:
                    record[key] = float(value)
                except (ValueError, TypeError):
                    record[key] = None

    return records


def filter_records_by_schema(
    records: list[dict[str, Any]],
    db_columns: set[str],
) -> list[dict[str, Any]]:
    """
    Filter record fields to only include columns present in DB schema.

    Args:
        records: List of record dictionaries
        db_columns: Set of column names in the database

    Returns:
        Records with only valid columns
    """
    if not records:
        return records

    # Log filtered columns once
    first_record_keys = set(records[0].keys())
    filtered_out = first_record_keys - db_columns
    if filtered_out:
        logger.debug(
            f"Filtering out {len(filtered_out)} columns not in DB: "
            f"{sorted(filtered_out)[:5]}{'...' if len(filtered_out) > 5 else ''}"
        )

    return [
        {k: v for k, v in record.items() if k in db_columns}
        for record in records
    ]


def validate_pk_fields(
    records: list[dict[str, Any]],
    pk_fields: tuple[str, ...] = ("symbol", "timeframe", "timestamp"),
) -> None:
    """
    Validate that all primary key fields are present and non-null.

    Args:
        records: List of record dictionaries
        pk_fields: Tuple of primary key field names

    Raises:
        ValueError: If any PK field is missing or null
    """
    for i, record in enumerate(records):
        for pk_field in pk_fields:
            if pk_field not in record or record[pk_field] is None:
                raise ValueError(
                    f"Row {i}: PK field '{pk_field}' is missing or NULL"
                )


def validate_service_fields(
    records: list[dict[str, Any]],
    service_fields: tuple[str, ...] = ("calculated_at", "created_at", "updated_at"),
) -> None:
    """
    Validate that service fields have correct types (not strings).

    Args:
        records: List of record dictionaries
        service_fields: Tuple of service field names

    Raises:
        TypeError: If service field has wrong type
    """
    for i, record in enumerate(records):
        for field in service_fields:
            if field in record and record[field] is not None:
                if isinstance(record[field], str):
                    raise TypeError(
                        f"Row {i}: Service field '{field}' is str, expected datetime or None"
                    )


def get_numeric_columns_from_table(indicators_table) -> set[str]:
    """
    Extract numeric column names from SQLAlchemy table.

    Args:
        indicators_table: Reflected SQLAlchemy table

    Returns:
        Set of numeric column names
    """
    numeric_types = (
        "NUMERIC", "DOUBLE PRECISION", "REAL", "FLOAT", "INTEGER", "BIGINT"
    )

    numeric_cols = set()
    for col in indicators_table.columns:
        try:
            python_type = col.type.python_type
            if python_type in (int, float):
                numeric_cols.add(col.name)
                continue
        except (AttributeError, NotImplementedError):
            pass

        col_type_str = str(col.type).upper()
        if any(t in col_type_str for t in numeric_types):
            numeric_cols.add(col.name)

    return numeric_cols


def transform_records_for_upsert(
    records: list[dict[str, Any]],
    db_columns: set[str],
    numeric_columns: set[str],
) -> list[dict[str, Any]]:
    """
    Complete transformation pipeline for UPSERT.

    Applies all transformations in correct order:
    1. Filter by schema
    2. Convert timestamps
    3. Normalize numeric values
    4. Validate PK fields
    5. Validate service fields

    Args:
        records: List of record dictionaries
        db_columns: Set of column names in the database
        numeric_columns: Set of numeric column names

    Returns:
        Transformed and validated records

    Raises:
        ValueError: If validation fails
    """
    if not records:
        return records

    # 1. Filter by schema
    records = filter_records_by_schema(records, db_columns)

    # 2. Convert timestamps
    records = convert_timestamps_to_int64(records)

    # 3. Normalize numeric values
    records = normalize_numeric_values(records, numeric_columns)

    # 4. Validate PK fields
    validate_pk_fields(records)

    # 5. Validate service fields
    validate_service_fields(records)

    return records
