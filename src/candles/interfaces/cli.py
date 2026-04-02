"""CLI for swap candles synchronization and diagnostics.

Consolidated candles diagnostics and sync commands on the canonical interface.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from src.candles.interfaces.swap_sync import sync_swap_candles
from src.utils.session_utils import get_db_session

# ---------------------------------------------------------------------------
# Query functions (from candles_cli_service.py)
# ---------------------------------------------------------------------------

async def fetch_swap_status() -> dict[str, Any] | None:
    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT
                    COUNT(DISTINCT symbol) as total_symbols,
                    COUNT(DISTINCT timeframe) as total_timeframes,
                    COUNT(*) as total_records,
                    MIN(timestamp) as earliest_timestamp,
                    MAX(timestamp) as latest_timestamp,
                    MIN(fetched_at) as earliest_fetch,
                    MAX(fetched_at) as latest_fetch
                FROM swap_ohlcv_p
                """
            )
        )
        stats = result.fetchone()
        if not stats or stats[0] == 0:
            return None

        result = await session.execute(
            text(
                """
                SELECT symbol, COUNT(*) as records,
                       COUNT(DISTINCT timeframe) as timeframes,
                       MAX(fetched_at) as last_update
                FROM swap_ohlcv_p
                GROUP BY symbol ORDER BY records DESC LIMIT 10
                """
            )
        )
        symbols = result.fetchall()

        result = await session.execute(
            text(
                """
                SELECT timeframe, COUNT(*) as records,
                       COUNT(DISTINCT symbol) as symbols
                FROM swap_ohlcv_p
                GROUP BY timeframe ORDER BY records DESC
                """
            )
        )
        timeframes = result.fetchall()

    return {"stats": stats, "symbols": symbols, "timeframes": timeframes}


