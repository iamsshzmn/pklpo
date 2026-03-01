"""
Тесты для расширенных функций market_meta.

Проверяет новые возможности:
- Расширенные метаданные
- Ставки финансирования
- Маржевые цены
- Информация о ликвидности
- Открытый интерес
"""

import asyncio
import sys
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Добавляем корневую директорию в путь для импортов (conftest.py уже делает это, но оставляем для совместимости)
if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.market_meta import (
    FundingRate,
    InstrumentMetadata,
    InstrumentType,
    LiquidityParams,
    MarginMode,
    MarketMetaAPI,
    get_funding_rate,
    get_liquidity_info,
    get_mark_price,
    get_open_interest,
    refresh_okx_meta_extended,
)


class TestExtendedFeatures(unittest.TestCase):
    """Тесты для расширенных функций"""

    def setUp(self):
        """Настройка тестов"""
        self.api = MarketMetaAPI()

        # Создаем тестовые метаданные
        self.test_instrument = InstrumentMetadata(
            symbol="BTC-USDT-SWAP",
            inst_id="BTC-USDT-SWAP",
            inst_type=InstrumentType.SWAP,
            base_ccy="BTC",
            quote_ccy="USDT",
            settle_ccy="USDT",
            fee_maker=Decimal("0.0001"),
            fee_taker=Decimal("0.0005"),
            max_leverage=100,
            margin_mode=MarginMode.ISOLATED,
            position_mode="LONG_SHORT",
            maint_margin_rate=Decimal("0.005"),
            risk_limit_tier=1,
            funding_rate=FundingRate(
                rate=Decimal("0.0001"),
                next_funding_time=datetime.now(),
                funding_interval_hours=8,
            ),
            liquidity=LiquidityParams(
                min_volume_24h=Decimal("10000"),
                min_trades_24h=100,
                spread_threshold=Decimal("0.01"),
            ),
            state="live",
            created_time=datetime.now(),
            updated_time=datetime.now(),
        )

    def test_get_funding_rate(self):
        """Тест получения ставки финансирования"""
        # Мокаем глобальный API
        from src.market_meta.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            self.test_instrument
        )

        # Получаем ставку финансирования
        funding_rate = get_funding_rate("BTC-USDT-SWAP")

        # Проверяем результат
        assert funding_rate is not None
        assert funding_rate.rate == Decimal("0.0001")
        assert funding_rate.funding_interval_hours == 8

    def test_get_funding_rate_no_instrument(self):
        """Тест получения ставки финансирования для несуществующего инструмента"""
        # Мокаем глобальный API
        from src.market_meta.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = None

        # Получаем ставку финансирования
        funding_rate = get_funding_rate("NONEXISTENT-SWAP")

        # Проверяем результат
        assert funding_rate is None

    def test_get_funding_rate_no_metadata(self):
        """Тест получения ставки финансирования без загруженных метаданных"""
        # Мокаем глобальный API
        from src.market_meta.application.api import market_meta_api

        market_meta_api.market_metadata = None

        # Проверяем, что возвращается None (исключение ловится внутри)
        funding_rate = get_funding_rate("BTC-USDT-SWAP")
        assert funding_rate is None

    def test_get_liquidity_info(self):
        """Тест получения информации о ликвидности"""
        # Мокаем глобальный API
        from src.market_meta.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            self.test_instrument
        )

        # Получаем информацию о ликвидности
        liquidity_info = get_liquidity_info("BTC-USDT-SWAP")

        # Проверяем результат
        assert liquidity_info is not None
        assert liquidity_info["min_volume_24h"] == Decimal("10000")
        assert liquidity_info["min_trades_24h"] == 100
        assert liquidity_info["spread_threshold"] == Decimal("0.01")

    def test_get_liquidity_info_no_liquidity(self):
        """Тест получения информации о ликвидности для инструмента без параметров ликвидности"""
        # Создаем инструмент без параметров ликвидности
        instrument_no_liquidity = InstrumentMetadata(
            symbol="BTC-USDT-SWAP",
            inst_id="BTC-USDT-SWAP",
            inst_type=InstrumentType.SWAP,
            base_ccy="BTC",
            quote_ccy="USDT",
            liquidity=None,  # Нет параметров ликвидности
            state="live",
        )

        # Мокаем глобальный API
        from src.market_meta.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            instrument_no_liquidity
        )

        # Получаем информацию о ликвидности
        liquidity_info = get_liquidity_info("BTC-USDT-SWAP")

        # Проверяем результат
        assert liquidity_info is None

    def test_get_mark_price_not_implemented(self):
        """Тест получения маржевой цены (пока не реализовано)"""
        # Мокаем глобальный API
        from src.market_meta.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            self.test_instrument
        )

        # Получаем маржевую цену
        mark_price = get_mark_price("BTC-USDT-SWAP")

        # Проверяем результат (пока возвращает None)
        assert mark_price is None

    def test_get_open_interest_not_implemented(self):
        """Тест получения открытого интереса (пока не реализовано)"""
        # Мокаем глобальный API
        from src.market_meta.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            self.test_instrument
        )

        # Получаем открытый интерес
        open_interest = get_open_interest("BTC-USDT-SWAP")

        # Проверяем результат (пока возвращает None)
        assert open_interest is None

    @patch("src.market_meta.application.api.OKXMetadataLoader")
    @patch("src.market_meta.application.api.MarketMetadata")
    def test_refresh_okx_meta_extended(self, mock_market_metadata, mock_loader_class):
        """Тест обновления расширенных метаданных"""
        # Мокаем загрузчик
        mock_loader = AsyncMock()
        mock_loader_class.return_value = mock_loader

        # Мокаем данные
        mock_loader.load_instruments.return_value = [
            {
                "instId": "BTC-USDT-SWAP",
                "instType": "SWAP",
                "baseCcy": "BTC",
                "quoteCcy": "USDT",
                "settleCcy": "USDT",
                "tickSz": "0.1",
                "lotSz": "1",
                "state": "live",
            }
        ]

        mock_loader.load_funding_rates_extended.return_value = {
            "BTC-USDT-SWAP": {
                "instId": "BTC-USDT-SWAP",
                "fundingRate": "0.0001",
                "nextFundingTime": "1640995200000",
            }
        }

        mock_loader.load_mark_prices_extended.return_value = {
            "BTC-USDT-SWAP": {
                "instId": "BTC-USDT-SWAP",
                "markPx": "50000.0",
                "ts": "1640995200000",
            }
        }

        mock_loader.load_tickers_extended.return_value = {
            "BTC-USDT-SWAP": {
                "instId": "BTC-USDT-SWAP",
                "volCcy24h": "1000000.0",
                "ts": "1640995200000",
            }
        }

        mock_loader.load_open_interest_extended.return_value = {
            "BTC-USDT-SWAP": {
                "instId": "BTC-USDT-SWAP",
                "oi": "1000.0",
                "oiCcy": "50000000.0",
                "ts": "1640995200000",
            }
        }

        # Мокаем конвертацию (это не асинхронный метод)
        mock_loader.convert_to_metadata = Mock(return_value=self.test_instrument)

        # Мокаем MarketMetadata
        mock_market_metadata.return_value = Mock()

        # Вызываем функцию
        result = asyncio.run(refresh_okx_meta_extended(force=True))

        # Проверяем результат
        assert result

        # Проверяем, что все методы были вызваны
        mock_loader.load_instruments.assert_called_once()
        mock_loader.load_funding_rates_extended.assert_called_once()
        mock_loader.load_mark_prices_extended.assert_called_once()
        mock_loader.load_tickers_extended.assert_called_once()
        mock_loader.load_open_interest_extended.assert_called_once()

    def test_funding_rate_annual_rate(self):
        """Тест расчета годовой ставки финансирования"""
        # Создаем ставку финансирования
        funding_rate = FundingRate(
            rate=Decimal("0.0001"),  # 0.01%
            next_funding_time=datetime.now(),
            funding_interval_hours=8,
        )

        # Рассчитываем годовую ставку
        annual_rate = funding_rate.annual_rate

        # Проверяем результат
        # 0.0001 * 365 * 24 / 8 = 0.1095 = 10.95%
        expected_rate = Decimal("0.0001") * 365 * 24 / 8
        assert annual_rate == expected_rate

    def test_liquidity_params_is_liquid(self):
        """Тест проверки ликвидности"""
        # Создаем параметры ликвидности
        liquidity_params = LiquidityParams(
            min_volume_24h=Decimal("10000"),
            min_trades_24h=100,
            spread_threshold=Decimal("0.01"),  # 1%
        )

        # Проверяем ликвидный инструмент
        is_liquid = liquidity_params.is_liquid(
            volume_24h=Decimal("50000"),  # Достаточный объем
            trades_24h=200,  # Достаточно сделок
            spread=Decimal("0.005"),  # Низкий спред
        )

        assert is_liquid

        # Проверяем неликвидный инструмент
        is_not_liquid = liquidity_params.is_liquid(
            volume_24h=Decimal("5000"),  # Недостаточный объем
            trades_24h=50,  # Недостаточно сделок
            spread=Decimal("0.02"),  # Высокий спред
        )

        assert not is_not_liquid


def run_tests():
    """Запуск тестов"""
    print("🧪 Запуск тестов расширенных функций market_meta...")

    # Создаем тестовый набор
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestExtendedFeatures)

    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Выводим результаты
    print("\n📊 Результаты тестов:")
    print(f"  Всего тестов: {result.testsRun}")
    print(f"  Успешно: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Ошибок: {len(result.errors)}")
    print(f"  Провалов: {len(result.failures)}")

    if result.failures:
        print("\n❌ Проваленные тесты:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")

    if result.errors:
        print("\n🚨 Ошибки в тестах:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")

    if result.wasSuccessful():
        print("\n✅ Все тесты прошли успешно!")
    else:
        print("\n❌ Некоторые тесты не прошли")

    return result.wasSuccessful()


if __name__ == "__main__":
    run_tests()
