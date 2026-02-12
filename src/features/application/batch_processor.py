"""
Application layer: batch processing orchestration.

Пока тонкая обертка, чтобы не менять поведение calc_indicators.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.logging import get_logger
from src.utils.retry import RetryConfig

from ..domain.calculator import calculate_batch
from ..domain.strategy import get_max_lookback_for_strategies
from ..infrastructure.database import (
    ensure_columns_exist,
    fetch_latest_ts,
    fetch_ohlcv_df,
    insert_indicators,
)
from ..utils.time_utils import timeframe_to_seconds

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)


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
    """
    Обработка одной пары symbol/timeframe.

    Использует инкрементный режим: загружает данные с max_ts - warmup_offset,
    где warmup_offset рассчитывается на основе максимального lookback индикаторов.
    """
    start_time = time.time()
    errors: list[str] = []

    try:
        # Получаем max_ts последнего рассчитанного индикатора (в секундах)
        max_ts = await fetch_latest_ts(session, symbol, timeframe) or 0

        # Рассчитываем warmup offset на основе lookback индикаторов
        max_lookback = get_max_lookback_for_strategies(list(available))
        # Добавляем 20% буфер для надёжности
        warmup_bars = int(max_lookback * 1.2)
        warmup_offset_sec = warmup_bars * timeframe_to_seconds(timeframe)

        # Вычисляем since_ts с учётом warmup
        since_ts = max(0, max_ts - warmup_offset_sec)

        logger.debug(
            f"Инкремент для {symbol} {timeframe}: max_ts={max_ts}, "
            f"warmup_bars={warmup_bars}, since_ts={since_ts}"
        )

        df = await fetch_ohlcv_df(session, symbol, timeframe, since_ts=since_ts)
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
        from src.utils.retry import RetryableOperation

        retry_config = RetryConfig.from_settings(preset="db")
        retry_op = RetryableOperation(retry_config)
        await retry_op.execute_async(
            insert_indicators, session, ind_df, symbol, timeframe
        )

        calculation_time = time.time() - start_time
        return True, len(ind_df), calculation_time, errors

    except Exception as e:
        errors.append(str(e))
        return False, 0, time.time() - start_time, errors
