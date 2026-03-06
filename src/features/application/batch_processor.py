"""
Application layer: batch processing orchestration.

Currently a thin wrapper to preserve calc_indicators behavior.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.logging import get_logger

from ..domain.calculator import calculate_batch
from ..domain.strategy import get_max_lookback_for_strategies
from ..infrastructure.database import (
    ensure_columns_exist,
    fetch_latest_ts,
    fetch_ohlcv_df,
)
from ..utils.time_utils import timeframe_to_seconds
from .save import save_batch
from .save_dependencies import create_feature_save_dependencies

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)


async def process_dataframe(
    df_ohlcv: pd.DataFrame,
    available: set[str],
    *,
    volatility_normalize: bool = False,
) -> pd.DataFrame:
    """Process one OHLCV DataFrame and return calculated indicators."""
    return calculate_batch(
        df_ohlcv=df_ohlcv,
        available=available,
        volatility_normalize=volatility_normalize,
    )


async def process_single_pair(
    session, symbol: str, timeframe: str, available: set[str]
) -> tuple[bool, int, float, list[str]]:
    """
    Process a single symbol/timeframe pair.

    Uses incremental mode: loads data from max_ts - warmup_offset,
    where warmup_offset is derived from the maximum indicator lookback.
    """
    start_time = time.time()
    errors: list[str] = []

    try:
        # Get the latest calculated indicator timestamp in seconds.
        max_ts = await fetch_latest_ts(session, symbol, timeframe) or 0

        # Calculate the warmup offset from indicator lookback.
        max_lookback = get_max_lookback_for_strategies(list(available))
        # Add a 20% safety buffer.
        warmup_bars = int(max_lookback * 1.2)
        warmup_offset_sec = warmup_bars * timeframe_to_seconds(timeframe)

        # Derive since_ts including warmup coverage.
        since_ts = max(0, max_ts - warmup_offset_sec)

        logger.debug(
            f"Incremental range for {symbol} {timeframe}: max_ts={max_ts}, "
            f"warmup_bars={warmup_bars}, since_ts={since_ts}"
        )

        df = await fetch_ohlcv_df(session, symbol, timeframe, since_ts=since_ts)
        if df is None or len(df) < 20:
            return False, 0, time.time() - start_time, ["Insufficient data"]

        ind_df = calculate_batch(df, available=available, volatility_normalize=False)
        indicator_columns = [
            c
            for c in ind_df.columns
            if c not in ("open", "high", "low", "close", "volume", "ts")
        ]
        await ensure_columns_exist(session, "indicators", indicator_columns)

        save_deps = create_feature_save_dependencies(session)
        save_result = await save_batch(
            session=session,
            df=ind_df,
            symbol=symbol,
            timeframe=timeframe,
            repository=save_deps.repository,
            observer=save_deps.observer,
        )

        calculation_time = time.time() - start_time
        return True, int(save_result["rows_saved"]), calculation_time, errors

    except Exception as e:
        errors.append(str(e))
        return False, 0, time.time() - start_time, errors
