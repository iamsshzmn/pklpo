from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from src.candles.application.bootstrap.dto import (
    BootstrapCommand,
    BootstrapProgress,
    BootstrapResult,
)
from src.candles.application.bootstrap.planning import (
    compute_chunk_window,
    compute_target_window,
)
from src.candles.domain.repair import (
    RepairWindow,
    count_expected_bars,
    sanitize_repair_candle,
)
from src.candles.domain.timeframes import TF_TO_MS
from src.pklpo_platform.observability.error_types import classify_error_type

if TYPE_CHECKING:
    from typing import SupportsInt

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
        if timeframe not in TF_TO_MS:
            raise ValueError(f"unsupported timeframe: {timeframe!r}")
        if command.circuit_break_after < 1:
            raise ValueError("circuit_break_after must be >= 1")

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

        # Load existing state and determine checkpoint
        existing = await self._state.get_bootstrap_state(symbol=symbol, timeframe=timeframe)
        should_reinitialize = _should_reinitialize_bootstrap(
            existing=existing,
            lookback_days=command.lookback_days,
            target_start_ts=target_start_ts,
            target_end_ts=target_end_ts,
        )

        if existing is not None and existing.status == "completed":
            # Reconcile: verify live DB before trusting cached completed state.
            # swap_ohlcv_p may have lost rows since completion (cleanup, partition drop, etc.).
            live_rec = await self._coverage.count_valid_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_ts_ms=target_start_ts,
                end_ts_ms=target_end_ts,
            )
            if live_rec.missing_bars == 0 and live_rec.invalid_extra_rows == 0:
                return BootstrapResult(
                    symbol=symbol,
                    timeframe=timeframe,
                    status="completed",
                    chunks_fetched=0,
                    rows_written=0,
                    expected_bars=live_rec.expected_bars,
                    actual_bars=live_rec.valid_bars,
                    missing_bars=0,
                    coverage_pct=100.0,
                    elapsed_seconds=time.monotonic() - started,
                )
            # State diverged from reality — downgrade and re-fetch from scratch.
            await self._state.upsert_bootstrap_state(
                symbol=symbol,
                timeframe=timeframe,
                lookback_days=command.lookback_days,
                target_start_ts=target_start_ts,
                target_end_ts=target_end_ts,
                expected_bars=live_rec.expected_bars,
                actual_bars=live_rec.valid_bars,
                missing_bars=live_rec.missing_bars,
                coverage_pct=(live_rec.valid_bars / live_rec.expected_bars * 100.0)
                if live_rec.expected_bars > 0
                else 0.0,
                status="incomplete",
                bootstrap_completed=False,
                checkpoint_ts=target_end_ts,
            )
            checkpoint_ts = target_end_ts
        elif should_reinitialize:
            checkpoint_ts = target_end_ts
        else:
            # Resume from checkpoint or start from target_end_ts
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
            bootstrap_completed=False,
            error_streak=0,
            last_error=None,
        )

        chunks_fetched = 0
        rows_written = 0
        error_streak = 0

        # FETCH LOOP: backward from checkpoint_ts to target_start_ts
        while checkpoint_ts > target_start_ts:
            chunk_start, chunk_end = compute_chunk_window(
                checkpoint_ts=checkpoint_ts,
                chunk_bars=command.chunk_bars,
                timeframe=timeframe,
                calendar=self._calendar,
            )
            chunk_start = max(chunk_start, target_start_ts)
            checkpoint_before = checkpoint_ts
            fetch_latency_ms = 0
            db_write_latency_ms = 0
            state_write_latency_ms = 0
            candles_returned = 0
            written = 0
            chunk_oldest_ts: int | None = None
            chunk_newest_ts: int | None = None

            fetch_started = time.perf_counter()
            try:
                raw_candles = await self._source.fetch_range(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_ts_ms=chunk_start,
                    end_ts_ms=chunk_end,
                )
            except Exception as exc:
                fetch_latency_ms = int((time.perf_counter() - fetch_started) * 1000)
                error_streak += 1
                if self._telemetry is not None:
                    self._telemetry.event(
                        "bootstrap.chunk_failed",
                        **_chunk_telemetry_payload(
                            symbol=symbol,
                            timeframe=timeframe,
                            chunk_start_ts=chunk_start,
                            chunk_end_ts=chunk_end,
                            checkpoint_before_ts=checkpoint_before,
                            checkpoint_after_ts=None,
                            candles_returned=0,
                            rows_written=0,
                            invalid_rows=0,
                            empty=True,
                            fetch_latency_ms=fetch_latency_ms,
                            db_write_latency_ms=0,
                            state_write_latency_ms=0,
                            target_start_ts=target_start_ts,
                            target_end_ts=target_end_ts,
                            oldest_ts=None,
                            newest_ts=None,
                            status="error",
                            error=str(exc),
                        ),
                        error_type=classify_error_type(exc),
                        exc_info=True,
                    )
                if error_streak >= command.circuit_break_after:
                    live_rec = await self._coverage.count_valid_candles(
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
                        checkpoint_ts=checkpoint_ts,
                        error_streak=error_streak,
                        last_error=str(exc),
                    )
                    return BootstrapResult(
                        symbol=symbol,
                        timeframe=timeframe,
                        status="stuck",
                        chunks_fetched=chunks_fetched,
                        rows_written=rows_written,
                        expected_bars=live_rec.expected_bars,
                        actual_bars=live_rec.valid_bars,
                        missing_bars=live_rec.missing_bars,
                        coverage_pct=(live_rec.valid_bars / live_rec.expected_bars * 100.0)
                        if live_rec.expected_bars > 0
                        else 0.0,
                        elapsed_seconds=time.monotonic() - started,
                        error=str(exc),
                    )
                # Retry the same chunk; do not advance checkpoint until circuit break
                continue
            else:
                fetch_latency_ms = int((time.perf_counter() - fetch_started) * 1000)

            checkpoint_after: int | None = None
            try:
                fetched_at = datetime.now(UTC)
                candles = [
                    _normalize_bootstrap_candle(candle, fetched_at=fetched_at)
                    for candle in raw_candles
                ]
                candles_returned = len(candles)
                error_streak = 0
                chunks_fetched += 1
                chunk_oldest_ts = (
                    min(_candle_ts(candle) for candle in candles) if candles else None
                )
                chunk_newest_ts = (
                    max(_candle_ts(candle) for candle in candles) if candles else None
                )

                db_write_started = time.perf_counter()
                try:
                    if candles and not command.dry_run:
                        written = await self._repair_store.selective_upsert_candles(
                            symbol=symbol,
                            timeframe=timeframe,
                            candles=candles,
                            window=RepairWindow(chunk_start, chunk_end),
                        )
                finally:
                    db_write_latency_ms = int(
                        (time.perf_counter() - db_write_started) * 1000
                    )
                rows_written += written

                # Advance checkpoint backward after the write succeeds.
                if candles:
                    min_ts = min(_candle_ts(c) for c in candles)
                    checkpoint_after = min(min_ts, chunk_start)
                else:
                    checkpoint_after = chunk_start

                state_write_started = time.perf_counter()
                try:
                    await self._state.upsert_bootstrap_state(
                        symbol=symbol,
                        timeframe=timeframe,
                        lookback_days=command.lookback_days,
                        target_start_ts=target_start_ts,
                        target_end_ts=target_end_ts,
                        expected_bars=expected_bars,
                        status="running",
                        checkpoint_ts=checkpoint_after,
                    )
                finally:
                    state_write_latency_ms = int(
                        (time.perf_counter() - state_write_started) * 1000
                    )
            except Exception as exc:
                if self._telemetry is not None:
                    self._telemetry.event(
                        "bootstrap.chunk_failed",
                        **_chunk_telemetry_payload(
                            symbol=symbol,
                            timeframe=timeframe,
                            chunk_start_ts=chunk_start,
                            chunk_end_ts=chunk_end,
                            checkpoint_before_ts=checkpoint_before,
                            checkpoint_after_ts=checkpoint_after,
                            candles_returned=candles_returned,
                            rows_written=written,
                            invalid_rows=0,
                            empty=(candles_returned == 0),
                            fetch_latency_ms=fetch_latency_ms,
                            db_write_latency_ms=db_write_latency_ms,
                            state_write_latency_ms=state_write_latency_ms,
                            target_start_ts=target_start_ts,
                            target_end_ts=target_end_ts,
                            oldest_ts=chunk_oldest_ts,
                            newest_ts=chunk_newest_ts,
                            status="error",
                            error=str(exc),
                        ),
                        error_type=classify_error_type(exc),
                        exc_info=True,
                    )
                raise

            assert checkpoint_after is not None
            checkpoint_ts = checkpoint_after
            if self._telemetry is not None:
                self._telemetry.event(
                    "bootstrap.chunk_result",
                    **_chunk_telemetry_payload(
                        symbol=symbol,
                        timeframe=timeframe,
                        chunk_start_ts=chunk_start,
                        chunk_end_ts=chunk_end,
                        checkpoint_before_ts=checkpoint_before,
                        checkpoint_after_ts=checkpoint_after,
                        candles_returned=candles_returned,
                        rows_written=written,
                        invalid_rows=0,
                        empty=(candles_returned == 0),
                        fetch_latency_ms=fetch_latency_ms,
                        db_write_latency_ms=db_write_latency_ms,
                        state_write_latency_ms=state_write_latency_ms,
                        target_start_ts=target_start_ts,
                        target_end_ts=target_end_ts,
                        oldest_ts=chunk_oldest_ts,
                        newest_ts=chunk_newest_ts,
                        status="ok",
                    ),
                )

        # VERIFY
        live_rec = await self._coverage.count_valid_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=target_start_ts,
            end_ts_ms=target_end_ts,
        )
        live_expected = live_rec.expected_bars
        live_actual = live_rec.valid_bars
        live_missing = live_rec.missing_bars
        coverage_pct = (live_actual / live_expected * 100.0) if live_expected > 0 else 100.0

        final_status = (
            "completed"
            if (
                live_missing == 0
                and live_rec.invalid_extra_rows == 0
                and not command.dry_run
            )
            else "incomplete"
        )

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
            checkpoint_ts=checkpoint_ts,
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


