"""
UPSERT Builder Module

   SQLAlchemy UPSERT      .
        .
"""

import math
import os
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.observability.prometheus import get_metrics as get_prom_metrics
from src.features.storage_contract import IndicatorStorageContract
from src.logging import (
    LogAggregator,
    LogCategory,
    Verbosity,
    get_category_logger,
    should_log,
)

logger = get_category_logger(LogCategory.INSERT)

#
DEFAULT_MIN_BATCH_SIZE = 5
DEFAULT_MAX_BATCH_SIZE = int(os.getenv("FEATURES_UPSERT_MAX_BATCH_SIZE", "200"))
TARGET_SQL_PARAMS = int(os.getenv("FEATURES_UPSERT_TARGET_SQL_PARAMS", "15000"))

#  :   -   ( 6 )
#     DIAGNOSTIC_SINGLE_ROW=1
DIAGNOSTIC_SINGLE_ROW = os.getenv("DIAGNOSTIC_SINGLE_ROW", "0").lower() in (
    "1",
    "true",
    "yes",
)


def _get_dynamic_batch_size(num_fields: int, total_records: int) -> int:
    """Compute adaptive batch size based on row width and workload size."""
    if num_fields <= 0:
        return DEFAULT_MIN_BATCH_SIZE

    by_sql_params = max(DEFAULT_MIN_BATCH_SIZE, TARGET_SQL_PARAMS // num_fields)
    batch_size = min(DEFAULT_MAX_BATCH_SIZE, by_sql_params)

    if total_records > 50_000:
        batch_size = max(DEFAULT_MIN_BATCH_SIZE, batch_size // 2)
    elif total_records > 10_000:
        batch_size = max(DEFAULT_MIN_BATCH_SIZE, int(batch_size * 0.75))

    return batch_size


def get_numeric_columns(model_class: Any) -> set[str]:
    """
          .

    Args:
        model_class: SQLAlchemy   Table

    Returns:

    """
    numeric_column_names = set()

    #
    if hasattr(model_class, "columns"):
        #  SQLAlchemy Table
        for col_name, col in model_class.columns.items():
            from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

            col_type = col.type
            #    SQLAlchemy
            if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                numeric_column_names.add(col_name)
            #      (  )
            elif hasattr(col_type, "__class__"):
                type_str = str(col_type).upper()
                if any(
                    t in type_str
                    for t in (
                        "NUMERIC",
                        "DECIMAL",
                        "DOUBLE PRECISION",
                        "REAL",
                        "FLOAT",
                        "INTEGER",
                        "BIGINT",
                        "SMALLINT",
                    )
                ):
                    numeric_column_names.add(col_name)
    elif hasattr(model_class, "__table__"):
        #  ORM
        for col_name, col in model_class.__table__.columns.items():
            from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

            col_type = col.type
            if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                numeric_column_names.add(col_name)
            elif hasattr(col_type, "__class__"):
                type_str = str(col_type).upper()
                if any(
                    t in type_str
                    for t in (
                        "NUMERIC",
                        "DECIMAL",
                        "DOUBLE PRECISION",
                        "REAL",
                        "FLOAT",
                        "INTEGER",
                        "BIGINT",
                        "SMALLINT",
                    )
                ):
                    numeric_column_names.add(col_name)

    return numeric_column_names


def validate_numeric_types(
    records: list[dict[str, Any]],
    numeric_columns: set[str],
    row_offset: int = 0,
) -> None:
    """
         UPSERT.

    ,        (int, float, Decimal)
       NaN/inf  float.

    Args:
        records:
        numeric_columns:
        row_offset:

    Raises:
        TypeError:
        ValueError:   NaN/inf
    """
    if not records:
        return

    errors: list[str] = []

    for row_idx, row in enumerate(records):
        actual_idx = row_offset + row_idx

        for col in numeric_columns:
            if col not in row:
                continue

            val = row[col]

            # None  -   NULL
            if val is None:
                continue

            #
            if isinstance(val, str):
                errors.append(
                    f"Row {actual_idx}: column '{col}' is str: {val!r} (type: {type(val).__name__})"
                )
                continue

            #
            if isinstance(val, int | float | Decimal | np.number):
                #  float  NaN/inf
                if isinstance(val, float | np.floating):
                    if not math.isfinite(val):
                        errors.append(
                            f"Row {actual_idx}: column '{col}' not finite: {val!r}"
                        )
                elif isinstance(val, np.integer):
                    # numpy integer
                    pass
                # int, Decimal
                continue

            #
            errors.append(
                f"Row {actual_idx}: column '{col}' has invalid type {type(val).__name__}: {val!r}"
            )

    if errors:
        error_msg = f"Type validation failed for {len(errors)} values:\n" + "\n".join(
            errors[:20]  #   20
        )
        if len(errors) > 20:
            error_msg += f"\n... and {len(errors) - 20} more errors"
        logger.error(error_msg)
        raise TypeError(error_msg)


async def load_db_columns(session: AsyncSession, table_name: str) -> set[str]:
    """
         .

    Args:
        session: SQLAlchemy
        table_name:

    Returns:

    """
    query = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name
        AND table_schema = 'public'
    """
    )

    result = await session.execute(query, {"table_name": table_name})
    columns = {
        row[0] for row in result.all()
    }  # FIXED: .all() instead of .fetchall() for async

    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Loaded {len(columns)} columns from {table_name}")
    return columns


def assert_required_fields(records: list[dict[str, Any]], required: set[str]) -> None:
    """
         .

    Args:
        records:
        required:

    Raises:
        ValueError:
    """
    if not records:
        raise ValueError("No records provided")

    first_record = records[0]
    missing_fields = required - set(first_record.keys())

    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")

    #
    for i, record in enumerate(records):
        missing_in_record = required - set(record.keys())
        if missing_in_record:
            raise ValueError(f"Record {i} missing required fields: {missing_in_record}")

    # Validation passed - no need to log in normal mode


def filter_problematic_fields(
    records: list[dict[str, Any]], problematic_fields: list[str] | None = None
) -> list[dict[str, Any]]:
    """
            UPSERT.

    Args:
        records:
        problematic_fields:

    Returns:

    """
    if problematic_fields is None:
        problematic_fields = []  #    —

    if not problematic_fields:
        #    —
        return records

    filtered_records = []
    for record in records:
        filtered_record = {
            k: v for k, v in record.items() if k not in problematic_fields
        }
        filtered_records.append(filtered_record)

    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Filtered out {len(problematic_fields)} problematic fields")
    return filtered_records


def sanitize_numeric_value(value: Any) -> float | None:
    """
        NaN/inf    float.

    Args:
        value:

    Returns:
         float   None

    Raises:
        ValueError:
    """
    if value is None:
        return None

    try:
        float_val = float(value)

        if np.isnan(float_val):
            return None
        if np.isinf(float_val):
            return None

        return float_val
    except (ValueError, TypeError, OverflowError) as e:
        logger.debug(f"Cannot convert {value} to float: {e}")
        return None


def sanitize_records(
    records: list[dict[str, Any]], db_cols: set[str]
) -> list[dict[str, Any]]:
    """
          .

    Args:
        records:
        db_cols:

    Returns:

    """
    if not records:
        raise ValueError("No records to sanitize")

    sanitized: list[dict[str, Any]] = []
    total_fields = 0
    filtered_fields = 0

    for record in records:
        sanitized_record: dict[str, Any] = {}
        total_fields += len(record)

        for key, value in record.items():
            if key not in db_cols:
                filtered_fields += 1
                continue

            #  None
            if value is None:
                sanitized_record[key] = None
            #  pandas Series/DataFrame —
            elif isinstance(value, pd.Series | pd.DataFrame):
                if len(value) > 0:
                    scalar_value = (
                        value.iloc[0]
                        if isinstance(value, pd.Series)
                        else value.iloc[0, 0]
                    )
                    #   scalar
                    if isinstance(scalar_value, int | float | np.number):
                        clean_value = sanitize_numeric_value(scalar_value)
                        sanitized_record[key] = clean_value
                    else:
                        sanitized_record[key] = (
                            None if pd.isna(scalar_value) else scalar_value
                        )
                else:
                    sanitized_record[key] = None
            #
            elif isinstance(value, int | float | np.number):
                clean_value = sanitize_numeric_value(value)
                # :   None,     UPSERT
                # Postgres  NULL  ON CONFLICT DO UPDATE
                sanitized_record[key] = clean_value
            #
            else:
                #  :
                #   ,
                if isinstance(value, str):
                    #
                    try:
                        #  float ( int)
                        num_value = float(value)
                        sanitized_record[key] = num_value
                    except (ValueError, TypeError):
                        #   ,
                        sanitized_record[key] = value
                else:
                    sanitized_record[key] = value

        sanitized.append(sanitized_record)

    if filtered_fields > 0 and should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Filtered {filtered_fields} fields from {total_fields} total")

    return sanitized


def _clip_numeric_value(value: float, precision: int, scale: int) -> float:
    """
          NUMERIC(precision, scale).

    Args:
        value:
        precision:   ( )
        scale:

    Returns:

    """
    #    NUMERIC(precision, scale):
    # 10^(precision-scale) - 10^(-scale)
    # ,  NUMERIC(10,4): 10^6 - 10^-4 = 999999.9999
    max_value = 10 ** (precision - scale) - 10 ** (-scale)
    min_value = -max_value

    if value > max_value:
        # Silently clip - this is expected for out-of-range values
        return max_value
    if value < min_value:
        return min_value

    return value


def _normalize_value(value: Any, col_type: Any = None) -> Any:
    """
        Python   SQLAlchemy.

    Args:
        value:
        col_type:   SQLAlchemy (,   NUMERIC)

    Returns:
          (int, float, None, str, datetime  ..)
    """
    if value is None:
        return None

    #  pandas NaN
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    #   numpy/pandas    Python
    try:
        #  numpy integer
        if isinstance(value, np.integer | np.int64 | np.int32 | np.int16 | np.int8):
            result = int(value)
            #   NUMERIC,
            if (
                col_type
                and hasattr(col_type, "precision")
                and hasattr(col_type, "scale")
                and col_type.precision is not None
                and col_type.scale is not None
            ):
                result = int(
                    _clip_numeric_value(
                        float(result), col_type.precision, col_type.scale
                    )
                )
            return result

        #  numpy floating
        if isinstance(value, np.floating | np.float64 | np.float32 | np.float16):
            float_val = float(value)
            if np.isnan(float_val) or np.isinf(float_val):
                return None
            #   NUMERIC,
            if (
                col_type
                and hasattr(col_type, "precision")
                and hasattr(col_type, "scale")
                and col_type.precision is not None
                and col_type.scale is not None
            ):
                float_val = _clip_numeric_value(
                    float_val, col_type.precision, col_type.scale
                )
            return float_val

        #  pandas scalar  (, pd.Scalar)
        if hasattr(pd, "Scalar") and isinstance(value, pd.Scalar):
            try:
                scalar_val = value.item()
                return _normalize_value(scalar_val, col_type)  #
            except (AttributeError, ValueError):
                pass

        #    float,
        if isinstance(value, int | float):
            if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                return None
            result = value
            #   NUMERIC,
            if (
                col_type
                and hasattr(col_type, "precision")
                and hasattr(col_type, "scale")
                and col_type.precision is not None
                and col_type.scale is not None
            ):
                result = _clip_numeric_value(
                    float(result), col_type.precision, col_type.scale
                )
            return result

        #       item()
        if hasattr(value, "item"):
            try:
                item_val = value.item()
                return _normalize_value(item_val, col_type)  #
            except (AttributeError, ValueError):
                pass

        #    float/int
        #   ,
        try:
            #   float
            float_val = float(value)
            if np.isnan(float_val) or np.isinf(float_val):
                return None
            #   NUMERIC,
            if (
                col_type
                and hasattr(col_type, "precision")
                and hasattr(col_type, "scale")
                and col_type.precision is not None
                and col_type.scale is not None
            ):
                float_val = _clip_numeric_value(
                    float_val, col_type.precision, col_type.scale
                )
            #    ,  int
            if float_val.is_integer():
                return int(float_val)
            return float_val
        except (ValueError, TypeError, OverflowError):
            pass

        #   ,     ,
        # (         build_upsert_statement)
        return value
    except Exception as e:
        logger.debug(f"Failed to normalize value {value} ({type(value)}): {e}")
        #     None
        return None


def build_upsert_statement(
    model_class,
    records: list[dict[str, Any]],
    pk: tuple[str, ...],
    db_cols: set[str] | None = None,
) -> Any:
    """
     SQLAlchemy UPSERT statement.

    Args:
        model_class: SQLAlchemy   Table
        records:
        pk:
        db_cols:   ( None,  model_class.columns.keys())

    Returns:
        SQLAlchemy Insert statement  on_conflict_do_update
    """
    if not records:
        raise ValueError("No records provided for UPSERT")

    first_record = records[0]

    # DEBUG: detailed logging for statement building
    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Building UPSERT for {len(records)} records")
        logger.debug(f"First record keys: {list(first_record.keys())}")

    #
    table_columns = db_cols if db_cols is not None else set(model_class.columns.keys())

    #
    filtered_records = []
    for record in records:
        filtered_record = {k: v for k, v in record.items() if k in table_columns}
        filtered_records.append(filtered_record)

    if filtered_records:
        removed_cols = set(first_record.keys()) - table_columns
        if removed_cols and should_log(LogCategory.DIAG, Verbosity.VERBOSE):
            logger.warning(f"Filtered out {len(removed_cols)} columns not in table")

    records = filtered_records
    if not records:
        raise ValueError("No valid records after filtering by table columns")

    first_record = records[0]

    #  :      Python
    #     SQLAlchemy bound parameters
    normalized_records: list[dict[str, Any]] = []
    psar_types: set[str] = set()  #    psar

    for record in records:
        normalized_record: dict[str, Any] = {}
        for key, value in record.items():
            #   psar (DEBUG only)
            if key == "psar":
                psar_types.add(type(value).__name__)

            if value is None or pd.isna(value):
                normalized_record[key] = None
            elif isinstance(value, pd.Series | pd.DataFrame):
                #  pandas
                if len(value) == 0:
                    normalized_record[key] = None
                else:
                    try:
                        scalar_value = (
                            value.iloc[0]
                            if isinstance(value, pd.Series)
                            else value.iloc[0, 0]
                        )
                        if pd.isna(scalar_value):
                            normalized_record[key] = None
                        else:
                            #
                            normalized_record[key] = _normalize_value(scalar_value)
                    except Exception:
                        normalized_record[key] = None
            elif isinstance(value, np.ndarray):
                #  numpy
                if value.size == 0:
                    normalized_record[key] = None
                else:
                    try:
                        scalar = value.flat[0]
                        normalized_record[key] = _normalize_value(scalar)
                    except Exception:
                        normalized_record[key] = None
            else:
                #
                normalized_record[key] = _normalize_value(value)
        normalized_records.append(normalized_record)

    # DEBUG: log psar types for diagnostics
    if psar_types and should_log(LogCategory.DIAG, Verbosity.DEBUG):
        psar_normalized_types = set()
        for record in normalized_records:
            if "psar" in record:
                psar_normalized_types.add(type(record["psar"]).__name__)
        logger.debug(f"psar types: {psar_types} -> {psar_normalized_types}")

    # ,
    #    SQLAlchemy,    bound parameters
    if normalized_records:
        all_keys: set[str] = set()
        for record in normalized_records:
            all_keys.update(record.keys())

        #      None
        for record in normalized_records:
            for key in all_keys:
                if key not in record:
                    record[key] = None

    #  :
    #  None,     "column is of type double precision but expression is of type character varying"
    if normalized_records:
        numeric_column_names = set()

        #
        if hasattr(model_class, "columns"):
            #  SQLAlchemy Table
            for col_name, col in model_class.columns.items():
                from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

                col_type = col.type
                #    SQLAlchemy
                if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                    numeric_column_names.add(col_name)
                #      (  )
                elif hasattr(col_type, "__class__"):
                    type_str = str(col_type).upper()
                    if any(
                        t in type_str
                        for t in (
                            "NUMERIC",
                            "DECIMAL",
                            "DOUBLE PRECISION",
                            "REAL",
                            "FLOAT",
                            "INTEGER",
                            "BIGINT",
                            "SMALLINT",
                        )
                    ):
                        numeric_column_names.add(col_name)
        elif hasattr(model_class, "__table__"):
            #  ORM
            for col_name, col in model_class.__table__.columns.items():
                from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

                col_type = col.type
                if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                    numeric_column_names.add(col_name)
                elif hasattr(col_type, "__class__"):
                    type_str = str(col_type).upper()
                    if any(
                        t in type_str
                        for t in (
                            "NUMERIC",
                            "DECIMAL",
                            "DOUBLE PRECISION",
                            "REAL",
                            "FLOAT",
                            "INTEGER",
                            "BIGINT",
                            "SMALLINT",
                        )
                    ):
                        numeric_column_names.add(col_name)

        if numeric_column_names and should_log(LogCategory.DIAG, Verbosity.DEBUG):
            logger.debug(f"Normalizing {len(numeric_column_names)} numeric columns")

            #
            column_types: dict[str, Any] = {}
            if hasattr(model_class, "columns"):
                for col_name, col in model_class.columns.items():
                    if col_name in numeric_column_names:
                        column_types[col_name] = col.type
            elif hasattr(model_class, "__table__"):
                for col_name, col in model_class.__table__.columns.items():
                    if col_name in numeric_column_names:
                        column_types[col_name] = col.type

            # :
            problematic_values: dict[str, list[tuple[Any, type]]] = {}
            for record in normalized_records:
                for key in numeric_column_names:
                    if key in record:
                        value = record[key]
                        if value is not None and isinstance(value, str):
                            if key not in problematic_values:
                                problematic_values[key] = []
                            problematic_values[key].append((value, type(value)))

            if problematic_values and should_log(LogCategory.DIAG, Verbosity.VERBOSE):
                for key, samples in list(problematic_values.items())[:3]:
                    logger.warning(
                        f"String values in numeric column '{key}': {len(samples)} found"
                    )

            #
            for record in normalized_records:
                for key in numeric_column_names:
                    if key in record:
                        value = record[key]
                        if value is None:
                            continue
                        col_type = column_types.get(key)
                        if isinstance(value, str):
                            #
                            # ,   int  float
                            try:
                                # ,    integer
                                is_integer = False
                                if col_type:
                                    if isinstance(col_type, Integer | BigInteger):
                                        is_integer = True
                                    else:
                                        type_str = str(col_type).upper()
                                        if (
                                            "INTEGER" in type_str
                                            or "BIGINT" in type_str
                                            or "SMALLINT" in type_str
                                        ):
                                            is_integer = True

                                #   NUMERIC,
                                if (
                                    col_type
                                    and hasattr(col_type, "precision")
                                    and hasattr(col_type, "scale")
                                    and col_type.precision is not None
                                    and col_type.scale is not None
                                ):
                                    from sqlalchemy.types import Numeric

                                    if isinstance(col_type, Numeric):
                                        #
                                        clipped = _clip_numeric_value(
                                            float(value),
                                            col_type.precision,
                                            col_type.scale,
                                        )
                                        if is_integer:
                                            normalized = int(clipped)
                                        else:
                                            normalized = clipped
                                    else:
                                        if is_integer:
                                            normalized = int(
                                                float(value)
                                            )  #  float  "1.0" -> 1
                                        else:
                                            normalized = float(value)
                                else:
                                    if is_integer:
                                        normalized = int(
                                            float(value)
                                        )  #  float  "1.0" -> 1
                                    else:
                                        normalized = float(value)
                                record[key] = normalized
                            except (ValueError, TypeError):
                                # Silently convert to None - logged at aggregate level
                                record[key] = None
                        elif value is not None and not isinstance(
                            value, int | float | np.number
                        ):
                            #
                            try:
                                normalized: float = float(value)
                                #   NUMERIC,
                                if (
                                    col_type
                                    and hasattr(col_type, "precision")
                                    and hasattr(col_type, "scale")
                                    and col_type.precision is not None
                                    and col_type.scale is not None
                                ):
                                    from sqlalchemy.types import Numeric

                                    if isinstance(col_type, Numeric):
                                        precision: int = col_type.precision
                                        scale: int = col_type.scale
                                        normalized = _clip_numeric_value(
                                            normalized, precision, scale
                                        )
                                record[key] = normalized
                            except (ValueError, TypeError):
                                # Silently convert to None - logged at aggregate level
                                record[key] = None
                        elif isinstance(value, np.number):
                            #  numpy   Python
                            normalized: float | int = float(value)
                            #   NUMERIC,
                            if (
                                col_type
                                and hasattr(col_type, "precision")
                                and hasattr(col_type, "scale")
                                and col_type.precision is not None
                                and col_type.scale is not None
                            ):
                                from sqlalchemy.types import Numeric

                                if isinstance(col_type, Numeric):
                                    precision: int = col_type.precision
                                    scale: int = col_type.scale
                                    normalized = _clip_numeric_value(
                                        normalized, precision, scale
                                    )
                            record[key] = normalized

    #   INSERT statement
    stmt = pg_insert(model_class).values(normalized_records)

    #  update_dict    excluded
    update_dict = {}
    non_pk_fields = [k for k in first_record if k not in pk]

    #     update_dict
    skipped_fields = []
    for field in non_pk_fields:
        try:
            excluded_value = stmt.excluded[field]
            update_dict[field] = excluded_value
        except (KeyError, AttributeError):
            skipped_fields.append(field)
            continue
        except Exception as e:
            logger.error(f"Unexpected error with field '{field}': {e}")
            continue

    if skipped_fields and should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Skipped {len(skipped_fields)} fields not in excluded")

    if not update_dict:
        raise ValueError("No fields available for UPSERT update")

    #  on_conflict_do_update
    stmt = stmt.on_conflict_do_update(index_elements=list(pk), set_=update_dict)

    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"UPSERT statement built with {len(update_dict)} update fields")

    return stmt


def validate_upsert_data(
    records: list[dict[str, Any]], db_cols: set[str], required_fields: set[str]
) -> None:
    """
         UPSERT.

    Args:
        records:
        db_cols:
        required_fields:

    Raises:
        ValueError:
    """
    #
    assert_required_fields(records, required_fields)

    #
    critical_fields = ["ics_26", "rma_20", "t3_20"]
    missing_critical = []

    for field in critical_fields:
        if field in db_cols and not any(field in record for record in records):
            missing_critical.append(field)

    if missing_critical and should_log(LogCategory.DIAG, Verbosity.VERBOSE):
        logger.warning(f"Critical fields missing from all records: {missing_critical}")

    #
    type_warnings = 0
    for record in records:
        for key, value in record.items():
            if key in db_cols and isinstance(value, int | float | np.number):
                try:
                    sanitize_numeric_value(value)
                except ValueError:
                    type_warnings += 1

    if type_warnings > 0 and should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Type warnings during validation: {type_warnings}")


async def execute_upsert(
    session: AsyncSession, stmt: Any, records: list[dict[str, Any]]
) -> int:
    """
     UPSERT   .

    Args:
        session: SQLAlchemy
        stmt: UPSERT statement
        records:

    Returns:

    """
    # DEBUG: detailed pre-execution logging
    if should_log(LogCategory.DIAG, Verbosity.DEBUG) and records:
        num_cols = len(records[0])
        total_params = len(records) * num_cols
        logger.debug(
            f"Executing UPSERT: {len(records)} rows × {num_cols} cols = {total_params} params"
        )

    try:
        # DEBUG: SQL preview
        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            try:
                compiled = stmt.compile(compile_kwargs={"literal_binds": False})
                sql_str = str(compiled)
                sql_preview = sql_str[:300] if len(sql_str) > 300 else sql_str
                logger.debug(f"SQL preview: {sql_preview}...")
            except Exception:
                pass  # Don't log SQL compilation failures

        result = await session.execute(stmt)

        # DEBUG: affected rows
        if should_log(LogCategory.DIAG, Verbosity.DEBUG) and hasattr(
            result, "rowcount"
        ):
            logger.debug(f"Affected rows: {result.rowcount}")

        return len(records)

    except Exception as e:
        import traceback

        # Always log errors in full detail
        logger.error(f"UPSERT FAILED: {type(e).__name__}: {e}")
        logger.error(f"Records count: {len(records)}")
        if records:
            logger.error(f"First record keys: {list(records[0].keys())[:15]}...")
            logger.error(f"First record sample: {dict(list(records[0].items())[:5])}")

        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

        raise


async def build_and_execute_upsert(
    session: AsyncSession,
    model_class,
    records: list[dict[str, Any]],
    db_cols: set[str],
    pk: tuple[str, ...] = IndicatorStorageContract.identity_fields,
    required_fields: set[str] | None = None,
) -> int:
    """
     : , ,    UPSERT.

    Args:
        session: SQLAlchemy
        model_class: SQLAlchemy
        records:
        db_cols:
        pk:
        required_fields:

    Returns:

    """
    # Use aggregator for summary logging
    with LogAggregator(LogCategory.INSERT, "upsert") as agg:
        # 1.
        if required_fields is None:
            required_fields = IndicatorStorageContract.required_fields_set()
        validate_upsert_data(records, db_cols, required_fields)

        # 2.
        sanitized_records = sanitize_records(records, db_cols)

        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            logger.debug(
                f"prepared {len(records)} records, sanitized {len(sanitized_records)}"
            )

        if not sanitized_records:
            logger.warning("No valid records after sanitization")
            return 0

        # 2.5.      UPSERT statement
        filtered_records = filter_problematic_fields(sanitized_records)

        if not filtered_records:
            logger.warning("No valid records after filtering")
            return 0

        # 2.7.
        numeric_columns = get_numeric_columns(model_class)

        # 2.8.
        try:
            validate_numeric_types(filtered_records, numeric_columns, row_offset=0)
        except (TypeError, ValueError) as validation_error:
            logger.error(f"Type validation failed: {validation_error}")
            raise

        # 2.9.    asyncpg   (32767)
        if filtered_records:
            num_fields = len(filtered_records[0])
            calculated_batch_size = _get_dynamic_batch_size(
                num_fields=num_fields,
                total_records=len(filtered_records),
            )
        else:
            calculated_batch_size = DEFAULT_MIN_BATCH_SIZE

        # F.1: Record batch distribution metrics
        prom = get_prom_metrics()
        symbol_label = ""
        timeframe_label = ""
        if filtered_records:
            symbol_label = str(filtered_records[0].get("symbol", ""))
            timeframe_label = str(filtered_records[0].get("timeframe", ""))

        num_batches_total = max(
            1,
            (len(filtered_records) - 1) // calculated_batch_size + 1,
        )
        if symbol_label and timeframe_label:
            prom.record_batch_size(symbol_label, timeframe_label, calculated_batch_size)
            logger.info(
                "Batch plan: %d records, %d fields, batch_size=%d, num_batches=%d",
                len(filtered_records),
                num_fields,
                calculated_batch_size,
                num_batches_total,
            )

        total_saved = 0

        #  :   -
        if DIAGNOSTIC_SINGLE_ROW:
            logger.warning(
                f"DIAGNOSTIC_SINGLE_ROW: Processing {len(filtered_records)} records individually"
            )

            for i, rec in enumerate(filtered_records):
                try:
                    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
                        logger.debug(f"Processing record {i+1}/{len(filtered_records)}")
                    validate_numeric_types([rec], numeric_columns, row_offset=i)
                    stmt = build_upsert_statement(model_class, [rec], pk, db_cols)
                    batch_saved = await execute_upsert(session, stmt, [rec])
                    total_saved += batch_saved
                except Exception:
                    logger.error(f"UPSERT FAILED on record {i+1}")
                    logger.error(f"Record sample: {dict(list(rec.items())[:10])}")
                    raise

            agg.set_extra("mode", "diagnostic")
            agg.set_extra("saved", total_saved)
            return total_saved

        # Normal batched execution
        if len(filtered_records) > calculated_batch_size:
            num_batches = (len(filtered_records) - 1) // calculated_batch_size + 1

            if should_log(LogCategory.DIAG, Verbosity.VERBOSE):
                logger.info(
                    f"Splitting {len(filtered_records)} records into {num_batches} batches"
                )

            for i in range(0, len(filtered_records), calculated_batch_size):
                batch = filtered_records[i : i + calculated_batch_size]
                batch_num = i // calculated_batch_size + 1

                # DEBUG: per-batch logging
                if should_log(LogCategory.DIAG, Verbosity.DEBUG):
                    logger.debug(
                        f"Processing batch {batch_num}/{num_batches} ({len(batch)} records)"
                    )

                try:
                    validate_numeric_types(batch, numeric_columns, row_offset=i)
                except (TypeError, ValueError) as batch_validation_error:
                    logger.error(
                        f"Type validation failed for batch {batch_num}: {batch_validation_error}"
                    )
                    raise

                try:
                    stmt = build_upsert_statement(model_class, batch, pk, db_cols)
                    batch_saved = await execute_upsert(session, stmt, batch)
                    total_saved += batch_saved
                    agg.add("batches", value=len(batch))
                except Exception as batch_error:
                    logger.error(f"UPSERT failed for batch {batch_num}: {batch_error}")
                    raise

            agg.set_extra("saved", total_saved)
            agg.set_extra("batches_count", num_batches)
            return total_saved

        #   ,
        stmt = build_upsert_statement(model_class, filtered_records, pk, db_cols)
        result = await execute_upsert(session, stmt, filtered_records)
        agg.set_extra("saved", result)
        return result
