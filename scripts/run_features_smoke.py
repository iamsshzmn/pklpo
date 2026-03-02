import asyncio
import sys
from argparse import ArgumentParser

from sqlalchemy import text

from src.database import get_async_session
from src.features.core import compute_features
from src.features.infrastructure.database import (
    ensure_columns_exist,
    fetch_ohlcv_df,
    insert_indicators,
)
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS


async def run(symbol: str, timeframe: str, limit: int, since_ts: int | None):
    async for session in get_async_session():
        print(f"Fetching OHLCV for {symbol} {timeframe} ...")
        df = await fetch_ohlcv_df(
            session, symbol, timeframe, since_ts=since_ts, limit=limit
        )
        if df is None or len(df) == 0:
            print("NO DATA: OHLCV not found")
            return 2
        print(f"OHLCV rows: {len(df)}; ts range: {df['ts'].min()} .. {df['ts'].max()}")

        print("Calculating features ...")
        features = compute_features(
            df, available=set(AVAILABLE_INDICATORS), volatility_normalize=False
        )
        indicator_columns = [
            c
            for c in features.columns
            if c not in ("open", "high", "low", "close", "volume", "ts")
        ]
        print(f"Calculated columns: {len(indicator_columns)} indicators")

        print("Ensuring indicator columns exist ...")
        await ensure_columns_exist(session, "indicators", indicator_columns)

        print("Upserting indicators ...")
        n = await insert_indicators(session, features, symbol, timeframe)
        print(f"UPSERTED rows: {n}")

        # Stats from indicators
        print("Reading indicators stats ...")
        q = await session.execute(
            text(
                "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM indicators "
                "WHERE symbol=:s AND timeframe=:t"
            ),
            {"s": symbol, "t": timeframe},
        )
        cnt, tmin, tmax = q.fetchone()
        print(f"Indicators count: {cnt}; ts(ms) range: {tmin} .. {tmax}")

        sel = await session.execute(
            text(
                "SELECT timestamp, sma_20, ema_12, rsi_14, macd, atr_14, obv "
                "FROM indicators WHERE symbol=:s AND timeframe=:t "
                "ORDER BY timestamp DESC LIMIT 3"
            ),
            {"s": symbol, "t": timeframe},
        )
        rows = sel.fetchall()
        print("Last 3 rows (key columns):")
        for r in rows:
            print(r)

        return 0


def main(argv: list[str]) -> int:
    parser = ArgumentParser(description="Run features smoke calculation and upsert")
    parser.add_argument("symbol", help="Instrument symbol, e.g., BTC-USDT-SWAP")
    parser.add_argument("timeframe", help="Timeframe, e.g., 1D/1H/15m/1m")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument(
        "--since", type=int, default=None, help="Since timestamp in seconds (optional)"
    )
    args = parser.parse_args(argv)

    return asyncio.run(run(args.symbol, args.timeframe, args.limit, args.since))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
