"""
Main inserter function for indicators.

REFACTORED (Stage 2): Decomposed into modular components:
- data_transformer.py: Type conversions and normalization
- schema_cache.py: Schema caching
- upsert_executor.py: UPSERT with retry

This file now contains only orchestration logic (~100 lines).
"""

import os
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.indicators_partition.application.partition_policy import (
    MonthlyPartitionPolicy,
)
from src.db.indicators_partition.infrastructure import (
    PostgresIndicatorsPartitionMaintenanceAdapter,
)
from src.logging import (
    LogAggregator,
    LogCategory,
    Verbosity,
    get_category_logger,
    should_log,
)

from ...domain.indicator_schema_registry import IndicatorSchemaRegistry
from ...domain.strategy import get_max_lookback_for_strategies
from ...observability.prometheus import get_metrics as get_prom_metrics
from .batch_builder import (
    build_batch_data,
    filter_batch_by_schema,
    normalize_record_names,
)
from .data_transformer import (
    get_numeric_columns_from_table,
    transform_records_for_upsert,
)
from .normalizer import (
    add_service_fields,
    filter_columns_by_schema,
    normalize_numeric_columns,
    normalize_timestamp_column,
    sanitize_column_names,
)
from .schema_cache import get_or_load_schema
from .schema_checker import check_db_state, load_db_columns, reflect_indicators_table
from .upsert_executor import execute_upsert_with_retry
from .validator import validate_dataframe, validate_required_fields

logger = get_category_logger(LogCategory.INSERT)

# Primary key fields
PK_FIELDS = ("symbol", "timeframe", "timestamp")

# Environment variable to disable warmup trimming (for debugging)
SKIP_WARMUP_TRIM = os.getenv("FEATURES_SKIP_WARMUP_TRIM", "false").lower() == "true"


def _month_start(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1, tzinfo=UTC)


def _add_month(dt: datetime) -> datetime:
    month_index = dt.month
    year = dt.year + (1 if month_index == 12 else 0)
    month = 1 if month_index == 12 else month_index + 1
    return datetime(year, month, 1, tzinfo=UTC)


async def _ensure_indicator_monthly_partitions(
    session: AsyncSession,
    ind_df: pd.DataFrame,
) -> None:
    if "timestamp" not in ind_df.columns:
        return

    timestamps = pd.to_numeric(ind_df["timestamp"], errors="coerce").dropna()
    if timestamps.empty:
        return

    start_dt = _month_start(datetime.fromtimestamp(int(timestamps.min()) / 1000, tz=UTC))
    end_dt = _month_start(datetime.fromtimestamp(int(timestamps.max()) / 1000, tz=UTC))
    policy = MonthlyPartitionPolicy()
    adapter = PostgresIndicatorsPartitionMaintenanceAdapter(session)

    await adapter.ensure_parent_exists()
    await adapter.assert_parent_upsert_constraint()

    current = start_dt
    while current <= end_dt:
        await adapter.ensure_partition(policy.build_partition_spec(current))
        current = _add_month(current)


def _calculate_warmup_rows(ind_df: pd.DataFrame) -> int:
    """
    Calculate the number of warmup rows to trim.

    Warmup rows contain NaN values because indicators need lookback periods
    to calculate valid values. These rows should not be saved to DB.

    Args:
        ind_df: DataFrame with calculated indicators

    Returns:
        Number of rows to trim from the beginning
    """
    # Get indicator columns (exclude service fields)
    service_cols = {
        "ts",
        "timestamp",
        "symbol",
        "timeframe",
        "calculated_at",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "data_status",
    }
    indicator_cols = [c for c in ind_df.columns if c not in service_cols]

    if not indicator_cols:
        return 0

    # Get max lookback from strategy module
    max_lookback = get_max_lookback_for_strategies(indicator_cols)

    # Add 10% buffer for safety
    warmup_rows = int(max_lookback * 1.1)

    return min(warmup_rows, len(ind_df) - 1)  # Don't trim all rows


