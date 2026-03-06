"""
Save module for features — thin orchestration layer.

Loads calculated indicators from parquet files and saves them to PostgreSQL
through an injected IndicatorRepository adapter.

Refactored (Stage 2 / repository boundary):
- All private persistence logic (_prepare_batch_data, _save_batch_*, COPY FROM)
  moved to infrastructure/persistence/ (inserter.py, data_transformer.py, etc.)
- save_batch() and save_parquet_to_pg() are now thin orchestration functions
- retry is handled inside infrastructure/persistence/upsert_executor.py
- persistence adapter is injected by the caller/composition root
"""

from __future__ import annotations

import gc
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from src.config import FeaturesSettings, get_settings

from ..infrastructure.persistence.row_processor import build_batch_data
from ..utils.memlog import force_cleanup
from .save_validation import create_feature_save_validator

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..domain.protocols import (
        FeatureSaveObserver,
        FeatureSaveValidator,
        IndicatorRepository,
    )


async def save_batch(
    session: AsyncSession,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    *,
    repository: IndicatorRepository,
    observer: FeatureSaveObserver,
    config: FeaturesSettings | None = None,
    snapshot_id: str | None = None,
    algorithm_version: str = "1.0.0",
    commit: bool = True,
) -> dict[str, Any]:
    """
    Save a batch of indicator data to database.

    Delegates actual persistence to an IndicatorRepository adapter.

    Args:
        session: Database session
        df: DataFrame with indicators
        symbol: Trading symbol
        timeframe: Timeframe
        config: Features configuration (from get_settings().features)
        snapshot_id: Optional snapshot ID for ML reproducibility
        algorithm_version: Algorithm version for ML reproducibility
        repository: Persistence adapter (DI)
        observer: Observability adapter (DI)
        commit: Whether this use case should finalize the transaction

    Returns:
        Dictionary with save results
    """
    if config is None:
        config = get_settings().features

    if df is None or len(df) == 0:
        return {"success": False, "error": "Empty DataFrame", "rows_saved": 0}

    with observer.observe(
        operation="save_batch",
        symbol=symbol,
        timeframe=timeframe,
        df=df,
        log_memory=config.log_memory,
    ) as observation:
        try:
            rows_saved = await repository.save_batch_from_df(
                df=df,
                symbol=symbol,
                timeframe=timeframe,
            )
            if commit:
                await session.commit()
        except Exception as e:
            observation.record_error(e)
            await session.rollback()
            raise

        if config.clear_intermediate_objects:
            force_cleanup(df)
        if config.force_gc_after_chunk:
            gc.collect()

        observation.record_success(rows_processed=len(df), rows_saved=rows_saved)

        return {
            "success": True,
            "rows_processed": len(df),
            "rows_saved": rows_saved,
            "committed": commit,
            "saved_at": datetime.utcnow().isoformat(),
        }


async def save_parquet_to_pg(
    session: AsyncSession,
    parquet_path: str,
    symbol: str,
    timeframe: str,
    *,
    repository: IndicatorRepository,
    validator: FeatureSaveValidator,
    observer: FeatureSaveObserver,
    batch_size: int = 1000,
    validate_before_save: bool = True,
    config: FeaturesSettings | None = None,
) -> dict[str, Any]:
    """
    Load parquet file and save indicators to PostgreSQL.

    Args:
        session: Database session
        parquet_path: Path to parquet file
        symbol: Trading symbol
        timeframe: Timeframe
        repository: Persistence adapter (DI)
        validator: Pre-save validator (DI)
        observer: Observability adapter (DI)
        batch_size: Unused (retained for API compatibility); persistence layer
                    handles batching internally
        validate_before_save: Whether to validate data before saving

    Returns:
        Dictionary with save results
    """
    try:
        df = pd.read_parquet(parquet_path)

        if len(df) == 0:
            raise ValueError("Parquet file is empty")

        with observer.observe(
            operation="save_parquet_to_pg",
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            log_memory=bool(config and config.log_memory),
        ) as observation:
            if validate_before_save:
                validation_result = validator.validate_save_dataframe(
                    df=df,
                    symbol=symbol,
                    timeframe=timeframe,
                )
                if not validation_result["valid"]:
                    raise ValueError(
                        f"Data validation failed: {validation_result['errors']}"
                    )

            rows_saved = await repository.save_batch_from_df(
                df=df,
                symbol=symbol,
                timeframe=timeframe,
            )
            await session.commit()
            observation.record_success(rows_processed=len(df), rows_saved=rows_saved)

        metadata = df.attrs if hasattr(df, "attrs") else {}

        return {
            "success": True,
            "parquet_path": parquet_path,
            "symbol": symbol,
            "timeframe": timeframe,
            "rows_processed": len(df),
            "rows_saved": rows_saved,
            "batches_processed": 1,
            "metadata": metadata,
            "saved_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        await session.rollback()
        return {
            "success": False,
            "error": str(e),
            "parquet_path": parquet_path,
            "symbol": symbol,
            "timeframe": timeframe,
        }


# =============================================================================
# INFRASTRUCTURE HEALTH CHECKS
# =============================================================================


async def validate_database_connection(
    session: AsyncSession,
    repository: IndicatorRepository,
) -> dict[str, Any]:
    """Validate database connection and table structure."""
    return await repository.validate_connection()


async def verify_database_integrity(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    repository: IndicatorRepository,
) -> dict[str, Any]:
    """Verify database integrity after batch operations."""
    return await repository.verify_integrity(symbol=symbol, timeframe=timeframe)


def _prepare_batch_data(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> list[dict[str, Any]]:
    """Legacy helper retained for old tests around batch preparation."""
    working_df = df.copy()
    if "timestamp" not in working_df.columns and "ts" in working_df.columns:
        working_df["timestamp"] = (
            pd.to_numeric(working_df["ts"], errors="coerce") * 1000
        )

    db_cols = set(working_df.columns) - {"ts"}
    batch_data, _ = build_batch_data(
        ind_df=working_df,
        symbol=symbol,
        timeframe=timeframe,
        db_cols=db_cols,
    )
    return batch_data


def _validate_dataframe(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> dict[str, Any]:
    """Legacy helper retained for old tests around save validation."""
    validator = create_feature_save_validator()
    return validator.validate_save_dataframe(df=df, symbol=symbol, timeframe=timeframe)
