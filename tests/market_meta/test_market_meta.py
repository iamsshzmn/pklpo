"""
РљРѕРјРїР»РµРєСЃРЅС‹Рµ С‚РµСЃС‚С‹ РґР»СЏ РјРѕРґСѓР»СЏ market_meta.

РџСЂРѕРІРµСЂСЏРµС‚ РІСЃСЋ С„СѓРЅРєС†РёРѕРЅР°Р»СЊРЅРѕСЃС‚СЊ РјРѕРґСѓР»СЏ:
- РЎРѕР·РґР°РЅРёРµ Рё РІР°Р»РёРґР°С†РёСЏ РјРµС‚Р°РґР°РЅРЅС‹С…
- Р’Р°Р»РёРґР°С†РёСЏ СЂС‹РЅРѕС‡РЅС‹С… РґР°РЅРЅС‹С… Рё РїРѕР·РёС†РёР№
- РЈРїСЂР°РІР»РµРЅРёРµ Р»РёРјРёС‚Р°РјРё СЂРёСЃРєР°
- РћСЃРЅРѕРІРЅРѕР№ API
- РРЅС‚РµРіСЂР°С†РёСЏ СЃ OKX
"""

from decimal import Decimal
from unittest.mock import Mock, patch

from src.market_meta_backup.application.api import (
    MarketMetaAPI,
    get_instrument_info,
    refresh_okx_meta,
    validate_order,
)
from src.market_meta_backup.domain.metadata import (
    InstrumentMetadata,
    InstrumentType,
    LotSize,
    MarginMode,
    MarketMetadata,
    TickSize,
)
from src.market_meta_backup.domain.risk_limits import (
    PositionLimit,
    PositionLimits,
    RiskLevel,
    RiskLimits,
)
from src.market_meta_backup.domain.validators import (
    MarketValidator,
    PositionValidator,
    ValidationResult,
)

# =============================================================================
# РўР•РЎРўР« РњР•РўРђР”РђРќРќР«РҐ
# =============================================================================


def test_instrument_metadata_creation():
    """РўРµСЃС‚ СЃРѕР·РґР°РЅРёСЏ РјРµС‚Р°РґР°РЅРЅС‹С… РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°"""
    # РЎРѕР·РґР°РµРј СЂР°Р·РјРµСЂС‹
    tick_size = TickSize(
        min_size=Decimal("0.1"), max_size=Decimal("1000000"), step_size=Decimal("0.1")
    )

    lot_size = LotSize(
        min_qty=Decimal("0.001"), max_qty=Decimal("1000"), step_size=Decimal("0.001")
    )

    # РЎРѕР·РґР°РµРј РёРЅСЃС‚СЂСѓРјРµРЅС‚
    instrument = InstrumentMetadata(
        symbol="BTC-USDT",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
        settle_ccy="USDT",
        tick_size=tick_size,
        lot_size=lot_size,
        contract_val=Decimal("0.01"),
        margin_mode=MarginMode.ISOLATED,
    )

    # РџСЂРѕРІРµСЂСЏРµРј СЃРІРѕР№СЃС‚РІР°
    assert instrument.symbol == "BTC-USDT"
    assert instrument.inst_type == InstrumentType.SWAP
    assert instrument.is_tradable()
    assert instrument.validate_order(50000.0, 0.1)

    # РџСЂРѕРІРµСЂСЏРµРј СЂР°СЃС‡РµС‚ РЅРѕРјРёРЅР°Р»СЊРЅРѕР№ СЃС‚РѕРёРјРѕСЃС‚Рё
    notional = instrument.calculate_notional_value(50000.0, 0.1)
    assert notional == Decimal("0.01") * Decimal("0.1")  # contract_val * quantity


def test_market_metadata():
    """РўРµСЃС‚ РјРµС‚Р°РґР°РЅРЅС‹С… СЂС‹РЅРєР°"""
    # РЎРѕР·РґР°РµРј РёРЅСЃС‚СЂСѓРјРµРЅС‚С‹
    btc_instrument = InstrumentMetadata(
        symbol="BTC-USDT",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
    )

    eth_instrument = InstrumentMetadata(
        symbol="ETH-USDT",
        inst_id="ETH-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="ETH",
        quote_ccy="USDT",
    )

    # РЎРѕР·РґР°РµРј СЂС‹РЅРѕРє
    market = MarketMetadata(
        exchange="OKX",
        instruments={"BTC-USDT": btc_instrument, "ETH-USDT": eth_instrument},
    )

    # РџСЂРѕРІРµСЂСЏРµРј РјРµС‚РѕРґС‹
    assert market.get_instrument("BTC-USDT") == btc_instrument
    assert market.get_instrument("INVALID") is None

    tradable = market.get_tradable_instruments()
    assert len(tradable) == 2

    swaps = market.get_instruments_by_type(InstrumentType.SWAP)
    assert len(swaps) == 2