def diagnose_nan_values(
    ind_df: pd.DataFrame,
    warmup_rows: int,
) -> dict[str, list[str]]:
    """
    Diagnose NaN values: separate expected (warmup) from unexpected (errors).

    Task 4: Helps identify calculation errors vs normal warmup NaN.

    Args:
        ind_df: DataFrame with calculated indicators
        warmup_rows: Number of warmup rows (expected NaN zone)

    Returns:
        Dict with 'expected_nan' (columns with NaN only in warmup) and
        'unexpected_nan' (columns with NaN after warmup - potential errors)
    """
    service_cols = {
        "ts",
        "timestamp",
        "symbol",
        "timeframe",
        "calculated_at",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "data_status",
    }
    indicator_cols = [c for c in ind_df.columns if c not in service_cols]

    if not indicator_cols or len(ind_df) <= warmup_rows:
        return {"expected_nan": [], "unexpected_nan": []}

    # Check post-warmup zone for NaN
    post_warmup_df = ind_df.iloc[warmup_rows:]

    expected_nan = []
    unexpected_nan = []

    for col in indicator_cols:
        nan_in_post_warmup = post_warmup_df[col].isna().sum()
        if nan_in_post_warmup > 0:
            # NaN after warmup = potential calculation error
            unexpected_nan.append(col)
        elif ind_df[col].iloc[:warmup_rows].isna().any():
            # NaN only in warmup zone = expected
            expected_nan.append(col)

    return {"expected_nan": expected_nan, "unexpected_nan": unexpected_nan}


