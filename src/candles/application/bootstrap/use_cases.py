from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.candles.application.bootstrap.dto import BootstrapCommand, BootstrapResult
from src.candles.application.bootstrap.planning import (
    compute_chunk_window,
    compute_target_window,
)
from src.candles.domain.repair import RepairWindow, count_expected_bars
from src.candles.domain.timeframes import TF_TO_MS

if TYPE_CHECKING:
    from src.candles.application.bootstrap.ports import BootstrapStatePort
    from src.candles.application.repair.ports import (
        CandleCoverageQueryPort,
        HistoricalCandleSourcePort,
        RepairAnchorMetadataPort,
        RepairCandleStorePort,
    )
    from src.candles.domain.okx_calendar import OKXCandleCalendar
    from src.candles.ports import TelemetryPort


class RunBootstrapUseCase:
    def __init__(
        self,
        *,
        historical_source: HistoricalCandleSourcePort,
        repair_store: RepairCandleStorePort,
        coverage_query: CandleCoverageQueryPort,
        anchor_metadata: RepairAnchorMetadataPort,
        bootstrap_state: BootstrapStatePort,
        calendar: OKXCandleCalendar,
        telemetry: TelemetryPort | None = None,
    ) -> None:
        self._source = historical_source
        self._repair_store = repair_store
        self._coverage = coverage_query
        self._anchor = anchor_metadata
        self._state = bootstrap_state
        self._calendar = calendar
        self._telemetry = telemetry

    async def run(self, command: BootstrapCommand, *, now_ms: int) -> BootstrapResult:
        started = time.monotonic()
        symbol = command.symbol
        timeframe = command.timeframe
        tf_ms = TF_TO_MS.get(timeframe)
        if tf_ms is None:
            raise ValueError(f"unsupported timeframe: {timeframe!r}")

        # INIT
        listing_time_ms = await self._anchor.get_listing_time_ts_ms(symbol=symbol)
        target_start_ts, target_end_ts = compute_target_window(
            now_ms=now_ms,
            lookback_days=command.lookback_days,
            listing_time_ms=listing_time_ms,
            timeframe=timeframe,
            calendar=self._calendar,
        )
        # Clamp to epoch-0; negative timestamps are not valid candle open times
        target_start_ts = max(0, target_start_ts)

        expected_bars = count_expected_bars(
            window=RepairWindow(start_ts_ms=target_start_ts, end_ts_ms=target_end_ts),
            timeframe=timeframe,
            calendar=self._calendar,
        )

        # Skip if already completed
        existing = await self._state.get_bootstrap_state(symbol=symbol, timeframe=timeframe)
        if existing is not None and existing.status == "completed":
            return BootstrapResult(
                symbol=symbol,
                timeframe=timeframe,
                status="completed",
                chunks_fetched=0,
                rows_written=0,
                expected_bars=existing.expected_bars,
                actual_bars=existing.actual_bars or 0,
                missing_bars=0,
                coverage_pct=100.0,
                elapsed_seconds=time.monotonic() - started,
            )

        # Resume checkpoint or start from target_end_ts
        checkpoint_ts = (
            existing.checkpoint_ts
            if existing is not None and existing.checkpoint_ts is not None
            else target_end_ts
        )

        await self._state.upsert_bootstrap_state(
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=command.lookback_days,
            target_start_ts=target_start_ts,
            target_end_ts=target_end_ts,
            expected_bars=expected_bars,
            status="running",
            checkpoint_ts=checkpoint_ts,
        )

        chunks_fetched = 0
        rows_written = 0
        error_streak = 0

        # FETCH LOOP: backward from checkpoint_ts to target_start_ts
        while checkpoint_ts > target_start_ts:
            chunk_start, chunk_end = compute_chunk_window(
                checkpoint_ts=checkpoint_ts,
                chunk_bars=command.chunk_bars,
                timeframe_ms=tf_ms,
            )
            chunk_start = max(chunk_start, target_start_ts)

            try:
                candles = await self._source.fetch_range(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_ts_ms=chunk_start,
                    end_ts_ms=chunk_end,
                )
            except Exception as exc:
                error_streak += 1
                if error_streak >= command.circuit_break_after:
                    live_actual = await self._coverage.count_candles(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_ts_ms=target_start_ts,
                        end_ts_ms=target_end_ts,
                    )
                    await self._state.upsert_bootstrap_state(
                        symbol=symbol,
                        timeframe=timeframe,
                        lookback_days=command.lookback_days,
                        target_start_ts=target_start_ts,
                        target_end_ts=target_end_ts,
                        expected_bars=expected_bars,
                        status="stuck",
                        error_streak=error_streak,
                        last_error=str(exc),
                    )
                    return BootstrapResult(
                        symbol=symbol,
                        timeframe=timeframe,
                        status="stuck",
                        chunks_fetched=chunks_fetched,
                        rows_written=rows_written,
                        expected_bars=expected_bars,
                        actual_bars=live_actual,
                        missing_bars=max(0, expected_bars - live_actual),
                        coverage_pct=(live_actual / expected_bars * 100.0) if expected_bars > 0 else 0.0,
                        elapsed_seconds=time.monotonic() - started,
                        error=str(exc),
                    )
                # Retry the same chunk; do not advance checkpoint until circuit break
                continue

            error_streak = 0
            chunks_fetched += 1

            if candles and not command.dry_run:
                written = await self._repair_store.selective_upsert_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    candles=candles,
                )
                rows_written += written

            # Advance checkpoint backward
            if candles:
                min_ts = min(int(c["timestamp"]) for c in candles)
                checkpoint_ts = min(min_ts, chunk_start)
            else:
                checkpoint_ts = chunk_start

            await self._state.upsert_bootstrap_state(
                symbol=symbol,
                timeframe=timeframe,
                lookback_days=command.lookback_days,
                target_start_ts=target_start_ts,
                target_end_ts=target_end_ts,
                expected_bars=expected_bars,
                status="running",
                checkpoint_ts=checkpoint_ts,
            )

        # VERIFY
        live_actual = await self._coverage.count_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=target_start_ts,
            end_ts_ms=target_end_ts,
        )
        live_expected = count_expected_bars(
            window=RepairWindow(start_ts_ms=target_start_ts, end_ts_ms=target_end_ts),
            timeframe=timeframe,
            calendar=self._calendar,
        )
        live_missing = max(0, live_expected - live_actual)
        coverage_pct = (live_actual / live_expected * 100.0) if live_expected > 0 else 100.0

        final_status = "completed" if (live_missing == 0 and not command.dry_run) else "incomplete"

        await self._state.upsert_bootstrap_state(
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=command.lookback_days,
            target_start_ts=target_start_ts,
            target_end_ts=target_end_ts,
            expected_bars=live_expected,
            actual_bars=live_actual,
            missing_bars=live_missing,
            coverage_pct=coverage_pct,
            status=final_status,
            bootstrap_completed=(final_status == "completed"),
            completed_at_ms=int(time.time() * 1000) if final_status == "completed" else None,
        )

        return BootstrapResult(
            symbol=symbol,
            timeframe=timeframe,
            status=final_status,
            chunks_fetched=chunks_fetched,
            rows_written=rows_written,
            expected_bars=live_expected,
            actual_bars=live_actual,
            missing_bars=live_missing,
            coverage_pct=coverage_pct,
            elapsed_seconds=time.monotonic() - started,
        )
