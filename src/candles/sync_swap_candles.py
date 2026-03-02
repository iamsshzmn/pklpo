#!/usr/bin/env python3
"""
Module for syncing OKX swap OHLCV candles.
Includes historical/regular candle fetch and optional extra data such as
funding rate and open interest.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import random
import time
from typing import Any

from tqdm import tqdm

from src.candles.domain.timeframes import TF_TO_MS
from src.candles.infrastructure.adapters import build_market_data_adapter
from src.candles.infrastructure.extra_data import ExtraDataFetcher
from src.candles.instruments_service import (
    refresh_instruments_list,
    resolve_instruments_cache_file,
)
from src.candles.ports import CandleRepositoryPort, MarketDataAdapterPort
from src.candles.repository import SwapCandlesRepository
from src.candles.sync_policy import SwapSyncPolicy
from src.logging import get_logger, setup_logging

# Logging
logger = get_logger("candles.sync_swap_candles")

# Supported swap timeframes
SWAP_BARS = list(TF_TO_MS.keys())

# Default runtime configuration
DEFAULT_CONFIG = {
    "max_requests_per_second": 80,  # Global request rate limiter
    "batch_size": 300,  # Candles per request
    "max_retries": 3,
    "retry_delay": 1.0,
    "max_concurrent_symbols": 3,  # Parallel symbol workers
    "extra_data": False,  # Disable optional metrics by default (avoid 429)
    "use_ccxt": True,
}


class UnavailableMarketDataAdapter:
    """Adapter placeholder used when no runtime adapter can be initialized."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    async def __aenter__(self) -> UnavailableMarketDataAdapter:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get_candles(self, **kwargs):
        raise RuntimeError(self._reason)

    async def get_funding_rates(self, symbols):
        raise RuntimeError(self._reason)

    async def get_open_interest(self, symbols):
        raise RuntimeError(self._reason)


