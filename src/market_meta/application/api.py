"""
Основной API для модуля market_meta.

Предоставляет функции для:
- Обновления метаданных с OKX
- Валидации ордеров
- Получения информации об инструментах
"""

import asyncio
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from ..domain.exceptions import (
    MetadataStaleError,
    OKXIntegrationError,
    OrderValidationError,
    ValidationError,
)
from ..domain.metadata import FundingRate, MarketMetadata
from ..domain.risk_limits import PositionLimits, RiskLimits
from ..domain.validators import MarketValidator, PositionValidator
from ..infrastructure.config import get_config
from ..infrastructure.logging_config import (
    get_logger,
    log_cache_status,
    log_refresh_status,
    log_validation_result,
)
from ..infrastructure.metrics import get_metrics_collector, measure_async_time
from ..infrastructure.okx_integration import OKXMetadataLoader

logger = get_logger("api")


class MarketMetaAPI:
    """Основной API для работы с метаданными рынка"""

    def __init__(self):
        self.market_metadata: MarketMetadata | None = None
        self.validator: MarketValidator | None = None
        self.position_validator: PositionValidator | None = None
        self.risk_limits: RiskLimits | None = None
        self.position_limits: PositionLimits | None = None

        # Загружаем конфигурацию
        config = get_config()

        # Кэширование из конфигурации
        self._last_refresh: datetime | None = None
        self._cache_ttl: timedelta = timedelta(hours=config.cache.metadata_ttl_hours)
        self._refresh_lock = asyncio.Lock()

        # Авто-refresh из конфигурации
        self._auto_refresh_enabled = config.cache.auto_refresh_enabled
        self._auto_refresh_interval = timedelta(
            hours=config.cache.auto_refresh_interval_hours
        )
        self._auto_refresh_task: asyncio.Task | None = None

        # Метрики
        self._metrics_collector = get_metrics_collector()

        # НЕ запускаем авто-refresh в конструкторе - это будет сделано лениво

    def _is_cache_valid(self) -> bool:
        """Проверяет, действителен ли кэш"""
        if not self._last_refresh or not self.market_metadata:
            self._metrics_collector.record_cache_miss()
            return False

        is_valid = datetime.now() - self._last_refresh < self._cache_ttl
        if is_valid:
            self._metrics_collector.record_cache_hit()
        else:
            self._metrics_collector.record_cache_miss()

        return is_valid

    def _start_auto_refresh(self):
        """Запускает авто-refresh метаданных"""
        if self._auto_refresh_task and not self._auto_refresh_task.done():
            return

        # Проверяем, есть ли запущенный event loop
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # Нет запущенного event loop - не запускаем авто-refresh
            logger.warning("Нет запущенного event loop, авто-refresh не запущен")
            return

        async def _auto_refresh_loop():
            while self._auto_refresh_enabled:
                try:
                    await asyncio.sleep(self._auto_refresh_interval.total_seconds())
                    if not self._is_cache_valid():
                        logger.info("Авто-refresh: обновляем метаданные")
                        await self.refresh_okx_meta()
                except Exception as e:
                    logger.error(f"Ошибка авто-refresh: {e}")

        self._auto_refresh_task = asyncio.create_task(_auto_refresh_loop())

    def stop_auto_refresh(self):
        """Останавливает авто-refresh"""
        self._auto_refresh_enabled = False
        if self._auto_refresh_task:
            self._auto_refresh_task.cancel()

    def start_auto_refresh(self):
        """Запускает авто-refresh (если есть event loop)"""
        if self._auto_refresh_enabled:
            self._start_auto_refresh()

    def set_cache_ttl(self, hours: int):
        """Устанавливает TTL кэша в часах"""
        self._cache_ttl = timedelta(hours=hours)

    def get_cache_status(self) -> dict[str, Any]:
        """Возвращает статус кэша"""
        status = {
            "is_valid": self._is_cache_valid(),
            "last_refresh": (
                self._last_refresh.isoformat() if self._last_refresh else None
            ),
            "ttl_hours": self._cache_ttl.total_seconds() / 3600,
            "auto_refresh_enabled": self._auto_refresh_enabled,
            "instruments_count": (
                len(self.market_metadata.instruments) if self.market_metadata else 0
            ),
        }
        log_cache_status(status)
        return status

    async def refresh_okx_meta(self, force: bool = False) -> bool:
        """
        Обновляет метаданные с OKX API.

        Args:
            force: Принудительное обновление (игнорирует кэш)

        Returns:
            bool: True если обновление прошло успешно
        """
        async with self._refresh_lock:
            # Проверяем кэш если не принудительное обновление
            if not force and self._is_cache_valid():
                logger.info("Метаданные актуальны, используем кэш")
                return True

            try:
                async with measure_async_time("cache_refresh"):
                    logger.info("Начинаем обновление метаданных OKX...")

                    # Загружаем метаданные с OKX
                    loader = OKXMetadataLoader()
                    instruments_data = await loader.load_instruments()

                    # Преобразуем в наши модели
                    instruments = {}
                    for data in instruments_data:
                        try:
                            instrument = loader.convert_to_metadata(data)
                            if instrument:
                                instruments[instrument.symbol] = instrument
                        except Exception as e:
                            logger.warning(
                                f"Ошибка конвертации инструмента {data.get('instId', 'unknown')}: {e}"
                            )

                    # Создаем метаданные рынка
                    self.market_metadata = MarketMetadata(
                        exchange="OKX", instruments=instruments
                    )

                    # Инициализируем валидаторы
                    self.validator = MarketValidator(self.market_metadata)
                    self.position_validator = PositionValidator(self.market_metadata)

                    # Создаем лимиты риска
                    self.risk_limits = RiskLimits()
                    self.position_limits = PositionLimits(
                        self.risk_limits, self.market_metadata
                    )

                    # Обновляем время последнего обновления
                    self._last_refresh = datetime.now()

                    # Записываем метрики
                    self._metrics_collector.record_instruments_loaded(len(instruments))

                    log_refresh_status(True, len(instruments))
                    return True

            except MetadataStaleError as e:
                error_msg = f"Метаданные устарели: {e}"
                logger.error(error_msg)
                log_refresh_status(False, 0, error_msg)
                return False
            except OKXIntegrationError as e:
                error_msg = f"Ошибка интеграции с OKX: {e}"
                logger.error(error_msg)
                log_refresh_status(False, 0, error_msg)
                return False
            except Exception as e:
                error_msg = f"Неожиданная ошибка обновления метаданных: {e}"
                logger.error(error_msg)
                log_refresh_status(False, 0, error_msg)
                return False

    async def refresh_okx_meta_extended(self, force: bool = False) -> bool:
        """
        Обновляет метаданные с OKX API (расширенная версия).

        Args:
            force: Принудительное обновление, игнорируя кэш

        Returns:
            True если обновление прошло успешно
        """
        try:
            # Проверяем кэш если не принудительное обновление
            if not force and not self._is_cache_valid():
                logger.info("✅ Метаданные актуальны, обновление не требуется")
                return True

            logger.info("🔄 Обновление расширенных метаданных с OKX API...")

            # Создаем загрузчик
            loader = OKXMetadataLoader()

            # Загружаем базовые инструменты
            instruments = await loader.load_instruments()

            # Загружаем расширенные данные
            funding_rates = await loader.load_funding_rates_extended()
            mark_prices = await loader.load_mark_prices_extended()
            tickers = await loader.load_tickers_extended()
            open_interest = await loader.load_open_interest_extended()

            # Конвертируем в метаданные
            metadata_dict = {}
            for instrument_data in instruments:
                metadata = loader.convert_to_metadata(instrument_data)
                if metadata:
                    # Обогащаем расширенными данными
                    symbol = metadata.symbol

                    # Добавляем ставки финансирования
                    if symbol in funding_rates:
                        funding_data = funding_rates[symbol]
                        if funding_data.get("fundingRate"):
                            metadata.funding_rate = FundingRate(
                                rate=Decimal(str(funding_data["fundingRate"])),
                                next_funding_time=datetime.fromtimestamp(
                                    int(funding_data.get("nextFundingTime", 0)) / 1000
                                ),
                                funding_interval_hours=8,
                            )

                    # Добавляем маржевые цены
                    if symbol in mark_prices:
                        mark_prices[symbol]
                        # Можно добавить поле mark_price в InstrumentMetadata

                    # Добавляем данные тикеров для ликвидности
                    if symbol in tickers:
                        ticker_data = tickers[symbol]
                        # Обновляем параметры ликвидности на основе реальных данных
                        if ticker_data.get("volCcy24h"):
                            volume_24h = Decimal(str(ticker_data["volCcy24h"]))
                            if metadata.liquidity:
                                metadata.liquidity.min_volume_24h = min(
                                    metadata.liquidity.min_volume_24h,
                                    volume_24h
                                    * Decimal("0.1"),  # 10% от текущего объема
                                )

                    # Добавляем открытый интерес
                    if symbol in open_interest:
                        open_interest[symbol]
                        # Можно добавить поле open_interest в InstrumentMetadata

                    metadata_dict[symbol] = metadata

            # Обновляем кэш
            self.market_metadata = MarketMetadata(
                exchange="OKX", instruments=metadata_dict
            )
            self._last_refresh = datetime.now()

            logger.info(
                f"✅ Расширенные метаданные обновлены: {len(metadata_dict)} инструментов"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка обновления расширенных метаданных: {e}")
            return False

    def get_funding_rate(self, symbol: str) -> FundingRate | None:
        """
        Получает ставку финансирования для инструмента.

        Args:
            symbol: Символ инструмента

        Returns:
            Ставка финансирования или None
        """
        try:
            if not self.market_metadata:
                raise MetadataStaleError("Метаданные не загружены")

            instrument = self.market_metadata.get_instrument(symbol)
            if not instrument:
                return None

            return instrument.funding_rate

        except Exception as e:
            logger.error(f"Ошибка получения ставки финансирования для {symbol}: {e}")
            return None

    def get_mark_price(self, symbol: str) -> Decimal | None:
        """
        Получает маржевую цену для инструмента.

        Args:
            symbol: Символ инструмента

        Returns:
            Маржевая цена или None
        """
        try:
            if not self.market_metadata:
                raise MetadataStaleError("Метаданные не загружены")

            # TODO: Добавить поле mark_price в InstrumentMetadata
            # Пока возвращаем None
            return None

        except Exception as e:
            logger.error(f"Ошибка получения маржевой цены для {symbol}: {e}")
            return None

    def get_liquidity_info(self, symbol: str) -> dict[str, Any] | None:
        """
        Получает информацию о ликвидности инструмента.

        Args:
            symbol: Символ инструмента

        Returns:
            Информация о ликвидности или None
        """
        try:
            if not self.market_metadata:
                raise MetadataStaleError("Метаданные не загружены")

            instrument = self.market_metadata.get_instrument(symbol)
            if not instrument or not instrument.liquidity:
                return None

            return {
                "min_volume_24h": instrument.liquidity.min_volume_24h,
                "min_trades_24h": instrument.liquidity.min_trades_24h,
                "spread_threshold": instrument.liquidity.spread_threshold,
            }

        except Exception as e:
            logger.error(f"Ошибка получения информации о ликвидности для {symbol}: {e}")
            return None

    def get_open_interest(self, symbol: str) -> Decimal | None:
        """
        Получает открытый интерес для инструмента.

        Args:
            symbol: Символ инструмента

        Returns:
            Открытый интерес или None
        """
        try:
            if not self.market_metadata:
                raise MetadataStaleError("Метаданные не загружены")

            # TODO: Добавить поле open_interest в InstrumentMetadata
            # Пока возвращаем None
            return None

        except Exception as e:
            logger.error(f"Ошибка получения открытого интереса для {symbol}: {e}")
            return None

    def validate_order(
        self,
        symbol: str,
        price: float,
        qty: float,
        order_type: str = "limit",
        side: str = "buy",
        account_balance: float | None = None,
        **kwargs: dict[str, Any],
    ) -> list[str]:
        """
        Валидирует параметры ордера.

        Args:
            symbol: Символ инструмента
            price: Цена
            qty: Количество
            order_type: Тип ордера (limit, market)
            side: Сторона (buy, sell)
            account_balance: Баланс аккаунта (для проверки рисков)

        Returns:
            List[str]: Список нарушений (пустой если все OK)
        """
        start_time = time.time()
        violations = []
        warnings = []

        try:
            if not self.market_metadata:
                violations.append(
                    "Метаданные рынка не загружены. Выполните refresh_okx_meta()"
                )
                log_validation_result(symbol, violations, warnings)
                return violations

            # Получаем инструмент
            instrument = self.market_metadata.get_instrument(symbol)
            if not instrument:
                violations.append(f"Инструмент {symbol} не найден в метаданных")
                log_validation_result(symbol, violations, warnings)
                return violations

            # Проверяем торгуемость
            if not instrument.is_tradable():
                violations.append(
                    f"Инструмент {symbol} не торгуется (статус: {instrument.state})"
                )

            # Валидация цены
            if price <= 0:
                violations.append("Цена должна быть положительной")
            elif self.validator:
                price_result = self.validator.validate_price_data(symbol, price)
                if not price_result.is_valid:
                    violations.extend(price_result.errors)

            # Валидация количества
            if qty <= 0:
                violations.append("Количество должно быть положительным")
            elif self.validator:
                volume_result = self.validator.validate_volume_data(symbol, qty)
                if not volume_result.is_valid:
                    violations.extend(volume_result.errors)

            # Валидация ордера
            if not instrument.validate_order(price, qty):
                violations.append(
                    "Параметры ордера не соответствуют требованиям инструмента"
                )

            # Валидация рисков (если переданы параметры)
            if self.validator:
                # Валидация плеча (если передано)
                leverage = kwargs.get("leverage")
                margin_mode = kwargs.get("margin_mode")
                if leverage is not None and margin_mode is not None:
                    risk_result = self.validator.validate_risk(
                        symbol, leverage, margin_mode
                    )
                    if not risk_result.is_valid:
                        violations.extend(risk_result.errors)

                # Валидация ликвидности (если переданы параметры)
                spread_bps = kwargs.get("spread_bps")
                vol_usdt = kwargs.get("vol_usdt")
                book_depth = kwargs.get("book_depth")
                if (
                    spread_bps is not None
                    and vol_usdt is not None
                    and book_depth is not None
                ):
                    liquidity_result = self.validator.validate_liquidity(
                        symbol, spread_bps, vol_usdt, book_depth
                    )
                    if not liquidity_result.is_valid:
                        violations.extend(liquidity_result.errors)

            # Проверка лимитов риска
            if account_balance and self.position_validator:
                risk_result = self.position_validator.validate_position_risk(
                    symbol, qty, price, account_balance
                )
                if not risk_result.is_valid:
                    violations.extend(risk_result.errors)

            # Проверка лимитов позиций
            if self.position_limits:
                position_results = self.position_limits.validate_new_position(
                    symbol, qty, price, account_balance or 0
                )
                for check_name, is_valid in position_results.items():
                    if not is_valid:
                        violations.append(f"Нарушен лимит: {check_name}")

            # Логируем результат валидации
            log_validation_result(symbol, violations, warnings)

            # Записываем метрики валидации
            duration = time.time() - start_time
            if violations:
                self._metrics_collector.record_validation_failure(duration)
            else:
                self._metrics_collector.record_validation_success(duration)

            return violations

        except Exception:
            # Записываем ошибку в метрики
            self._metrics_collector.record_error()
            duration = time.time() - start_time
            self._metrics_collector.record_validation_failure(duration)
            raise

    def get_instrument_info(self, symbol: str) -> dict[str, Any] | None:
        """
        Получает информацию об инструменте.

        Args:
            symbol: Символ инструмента

        Returns:
            Dict с информацией об инструменте или None
        """
        if not self.market_metadata:
            return None

        instrument = self.market_metadata.get_instrument(symbol)
        if not instrument:
            return None

        return {
            "symbol": instrument.symbol,
            "inst_id": instrument.inst_id,
            "inst_type": instrument.inst_type.value,
            "base_ccy": instrument.base_ccy,
            "quote_ccy": instrument.quote_ccy,
            "settle_ccy": instrument.settle_ccy,
            "state": instrument.state,
            "is_tradable": instrument.is_tradable(),
            "tick_size": (
                {
                    "min": (
                        float(instrument.tick_size.min_size)
                        if instrument.tick_size
                        else None
                    ),
                    "max": (
                        float(instrument.tick_size.max_size)
                        if instrument.tick_size
                        else None
                    ),
                    "step": (
                        float(instrument.tick_size.step_size)
                        if instrument.tick_size
                        else None
                    ),
                }
                if instrument.tick_size
                else None
            ),
            "lot_size": (
                {
                    "min": (
                        float(instrument.lot_size.min_qty)
                        if instrument.lot_size
                        else None
                    ),
                    "max": (
                        float(instrument.lot_size.max_qty)
                        if instrument.lot_size
                        else None
                    ),
                    "step": (
                        float(instrument.lot_size.step_size)
                        if instrument.lot_size
                        else None
                    ),
                }
                if instrument.lot_size
                else None
            ),
            "contract_val": (
                float(instrument.contract_val) if instrument.contract_val else None
            ),
            "fee_maker": float(instrument.fee_maker) if instrument.fee_maker else None,
            "fee_taker": float(instrument.fee_taker) if instrument.fee_taker else None,
            "max_leverage": instrument.max_leverage,
            "margin_mode": (
                instrument.margin_mode.value if instrument.margin_mode else None
            ),
            "position_mode": instrument.position_mode,
            "maint_margin_rate": (
                float(instrument.maint_margin_rate)
                if instrument.maint_margin_rate
                else None
            ),
            "risk_limit_tier": instrument.risk_limit_tier,
        }

    def calculate_notional_value(
        self, symbol: str, price: float, qty: float
    ) -> float | None:
        """
        Рассчитывает номинальную стоимость позиции.

        Args:
            symbol: Символ инструмента
            price: Цена
            qty: Количество

        Returns:
            Номинальная стоимость или None
        """
        if not self.market_metadata:
            return None

        instrument = self.market_metadata.get_instrument(symbol)
        if not instrument:
            return None

        return float(instrument.calculate_notional_value(price, qty))

    def get_risk_metrics(self, account_balance: float) -> dict[str, Any]:
        """
        Получает метрики риска.

        Args:
            account_balance: Баланс аккаунта

        Returns:
            Dict с метриками риска
        """
        if not self.position_limits:
            return {}

        return self.position_limits.get_risk_metrics(account_balance)

    def check_risk_alerts(self, account_balance: float) -> list[str]:
        """
        Проверяет алерты риска.

        Args:
            account_balance: Баланс аккаунта

        Returns:
            Список алертов
        """
        if not self.position_limits:
            return []

        return self.position_limits.check_risk_alerts(account_balance)


# Глобальный экземпляр API
market_meta_api = MarketMetaAPI()


# Удобные функции для быстрого доступа
async def refresh_okx_meta() -> bool:
    """Обновляет метаданные OKX"""
    return await market_meta_api.refresh_okx_meta()


def validate_order(symbol: str, price: float, qty: float, **kwargs) -> list[str]:
    """Валидирует ордер"""
    return market_meta_api.validate_order(symbol, price, qty, **kwargs)


def get_instrument_info(symbol: str) -> dict[str, Any] | None:
    """Получает информацию об инструменте"""
    return market_meta_api.get_instrument_info(symbol)


def calculate_notional_value(symbol: str, price: float, qty: float) -> float | None:
    """Рассчитывает номинальную стоимость"""
    return market_meta_api.calculate_notional_value(symbol, price, qty)


async def refresh_okx_meta_extended(force: bool = False) -> bool:
    """Обновляет расширенные метаданные OKX"""
    return await market_meta_api.refresh_okx_meta_extended(force)


def get_funding_rate(symbol: str) -> FundingRate | None:
    """Получает ставку финансирования для инструмента"""
    return market_meta_api.get_funding_rate(symbol)


def get_mark_price(symbol: str) -> float | None:
    """Получает маржевую цену для инструмента"""
    return market_meta_api.get_mark_price(symbol)


def get_liquidity_info(symbol: str) -> dict[str, Any] | None:
    """Получает информацию о ликвидности для инструмента"""
    return market_meta_api.get_liquidity_info(symbol)


def get_open_interest(symbol: str) -> dict[str, Any] | None:
    """Получает открытый интерес для инструмента"""
    return market_meta_api.get_open_interest(symbol)