async def fetch_symbol_details(symbol: str) -> dict[str, Any] | None:
    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT symbol, COUNT(DISTINCT timeframe), COUNT(*),
                       MIN(timestamp), MAX(timestamp),
                       MIN(fetched_at), MAX(fetched_at),
                       AVG(volume),
                       AVG(COALESCE(funding_rate, 0)),
                       COUNT(CASE WHEN funding_rate IS NOT NULL THEN 1 END),
                       COUNT(CASE WHEN open_interest IS NOT NULL THEN 1 END)
                FROM swap_ohlcv_p WHERE symbol = :symbol GROUP BY symbol
                """
            ),
            {"symbol": symbol},
        )
        info = result.fetchone()
        if not info:
            return None

        result = await session.execute(
            text(
                """
                SELECT timeframe, COUNT(*), MIN(timestamp), MAX(timestamp),
                       MAX(fetched_at)
                FROM swap_ohlcv_p WHERE symbol = :symbol
                GROUP BY timeframe ORDER BY timeframe
                """
            ),
            {"symbol": symbol},
        )
        timeframes = result.fetchall()

    return {"info": info, "timeframes": timeframes}


async def cleanup_swap_data(days: int) -> tuple[int, int]:
    cutoff_timestamp = int(
        (datetime.now(UTC) - timedelta(days=days)).timestamp() * 1000
    )
    async with get_db_session() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM swap_ohlcv_p WHERE timestamp < :t"),
            {"t": cutoff_timestamp},
        )
        count = int(result.scalar() or 0)
        if count == 0:
            return 0, 0

        result = await session.execute(
            text("DELETE FROM swap_ohlcv_p WHERE timestamp < :t"),
            {"t": cutoff_timestamp},
        )
        await session.commit()
        return count, int(result.rowcount or 0)


async def export_swap_symbol_data(
    symbol: str, timeframes: list[str] | None = None
) -> list[dict[str, Any]]:
    base_query = """
        SELECT symbol, timeframe, timestamp, open, high, low, close, volume,
               vol_ccy, vol_usd, funding_rate, open_interest,
               long_short_ratio, long_account_ratio, short_account_ratio,
               top_long_short_ratio, top_long_account_ratio, top_short_account_ratio,
               fetched_at
        FROM swap_ohlcv_p WHERE symbol = :symbol
    """
    params: dict[str, Any] = {"symbol": symbol}
    if timeframes:
        placeholders = []
        for i, tf in enumerate(timeframes):
            key = f"tf_{i}"
            placeholders.append(f":{key}")
            params[key] = tf
        base_query += f" AND timeframe IN ({', '.join(placeholders)})"
    base_query += " ORDER BY timeframe, timestamp"

    async with get_db_session() as session:
        result = await session.execute(text(base_query), params)
        rows = result.fetchall()

    cols = [
        "symbol", "timeframe", "timestamp", "open", "high", "low", "close",
        "volume", "vol_ccy", "vol_usd", "funding_rate", "open_interest",
        "long_short_ratio", "long_account_ratio", "short_account_ratio",
        "top_long_short_ratio", "top_long_account_ratio", "top_short_account_ratio",
        "fetched_at",
    ]
    out: list[dict[str, Any]] = []
    for row in rows:
        record: dict[str, Any] = {}
        for idx, col in enumerate(cols):
            val = row[idx]
            if col == "fetched_at":
                record[col] = val.isoformat() if val else None
            elif col in ("symbol", "timeframe", "timestamp"):
                record[col] = val
            else:
                record[col] = float(val) if val is not None else None
        out.append(record)
    return out


# ---------------------------------------------------------------------------
# CLI command handlers
# ---------------------------------------------------------------------------

async def _sync_all(
    symbols: list[str] | None,
    timeframes: list[str] | None,
    config: dict[str, Any] | None,
) -> None:
    print("Starting swap candles sync...")
    try:
        stats = await sync_swap_candles(symbols, timeframes, config)
        print("Sync completed")
        print(f"  symbols: {stats['total_symbols']}")
        print(f"  candles: {stats['total_candles_synced']}")
        print(f"  errors: {stats['errors_count']}")
        print(f"  duration_sec: {stats['duration_seconds']:.2f}")
        print(f"  candles_per_sec: {stats['candles_per_second']:.2f}")
    except Exception as e:
        print(f"Sync failed: {e}")
        sys.exit(1)


async def _show_status() -> None:
    try:
        payload = await fetch_swap_status()
        if not payload:
            print("No swap data found")
            return

        stats = payload["stats"]
        print("SWAP DATA STATUS")
        print("=" * 60)
        print(f"symbols: {stats[0]}")
        print(f"timeframes: {stats[1]}")
        print(f"records: {stats[2]:,}")

        if stats[3] and stats[4]:
            earliest = datetime.fromtimestamp(stats[3] / 1000, tz=UTC)
            latest = datetime.fromtimestamp(stats[4] / 1000, tz=UTC)
            print(f"period: {earliest:%Y-%m-%d %H:%M} - {latest:%Y-%m-%d %H:%M}")

        if stats[6]:
            print(f"last_update: {stats[6]:%Y-%m-%d %H:%M:%S}")

        print("\nTOP-10 SYMBOLS")
        print("-" * 60)
        for row in payload["symbols"]:
            print(f"{row[0]:<15} {row[1]:<10,} {row[2]:<12} {row[3]:%Y-%m-%d %H:%M}")

        print("\nTIMEFRAME STATS")
        print("-" * 40)
        for row in payload["timeframes"]:
            print(f"{row[0]:<12} {row[1]:<10,} {row[2]}")
    except Exception as e:
        print(f"Status failed: {e}")


async def _show_details(symbol: str) -> None:
    try:
        payload = await fetch_symbol_details(symbol)
        if not payload:
            print(f"No data for symbol {symbol}")
            return

        info = payload["info"]
        print(f"DETAILS: {symbol}")
        print("=" * 60)
        print(f"timeframes: {info[1]}")
        print(f"records: {info[2]:,}")

        if info[3] and info[4]:
            earliest = datetime.fromtimestamp(info[3] / 1000, tz=UTC)
            latest = datetime.fromtimestamp(info[4] / 1000, tz=UTC)
            print(f"period: {earliest:%Y-%m-%d %H:%M} - {latest:%Y-%m-%d %H:%M}")

        if info[6]:
            print(f"last_update: {info[6]:%Y-%m-%d %H:%M:%S}")

        print(f"avg_volume: {info[7]:.2f}")
        print(f"avg_funding_rate: {info[8]:.6f}")
        print(f"funding_records: {info[9]:,}")
        print(f"open_interest_records: {info[10]:,}")

        print("\nTIMEFRAME BREAKDOWN")
        print("-" * 70)
        for tf in payload["timeframes"]:
            earliest = datetime.fromtimestamp(tf[2] / 1000, tz=UTC)
            latest = datetime.fromtimestamp(tf[3] / 1000, tz=UTC)
            period = f"{earliest:%Y-%m-%d} - {latest:%Y-%m-%d}"
            print(f"{tf[0]:<12} {tf[1]:<10,} {period:<30} {tf[4]:%Y-%m-%d %H:%M}")
    except Exception as e:
        print(f"Details failed: {e}")


async def _cleanup(days: int) -> None:
    try:
        count, deleted = await cleanup_swap_data(days)
        if count == 0:
            print(f"No data older than {days} days")
            return
        print(f"Deleting {count:,} rows older than {days} days...")
        print(f"Deleted {deleted:,} rows")
    except Exception as e:
        print(f"Cleanup failed: {e}")


async def _export(symbol: str, output_file: str, timeframes: list[str] | None) -> None:
    try:
        data = await export_swap_symbol_data(symbol, timeframes)
        if not data:
            print(f"No data for symbol {symbol}")
            return

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        print(f"Exported {len(data):,} rows to {output_file}")
    except Exception as e:
        print(f"Export failed: {e}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="CLI for swap candles")
    subparsers = parser.add_subparsers(dest="command", help="commands")

    sync_parser = subparsers.add_parser("sync", help="sync swap candles")
    sync_parser.add_argument("--symbols", nargs="+", help="specific symbols")
    sync_parser.add_argument("--timeframes", nargs="+", help="specific timeframes")
    sync_parser.add_argument("--config", help="JSON config file")

    subparsers.add_parser("status", help="show status")

    details_parser = subparsers.add_parser("details", help="show symbol details")
    details_parser.add_argument("symbol", help="target symbol")

    cleanup_parser = subparsers.add_parser("cleanup", help="delete old data")
    cleanup_parser.add_argument("--days", type=int, default=30, help="days threshold")

    export_parser = subparsers.add_parser("export", help="export symbol data")
    export_parser.add_argument("symbol", help="target symbol")
    export_parser.add_argument("output", help="output json file")
    export_parser.add_argument("--timeframes", nargs="+", help="specific timeframes")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    config = None
    if hasattr(args, "config") and args.config:
        try:
            with open(args.config, encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Failed to load config: {e}")
            return

    if args.command == "sync":
        asyncio.run(_sync_all(args.symbols, args.timeframes, config))
    elif args.command == "status":
        asyncio.run(_show_status())
    elif args.command == "details":
        asyncio.run(_show_details(args.symbol))
    elif args.command == "cleanup":
        asyncio.run(_cleanup(args.days))
    elif args.command == "export":
        asyncio.run(_export(args.symbol, args.output, args.timeframes))


if __name__ == "__main__":
    main()
