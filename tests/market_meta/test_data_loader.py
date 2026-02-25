"""
Unit тесты для MarketDataLoader.

Проверяет загрузку расширенных рыночных данных с OKX.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.market_meta.infrastructure.data_loader import MarketDataLoader


class TestMarketDataLoader:
    """Тесты для MarketDataLoader"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.loader = MarketDataLoader()

    @pytest.mark.asyncio
    async def test_load_funding_rates(self):
        """Тест загрузки funding rates"""
        # Мокаем OKXMarket
        mock_market = AsyncMock()
        mock_market.__aenter__ = AsyncMock(return_value=mock_market)
        mock_market.__aexit__ = AsyncMock(return_value=None)
        mock_market.get_funding_rates_range.return_value = [
            {
                "instId": "BTC-USDT-SWAP",
                "fundingRate": "0.0001",
                "nextFundingTime": "1700000000000",
                "ts": "1700000000000",
            }
        ]

        self.loader.market = mock_market

        result = await self.loader.load_funding_rates(
            symbols=["BTC-USDT-SWAP"],
            start_time=datetime(2023, 11, 14, 22, 0, 0),
            end_time=datetime(2023, 11, 14, 23, 0, 0),
        )

        assert len(result) == 1
        assert result[0]["symbol"] == "BTC-USDT-SWAP"
        assert result[0]["funding_rate"] == 0.0001
        assert result[0]["source"] == "okx"
        assert "timestamp" in result[0]

    @pytest.mark.asyncio
    async def test_load_open_interest(self):
        """Тест загрузки Open Interest"""
        mock_market = AsyncMock()
        mock_market.__aenter__ = AsyncMock(return_value=mock_market)
        mock_market.__aexit__ = AsyncMock(return_value=None)
        mock_market.get_open_interest_range.return_value = [
            {
                "instId": "BTC-USDT-SWAP",
                "oi": "1000000",
                "oiCcy": "50000000",
                "ts": "1700000000000",
            }
        ]

        self.loader.market = mock_market

        result = await self.loader.load_open_interest(
            symbols=["BTC-USDT-SWAP"],
            start_time=datetime(2023, 11, 14, 22, 0, 0),
            end_time=datetime(2023, 11, 14, 23, 0, 0),
        )

        assert len(result) == 1
        assert result[0]["symbol"] == "BTC-USDT-SWAP"
        assert result[0]["open_interest"] == 1000000.0
        assert result[0]["source"] == "okx"

    @pytest.mark.asyncio
    async def test_load_order_book_l2(self):
        """Тест загрузки L2 Order Book"""
        mock_market = AsyncMock()
        mock_market.__aenter__ = AsyncMock(return_value=mock_market)
        mock_market.__aexit__ = AsyncMock(return_value=None)
        mock_market.get_order_book_l2.return_value = {
            "instId": "BTC-USDT-SWAP",
            "ts": "1700000000000",
            "bid_imbalance": 0.6,
            "ask_imbalance": 0.4,
            "spread_bps": 10.5,
            "bids": [[50000, 1.0]],
            "asks": [[50010, 1.0]],
        }

        self.loader.market = mock_market

        result = await self.loader.load_order_book_l2(
            symbols=["BTC-USDT-SWAP"], at=datetime(2023, 11, 14, 22, 0, 0), depth=20
        )

        assert len(result) == 1
        assert result[0]["instId"] == "BTC-USDT-SWAP"
        assert result[0]["bid_imbalance"] == 0.6
        assert result[0]["ask_imbalance"] == 0.4
        assert result[0]["spread_bps"] == 10.5

    @pytest.mark.asyncio
    async def test_load_all(self):
        """Тест загрузки всех типов данных"""
        mock_market = AsyncMock()
        mock_market.__aenter__ = AsyncMock(return_value=mock_market)
        mock_market.__aexit__ = AsyncMock(return_value=None)
        mock_market.get_funding_rates_range.return_value = []
        mock_market.get_open_interest_range.return_value = []
        mock_market.get_order_book_l2.return_value = {}

        self.loader.market = mock_market

        result = await self.loader.load_all(
            symbols=["BTC-USDT-SWAP"],
            start_time=datetime(2023, 11, 14, 22, 0, 0),
            end_time=datetime(2023, 11, 14, 23, 0, 0),
        )

        assert "funding" in result
        assert "oi" in result
        assert "l2" in result

    @pytest.mark.asyncio
    async def test_load_funding_rates_error_handling(self):
        """Тест обработки ошибок при загрузке funding rates"""
        mock_market = AsyncMock()
        mock_market.__aenter__ = AsyncMock(return_value=mock_market)
        mock_market.__aexit__ = AsyncMock(return_value=None)
        mock_market.get_funding_rates_range.side_effect = Exception("API Error")

        self.loader.market = mock_market

        # Должен вернуть пустой список, а не упасть
        result = await self.loader.load_funding_rates(symbols=["BTC-USDT-SWAP"])

        assert result == []

    def test_convert_funding_to_records(self):
        """Тест преобразования funding rates в записи"""
        funding_data = [
            {
                "instId": "BTC-USDT-SWAP",
                "fundingRate": "0.0001",
                "nextFundingTime": "1700000000000",
                "ts": "1700000000000",
            }
        ]

        result = self.loader._convert_funding_to_records(funding_data, "BTC-USDT-SWAP")

        assert len(result) == 1
        assert result[0]["symbol"] == "BTC-USDT-SWAP"
        assert result[0]["funding_rate"] == 0.0001
        assert result[0]["funding_interval_hours"] == 8

    def test_convert_oi_to_records(self):
        """Тест преобразования OI в записи"""
        oi_data = [
            {
                "instId": "BTC-USDT-SWAP",
                "oi": "1000000",
                "oiCcy": "50000000",
                "ts": "1700000000000",
            }
        ]

        result = self.loader._convert_oi_to_records(oi_data, "BTC-USDT-SWAP")

        assert len(result) == 1
        assert result[0]["symbol"] == "BTC-USDT-SWAP"
        assert result[0]["open_interest"] == 1000000.0
