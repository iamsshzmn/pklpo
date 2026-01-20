from typing import Any

from .client import OKXClient


class OKXMarket(OKXClient):
    async def get_instruments(
        self, inst_type: str = "FUTURES", **extra_params: Any
    ) -> list[dict[str, Any]]:
        params = {"instType": inst_type.upper()}
        params.update(extra_params)
        data = await self._request("GET", "/api/v5/public/instruments", params=params)
        if data is None:
            return []
        return data.get("data", [])

    async def get_usdt_spot(self) -> list[dict[str, Any]]:
        instruments = await self.get_instruments("SPOT")
        return [i for i in instruments if i.get("quoteCcy") == "USDT"]

    async def get_usdt_swap(self) -> list[dict[str, Any]]:
        """Получает все USDT свопы"""
        instruments = await self.get_instruments("SWAP")
        return [i for i in instruments if i.get("settleCcy") == "USDT"]

    async def get_candles(
        self,
        inst_id: str,
        bar: str = "1m",
        limit: int = 300,
        after: str | None = None,
        before: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {
            "instId": inst_id,
            "bar": bar,
            "limit": limit,
        }
        if before is not None:
            params["before"] = before
        elif after is not None:
            params["after"] = after
        data = await self._request(
            "GET",
            "/api/v5/market/candles",
            params=params,
            symbol=inst_id,
            is_public=True,
        )
        if data is None:
            return []
        result = []
        for row in data.get("data", []):
            result.append(
                {
                    "ts": int(row[0]),
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                    "volCcy": row[6] if len(row) > 6 else None,
                    "volUsd": row[7] if len(row) > 7 else None,
                }
            )
        return result
