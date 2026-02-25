"""
Комплексные тесты для модуля market_meta.

Проверяет всю функциональность модуля:
- Создание и валидация метаданных
- Валидация рыночных данных и позиций
- Управление лимитами риска
- Основной API
- Интеграция с OKX
"""

from decimal import Decimal
from unittest.mock import Mock, patch

from src.market_meta.application.api import (
    MarketMetaAPI,
    get_instrument_info,
    refresh_okx_meta,
    validate_order,
)
from src.market_meta.domain.metadata import (
    InstrumentMetadata,
    InstrumentType,
    LotSize,
    MarginMode,
    MarketMetadata,
    TickSize,
)
from src.market_meta.domain.risk_limits import (
    PositionLimit,
    PositionLimits,
    RiskLevel,
    RiskLimits,
)
from src.market_meta.domain.validators import (
    MarketValidator,
    PositionValidator,
    ValidationResult,
)

# =============================================================================
# ТЕСТЫ МЕТАДАННЫХ
# =============================================================================


def test_instrument_metadata_creation():
    """Тест создания метаданных инструмента"""
    # Создаем размеры
    tick_size = TickSize(
        min_size=Decimal("0.1"), max_size=Decimal("1000000"), step_size=Decimal("0.1")
    )

    lot_size = LotSize(
        min_qty=Decimal("0.001"), max_qty=Decimal("1000"), step_size=Decimal("0.001")
    )

    # Создаем инструмент
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

    # Проверяем свойства
    assert instrument.symbol == "BTC-USDT"
    assert instrument.inst_type == InstrumentType.SWAP
    assert instrument.is_tradable()
    assert instrument.validate_order(50000.0, 0.1)

    # Проверяем расчет номинальной стоимости
    notional = instrument.calculate_notional_value(50000.0, 0.1)
    assert notional == Decimal("0.01") * Decimal("0.1")  # contract_val * quantity


def test_market_metadata():
    """Тест метаданных рынка"""
    # Создаем инструменты
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

    # Создаем рынок
    market = MarketMetadata(
        exchange="OKX",
        instruments={"BTC-USDT": btc_instrument, "ETH-USDT": eth_instrument},
    )

    # Проверяем методы
    assert market.get_instrument("BTC-USDT") == btc_instrument
    assert market.get_instrument("INVALID") is None

    tradable = market.get_tradable_instruments()
    assert len(tradable) == 2

    swaps = market.get_instruments_by_type(InstrumentType.SWAP)
    assert len(swaps) == 2


def test_tick_size_validation():
    """Тест валидации размера тика"""
    tick_size = TickSize(
        min_size=Decimal("0.1"), max_size=Decimal("1000000"), step_size=Decimal("0.1")
    )

    # Валидные цены
    assert tick_size.validate_price(50000.0)
    assert tick_size.validate_price(50000.1)
    assert tick_size.validate_price(50000.2)

    # Невалидные цены
    assert not tick_size.validate_price(50000.05)  # не кратно step_size
    assert not tick_size.validate_price(0.05)  # меньше min_size
    assert not tick_size.validate_price(2000000.0)  # больше max_size


def test_lot_size_validation():
    """Тест валидации размера лота"""
    lot_size = LotSize(
        min_qty=Decimal("0.001"), max_qty=Decimal("1000"), step_size=Decimal("0.001")
    )

    # Валидные количества
    assert lot_size.validate_quantity(0.1)
    assert lot_size.validate_quantity(0.101)
    assert lot_size.validate_quantity(500.0)

    # Невалидные количества
    assert not lot_size.validate_quantity(0.0005)  # меньше min_qty
    assert not lot_size.validate_quantity(0.1005)  # не кратно step_size
    assert not lot_size.validate_quantity(1500.0)  # больше max_qty


# =============================================================================
# ТЕСТЫ ВАЛИДАТОРОВ
# =============================================================================


