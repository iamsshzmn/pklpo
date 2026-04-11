from __future__ import annotations

from typing import Any

from src.candles.application.repair import (
    RepairCommand,
    RunGapRepairUseCase,
    RunHistoricalBackfillUseCase,
)
from src.candles.domain.repair import (
    RepairExecutionMode,
    RepairGuardrails,
    RepairStrategy,
)
from src.candles.infrastructure.adapters import build_market_data_adapter
from src.candles.infrastructure.repair_repository import RepairCandlesRepository
from src.candles.interfaces.swap_sync import (
    _MarketDataPortAdapter,
    _TracingTelemetryAdapter,
)


class _HistoricalRangeSourceAdapter:
    def __init__(self, market_data: _MarketDataPortAdapter, *, batch_size: int = 300) -> None:
        self._market_data = market_data
        self._batch_size = batch_size

    async def fetch_range(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        if start_ts_ms >= end_ts_ms:
            return []

        before = str(end_ts_ms)
        collected: dict[int, dict[str, Any]] = {}
        while True:
            candles = await self._market_data.fetch_candles(
                instrument_id=symbol,
                timeframe=timeframe,
                limit=self._batch_size,
                before=before,
            )
            if not candles:
                break

            oldest_ts = min(int(candle["ts"]) for candle in candles)
            for candle in candles:
                ts = int(candle["ts"])
                if start_ts_ms <= ts < end_ts_ms:
                    collected[ts] = candle

            if oldest_ts <= start_ts_ms:
                break

            next_before = str(oldest_ts)
            if next_before == before:
                break
            before = next_before

        return [collected[ts] for ts in sorted(collected)]


class _NoopHistoricalRangeSource:
    async def fetch_range(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        return []


async def run_swap_repair(
    *,
    symbol: str,
    timeframe: str,
    start_ts_ms: int,
    end_ts_ms: int,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    max_gap_tasks_per_run: int,
    max_requested_bars_per_run: int,
    max_range_days: int,
    max_fail_ratio: float,
    padding_bars: int,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repository = RepairCandlesRepository()
    command = RepairCommand(
        symbol=symbol,
        timeframe=timeframe,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        mode=mode,
        strategy=strategy,
        guardrails=RepairGuardrails(
            max_gap_tasks_per_run=max_gap_tasks_per_run,
            max_requested_bars_per_run=max_requested_bars_per_run,
            max_range_days=max_range_days,
            max_fail_ratio=max_fail_ratio,
        ),
        now_ts_ms=end_ts_ms,
        padding_bars=padding_bars,
    )
    telemetry = _TracingTelemetryAdapter()

    if mode is RepairExecutionMode.APPLY:
        market_adapter = build_market_data_adapter(config or {})
        async with _MarketDataPortAdapter(market_adapter) as market_data:
            source = _HistoricalRangeSourceAdapter(market_data)
            use_case = (
                RunHistoricalBackfillUseCase(
                    coverage_query=repository,
                    historical_source=source,
                    repair_store=repository,
                    telemetry=telemetry,
                )
                if strategy is RepairStrategy.BACKFILL
                else RunGapRepairUseCase(
                    coverage_query=repository,
                    historical_source=source,
                    repair_store=repository,
                    telemetry=telemetry,
                )
            )
            result = await use_case.run(command)
    else:
        source = _NoopHistoricalRangeSource()
        use_case = (
            RunHistoricalBackfillUseCase(
                coverage_query=repository,
                historical_source=source,
                repair_store=repository,
                telemetry=telemetry,
            )
            if strategy is RepairStrategy.BACKFILL
            else RunGapRepairUseCase(
                coverage_query=repository,
                historical_source=source,
                repair_store=repository,
                telemetry=telemetry,
            )
        )
        result = await use_case.run(command)

    violations = command.guardrails.check(result.plan)
    return {
        "mode": result.mode.value,
        "strategy": result.strategy.value,
        "symbol": symbol,
        "timeframe": timeframe,
        "window": {
            "start_ts_ms": result.plan.window.start_ts_ms,
            "end_ts_ms": result.plan.window.end_ts_ms,
        },
        "gap_tasks": result.plan.gap_tasks,
        "requested_bars": result.plan.requested_bars,
        "rows_written": result.rows_written,
        "fetch_calls": result.fetch_calls,
        "verified": result.verified,
        "padding_bars": padding_bars,
        "guardrail_violations": [violation.code for violation in violations],
        "watermark_updated": result.watermark_updated,
    }