class SwapCandlesSync:
    """
    Sync service for OKX swap candles.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        repository: CandleRepositoryPort | None = None,
        market_adapter: MarketDataAdapterPort | None = None,
        extra_data_fetcher: ExtraDataFetcher | None = None,
    ):
        """
        Initialize sync service.

        Args:
            config: Runtime sync configuration.
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}

        # Build adapters and policies.
        self.okx_client: MarketDataAdapterPort = (
            market_adapter or self._build_market_adapter()
        )
        self.repository = repository or SwapCandlesRepository()
        self.sync_policy = SwapSyncPolicy(
            max_retries=int(self.config.get("max_retries", 3)),
            retry_delay=float(self.config.get("retry_delay", 1.0)),
            batch_size=int(self.config.get("batch_size", 300)),
        )
        # Symbol list is resolved from input/file/DB fallback at runtime.

        if self.config.get("extra_data", False):
            self.extra_data_fetcher = extra_data_fetcher or ExtraDataFetcher(
                self.okx_client
            )
        else:
            self.extra_data_fetcher = None

        # Endpoint-level counters.
        self.endpoint_stats: dict[str, dict[str, float]] = {
            "candles": {"ok": 0, "retries": 0, "rate_limit": 0},
        }

        # Aggregated run metrics.
        self.total_candles_synced = 0
        self.total_symbols_processed = 0
        self.errors_count = 0
        self._db_write_latencies_sec: list[float] = []
        self._db_write_batch_sizes: list[int] = []

        logger.info("SwapCandlesSync initialized with config: %s", self.config)
        logger.debug(f"Rate limiter: {self.config['max_requests_per_second']} req/s")
        logger.debug(f"Batch size: {self.config['batch_size']} candles")
        logger.debug(f"Max concurrent symbols: {self.config['max_concurrent_symbols']}")

    def _build_market_adapter(self) -> MarketDataAdapterPort:
        try:
            adapter = build_market_data_adapter(self.config)
            logger.info("Initialized market adapter: %s", adapter.__class__.__name__)
            return adapter
        except Exception as exc:
            logger.warning("Adapter init failed (%s), fallback to legacy", exc)
            try:
                return build_market_data_adapter(
                    {
                        "adapter": "legacy",
                        "legacy_adapter_factory": self.config.get("legacy_adapter_factory"),
                    }
                )
            except Exception as fallback_exc:
                reason = (
                    "No market adapter available. Primary init failed: "
                    f"{exc}. Legacy fallback failed: {fallback_exc}"
                )
                logger.error(reason)
                return UnavailableMarketDataAdapter(reason)

    @staticmethod
    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = int(round((len(ordered) - 1) * pct))
        return ordered[index]

    async def resolve_symbols(self, symbols: list[str] | None) -> list[str]:
        """
        Resolve symbol list for sync.
        1) If symbols are passed explicitly, use them.
        2) Otherwise refresh cache and load symbols from file (or DB fallback).
        """
        if symbols:
            logger.info("Using provided symbols: %s", len(symbols))
            return symbols

        logger.info("Refreshing instruments list...")
        await refresh_instruments_list(repository=self.repository, logger=logger)

        # Load refreshed list from file cache.
        instruments_file = resolve_instruments_cache_file()
        if instruments_file.exists():
            try:
                with open(instruments_file, encoding="utf-8") as f:
                    file_symbols: list[str] = json.load(f)
                logger.info(
                    "Loaded %s symbols from refreshed cache file %s",
                    len(file_symbols),
                    instruments_file,
                )
                return file_symbols
            except Exception as e:
                logger.warning(
                    "Failed to read symbols from cache file (%s). Falling back to DB.",
                    e,
                )

        # Fallback to repository read-model if file cache is unavailable.
        logger.info("Loading swap symbols from repository fallback")
        symbols_list = await self.repository.fetch_swap_usdt_symbols()
        logger.info("Loaded %s swap symbols from repository fallback", len(symbols_list))
        return symbols_list

    async def sync_swap_bar(
        self, symbol: str, timeframe: str, before: str | None = None
    ) -> tuple[int, str | None]:
        """
        Sync one timeframe page for one symbol.

        Args:
            symbol: Instrument symbol.
            timeframe: Candle timeframe.
            before: Pagination timestamp.

        Returns:
            Tuple: (saved_count, last_timestamp).
        """
        try:
            logger.debug("Fetching candles %s %s (before=%s)", symbol, timeframe, before)
            # Exponential backoff with jitter on 429/5xx errors.
            attempts = 0
            delay = self.sync_policy.initial_delay()
            requested_limit = self.sync_policy.request_limit()
            while True:
                try:
                    candles = await self.okx_client.get_candles(
                        inst_id=symbol,
                        bar=timeframe,
                        limit=requested_limit,
                        before=before,
                    )
                    self.endpoint_stats["candles"]["ok"] += 1
                    break
                except Exception as fetch_err:
                    msg = str(fetch_err)
                    retriable = self.sync_policy.is_retriable(msg)
                    if not retriable or not self.sync_policy.can_retry(attempts):
                        raise
                    attempts += 1
                    if self.sync_policy.is_rate_limited(msg):
                        self.endpoint_stats["candles"]["rate_limit"] += 1
                    self.endpoint_stats["candles"]["retries"] += 1
                    sleep_for = self.sync_policy.next_sleep(delay)
                    logger.warning(
                        "%s %s: request limited/failed, retry in %.2fs (attempt %s)",
                        symbol,
                        timeframe,
                        sleep_for,
                        attempts,
                    )
                    await asyncio.sleep(sleep_for)
                    delay = self.sync_policy.bump_delay(delay)

            if not candles:
                logger.debug("No candles returned for %s %s", symbol, timeframe)
                return 0, None

            logger.debug("Received %s candles for %s %s", len(candles), symbol, timeframe)
            # Optional extra data for swap instruments.
            additional_data = await self._get_swap_additional_data(symbol)

            # Persist to DB.
            saved_count = await self._save_swap_candles(
                symbol, timeframe, candles, additional_data
            )
            last_ts: str | None = str(candles[-1]["ts"]) if candles else None
            logger.debug("Saved %s candles for %s %s", saved_count, symbol, timeframe)
            return saved_count, last_ts

        except Exception as e:
            if "51000" in str(e) and "Parameter bar error" in str(e):
                logger.warning("%s: timeframe %s is not supported", symbol, timeframe)
                return 0, None
            logger.error("Failed syncing %s %s: %s", symbol, timeframe, e)
            self.errors_count += 1
            raise

    async def _get_swap_additional_data(self, symbol: str) -> dict[str, Any]:
        """
        Fetch optional extra data for swap candles.

        Args:
            symbol: Instrument symbol.
        Returns:
            Extra data map.
        """
        if self.extra_data_fetcher is None:
            logger.debug("Extra data is disabled for %s", symbol)
            return {}

        logger.debug("Fetching extra data for %s", symbol)
        return await self.extra_data_fetcher.fetch_for_symbol(symbol)

    async def _save_swap_candles(
        self,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        additional_data: dict[str, Any],
    ) -> int:
        """
        Save swap candles to DB through repository abstraction.
        """
        started = time.perf_counter()
        saved_count = await self.repository.upsert_swap_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            additional_data=additional_data,
        )
        elapsed = time.perf_counter() - started
        self._db_write_latencies_sec.append(elapsed)
        self._db_write_batch_sizes.append(len(candles))
        logger.debug(
            "Persisted %s candles via repository for %s %s in %.4fs (batch=%s)",
            saved_count,
            symbol,
            timeframe,
            elapsed,
            len(candles),
        )
        return saved_count

    async def sync_swap_symbol(
        self, symbol: str, timeframes: list[str] | None = None
    ) -> dict[str, int]:
        """
        Sync all requested timeframes for one symbol.

        Args:
            symbol: Instrument symbol.
            timeframes: Timeframes to sync.

        Returns:
            Synced candles count by timeframe.
        """
        if timeframes is None:
            timeframes = SWAP_BARS

        stats: dict[str, int] = {}

        async def sync_one_tf(tf: str) -> tuple[str, int]:
            total = 0
            before_local: str | None = None
            logger.debug("Start sync for %s %s", symbol, tf)
            while True:
                count, last_ts = await self.sync_swap_bar(symbol, tf, before_local)
                total += count
                if count < self.sync_policy.request_limit() or not last_ts:
                    break
                before_local = last_ts
                logger.debug("%s %s: fetched=%s, total=%s", symbol, tf, count, total)
            logger.info("%s %s: synced %s candles", symbol, tf, total)
            return tf, total

        # Run sequentially by timeframe to reduce API pressure.
        logger.debug(
            "Running sequential sync for %s timeframes on %s",
            len(timeframes),
            symbol,
        )
        for tf in timeframes:
            tf_name, total = await sync_one_tf(tf)
            stats[tf_name] = total
            # Small jitter between timeframe loops.
            await asyncio.sleep(random.uniform(0.2, 0.5))

        return stats

    async def sync_all_swap_candles(
        self, symbols: list[str] | None = None, timeframes: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Sync all swap candles.

        Args:
            symbols: Optional explicit symbol list.
            timeframes: Optional explicit timeframe list.

        Returns:
            Aggregated sync statistics.
        """
        logger.info("Starting swap candles sync...")

        start_time = datetime.datetime.now()

        try:
            # Ensure HTTP session lifecycle is handled by the adapter.
            async with self.okx_client:
                # Resolve symbol list from input/file/DB fallback.
                symbols = await self.resolve_symbols(symbols)

                logger.info("Will sync %s swap symbols", len(symbols))
                logger.info("Timeframes: %s", timeframes or SWAP_BARS)
                logger.info("Runtime config: %s", self.config)

                # Process symbols in parallel with semaphore guard.
                max_concurrent = self.config.get("max_concurrent_symbols", 1)
                semaphore = asyncio.Semaphore(max_concurrent)
                results = {}

                logger.info(
                    f"Starting parallel symbol sync for {len(symbols)} symbols "
                    f"(max_concurrent={max_concurrent})"
                )

                async def sync_symbol_with_semaphore(
                    symbol: str,
                ) -> tuple[str, dict[str, int] | Exception]:
                    """Sync one symbol with semaphore-limited concurrency."""
                    async with semaphore:
                        try:
                            logger.info("Syncing symbol: %s", symbol)
                            result = await self.sync_swap_symbol(symbol, timeframes)

                            # Update shared stats (safe in single-threaded event loop).
                            for _timeframe, count in result.items():
                                self.total_candles_synced += count
                            self.total_symbols_processed += 1

                            total_candles = sum(result.values())
                            logger.info(
                                "Symbol %s completed: %s candles",
                                symbol,
                                total_candles,
                            )
                            return symbol, result
                        except Exception as e:
                            logger.error(
                                "Error syncing symbol %s: %s",
                                symbol,
                                e,
                            )
                            # sync_swap_bar already increments error counters for
                            # failed sync attempts; avoid double counting here.
                            return symbol, e

                # Create tasks for all symbols.
                tasks = [
                    asyncio.create_task(sync_symbol_with_semaphore(symbol))
                    for symbol in symbols
                ]

                # Collect results as tasks complete.
                with tqdm(total=len(symbols), desc="Swap sync") as pbar:
                    for coro in asyncio.as_completed(tasks):
                        symbol, result = await coro
                        if isinstance(result, Exception):
                            results[symbol] = {}
                        else:
                            results[symbol] = result
                        pbar.update(1)

            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Read today's fill statistics.
            today_stats = {
                "rows_today": 0,
                "funding_rate_non_null": 0,
                "open_interest_non_null": 0,
                "funding_rate_fill_pct": 0.0,
                "open_interest_fill_pct": 0.0,
            }

            try:
                start_of_day_ms = int(
                    datetime.datetime.utcnow()
                    .replace(hour=0, minute=0, second=0, microsecond=0)
                    .timestamp()
                    * 1000
                )
                today_stats = await self.repository.fetch_today_fill_stats(start_of_day_ms)
            except Exception as e:
                logger.warning("Failed to compute today's fill stats: %s", e)

            # Build DB write stats.
            db_write_stats = {
                "writes_count": len(self._db_write_latencies_sec),
                "latency_avg_ms": (
                    round(
                        (sum(self._db_write_latencies_sec) / len(self._db_write_latencies_sec))
                        * 1000.0,
                        3,
                    )
                    if self._db_write_latencies_sec
                    else 0.0
                ),
                "latency_p95_ms": round(
                    self._percentile(self._db_write_latencies_sec, 0.95) * 1000.0,
                    3,
                ),
                "batch_size_avg": (
                    round(sum(self._db_write_batch_sizes) / len(self._db_write_batch_sizes), 2)
                    if self._db_write_batch_sizes
                    else 0.0
                ),
                "batch_size_max": max(self._db_write_batch_sizes) if self._db_write_batch_sizes else 0,
            }

            total_stats = {
                "total_symbols": len(symbols),
                "total_candles_synced": self.total_candles_synced,
                "total_symbols_processed": self.total_symbols_processed,
                "errors_count": self.errors_count,
                "duration_seconds": duration,
                "symbols_per_second": len(symbols) / duration if duration > 0 else 0,
                "candles_per_second": (
                    self.total_candles_synced / duration if duration > 0 else 0
                ),
                "results_by_symbol": results,
                "endpoint_stats": self.endpoint_stats,
                "today_fill": today_stats,
                "db_write": db_write_stats,
            }
            if self.extra_data_fetcher is not None:
                total_stats["endpoint_stats"].update(
                    self.extra_data_fetcher.snapshot_stats()
                )

            logger.info("Swap candles sync completed")
            logger.info("Summary:")
            logger.info("  Symbols processed: %s", total_stats["total_symbols"])
            logger.info(
                "  Candles synced: %s",
                f"{total_stats['total_candles_synced']:,}",
            )
            logger.info("  Errors: %s", total_stats["errors_count"])
            logger.info(
                "  Duration: %.2f sec",
                total_stats["duration_seconds"],
            )
            logger.info(
                "  Throughput: %.2f candles/sec",
                total_stats["candles_per_second"],
            )
            logger.info(
                "  DB write p95: %.3f ms, avg: %.3f ms, avg batch: %.2f",
                total_stats["db_write"]["latency_p95_ms"],
                total_stats["db_write"]["latency_avg_ms"],
                total_stats["db_write"]["batch_size_avg"],
            )
            logger.debug("Detailed stats: %s", total_stats)

            return total_stats

        except Exception as e:
            logger.error("Critical error during swap candle sync: %s", e)
            raise


async def sync_swap_candles(
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Top-level API for swap candles sync.

    Args:
        symbols: Optional explicit symbol list.
        timeframes: Optional explicit timeframe list.
        config: Runtime sync configuration.

    Returns:
        Aggregated sync statistics.
    """
    sync = SwapCandlesSync(config)
    return await sync.sync_all_swap_candles(symbols, timeframes)


if __name__ == "__main__":
    # Configure logging.
    setup_logging(level="INFO")
    logger.info("Launching swap candles sync module")

    # Run sync.
    asyncio.run(sync_swap_candles())
