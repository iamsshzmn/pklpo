from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import UTC, datetime
from typing import Any

from ...domain.timeframes import TF_TO_MS
from .dto import SyncJobRequest, SyncJobResult
from .policy import RetryPolicy
from .ports import CandleStorePort, InstrumentCatalogPort, MarketDataPort

logger = logging.getLogger(__name__)

DEFAULT_TIMEFRAMES = tuple(TF_TO_MS.keys())


class RefreshInstrumentCatalogUseCase:
    def __init__(self, *, instrument_catalog: InstrumentCatalogPort) -> None:
        self._instrument_catalog = instrument_catalog

    async def run(self) -> list[str]:
        return await self._instrument_catalog.refresh_catalog()


class _AdditionalDataLoader:
    def __init__(self, market_data: MarketDataPort) -> None:
        self._market_data = market_data
        self._stats: dict[str, dict[str, float]] = {
            "funding": {"ok": 0, "retries": 0, "rate_limit": 0, "errors": 0},
            "open_interest": {"ok": 0, "retries": 0, "rate_limit": 0, "errors": 0},
        }

    @staticmethod
    def _is_rate_limited(message: str) -> bool:
        return any(marker in message for marker in ("429", "Too Many Requests", "50011"))

    async def fetch_for_symbol(self, symbol: str) -> dict[str, Any]:
        out: dict[str, Any] = {}

        try:
            funding = await self._market_data.fetch_funding_rates([symbol])
            if funding.get(symbol):
                self._stats["funding"]["ok"] += 1
                out["funding_rate"] = funding[symbol]
        except Exception as exc:
            if self._is_rate_limited(str(exc)):
                self._stats["funding"]["rate_limit"] += 1
                self._stats["funding"]["retries"] += 1
            else:
                self._stats["funding"]["errors"] += 1

        try:
            open_interest = await self._market_data.fetch_open_interest([symbol])
            if open_interest.get(symbol):
                self._stats["open_interest"]["ok"] += 1
                out["open_interest"] = open_interest[symbol]
        except Exception as exc:
            if self._is_rate_limited(str(exc)):
                self._stats["open_interest"]["rate_limit"] += 1
                self._stats["open_interest"]["retries"] += 1
            else:
                self._stats["open_interest"]["errors"] += 1

        return out

    def snapshot_stats(self) -> dict[str, dict[str, float]]:
        return {endpoint: values.copy() for endpoint, values in self._stats.items()}