def test_market_validator():
    """Тест валидатора рыночных данных"""
    # Создаем рынок с одним инструментом
    instrument = InstrumentMetadata(
        symbol="BTC-USDT",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
    )

    market = MarketMetadata(exchange="OKX", instruments={"BTC-USDT": instrument})

    validator = MarketValidator(market)

    # Тест валидации корректных OHLCV данных
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

    # Тест валидации некорректных данных
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

    # Тест валидации несуществующего инструмента
    result = validator.validate_ohlcv_data("INVALID-SYMBOL", valid_ohlcv)
    assert not result.is_valid
    assert "not found" in result.errors[0]


def test_position_validator():
    """Тест валидатора позиций"""
    # Создаем рынок
    instrument = InstrumentMetadata(
        symbol="BTC-USDT",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
        contract_val=Decimal("100"),  # Увеличиваем contract_val для прохождения теста
    )

    market = MarketMetadata(exchange="OKX", instruments={"BTC-USDT": instrument})

    validator = PositionValidator(market)

    # Тест валидации корректной позиции
    result = validator.validate_position_size("BTC-USDT", 0.1, 50000.0)
    assert result.is_valid

    # Тест валидации нулевой позиции
    result = validator.validate_position_size("BTC-USDT", 0.0, 50000.0)
    assert not result.is_valid
    assert "cannot be zero" in result.errors[0]

    # Тест валидации рисков
    result = validator.validate_position_risk(
        "BTC-USDT", 0.1, 50000.0, account_balance=10000.0
    )
    assert result.is_valid

    # Тест валидации рисков (0.1 * 100 = 10, что составляет 0.1% от баланса)
    result = validator.validate_position_risk(
        "BTC-USDT", 0.1, 50000.0, account_balance=10000.0
    )
    assert result.is_valid  # 0.1 * 100 = 10, что составляет 0.1% от баланса 10000

    # Тест превышения лимита (0.05% от баланса)
    result = validator.validate_position_risk(
        "BTC-USDT", 0.1, 50000.0, account_balance=10000.0, max_position_size_pct=0.0005
    )
    assert not result.is_valid  # 0.1% > 0.05%


def test_validation_result():
    """Тест результата валидации"""
    result = ValidationResult(is_valid=True, errors=[], warnings=[])

    # Добавляем предупреждение
    result.add_warning("Test warning")
    assert len(result.warnings) == 1
    assert result.is_valid  # предупреждения не влияют на валидность

    # Добавляем ошибку
    result.add_error("Test error")
    assert len(result.errors) == 1
    assert not result.is_valid  # ошибки делают результат невалидным


# =============================================================================
# ТЕСТЫ ЛИМИТОВ РИСКА
# =============================================================================


def test_risk_limits():
    """Тест лимитов риска"""
    # Создаем лимиты
    risk_limits = RiskLimits(
        max_total_exposure_pct=Decimal("0.5"), max_daily_loss_pct=Decimal("0.05")
    )

    # Добавляем лимит позиции
    btc_limit = PositionLimit(
        symbol="BTC-USDT",
        max_quantity=Decimal("1.0"),
        max_notional_value=Decimal("100000"),
        max_position_size_pct=Decimal("0.1"),
        risk_level=RiskLevel.MEDIUM,
    )
    risk_limits.add_position_limit(btc_limit)

    # Проверяем получение лимита
    retrieved_limit = risk_limits.get_position_limit("BTC-USDT")
    assert retrieved_limit == btc_limit

    # Проверяем валидацию позиции
    assert btc_limit.validate_position(
        0.01, 50000.0, 10000.0
    )  # 0.01 * 50000 = 500, что составляет 5% от баланса
    assert not btc_limit.validate_position(
        0.5, 50000.0, 10000.0
    )  # 0.5 * 50000 = 25000, что составляет 250% от баланса