def _should_reinitialize_bootstrap(
    *,
    existing: BootstrapProgress | None,
    lookback_days: int,
    target_start_ts: int,
    target_end_ts: int,
) -> bool:
    if existing is None:
        return True

    status = existing.status
    if status not in {"pending", "running", "in_progress", "incomplete"}:
        return False

    checkpoint_ts = existing.checkpoint_ts
    return (
        existing.target_start_ts != target_start_ts
        or existing.target_end_ts != target_end_ts
        or existing.lookback_days != lookback_days
        or checkpoint_ts is None
        or checkpoint_ts <= target_start_ts
    )


def _candle_ts(candle: dict[str, object]) -> int:
    """Coerce a normalized candle's ``timestamp`` (typed ``object``) to ``int``."""
    return int(cast("SupportsInt | str", candle["timestamp"]))


def _normalize_bootstrap_candle(
    candle: dict[str, object],
    *,
    fetched_at: datetime,
) -> dict[str, object]:
    if "timestamp" not in candle and "ts" in candle:
        return sanitize_repair_candle(candle, fetched_at=fetched_at)
    return {
        "timestamp": candle["timestamp"],
        "open": candle["open"],
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"],
        "volume": candle["volume"],
        "vol_ccy": candle.get("vol_ccy", candle.get("volCcy")),
        "vol_usd": candle.get("vol_usd", candle.get("volUsd")),
        "fetched_at": candle.get("fetched_at", fetched_at),
    }