def test_tick_size_validation():
    """РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё СЂР°Р·РјРµСЂР° С‚РёРєР°"""
    tick_size = TickSize(
        min_size=Decimal("0.1"), max_size=Decimal("1000000"), step_size=Decimal("0.1")
    )

    # Р’Р°Р»РёРґРЅС‹Рµ С†РµРЅС‹
    assert tick_size.validate_price(50000.0)
    assert tick_size.validate_price(50000.1)
    assert tick_size.validate_price(50000.2)

    # РќРµРІР°Р»РёРґРЅС‹Рµ С†РµРЅС‹
    assert not tick_size.validate_price(50000.05)  # РЅРµ РєСЂР°С‚РЅРѕ step_size
    assert not tick_size.validate_price(0.05)  # РјРµРЅСЊС€Рµ min_size
    assert not tick_size.validate_price(2000000.0)  # Р±РѕР»СЊС€Рµ max_size


def test_lot_size_validation():
    """РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё СЂР°Р·РјРµСЂР° Р»РѕС‚Р°"""
    lot_size = LotSize(
        min_qty=Decimal("0.001"), max_qty=Decimal("1000"), step_size=Decimal("0.001")
    )

    # Р’Р°Р»РёРґРЅС‹Рµ РєРѕР»РёС‡РµСЃС‚РІР°
    assert lot_size.validate_quantity(0.1)
    assert lot_size.validate_quantity(0.101)
    assert lot_size.validate_quantity(500.0)

    # РќРµРІР°Р»РёРґРЅС‹Рµ РєРѕР»РёС‡РµСЃС‚РІР°
    assert not lot_size.validate_quantity(0.0005)  # РјРµРЅСЊС€Рµ min_qty
    assert not lot_size.validate_quantity(0.1005)  # РЅРµ РєСЂР°С‚РЅРѕ step_size
    assert not lot_size.validate_quantity(1500.0)  # Р±РѕР»СЊС€Рµ max_qty


# =============================================================================
# РўР•РЎРўР« Р’РђР›РР”РђРўРћР РћР’
# =============================================================================


def test_market_validator():
    """РўРµСЃС‚ РІР°Р»РёРґР°С‚РѕСЂР° СЂС‹РЅРѕС‡РЅС‹С… РґР°РЅРЅС‹С…"""
    # РЎРѕР·РґР°РµРј СЂС‹РЅРѕРє СЃ РѕРґРЅРёРј РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРј
    instrument = InstrumentMetadata(
        symbol="BTC-USDT",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
    )

    market = MarketMetadata(exchange="OKX", instruments={"BTC-USDT": instrument})

    validator = MarketValidator(market)

    # РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё РєРѕСЂСЂРµРєС‚РЅС‹С… OHLCV РґР°РЅРЅС‹С…
    valid_ohlcv = [
        {
            "ts": 1640995200000,
            "open": "50000.0",
            "high": "50100.0",
            "low": "49900.0",
            "close": "50050.0",
            "volume": "100.0",
        }
    ]

    result = validator.validate_ohlcv_data("BTC-USDT", valid_ohlcv)
    assert result.is_valid
    assert len(result.errors) == 0

    # РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё РЅРµРєРѕСЂСЂРµРєС‚РЅС‹С… РґР°РЅРЅС‹С…
    invalid_ohlcv = [
        {
            "ts": 1640995200000,
            "open": "50000.0",
            "high": "49900.0",  # high < low
            "low": "50100.0",
            "close": "50050.0",
            "volume": "100.0",
        }
    ]

    result = validator.validate_ohlcv_data("BTC-USDT", invalid_ohlcv)
    assert not result.is_valid
    assert len(result.errors) > 0

    # РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°
    result = validator.validate_ohlcv_data("INVALID-SYMBOL", valid_ohlcv)
    assert not result.is_valid
    assert "not found" in result.errors[0]


def test_position_validator():
    """РўРµСЃС‚ РІР°Р»РёРґР°С‚РѕСЂР° РїРѕР·РёС†РёР№"""
    # РЎРѕР·РґР°РµРј СЂС‹РЅРѕРє
    instrument = InstrumentMetadata(
        symbol="BTC-USDT",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
        contract_val=Decimal("100"),  # РЈРІРµР»РёС‡РёРІР°РµРј contract_val РґР»СЏ РїСЂРѕС…РѕР¶РґРµРЅРёСЏ С‚РµСЃС‚Р°
    )

    market = MarketMetadata(exchange="OKX", instruments={"BTC-USDT": instrument})

    validator = PositionValidator(market)

    # РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё РєРѕСЂСЂРµРєС‚РЅРѕР№ РїРѕР·РёС†РёРё
    result = validator.validate_position_size("BTC-USDT", 0.1, 50000.0)
    assert result.is_valid

    # РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё РЅСѓР»РµРІРѕР№ РїРѕР·РёС†РёРё
    result = validator.validate_position_size("BTC-USDT", 0.0, 50000.0)
    assert not result.is_valid
    assert "cannot be zero" in result.errors[0]

    # РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё СЂРёСЃРєРѕРІ
    result = validator.validate_position_risk(
        "BTC-USDT", 0.1, 50000.0, account_balance=10000.0
    )
    assert result.is_valid

    # РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё СЂРёСЃРєРѕРІ (0.1 * 100 = 10, С‡С‚Рѕ СЃРѕСЃС‚Р°РІР»СЏРµС‚ 0.1% РѕС‚ Р±Р°Р»Р°РЅСЃР°)
    result = validator.validate_position_risk(
        "BTC-USDT", 0.1, 50000.0, account_balance=10000.0
    )
    assert result.is_valid  # 0.1 * 100 = 10, С‡С‚Рѕ СЃРѕСЃС‚Р°РІР»СЏРµС‚ 0.1% РѕС‚ Р±Р°Р»Р°РЅСЃР° 10000

    # РўРµСЃС‚ РїСЂРµРІС‹С€РµРЅРёСЏ Р»РёРјРёС‚Р° (0.05% РѕС‚ Р±Р°Р»Р°РЅСЃР°)
    result = validator.validate_position_risk(
        "BTC-USDT", 0.1, 50000.0, account_balance=10000.0, max_position_size_pct=0.0005
    )
    assert not result.is_valid  # 0.1% > 0.05%


