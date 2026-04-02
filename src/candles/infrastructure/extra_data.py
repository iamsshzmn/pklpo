from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from src.logging import get_logger

if TYPE_CHECKING:
    from src.candles.ports import MarketDataPort

logger = get_logger("candles.extra_data")


class ExtraDataFetcher:
    """Fetch optional funding/open-interest data with local cache and stats."""

    def __init__(self, market_data: MarketDataPort) -> None:
        self._market_data = market_data
        self._funding_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._oi_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._stats: dict[str, dict[str, float]] = {
            "funding": {"ok": 0, "retries": 0, "rate_limit": 0, "errors": 0},
            "open_interest": {"ok": 0, "retries": 0, "rate_limit": 0, "errors": 0},
        }

    @staticmethod
    def _is_rate_limited(msg: str) -> bool:
        return any(x in msg for x in ["429", "Too Many Requests", "50011"])

    def snapshot_stats(self) -> dict[str, dict[str, float]]:
        return deepcopy(self._stats)

    async def fetch_funding_rate(self, symbol: str) -> dict[str, Any] | None:
        try:
            fr_map = await self._market_data.fetch_funding_rates([symbol])
            fr = fr_map.get(symbol)
            if not fr:
                return None
            f_time = str(fr.get("fundingTime") or fr.get("ts") or "")
            cache_key = (symbol, f_time)
            if cache_key not in self._funding_cache:
                self._funding_cache[cache_key] = fr
            self._stats["funding"]["ok"] += 1
            return self._funding_cache[cache_key]
        except Exception as exc:
            msg = str(exc)
            if self._is_rate_limited(msg):
                self._stats["funding"]["rate_limit"] += 1
                self._stats["funding"]["retries"] += 1
            else:
                self._stats["funding"]["errors"] += 1
            logger.warning("Failed to fetch funding rate for %s: %s", symbol, exc)
            return None

    async def fetch_open_interest(self, symbol: str) -> dict[str, Any] | None:
        try:
            oi_map = await self._market_data.fetch_open_interest([symbol])
            oi = oi_map.get(symbol)
            if not oi:
                return None
            o_time = str(oi.get("ts") or oi.get("time") or "")
            cache_key = (symbol, o_time)
            if cache_key not in self._oi_cache:
                self._oi_cache[cache_key] = oi
            self._stats["open_interest"]["ok"] += 1
            return self._oi_cache[cache_key]
        except Exception as exc:
            msg = str(exc)
            if self._is_rate_limited(msg):
                self._stats["open_interest"]["rate_limit"] += 1
                self._stats["open_interest"]["retries"] += 1
            else:
                self._stats["open_interest"]["errors"] += 1
            logger.warning("Failed to fetch open interest for %s: %s", symbol, exc)
            return None

    async def fetch_for_symbol(self, symbol: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        funding = await self.fetch_funding_rate(symbol)
        if funding:
            out["funding_rate"] = funding
        open_interest = await self.fetch_open_interest(symbol)
        if open_interest:
            out["open_interest"] = open_interest
        return out
