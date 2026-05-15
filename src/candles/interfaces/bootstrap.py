"""Airflow-facing entry points for the bootstrap use case.

Wires concrete infrastructure implementations into RunBootstrapUseCase.
All public coroutines accept ``config: dict[str, Any] | None = None``
for OKX credential injection — same pattern as interfaces/repair.py.
"""
from __future__ import annotations

import time as _time
from typing import Any

from src.candles.application.bootstrap import (
    BootstrapCommand,
    BootstrapResult,
    RunBootstrapUseCase,
)
from src.candles.application.bootstrap.planning import compute_target_window
from src.candles.domain.okx_calendar import StorageCalendar
from src.candles.domain.repair import RepairWindow, count_expected_bars
from src.candles.domain.timeframes import TF_TO_MS
from src.candles.infrastructure.adapters import build_market_data_adapter
from src.candles.infrastructure.bootstrap_repository import BootstrapCandlesRepository
from src.candles.interfaces.repair import _HistoricalRangeSourceAdapter
from src.candles.interfaces.swap_sync import (
    _MarketDataPortAdapter,
    _TracingTelemetryAdapter,
)


async def run_bootstrap(
    command: BootstrapCommand,
    *,
    now_ms: int | None = None,
    config: dict[str, Any] | None = None,
) -> BootstrapResult:
    """Run bootstrap for a single (symbol, timeframe) pair."""
    if now_ms is None:
        now_ms = int(_time.time() * 1000)

    market_adapter = build_market_data_adapter(config or {})
    async with _MarketDataPortAdapter(market_adapter) as market_data:
        source = _HistoricalRangeSourceAdapter(market_data)
        repository = BootstrapCandlesRepository()
        calendar = StorageCalendar()
        telemetry = _TracingTelemetryAdapter()

        use_case = RunBootstrapUseCase(
            historical_source=source,
            repair_store=repository,
            coverage_query=repository,
            anchor_metadata=repository,
            bootstrap_state=repository,
            calendar=calendar,
            telemetry=telemetry,
        )
        return await use_case.run(command, now_ms=now_ms)


async def init_bootstrap_state(
    *,
    symbols: list[str],
    timeframes: list[str],
    lookback_days: int,
    chunk_bars: int = 500,
    config: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """Upsert state rows for all (symbol, timeframe) pairs without running the fetch loop.

    Skips pairs where bootstrap_completed=True.
    Returns {"skipped": [...], "pending": [...]}.
    """
    now_ms = int(_time.time() * 1000)
    repository = BootstrapCandlesRepository()
    calendar = StorageCalendar()

    skipped: list[str] = []
    pending: list[str] = []

    for symbol in symbols:
        listing_time_ms = await repository.get_listing_time_ts_ms(symbol=symbol)
        for timeframe in timeframes:
            tf_ms = TF_TO_MS.get(timeframe)
            if tf_ms is None:
                continue

            existing = await repository.get_bootstrap_state(symbol=symbol, timeframe=timeframe)
            if existing is not None and existing.bootstrap_completed:
                skipped.append(f"{symbol}/{timeframe}")
                continue

            target_start_ts, target_end_ts = compute_target_window(
                now_ms=now_ms,
                lookback_days=lookback_days,
                listing_time_ms=listing_time_ms,
                timeframe=timeframe,
                calendar=calendar,
            )
            expected_bars = count_expected_bars(
                window=RepairWindow(start_ts_ms=target_start_ts, end_ts_ms=target_end_ts),
                timeframe=timeframe,
                calendar=calendar,
            )

            # Check if already fully covered (live check)
            actual = await repository.count_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_ts_ms=target_start_ts,
                end_ts_ms=target_end_ts,
            )
            if actual >= expected_bars > 0:
                await repository.upsert_bootstrap_state(
                    symbol=symbol,
                    timeframe=timeframe,
                    lookback_days=lookback_days,
                    target_start_ts=target_start_ts,
                    target_end_ts=target_end_ts,
                    expected_bars=expected_bars,
                    actual_bars=actual,
                    missing_bars=0,
                    coverage_pct=100.0,
                    status="completed",
                    bootstrap_completed=True,
                )
                skipped.append(f"{symbol}/{timeframe}")
                continue

            await repository.upsert_bootstrap_state(
                symbol=symbol,
                timeframe=timeframe,
                lookback_days=lookback_days,
                target_start_ts=target_start_ts,
                target_end_ts=target_end_ts,
                expected_bars=expected_bars,
                actual_bars=actual,
                missing_bars=max(0, expected_bars - actual),
                coverage_pct=(actual / expected_bars * 100.0) if expected_bars > 0 else 100.0,
                status="pending",
            )
            pending.append(f"{symbol}/{timeframe}")

    return {"skipped": skipped, "pending": pending}


async def build_coverage_report(
    *,
    symbols: list[str],
    timeframes: list[str],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return coverage_pct, missing_bars per (symbol, timeframe) from state table."""
    repository = BootstrapCandlesRepository()
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        for timeframe in timeframes:
            state = await repository.get_bootstrap_state(symbol=symbol, timeframe=timeframe)
            if state is None:
                rows.append({"symbol": symbol, "timeframe": timeframe, "status": "not_initialized"})
            else:
                rows.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "status": state.status,
                    "coverage_pct": state.coverage_pct,
                    "missing_bars": state.missing_bars,
                    "expected_bars": state.expected_bars,
                    "actual_bars": state.actual_bars,
                    "bootstrap_completed": state.bootstrap_completed,
                })
    return rows