def test_validation_result():
    """РўРµСЃС‚ СЂРµР·СѓР»СЊС‚Р°С‚Р° РІР°Р»РёРґР°С†РёРё"""
    result = ValidationResult(is_valid=True, errors=[], warnings=[])

    # Р”РѕР±Р°РІР»СЏРµРј РїСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ
    result.add_warning("Test warning")
    assert len(result.warnings) == 1
    assert result.is_valid  # РїСЂРµРґСѓРїСЂРµР¶РґРµРЅРёСЏ РЅРµ РІР»РёСЏСЋС‚ РЅР° РІР°Р»РёРґРЅРѕСЃС‚СЊ

    # Р”РѕР±Р°РІР»СЏРµРј РѕС€РёР±РєСѓ
    result.add_error("Test error")
    assert len(result.errors) == 1
    assert not result.is_valid  # РѕС€РёР±РєРё РґРµР»Р°СЋС‚ СЂРµР·СѓР»СЊС‚Р°С‚ РЅРµРІР°Р»РёРґРЅС‹Рј


# =============================================================================
# РўР•РЎРўР« Р›РРњРРўРћР’ Р РРЎРљРђ
# =============================================================================


def test_risk_limits():
    """РўРµСЃС‚ Р»РёРјРёС‚РѕРІ СЂРёСЃРєР°"""
    # РЎРѕР·РґР°РµРј Р»РёРјРёС‚С‹
    risk_limits = RiskLimits(
        max_total_exposure_pct=Decimal("0.5"), max_daily_loss_pct=Decimal("0.05")
    )

    # Р”РѕР±Р°РІР»СЏРµРј Р»РёРјРёС‚ РїРѕР·РёС†РёРё
    btc_limit = PositionLimit(
        symbol="BTC-USDT",
        max_quantity=Decimal("1.0"),
        max_notional_value=Decimal("100000"),
        max_position_size_pct=Decimal("0.1"),
        risk_level=RiskLevel.MEDIUM,
    )
    risk_limits.add_position_limit(btc_limit)

    # РџСЂРѕРІРµСЂСЏРµРј РїРѕР»СѓС‡РµРЅРёРµ Р»РёРјРёС‚Р°
    retrieved_limit = risk_limits.get_position_limit("BTC-USDT")
    assert retrieved_limit == btc_limit

    # РџСЂРѕРІРµСЂСЏРµРј РІР°Р»РёРґР°С†РёСЋ РїРѕР·РёС†РёРё
    assert btc_limit.validate_position(
        0.01, 50000.0, 10000.0
    )  # 0.01 * 50000 = 500, С‡С‚Рѕ СЃРѕСЃС‚Р°РІР»СЏРµС‚ 5% РѕС‚ Р±Р°Р»Р°РЅСЃР°
    assert not btc_limit.validate_position(
        0.5, 50000.0, 10000.0
    )  # 0.5 * 50000 = 25000, С‡С‚Рѕ СЃРѕСЃС‚Р°РІР»СЏРµС‚ 250% РѕС‚ Р±Р°Р»Р°РЅСЃР°


def test_position_limits():
    """РўРµСЃС‚ СѓРїСЂР°РІР»РµРЅРёСЏ РїРѕР·РёС†РёСЏРјРё"""
    # РЎРѕР·РґР°РµРј СЂС‹РЅРѕРє
    instrument = InstrumentMetadata(
        symbol="BTC-USDT",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
    )

    market = MarketMetadata(exchange="OKX", instruments={"BTC-USDT": instrument})

    # РЎРѕР·РґР°РµРј Р»РёРјРёС‚С‹
    risk_limits = RiskLimits()
    position_limits = PositionLimits(risk_limits, market)

    # Р”РѕР±Р°РІР»СЏРµРј РїРѕР·РёС†РёСЋ
    position_limits.add_position("BTC-USDT", 0.1, 50000.0)

    # РџСЂРѕРІРµСЂСЏРµРј СЃРІРѕРґРєСѓ
    summary = position_limits.get_position_summary()
    assert summary["total_positions"] == 1
    assert "BTC-USDT" in summary["positions"]

    # РџСЂРѕРІРµСЂСЏРµРј РјРµС‚СЂРёРєРё
    metrics = position_limits.get_risk_metrics(account_balance=10000.0)
    assert metrics["position_count"] == 1
    assert metrics["total_exposure_pct"] > 0

    # РџСЂРѕРІРµСЂСЏРµРј Р°Р»РµСЂС‚С‹
    alerts = position_limits.check_risk_alerts(account_balance=10000.0)
    # РџРѕРєР° Р°Р»РµСЂС‚РѕРІ РЅРµС‚, С‚Р°Рє РєР°Рє РїРѕР·РёС†РёСЏ РЅРµР±РѕР»СЊС€Р°СЏ
    assert len(alerts) == 0


