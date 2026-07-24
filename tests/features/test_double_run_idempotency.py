"""A4 (Roadmap Phase A): double-run idempotency test for the features DAG write path.

`insert_indicators` (src/features/infrastructure/persistence/inserter.py) is the
write path used by the features DAG (`ops/airflow/dags/features_calc.py`) to
persist rows into `indicators_p`. Running it twice with the same computed
features for the same symbol/timeframe/timestamp window must not create
duplicate rows or change the stored values on the second run.

Reads real OHLCV history (read-only) to get a realistic indicator vector, but
writes under a synthetic `TEST-*` symbol so it never touches a real
instrument's row in `indicators_p` - unlike a plain UPSERT test, writing to a
live production row and overwriting it based on a smaller lookback window
than the production DAG uses would silently degrade real data.
"""

from __future__ import annotations

from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.database import get_async_session
from src.features.core import compute_features

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_SOURCE_SYMBOL = "BTC-USDT-SWAP"
_TIMEFRAME = "1D"


def _skip_if_db_unavailable(exc: Exception) -> None:
    if isinstance(exc, ConnectionRefusedError | OSError | OperationalError):
        pytest.skip(f"Database is unavailable for double-run idempotency test: {exc}")
    message = str(exc).lower()
    if "connection refused" in message or "could not connect" in message:
        pytest.skip(f"Database is unavailable for double-run idempotency test: {exc}")


async def test_insert_indicators_double_run_is_idempotent() -> None:
    """Covers the features DAG write path (insert_indicators -> indicators_p)."""
    from src.features.infrastructure.persistence.inserter import (
        insert_indicators as insert_indicators_v2,
    )
    from src.features.infrastructure.persistence.schema_checker import (
        reflect_indicators_table,
    )

    test_symbol = f"TEST-DOUBLE-RUN-{uuid4().hex[:8]}"

    try:
        async for session in get_async_session():
            ohlcv_result = await session.execute(
                text(
                    """
                    SELECT open, high, low, close, volume, timestamp
                    FROM swap_ohlcv_p
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    ORDER BY timestamp ASC
                    """
                ),
                {"symbol": _SOURCE_SYMBOL, "timeframe": _TIMEFRAME},
            )
            rows = ohlcv_result.fetchall()
            if len(rows) < 60:
                pytest.skip(
                    f"Not enough OHLCV data for {_SOURCE_SYMBOL} {_TIMEFRAME} "
                    "to compute a stable double-run fixture"
                )

            df_ohlcv = pd.DataFrame(
                [
                    {
                        "open": float(r.open),
                        "high": float(r.high),
                        "low": float(r.low),
                        "close": float(r.close),
                        "volume": float(r.volume),
                        "timestamp": r.timestamp,
                    }
                    for r in rows
                ]
            )

            features_df = compute_features(df_ohlcv, specs=None)
            assert features_df is not None and len(features_df) > 0

            last_ts = int(features_df["ts"].iloc[-1])
            last_ts_ms = last_ts if last_ts > 10**12 else last_ts * 1000
            one_row = features_df.tail(1).copy()

            await reflect_indicators_table(session)

            try:
                saved_first_run = await insert_indicators_v2(
                    session=session,
                    ind_df=one_row,
                    symbol=test_symbol,
                    timeframe=_TIMEFRAME,
                    trim_warmup=False,
                )
                await session.commit()

                check_query = text(
                    """
                    SELECT rsi_14, ema_8, sma_20
                    FROM indicators_p
                    WHERE symbol = :symbol AND timeframe = :timeframe AND timestamp = :ts
                    """
                )
                result_after_first = await session.execute(
                    check_query,
                    {"symbol": test_symbol, "timeframe": _TIMEFRAME, "ts": last_ts_ms},
                )
                row_after_first = result_after_first.mappings().one()

                saved_second_run = await insert_indicators_v2(
                    session=session,
                    ind_df=one_row,
                    symbol=test_symbol,
                    timeframe=_TIMEFRAME,
                    trim_warmup=False,
                )
                await session.commit()

                count_result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM indicators_p
                        WHERE symbol = :symbol AND timeframe = :timeframe AND timestamp = :ts
                        """
                    ),
                    {"symbol": test_symbol, "timeframe": _TIMEFRAME, "ts": last_ts_ms},
                )
                row_count_after_second = count_result.scalar_one()

                result_after_second = await session.execute(
                    check_query,
                    {"symbol": test_symbol, "timeframe": _TIMEFRAME, "ts": last_ts_ms},
                )
                row_after_second = result_after_second.mappings().one()

                assert saved_first_run == 1
                assert saved_second_run == 1
                # No duplicate row created by the second, identical run.
                assert row_count_after_second == 1
                # Values are unchanged between the two runs (same input -> same output).
                assert dict(row_after_first) == dict(row_after_second)
            finally:
                await session.execute(
                    text(
                        """
                        DELETE FROM indicators_p
                        WHERE symbol = :symbol AND timeframe = :timeframe
                        """
                    ),
                    {"symbol": test_symbol, "timeframe": _TIMEFRAME},
                )
                await session.commit()
            break
    except Exception as exc:
        _skip_if_db_unavailable(exc)
        raise