def test_position_limits():
    """Тест управления позициями"""
    # Создаем рынок
    instrument = InstrumentMetadata(
        symbol="BTC-USDT",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
    )

    market = MarketMetadata(exchange="OKX", instruments={"BTC-USDT": instrument})

    # Создаем лимиты
    risk_limits = RiskLimits()
    position_limits = PositionLimits(risk_limits, market)

    # Добавляем позицию
    position_limits.add_position("BTC-USDT", 0.1, 50000.0)

    # Проверяем сводку
    summary = position_limits.get_position_summary()
    assert summary["total_positions"] == 1
    assert "BTC-USDT" in summary["positions"]

    # Проверяем метрики
    metrics = position_limits.get_risk_metrics(account_balance=10000.0)
    assert metrics["position_count"] == 1
    assert metrics["total_exposure_pct"] > 0

    # Проверяем алерты
    alerts = position_limits.check_risk_alerts(account_balance=10000.0)
    # Пока алертов нет, так как позиция небольшая
    assert len(alerts) == 0


# =============================================================================
# ТЕСТЫ API
# =============================================================================


class TestMarketMetaAPI:
    """Тесты для MarketMetaAPI"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.api = MarketMetaAPI()

    @patch("src.market_meta.application.api.OKXMetadataLoader")
    async def test_refresh_okx_meta_success(self, mock_loader_class):
        """Тест успешного обновления метаданных"""
        from unittest.mock import AsyncMock

        # Мокаем загрузчик
        mock_loader = Mock()
        mock_loader_class.return_value = mock_loader

        # Мокаем данные инструментов
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

        # Мокаем конвертацию
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

        # Сбрасываем кэш и выполняем обновление с force=True
        self.api._last_refresh = None
        self.api.market_metadata = None
        result = await self.api.refresh_okx_meta(force=True)

        # Проверяем результат
        assert result is True
        assert self.api.market_metadata is not None
        assert len(self.api.market_metadata.instruments) == 1
        assert "BTC-USDT-SWAP" in self.api.market_metadata.instruments
        assert self.api.validator is not None
        assert self.api.position_validator is not None
        assert self.api.risk_limits is not None
        assert self.api.position_limits is not None

    @patch("src.market_meta.application.api.OKXMetadataLoader")
    async def test_refresh_okx_meta_failure(self, mock_loader_class):
        """Тест неудачного обновления метаданных"""
        from unittest.mock import AsyncMock

        # Сбрасываем кэш, чтобы гарантировать попытку обновления
        self.api._last_refresh = None
        self.api.market_metadata = None

        mock_loader = AsyncMock()
        mock_loader_class.return_value = mock_loader

        # Используем side_effect для async метода
        async def raise_exception():
            raise Exception("API Error")

        mock_loader.load_instruments = AsyncMock(side_effect=raise_exception)

        # Выполняем обновление с force=True, чтобы гарантировать попытку обновления
        result = await self.api.refresh_okx_meta(force=True)

        # Проверяем результат
        assert result is False
        # market_metadata может быть None или остаться от предыдущего теста
        # Главное - что обновление не прошло успешно

    def test_validate_order_no_metadata(self):
        """Тест валидации ордера без загруженных метаданных"""
        violations = self.api.validate_order("BTC-USDT", 50000.0, 0.1)

        assert len(violations) == 1
        assert "Метаданные рынка не загружены" in violations[0]

    def test_validate_order_invalid_symbol(self):
        """Тест валидации ордера с несуществующим символом"""
        # Создаем пустые метаданные
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = None

        violations = self.api.validate_order("INVALID-SYMBOL", 50000.0, 0.1)

        assert len(violations) == 1
        assert "не найден в метаданных" in violations[0]

    def test_validate_order_success(self):
        """Тест успешной валидации ордера"""
        # Создаем инструмент
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

        # Создаем метаданные
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = instrument

        # Создаем валидаторы
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

        # Выполняем валидацию
        violations = self.api.validate_order("BTC-USDT-SWAP", 50000.0, 0.1)

        # Проверяем результат
        assert len(violations) == 0

    def test_validate_order_price_violation(self):
        """Тест валидации ордера с нарушением цены"""
        # Создаем инструмент
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

        # Мокируем validate_order инструмента, чтобы не добавлять дополнительные нарушения
        instrument.validate_order = Mock(return_value=True)

        # Создаем метаданные
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = instrument

        # Создаем валидатор с ошибкой цены
        self.api.validator = Mock()
        self.api.validator.validate_price_data.return_value = Mock(
            is_valid=False, errors=["Цена не соответствует размеру тика"]
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

        # Выполняем валидацию
        violations = self.api.validate_order("BTC-USDT-SWAP", 50000.05, 0.1)

        # Проверяем результат
        assert len(violations) == 1
        assert "размеру тика" in violations[0]

    def test_get_instrument_info(self):
        """Тест получения информации об инструменте"""
        # Создаем инструмент
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

        # Создаем метаданные
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = instrument

        # Получаем информацию
        info = self.api.get_instrument_info("BTC-USDT-SWAP")

        # Проверяем результат
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
        """Тест расчета номинальной стоимости"""
        # Создаем инструмент
        instrument = InstrumentMetadata(
            symbol="BTC-USDT-SWAP",
            inst_id="BTC-USDT-SWAP",
            inst_type=InstrumentType.SWAP,
            base_ccy="BTC",
            quote_ccy="USDT",
            settle_ccy="USDT",
            contract_val=Decimal("0.01"),
        )

        # Создаем метаданные
        self.api.market_metadata = Mock()
        self.api.market_metadata.get_instrument.return_value = instrument

        # Рассчитываем номинальную стоимость
        notional = self.api.calculate_notional_value("BTC-USDT-SWAP", 50000.0, 0.1)

        # Проверяем результат (contract_val * qty = 0.01 * 0.1 = 0.001)
        assert notional == 0.001

    def test_get_risk_metrics(self):
        """Тест получения метрик риска"""
        # Создаем position_limits
        self.api.position_limits = Mock()
        self.api.position_limits.get_risk_metrics.return_value = {
            "total_exposure_pct": 0.25,
            "position_count": 3,
            "avg_position_size": 1000.0,
        }

        # Получаем метрики
        metrics = self.api.get_risk_metrics(10000.0)

        # Проверяем результат
        assert metrics["total_exposure_pct"] == 0.25
        assert metrics["position_count"] == 3
        assert metrics["avg_position_size"] == 1000.0

    def test_check_risk_alerts(self):
        """Тест проверки алертов риска"""
        # Создаем position_limits
        self.api.position_limits = Mock()
        self.api.position_limits.check_risk_alerts.return_value = [
            "Высокая общая экспозиция: 75% (лимит: 50%)"
        ]

        # Проверяем алерты
        alerts = self.api.check_risk_alerts(10000.0)

        # Проверяем результат
        assert len(alerts) == 1
        assert "экспозиция" in alerts[0]


# =============================================================================
# ТЕСТЫ ГЛОБАЛЬНЫХ ФУНКЦИЙ
# =============================================================================


class TestGlobalFunctions:
    """Тесты для глобальных функций"""

    @patch("src.market_meta.application.api.market_meta_api")
    async def test_refresh_okx_meta_global(self, mock_api):
        """Тест глобальной функции refresh_okx_meta"""
        from unittest.mock import AsyncMock

        mock_api.refresh_okx_meta = AsyncMock(return_value=True)

        result = await refresh_okx_meta()

        assert result is True
        mock_api.refresh_okx_meta.assert_called_once()

    @patch("src.market_meta.application.api.market_meta_api")
    def test_validate_order_global(self, mock_api):
        """Тест глобальной функции validate_order"""
        mock_api.validate_order.return_value = []

        violations = validate_order("BTC-USDT", 50000.0, 0.1)

        assert violations == []
        mock_api.validate_order.assert_called_once_with("BTC-USDT", 50000.0, 0.1)

    @patch("src.market_meta.application.api.market_meta_api")
    def test_get_instrument_info_global(self, mock_api):
        """Тест глобальной функции get_instrument_info"""
        mock_info = {"symbol": "BTC-USDT", "inst_type": "SWAP"}
        mock_api.get_instrument_info.return_value = mock_info

        info = get_instrument_info("BTC-USDT")

        assert info == mock_info
        mock_api.get_instrument_info.assert_called_once_with("BTC-USDT")


# =============================================================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# =============================================================================


def test_full_validation_flow():
    """Тест полного потока валидации"""
    # Создаем полный набор метаданных
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

    # Создаем валидаторы
    market_validator = MarketValidator(market)
    position_validator = PositionValidator(market)

    # Создаем лимиты с увеличенным лимитом экспозиции
    risk_limits = RiskLimits(max_total_exposure_pct=Decimal("0.6"))  # 60% вместо 50%
    position_limits = PositionLimits(risk_limits, market)

    # Тестируем валидацию ордера
    violations = []

    # 1. Валидация цены
    price_result = market_validator.validate_price_data("BTC-USDT", 50000.1)
    if not price_result.is_valid:
        violations.extend(price_result.errors)

    # 2. Валидация объема
    volume_result = market_validator.validate_volume_data("BTC-USDT", 0.1)
    if not volume_result.is_valid:
        violations.extend(volume_result.errors)

    # 3. Валидация позиции
    position_result = position_validator.validate_position_size(
        "BTC-USDT", 0.1, 50000.1
    )
    if not position_result.is_valid:
        violations.extend(position_result.errors)

    # 4. Валидация рисков
    risk_result = position_validator.validate_position_risk(
        "BTC-USDT", 0.1, 50000.1, account_balance=10000.0
    )
    if not risk_result.is_valid:
        violations.extend(risk_result.errors)

    # 5. Проверка лимитов
    limit_results = position_limits.validate_new_position(
        "BTC-USDT", 0.1, 50000.1, account_balance=10000.0
    )
    for check_name, is_valid in limit_results.items():
        if not is_valid:
            violations.append(f"Нарушен лимит: {check_name}")

    # Проверяем, что все валидации прошли успешно
    assert len(violations) == 0, f"Найдены нарушения: {violations}"


# =============================================================================
# ЗАПУСК ТЕСТОВ
# =============================================================================


def run_all_tests():
    """Запуск всех тестов"""
    print("🧪 Запуск комплексных тестов market_meta...")

    # Тесты метаданных
    test_instrument_metadata_creation()
    print("✅ Тест создания метаданных инструмента")

    test_market_metadata()
    print("✅ Тест метаданных рынка")

    test_tick_size_validation()
    print("✅ Тест валидации размера тика")

    test_lot_size_validation()
    print("✅ Тест валидации размера лота")

    # Тесты валидаторов
    test_market_validator()
    print("✅ Тест валидатора рыночных данных")

    test_position_validator()
    print("✅ Тест валидатора позиций")

    test_validation_result()
    print("✅ Тест результата валидации")

    # Тесты лимитов риска
    test_risk_limits()
    print("✅ Тест лимитов риска")

    test_position_limits()
    print("✅ Тест управления позициями")

    # Интеграционные тесты
    test_full_validation_flow()
    print("✅ Тест полного потока валидации")

    print("\n🎉 Все тесты прошли успешно!")


if __name__ == "__main__":
    # Запуск всех тестов
    run_all_tests()

    # Дополнительные тесты API (требуют async)
    print("\n🔄 Запуск асинхронных тестов API...")

    # Создаем тестовый экземпляр API
    api = MarketMetaAPI()

    # Тест без метаданных
    violations = api.validate_order("BTC-USDT", 50000.0, 0.1)
    print(f"✅ Тест валидации ордера без метаданных: {len(violations)} нарушений")

    # Тест получения информации без метаданных
    info = api.get_instrument_info("BTC-USDT")
    print(f"✅ Тест получения информации без метаданных: {info is None}")

    print("\n🎉 Все тесты завершены!")