async def insert_indicators(
    session: AsyncSession,
    ind_df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    *,
    trim_warmup: bool = True,
    seen_timestamps: set[int] | None = None,
) -> int:
    """
    Batch UPSERT indicators to database.

    Performs bulk insert/update of indicators to the `indicators` table.
    Uses schema manager for validation and DB reflection for compatibility.

    Warmup trimming: By default, the first N rows (warmup period) are trimmed
    because they contain NaN values from indicator lookback periods. This can
    be disabled with trim_warmup=False or FEATURES_SKIP_WARMUP_TRIM=true env var.

    Args:
        session: Async SQLAlchemy session
        ind_df: DataFrame with calculated indicators
        symbol: Instrument symbol (e.g., 'BTC-USDT-SWAP')
        timeframe: Timeframe (e.g., '1m', '5m', '1h')
        trim_warmup: Whether to trim warmup rows (default: True)
        seen_timestamps: Optional shared set of seen timestamps. Pass the same set
            across chunked calls to detect duplicates at chunk boundaries.

    Returns:
        Number of successfully saved records

    Raises:
        ValueError: If required fields are missing or data is invalid
    """
    # Use aggregator for summary logging
    with LogAggregator(LogCategory.INSERT, "insert_indicators") as agg:
        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            logger.debug(
                f"symbol={symbol}, timeframe={timeframe}, shape={ind_df.shape if ind_df is not None else 'None'}"
            )

        # 1. Validate input
        if not validate_dataframe(ind_df):
            return 0

        # 2. Trim warmup rows (if enabled)
        warmup_rows = _calculate_warmup_rows(ind_df)
        if warmup_rows > 0:
            # Mark warmup zone with data_status (for observability/debugging)
            if "data_status" not in ind_df.columns:
                ind_df["data_status"] = "ok"
            ind_df.loc[: warmup_rows - 1, "data_status"] = "warmup"

            # Task 4: Diagnose NaN - separate expected (warmup) from errors
            nan_diagnosis = diagnose_nan_values(ind_df, warmup_rows)
            if nan_diagnosis["unexpected_nan"]:
                agg.add_warning(
                    f"Unexpected NaN in {len(nan_diagnosis['unexpected_nan'])} indicators"
                )

        if trim_warmup and not SKIP_WARMUP_TRIM and warmup_rows > 0:
            ind_df = ind_df.iloc[warmup_rows:].reset_index(drop=True)
            agg.set_extra("warmup_trimmed", warmup_rows)

            if len(ind_df) == 0:
                logger.warning("No data left after warmup trim")
                return 0

        # 3. Initialize schema manager
        schema_registry = IndicatorSchemaRegistry()

        # 4. Prepare DataFrame
        ind_df = _prepare_dataframe(ind_df, symbol, timeframe)
        await _ensure_indicator_monthly_partitions(session, ind_df)

        # 5. Load schema (cached)
        schema_info = await get_or_load_schema(
            session,
            load_db_columns_func=load_db_columns,
            reflect_table_func=reflect_indicators_table,
            get_numeric_columns_func=get_numeric_columns_from_table,
        )

        db_cols = schema_info.db_columns
        indicators_table = schema_info.indicators_table
        numeric_cols = schema_info.numeric_columns
        prom = get_prom_metrics()

        # 6. Filter columns by DB schema
        ind_df = filter_columns_by_schema(ind_df, db_cols)
        validate_required_fields(ind_df)

        # 7. Build batch data
        batch_data, skipped = build_batch_data(
            ind_df,
            symbol,
            timeframe,
            db_cols,
            seen_timestamps=seen_timestamps,
            on_duplicate=prom.record_duplicates,
        )
        if not batch_data:
            logger.warning("No valid data to insert")
            return 0

        if skipped > 0:
            agg.set_extra("skipped", skipped)

        # 8. Filter and normalize batch
        base_keys = ["symbol", "timeframe", "timestamp", "calculated_at"]
        batch_data = filter_batch_by_schema(batch_data, db_cols, base_keys)
        batch_data = normalize_record_names(batch_data, db_cols)

        # 9. Validate with schema manager
        validation = schema_registry.validate_data(batch_data)
        if not validation["valid"]:
            raise ValueError(f"Data validation failed: {validation['errors']}")

        validated_records = validation["mapped_records"]

        # 10. Transform for UPSERT
        validated_records = transform_records_for_upsert(
            validated_records,
            db_columns=db_cols,
            numeric_columns=numeric_cols,
        )

        # 11. Execute UPSERT with retry
        try:
            # Check state before (for diagnostics) - only in DEBUG mode
            count_before = None
            if should_log(LogCategory.DIAG, Verbosity.DEBUG):
                count_before, _ = await check_db_state(session, symbol, timeframe)

            with prom.upsert_timer(symbol, timeframe):
                saved_count = await execute_upsert_with_retry(
                    session=session,
                    indicators_table=indicators_table,
                    records=validated_records,
                    db_columns=db_cols,
                    pk=PK_FIELDS,
                    required_fields=schema_registry.get_required_fields(),
                )

            # Record rows written and batch size
            prom.record_rows_written(symbol, timeframe, saved_count)
            prom.record_batch_size(symbol, timeframe, len(validated_records))

            # Check state after (for diagnostics) - only in DEBUG mode
            if (
                should_log(LogCategory.DIAG, Verbosity.DEBUG)
                and count_before is not None
            ):
                count_after, _ = await check_db_state(session, symbol, timeframe)
                rows_added = (count_after or 0) - count_before
                agg.set_extra("rows_added", rows_added)

            agg.set_extra("saved", saved_count)
            agg.set_extra("records", len(validated_records))
            return saved_count

        except Exception as e:
            prom.record_upsert_failure(symbol, timeframe)
            logger.error(f"Database insertion failed: {e}")
            await session.rollback()
            raise


def _prepare_dataframe(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    """
    Prepare DataFrame for insertion.

    Args:
        df: Raw DataFrame
        symbol: Trading symbol
        timeframe: Timeframe

    Returns:
        Prepared DataFrame
    """
    return normalize_timestamp_column(
        add_service_fields(
            normalize_numeric_columns(sanitize_column_names(df)),
            symbol,
            timeframe,
        )
    )
