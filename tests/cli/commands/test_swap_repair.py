from __future__ import annotations

import json
from argparse import ArgumentParser
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from src.candles.domain.repair import RepairExecutionMode, RepairStrategy
from src.cli.commands import swap_repair
from src.cli.main import create_parser


def test_create_parser_registers_swap_repair_command() -> None:
    parser = create_parser()

    args = parser.parse_args(
        [
            "swap-repair",
            "--start",
            "2026-04-01T00:00:00Z",
            "--end",
            "2026-04-01T01:00:00Z",
        ]
    )

    assert args.command == "swap-repair"
    assert args.symbols == ["BTC-USDT-SWAP"]
    assert args.timeframes == ["1m"]
    assert args.mode == "detect-only"
    assert args.repair_strategy == "gap-repair"
    assert args._handler is swap_repair.handle


def test_register_sets_expected_defaults() -> None:
    parser = ArgumentParser(prog="test")
    subparsers = parser.add_subparsers(dest="command", required=True)

    swap_repair.register(subparsers)

    args = parser.parse_args(
        [
            "swap-repair",
            "--start",
            "2026-04-01T00:00:00Z",
            "--end",
            "2026-04-01T01:00:00Z",
        ]
    )

    assert args.symbols == ["BTC-USDT-SWAP"]
    assert args.timeframes == ["1m"]
    assert args.padding_bars == 0
    assert args.max_gap_tasks_per_run == 50
    assert args.max_requested_bars_per_run == 10_000
    assert args.max_range_days == 7
    assert args.max_fail_ratio == 0.1


def test_parse_utc_timestamp_ms_supports_z_suffix_and_naive_datetime() -> None:
    zulu = swap_repair._parse_utc_timestamp_ms("2026-04-01T00:00:00Z")
    naive = swap_repair._parse_utc_timestamp_ms("2026-04-01T00:00:00")

    assert zulu == naive
    assert zulu == 1_775_001_600_000


@pytest.mark.asyncio
async def test_handle_calls_run_swap_repair_for_each_timeframe_and_prints_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_run_swap_repair(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "status": "ok",
            "gap_tasks": 2,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "plan-only",
        }

    @asynccontextmanager
    async def fake_job_lock(*args: object, **kwargs: object):
        del args, kwargs
        yield

    monkeypatch.setattr(swap_repair, "job_lock", fake_job_lock)
    monkeypatch.setattr(swap_repair, "run_swap_repair", fake_run_swap_repair)
    monkeypatch.setattr(
        swap_repair,
        "datetime",
        SimpleNamespace(
            now=lambda tz=None: __import__("datetime").datetime(
                2026, 4, 1, 0, 30, tzinfo=tz
            ),
            fromisoformat=__import__("datetime").datetime.fromisoformat,
        ),
    )

    args = SimpleNamespace(
        symbols=["BTC-USDT-SWAP"],
        timeframes=["1m", "1H"],
        start="2026-04-01T00:00:00Z",
        end="2026-04-01T01:00:00Z",
        mode="dry-run",
        repair_strategy="backfill",
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=1000,
        max_range_days=7,
        max_fail_ratio=0.25,
        padding_bars=3,
    )

    await swap_repair.handle(args)

    assert calls == [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "start_ts_ms": 1_775_001_600_000,
            "end_ts_ms": 1_775_003_400_000,
            "mode": RepairExecutionMode.DRY_RUN,
            "strategy": RepairStrategy.BACKFILL,
            "max_gap_tasks_per_run": 10,
            "max_requested_bars_per_run": 1000,
            "max_range_days": 7,
            "max_fail_ratio": 0.25,
            "padding_bars": 3,
        },
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1H",
            "start_ts_ms": 1_775_001_600_000,
            "end_ts_ms": 1_775_003_400_000,
            "mode": RepairExecutionMode.DRY_RUN,
            "strategy": RepairStrategy.BACKFILL,
            "max_gap_tasks_per_run": 10,
            "max_requested_bars_per_run": 1000,
            "max_range_days": 7,
            "max_fail_ratio": 0.25,
            "padding_bars": 3,
        },
    ]
    assert json.loads(capsys.readouterr().out) == [
        {
            "status": "ok",
            "gap_tasks": 2,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "plan-only",
        },
        {
            "status": "ok",
            "gap_tasks": 2,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "plan-only",
        },
    ]


@pytest.mark.asyncio
async def test_handle_rejects_multiple_symbols() -> None:
    args = SimpleNamespace(
        symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        timeframes=["1m"],
        start="2026-04-01T00:00:00Z",
        end="2026-04-01T01:00:00Z",
        mode="detect-only",
        repair_strategy="gap-repair",
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=1000,
        max_range_days=7,
        max_fail_ratio=0.25,
        padding_bars=0,
    )

    with pytest.raises(ValueError, match="exactly one symbol per run"):
        await swap_repair.handle(args)


@pytest.mark.asyncio
async def test_handle_rejects_empty_timeframes() -> None:
    args = SimpleNamespace(
        symbols=["BTC-USDT-SWAP"],
        timeframes=[],
        start="2026-04-01T00:00:00Z",
        end="2026-04-01T01:00:00Z",
        mode="detect-only",
        repair_strategy="gap-repair",
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=1000,
        max_range_days=7,
        max_fail_ratio=0.25,
        padding_bars=0,
    )

    with pytest.raises(ValueError, match="requires at least one timeframe"):
        await swap_repair.handle(args)
