"""
Application layer: batch processing orchestration.

Пока тонкая обертка, чтобы не менять поведение calc_indicators.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from ..domain.calculator import calculate_batch
from ..infrastructure.database import (
    ensure_columns_exist,
    fetch_latest_ts,
    fetch_ohlcv_df,
    insert_indicators,
)

if TYPE_CHECKING:
    import pandas as pd


async def process_dataframe(
    df_ohlcv: pd.DataFrame,
    available: set[str],
    *,
    volatility_normalize: bool = False,
) -> pd.DataFrame:
    """Обработать один датафрейм OHLCV и вернуть рассчитанные индикаторы."""
    return calculate_batch(
        df_ohlcv=df_ohlcv,
        available=available,
        volatility_normalize=volatility_normalize,
    )


async def process_single_pair(
    session, symbol: str, timeframe: str, available: set[str]
) -> tuple[bool, int, float, list[str]]:
    """Перенос логики из calc_indicators.process_single_pair без изменения поведения."""
    start_time = time.time()
    errors: list[str] = []

    try:
        max_ts = await fetch_latest_ts(session, symbol, timeframe) or 0
        df = await fetch_ohlcv_df(session, symbol, timeframe, since_ts=max_ts)
        if df is None or len(df) < 20:
            return False, 0, time.time() - start_time, ["Недостаточно данных"]

        ind_df = calculate_batch(df, available=available, volatility_normalize=False)
        indicator_columns = [
            c
            for c in ind_df.columns
            if c not in ("open", "high", "low", "close", "volume", "ts")
        ]
        await ensure_columns_exist(session, "indicators", indicator_columns)

        # Вставка с retry/backoff для транзиентных ошибок БД
        delay = 0.2
        attempts = 0
        while True:
            try:
                await insert_indicators(session, ind_df, symbol, timeframe)
                break
            except Exception:  # транзиентные ошибки БД/сети
                attempts += 1
                if attempts >= 5:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * 2, 2.0)

        calculation_time = time.time() - start_time
        return True, len(ind_df), calculation_time, errors

    except Exception as e:
        errors.append(str(e))
        return False, 0, time.time() - start_time, errors
