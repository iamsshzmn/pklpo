from __future__ import annotations

import asyncio
import logging
import random
import socket
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import exc as sa_exc

from ...domain.okx_calendar import StorageCalendar
from ...domain.repair import RepairWindow
from ...domain.timeframes import TF_TO_MS
from ...observability.metrics import ReservoirSampling
from .dto import SyncJobRequest, SyncJobResult, SyncRun, SyncRunStatus
from .policy import (
    MarketDataFailureKind,
    RetryPolicy,
    classify_market_data_failure,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEFRAMES = tuple(TF_TO_MS.keys())

if TYPE_CHECKING:
    from .ports import (
        CandleStorePort,
        InstrumentCatalogPort,
        MarketDataPort,
        TelemetryPort,
    )

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None


class DatabaseUnavailableError(RuntimeError):
    """Raised when the candle store is unavailable at run level."""


def _iter_exception_chain(error: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _is_db_outage_error(error: BaseException) -> bool:
    transient_messages = (
        "connection is closed",
        "connect call failed",
        "name or service not known",
        "temporary failure in name resolution",
        "connection refused",
        "database connection invalidated",
    )
    transient_errnos = {111, -2, 11001}

    for current in _iter_exception_chain(error):
        if isinstance(
            current, (ConnectionError, ConnectionRefusedError, socket.gaierror)
        ):
            return True
        if isinstance(current, (sa_exc.OperationalError, sa_exc.InterfaceError)):
            return True
        if isinstance(current, sa_exc.DBAPIError) and current.connection_invalidated:
            return True
        if asyncpg is not None and isinstance(
            current,
            (
                asyncpg.PostgresConnectionError,
                asyncpg.ConnectionDoesNotExistError,
                asyncpg.InterfaceError,
            ),
        ):
            return True
        if isinstance(current, OSError):
            if getattr(current, "errno", None) in transient_errnos:
                return True
            if any(marker in str(current).lower() for marker in transient_messages):
                return True
        if any(marker in str(current).lower() for marker in transient_messages):
            return True
    return False


class RefreshInstrumentCatalogUseCase:
    def __init__(self, *, instrument_catalog: InstrumentCatalogPort) -> None:
        self._instrument_catalog = instrument_catalog

    async def run(self) -> list[str]:
        return await self._instrument_catalog.refresh_catalog()


class _AdditionalDataLoader:
    def __init__(self, market_data: MarketDataPort) -> None:
        self._market_data = market_data
        self._stats: dict[str, dict[str, float]] = {
            "funding": {
                "ok": 0,
                "retries": 0,
                "rate_limit": 0,
                "timeout": 0,
                "errors": 0,
            },
            "open_interest": {
                "ok": 0,
                "retries": 0,
                "rate_limit": 0,
                "timeout": 0,
                "errors": 0,
            },
        }

    async def fetch_for_symbol(self, symbol: str) -> dict[str, Any]:
        out: dict[str, Any] = {}

        try:
            funding = await self._market_data.fetch_funding_rates([symbol])
            if funding.get(symbol):
                self._stats["funding"]["ok"] += 1
                out["funding_rate"] = funding[symbol]
        except Exception as exc:
            failure_kind = classify_market_data_failure(exc)
            if failure_kind is MarketDataFailureKind.RATE_LIMIT:
                self._stats["funding"]["rate_limit"] += 1
                self._stats["funding"]["retries"] += 1
                logger.warning(
                    "Funding rate fetch rate-limited for %s: %s", symbol, exc
                )
            elif failure_kind is MarketDataFailureKind.TIMEOUT:
                self._stats["funding"]["timeout"] += 1
                logger.warning("Funding rate fetch timed out for %s: %s", symbol, exc)
            else:
                self._stats["funding"]["errors"] += 1
                logger.warning("Funding rate fetch failed for %s: %s", symbol, exc)

        try:
            open_interest = await self._market_data.fetch_open_interest([symbol])
            if open_interest.get(symbol):
                self._stats["open_interest"]["ok"] += 1
                out["open_interest"] = open_interest[symbol]
        except Exception as exc:
            failure_kind = classify_market_data_failure(exc)
            if failure_kind is MarketDataFailureKind.RATE_LIMIT:
                self._stats["open_interest"]["rate_limit"] += 1
                self._stats["open_interest"]["retries"] += 1
                logger.warning(
                    "Open interest fetch rate-limited for %s: %s", symbol, exc
                )
            elif failure_kind is MarketDataFailureKind.TIMEOUT:
                self._stats["open_interest"]["timeout"] += 1
                logger.warning("Open interest fetch timed out for %s: %s", symbol, exc)
            else:
                self._stats["open_interest"]["errors"] += 1
                logger.warning("Open interest fetch failed for %s: %s", symbol, exc)

        return out

    def snapshot_stats(self) -> dict[str, dict[str, float]]:
        return {endpoint: values.copy() for endpoint, values in self._stats.items()}


class _SyncStats:
    """Thread-safe sync run statistics with bounded memory."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.endpoint_stats: dict[str, dict[str, float]] = {
            "candles": {"ok": 0, "retries": 0, "rate_limit": 0, "timeout": 0},
        }
        self.db_write_latencies = ReservoirSampling(max_size=1000)
        self.db_write_batch_sizes = ReservoirSampling(max_size=1000)

    async def record_fetch_ok(self) -> None:
        async with self._lock:
            self.endpoint_stats["candles"]["ok"] += 1

    async def record_fetch_retry(
        self,
        *,
        rate_limited: bool = False,
        timed_out: bool = False,
    ) -> None:
        async with self._lock:
            self.endpoint_stats["candles"]["retries"] += 1
            if rate_limited:
                self.endpoint_stats["candles"]["rate_limit"] += 1
            if timed_out:
                self.endpoint_stats["candles"]["timeout"] += 1

    async def record_db_write(self, latency_sec: float, batch_size: int) -> None:
        async with self._lock:
            self.db_write_latencies.add(latency_sec)
            self.db_write_batch_sizes.add(batch_size)

    def merge_extra_data_stats(self, extra_stats: dict[str, dict[str, float]]) -> None:
        self.endpoint_stats.update(extra_stats)

    def db_write_summary(self) -> dict[str, float | int]:
        lats = self.db_write_latencies
        batches = self.db_write_batch_sizes
        return {
            "writes_count": lats.count,
            "latency_avg_ms": round(lats.mean() * 1000, 3),
            "latency_p95_ms": round(lats.percentile(95) * 1000, 3),
            "batch_size_avg": round(batches.mean(), 2),
            "batch_size_max": (max(batches._samples) if batches._samples else 0),
        }


class RunCandleSyncUseCase:
    def __init__(
        self,
        *,
        market_data: MarketDataPort,
        candle_store: CandleStorePort,
        instrument_catalog: InstrumentCatalogPort,
        retry_policy: RetryPolicy,
        telemetry: TelemetryPort | None = None,
    ) -> None:
        self._market_data = market_data
        self._candle_store = candle_store
        self._instrument_catalog = instrument_catalog
        self._retry_policy = retry_policy
        self._telemetry = telemetry
        self._last_api_latency_ms: float = 0.0

    async def _ensure_candle_store_ready(self) -> None:
        probe_timestamp_ms = int(datetime.now(UTC).timestamp() * 1000)
        try:
            await self._candle_store.get_fill_stats(probe_timestamp_ms)
        except Exception as exc:
            if _is_db_outage_error(exc):
                raise DatabaseUnavailableError("database_unavailable") from exc
            raise

    async def _resolve_symbols(self, requested_symbols: tuple[str, ...]) -> list[str]:
        if requested_symbols:
            return list(requested_symbols)

        curated = await self._instrument_catalog.load_curated_symbols()
        if curated:
            return curated

        cached = await self._instrument_catalog.load_cached_symbols()
        if cached:
            return cached

        refreshed = await self._instrument_catalog.refresh_catalog()
        if refreshed:
            return refreshed

        return await self._instrument_catalog.list_symbols()

    async def _filter_supported_symbols(self, symbols: list[str]) -> list[str]:
        if not symbols:
            return []

        try:
            instruments = await self._market_data.fetch_instruments("SWAP")
        except Exception as exc:
            logger.warning("Failed to refresh supported SWAP instrument set: %s", exc)
            return symbols

        supported = {item.get("instId") for item in instruments if item.get("instId")}
        if not supported:
            logger.warning(
                "Market adapter returned empty SWAP instrument set; using unfiltered symbol list"
            )
            return symbols

        filtered = [symbol for symbol in symbols if symbol in supported]
        skipped = sorted(set(symbols) - set(filtered))
        if skipped:
            logger.warning(
                "Skipping %s unsupported/delisted symbols before sync: %s",
                len(skipped),
                skipped[:20],
            )
        return filtered

    async def _sync_bar(
        self,
        *,
        symbol: str,
        timeframe: str,
        before: str | None,
        latest_stored_ts: int | None,
        extra_data_loader: _AdditionalDataLoader | None,
        stats: _SyncStats,
    ) -> tuple[int, str | None]:
        attempts = 0
        delay = self._retry_policy.initial_delay()

        while True:
            try:
                started = time.perf_counter()
                candles = await self._market_data.fetch_candles(
                    instrument_id=symbol,
                    timeframe=timeframe,
                    limit=self._retry_policy.request_limit(),
                    before=before,
                )
                self._last_api_latency_ms = (time.perf_counter() - started) * 1000
                await stats.record_fetch_ok()
                break
            except Exception as exc:
                failure_kind = classify_market_data_failure(exc)
                if not self._retry_policy.is_retriable_failure(
                    failure_kind
                ) or not self._retry_policy.can_retry(attempts):
                    raise
                attempts += 1
                await stats.record_fetch_retry(
                    rate_limited=self._retry_policy.is_rate_limited_failure(
                        failure_kind
                    ),
                    timed_out=failure_kind is MarketDataFailureKind.TIMEOUT,
                )
                if self._telemetry is not None:
                    self._telemetry.event(
                        "fetch_retried",
                        symbol=symbol,
                        timeframe=timeframe,
                        attempt=attempts,
                        rate_limited=self._retry_policy.is_rate_limited_failure(
                            failure_kind
                        ),
                        failure_kind=failure_kind.value,
                        error=str(exc),
                    )
                await asyncio.sleep(self._retry_policy.next_sleep(delay))
                delay = self._retry_policy.bump_delay(delay)

        if not candles:
            return 0, None

        last_ts = str(candles[-1]["ts"])
        if latest_stored_ts is not None:
            candles = [c for c in candles if int(c["ts"]) > latest_stored_ts]
            if not candles:
                return 0, last_ts
        calendar = StorageCalendar()
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        open_bar_start = calendar.floor_open(now_ms, timeframe)
        candles = [c for c in candles if int(c["ts"]) < open_bar_start]
        if not candles:
            return 0, last_ts
        candle_timestamps = [int(candle["ts"]) for candle in candles]
        window_start = (
            calendar.next_open(latest_stored_ts, timeframe)
            if latest_stored_ts is not None
            else min(candle_timestamps)
        )
        window_end = (
            open_bar_start
            if latest_stored_ts is not None
            else calendar.next_open(max(candle_timestamps), timeframe)
        )
        window = RepairWindow(
            window_start,
            window_end,
        )

        additional_data = {}
        if extra_data_loader is not None:
            additional_data = await extra_data_loader.fetch_for_symbol(symbol)

        db_started = time.perf_counter()
        try:
            saved_count = await self._candle_store.upsert_candles(
                symbol=symbol,
                timeframe=timeframe,
                candles=candles,
                additional_data=additional_data,
                window=window,
            )
        except Exception as exc:
            if self._telemetry is not None:
                self._telemetry.event(
                    "upsert_failed",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(exc),
                )
            if _is_db_outage_error(exc):
                raise DatabaseUnavailableError("database_unavailable") from exc
            raise
        await stats.record_db_write(
            latency_sec=time.perf_counter() - db_started,
            batch_size=len(candles),
        )
        return saved_count, last_ts

    async def _sync_symbol(
        self,
        *,
        symbol: str,
        timeframes: tuple[str, ...],
        extra_data_loader: _AdditionalDataLoader | None,
        stats: _SyncStats,
    ) -> dict[str, int]:
        per_tf: dict[str, int] = {}

        for timeframe in timeframes:
            total = 0
            before: str | None = None
            try:
                latest_stored_ts = await self._candle_store.get_latest_timestamp(
                    symbol=symbol,
                    timeframe=timeframe,
                )
            except Exception as exc:
                if _is_db_outage_error(exc):
                    raise DatabaseUnavailableError("database_unavailable") from exc
                raise
            while True:
                try:
                    count, last_ts = await self._sync_bar(
                        symbol=symbol,
                        timeframe=timeframe,
                        before=before,
                        latest_stored_ts=latest_stored_ts,
                        extra_data_loader=extra_data_loader,
                        stats=stats,
                    )
                except Exception as exc:
                    if "51000" in str(exc) and "Parameter bar error" in str(exc):
                        count, last_ts = 0, None
                    else:
                        raise
                total += count
                if (
                    latest_stored_ts is not None
                    and last_ts is not None
                    and int(last_ts) <= latest_stored_ts
                ):
                    break
                if count < self._retry_policy.request_limit() or not last_ts:
                    break
                before = last_ts
            per_tf[timeframe] = total
            await asyncio.sleep(random.uniform(0.2, 0.5))

        return per_tf

    async def run(self, request: SyncJobRequest) -> SyncJobResult:
        started_at = time.perf_counter()
        started_dt = datetime.now(UTC)
        timeframes = request.timeframes or DEFAULT_TIMEFRAMES
        stats = _SyncStats()
        total_candles_synced = 0
        total_symbols_processed = 0
        errors_count = 0
        results_by_symbol: dict[str, dict[str, int]] = {}

        extra_data_loader = (
            _AdditionalDataLoader(self._market_data) if request.extra_data else None
        )
        sync_run = SyncRun(
            correlation_id=uuid.uuid4().hex[:12],
            mode=request.mode.value,
            requested_symbols=request.symbols,
            requested_timeframes=tuple(timeframes),
            started_at=started_dt,
        )
        if self._telemetry is not None:
            self._telemetry.event(
                "sync_started",
                correlation_id=sync_run.correlation_id,
                mode=sync_run.mode,
                requested_symbols=len(sync_run.requested_symbols),
                requested_timeframes=",".join(sync_run.requested_timeframes),
            )

        async with self._market_data:
            await self._ensure_candle_store_ready()
            try:
                symbols = await self._resolve_symbols(request.symbols)
            except Exception as exc:
                if _is_db_outage_error(exc):
                    raise DatabaseUnavailableError("database_unavailable") from exc
                raise
            symbols = await self._filter_supported_symbols(symbols)
            semaphore = asyncio.Semaphore(request.max_concurrent_symbols)
            abort_requested = asyncio.Event()

            async def _run_symbol(symbol: str) -> None:
                nonlocal total_candles_synced, total_symbols_processed, errors_count

                async with semaphore:
                    if abort_requested.is_set():
                        return
                    if self._telemetry is not None:
                        self._telemetry.event(
                            "symbol_started",
                            correlation_id=sync_run.correlation_id,
                            symbol=symbol,
                        )
                    try:
                        result = await self._sync_symbol(
                            symbol=symbol,
                            timeframes=timeframes,
                            extra_data_loader=extra_data_loader,
                            stats=stats,
                        )
                        total_candles_synced += sum(result.values())
                        total_symbols_processed += 1
                        results_by_symbol[symbol] = result
                        if self._telemetry is not None:
                            self._telemetry.event(
                                "symbol_completed",
                                correlation_id=sync_run.correlation_id,
                                symbol=symbol,
                                rows_upserted=sum(result.values()),
                            )
                    except Exception as exc:
                        errors_count += 1
                        if isinstance(
                            exc, DatabaseUnavailableError
                        ) or _is_db_outage_error(exc):
                            abort_requested.set()
                            logger.exception(
                                "Database unavailable during swap sync; aborting remaining symbols"
                            )
                            raise DatabaseUnavailableError(
                                "database_unavailable"
                            ) from exc
                        logger.exception(
                            "Failed to sync symbol %s", symbol, exc_info=exc
                        )
                        results_by_symbol[symbol] = {}

            try:
                async with asyncio.TaskGroup() as tg:
                    for symbol in symbols:
                        tg.create_task(_run_symbol(symbol))
            except* DatabaseUnavailableError as eg:
                failed_run = SyncRun(
                    correlation_id=sync_run.correlation_id,
                    mode=sync_run.mode,
                    requested_symbols=sync_run.requested_symbols,
                    requested_timeframes=sync_run.requested_timeframes,
                    started_at=sync_run.started_at,
                    completed_at=datetime.now(UTC),
                    status=SyncRunStatus.ABORTED,
                    error_summary="database_unavailable",
                    aggregate_metrics={
                        "total_symbols_processed": total_symbols_processed,
                        "rows_upserted_total": total_candles_synced,
                        "errors_count": errors_count,
                    },
                )
                if self._telemetry is not None:
                    self._telemetry.event(
                        "sync_completed",
                        correlation_id=failed_run.correlation_id,
                        status=failed_run.status.value,
                        errors_count=errors_count,
                        rows_upserted_total=total_candles_synced,
                    )
                raise eg.exceptions[0] from eg.exceptions[0].__cause__

        duration = time.perf_counter() - started_at
        start_of_day_ms = int(
            datetime.now(UTC)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
            * 1000
        )
        try:
            today_fill = await self._candle_store.get_fill_stats(start_of_day_ms)
        except Exception as exc:
            if _is_db_outage_error(exc):
                raise DatabaseUnavailableError("database_unavailable") from exc
            raise

        if extra_data_loader is not None:
            stats.merge_extra_data_stats(extra_data_loader.snapshot_stats())

        completed_run = SyncRun(
            correlation_id=sync_run.correlation_id,
            mode=sync_run.mode,
            requested_symbols=sync_run.requested_symbols,
            requested_timeframes=sync_run.requested_timeframes,
            started_at=sync_run.started_at,
            completed_at=datetime.now(UTC),
            status=SyncRunStatus.COMPLETED,
            aggregate_metrics={
                "total_symbols_processed": total_symbols_processed,
                "rows_upserted_total": total_candles_synced,
                "errors_count": errors_count,
                "duration_sec": duration,
            },
        )
        if self._telemetry is not None:
            self._telemetry.event(
                "sync_completed",
                correlation_id=completed_run.correlation_id,
                status=completed_run.status.value,
                total_symbols=len(symbols),
                total_symbols_processed=total_symbols_processed,
                rows_upserted_total=total_candles_synced,
                errors_count=errors_count,
            )

        return SyncJobResult(
            mode=request.mode.value,
            timeframes=tuple(timeframes),
            total_symbols=len(symbols),
            symbols_count=len(symbols),
            total_symbols_processed=total_symbols_processed,
            rows_upserted_total=total_candles_synced,
            errors_count=errors_count,
            duration_sec=duration,
            candles_per_second=total_candles_synced / duration if duration > 0 else 0.0,
            symbols_per_second=len(symbols) / duration if duration > 0 else 0.0,
            results_by_symbol=results_by_symbol,
            endpoint_stats=stats.endpoint_stats,
            today_fill=today_fill,
            db_write=stats.db_write_summary(),
            sync_run=completed_run,
        )


async def refresh_instrument_catalog(
    *,
    instrument_catalog: InstrumentCatalogPort,
) -> list[str]:
    use_case = RefreshInstrumentCatalogUseCase(instrument_catalog=instrument_catalog)
    return await use_case.run()


async def run_candle_sync(
    request: SyncJobRequest,
    *,
    market_data: MarketDataPort,
    candle_store: CandleStorePort,
    instrument_catalog: InstrumentCatalogPort,
    retry_policy: RetryPolicy,
    telemetry: TelemetryPort | None = None,
) -> SyncJobResult:
    use_case = RunCandleSyncUseCase(
        market_data=market_data,
        candle_store=candle_store,
        instrument_catalog=instrument_catalog,
        retry_policy=retry_policy,
        telemetry=telemetry,
    )
    return await use_case.run(request)