class RunCandleSyncUseCase:
    def __init__(
        self,
        *,
        market_data: MarketDataPort,
        candle_store: CandleStorePort,
        instrument_catalog: InstrumentCatalogPort,
        retry_policy: RetryPolicy,
    ) -> None:
        self._market_data = market_data
        self._candle_store = candle_store
        self._instrument_catalog = instrument_catalog
        self._retry_policy = retry_policy
        self._last_api_latency_ms: float = 0.0

    @staticmethod
    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = int(round((len(ordered) - 1) * pct))
        return ordered[index]

    async def _resolve_symbols(self, requested_symbols: tuple[str, ...]) -> list[str]:
        if requested_symbols:
            return list(requested_symbols)

        refreshed = await self._instrument_catalog.refresh_catalog()
        if refreshed:
            return refreshed

        cached = await self._instrument_catalog.load_cached_symbols()
        if cached:
            return cached

        return await self._instrument_catalog.list_symbols()

    async def _sync_bar(
        self,
        *,
        symbol: str,
        timeframe: str,
        before: str | None,
        latest_stored_ts: int | None,
        extra_data_loader: _AdditionalDataLoader | None,
        endpoint_stats: dict[str, dict[str, float]],
        db_write_latencies_sec: list[float],
        db_write_batch_sizes: list[int],
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
                endpoint_stats["candles"]["ok"] += 1
                break
            except Exception as exc:
                message = str(exc)
                if (
                    not self._retry_policy.is_retriable(message)
                    or not self._retry_policy.can_retry(attempts)
                ):
                    raise
                attempts += 1
                if self._retry_policy.is_rate_limited(message):
                    endpoint_stats["candles"]["rate_limit"] += 1
                endpoint_stats["candles"]["retries"] += 1
                await asyncio.sleep(self._retry_policy.next_sleep(delay))
                delay = self._retry_policy.bump_delay(delay)

        if not candles:
            return 0, None

        last_ts = str(candles[-1]["ts"])
        if latest_stored_ts is not None:
            candles = [c for c in candles if int(c["ts"]) > latest_stored_ts]
            if not candles:
                return 0, last_ts

        additional_data = {}
        if extra_data_loader is not None:
            additional_data = await extra_data_loader.fetch_for_symbol(symbol)

        db_started = time.perf_counter()
        saved_count = await self._candle_store.upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            additional_data=additional_data,
        )
        db_write_latencies_sec.append(time.perf_counter() - db_started)
        db_write_batch_sizes.append(len(candles))
        return saved_count, last_ts

    async def _sync_symbol(
        self,
        *,
        symbol: str,
        timeframes: tuple[str, ...],
        extra_data_loader: _AdditionalDataLoader | None,
        endpoint_stats: dict[str, dict[str, float]],
        db_write_latencies_sec: list[float],
        db_write_batch_sizes: list[int],
    ) -> dict[str, int]:
        stats: dict[str, int] = {}

        for timeframe in timeframes:
            total = 0
            before: str | None = None
            latest_stored_ts = await self._candle_store.get_latest_timestamp(
                symbol=symbol,
                timeframe=timeframe,
            )
            while True:
                try:
                    count, last_ts = await self._sync_bar(
                        symbol=symbol,
                        timeframe=timeframe,
                        before=before,
                        latest_stored_ts=latest_stored_ts,
                        extra_data_loader=extra_data_loader,
                        endpoint_stats=endpoint_stats,
                        db_write_latencies_sec=db_write_latencies_sec,
                        db_write_batch_sizes=db_write_batch_sizes,
                    )
                except Exception as exc:
                    if "51000" in str(exc) and "Parameter bar error" in str(exc):
                        count, last_ts = 0, None
                    else:
                        raise
                total += count
                if latest_stored_ts is not None and last_ts is not None:
                    if int(last_ts) <= latest_stored_ts:
                        break
                if count < self._retry_policy.request_limit() or not last_ts:
                    break
                before = last_ts
            stats[timeframe] = total
            await asyncio.sleep(random.uniform(0.2, 0.5))

        return stats

    async def run(self, request: SyncJobRequest) -> SyncJobResult:
        started_at = time.perf_counter()
        timeframes = request.timeframes or DEFAULT_TIMEFRAMES
        endpoint_stats: dict[str, dict[str, float]] = {
            "candles": {"ok": 0, "retries": 0, "rate_limit": 0},
        }
        db_write_latencies_sec: list[float] = []
        db_write_batch_sizes: list[int] = []
        total_candles_synced = 0
        total_symbols_processed = 0
        errors_count = 0
        results_by_symbol: dict[str, dict[str, int]] = {}

        extra_data_loader = (
            _AdditionalDataLoader(self._market_data) if request.extra_data else None
        )

        async with self._market_data:
            symbols = await self._resolve_symbols(request.symbols)
            semaphore = asyncio.Semaphore(request.max_concurrent_symbols)

            async def _run_symbol(symbol: str) -> tuple[str, dict[str, int] | Exception]:
                nonlocal total_candles_synced
                nonlocal total_symbols_processed
                nonlocal errors_count

                async with semaphore:
                    try:
                        result = await self._sync_symbol(
                            symbol=symbol,
                            timeframes=timeframes,
                            extra_data_loader=extra_data_loader,
                            endpoint_stats=endpoint_stats,
                            db_write_latencies_sec=db_write_latencies_sec,
                            db_write_batch_sizes=db_write_batch_sizes,
                        )
                        total_candles_synced += sum(result.values())
                        total_symbols_processed += 1
                        return symbol, result
                    except Exception as exc:
                        errors_count += 1
                        logger.exception("Failed to sync symbol %s", symbol, exc_info=exc)
                        return symbol, exc

            tasks = [asyncio.create_task(_run_symbol(symbol)) for symbol in symbols]
            for task in asyncio.as_completed(tasks):
                symbol, result = await task
                results_by_symbol[symbol] = result if isinstance(result, dict) else {}

        duration = time.perf_counter() - started_at
        start_of_day_ms = int(
            datetime.now(UTC)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
            * 1000
        )
        today_fill = await self._candle_store.get_fill_stats(start_of_day_ms)
        db_write = {
            "writes_count": len(db_write_latencies_sec),
            "latency_avg_ms": (
                round(sum(db_write_latencies_sec) / len(db_write_latencies_sec) * 1000, 3)
                if db_write_latencies_sec
                else 0.0
            ),
            "latency_p95_ms": round(
                self._percentile(db_write_latencies_sec, 0.95) * 1000.0,
                3,
            ),
            "batch_size_avg": (
                round(sum(db_write_batch_sizes) / len(db_write_batch_sizes), 2)
                if db_write_batch_sizes
                else 0.0
            ),
            "batch_size_max": max(db_write_batch_sizes) if db_write_batch_sizes else 0,
        }

        if extra_data_loader is not None:
            endpoint_stats.update(extra_data_loader.snapshot_stats())

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
            endpoint_stats=endpoint_stats,
            today_fill=today_fill,
            db_write=db_write,
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
) -> SyncJobResult:
    use_case = RunCandleSyncUseCase(
        market_data=market_data,
        candle_store=candle_store,
        instrument_catalog=instrument_catalog,
        retry_policy=retry_policy,
    )
    return await use_case.run(request)
