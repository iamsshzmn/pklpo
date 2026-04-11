from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from aiolimiter import AsyncLimiter

from src.candles.application.sync.policy import (
    MarketDataFailureKind,
    classify_market_data_failure,
)
from src.candles.domain.timeframes import TF_TO_MS
from src.candles.observability.tracer import trace_event

logger = logging.getLogger(__name__)

try:
    import ccxt.async_support as ccxt
except ImportError:  # pragma: no cover - handled at runtime
    ccxt = None

_TF_TO_CCXT = {
    "1H": "1h",
    "4H": "4h",
    "12H": "12h",
    "1D": "1d",
    "1W": "1w",
}


def _to_ccxt_symbol(inst_id: str) -> str:
    # BTC-USDT-SWAP -> BTC/USDT:USDT
    parts = inst_id.split("-")
    if len(parts) != 3 or parts[2] != "SWAP" or not parts[0] or not parts[1]:
        raise ValueError(
            "Unsupported instrument format. Expected BASE-QUOTE-SWAP, "
            f"got: {inst_id!r}"
        )
    base, quote, _kind = parts
    return f"{base}/{quote}:{quote}"


class CcxtOKXAdapter:
    """CCXT-backed market data adapter for the candles sync runtime."""

    _RETRIABLE_INIT_KINDS = frozenset({
        MarketDataFailureKind.TIMEOUT,
        MarketDataFailureKind.RATE_LIMIT,
        MarketDataFailureKind.TRANSIENT,
    })

    def __init__(
        self,
        max_requests_per_second: int = 80,
        timeout_seconds: float | None = None,
        max_init_retries: int = 3,
        init_retry_delay: float = 2.0,
    ) -> None:
        if ccxt is None:
            raise RuntimeError(
                "ccxt is not installed. Install `ccxt` or disable use_ccxt."
            )
        effective_timeout_seconds = 30 if timeout_seconds is None else timeout_seconds
        self._timeout_ms = int(effective_timeout_seconds * 1000)
        self._max_requests_per_second = max_requests_per_second
        self._exchange_config: dict[str, Any] = {
            "enableRateLimit": True,
            "timeout": self._timeout_ms,
        }
        self._exchange = ccxt.okx(self._exchange_config)
        self._max_init_retries = max_init_retries
        self._init_retry_delay = init_retry_delay
        # Adapter-local traffic shaping. Orchestrator should not depend on limiter internals.
        self._global_limiter = AsyncLimiter(max_requests_per_second, 1)
        self._candles_limiter = AsyncLimiter(16, 1)
        self._extra_data_limiter = AsyncLimiter(3, 1)
        self._instrument_limiters: dict[str, AsyncLimiter] = {}
        self._funding_instrument_limiters: dict[str, AsyncLimiter] = {}
        self._init_metrics: dict[str, Any] = {
            "load_markets_attempts": 0,
            "load_markets_retries": 0,
            "load_markets_duration_ms": 0.0,
            "load_markets_failure_kind": None,
            "load_markets_succeeded": False,
        }

    def _instrument_limiter(self, symbol: str) -> AsyncLimiter:
        if symbol not in self._instrument_limiters:
            self._instrument_limiters[symbol] = AsyncLimiter(27, 1)
        return self._instrument_limiters[symbol]

    def _funding_instrument_limiter(self, symbol: str) -> AsyncLimiter:
        if symbol not in self._funding_instrument_limiters:
            self._funding_instrument_limiters[symbol] = AsyncLimiter(2, 1)
        return self._funding_instrument_limiters[symbol]

    async def _recreate_exchange(self) -> None:
        """Close current exchange and create a fresh instance."""
        try:
            await self._exchange.close()
        except Exception:
            logger.debug("Ignoring error closing exchange during retry cleanup", exc_info=True)
        self._exchange = ccxt.okx(self._exchange_config)

    def snapshot_init_metrics(self) -> dict[str, Any]:
        return dict(self._init_metrics)

    async def __aenter__(self) -> CcxtOKXAdapter:
        last_error: BaseException | None = None
        for attempt in range(1 + self._max_init_retries):
            t0 = time.monotonic()
            trace_event(
                "load_markets.start",
                attempt=attempt + 1,
                max_attempts=1 + self._max_init_retries,
                timeout_ms=self._timeout_ms,
            )
            try:
                await self._exchange.load_markets()
                elapsed_ms = (time.monotonic() - t0) * 1000
                self._init_metrics.update(
                    {
                        "load_markets_attempts": attempt + 1,
                        "load_markets_retries": attempt,
                        "load_markets_duration_ms": elapsed_ms,
                        "load_markets_failure_kind": None,
                        "load_markets_succeeded": True,
                    }
                )
                trace_event(
                    "load_markets.success",
                    attempt=attempt + 1,
                    retries=attempt,
                    duration_ms=round(elapsed_ms, 3),
                )
                logger.info(
                    "load_markets succeeded (attempt=%d, elapsed_ms=%.0f)",
                    attempt + 1,
                    elapsed_ms,
                )
                return self
            except Exception as exc:
                elapsed_ms = (time.monotonic() - t0) * 1000
                failure_kind = classify_market_data_failure(exc)
                self._init_metrics.update(
                    {
                        "load_markets_attempts": attempt + 1,
                        "load_markets_retries": attempt,
                        "load_markets_duration_ms": elapsed_ms,
                        "load_markets_failure_kind": failure_kind.value,
                        "load_markets_succeeded": False,
                    }
                )
                trace_event(
                    "load_markets.failure",
                    attempt=attempt + 1,
                    max_attempts=1 + self._max_init_retries,
                    failure_kind=failure_kind.value,
                    duration_ms=round(elapsed_ms, 3),
                    retriable=failure_kind in self._RETRIABLE_INIT_KINDS,
                )
                logger.warning(
                    "load_markets failed (attempt=%d/%d, kind=%s, elapsed_ms=%.0f): %s",
                    attempt + 1,
                    1 + self._max_init_retries,
                    failure_kind.value,
                    elapsed_ms,
                    exc,
                )
                if failure_kind not in self._RETRIABLE_INIT_KINDS:
                    raise
                last_error = exc
                if attempt < self._max_init_retries:
                    await self._recreate_exchange()
                    await asyncio.sleep(self._init_retry_delay * (attempt + 1))

        # All retries exhausted — close the last exchange to prevent resource leak
        # (__aexit__ won't run because __aenter__ is failing).
        trace_event(
            "load_markets.exhausted",
            attempts=1 + self._max_init_retries,
            retries=self._max_init_retries,
            failure_kind=self._init_metrics.get("load_markets_failure_kind"),
        )
        try:
            await self._exchange.close()
        except Exception:
            logger.debug("Ignoring error closing exchange after exhausted retries", exc_info=True)
        assert last_error is not None
        raise last_error

    async def __aexit__(self, *exc: Any) -> None:
        await self._exchange.close()

    async def get_candles(
        self,
        *,
        inst_id: str,
        bar: str = "1m",
        limit: int = 300,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        symbol = _to_ccxt_symbol(inst_id)
        tf_ms = TF_TO_MS.get(bar, 60_000)
        ccxt_tf = _TF_TO_CCXT.get(bar, bar)

        since = None
        if before is not None:
            before_ms = int(before)
            since = max(0, before_ms - (limit * tf_ms))

        async with self._global_limiter:
            async with self._candles_limiter:
                async with self._instrument_limiter(inst_id):
                    rows = await self._exchange.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=ccxt_tf,
                        since=since,
                        limit=limit,
                        params={"instId": inst_id},
                    )
        rows.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "ts": int(r[0]),
                "open": r[1],
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "volume": r[5],
                "volCcy": None,
                "volUsd": None,
            }
            for r in rows
        ]

    async def get_instruments(self, inst_type: str = "SWAP") -> list[dict[str, Any]]:
        ccxt_type_map = {"SWAP": "swap", "SPOT": "spot", "FUTURES": "future"}
        target = ccxt_type_map.get(inst_type.upper(), inst_type.lower())
        results = []
        for mkt in self._exchange.markets.values():
            if mkt.get("type") != target or mkt.get("quote") != "USDT":
                continue
            info = mkt.get("info", {})
            results.append({
                "instId": info.get("instId", mkt.get("id")),
                "instType": inst_type.upper(),
                "baseCcy": mkt.get("base"),
                "quoteCcy": mkt.get("quote"),
                "settleCcy": info.get("settleCcy"),
                "ctType": info.get("ctType"),
                "ctVal": info.get("ctVal"),
                "state": info.get("state"),
                "listTime": info.get("listTime"),
                "minSz": info.get("minSz"),
                "maxSz": info.get("maxSz"),
                "minNotional": info.get("minNotional"),
            })
        return results

    async def get_funding_rates(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for inst_id in symbols:
            symbol = _to_ccxt_symbol(inst_id)
            async with self._global_limiter:
                async with self._extra_data_limiter:
                    async with self._funding_instrument_limiter(inst_id):
                        async with self._instrument_limiter(inst_id):
                            row = await self._exchange.fetch_funding_rate(
                                symbol=symbol, params={"instId": inst_id}
                            )
            out[inst_id] = {
                "instId": inst_id,
                "fundingRate": row.get("fundingRate"),
                "nextFundingRate": row.get("nextFundingRate"),
                "nextFundingTime": row.get("nextFundingTimestamp"),
                "fundingTime": row.get("fundingTimestamp"),
                "ts": row.get("timestamp"),
            }
        return out

    async def get_open_interest(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for inst_id in symbols:
            symbol = _to_ccxt_symbol(inst_id)
            async with self._global_limiter:
                async with self._extra_data_limiter:
                    async with self._instrument_limiter(inst_id):
                        row = await self._exchange.fetch_open_interest(
                            symbol=symbol, params={"instId": inst_id}
                        )
            out[inst_id] = {
                "instId": inst_id,
                "oi": row.get("openInterestAmount") or row.get("openInterestValue"),
                "oiCcy": "USDT",
                "ts": row.get("timestamp"),
            }
        return out