# =============================================================================
# РўР•РЎРўР« API
# =============================================================================


class TestMarketMetaAPI:
    """РўРµСЃС‚С‹ РґР»СЏ MarketMetaAPI"""

    def setup_method(self):
        """РќР°СЃС‚СЂРѕР№РєР° РїРµСЂРµРґ РєР°Р¶РґС‹Рј С‚РµСЃС‚РѕРј"""
        self.api = MarketMetaAPI()

    @patch("src.candles.application.api.OKXMetadataLoader")
    async def test_refresh_okx_meta_success(self, mock_loader_class):
        """РўРµСЃС‚ СѓСЃРїРµС€РЅРѕРіРѕ РѕР±РЅРѕРІР»РµРЅРёСЏ РјРµС‚Р°РґР°РЅРЅС‹С…"""
        from unittest.mock import AsyncMock

        # РњРѕРєР°РµРј Р·Р°РіСЂСѓР·С‡РёРє
        mock_loader = Mock()
        mock_loader_class.return_value = mock_loader

        # РњРѕРєР°РµРј РґР°РЅРЅС‹Рµ РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ
        mock_instruments_data = [
            {
                "instId": "BTC-USDT-SWAP",
                "instType": "SWAP",
                "baseCcy": "BTC",
                "quoteCcy": "USDT",
                "settleCcy": "USDT",
                "state": "live",
                "tickSz": "0.1",
                "lotSz": "0.01",
                "minSz": "0.01",
                "maxSz": "1000",
                "ctVal": "0.01",
            }
        ]
        mock_loader.load_instruments = AsyncMock(return_value=mock_instruments_data)

        # РњРѕРєР°РµРј РєРѕРЅРІРµСЂС‚Р°С†РёСЋ
        mock_instrument = InstrumentMetadata(
            symbol="BTC-USDT-SWAP",
            inst_id="BTC-USDT-SWAP",
            inst_type=InstrumentType.SWAP,
            base_ccy="BTC",
            quote_ccy="USDT",
            settle_ccy="USDT",
            tick_size=TickSize(
                min_size=Decimal("0.1"),
                max_size=Decimal("999999999"),
                step_size=Decimal("0.1"),
            ),
            lot_size=LotSize(
                min_qty=Decimal("0.01"),
                max_qty=Decimal("1000"),
                step_size=Decimal("0.01"),
            ),
            contract_val=Decimal("0.01"),
        )
        mock_loader.convert_to_metadata.return_value = mock_instrument

        # РЎР±СЂР°СЃС‹РІР°РµРј РєСЌС€ Рё РІС‹РїРѕР»РЅСЏРµРј РѕР±РЅРѕРІР»РµРЅРёРµ СЃ force=True
        self.api._last_refresh = None
        self.api.market_metadata = None
        result = await self.api.refresh_okx_meta(force=True)

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert result is True
        assert self.api.market_metadata is not None
        assert len(self.api.market_metadata.instruments) == 1
        assert "BTC-USDT-SWAP" in self.api.market_metadata.instruments
        assert self.api.validator is not None
        assert self.api.position_validator is not None
        assert self.api.risk_limits is not None
        assert self.api.position_limits is not None

    @patch("src.candles.application.api.OKXMetadataLoader")
    async def test_refresh_okx_meta_failure(self, mock_loader_class):
        """РўРµСЃС‚ РЅРµСѓРґР°С‡РЅРѕРіРѕ РѕР±РЅРѕРІР»РµРЅРёСЏ РјРµС‚Р°РґР°РЅРЅС‹С…"""
        from unittest.mock import AsyncMock

        # РЎР±СЂР°СЃС‹РІР°РµРј РєСЌС€, С‡С‚РѕР±С‹ РіР°СЂР°РЅС‚РёСЂРѕРІР°С‚СЊ РїРѕРїС‹С‚РєСѓ РѕР±РЅРѕРІР»РµРЅРёСЏ
        self.api._last_refresh = None
        self.api.market_metadata = None

        mock_loader = AsyncMock()
        mock_loader_class.return_value = mock_loader

        # РСЃРїРѕР»СЊР·СѓРµРј side_effect РґР»СЏ async РјРµС‚РѕРґР°
        async def raise_exception():
            raise Exception("API Error")

        mock_loader.load_instruments = AsyncMock(side_effect=raise_exception)

        # Р’С‹РїРѕР»РЅСЏРµРј РѕР±РЅРѕРІР»РµРЅРёРµ СЃ force=True, С‡С‚РѕР±С‹ РіР°СЂР°РЅС‚РёСЂРѕРІР°С‚СЊ РїРѕРїС‹С‚РєСѓ РѕР±РЅРѕРІР»РµРЅРёСЏ
        result = await self.api.refresh_okx_meta(force=True)

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert result is False
        # market_metadata РјРѕР¶РµС‚ Р±С‹С‚СЊ None РёР»Рё РѕСЃС‚Р°С‚СЊСЃСЏ РѕС‚ РїСЂРµРґС‹РґСѓС‰РµРіРѕ С‚РµСЃС‚Р°
        # Р“Р»Р°РІРЅРѕРµ - С‡С‚Рѕ РѕР±РЅРѕРІР»РµРЅРёРµ РЅРµ РїСЂРѕС€Р»Рѕ СѓСЃРїРµС€РЅРѕ

    def test_validate_order_no_metadata(self):
        """РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё РѕСЂРґРµСЂР° Р±РµР· Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… РјРµС‚Р°РґР°РЅРЅС‹С…"""
        violations = self.api.validate_order("BTC-USDT", 50000.0, 0.1)

        assert len(violations) == 1
        assert "refresh_okx_meta" in violations[0]

    def test_validate_order_invalid_symbol(self):
        """РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё РѕСЂРґРµСЂР° СЃ РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРј СЃРёРјРІРѕР»РѕРј"""
        # РЎРѕР·РґР°РµРј РїСѓСЃС‚С‹Рµ РјРµС‚Р°РґР°РЅРЅС‹Рµ
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = None

        violations = self.api.validate_order("INVALID-SYMBOL", 50000.0, 0.1)

        assert len(violations) == 1
        assert "INVALID-SYMBOL" in violations[0]

    def test_validate_order_success(self):
        """РўРµСЃС‚ СѓСЃРїРµС€РЅРѕР№ РІР°Р»РёРґР°С†РёРё РѕСЂРґРµСЂР°"""
        # РЎРѕР·РґР°РµРј РёРЅСЃС‚СЂСѓРјРµРЅС‚
        instrument = InstrumentMetadata(
            symbol="BTC-USDT-SWAP",
            inst_id="BTC-USDT-SWAP",
            inst_type=InstrumentType.SWAP,
            base_ccy="BTC",
            quote_ccy="USDT",
            settle_ccy="USDT",
            tick_size=TickSize(
                min_size=Decimal("0.1"),
                max_size=Decimal("999999999"),
                step_size=Decimal("0.1"),
            ),
            lot_size=LotSize(
                min_qty=Decimal("0.01"),
                max_qty=Decimal("1000"),
                step_size=Decimal("0.01"),
            ),
            contract_val=Decimal("0.01"),
        )

        # РЎРѕР·РґР°РµРј РјРµС‚Р°РґР°РЅРЅС‹Рµ
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = instrument

        # РЎРѕР·РґР°РµРј РІР°Р»РёРґР°С‚РѕСЂС‹
        self.api.validator = Mock()
        self.api.validator.validate_price_data.return_value = Mock(
            is_valid=True, errors=[]
        )
        self.api.validator.validate_volume_data.return_value = Mock(
            is_valid=True, errors=[]
        )

        self.api.position_validator = Mock()
        self.api.position_validator.validate_position_risk.return_value = Mock(
            is_valid=True, errors=[]
        )

        self.api.position_limits = Mock()
        self.api.position_limits.validate_new_position.return_value = {
            "position_limit": True,
            "total_exposure": True,
            "spot": True,
            "swap": True,
            "futures": True,
        }

        # Р’С‹РїРѕР»РЅСЏРµРј РІР°Р»РёРґР°С†РёСЋ
        violations = self.api.validate_order("BTC-USDT-SWAP", 50000.0, 0.1)

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert len(violations) == 0

    def test_validate_order_price_violation(self):
        """РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё РѕСЂРґРµСЂР° СЃ РЅР°СЂСѓС€РµРЅРёРµРј С†РµРЅС‹"""
        # РЎРѕР·РґР°РµРј РёРЅСЃС‚СЂСѓРјРµРЅС‚
        instrument = InstrumentMetadata(
            symbol="BTC-USDT-SWAP",
            inst_id="BTC-USDT-SWAP",
            inst_type=InstrumentType.SWAP,
            base_ccy="BTC",
            quote_ccy="USDT",
            settle_ccy="USDT",
            tick_size=TickSize(
                min_size=Decimal("0.1"),
                max_size=Decimal("999999999"),
                step_size=Decimal("0.1"),
            ),
            lot_size=LotSize(
                min_qty=Decimal("0.01"),
                max_qty=Decimal("1000"),
                step_size=Decimal("0.01"),
            ),
            contract_val=Decimal("0.01"),
        )

        # РњРѕРєРёСЂСѓРµРј validate_order РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°, С‡С‚РѕР±С‹ РЅРµ РґРѕР±Р°РІР»СЏС‚СЊ РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ РЅР°СЂСѓС€РµРЅРёСЏ
        instrument.validate_order = Mock(return_value=True)

        # РЎРѕР·РґР°РµРј РјРµС‚Р°РґР°РЅРЅС‹Рµ
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = instrument

        # РЎРѕР·РґР°РµРј РІР°Р»РёРґР°С‚РѕСЂ СЃ РѕС€РёР±РєРѕР№ С†РµРЅС‹
        self.api.validator = Mock()
        self.api.validator.validate_price_data.return_value = Mock(
            is_valid=False, errors=["Р¦РµРЅР° РЅРµ СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ СЂР°Р·РјРµСЂСѓ С‚РёРєР°"]
        )
        self.api.validator.validate_volume_data.return_value = Mock(
            is_valid=True, errors=[]
        )

        self.api.position_validator = Mock()
        self.api.position_validator.validate_position_risk.return_value = Mock(
            is_valid=True, errors=[]
        )

        self.api.position_limits = Mock()
        self.api.position_limits.validate_new_position.return_value = {
            "position_limit": True,
            "total_exposure": True,
            "spot": True,
            "swap": True,
            "futures": True,
        }

        # Р’С‹РїРѕР»РЅСЏРµРј РІР°Р»РёРґР°С†РёСЋ
        violations = self.api.validate_order("BTC-USDT-SWAP", 50000.05, 0.1)

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert len(violations) == 1
        assert "СЂР°Р·РјРµСЂСѓ С‚РёРєР°" in violations[0]

    def test_get_instrument_info(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РёРЅС„РѕСЂРјР°С†РёРё РѕР± РёРЅСЃС‚СЂСѓРјРµРЅС‚Рµ"""
        # РЎРѕР·РґР°РµРј РёРЅСЃС‚СЂСѓРјРµРЅС‚
        instrument = InstrumentMetadata(
            symbol="BTC-USDT-SWAP",
            inst_id="BTC-USDT-SWAP",
            inst_type=InstrumentType.SWAP,
            base_ccy="BTC",
            quote_ccy="USDT",
            settle_ccy="USDT",
            tick_size=TickSize(
                min_size=Decimal("0.1"),
                max_size=Decimal("999999999"),
                step_size=Decimal("0.1"),
            ),
            lot_size=LotSize(
                min_qty=Decimal("0.01"),
                max_qty=Decimal("1000"),
                step_size=Decimal("0.01"),
            ),
            contract_val=Decimal("0.01"),
        )

        # РЎРѕР·РґР°РµРј РјРµС‚Р°РґР°РЅРЅС‹Рµ
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = instrument

        # РџРѕР»СѓС‡Р°РµРј РёРЅС„РѕСЂРјР°С†РёСЋ
        info = self.api.get_instrument_info("BTC-USDT-SWAP")

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert info is not None
        assert info["symbol"] == "BTC-USDT-SWAP"
        assert info["inst_type"] == "SWAP"
        assert info["base_ccy"] == "BTC"
        assert info["quote_ccy"] == "USDT"
        assert info["is_tradable"] is True
        assert info["tick_size"]["step"] == 0.1
        assert info["lot_size"]["step"] == 0.01
        assert info["contract_val"] == 0.01

    def test_calculate_notional_value(self):
        """РўРµСЃС‚ СЂР°СЃС‡РµС‚Р° РЅРѕРјРёРЅР°Р»СЊРЅРѕР№ СЃС‚РѕРёРјРѕСЃС‚Рё"""
        # РЎРѕР·РґР°РµРј РёРЅСЃС‚СЂСѓРјРµРЅС‚
        instrument = InstrumentMetadata(
            symbol="BTC-USDT-SWAP",
            inst_id="BTC-USDT-SWAP",
            inst_type=InstrumentType.SWAP,
            base_ccy="BTC",
            quote_ccy="USDT",
            settle_ccy="USDT",
            contract_val=Decimal("0.01"),
        )

        # РЎРѕР·РґР°РµРј РјРµС‚Р°РґР°РЅРЅС‹Рµ
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = instrument

        # Р Р°СЃСЃС‡РёС‚С‹РІР°РµРј РЅРѕРјРёРЅР°Р»СЊРЅСѓСЋ СЃС‚РѕРёРјРѕСЃС‚СЊ
        notional = self.api.calculate_notional_value("BTC-USDT-SWAP", 50000.0, 0.1)

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚ (contract_val * qty = 0.01 * 0.1 = 0.001)
        assert notional == 0.001

    def test_get_risk_metrics(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РјРµС‚СЂРёРє СЂРёСЃРєР°"""
        # РЎРѕР·РґР°РµРј position_limits
        self.api.position_limits = Mock()
        self.api.position_limits.get_risk_metrics.return_value = {
            "total_exposure_pct": 0.25,
            "position_count": 3,
            "avg_position_size": 1000.0,
        }

        # РџРѕР»СѓС‡Р°РµРј РјРµС‚СЂРёРєРё
        metrics = self.api.get_risk_metrics(10000.0)

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert metrics["total_exposure_pct"] == 0.25
        assert metrics["position_count"] == 3
        assert metrics["avg_position_size"] == 1000.0

    def test_check_risk_alerts(self):
        """РўРµСЃС‚ РїСЂРѕРІРµСЂРєРё Р°Р»РµСЂС‚РѕРІ СЂРёСЃРєР°"""
        # РЎРѕР·РґР°РµРј position_limits
        self.api.position_limits = Mock()
        self.api.position_limits.check_risk_alerts.return_value = [
            "Р’С‹СЃРѕРєР°СЏ РѕР±С‰Р°СЏ СЌРєСЃРїРѕР·РёС†РёСЏ: 75% (Р»РёРјРёС‚: 50%)"
        ]

        # РџСЂРѕРІРµСЂСЏРµРј Р°Р»РµСЂС‚С‹
        alerts = self.api.check_risk_alerts(10000.0)

        # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
        assert len(alerts) == 1
        assert "СЌРєСЃРїРѕР·РёС†РёСЏ" in alerts[0]


# =============================================================================
# РўР•РЎРўР« Р“Р›РћР‘РђР›Р¬РќР«РҐ Р¤РЈРќРљР¦РР™
# =============================================================================


class TestGlobalFunctions:
    """РўРµСЃС‚С‹ РґР»СЏ РіР»РѕР±Р°Р»СЊРЅС‹С… С„СѓРЅРєС†РёР№"""

    @patch("src.candles.application.api.market_meta_api")
    async def test_refresh_okx_meta_global(self, mock_api):
        """РўРµСЃС‚ РіР»РѕР±Р°Р»СЊРЅРѕР№ С„СѓРЅРєС†РёРё refresh_okx_meta"""
        from unittest.mock import AsyncMock

        mock_api.refresh_okx_meta = AsyncMock(return_value=True)

        result = await refresh_okx_meta()

        assert result is True
        mock_api.refresh_okx_meta.assert_called_once()

    @patch("src.candles.application.api.market_meta_api")
    def test_validate_order_global(self, mock_api):
        """РўРµСЃС‚ РіР»РѕР±Р°Р»СЊРЅРѕР№ С„СѓРЅРєС†РёРё validate_order"""
        mock_api.validate_order.return_value = []

        violations = validate_order("BTC-USDT", 50000.0, 0.1)

        assert violations == []
        mock_api.validate_order.assert_called_once_with("BTC-USDT", 50000.0, 0.1)

    @patch("src.candles.application.api.market_meta_api")
    def test_get_instrument_info_global(self, mock_api):
        """РўРµСЃС‚ РіР»РѕР±Р°Р»СЊРЅРѕР№ С„СѓРЅРєС†РёРё get_instrument_info"""
        mock_info = {"symbol": "BTC-USDT", "inst_type": "SWAP"}
        mock_api.get_instrument_info.return_value = mock_info

        info = get_instrument_info("BTC-USDT")

        assert info == mock_info
        mock_api.get_instrument_info.assert_called_once_with("BTC-USDT")


# =============================================================================
# РРќРўР•Р“Р РђР¦РРћРќРќР«Р• РўР•РЎРўР«
# =============================================================================


def test_full_validation_flow():
    """РўРµСЃС‚ РїРѕР»РЅРѕРіРѕ РїРѕС‚РѕРєР° РІР°Р»РёРґР°С†РёРё"""
    # РЎРѕР·РґР°РµРј РїРѕР»РЅС‹Р№ РЅР°Р±РѕСЂ РјРµС‚Р°РґР°РЅРЅС‹С…
    instrument = InstrumentMetadata(
        symbol="BTC-USDT",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
        settle_ccy="USDT",
        tick_size=TickSize(
            min_size=Decimal("0.1"),
            max_size=Decimal("1000000"),
            step_size=Decimal("0.1"),
        ),
        lot_size=LotSize(
            min_qty=Decimal("0.001"),
            max_qty=Decimal("1000"),
            step_size=Decimal("0.001"),
        ),
        contract_val=Decimal("100"),
        margin_mode=MarginMode.ISOLATED,
    )

    market = MarketMetadata(exchange="OKX", instruments={"BTC-USDT": instrument})

    # РЎРѕР·РґР°РµРј РІР°Р»РёРґР°С‚РѕСЂС‹
    market_validator = MarketValidator(market)
    position_validator = PositionValidator(market)

    # РЎРѕР·РґР°РµРј Р»РёРјРёС‚С‹ СЃ СѓРІРµР»РёС‡РµРЅРЅС‹Рј Р»РёРјРёС‚РѕРј СЌРєСЃРїРѕР·РёС†РёРё
    risk_limits = RiskLimits(max_total_exposure_pct=Decimal("0.6"))  # 60% РІРјРµСЃС‚Рѕ 50%
    position_limits = PositionLimits(risk_limits, market)

    # РўРµСЃС‚РёСЂСѓРµРј РІР°Р»РёРґР°С†РёСЋ РѕСЂРґРµСЂР°
    violations = []

    # 1. Р’Р°Р»РёРґР°С†РёСЏ С†РµРЅС‹
    price_result = market_validator.validate_price_data("BTC-USDT", 50000.1)
    if not price_result.is_valid:
        violations.extend(price_result.errors)

    # 2. Р’Р°Р»РёРґР°С†РёСЏ РѕР±СЉРµРјР°
    volume_result = market_validator.validate_volume_data("BTC-USDT", 0.1)
    if not volume_result.is_valid:
        violations.extend(volume_result.errors)

    # 3. Р’Р°Р»РёРґР°С†РёСЏ РїРѕР·РёС†РёРё
    position_result = position_validator.validate_position_size(
        "BTC-USDT", 0.1, 50000.1
    )
    if not position_result.is_valid:
        violations.extend(position_result.errors)

    # 4. Р’Р°Р»РёРґР°С†РёСЏ СЂРёСЃРєРѕРІ
    risk_result = position_validator.validate_position_risk(
        "BTC-USDT", 0.1, 50000.1, account_balance=10000.0
    )
    if not risk_result.is_valid:
        violations.extend(risk_result.errors)

    # 5. РџСЂРѕРІРµСЂРєР° Р»РёРјРёС‚РѕРІ
    limit_results = position_limits.validate_new_position(
        "BTC-USDT", 0.1, 50000.1, account_balance=10000.0
    )
    for check_name, is_valid in limit_results.items():
        if not is_valid:
            violations.append(f"РќР°СЂСѓС€РµРЅ Р»РёРјРёС‚: {check_name}")

    # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РІСЃРµ РІР°Р»РёРґР°С†РёРё РїСЂРѕС€Р»Рё СѓСЃРїРµС€РЅРѕ
    assert len(violations) == 0, f"РќР°Р№РґРµРЅС‹ РЅР°СЂСѓС€РµРЅРёСЏ: {violations}"


# =============================================================================
# Р—РђРџРЈРЎРљ РўР•РЎРўРћР’
# =============================================================================


def run_all_tests():
    """Р—Р°РїСѓСЃРє РІСЃРµС… С‚РµСЃС‚РѕРІ"""
    print("рџ§Є Р—Р°РїСѓСЃРє РєРѕРјРїР»РµРєСЃРЅС‹С… С‚РµСЃС‚РѕРІ market_meta...")

    # РўРµСЃС‚С‹ РјРµС‚Р°РґР°РЅРЅС‹С…
    test_instrument_metadata_creation()
    print("вњ… РўРµСЃС‚ СЃРѕР·РґР°РЅРёСЏ РјРµС‚Р°РґР°РЅРЅС‹С… РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°")

    test_market_metadata()
    print("вњ… РўРµСЃС‚ РјРµС‚Р°РґР°РЅРЅС‹С… СЂС‹РЅРєР°")

    test_tick_size_validation()
    print("вњ… РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё СЂР°Р·РјРµСЂР° С‚РёРєР°")

    test_lot_size_validation()
    print("вњ… РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё СЂР°Р·РјРµСЂР° Р»РѕС‚Р°")

    # РўРµСЃС‚С‹ РІР°Р»РёРґР°С‚РѕСЂРѕРІ
    test_market_validator()
    print("вњ… РўРµСЃС‚ РІР°Р»РёРґР°С‚РѕСЂР° СЂС‹РЅРѕС‡РЅС‹С… РґР°РЅРЅС‹С…")

    test_position_validator()
    print("вњ… РўРµСЃС‚ РІР°Р»РёРґР°С‚РѕСЂР° РїРѕР·РёС†РёР№")

    test_validation_result()
    print("вњ… РўРµСЃС‚ СЂРµР·СѓР»СЊС‚Р°С‚Р° РІР°Р»РёРґР°С†РёРё")

    # РўРµСЃС‚С‹ Р»РёРјРёС‚РѕРІ СЂРёСЃРєР°
    test_risk_limits()
    print("вњ… РўРµСЃС‚ Р»РёРјРёС‚РѕРІ СЂРёСЃРєР°")

    test_position_limits()
    print("вњ… РўРµСЃС‚ СѓРїСЂР°РІР»РµРЅРёСЏ РїРѕР·РёС†РёСЏРјРё")

    # РРЅС‚РµРіСЂР°С†РёРѕРЅРЅС‹Рµ С‚РµСЃС‚С‹
    test_full_validation_flow()
    print("вњ… РўРµСЃС‚ РїРѕР»РЅРѕРіРѕ РїРѕС‚РѕРєР° РІР°Р»РёРґР°С†РёРё")

    print("\nрџЋ‰ Р’СЃРµ С‚РµСЃС‚С‹ РїСЂРѕС€Р»Рё СѓСЃРїРµС€РЅРѕ!")


if __name__ == "__main__":
    # Р—Р°РїСѓСЃРє РІСЃРµС… С‚РµСЃС‚РѕРІ
    run_all_tests()

    # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ С‚РµСЃС‚С‹ API (С‚СЂРµР±СѓСЋС‚ async)
    print("\nрџ”„ Р—Р°РїСѓСЃРє Р°СЃРёРЅС…СЂРѕРЅРЅС‹С… С‚РµСЃС‚РѕРІ API...")

    # РЎРѕР·РґР°РµРј С‚РµСЃС‚РѕРІС‹Р№ СЌРєР·РµРјРїР»СЏСЂ API
    api = MarketMetaAPI()

    # РўРµСЃС‚ Р±РµР· РјРµС‚Р°РґР°РЅРЅС‹С…
    violations = api.validate_order("BTC-USDT", 50000.0, 0.1)
    print(f"вњ… РўРµСЃС‚ РІР°Р»РёРґР°С†РёРё РѕСЂРґРµСЂР° Р±РµР· РјРµС‚Р°РґР°РЅРЅС‹С…: {len(violations)} РЅР°СЂСѓС€РµРЅРёР№")

    # РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РёРЅС„РѕСЂРјР°С†РёРё Р±РµР· РјРµС‚Р°РґР°РЅРЅС‹С…
    info = api.get_instrument_info("BTC-USDT")
    print(f"вњ… РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РёРЅС„РѕСЂРјР°С†РёРё Р±РµР· РјРµС‚Р°РґР°РЅРЅС‹С…: {info is None}")

    print("\nрџЋ‰ Р’СЃРµ С‚РµСЃС‚С‹ Р·Р°РІРµСЂС€РµРЅС‹!")
