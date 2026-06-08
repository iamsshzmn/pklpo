from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from aiolimiter import AsyncLimiter

from src.candles.application.sync.policy import (
    MarketDataFailureKind,
    classify_market_data_failure,
)
from src.candles.domain.timeframes import TF_TO_MS
from src.candles.infrastructure.client import OKXClient
from src.candles.observability.tracer import trace_event

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

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

_HISTORY_ENDPOINT = "/api/v5/market/history-candles"
_HISTORY_PAGE_LIMIT = 100
_OKX_HISTORY_UTC_BARS = {
    "1D": "1Dutc",
    "1W": "1Wutc",
    "1M": "1Mutc",
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


class _OKXHistoryCandlesClient:
    _RETRIABLE_FAILURE_KINDS = frozenset(
        {
            MarketDataFailureKind.TIMEOUT,
            MarketDataFailureKind.RATE_LIMIT,
            MarketDataFailureKind.TRANSIENT,
        }
    )

    def __init__(
        self,
        *,
        request: Callable[..., Awaitable[dict[str, Any]]],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        trace: Callable[..., None] = trace_event,
        page_limit: int = _HISTORY_PAGE_LIMIT,
        max_transport_retries: int = 3,
        max_partial_retries: int = 3,
        backoff_base_seconds: float = 0.5,
    ) -> None:
        self._request = request
        self._sleep = sleep
        self._trace = trace
        self._page_limit = page_limit
        self._max_transport_retries = max_transport_retries
        self._max_partial_retries = max_partial_retries
        self._backoff_base_seconds = backoff_base_seconds

    async def fetch_range(
        self,
        *,
        inst_id: str,
        bar: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        if start_ts_ms >= end_ts_ms:
            return []

        tf_ms = TF_TO_MS.get(bar)
        if tf_ms is None:
            raise ValueError(f"Unsupported timeframe for history fetch: {bar}")

        collected: dict[int, dict[str, Any]] = {}
        cursor = end_ts_ms - tf_ms
        while cursor >= start_ts_ms:
            page_end_ts_ms = min(end_ts_ms, cursor + tf_ms)
            page_start_ts_ms = max(
                start_ts_ms,
                page_end_ts_ms - (self._page_limit * tf_ms),
            )
            page = await self._fetch_page(
                inst_id=inst_id,
                bar=bar,
                page_start_ts_ms=page_start_ts_ms,
                page_end_ts_ms=page_end_ts_ms,
            )
            for candle in page["candles"]:
                collected.setdefault(int(candle["ts"]), candle)

            oldest_ts = page["oldest_ts"]
            if oldest_ts is None:
                break
            if oldest_ts <= start_ts_ms:
                break

            next_cursor = oldest_ts - tf_ms
            if next_cursor >= cursor:
                break
            cursor = next_cursor

        return [collected[ts] for ts in sorted(collected)]

    async def _fetch_page(
        self,
        *,
        inst_id: str,
        bar: str,
        page_start_ts_ms: int,
        page_end_ts_ms: int,
    ) -> dict[str, Any]:
        tf_ms = TF_TO_MS[bar]
        params = {
            "instId": inst_id,
            "bar": self._okx_history_bar(bar),
            # OKX history-candles semantics are direction-sensitive:
            # "before" returns newer rows and "after" returns older rows.
            # For a half-open window [page_start_ts_ms, page_end_ts_ms), the
            # lower bound must therefore go to "before" and the upper bound to
            # "after". OKX excludes the row whose ts equals "before", so shift
            # back by one storage bar and keep local [start, end) filtering.
            "before": str(max(0, page_start_ts_ms - tf_ms)),
            "after": str(page_end_ts_ms),
            "limit": str(self._page_limit),
        }
        expected_rows = max(0, (page_end_ts_ms - page_start_ts_ms) // tf_ms)
        candles_by_ts: dict[int, dict[str, Any]] = {}
        partial_attempts = 0
        transport_attempts = 0

        while True:
            try:
                payload = await self._request(path=_HISTORY_ENDPOINT, params=params)
            except Exception as exc:
                failure_kind = classify_market_data_failure(exc)
                if (
                    failure_kind not in self._RETRIABLE_FAILURE_KINDS
                    or transport_attempts >= self._max_transport_retries
                ):
                    raise
                await self._sleep(self._backoff_seconds(transport_attempts))
                transport_attempts += 1
                continue

            for candle in self._normalize_rows(
                payload.get("data", []),
                page_start_ts_ms=page_start_ts_ms,
                page_end_ts_ms=page_end_ts_ms,
            ):
                candles_by_ts[int(candle["ts"])] = candle

            received_rows = len(candles_by_ts)
            oldest_ts = min(candles_by_ts) if candles_by_ts else None
            newest_ts = max(candles_by_ts) if candles_by_ts else None
            status = self._page_status(
                received_rows=received_rows,
                expected_rows=expected_rows,
            )

            if status != "PARTIAL" or partial_attempts >= self._max_partial_retries:
                self._trace(
                    "okx.history_candles.page",
                    endpoint="history-candles",
                    symbol=inst_id,
                    timeframe=bar,
                    okx_bar=params["bar"],
                    requested_start_ts_ms=page_start_ts_ms,
                    requested_end_ts_ms=page_end_ts_ms,
                    received_rows=received_rows,
                    expected_rows=expected_rows,
                    oldest_ts=oldest_ts,
                    newest_ts=newest_ts,
                    status=status,
                    before=params["before"],
                    after=params["after"],
                    limit=self._page_limit,
                )
                return {
                    "candles": [candles_by_ts[ts] for ts in sorted(candles_by_ts)],
                    "oldest_ts": oldest_ts,
                    "newest_ts": newest_ts,
                    "status": status,
                }

            await self._sleep(self._backoff_seconds(partial_attempts))
            partial_attempts += 1

    def _normalize_rows(
        self,
        rows: list[list[Any]],
        *,
        page_start_ts_ms: int,
        page_end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        candles_by_ts: dict[int, dict[str, Any]] = {}
        for row in rows:
            ts = int(row[0])
            if not page_start_ts_ms <= ts < page_end_ts_ms:
                continue
            candles_by_ts[ts] = {
                "ts": ts,
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
                "volCcy": row[6] if len(row) > 6 else None,
                "volUsd": row[7] if len(row) > 7 else None,
            }
        return [candles_by_ts[ts] for ts in sorted(candles_by_ts)]

    @staticmethod
    def _page_status(*, received_rows: int, expected_rows: int) -> str:
        if received_rows == 0:
            return "EMPTY"
        if received_rows < expected_rows:
            return "PARTIAL"
        return "OK"

    @staticmethod
    def _okx_history_bar(bar: str) -> str:
        return _OKX_HISTORY_UTC_BARS.get(bar, bar)

    def _backoff_seconds(self, attempt: int) -> float:
        return self._backoff_base_seconds * (2**attempt)


class CcxtOKXAdapter:
    """CCXT-backed market data adapter for the candles sync runtime."""

    _RETRIABLE_INIT_KINDS = frozenset(
        {
            MarketDataFailureKind.TIMEOUT,
            MarketDataFailureKind.RATE_LIMIT,
            MarketDataFailureKind.TRANSIENT,
        }
    )

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
        # Adapter-local traffic shaping. Orchestrator should not depend on limiter internals.
        self._global_limiter = AsyncLimiter(max_requests_per_second, 1)
        self._candles_limiter = AsyncLimiter(16, 1)
        self._extra_data_limiter = AsyncLimiter(3, 1)
        self._instrument_limiters: dict[str, AsyncLimiter] = {}
        self._funding_instrument_limiters: dict[str, AsyncLimiter] = {}
        self._history_transport = OKXClient(
            timeout=int(effective_timeout_seconds),
            instrument_limiter=self._instrument_limiters,
            public_limiter=self._global_limiter,
        )
        self._history_client = _OKXHistoryCandlesClient(request=self._history_request)
        self._max_init_retries = max_init_retries
        self._init_retry_delay = init_retry_delay
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
            logger.debug(
                "Ignoring error closing exchange during retry cleanup", exc_info=True
            )
        self._exchange = ccxt.okx(self._exchange_config)

    async def _history_request(
        self, *, path: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        async with self._candles_limiter:
            return await self._history_transport._request(
                "GET",
                path,
                params=params,
                symbol=str(params["instId"]),
                is_public=True,
            )

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
                history_transport = getattr(self, "_history_transport", None)
                if history_transport is not None:
                    await history_transport.__aenter__()
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
            logger.debug(
                "Ignoring error closing exchange after exhausted retries", exc_info=True
            )
        assert last_error is not None
        raise last_error

    async def __aexit__(self, *exc: Any) -> None:
        history_transport = getattr(self, "_history_transport", None)
        if history_transport is not None:
            await history_transport.__aexit__(*exc)
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

    async def _get_history_candles_via_ccxt_legacy(
        self,
        *,
        inst_id: str,
        bar: str = "1m",
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        """Range-based candle fetch for historical backfill / gap repair.

        Returns candles whose ``ts`` falls within ``[start_ts_ms, end_ts_ms)``.
        Paginates forward using ``since = last_ts + tf_ms`` and keeps the per
        page limit at 100 so it works against both OKX endpoints.

        NOTE / root cause for the rows_written=0 bug in repair apply path
        =================================================================
        The fast-path :meth:`get_candles` paginates by a ``before`` cursor and
        assumes every page returns ``limit`` (up to 300) candles. ccxt's OKX
        ``fetch_ohlcv`` auto-switches to ``/api/v5/market/history-candles``
        when ``since`` is older than ~24h, and silently caps ``limit`` at 100.
        The old repair range-fetcher combined that with
        ``since = before - limit * tf_ms`` (jump 300 bars back per iteration)
        which caused two distinct failures:

        * for small task windows (e.g. 11-bar prefix gap) the initial
          ``since`` overshot entirely BEFORE the task range, and every
          returned candle was filtered out, so the gap task wrote 0 rows;
        * for larger windows the pagination jumped 300 bars back but only
          received 100 bars per page, leaving 200-bar coverage holes per
          iteration which also manifested as incomplete fetches.

        This method is the targeted workaround: explicit range contract,
        forward pagination, conservative page size. It intentionally does
        NOT touch :meth:`get_candles` so the incremental swap-sync fast
        path keeps its existing behavior.

        TODO(repair-refactor):
            * unify fast-path and repair-path fetch semantics behind a
              single range-based port contract once the repair path is
              stable and covered by tests;
            * document/enforce the 100-bar history cap constant in one
              place instead of relying on ccxt's silent clamp;
            * reconsider forward vs backward pagination once fast-path
              load/latency characteristics are measured.
        """
        if start_ts_ms >= end_ts_ms:
            return []

        symbol = _to_ccxt_symbol(inst_id)
        tf_ms = TF_TO_MS.get(bar, 60_000)
        ccxt_tf = _TF_TO_CCXT.get(bar, bar)

        # 100 is the safe upper bound that works for both
        # /api/v5/market/candles (cap 300) and /api/v5/market/history-candles
        # (cap 100, enforced silently by ccxt).
        page_limit = 100

        collected: dict[int, dict[str, Any]] = {}
        since = start_ts_ms

        while since < end_ts_ms:
            async with self._global_limiter:
                async with self._candles_limiter:
                    async with self._instrument_limiter(inst_id):
                        rows = await self._exchange.fetch_ohlcv(
                            symbol=symbol,
                            timeframe=ccxt_tf,
                            since=since,
                            limit=page_limit,
                            params={"instId": inst_id},
                        )
            if not rows:
                break

            newest_ts = since
            for r in rows:
                ts = int(r[0])
                if ts > newest_ts:
                    newest_ts = ts
                if start_ts_ms <= ts < end_ts_ms and ts not in collected:
                    collected[ts] = {
                        "ts": ts,
                        "open": r[1],
                        "high": r[2],
                        "low": r[3],
                        "close": r[4],
                        "volume": r[5],
                        "volCcy": None,
                        "volUsd": None,
                    }

            next_since = newest_ts + tf_ms
            if next_since <= since:
                # No forward progress — guard against infinite loops if OKX
                # returns only stale timestamps.
                break
            since = next_since

        return [collected[ts] for ts in sorted(collected)]

    async def get_history_candles(
        self,
        *,
        inst_id: str,
        bar: str = "1m",
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        return await self._history_client.fetch_range(
            inst_id=inst_id,
            bar=bar,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )

    async def get_instruments(self, inst_type: str = "SWAP") -> list[dict[str, Any]]:
        ccxt_type_map = {"SWAP": "swap", "SPOT": "spot", "FUTURES": "future"}
        target = ccxt_type_map.get(inst_type.upper(), inst_type.lower())
        results = []
        for mkt in self._exchange.markets.values():
            if mkt.get("type") != target or mkt.get("quote") != "USDT":
                continue
            info = mkt.get("info", {})
            results.append(
                {
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
                }
            )
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