def _chunk_telemetry_payload(
    *,
    symbol: str,
    timeframe: str,
    chunk_start_ts: int,
    chunk_end_ts: int,
    checkpoint_before_ts: int,
    checkpoint_after_ts: int | None,
    candles_returned: int,
    rows_written: int,
    invalid_rows: int,
    empty: bool,
    fetch_latency_ms: int,
    db_write_latency_ms: int,
    state_write_latency_ms: int,
    target_start_ts: int,
    target_end_ts: int,
    oldest_ts: int | None,
    newest_ts: int | None,
    status: str,
    error: str | None = None,
) -> dict[str, object]:
    progress_checkpoint = (
        checkpoint_after_ts if checkpoint_after_ts is not None else checkpoint_before_ts
    )
    payload: dict[str, object] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "chunk_start": chunk_start_ts,
        "chunk_end": chunk_end_ts,
        "chunk_start_ts": chunk_start_ts,
        "chunk_end_ts": chunk_end_ts,
        "checkpoint_before_ts": checkpoint_before_ts,
        "checkpoint_after_ts": checkpoint_after_ts,
        "candles_returned": candles_returned,
        "rows_written": rows_written,
        "invalid_rows": invalid_rows,
        "empty": empty,
        "oldest_ts": oldest_ts,
        "newest_ts": newest_ts,
        "fetch_latency_ms": fetch_latency_ms,
        "db_write_latency_ms": db_write_latency_ms,
        "state_write_latency_ms": state_write_latency_ms,
        "progress_pct": _progress_pct(
            target_start_ts=target_start_ts,
            target_end_ts=target_end_ts,
            checkpoint_ts=progress_checkpoint,
        ),
        "status": status,
    }
    if error is not None:
        payload["error"] = error
    return payload


def _progress_pct(
    *,
    target_start_ts: int,
    target_end_ts: int,
    checkpoint_ts: int,
) -> float:
    total = target_end_ts - target_start_ts
    if total <= 0:
        return 100.0
    completed = target_end_ts - checkpoint_ts
    return max(0.0, min(100.0, completed / total * 100.0))
