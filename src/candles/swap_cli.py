#!/usr/bin/env python3
"""CLI for swap candles synchronization and diagnostics."""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Any

from src.candles.candles_cli_service import (
    cleanup_swap_data,
    export_swap_symbol_data,
    fetch_swap_status,
    fetch_symbol_details,
)
from src.candles.infrastructure.adapters import build_market_data_adapter
from src.candles.interfaces.swap_sync import sync_swap_candles
from src.candles.parity_check import (
    ParityGate,
    evaluate_parity_gate,
    run_adapter_parity_check,
)


async def sync_all_swap(
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    config: dict[str, Any] | None = None,
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


async def sync_specific_symbols(
    symbols: list[str], timeframes: list[str] | None = None
) -> None:
    print(f"Sync symbols: {', '.join(symbols)}")
    try:
        stats = await sync_swap_candles(symbols, timeframes)
        print("Sync completed")
        for symbol, result in stats["results_by_symbol"].items():
            print(f"  {symbol}: {sum(result.values())} candles")
    except Exception as e:
        print(f"Sync failed: {e}")
        sys.exit(1)


async def show_swap_status() -> None:
    try:
        payload = await fetch_swap_status()
        if not payload:
            print("No swap data found")
            return

        stats = payload["stats"]
        symbols = payload["symbols"]
        timeframes = payload["timeframes"]

        print("SWAP DATA STATUS")
        print("=" * 60)
        print(f"symbols: {stats[0]}")
        print(f"timeframes: {stats[1]}")
        print(f"records: {stats[2]:,}")

        if stats[3] and stats[4]:
            earliest = datetime.fromtimestamp(stats[3] / 1000)
            latest = datetime.fromtimestamp(stats[4] / 1000)
            print(f"period: {earliest:%Y-%m-%d %H:%M} - {latest:%Y-%m-%d %H:%M}")

        if stats[6]:
            print(f"last_update: {stats[6]:%Y-%m-%d %H:%M:%S}")

        print("\nTOP-10 SYMBOLS")
        print("-" * 60)
        print(f"{'symbol':<15} {'records':<10} {'timeframes':<12} {'last_update'}")
        print("-" * 60)
        for row in symbols:
            print(f"{row[0]:<15} {row[1]:<10,} {row[2]:<12} {row[3]:%Y-%m-%d %H:%M}")

        print("\nTIMEFRAME STATS")
        print("-" * 40)
        print(f"{'timeframe':<12} {'records':<10} {'symbols'}")
        print("-" * 40)
        for row in timeframes:
            print(f"{row[0]:<12} {row[1]:<10,} {row[2]}")
    except Exception as e:
        print(f"Status failed: {e}")


async def show_symbol_details(symbol: str) -> None:
    try:
        payload = await fetch_symbol_details(symbol)
        if not payload:
            print(f"No data for symbol {symbol}")
            return

        info = payload["info"]
        timeframes = payload["timeframes"]

        print(f"DETAILS: {symbol}")
        print("=" * 60)
        print(f"timeframes: {info[1]}")
        print(f"records: {info[2]:,}")

        if info[3] and info[4]:
            earliest = datetime.fromtimestamp(info[3] / 1000)
            latest = datetime.fromtimestamp(info[4] / 1000)
            print(f"period: {earliest:%Y-%m-%d %H:%M} - {latest:%Y-%m-%d %H:%M}")

        if info[6]:
            print(f"last_update: {info[6]:%Y-%m-%d %H:%M:%S}")

        print(f"avg_volume: {info[7]:.2f}")
        print(f"avg_funding_rate: {info[8]:.6f}")
        print(f"funding_records: {info[9]:,}")
        print(f"open_interest_records: {info[10]:,}")

        print("\nTIMEFRAME BREAKDOWN")
        print("-" * 70)
        print(f"{'timeframe':<12} {'records':<10} {'period':<30} {'last_update'}")
        print("-" * 70)
        for tf in timeframes:
            earliest = datetime.fromtimestamp(tf[2] / 1000)
            latest = datetime.fromtimestamp(tf[3] / 1000)
            period = f"{earliest:%Y-%m-%d} - {latest:%Y-%m-%d}"
            print(f"{tf[0]:<12} {tf[1]:<10,} {period:<30} {tf[4]:%Y-%m-%d %H:%M}")
    except Exception as e:
        print(f"Details failed: {e}")


async def cleanup_old_data(days: int = 30) -> None:
    try:
        count, deleted = await cleanup_swap_data(days)
        if count == 0:
            print(f"No data older than {days} days")
            return
        print(f"Deleting {count:,} rows older than {days} days...")
        print(f"Deleted {deleted:,} rows")
    except Exception as e:
        print(f"Cleanup failed: {e}")


async def export_symbol_data(
    symbol: str, output_file: str, timeframes: list[str] | None = None
) -> None:
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


async def run_parity(
    symbols: list[str],
    timeframe: str = "1m",
    limit: int = 300,
    before: str | None = None,
    max_failed_symbols: int = 0,
    max_mismatch_per_symbol: int = 0,
    max_missing_per_symbol: int = 0,
    max_extra_per_symbol: int = 0,
) -> None:
    try:
        report = await run_adapter_parity_check(
            baseline_adapter=build_market_data_adapter({"adapter": "legacy"}),
            candidate_adapter=build_market_data_adapter({"adapter": "ccxt"}),
            symbols=symbols,
            timeframe=timeframe,
            limit=limit,
            before=before,
        )
        gate = ParityGate(
            max_failed_symbols=max_failed_symbols,
            max_mismatch_per_symbol=max_mismatch_per_symbol,
            max_missing_per_symbol=max_missing_per_symbol,
            max_extra_per_symbol=max_extra_per_symbol,
        )
        gate_result = evaluate_parity_gate(report, gate)
        print("PARITY REPORT")
        print("=" * 60)
        print(f"timeframe: {report['timeframe']}")
        print(f"limit: {report['limit']}")
        print(f"symbols_total: {report['symbols_total']}")
        print(f"symbols_ok: {report['symbols_ok']}")
        print(f"symbols_failed: {report['symbols_failed']}")
        print(f"ok: {report['ok']}")
        print("\nPER SYMBOL")
        print("-" * 60)
        for symbol, item in report["per_symbol"].items():
            print(
                f"{symbol}: ok={item['ok']} common={item['common_count']} "
                f"missing={item['missing_in_candidate_count']} "
                f"extra={item['extra_in_candidate_count']} "
                f"mismatch={item['mismatch_count']}"
            )
        print("\nGATE")
        print("-" * 60)
        print(
            "thresholds:"
            f" failed_symbols<={gate.max_failed_symbols},"
            f" mismatch<={gate.max_mismatch_per_symbol},"
            f" missing<={gate.max_missing_per_symbol},"
            f" extra<={gate.max_extra_per_symbol}"
        )
        print(f"gate_ok: {gate_result['ok']}")
        if gate_result["violations"]:
            print("violations:")
            for symbol, violations in gate_result["violations"].items():
                print(f"  {symbol}: {violations}")
        if not gate_result["ok"]:
            sys.exit(2)
    except Exception as e:
        print(f"Parity check failed: {e}")
        sys.exit(1)


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

    parity_parser = subparsers.add_parser(
        "parity",
        help="compare candles payload between legacy and CCXT adapters",
    )
    parity_parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="symbols for parity check, example: BTC-USDT-SWAP",
    )
    parity_parser.add_argument(
        "--timeframe",
        default="1m",
        help="timeframe for parity check",
    )
    parity_parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="candles limit per symbol",
    )
    parity_parser.add_argument(
        "--before",
        help="pagination cursor timestamp (ms) for historical page",
    )
    parity_parser.add_argument(
        "--max-failed-symbols",
        type=int,
        default=0,
        help="gate threshold for number of symbols allowed to violate parity",
    )
    parity_parser.add_argument(
        "--max-mismatch-per-symbol",
        type=int,
        default=0,
        help="gate threshold for mismatched candles per symbol",
    )
    parity_parser.add_argument(
        "--max-missing-per-symbol",
        type=int,
        default=0,
        help="gate threshold for missing candles per symbol",
    )
    parity_parser.add_argument(
        "--max-extra-per-symbol",
        type=int,
        default=0,
        help="gate threshold for extra candles per symbol",
    )

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
        if args.symbols:
            asyncio.run(sync_specific_symbols(args.symbols, args.timeframes))
        else:
            asyncio.run(sync_all_swap(None, args.timeframes, config))
    elif args.command == "status":
        asyncio.run(show_swap_status())
    elif args.command == "details":
        asyncio.run(show_symbol_details(args.symbol))
    elif args.command == "cleanup":
        asyncio.run(cleanup_old_data(args.days))
    elif args.command == "export":
        asyncio.run(export_symbol_data(args.symbol, args.output, args.timeframes))
    elif args.command == "parity":
        asyncio.run(
            run_parity(
                symbols=args.symbols,
                timeframe=args.timeframe,
                limit=args.limit,
                before=args.before,
                max_failed_symbols=args.max_failed_symbols,
                max_mismatch_per_symbol=args.max_mismatch_per_symbol,
                max_missing_per_symbol=args.max_missing_per_symbol,
                max_extra_per_symbol=args.max_extra_per_symbol,
            )
        )


if __name__ == "__main__":
    main()

