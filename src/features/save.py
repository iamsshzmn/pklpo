"""
Save module for features - loads parquet files and saves to database.

This module implements the strategy of loading calculated indicators from parquet files
and saving them to PostgreSQL with proper upsert operations.
"""

import gc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.models import Indicator

from .config import DatabaseConfig, create_database_config
from .logging_config import get_features_logger
from .utils.memlog import force_cleanup, memory_monitor

logger = get_features_logger("features.save")


async def save_batch(
    session,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    config: DatabaseConfig | None = None,
    snapshot_id: str | None = None,
    algorithm_version: str = "1.0.0",
) -> dict[str, Any]:
    """
    Save a batch of data to database using optimized COPY + MERGE.

    Args:
        session: Database session
        df: DataFrame with indicators
        symbol: Trading symbol
        timeframe: Timeframe
        config: Database configuration
        snapshot_id: Optional snapshot ID for ML reproducibility (FEAT-001)
        algorithm_version: Algorithm version for ML reproducibility (FEAT-001)

    Returns:
        Dictionary with save results
    """
    if config is None:
        config = create_database_config()

    if df is None or len(df) == 0:
        logger.warning("Empty DataFrame provided for saving")
        return {"success": False, "error": "Empty DataFrame", "rows_saved": 0}

    logger.info(f"Saving batch: {len(df)} rows for {symbol} {timeframe}")

    with memory_monitor("save_batch") as mem_log:
        if config.LOG_MEMORY_USAGE:
            mem_log.log_dataframe_memory(df, "Batch DataFrame")

        # Prepare data for database (FEAT-001: with versioning)
        batch_data = _prepare_batch_data(
            df,
            symbol,
            timeframe,
            snapshot_id=snapshot_id,
            algorithm_version=algorithm_version,
        )

        if not batch_data:
            logger.warning("No valid data to save")
            return {"success": False, "error": "No valid data", "rows_saved": 0}

        # Save in smaller batches if needed
        total_saved = 0
        batch_size = config.BATCH_SIZE

        for i in range(0, len(batch_data), batch_size):
            batch = batch_data[i : i + batch_size]

            try:
                saved_count = await _save_batch_optimized(session, batch, config)
                total_saved += saved_count

                logger.debug(
                    f"Saved sub-batch {i//batch_size + 1}: {saved_count} records"
                )

                # Commit periodically
                if (i // batch_size + 1) % config.COMMIT_FREQUENCY == 0:
                    await session.commit()
                    logger.debug(f"Committed after {i//batch_size + 1} sub-batches")

            except Exception as e:
                logger.error(f"Failed to save sub-batch {i//batch_size + 1}: {e}")
                await session.rollback()
                raise

        # Final commit
        await session.commit()

        # Clean up
        if config.CLEAR_INTERMEDIATE_OBJECTS:
            force_cleanup(df, batch_data)

        if config.FORCE_GC_AFTER_CHUNK:
            gc.collect()

        result = {
            "success": True,
            "rows_processed": len(df),
            "rows_saved": total_saved,
            "batches_processed": (len(batch_data) + batch_size - 1) // batch_size,
            "saved_at": datetime.utcnow().isoformat(),
        }

        logger.info(f"Successfully saved batch: {total_saved} records")
        return result


async def save_parquet_to_pg(
    session,
    parquet_path: str,
    symbol: str,
    timeframe: str,
    batch_size: int = 1000,
    validate_before_save: bool = True,
    config: DatabaseConfig | None = None,
) -> dict[str, Any]:
    """
    Load parquet file and save indicators to PostgreSQL.

    Args:
        session: Database session
        parquet_path: Path to parquet file
        symbol: Trading symbol
        timeframe: Timeframe
        batch_size: Batch size for database operations
        validate_before_save: Whether to validate data before saving

    Returns:
        Dictionary with save results
    """
    logger.info(f"Loading parquet file: {parquet_path}")

    try:
        # Load parquet file
        df = pd.read_parquet(parquet_path)

        if len(df) == 0:
            raise ValueError("Parquet file is empty")

        # Validate data
        if validate_before_save:
            validation_result = _validate_dataframe(df, symbol, timeframe)
            if not validation_result["valid"]:
                raise ValueError(
                    f"Data validation failed: {validation_result['errors']}"
                )

        # Prepare data for database (FEAT-001: with versioning)
        batch_data = _prepare_batch_data(df, symbol, timeframe)

        if not batch_data:
            logger.warning("No valid data to save")
            return {
                "success": False,
                "error": "No valid data to save",
                "rows_processed": 0,
                "rows_saved": 0,
            }

        # Save in batches
        total_saved = 0
        for i in range(0, len(batch_data), batch_size):
            batch = batch_data[i : i + batch_size]
            saved_count = await _save_batch(session, batch)
            total_saved += saved_count

            logger.info(f"Saved batch {i//batch_size + 1}: {saved_count} records")

        # Get metadata from parquet file
        metadata = df.attrs if hasattr(df, "attrs") else {}

        result = {
            "success": True,
            "parquet_path": parquet_path,
            "symbol": symbol,
            "timeframe": timeframe,
            "rows_processed": len(df),
            "rows_saved": total_saved,
            "batches_processed": (len(batch_data) + batch_size - 1) // batch_size,
            "metadata": metadata,
            "saved_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Successfully saved {symbol} {timeframe}",
            rows_processed=result["rows_processed"],
            rows_saved=result["rows_saved"],
        )

        return result

    except Exception as e:
        logger.error(f"Failed to save {symbol} {timeframe}: {e}")
        return {
            "success": False,
            "error": str(e),
            "parquet_path": parquet_path,
            "symbol": symbol,
            "timeframe": timeframe,
        }


def _validate_dataframe(
    df: pd.DataFrame, symbol: str, timeframe: str
) -> dict[str, Any]:
    """
    Validate DataFrame before saving to database.

    Args:
        df: DataFrame to validate
        symbol: Trading symbol
        timeframe: Timeframe

    Returns:
        Validation result
    """
    errors = []
    warnings = []

    # Check required columns
    required_cols = ["ts"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")

    # Check for empty DataFrame
    if len(df) == 0:
        errors.append("DataFrame is empty")

    # Check for timestamp column
    if "ts" in df.columns:
        ts_series = df["ts"]
        if ts_series.isna().any():
            warnings.append("Timestamp column contains NaN values")

        # Check timestamp range
        if not ts_series.empty:
            max_ts = ts_series.max()
            current_ts = datetime.utcnow().timestamp()

            if max_ts > current_ts + 86400:  # More than 1 day in future
                warnings.append(
                    f"Timestamps in future: max={max_ts}, current={current_ts}"
                )

    # Check feature columns
    feature_cols = [
        col
        for col in df.columns
        if col not in ["open", "high", "low", "close", "volume", "ts"]
    ]

    if not feature_cols:
        warnings.append("No feature columns found")

    # Check for critical features
    critical_features = ["hlc3", "ema_8", "sma_20"]
    missing_critical = [f for f in critical_features if f not in feature_cols]
    if missing_critical:
        warnings.append(f"Missing critical features: {missing_critical}")

    # Check data types
    for col in feature_cols:
        if df[col].dtype == "object":
            warnings.append(f"Column {col} has object dtype - may cause issues")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "feature_count": len(feature_cols),
        "row_count": len(df),
    }


def _prepare_batch_data(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    snapshot_id: str | None = None,
    algorithm_version: str = "1.0.0",
) -> list[dict[str, Any]]:
    """
    Prepare DataFrame data for database insertion.

    Args:
        df: DataFrame with indicators
        symbol: Trading symbol
        timeframe: Timeframe
        snapshot_id: Optional snapshot ID for ML reproducibility (FEAT-001)
        algorithm_version: Algorithm version for ML reproducibility (FEAT-001)

    Returns:
        List of dictionaries for batch insertion
    """
    batch_data = []

    # Оптимизация: используем itertuples() вместо iterrows() для лучшей производительности
    # itertuples() быстрее iterrows() в 2-3 раза для больших DataFrame
    for row_tuple in df.itertuples(index=False, name=None):
        # Создаём словарь для доступа к значениям по имени колонки
        row_dict = {col: row_tuple[i] for i, col in enumerate(df.columns)}

        # Use the data timestamp for calculated_at, not current time
        ts_value = row_dict.get("ts")
        if ts_value is None:
            continue
        calculated_at = datetime.fromtimestamp(int(ts_value), tz=UTC)

        # Base data (FEAT-001: with versioning fields)
        base_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": int(ts_value) * 1000,  # Convert seconds to milliseconds
            "calculated_at": calculated_at,
            # TODO: Add back when DB migration is done (FEAT-001)
            # "algorithm_version": algorithm_version,
            # "snapshot_id": snapshot_id,
        }

        # Add indicator columns
        indicator_data = {**base_data}
        indicators_added = 0

        for col in df.columns:
            if col in ("ts", "open", "high", "low", "close", "volume"):
                continue

            value = row_dict.get(col)

            # Skip NaN, None, and invalid values
            if pd.isna(value) or value is None:
                continue

            try:
                # Ensure numeric type
                float_value = float(value)
                if pd.isna(float_value) or np.isinf(float_value):
                    continue

                indicator_data[col] = float_value
                indicators_added += 1

            except (ValueError, TypeError, OverflowError):
                continue

        # Only add if we have indicators
        if indicators_added > 0:
            batch_data.append(indicator_data)

    return batch_data


