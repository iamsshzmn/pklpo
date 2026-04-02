from __future__ import annotations

from typing import Any

from aiolimiter import AsyncLimiter

from src.candles.domain.timeframes import TF_TO_MS

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

    def __init__(self, max_requests_per_second: int = 80) -> None:
        if ccxt is None:
            raise RuntimeError(
                "ccxt is not installed. Install `ccxt` or disable use_ccxt."
            )
        self._exchange = ccxt.okx(
            {
                "enableRateLimit": True,
            }
        )
        # Adapter-local traffic shaping. Orchestrator should not depend on limiter internals.
        self._global_limiter = AsyncLimiter(max_requests_per_second, 1)
        self._candles_limiter = AsyncLimiter(16, 1)
        self._extra_data_limiter = AsyncLimiter(3, 1)
        self._instrument_limiters: dict[str, AsyncLimiter] = {}
        self._funding_instrument_limiters: dict[str, AsyncLimiter] = {}

    def _instrument_limiter(self, symbol: str) -> AsyncLimiter:
        if symbol not in self._instrument_limiters:
            self._instrument_limiters[symbol] = AsyncLimiter(27, 1)
        return self._instrument_limiters[symbol]

    def _funding_instrument_limiter(self, symbol: str) -> AsyncLimiter:
        if symbol not in self._funding_instrument_limiters:
            self._funding_instrument_limiters[symbol] = AsyncLimiter(2, 1)
        return self._funding_instrument_limiters[symbol]

    async def __aenter__(self) -> CcxtOKXAdapter:
        await self._exchange.load_markets()
        return self

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
