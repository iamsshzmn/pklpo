"""
Интеграция с OKX API для загрузки метаданных инструментов.

Загружает реальные данные с OKX и преобразует их в наши модели метаданных.
Включает retry/backoff механизмы и обработку ошибок.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ..domain.exceptions import (
    MetadataStaleError,
    OKXIntegrationError,
    OKXNetworkError,
    OKXRateLimitError,
)
from ..domain.metadata import (
    FundingRate,
    InstrumentMetadata,
    InstrumentType,
    LiquidityParams,
    LotSize,
    MarginMode,
    TickSize,
)
from .client import OKXClient
from .config import get_config
from .logging_config import get_logger
from .market import OKXMarket
from .metrics import get_metrics_collector, measure_async_time

logger = get_logger("okx_integration")


def _get_okx_retry():
    """
    Создаёт retry декоратор для OKX API с настройками из централизованной конфигурации.

    Использует tenacity для продвинутого логирования (before_sleep, after).
    Настройки берутся из src/config/settings.py -> RetrySettings.
    """
    from src.config.settings import get_settings

    settings = get_settings().retry

    return retry(
        stop=stop_after_attempt(settings.api_max_attempts),
        wait=wait_exponential_jitter(
            initial=settings.api_base_delay,
            max=settings.api_max_delay,
            jitter=settings.api_max_delay * 0.1 if settings.jitter else 0,
        ),
        retry=retry_if_exception_type(
            (OKXNetworkError, OKXRateLimitError, OKXIntegrationError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
    )


# Pre-configured OKX retry decorator
okx_retry = _get_okx_retry()


class OKXMetadataLoader:
    """Загрузчик метаданных с OKX API"""

    def __init__(
        self,
        max_retries: int | None = None,
        base_delay: float | None = None,
        max_delay: float | None = None,
        market: OKXMarket | None = None,
        client: OKXClient | None = None,
    ):
        # Загружаем конфигурацию
        config = get_config()

        # Используем переданные параметры или значения из конфигурации
        self.max_retries = max_retries or config.okx.max_retries
        self.base_delay = base_delay or config.okx.base_delay_seconds
        self.max_delay = max_delay or config.okx.max_delay_seconds

        # Инициализируем клиенты с конфигурацией (DI для тестирования)
        self.client = client or OKXClient()
        self.market = market or OKXMarket()

        # Rate limiting из конфигурации
        self._request_count = 0
        self._last_request_time = 0
        self._max_requests_per_second = config.okx.max_requests_per_second

        # Метрики
        self._metrics_collector = get_metrics_collector()

    @okx_retry
    async def load_instruments(
        self, inst_types: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Загружает инструменты с OKX API с retry механизмами.

        Args:
            inst_types: Список типов инструментов для загрузки

        Returns:
            Список инструментов

        Raises:
            OKXIntegrationError: При критических ошибках интеграции
            MetadataStaleError: При невозможности загрузить метаданные
        """
        if inst_types is None:
            inst_types = ["SPOT", "SWAP", "FUTURES"]

        all_instruments = []
        failed_types = []
        rate_limit_hits = 0

        # Гарантируем корректное закрытие HTTP-сессии клиента
        async with self.market:
            for inst_type in inst_types:
                try:
                    await self._rate_limit_check()
                    logger.info(f"Загружаем {inst_type} инструменты...")

                    async with measure_async_time("okx_request"):
                        instruments = await self._load_instrument_type(inst_type)

                    all_instruments.extend(instruments)
                    logger.info(
                        f"Загружено {len(instruments)} {inst_type} инструментов"
                    )

                except OKXRateLimitError as e:
                    logger.warning(f"Rate limit для {inst_type}: {e}")
                    failed_types.append(inst_type)
                    rate_limit_hits += 1
                    # Продолжаем с другими типами

                except OKXNetworkError as e:
                    logger.error(f"Сетевая ошибка для {inst_type}: {e}")
                    failed_types.append(inst_type)
                    # Продолжаем с другими типами

                except Exception as e:
                    logger.error(f"Неожиданная ошибка для {inst_type}: {e}")
                    failed_types.append(inst_type)
                    # Продолжаем с другими типами

        # Записываем метрики
        if rate_limit_hits > 0:
            self._metrics_collector.record_okx_request(0, 0, rate_limited=True)

        # Проверяем, загрузили ли мы что-то
        if not all_instruments:
            # MetadataStaleError не принимает параметр context, добавим детали в сообщение
            failed_info = f"; failed_types={failed_types}" if failed_types else ""
            raise MetadataStaleError(
                f"Не удалось загрузить ни одного инструмента{failed_info}"
            )

        # Логируем неудачные типы
        if failed_types:
            logger.warning(f"Не удалось загрузить типы: {failed_types}")

        return all_instruments

    @okx_retry
    async def _load_instrument_type(self, inst_type: str) -> list[dict[str, Any]]:
        """
        Загружает инструменты конкретного типа с retry.

        Args:
            inst_type: Тип инструмента

        Returns:
            Список инструментов

        Raises:
            OKXNetworkError: При сетевых ошибках (retryable)
            OKXRateLimitError: При превышении лимита запросов (retryable)
            OKXIntegrationError: При других ошибках интеграции (retryable)
        """
        try:
            # Всегда используем self.market напрямую (не кешируем ссылку)
            # Это позволяет подменять market в тестах через DI
            return await self.market.get_instruments(inst_type)
        except (OKXNetworkError, OKXRateLimitError, OKXIntegrationError):
            # Пробрасываем retryable исключения как есть
            raise
        except (ValueError, TypeError) as e:
            # ValueError/TypeError могут возникать из-за проблем конфигурации (например, логгера)
            # Преобразуем в OKXIntegrationError для retry
            error_msg = str(e).lower()
            if "level must be an integer" in error_msg:
                # Специальная обработка ошибки конфигурации логгера
                raise OKXIntegrationError(
                    f"Ошибка конфигурации при запросе к OKX для {inst_type}",
                    context={"instrument_type": inst_type, "original_error": str(e)},
                ) from e
            # Другие ValueError/TypeError тоже преобразуем в retryable
            raise OKXIntegrationError(
                f"Ошибка валидации при загрузке {inst_type}: {e}",
                context={"instrument_type": inst_type, "original_error": str(e)},
            ) from e
        except Exception as e:
            # Преобразуем общие исключения в специфичные
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise OKXRateLimitError(
                    retry_after=60, context={"instrument_type": inst_type}
                ) from e
            if "connection" in error_msg or "timeout" in error_msg:
                raise OKXNetworkError(
                    original_error=e, context={"instrument_type": inst_type}
                ) from e
            # Все остальные исключения преобразуем в OKXIntegrationError (retryable)
            raise OKXIntegrationError(
                f"Ошибка загрузки {inst_type}: {e}",
                context={"instrument_type": inst_type, "original_error": str(e)},
            ) from e

    async def _rate_limit_check(self):
        """
        Проверяет и соблюдает rate limiting.
        """
        current_time = asyncio.get_event_loop().time()

        # Сбрасываем счетчик если прошла секунда
        if current_time - self._last_request_time >= 1.0:
            self._request_count = 0
            self._last_request_time = current_time

        # Проверяем лимит
        if self._request_count >= self._max_requests_per_second:
            sleep_time = 1.0 - (current_time - self._last_request_time)
            if sleep_time > 0:
                logger.debug(f"Rate limit: ожидаем {sleep_time:.2f}с")
                await asyncio.sleep(sleep_time)
                self._request_count = 0
                self._last_request_time = asyncio.get_event_loop().time()

        self._request_count += 1

    def convert_to_metadata(
        self, okx_data: dict[str, Any]
    ) -> InstrumentMetadata | None:
        """
        Преобразует данные OKX в нашу модель метаданных.

        Args:
            okx_data: Данные инструмента от OKX API

        Returns:
            InstrumentMetadata или None
        """
        try:
            # Основная информация
            inst_id = okx_data.get("instId", "")
            inst_type_str = okx_data.get("instType", "")
            base_ccy = okx_data.get("baseCcy", "")
            quote_ccy = okx_data.get("quoteCcy", "")
            settle_ccy = okx_data.get("settleCcy", "")
            state = okx_data.get("state", "live")

            # Определяем тип инструмента
            inst_type = self._map_inst_type(inst_type_str)
            if not inst_type:
                logger.warning(f"Неизвестный тип инструмента: {inst_type_str}")
                return None

            # Создаем размеры тика и лота
            tick_size = self._create_tick_size(okx_data)
            lot_size = self._create_lot_size(okx_data)

            # Номинальная стоимость контракта
            contract_val = self._parse_contract_val(okx_data)

            # Комиссии
            fee_maker, fee_taker = self._parse_fees(okx_data)

            # Плечо и маржа
            max_leverage = self._parse_leverage(okx_data)
            margin_mode = self._parse_margin_mode(okx_data)
            position_mode = self._parse_position_mode(okx_data)
            maint_margin_rate, risk_limit_tier = self._parse_risk_limits(okx_data)

            # Ставка финансирования (для свопов)
            funding_rate = self._parse_funding_rate(okx_data)

            # Параметры ликвидности
            liquidity = self._parse_liquidity_params(okx_data)

            # Создаем метаданные
            return InstrumentMetadata(
                symbol=inst_id,
                inst_id=inst_id,
                inst_type=inst_type,
                base_ccy=base_ccy,
                quote_ccy=quote_ccy,
                settle_ccy=settle_ccy,
                tick_size=tick_size,
                lot_size=lot_size,
                contract_val=contract_val,
                fee_maker=fee_maker,
                fee_taker=fee_taker,
                max_leverage=max_leverage,
                margin_mode=margin_mode,
                position_mode=position_mode,
                maint_margin_rate=maint_margin_rate,
                risk_limit_tier=risk_limit_tier,
                funding_rate=funding_rate,
                liquidity=liquidity,
                state=state,
                created_time=datetime.now(),
                updated_time=datetime.now(),
            )

        except Exception as e:
            logger.error(
                f"Ошибка конвертации инструмента {okx_data.get('instId', 'unknown')}: {e}"
            )
            return None

    def _map_inst_type(self, okx_type: str) -> InstrumentType | None:
        """Преобразует тип инструмента OKX в наш enum"""
        mapping = {
            "SPOT": InstrumentType.SPOT,
            "SWAP": InstrumentType.SWAP,
            "FUTURES": InstrumentType.FUTURES,
            "OPTIONS": InstrumentType.OPTIONS,
        }
        return mapping.get(okx_type)

    def _create_tick_size(self, data: dict[str, Any]) -> TickSize | None:
        """Создает размер тика из данных OKX"""
        try:
            tick_sz = data.get("tickSz")
            if not tick_sz:
                return None

            step_size = Decimal(str(tick_sz))
            min_size = step_size  # Минимальный размер = шаг
            max_size = Decimal("999999999")  # Максимальный размер

            return TickSize(min_size=min_size, max_size=max_size, step_size=step_size)
        except Exception as e:
            logger.warning(f"Ошибка создания tick_size: {e}")
            return None

    def _create_lot_size(self, data: dict[str, Any]) -> LotSize | None:
        """Создает размер лота из данных OKX"""
        try:
            lot_sz = data.get("lotSz")
            min_sz = data.get("minSz")
            max_sz = data.get("maxSz")

            if not lot_sz:
                return None

            step_size = Decimal(str(lot_sz))
            min_qty = Decimal(str(min_sz)) if min_sz else step_size
            max_qty = Decimal(str(max_sz)) if max_sz else Decimal("999999999")

            return LotSize(min_qty=min_qty, max_qty=max_qty, step_size=step_size)
        except Exception as e:
            logger.warning(f"Ошибка создания lot_size: {e}")
            return None

    def _parse_contract_val(self, data: dict[str, Any]) -> Decimal | None:
        """Парсит номинальную стоимость контракта"""
        try:
            contract_val = data.get("ctVal")
            if contract_val:
                return Decimal(str(contract_val))
        except Exception as e:
            logger.warning(f"Ошибка парсинга contract_val: {e}")
        return None

    def _parse_margin_mode(self, data: dict[str, Any]) -> MarginMode | None:
        """Парсит режим маржи"""
        try:
            margin_mode = data.get("tdMode")
            if margin_mode == "isolated":
                return MarginMode.ISOLATED
            if margin_mode == "cross":
                return MarginMode.CROSS
        except Exception as e:
            logger.warning(f"Ошибка парсинга margin_mode: {e}")
        return None

    def _parse_margin_ratio(self, data: dict[str, Any]) -> Decimal | None:
        """Парсит коэффициент маржи"""
        try:
            margin_ratio = data.get("mgnRatio")
            if margin_ratio:
                return Decimal(str(margin_ratio))
        except Exception as e:
            logger.warning(f"Ошибка парсинга margin_ratio: {e}")
        return None

    def _parse_fees(
        self, data: dict[str, Any]
    ) -> tuple[Decimal | None, Decimal | None]:
        """Парсит комиссии мейкера и тейкера"""
        try:
            fee_maker = data.get("makerFee")
            fee_taker = data.get("takerFee")

            maker = Decimal(str(fee_maker)) if fee_maker else None
            taker = Decimal(str(fee_taker)) if fee_taker else None

            return maker, taker
        except Exception as e:
            logger.warning(f"Ошибка парсинга fees: {e}")
            return None, None

    def _parse_leverage(self, data: dict[str, Any]) -> int | None:
        """Парсит максимальное плечо"""
        try:
            max_leverage = data.get("maxLmtSz")
            if max_leverage:
                return int(max_leverage)
        except Exception as e:
            logger.warning(f"Ошибка парсинга max_leverage: {e}")
        return None

    def _parse_position_mode(self, data: dict[str, Any]) -> str | None:
        """Парсит режим позиций"""
        try:
            pos_mode = data.get("posMode")
            if pos_mode:
                return pos_mode.upper()  # LONG_SHORT, NET
        except Exception as e:
            logger.warning(f"Ошибка парсинга position_mode: {e}")
        return None

    def _parse_risk_limits(
        self, data: dict[str, Any]
    ) -> tuple[Decimal | None, int | None]:
        """Парсит лимиты риска"""
        try:
            maint_margin_rate = data.get("maintMarginRatio")
            risk_limit_tier = data.get("riskLimitTier")

            margin_rate = Decimal(str(maint_margin_rate)) if maint_margin_rate else None
            tier = int(risk_limit_tier) if risk_limit_tier else None

            return margin_rate, tier
        except Exception as e:
            logger.warning(f"Ошибка парсинга risk_limits: {e}")
            return None, None

    def _parse_funding_rate(self, data: dict[str, Any]) -> FundingRate | None:
        """Парсит ставку финансирования"""
        try:
            funding_rate = data.get("fundingRate")
            if funding_rate:
                rate = Decimal(str(funding_rate))
                # OKX финансирование каждые 8 часов
                next_funding_time = datetime.now()  # TODO: получить реальное время

                return FundingRate(
                    rate=rate,
                    next_funding_time=next_funding_time,
                    funding_interval_hours=8,
                )
        except Exception as e:
            logger.warning(f"Ошибка парсинга funding_rate: {e}")
        return None

    def _parse_liquidity_params(self, data: dict[str, Any]) -> LiquidityParams | None:
        """Парсит параметры ликвидности"""
        try:
            # Базовые параметры ликвидности
            # В реальности нужно получать эти данные из других эндпоинтов
            min_volume_24h = Decimal("1000")  # Минимум $1000 объема за 24ч
            min_trades_24h = 10  # Минимум 10 сделок за 24ч
            spread_threshold = Decimal("0.1")  # Максимальный спред 0.1%

            return LiquidityParams(
                min_volume_24h=min_volume_24h,
                min_trades_24h=min_trades_24h,
                spread_threshold=spread_threshold,
            )
        except Exception as e:
            logger.warning(f"Ошибка парсинга liquidity_params: {e}")
        return None

    async def load_funding_rates(
        self, symbols: list[str] | None = None
    ) -> dict[str, FundingRate]:
        """
        Загружает ставки финансирования для свопов.

        Args:
            symbols: Список символов для загрузки

        Returns:
            Словарь {symbol: FundingRate}
        """
        try:
            # TODO: Реализовать загрузку ставок финансирования с OKX API
            # Это требует отдельного эндпоинта /api/v5/public/funding-rate
            logger.info("Загрузка ставок финансирования пока не реализована")
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки ставок финансирования: {e}")
            return {}

    async def load_ticker_data(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Загружает данные тикеров для анализа ликвидности.

        Args:
            symbols: Список символов для загрузки

        Returns:
            Словарь с данными тикеров
        """
        try:
            # TODO: Реализовать загрузку данных тикеров с OKX API
            # Это требует эндпоинта /api/v5/market/ticker
            logger.info("Загрузка данных тикеров пока не реализована")
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки данных тикеров: {e}")
            return {}

    @okx_retry
    async def load_funding_rates_extended(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Загружает ставки финансирования для свопов (расширенная версия).

        Args:
            symbols: Список символов для загрузки (если None - все доступные)

        Returns:
            Словарь с ставками финансирования по символам
        """
        try:
            await self._rate_limit_check()

            with measure_async_time(
                "okx_api_latency", {"operation": "load_funding_rates"}
            ):
                funding_data = await self.market.get_funding_rates(symbols)

            self._metrics_collector.record_okx_request(
                "load_funding_rates", len(funding_data)
            )
            logger.info(f"✅ Загружено {len(funding_data)} ставок финансирования")

            return funding_data

        except Exception as e:
            self._metrics_collector.record_okx_error("load_funding_rates", 1)
            logger.error(f"❌ Ошибка загрузки ставок финансирования: {e}")
            raise

    @okx_retry
    async def load_mark_prices_extended(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Загружает маржевые цены для инструментов (расширенная версия).

        Args:
            symbols: Список символов для загрузки (если None - все доступные)

        Returns:
            Словарь с маржевыми ценами по символам
        """
        try:
            await self._rate_limit_check()

            with measure_async_time(
                "okx_api_latency", {"operation": "load_mark_prices"}
            ):
                mark_prices = await self.market.get_mark_prices(symbols)

            self._metrics_collector.record_okx_request(
                "load_mark_prices", len(mark_prices)
            )
            logger.info(f"✅ Загружено {len(mark_prices)} маржевых цен")

            return mark_prices

        except Exception as e:
            self._metrics_collector.record_okx_error("load_mark_prices", 1)
            logger.error(f"❌ Ошибка загрузки маржевых цен: {e}")
            raise

    @okx_retry
    async def load_tickers_extended(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Загружает тикеры с объемом и спредом (расширенная версия).

        Args:
            symbols: Список символов для загрузки (если None - все доступные)

        Returns:
            Словарь с тикерами по символам
        """
        try:
            await self._rate_limit_check()

            with measure_async_time("okx_api_latency", {"operation": "load_tickers"}):
                tickers = await self.market.get_tickers(symbols)

            self._metrics_collector.record_okx_request("load_tickers", len(tickers))
            logger.info(f"✅ Загружено {len(tickers)} тикеров")

            return tickers

        except Exception as e:
            self._metrics_collector.record_okx_error("load_tickers", 1)
            logger.error(f"❌ Ошибка загрузки тикеров: {e}")
            raise

    @okx_retry
    async def load_open_interest_extended(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Загружает открытый интерес для фьючерсов и свопов (расширенная версия).

        Args:
            symbols: Список символов для загрузки (если None - все доступные)

        Returns:
            Словарь с открытым интересом по символам
        """
        try:
            await self._rate_limit_check()

            with measure_async_time(
                "okx_api_latency", {"operation": "load_open_interest"}
            ):
                open_interest = await self.market.get_open_interest(symbols)

            self._metrics_collector.record_okx_request(
                "load_open_interest", len(open_interest)
            )
            logger.info(
                f"✅ Загружено {len(open_interest)} значений открытого интереса"
            )

            return open_interest

        except Exception as e:
            self._metrics_collector.record_okx_error("load_open_interest", 1)
            logger.error(f"❌ Ошибка загрузки открытого интереса: {e}")
            raise