async def _save_batch_optimized(
    session, batch_data: list[dict[str, Any]], config: DatabaseConfig
) -> int:
    """
    Optimized batch save using COPY FROM + MERGE.

    Args:
        session: Database session
        batch_data: List of dictionaries to insert
        config: Database configuration

    Returns:
        Number of records saved
    """
    if not batch_data:
        return 0

    try:
        if config.USE_COPY_FROM:
            # Use COPY FROM for bulk inserts (faster for large batches)
            return await _save_batch_copy_from(session, batch_data, config)
        # Use traditional UPSERT
        return await _save_batch_upsert(session, batch_data, config)

    except Exception as e:
        logger.error(f"Optimized batch save failed: {e}")
        raise


async def _save_batch_copy_from(
    session, batch_data: list[dict[str, Any]], config: DatabaseConfig
) -> int:
    """Save batch using COPY FROM + MERGE for maximum performance."""
    import csv
    import io

    # Create temporary table name
    temp_table = f"{config.TEMP_TABLE_PREFIX}{int(datetime.utcnow().timestamp())}"

    try:
        # Create temporary table with same structure as indicators
        create_temp_sql = f"""
        CREATE TEMP TABLE {temp_table} (LIKE indicators INCLUDING ALL)
        """
        await session.execute(text(create_temp_sql))

        # Prepare CSV data
        csv_buffer = io.StringIO()
        if batch_data:
            fieldnames = batch_data[0].keys()
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(batch_data)

        # Use COPY FROM to load data
        csv_data = csv_buffer.getvalue()
        copy_sql = f"""
        COPY {temp_table} FROM STDIN WITH (FORMAT csv, HEADER true)
        """

        await session.execute(text(copy_sql), {"data": csv_data})

        # Merge data using UPSERT
        merge_sql = f"""
        INSERT INTO indicators
        SELECT * FROM {temp_table}
        ON CONFLICT (symbol, timeframe, timestamp)
        DO UPDATE SET
            calculated_at = EXCLUDED.calculated_at,
            {', '.join([f"{k} = EXCLUDED.{k}" for k in batch_data[0]
                       if k not in ["symbol", "timeframe", "timestamp", "calculated_at"]])}
        """

        await session.execute(text(merge_sql))

        # Get number of affected rows
        count_sql = f"SELECT COUNT(*) FROM {temp_table}"
        count_result = await session.execute(text(count_sql))
        rows_affected = count_result.scalar()

        logger.debug(f"COPY FROM + MERGE completed: {rows_affected} rows")
        return int(rows_affected) if rows_affected is not None else 0

    except Exception as e:
        logger.error(f"COPY FROM save failed: {e}")
        raise
    finally:
        # Clean up temporary table
        try:
            drop_sql = f"DROP TABLE IF EXISTS {temp_table}"
            await session.execute(text(drop_sql))
        except Exception as e:
            logger.debug(f"Cleanup error (ignored): {e}")


