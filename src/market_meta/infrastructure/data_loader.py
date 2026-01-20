"""
Загрузчик расширенных рыночных данных с OKX.

Использует OKXMarket для загрузки временных рядов:
- Open Interest (OI)
- Funding Rates
- L2 Order Book метрики (imbalance, spread)
"""

from datetime import datetime
from typing import Any

from .logging_config import get_logger
from .market import OKXMarket
from .okx_integration import OKXMetadataLoader

logger = get_logger("market_data_loader")


class MarketDataLoader:
    """
    Загрузчик расширенных рыночных данных с OKX (v1).

    Использует существующие методы OKXMarket и OKXMetadataLoader.
    Не заменяет их, а дополняет новым функционалом для временных рядов.

    v1 поддерживает только: OI, Funding Rates, L2 (imbalance + spread).
    """

    def __init__(self):
        self.market = OKXMarket()  # Использует все существующие методы
        self.loader = (
            OKXMetadataLoader()
        )  # Использует существующий loader для rate limiting и retry

    async def load_funding_rates(
        self,
        symbols: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Загрузка ставок финансирования с временным диапазоном.

        Args:
            symbols: Список символов
            start_time: Начало периода (datetime, UTC)
            end_time: Конец периода (datetime, UTC)

        Returns:
            Список записей funding rates в формате для временных рядов
        """
        records = []
        async with self.market:
            for symbol in symbols:
                try:
                    funding_data = await self.market.get_funding_rates_range(
                        inst_id=symbol, start=start_time, end=end_time
                    )
                    # Преобразуем в формат для временных рядов
                    converted = self._convert_funding_to_records(funding_data, symbol)
                    records.extend(converted)
                    logger.debug(
                        f"Загружено {len(converted)} записей funding для {symbol}"
                    )
                except Exception as e:
                    logger.warning(f"Ошибка загрузки funding для {symbol}: {e}")
                    continue

        return records

    async def load_open_interest(
        self,
        symbols: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Загрузка Open Interest с временным диапазоном.

        Args:
            symbols: Список символов
            start_time: Начало периода (datetime, UTC)
            end_time: Конец периода (datetime, UTC)

        Returns:
            Список записей OI в формате для временных рядов
        """
        records = []
        async with self.market:
            for symbol in symbols:
                try:
                    oi_data = await self.market.get_open_interest_range(
                        inst_id=symbol, start=start_time, end=end_time
                    )
                    # Преобразуем в формат для временных рядов
                    converted = self._convert_oi_to_records(oi_data, symbol)
                    records.extend(converted)
                    logger.debug(f"Загружено {len(converted)} записей OI для {symbol}")
                except Exception as e:
                    logger.warning(f"Ошибка загрузки OI для {symbol}: {e}")
                    continue

        return records

    async def load_order_book_l2(
        self,
        symbols: list[str],
        at: datetime | None = None,
        depth: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Загрузка L2 snapshot стакана (текущий момент или указанное время).

        Args:
            symbols: Список символов
            at: Время снимка (datetime, UTC). Если None - текущий момент
            depth: Глубина стакана

        Returns:
            Список записей L2 метрик
        """
        records = []
        async with self.market:
            for symbol in symbols:
                try:
                    l2_data = await self.market.get_order_book_l2(
                        inst_id=symbol, at=at, sz=depth
                    )
                    if l2_data:
                        records.append(l2_data)
                        logger.debug(f"Загружены L2 метрики для {symbol}")
                except Exception as e:
                    logger.warning(f"Ошибка загрузки L2 для {symbol}: {e}")
                    continue

        return records

    async def load_all(
        self,
        symbols: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Загрузка всех типов данных (v1: OI, Funding, L2).

        Использует один контекстный менеджер для всех загрузок,
        чтобы избежать закрытия сессии между вызовами.

        Args:
            symbols: Список символов
            start_time: Начало периода (datetime, UTC)
            end_time: Конец периода (datetime, UTC)

        Returns:
            Словарь с данными по типам:
            - funding: список funding rates
            - oi: список open interest
            - l2: список L2 метрик
        """
        funding_records = []
        oi_records = []
        l2_records = []

        # Используем один контекстный менеджер для всех загрузок
        async with self.market:
            # Загрузка funding rates
            for symbol in symbols:
                try:
                    funding_data = await self.market.get_funding_rates_range(
                        inst_id=symbol, start=start_time, end=end_time
                    )
                    converted = self._convert_funding_to_records(funding_data, symbol)
                    funding_records.extend(converted)
                    logger.debug(
                        f"Загружено {len(converted)} записей funding для {symbol}"
                    )
                except Exception as e:
                    logger.warning(f"Ошибка загрузки funding для {symbol}: {e}")
                    continue

            # Загрузка Open Interest
            for symbol in symbols:
                try:
                    oi_data = await self.market.get_open_interest_range(
                        inst_id=symbol, start=start_time, end=end_time
                    )
                    converted = self._convert_oi_to_records(oi_data, symbol)
                    oi_records.extend(converted)
                    logger.debug(f"Загружено {len(converted)} записей OI для {symbol}")
                except Exception as e:
                    logger.warning(f"Ошибка загрузки OI для {symbol}: {e}")
                    continue

            # Загрузка L2 Order Book
            for symbol in symbols:
                try:
                    l2_data = await self.market.get_order_book_l2(
                        inst_id=symbol, at=end_time or datetime.now(), sz=20
                    )
                    if l2_data:
                        l2_records.append(l2_data)
                        logger.debug(f"Загружены L2 метрики для {symbol}")
                except Exception as e:
                    logger.warning(f"Ошибка загрузки L2 для {symbol}: {e}")
                    continue

        return {
            "funding": funding_records,
            "oi": oi_records,
            "l2": l2_records,
        }

    def _convert_funding_to_records(
        self, funding_data: list[dict[str, Any]], symbol: str
    ) -> list[dict[str, Any]]:
        """
        Преобразует данные funding rates в формат для временных рядов.

        Args:
            funding_data: Сырые данные из API
            symbol: Символ инструмента

        Returns:
            Список записей в формате для market_data_ext
        """
        records = []
        for item in funding_data:
            # Парсим timestamp (может быть в мс или строке)
            ts = item.get("ts")
            if isinstance(ts, str):
                timestamp = datetime.fromtimestamp(int(ts) / 1000)
            elif isinstance(ts, int):
                timestamp = datetime.fromtimestamp(ts / 1000)
            else:
                timestamp = datetime.now()

            record = {
                "symbol": symbol,
                "timestamp": timestamp,
                "funding_rate": (
                    float(item.get("fundingRate", 0))
                    if item.get("fundingRate")
                    else None
                ),
                "next_funding_time": (
                    datetime.fromtimestamp(int(item.get("nextFundingTime", 0)) / 1000)
                    if item.get("nextFundingTime")
                    else None
                ),
                "funding_interval_hours": 8,  # OKX финансирование каждые 8 часов
                "source": "okx",
            }
            records.append(record)

        return records

    def _convert_oi_to_records(
        self, oi_data: list[dict[str, Any]], symbol: str
    ) -> list[dict[str, Any]]:
        """
        Преобразует данные Open Interest в формат для временных рядов.

        Args:
            oi_data: Сырые данные из API
            symbol: Символ инструмента

        Returns:
            Список записей в формате для market_data_ext
        """
        records = []
        for item in oi_data:
            # Парсим timestamp
            ts = item.get("ts")
            if isinstance(ts, str):
                timestamp = datetime.fromtimestamp(int(ts) / 1000)
            elif isinstance(ts, int):
                timestamp = datetime.fromtimestamp(ts / 1000)
            else:
                timestamp = datetime.now()

            record = {
                "symbol": symbol,
                "timestamp": timestamp,
                "open_interest": float(item.get("oi", 0)) if item.get("oi") else None,
                "source": "okx",
            }
            records.append(record)

        return records
