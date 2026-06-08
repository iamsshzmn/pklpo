"""
РўРµСЃС‚С‹ РґР»СЏ СЂР°СЃС€РёСЂРµРЅРЅС‹С… С„СѓРЅРєС†РёР№ market_meta.

РџСЂРѕРІРµСЂСЏРµС‚ РЅРѕРІС‹Рµ РІРѕР·РјРѕР¶РЅРѕСЃС‚Рё:
- Р Р°СЃС€РёСЂРµРЅРЅС‹Рµ РјРµС‚Р°РґР°РЅРЅС‹Рµ
- РЎС‚Р°РІРєРё С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёСЏ
- РњР°СЂР¶РµРІС‹Рµ С†РµРЅС‹
- РРЅС„РѕСЂРјР°С†РёСЏ Рѕ Р»РёРєРІРёРґРЅРѕСЃС‚Рё
- РћС‚РєСЂС‹С‚С‹Р№ РёРЅС‚РµСЂРµСЃ
"""

import asyncio
import sys
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Р”РѕР±Р°РІР»СЏРµРј РєРѕСЂРЅРµРІСѓСЋ РґРёСЂРµРєС‚РѕСЂРёСЋ РІ РїСѓС‚СЊ РґР»СЏ РёРјРїРѕСЂС‚РѕРІ (conftest.py СѓР¶Рµ РґРµР»Р°РµС‚ СЌС‚Рѕ, РЅРѕ РѕСЃС‚Р°РІР»СЏРµРј РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё)
if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.market_meta_backup import (
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
    """РўРµСЃС‚С‹ РґР»СЏ СЂР°СЃС€РёСЂРµРЅРЅС‹С… С„СѓРЅРєС†РёР№"""

    def setUp(self):
        """РќР°СЃС‚СЂРѕР№РєР° С‚РµСЃС‚РѕРІ"""
        self.api = MarketMetaAPI()

        # РЎРѕР·РґР°РµРј С‚РµСЃС‚РѕРІС‹Рµ РјРµС‚Р°РґР°РЅРЅС‹Рµ
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
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚Р°РІРєРё С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёСЏ"""
        # РњРѕРєР°РµРј РіР»РѕР±Р°Р»СЊРЅС‹Р№ API
        from src.market_meta_backup.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            self.test_instrument
        )

        # РџРѕР»СѓС‡Р°РµРј СЃС‚Р°РІРєСѓ С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёСЏ
        funding_rate = get_funding_rate("BTC-USDT-SWAP")

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert funding_rate is not None
        assert funding_rate.rate == Decimal("0.0001")
        assert funding_rate.funding_interval_hours == 8

    def test_get_funding_rate_no_instrument(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚Р°РІРєРё С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёСЏ РґР»СЏ РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°"""
        # РњРѕРєР°РµРј РіР»РѕР±Р°Р»СЊРЅС‹Р№ API
        from src.market_meta_backup.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = None

        # РџРѕР»СѓС‡Р°РµРј СЃС‚Р°РІРєСѓ С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёСЏ
        funding_rate = get_funding_rate("NONEXISTENT-SWAP")

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert funding_rate is None

    def test_get_funding_rate_no_metadata(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚Р°РІРєРё С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёСЏ Р±РµР· Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… РјРµС‚Р°РґР°РЅРЅС‹С…"""
        # РњРѕРєР°РµРј РіР»РѕР±Р°Р»СЊРЅС‹Р№ API
        from src.market_meta_backup.application.api import market_meta_api

        market_meta_api.market_metadata = None

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РІРѕР·РІСЂР°С‰Р°РµС‚СЃСЏ None (РёСЃРєР»СЋС‡РµРЅРёРµ Р»РѕРІРёС‚СЃСЏ РІРЅСѓС‚СЂРё)
        funding_rate = get_funding_rate("BTC-USDT-SWAP")
        assert funding_rate is None

    def test_get_liquidity_info(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РёРЅС„РѕСЂРјР°С†РёРё Рѕ Р»РёРєРІРёРґРЅРѕСЃС‚Рё"""
        # РњРѕРєР°РµРј РіР»РѕР±Р°Р»СЊРЅС‹Р№ API
        from src.market_meta_backup.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            self.test_instrument
        )

        # РџРѕР»СѓС‡Р°РµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ Р»РёРєРІРёРґРЅРѕСЃС‚Рё
        liquidity_info = get_liquidity_info("BTC-USDT-SWAP")

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert liquidity_info is not None
        assert liquidity_info["min_volume_24h"] == Decimal("10000")
        assert liquidity_info["min_trades_24h"] == 100
        assert liquidity_info["spread_threshold"] == Decimal("0.01")

    def test_get_liquidity_info_no_liquidity(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РёРЅС„РѕСЂРјР°С†РёРё Рѕ Р»РёРєРІРёРґРЅРѕСЃС‚Рё РґР»СЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° Р±РµР· РїР°СЂР°РјРµС‚СЂРѕРІ Р»РёРєРІРёРґРЅРѕСЃС‚Рё"""
        # РЎРѕР·РґР°РµРј РёРЅСЃС‚СЂСѓРјРµРЅС‚ Р±РµР· РїР°СЂР°РјРµС‚СЂРѕРІ Р»РёРєРІРёРґРЅРѕСЃС‚Рё
        instrument_no_liquidity = InstrumentMetadata(
            symbol="BTC-USDT-SWAP",
            inst_id="BTC-USDT-SWAP",
            inst_type=InstrumentType.SWAP,
            base_ccy="BTC",
            quote_ccy="USDT",
            liquidity=None,  # РќРµС‚ РїР°СЂР°РјРµС‚СЂРѕРІ Р»РёРєРІРёРґРЅРѕСЃС‚Рё
            state="live",
        )

        # РњРѕРєР°РµРј РіР»РѕР±Р°Р»СЊРЅС‹Р№ API
        from src.market_meta_backup.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            instrument_no_liquidity
        )

        # РџРѕР»СѓС‡Р°РµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ Р»РёРєРІРёРґРЅРѕСЃС‚Рё
        liquidity_info = get_liquidity_info("BTC-USDT-SWAP")

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert liquidity_info is None

    def test_get_mark_price_not_implemented(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РјР°СЂР¶РµРІРѕР№ С†РµРЅС‹ (РїРѕРєР° РЅРµ СЂРµР°Р»РёР·РѕРІР°РЅРѕ)"""
        # РњРѕРєР°РµРј РіР»РѕР±Р°Р»СЊРЅС‹Р№ API
        from src.market_meta_backup.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            self.test_instrument
        )

        # РџРѕР»СѓС‡Р°РµРј РјР°СЂР¶РµРІСѓСЋ С†РµРЅСѓ
        mark_price = get_mark_price("BTC-USDT-SWAP")

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚ (РїРѕРєР° РІРѕР·РІСЂР°С‰Р°РµС‚ None)
        assert mark_price is None

    def test_get_open_interest_not_implemented(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РѕС‚РєСЂС‹С‚РѕРіРѕ РёРЅС‚РµСЂРµСЃР° (РїРѕРєР° РЅРµ СЂРµР°Р»РёР·РѕРІР°РЅРѕ)"""
        # РњРѕРєР°РµРј РіР»РѕР±Р°Р»СЊРЅС‹Р№ API
        from src.market_meta_backup.application.api import market_meta_api

        market_meta_api.market_metadata = Mock()
        market_meta_api.market_metadata.get_instrument.return_value = (
            self.test_instrument
        )

        # РџРѕР»СѓС‡Р°РµРј РѕС‚РєСЂС‹С‚С‹Р№ РёРЅС‚РµСЂРµСЃ
        open_interest = get_open_interest("BTC-USDT-SWAP")

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚ (РїРѕРєР° РІРѕР·РІСЂР°С‰Р°РµС‚ None)
        assert open_interest is None

    @patch("src.candles.application.api.OKXMetadataLoader")
    @patch("src.candles.application.api.MarketMetadata")
    def test_refresh_okx_meta_extended(self, mock_market_metadata, mock_loader_class):
        """РўРµСЃС‚ РѕР±РЅРѕРІР»РµРЅРёСЏ СЂР°СЃС€РёСЂРµРЅРЅС‹С… РјРµС‚Р°РґР°РЅРЅС‹С…"""
        # РњРѕРєР°РµРј Р·Р°РіСЂСѓР·С‡РёРє
        mock_loader = AsyncMock()
        mock_loader_class.return_value = mock_loader

        # РњРѕРєР°РµРј РґР°РЅРЅС‹Рµ
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

        # РњРѕРєР°РµРј РєРѕРЅРІРµСЂС‚Р°С†РёСЋ (СЌС‚Рѕ РЅРµ Р°СЃРёРЅС…СЂРѕРЅРЅС‹Р№ РјРµС‚РѕРґ)
        mock_loader.convert_to_metadata = Mock(return_value=self.test_instrument)

        # РњРѕРєР°РµРј MarketMetadata
        mock_market_metadata.return_value = Mock()

        # Р’С‹Р·С‹РІР°РµРј С„СѓРЅРєС†РёСЋ
        result = asyncio.run(refresh_okx_meta_extended(force=True))

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert result

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РІСЃРµ РјРµС‚РѕРґС‹ Р±С‹Р»Рё РІС‹Р·РІР°РЅС‹
        mock_loader.load_instruments.assert_called_once()
        mock_loader.load_funding_rates_extended.assert_called_once()
        mock_loader.load_mark_prices_extended.assert_called_once()
        mock_loader.load_tickers_extended.assert_called_once()
        mock_loader.load_open_interest_extended.assert_called_once()

    def test_funding_rate_annual_rate(self):
        """РўРµСЃС‚ СЂР°СЃС‡РµС‚Р° РіРѕРґРѕРІРѕР№ СЃС‚Р°РІРєРё С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёСЏ"""
        # РЎРѕР·РґР°РµРј СЃС‚Р°РІРєСѓ С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёСЏ
        funding_rate = FundingRate(
            rate=Decimal("0.0001"),  # 0.01%
            next_funding_time=datetime.now(),
            funding_interval_hours=8,
        )

        # Р Р°СЃСЃС‡РёС‚С‹РІР°РµРј РіРѕРґРѕРІСѓСЋ СЃС‚Р°РІРєСѓ
        annual_rate = funding_rate.annual_rate

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        # 0.0001 * 365 * 24 / 8 = 0.1095 = 10.95%
        expected_rate = Decimal("0.0001") * 365 * 24 / 8
        assert annual_rate == expected_rate

    def test_liquidity_params_is_liquid(self):
        """РўРµСЃС‚ РїСЂРѕРІРµСЂРєРё Р»РёРєРІРёРґРЅРѕСЃС‚Рё"""
        # РЎРѕР·РґР°РµРј РїР°СЂР°РјРµС‚СЂС‹ Р»РёРєРІРёРґРЅРѕСЃС‚Рё
        liquidity_params = LiquidityParams(
            min_volume_24h=Decimal("10000"),
            min_trades_24h=100,
            spread_threshold=Decimal("0.01"),  # 1%
        )

        # РџСЂРѕРІРµСЂСЏРµРј Р»РёРєРІРёРґРЅС‹Р№ РёРЅСЃС‚СЂСѓРјРµРЅС‚
        is_liquid = liquidity_params.is_liquid(
            volume_24h=Decimal("50000"),  # Р”РѕСЃС‚Р°С‚РѕС‡РЅС‹Р№ РѕР±СЉРµРј
            trades_24h=200,  # Р”РѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃРґРµР»РѕРє
            spread=Decimal("0.005"),  # РќРёР·РєРёР№ СЃРїСЂРµРґ
        )

        assert is_liquid

        # РџСЂРѕРІРµСЂСЏРµРј РЅРµР»РёРєРІРёРґРЅС‹Р№ РёРЅСЃС‚СЂСѓРјРµРЅС‚
        is_not_liquid = liquidity_params.is_liquid(
            volume_24h=Decimal("5000"),  # РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅС‹Р№ РѕР±СЉРµРј
            trades_24h=50,  # РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃРґРµР»РѕРє
            spread=Decimal("0.02"),  # Р’С‹СЃРѕРєРёР№ СЃРїСЂРµРґ
        )

        assert not is_not_liquid


def run_tests():
    """Р—Р°РїСѓСЃРє С‚РµСЃС‚РѕРІ"""
    print("рџ§Є Р—Р°РїСѓСЃРє С‚РµСЃС‚РѕРІ СЂР°СЃС€РёСЂРµРЅРЅС‹С… С„СѓРЅРєС†РёР№ market_meta...")

    # РЎРѕР·РґР°РµРј С‚РµСЃС‚РѕРІС‹Р№ РЅР°Р±РѕСЂ
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestExtendedFeatures)

    # Р—Р°РїСѓСЃРєР°РµРј С‚РµСЃС‚С‹
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Р’С‹РІРѕРґРёРј СЂРµР·СѓР»СЊС‚Р°С‚С‹
    print("\nрџ“Љ Р РµР·СѓР»СЊС‚Р°С‚С‹ С‚РµСЃС‚РѕРІ:")
    print(f"  Р’СЃРµРіРѕ С‚РµСЃС‚РѕРІ: {result.testsRun}")
    print(f"  РЈСЃРїРµС€РЅРѕ: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  РћС€РёР±РѕРє: {len(result.errors)}")
    print(f"  РџСЂРѕРІР°Р»РѕРІ: {len(result.failures)}")

    if result.failures:
        print("\nвќЊ РџСЂРѕРІР°Р»РµРЅРЅС‹Рµ С‚РµСЃС‚С‹:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")

    if result.errors:
        print("\nрџљЁ РћС€РёР±РєРё РІ С‚РµСЃС‚Р°С…:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")

    if result.wasSuccessful():
        print("\nвњ… Р’СЃРµ С‚РµСЃС‚С‹ РїСЂРѕС€Р»Рё СѓСЃРїРµС€РЅРѕ!")
    else:
        print("\nвќЊ РќРµРєРѕС‚РѕСЂС‹Рµ С‚РµСЃС‚С‹ РЅРµ РїСЂРѕС€Р»Рё")

    return result.wasSuccessful()


if __name__ == "__main__":
    run_tests()