async def _save_batch_upsert(
    session, batch_data: list[dict[str, Any]], config: DatabaseConfig
) -> int:
    """Save batch using traditional UPSERT."""
    try:
        # Create UPSERT statement
        stmt = pg_insert(Indicator).values(batch_data)

        # Create update dictionary (exclude primary key columns)
        first_record = batch_data[0]
        update_dict = {
            k: stmt.excluded[k]
            for k in first_record
            if k not in ["symbol", "timeframe", "timestamp"]
        }

        # Execute UPSERT
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "timestamp"], set_=update_dict
        )

        await session.execute(stmt)
        return len(batch_data)

    except Exception as e:
        logger.error(f"UPSERT save failed: {e}")
        raise


async def _save_batch(session, batch_data: list[dict[str, Any]]) -> int:
    """
    Save a batch of data to database using UPSERT.

    Args:
        session: Database session
        batch_data: List of dictionaries to insert

    Returns:
        Number of records saved
    """
    if not batch_data:
        return 0

    try:
        # Create UPSERT statement
        stmt = pg_insert(Indicator).values(batch_data)

        # Create update dictionary (exclude primary key columns)
        first_record = batch_data[0]
        update_dict = {
            k: stmt.excluded[k]
            for k in first_record
            if k not in ["symbol", "timeframe", "timestamp"]
        }

        # Execute UPSERT
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "timestamp"], set_=update_dict
        )

        await session.execute(stmt)
        await session.commit()

        return len(batch_data)

    except Exception as e:
        logger.error(f"Failed to save batch: {e}")
        await session.rollback()
        raise


