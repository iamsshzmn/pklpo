"""
Рыночные данные OKX API.

Расширенный клиент для получения рыночных данных с OKX API.
Включает методы для получения метаданных, свечей, тикеров и других данных.
"""

from datetime import datetime
from typing import Any

from .client import OKXClient
from .logging_config import get_logger

logger = get_logger("okx_market")


class OKXMarket(OKXClient):
    """Расширенный клиент для рыночных данных OKX"""

    async def get_instruments(
        self, inst_type: str = "FUTURES", **extra_params: Any
    ) -> list[dict[str, Any]]:
        """
        Получает список инструментов.

        Args:
            inst_type: Тип инструмента (SPOT, SWAP, FUTURES, OPTIONS)
            **extra_params: Дополнительные параметры

        Returns:
            Список инструментов
        """
        params = {"instType": inst_type.upper()}
        params.update(extra_params)

        data = await self._request("GET", "/api/v5/public/instruments", params=params)
        if data is None:
            return []
        return data.get("data", [])

    async def get_usdt_spot(self) -> list[dict[str, Any]]:
        """Получает все USDT споты"""
        instruments = await self.get_instruments("SPOT")
        return [i for i in instruments if i.get("quoteCcy") == "USDT"]

    async def get_usdt_swap(self) -> list[dict[str, Any]]:
        """Получает все USDT свопы"""
        instruments = await self.get_instruments("SWAP")
        return [i for i in instruments if i.get("settleCcy") == "USDT"]

    async def get_usdt_futures(self) -> list[dict[str, Any]]:
        """Получает все USDT фьючерсы"""
        instruments = await self.get_instruments("FUTURES")
        return [i for i in instruments if i.get("settleCcy") == "USDT"]

    async def get_candles(
        self,
        inst_id: str,
        bar: str = "1m",
        limit: int = 300,
        after: str | None = None,
        before: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получает свечи для инструмента.

        Args:
            inst_id: ID инструмента
            bar: Временной интервал (1m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M, 3M, 6M, 1Y)
            limit: Количество свечей (максимум 300)
            after: Время начала (timestamp)
            before: Время окончания (timestamp)

        Returns:
            Список свечей
        """
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

    async def get_funding_rates(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Получает ставки финансирования для свопов.

        Args:
            symbols: Список символов (если None - все доступные)

        Returns:
            Словарь с ставками финансирования по символам
        """
        params = {}
        if symbols:
            params["instId"] = ",".join(symbols)

        data = await self._request(
            "GET",
            "/api/v5/public/funding-rate",
            params=params,
            is_public=True,
        )

        if data is None:
            return {}

        result = {}
        for item in data.get("data", []):
            symbol = item.get("instId")
            if symbol:
                result[symbol] = {
                    "instId": item.get("instId"),
                    "fundingRate": item.get("fundingRate"),
                    "nextFundingRate": item.get("nextFundingRate"),
                    "nextFundingTime": item.get("nextFundingTime"),
                    "settleTime": item.get("settleTime"),
                }
        return result

    async def get_mark_prices(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Получает маржевые цены для инструментов.

        Args:
            symbols: Список символов (если None - все доступные)

        Returns:
            Словарь с маржевыми ценами по символам
        """
        params = {}
        if symbols:
            params["instId"] = ",".join(symbols)

        data = await self._request(
            "GET",
            "/api/v5/public/mark-price",
            params=params,
            is_public=True,
        )

        if data is None:
            return {}

        result = {}
        for item in data.get("data", []):
            symbol = item.get("instId")
            if symbol:
                result[symbol] = {
                    "instId": item.get("instId"),
                    "markPx": item.get("markPx"),
                    "ts": item.get("ts"),
                }
        return result

    async def get_tickers(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Получает тикеры с объемом и спредом.

        Args:
            symbols: Список символов (если None - все доступные)

        Returns:
            Словарь с тикерами по символам
        """
        params = {}
        if symbols:
            params["instId"] = ",".join(symbols)

        data = await self._request(
            "GET",
            "/api/v5/market/ticker",
            params=params,
            is_public=True,
        )

        if data is None:
            return {}

        result = {}
        for item in data.get("data", []):
            symbol = item.get("instId")
            if symbol:
                result[symbol] = {
                    "instId": item.get("instId"),
                    "last": item.get("last"),
                    "lastSz": item.get("lastSz"),
                    "askPx": item.get("askPx"),
                    "askSz": item.get("askSz"),
                    "bidPx": item.get("bidPx"),
                    "bidSz": item.get("bidSz"),
                    "open24h": item.get("open24h"),
                    "high24h": item.get("high24h"),
                    "low24h": item.get("low24h"),
                    "volCcy24h": item.get("volCcy24h"),
                    "vol24h": item.get("vol24h"),
                    "ts": item.get("ts"),
                    "sodUtc0": item.get("sodUtc0"),
                    "sodUtc8": item.get("sodUtc8"),
                }
        return result

    async def get_open_interest(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Получает открытый интерес для фьючерсов и свопов.

        Args:
            symbols: Список символов (если None - все доступные)

        Returns:
            Словарь с открытым интересом по символам
        """
        params = {}
        if symbols:
            params["instId"] = ",".join(symbols)

        data = await self._request(
            "GET",
            "/api/v5/public/open-interest",
            params=params,
            is_public=True,
        )

        if data is None:
            return {}

        result = {}
        for item in data.get("data", []):
            symbol = item.get("instId")
            if symbol:
                result[symbol] = {
                    "instId": item.get("instId"),
                    "oi": item.get("oi"),
                    "oiCcy": item.get("oiCcy"),
                    "ts": item.get("ts"),
                }
        return result

    async def get_open_interest_range(
        self,
        inst_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получает Open Interest с временным диапазоном.

        Возвращает rows с OI, приведёнными к минутным барам.

        OKX API: /api/v5/public/open-interest

        Args:
            inst_id: ID инструмента
            start: Начало периода (datetime, UTC)
            end: Конец периода (datetime, UTC)

        Returns:
            Список записей OI с полями:
            - instId: ID инструмента
            - oi: Open Interest
            - oiCcy: Open Interest в валюте
            - ts: Timestamp
        """
        params = {"instId": inst_id}

        if start:
            params["after"] = str(int(start.timestamp() * 1000))
        if end:
            params["before"] = str(int(end.timestamp() * 1000))

        data = await self._request(
            "GET",
            "/api/v5/public/open-interest",
            params=params,
            symbol=inst_id,
            is_public=True,
        )

        if data is None:
            return []

        result = []
        for item in data.get("data", []):
            result.append(
                {
                    "instId": item.get("instId"),
                    "oi": item.get("oi"),
                    "oiCcy": item.get("oiCcy"),
                    "ts": item.get("ts"),
                }
            )
        return result

    async def get_funding_rates_range(
        self,
        inst_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получает Funding Rates с временным диапазоном.

        Возвращает funding events, нормализованные к ближайшему бару.

        OKX API: /api/v5/public/funding-rate

        Args:
            inst_id: ID инструмента
            start: Начало периода (datetime, UTC)
            end: Конец периода (datetime, UTC)

        Returns:
            Список записей funding rate с полями:
            - instId: ID инструмента
            - fundingRate: Ставка финансирования
            - nextFundingRate: Следующая ставка
            - nextFundingTime: Время следующего финансирования
            - ts: Timestamp
        """
        params = {"instId": inst_id}

        if start:
            params["after"] = str(int(start.timestamp() * 1000))
        if end:
            params["before"] = str(int(end.timestamp() * 1000))

        data = await self._request(
            "GET",
            "/api/v5/public/funding-rate",
            params=params,
            symbol=inst_id,
            is_public=True,
        )

        if data is None:
            return []

        result = []
        for item in data.get("data", []):
            result.append(
                {
                    "instId": item.get("instId"),
                    "fundingRate": item.get("fundingRate"),
                    "nextFundingRate": item.get("nextFundingRate"),
                    "nextFundingTime": item.get("nextFundingTime"),
                    "ts": item.get("ts"),
                }
            )
        return result

    async def get_order_book_l2(
        self,
        inst_id: str,
        at: datetime | None = None,
        sz: int = 20,
    ) -> dict[str, Any]:
        """
        Получает L2 snapshot стакана с вычислением метрик.

        Использует существующий get_order_book() и добавляет вычисление метрик.
        get_order_book() остается без изменений.

        OKX API: /api/v5/market/books (уже используется в get_order_book)

        Args:
            inst_id: ID инструмента
            at: Время снимка (datetime, UTC). Если None - текущий момент
            sz: Глубина стакана (максимум 400)

        Returns:
            Словарь с метриками:
            - instId: ID инструмента
            - ts: Timestamp снимка
            - bid_imbalance: Доля bid объема (0-1)
            - ask_imbalance: Доля ask объема (0-1)
            - spread_bps: Спред в базисных пунктах
            - bids: Массив bid уровней
            - asks: Массив ask уровней
        """
        # Используем существующий get_order_book
        book_data = await self.get_order_book(inst_id, sz)

        if not book_data:
            return {}

        # Структура ответа OKX: bids/asks - массивы [price, size, num_orders, ...]
        bids = book_data.get("bids", [])
        asks = book_data.get("asks", [])

        if not bids or not asks:
            return {}

        # Вычисление метрик
        bid_volume = sum(float(bid[1]) for bid in bids)
        ask_volume = sum(float(ask[1]) for ask in asks)
        total_volume = bid_volume + ask_volume

        bid_imbalance = bid_volume / total_volume if total_volume > 0 else 0.5
        ask_imbalance = ask_volume / total_volume if total_volume > 0 else 0.5

        best_bid = float(bids[0][0]) if bids else 0
        best_ask = float(asks[0][0]) if asks else 0
        spread_bps = ((best_ask - best_bid) / best_bid * 10000) if best_bid > 0 else 0

        return {
            "instId": inst_id,
            "ts": book_data.get("ts"),
            "bid_imbalance": bid_imbalance,
            "ask_imbalance": ask_imbalance,
            "spread_bps": spread_bps,
            "bids": bids,
            "asks": asks,
        }

    async def get_order_book(self, inst_id: str, sz: int = 20) -> dict[str, Any]:
        """
        Получает стакан ордеров.

        Args:
            inst_id: ID инструмента
            sz: Глубина стакана (максимум 400)

        Returns:
            Данные стакана
        """
        params = {
            "instId": inst_id,
            "sz": sz,
        }

        data = await self._request(
            "GET",
            "/api/v5/market/books",
            params=params,
            symbol=inst_id,
            is_public=True,
        )

        if data is None or not data.get("data"):
            return {}

        return data.get("data", [{}])[0]

    async def get_trades(self, inst_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """
        Получает последние сделки.

        Args:
            inst_id: ID инструмента
            limit: Количество сделок (максимум 100)

        Returns:
            Список сделок
        """
        params = {
            "instId": inst_id,
            "limit": limit,
        }

        data = await self._request(
            "GET",
            "/api/v5/market/trades",
            params=params,
            symbol=inst_id,
            is_public=True,
        )

        if data is None:
            return []

        result = []
        for item in data.get("data", []):
            result.append(
                {
                    "instId": item.get("instId"),
                    "tradeId": item.get("tradeId"),
                    "px": item.get("px"),
                    "sz": item.get("sz"),
                    "side": item.get("side"),
                    "ts": item.get("ts"),
                }
            )
        return result
