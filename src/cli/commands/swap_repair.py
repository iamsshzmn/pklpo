from __future__ import annotations

import json
from datetime import UTC, datetime

from src.candles.domain.repair import RepairExecutionMode, RepairStrategy
from src.candles.interfaces.repair import run_swap_repair


def _parse_utc_timestamp_ms(value: str) -> int:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.astimezone(UTC).timestamp() * 1000)


def _utc_now_ts_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def register(subparsers) -> None:
    parser = subparsers.add_parser("swap-repair", help="Historical backfill and gap repair")
    parser.add_argument("--symbols", nargs="+", default=["BTC-USDT-SWAP"])
    parser.add_argument("--timeframes", nargs="+", default=["1m"])
    parser.add_argument("--start", required=True, help="UTC ISO-8601 start")
    parser.add_argument("--end", required=True, help="UTC ISO-8601 end")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in RepairExecutionMode],
        default=RepairExecutionMode.DETECT_ONLY.value,
    )
    parser.add_argument(
        "--repair-strategy",
        choices=[strategy.value for strategy in RepairStrategy],
        default=RepairStrategy.GAP_REPAIR.value,
    )
    parser.add_argument("--padding-bars", type=int, default=0)
    parser.add_argument("--max-gap-tasks-per-run", type=int, default=50)
    parser.add_argument("--max-requested-bars-per-run", type=int, default=10_000)
    parser.add_argument("--max-range-days", type=int, default=7)
    parser.add_argument("--max-fail-ratio", type=float, default=0.1)
    parser.set_defaults(_handler=handle)


async def handle(args) -> None:
    symbols = list(getattr(args, "symbols", []) or [])
    timeframes = list(getattr(args, "timeframes", []) or [])
    if len(symbols) != 1:
        raise ValueError("swap-repair supports exactly one symbol per run")
    if not timeframes:
        raise ValueError("swap-repair requires at least one timeframe")

    start_ts_ms = _parse_utc_timestamp_ms(args.start)
    requested_end_ts_ms = _parse_utc_timestamp_ms(args.end)
    summaries = []
    for timeframe in timeframes:
        summary = await run_swap_repair(
            symbol=symbols[0],
            timeframe=timeframe,
            start_ts_ms=start_ts_ms,
            end_ts_ms=min(requested_end_ts_ms, _utc_now_ts_ms()),
            mode=RepairExecutionMode(args.mode),
            strategy=RepairStrategy(args.repair_strategy),
            max_gap_tasks_per_run=args.max_gap_tasks_per_run,
            max_requested_bars_per_run=args.max_requested_bars_per_run,
            max_range_days=args.max_range_days,
            max_fail_ratio=args.max_fail_ratio,
            padding_bars=args.padding_bars,
        )
        summaries.append(summary)
    print(json.dumps(summaries, ensure_ascii=True, indent=2))