async def validate_database_connection(session) -> dict[str, Any]:
    """
    Validate database connection and table structure.

    Args:
        session: Database session

    Returns:
        Validation result
    """
    try:
        # Test basic connection
        result = await session.execute(text("SELECT 1"))
        connection_ok = result.scalar() == 1

        # Check if indicators table exists
        table_check = await session.execute(
            text(
                """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'indicators'
            )
        """
            )
        )
        table_exists = table_check.scalar()

        # Get table info
        if table_exists:
            columns_result = await session.execute(
                text(
                    """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'indicators'
                ORDER BY ordinal_position
            """
                )
            )
            columns = [
                {"name": row[0], "type": row[1]} for row in columns_result.fetchall()
            ]
        else:
            columns = []

        return {
            "connection_ok": connection_ok,
            "table_exists": table_exists,
            "columns": columns,
            "valid": connection_ok and table_exists,
        }

    except Exception as e:
        return {
            "connection_ok": False,
            "table_exists": False,
            "error": str(e),
            "valid": False,
        }


if __name__ == "__main__":
    import argparse
    import asyncio
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    sys.path.append(str(Path(__file__).parent.parent.parent))

    from src.database import get_async_session  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="Save parquet file to database")
    parser.add_argument("parquet_file", help="Parquet file path")
    parser.add_argument("--symbol", required=True, help="Trading symbol")
    parser.add_argument("--timeframe", required=True, help="Timeframe")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for database operations",
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate data before saving"
    )

    args = parser.parse_args()

    async def main():
        async for session in get_async_session():
            # Validate connection
            validation = await validate_database_connection(session)
            if not validation["valid"]:
                print(f"❌ Database validation failed: {validation}")
                return

            # Save parquet file
            result = await save_parquet_to_pg(
                session=session,
                parquet_path=args.parquet_file,
                symbol=args.symbol,
                timeframe=args.timeframe,
                batch_size=args.batch_size,
                validate_before_save=args.validate,
            )

            if result["success"]:
                print(f"✅ Successfully saved {args.symbol} {args.timeframe}")
                print(f"📊 Rows processed: {result['rows_processed']}")
                print(f"💾 Rows saved: {result['rows_saved']}")
                print(f"📁 Batches: {result['batches_processed']}")
            else:
                print(f"❌ Failed to save: {result['error']}")
                sys.exit(1)

    asyncio.run(main())


async def verify_database_integrity(
    session, symbol: str, timeframe: str
) -> dict[str, Any]:
    """
    Verify database integrity after batch operations.

    Args:
        session: Database session
        symbol: Trading symbol
        timeframe: Timeframe

    Returns:
        Dictionary with integrity check results
    """
    try:
        from sqlalchemy import text

        # Set statement timeout to prevent hanging
        await session.execute(text("SET statement_timeout = '60s'"))

        # Check total count
        count_result = await session.execute(
            text(
                "SELECT COUNT(*) as total_count FROM indicators WHERE symbol = :symbol AND timeframe = :timeframe"
            ),
            {"symbol": symbol, "timeframe": timeframe},
        )
        total_count = count_result.scalar()

        # Check timestamp range
        ts_result = await session.execute(
            text(
                """
                SELECT
                    MIN(timestamp) as min_ts,
                    MAX(timestamp) as max_ts,
                    COUNT(DISTINCT timestamp) as unique_ts
                FROM indicators
                WHERE symbol = :symbol AND timeframe = :timeframe
            """
            ),
            {"symbol": symbol, "timeframe": timeframe},
        )
        ts_data = ts_result.fetchone()

        # Check for duplicates
        duplicate_result = await session.execute(
            text(
                """
                SELECT COUNT(*) as duplicate_count
                FROM (
                    SELECT symbol, timeframe, timestamp, COUNT(*)
                    FROM indicators
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    GROUP BY symbol, timeframe, timestamp
                    HAVING COUNT(*) > 1
                ) duplicates
            """
            ),
            {"symbol": symbol, "timeframe": timeframe},
        )
        duplicate_count = duplicate_result.scalar()

        integrity_result = {
            "total_count": total_count,
            "min_timestamp": ts_data.min_ts if ts_data else None,
            "max_timestamp": ts_data.max_ts if ts_data else None,
            "unique_timestamps": ts_data.unique_ts if ts_data else 0,
            "duplicate_count": duplicate_count,
            "integrity_ok": duplicate_count == 0,
            "timestamp_range_ok": (
                ts_data.min_ts is not None and ts_data.max_ts is not None
                if ts_data
                else False
            ),
        }

        logger.info(f"Database integrity check for {symbol} {timeframe}:")
        logger.info(f"  Total records: {total_count}")
        logger.info(f"  Timestamp range: {ts_data.min_ts} to {ts_data.max_ts}")
        logger.info(f"  Unique timestamps: {ts_data.unique_ts}")
        logger.info(f"  Duplicates: {duplicate_count}")
        logger.info(f"  Integrity OK: {integrity_result['integrity_ok']}")

        return integrity_result

    except Exception as e:
        logger.error(f"Database integrity check failed: {e}")
        return {"error": str(e), "integrity_ok": False}
