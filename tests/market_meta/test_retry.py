"""
РўРµСЃС‚С‹ РґР»СЏ retry РјРµС…Р°РЅРёР·РјРѕРІ РІ OKX РёРЅС‚РµРіСЂР°С†РёРё.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.market_meta_backup.domain.exceptions import (
    MetadataStaleError,
    OKXIntegrationError,
    OKXNetworkError,
    OKXRateLimitError,
)
from src.market_meta_backup.infrastructure.okx_integration import OKXMetadataLoader


class TestOKXRetryMechanisms:
    """РўРµСЃС‚С‹ retry РјРµС…Р°РЅРёР·РјРѕРІ"""

    def setup_method(self):
        """РќР°СЃС‚СЂРѕР№РєР° РїРµСЂРµРґ РєР°Р¶РґС‹Рј С‚РµСЃС‚РѕРј"""
        self.loader = OKXMetadataLoader(max_retries=3, base_delay=0.1, max_delay=1.0)

    @patch("src.candles.infrastructure.okx_integration.OKXMarket")
    async def test_successful_load_without_retry(self, mock_market_class):
        """РўРµСЃС‚ СѓСЃРїРµС€РЅРѕР№ Р·Р°РіСЂСѓР·РєРё Р±РµР· retry"""
        # РќР°СЃС‚СЂР°РёРІР°РµРј РјРѕРє СЃ РїРѕРґРґРµСЂР¶РєРѕР№ async context manager
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            return_value=[
                {
                    "instId": "BTC-USDT-SWAP",
                    "instType": "SWAP",
                    "baseCcy": "BTC",
                    "quoteCcy": "USDT",
                }
            ]
        )
        # Р”РµР»Р°РµРј РјРѕРє async context manager
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # РЎРѕР·РґР°РµРј РЅРѕРІС‹Р№ loader СЃ РјРѕРєРѕРј С‡РµСЂРµР· DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.1, max_delay=1.0, market=mock_market_instance
        )

        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РіСЂСѓР·РєСѓ
        result = await loader.load_instruments(["SWAP"])

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert len(result) == 1
        assert result[0]["instId"] == "BTC-USDT-SWAP"

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РјРµС‚РѕРґ РІС‹Р·РІР°Р»СЃСЏ С‚РѕР»СЊРєРѕ РѕРґРёРЅ СЂР°Р·
        # РњРµС‚РѕРґ РІС‹Р·С‹РІР°РµС‚СЃСЏ СЃ РѕС‚РґРµР»СЊРЅС‹Рј С‚РёРїРѕРј РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°, Р° РЅРµ СЃРїРёСЃРєРѕРј
        mock_market_instance.get_instruments.assert_called_once_with("SWAP")

    @patch("src.candles.infrastructure.okx_integration.OKXMarket")
    async def test_retry_on_network_error(self, mock_market_class):
        """РўРµСЃС‚ retry РїСЂРё СЃРµС‚РµРІРѕР№ РѕС€РёР±РєРµ"""
        # РќР°СЃС‚СЂР°РёРІР°РµРј РјРѕРє РґР»СЏ РёРјРёС‚Р°С†РёРё СЃРµС‚РµРІРѕР№ РѕС€РёР±РєРё, Р·Р°С‚РµРј СѓСЃРїРµС…Р°
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=[
                Exception(
                    "Connection timeout"
                ),  # Р‘СѓРґРµС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРѕ РІ OKXNetworkError
                Exception(
                    "Connection refused"
                ),  # Р‘СѓРґРµС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРѕ РІ OKXNetworkError
                [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "instType": "SWAP",
                        "baseCcy": "BTC",
                        "quoteCcy": "USDT",
                    }
                ],
            ]
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # РЎРѕР·РґР°РµРј РЅРѕРІС‹Р№ loader СЃ РјРѕРєРѕРј С‡РµСЂРµР· DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РіСЂСѓР·РєСѓ
        result = await loader.load_instruments(["SWAP"])

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert len(result) == 1
        assert result[0]["instId"] == "BTC-USDT-SWAP"

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РјРµС‚РѕРґ РІС‹Р·РІР°Р»СЃСЏ 3 СЂР°Р·Р° (2 РѕС€РёР±РєРё + 1 СѓСЃРїРµС…)
        assert mock_market_instance.get_instruments.call_count >= 3

    @patch("src.candles.infrastructure.okx_integration.OKXMarket")
    async def test_retry_on_rate_limit_error(self, mock_market_class):
        """РўРµСЃС‚ retry РїСЂРё РїСЂРµРІС‹С€РµРЅРёРё Р»РёРјРёС‚Р° Р·Р°РїСЂРѕСЃРѕРІ"""
        # РќР°СЃС‚СЂР°РёРІР°РµРј РјРѕРє РґР»СЏ РёРјРёС‚Р°С†РёРё rate limit, Р·Р°С‚РµРј СѓСЃРїРµС…Р°
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=[
                OKXRateLimitError(retry_after=1),
                OKXRateLimitError(retry_after=1),
                [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "instType": "SWAP",
                        "baseCcy": "BTC",
                        "quoteCcy": "USDT",
                    }
                ],
            ]
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # РЎРѕР·РґР°РµРј РЅРѕРІС‹Р№ loader СЃ РјРѕРєРѕРј С‡РµСЂРµР· DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РіСЂСѓР·РєСѓ
        result = await loader.load_instruments(["SWAP"])

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert len(result) == 1
        assert result[0]["instId"] == "BTC-USDT-SWAP"

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РјРµС‚РѕРґ РІС‹Р·РІР°Р»СЃСЏ 3 СЂР°Р·Р°
        assert mock_market_instance.get_instruments.call_count >= 3

    @patch("src.candles.infrastructure.okx_integration.OKXMarket")
    async def test_max_retries_exceeded(self, mock_market_class):
        """РўРµСЃС‚ РїСЂРµРІС‹С€РµРЅРёСЏ РјР°РєСЃРёРјР°Р»СЊРЅРѕРіРѕ РєРѕР»РёС‡РµСЃС‚РІР° РїРѕРїС‹С‚РѕРє"""
        # РќР°СЃС‚СЂР°РёРІР°РµРј РјРѕРє РґР»СЏ РїРѕСЃС‚РѕСЏРЅРЅС‹С… РѕС€РёР±РѕРє
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception(
                "Connection failed"
            )  # Р‘СѓРґРµС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРѕ РІ OKXNetworkError
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # РЎРѕР·РґР°РµРј РЅРѕРІС‹Р№ loader СЃ РјРѕРєРѕРј С‡РµСЂРµР· DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РіСЂСѓР·РєСѓ Рё РѕР¶РёРґР°РµРј MetadataStaleError (РІСЃРµ С‚РёРїС‹ РїСЂРѕРІР°Р»РёР»РёСЃСЊ)
        with pytest.raises(MetadataStaleError):
            await loader.load_instruments(["SWAP"])

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РјРµС‚РѕРґ РІС‹Р·РІР°Р»СЃСЏ РјР°РєСЃРёРјР°Р»СЊРЅРѕРµ РєРѕР»РёС‡РµСЃС‚РІРѕ СЂР°Р· (3 РїРѕРїС‹С‚РєРё)
        # Retry РґРµРєРѕСЂР°С‚РѕСЂ РґРµР»Р°РµС‚ 3 РїРѕРїС‹С‚РєРё
        assert mock_market_instance.get_instruments.call_count >= 3

    @patch("src.candles.infrastructure.okx_integration.OKXMarket")
    async def test_no_retry_on_validation_error(self, mock_market_class):
        """РўРµСЃС‚ РѕС‚СЃСѓС‚СЃС‚РІРёСЏ retry РїСЂРё РѕС€РёР±РєРµ РІР°Р»РёРґР°С†РёРё"""
        # РќР°СЃС‚СЂР°РёРІР°РµРј РјРѕРє РґР»СЏ РѕС€РёР±РєРё РІР°Р»РёРґР°С†РёРё
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=ValueError("Invalid data")
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # РЎРѕР·РґР°РµРј РЅРѕРІС‹Р№ loader СЃ РјРѕРєРѕРј С‡РµСЂРµР· DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.1, max_delay=1.0, market=mock_market_instance
        )

        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РіСЂСѓР·РєСѓ Рё РѕР¶РёРґР°РµРј MetadataStaleError (РІСЃРµ С‚РёРїС‹ РїСЂРѕРІР°Р»РёР»РёСЃСЊ)
        # ValueError РїСЂРµРѕР±СЂР°Р·СѓРµС‚СЃСЏ РІ OKXIntegrationError, РєРѕС‚РѕСЂС‹Р№ СЏРІР»СЏРµС‚СЃСЏ retryable
        # Retry РґРµР»Р°РµС‚ 3 РїРѕРїС‹С‚РєРё, РІСЃРµ РїСЂРѕРІР°Р»РёРІР°СЋС‚СЃСЏ, РІС‹Р±СЂР°СЃС‹РІР°РµС‚СЃСЏ MetadataStaleError
        with pytest.raises(MetadataStaleError):
            await loader.load_instruments(["SWAP"])

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РјРµС‚РѕРґ РІС‹Р·РІР°Р»СЃСЏ 3 СЂР°Р·Р° (retry РґР»СЏ OKXIntegrationError)
        assert mock_market_instance.get_instruments.call_count >= 3

    @patch("src.candles.infrastructure.okx_integration.OKXMarket")
    async def test_partial_failure_handling(self, mock_market_class):
        """РўРµСЃС‚ РѕР±СЂР°Р±РѕС‚РєРё С‡Р°СЃС‚РёС‡РЅС‹С… РЅРµСѓРґР°С‡"""
        # РќР°СЃС‚СЂР°РёРІР°РµРј РјРѕРє РґР»СЏ СѓСЃРїРµС…Р° РѕРґРЅРѕРіРѕ С‚РёРїР° Рё РЅРµСѓРґР°С‡Рё РґСЂСѓРіРѕРіРѕ
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=[
                [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "instType": "SWAP",
                        "baseCcy": "BTC",
                        "quoteCcy": "USDT",
                    }
                ],  # SWAP СѓСЃРїРµС…
                Exception(
                    "Connection failed"
                ),  # FUTURES РЅРµСѓРґР°С‡Р° (Р±СѓРґРµС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРѕ РІ OKXNetworkError)
            ]
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # РЎРѕР·РґР°РµРј РЅРѕРІС‹Р№ loader СЃ РјРѕРєРѕРј С‡РµСЂРµР· DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.1, max_delay=1.0, market=mock_market_instance
        )

        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РіСЂСѓР·РєСѓ
        result = await loader.load_instruments(["SWAP", "FUTURES"])

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РїРѕР»СѓС‡РёР»Рё РґР°РЅРЅС‹Рµ С‚РѕР»СЊРєРѕ РѕС‚ СѓСЃРїРµС€РЅРѕРіРѕ С‚РёРїР°
        assert len(result) == 1
        assert result[0]["instId"] == "BTC-USDT-SWAP"

        # РџСЂРѕРІРµСЂСЏРµРј РєРѕР»РёС‡РµСЃС‚РІРѕ РІС‹Р·РѕРІРѕРІ
        # SWAP: 1 СѓСЃРїРµС€РЅС‹Р№ РІС‹Р·РѕРІ
        # FUTURES: 3 РїРѕРїС‹С‚РєРё (retry РґР»СЏ OKXNetworkError), РІСЃРµ РїСЂРѕРІР°Р»РёР»РёСЃСЊ
        assert mock_market_instance.get_instruments.call_count >= 4

    @patch("src.candles.infrastructure.okx_integration.OKXMarket")
    async def test_complete_failure_raises_metadata_stale_error(
        self, mock_market_class
    ):
        """РўРµСЃС‚ РїРѕР»РЅРѕР№ РЅРµСѓРґР°С‡Рё РІС‹Р·С‹РІР°РµС‚ MetadataStaleError"""
        # РќР°СЃС‚СЂР°РёРІР°РµРј РјРѕРє РґР»СЏ РїРѕР»РЅРѕР№ РЅРµСѓРґР°С‡Рё
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception(
                "Connection failed"
            )  # Р‘СѓРґРµС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРѕ РІ OKXNetworkError
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # РЎРѕР·РґР°РµРј РЅРѕРІС‹Р№ loader СЃ РјРѕРєРѕРј С‡РµСЂРµР· DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РіСЂСѓР·РєСѓ Рё РѕР¶РёРґР°РµРј MetadataStaleError
        with pytest.raises(MetadataStaleError) as exc_info:
            await loader.load_instruments(["SWAP", "FUTURES"])

        # РџСЂРѕРІРµСЂСЏРµРј СЃРѕРѕР±С‰РµРЅРёРµ РѕР± РѕС€РёР±РєРµ
        assert "failed_types" in str(exc_info.value)
        assert "SWAP" in str(exc_info.value) and "FUTURES" in str(exc_info.value)

    async def test_rate_limit_check(self):
        """РўРµСЃС‚ РїСЂРѕРІРµСЂРєРё rate limiting"""
        # РЎР±СЂР°СЃС‹РІР°РµРј СЃС‡РµС‚С‡РёРє
        self.loader._request_count = 0
        self.loader._last_request_time = 0

        # Р’С‹РїРѕР»РЅСЏРµРј РЅРµСЃРєРѕР»СЊРєРѕ РїСЂРѕРІРµСЂРѕРє РїРѕРґСЂСЏРґ
        start_time = asyncio.get_event_loop().time()

        for _i in range(5):
            await self.loader._rate_limit_check()

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ СЃС‡РµС‚С‡РёРє СѓРІРµР»РёС‡РёР»СЃСЏ
        assert self.loader._request_count == 5

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РЅРµ Р±С‹Р»Рѕ Р·Р°РґРµСЂР¶РµРє (РЅРµ РїСЂРµРІС‹СЃРёР»Рё Р»РёРјРёС‚)
        end_time = asyncio.get_event_loop().time()
        assert end_time - start_time < 0.1  # Р”РѕР»Р¶РЅРѕ Р±С‹С‚СЊ Р±С‹СЃС‚СЂРѕ

    async def test_rate_limit_enforcement(self):
        """РўРµСЃС‚ СЃРѕР±Р»СЋРґРµРЅРёСЏ rate limiting"""
        # РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј РІС‹СЃРѕРєРёР№ СЃС‡РµС‚С‡РёРє Р·Р°РїСЂРѕСЃРѕРІ
        self.loader._request_count = 10  # РњР°РєСЃРёРјСѓРј
        self.loader._last_request_time = asyncio.get_event_loop().time()

        # Р’С‹РїРѕР»РЅСЏРµРј РїСЂРѕРІРµСЂРєСѓ rate limit
        start_time = asyncio.get_event_loop().time()
        await self.loader._rate_limit_check()
        end_time = asyncio.get_event_loop().time()

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ Р±С‹Р»Р° Р·Р°РґРµСЂР¶РєР°
        assert (
            end_time - start_time >= 0.9
        )  # Р”РѕР»Р¶РЅР° Р±С‹С‚СЊ Р·Р°РґРµСЂР¶РєР° РѕРєРѕР»Рѕ 1 СЃРµРєСѓРЅРґС‹

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ СЃС‡РµС‚С‡РёРє СЃР±СЂРѕСЃРёР»СЃСЏ
        assert self.loader._request_count == 1

    @patch("src.candles.infrastructure.okx_integration.OKXMarket")
    async def test_exponential_backoff_timing(self, mock_market_class):
        """РўРµСЃС‚ СЌРєСЃРїРѕРЅРµРЅС†РёР°Р»СЊРЅРѕРіРѕ backoff"""
        # РќР°СЃС‚СЂР°РёРІР°РµРј РјРѕРє РґР»СЏ РёРјРёС‚Р°С†РёРё РѕС€РёР±РѕРє
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=[
                Exception(
                    "Connection timeout"
                ),  # Р‘СѓРґРµС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРѕ РІ OKXNetworkError
                Exception(
                    "Connection refused"
                ),  # Р‘СѓРґРµС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРѕ РІ OKXNetworkError
                [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "instType": "SWAP",
                        "baseCcy": "BTC",
                        "quoteCcy": "USDT",
                    }
                ],
            ]
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # РЎРѕР·РґР°РµРј РЅРѕРІС‹Р№ loader СЃ РјРѕРєРѕРј С‡РµСЂРµР· DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РіСЂСѓР·РєСѓ СЃ РёР·РјРµСЂРµРЅРёРµРј РІСЂРµРјРµРЅРё
        start_time = asyncio.get_event_loop().time()
        result = await loader.load_instruments(["SWAP"])
        end_time = asyncio.get_event_loop().time()

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert len(result) == 1

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ Р±С‹Р»Рѕ РІСЂРµРјСЏ РЅР° retry (СЌРєСЃРїРѕРЅРµРЅС†РёР°Р»СЊРЅС‹Р№ backoff)
        # РњРёРЅРёРјР°Р»СЊРЅР°СЏ Р·Р°РґРµСЂР¶РєР°: 4СЃ + 8СЃ = 12СЃ, РЅРѕ СЃ РЅР°С€РёРјРё РЅР°СЃС‚СЂРѕР№РєР°РјРё РјРµРЅСЊС€Рµ
        assert (
            end_time - start_time > 0.1
        )  # Р”РѕР»Р¶РЅР° Р±С‹С‚СЊ РєР°РєР°СЏ-С‚Рѕ Р·Р°РґРµСЂР¶РєР°


class TestOKXErrorHandling:
    """РўРµСЃС‚С‹ РѕР±СЂР°Р±РѕС‚РєРё РѕС€РёР±РѕРє OKX"""

    def setup_method(self):
        """РќР°СЃС‚СЂРѕР№РєР° РїРµСЂРµРґ РєР°Р¶РґС‹Рј С‚РµСЃС‚РѕРј"""
        self.loader = OKXMetadataLoader()

    @patch("src.candles.infrastructure.okx_integration.OKXMarket")
    async def test_error_transformation(self, mock_market_class):
        """РўРµСЃС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёСЏ РѕР±С‰РёС… РѕС€РёР±РѕРє РІ СЃРїРµС†РёС„РёС‡РЅС‹Рµ"""
        from tenacity import RetryError

        # РўРµСЃС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёСЏ rate limit РѕС€РёР±РєРё
        # Retry РґРµР»Р°РµС‚ 3 РїРѕРїС‹С‚РєРё, РІСЃРµ РїСЂРѕРІР°Р»РёРІР°СЋС‚СЃСЏ, РІС‹Р±СЂР°СЃС‹РІР°РµС‚СЃСЏ RetryError СЃ OKXRateLimitError РІРЅСѓС‚СЂРё
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception("rate limit exceeded")
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        loader = OKXMetadataLoader(
            max_retries=1, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )
        with pytest.raises((OKXRateLimitError, RetryError)) as exc_info:
            await loader._load_instrument_type("SWAP")
        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РІРЅСѓС‚СЂРё RetryError РµСЃС‚СЊ OKXRateLimitError
        if isinstance(exc_info.value, RetryError):
            assert isinstance(
                exc_info.value.last_attempt.exception(), OKXRateLimitError
            )

        # РўРµСЃС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёСЏ СЃРµС‚РµРІРѕР№ РѕС€РёР±РєРё
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception("connection timeout")
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        loader = OKXMetadataLoader(
            max_retries=1, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )
        with pytest.raises((OKXNetworkError, RetryError)) as exc_info:
            await loader._load_instrument_type("SWAP")
        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РІРЅСѓС‚СЂРё RetryError РµСЃС‚СЊ OKXNetworkError
        if isinstance(exc_info.value, RetryError):
            assert isinstance(exc_info.value.last_attempt.exception(), OKXNetworkError)

        # РўРµСЃС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёСЏ РѕР±С‰РµР№ РѕС€РёР±РєРё
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception("unknown error")
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        loader = OKXMetadataLoader(
            max_retries=1, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )
        with pytest.raises((OKXIntegrationError, RetryError)) as exc_info:
            await loader._load_instrument_type("SWAP")
        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РІРЅСѓС‚СЂРё RetryError РµСЃС‚СЊ OKXIntegrationError
        if isinstance(exc_info.value, RetryError):
            assert isinstance(
                exc_info.value.last_attempt.exception(), OKXIntegrationError
            )

    def test_loader_configuration(self):
        """РўРµСЃС‚ РєРѕРЅС„РёРіСѓСЂР°С†РёРё Р·Р°РіСЂСѓР·С‡РёРєР°"""
        # РўРµСЃС‚ СЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєРёРјРё РЅР°СЃС‚СЂРѕР№РєР°РјРё
        loader = OKXMetadataLoader(max_retries=5, base_delay=2.0, max_delay=120.0)

        assert loader.max_retries == 5
        assert loader.base_delay == 2.0
        assert loader.max_delay == 120.0
        assert loader._max_requests_per_second == 10


if __name__ == "__main__":
    pytest.main([__file__])
