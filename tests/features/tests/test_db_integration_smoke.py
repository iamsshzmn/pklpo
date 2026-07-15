import os
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.database import get_async_session
from src.features.core import compute_features
from src.features.infrastructure.database import (
    ensure_columns_exist,
    fetch_ohlcv_df,
    insert_indicators,
)
from src.features.registry import AVAILABLE_INDICATORS

pytestmark = pytest.mark.asyncio


def _skip_if_db_unavailable(exc: Exception) -> None:
    """Treat unavailable Postgres as an environmental skip for smoke tests."""
    if isinstance(exc, ConnectionRefusedError | OSError | OperationalError):
        pytest.skip(f"Database is unavailable for smoke test: {exc}")

    message = str(exc).lower()
    if "connection refused" in message or "could not connect" in message:
        pytest.skip(f"Database is unavailable for smoke test: {exc}")


async def test_features_pipeline_smoke_btc_1d():
    """Smoke test: read OHLCV, compute features, persist one row to indicators."""
    if not (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN")):
        pytest.skip("DATABASE_URL is not set")

    symbol = "BTC-USDT-SWAP"
    timeframe = "1D"

    try:
        async for session in get_async_session():
            df = await fetch_ohlcv_df(
                session, symbol, timeframe, since_ts=None, limit=200
            )
            if df is None or len(df) < 50:
                pytest.skip("Not enough OHLCV data in swap_ohlcv_p/ohlcv for BTC 1D")

            requested = {"sma_20", "ema_12", "rsi_14", "macd", "atr_14", "obv"}
            available = set(AVAILABLE_INDICATORS)
            to_calc = requested & available
            features = compute_features(
                df,
                available=to_calc if to_calc else available,
                volatility_normalize=False,
            )
            assert len(features) == len(df)

            last_row_ts = int(features["ts"].iloc[-1])
            last_row_ts_ms = last_row_ts if last_row_ts > 10**12 else last_row_ts * 1000
            one_row = features.tail(1)

            indicator_columns = [
                c
                for c in one_row.columns
                if c not in ("open", "high", "low", "close", "volume", "ts")
            ]
            await ensure_columns_exist(session, "indicators", indicator_columns)
            n = await insert_indicators(session, one_row, symbol, timeframe)
            assert n == 1

            non_null_cols = [
                c for c in indicator_columns if pd.notna(one_row[c].iloc[0])
            ]
            assert non_null_cols, "No non-null indicators on the last row"

            check_col = non_null_cols[0]
            q = await session.execute(
                text(
                    f"SELECT {check_col} FROM indicators "
                    "WHERE symbol=:s AND timeframe=:t AND timestamp=:ts"
                ),
                {"s": symbol, "t": timeframe, "ts": last_row_ts_ms},
            )
            row = q.first()
            assert row is not None and row[0] is not None, (
                f"Column {check_col} is NULL in DB for last row"
            )
            break
    except Exception as exc:
        _skip_if_db_unavailable(exc)
        raise


@pytest.mark.integration
async def test_upsert_full_pipeline_with_validation():
    """Smoke test for full DB pipeline with type validation before UPSERT."""
    if not (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN")):
        pytest.skip("DATABASE_URL is not set")

    symbol = "BTC-USDT-SWAP"
    timeframe = "1m"
    limit = 10

    try:
        async for session in get_async_session():
            query = text(
                """
                SELECT open, high, low, close, volume, timestamp
                FROM swap_ohlcv_p
                WHERE symbol = :symbol AND timeframe = :timeframe
                ORDER BY timestamp DESC
                LIMIT :limit
                """
            )
            result = await session.execute(
                query, {"symbol": symbol, "timeframe": timeframe, "limit": limit}
            )
            rows = result.fetchall()

            if not rows:
                pytest.skip(f"No OHLCV data for {symbol} {timeframe}")

            df_ohlcv = pd.DataFrame(
                [
                    {
                        "open": float(row.open),
                        "high": float(row.high),
                        "low": float(row.low),
                        "close": float(row.close),
                        "volume": float(row.volume),
                        "timestamp": row.timestamp,
                    }
                    for row in reversed(rows)
                ]
            )
            assert len(df_ohlcv) > 0, "No OHLCV data loaded"

            features_df = compute_features(df_ohlcv, specs=None)
            assert features_df is not None and len(features_df) > 0, (
                "No features computed"
            )

            from src.features.infrastructure.persistence.inserter import (
                insert_indicators as insert_indicators_v2,
            )
            from src.features.infrastructure.persistence.schema_checker import (
                reflect_indicators_table,
            )

            await reflect_indicators_table(session)
            saved_count = await insert_indicators_v2(
                session=session,
                ind_df=features_df,
                symbol=symbol,
                timeframe=timeframe,
            )
            assert saved_count > 0, f"Expected saved_count > 0, got {saved_count}"

            check_query = text(
                """
                SELECT ultosc, stochrsi_k, cdl_doji, willr, rsi_14
                FROM indicators
                WHERE symbol = :symbol AND timeframe = :timeframe
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
            check_result = await session.execute(
                check_query, {"symbol": symbol, "timeframe": timeframe}
            )
            check_row = check_result.first()

            if check_row:
                for i, col_name in enumerate(
                    ["ultosc", "stochrsi_k", "cdl_doji", "willr", "rsi_14"]
                ):
                    val = check_row[i]
                    if val is not None:
                        assert isinstance(val, int | float | Decimal), (
                            f"Column {col_name} has wrong type: {type(val)}"
                        )
            break
    except Exception as exc:
        _skip_if_db_unavailable(exc)
        raise
