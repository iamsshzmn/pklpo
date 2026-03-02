"""
Адаптер для Market Meta Module
"""

import asyncio
from datetime import datetime
from typing import Any

from .config import IntegrationConfig
from .models import (
    ConnectionStatus,
    DataQualityMetrics,
    DataSource,
    IntegrationResult,
    MarketMetaData,
)


class MarketMetaAdapter:
    """Адаптер для интеграции с market_meta модулем"""

    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.market_meta_settings = config.market_meta_settings
        self.timeout_settings = config.timeout_settings
        self.retry_settings = config.retry_settings
        self.data_quality_settings = config.data_quality_settings

    async def get_market_metadata(self, symbol: str) -> IntegrationResult:
        """
        Получение рыночной метаинформации

        Args:
            symbol: Символ

        Returns:
            IntegrationResult: Результат интеграции
        """
        start_time = datetime.now()

        try:
            # Проверка доступности модуля
            if not self.market_meta_settings.get("enabled", True):
                return self._create_error_result(
                    "Market meta module disabled",
                    start_time,
                    ["Market meta module is disabled in configuration"],
                )

            # Получение данных с таймаутом
            timeout = self.timeout_settings.get("market_meta_timeout", 10.0)
            market_data = await asyncio.wait_for(
                self._get_market_meta_with_retry(symbol), timeout=timeout
            )

            # Валидация данных
            quality_metrics = self._validate_market_meta_data(market_data, symbol)

            # Создание результата
            duration = (datetime.now() - start_time).total_seconds()

            return IntegrationResult(
                source=DataSource.MARKET_META,
                status=ConnectionStatus.CONNECTED,
                data=MarketMetaData(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    source=DataSource.MARKET_META,
                    order_validation=market_data.get("order_validation", {}),
                    risk_limits=market_data.get("risk_limits", {}),
                    liquidity_info=market_data.get("liquidity_info", {}),
                    quality_score=quality_metrics.overall_score,
                    metadata={
                        "quality_metrics": quality_metrics,
                        "data_freshness": market_data.get("data_freshness", 0),
                    },
                ),
                timestamp=datetime.now(),
                duration_seconds=duration,
                errors=[],
                warnings=quality_metrics.issues,
                metadata={
                    "symbol": symbol,
                    "quality_score": quality_metrics.overall_score,
                    "data_freshness": market_data.get("data_freshness", 0),
                },
            )

        except TimeoutError:
            return self._create_error_result(
                "Market meta timeout",
                start_time,
                [f"Market meta request timed out after {timeout} seconds"],
            )

        except Exception as e:
            return self._create_error_result(
                f"Market meta error: {e!s}", start_time, [str(e)]
            )

    async def _get_market_meta_with_retry(self, symbol: str) -> dict[str, Any]:
        """Получение метаданных с повторными попытками"""
        max_retries = self.retry_settings.get("max_retries", 3)
        retry_delay = self.retry_settings.get("retry_delay", 1.0)
        backoff_factor = self.retry_settings.get("backoff_factor", 2.0)

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                # TODO: Реальная интеграция с market_meta модулем
                # from src.market_meta.api import get_market_metadata
                # return get_market_metadata(symbol)

                # Заглушка для тестирования
                await asyncio.sleep(0.05)  # Имитация работы

                # Создание мок данных
                return {
                    "order_validation": {
                        "min_order_size": 0.001,
                        "max_order_size": 1000.0,
                        "tick_size": 0.01,
                        "step_size": 0.001,
                        "min_notional": 5.0,
                        "max_notional": 1000000.0,
                    },
                    "risk_limits": {
                        "max_position_size": 0.02,  # 2%
                        "daily_loss_limit": 0.05,  # 5%
                        "max_leverage": 3.0,
                        "margin_requirement": 0.1,
                    },
                    "liquidity_info": {
                        "bid_ask_spread": 0.0001,
                        "volume_24h": 1000000.0,
                        "liquidity_score": 0.8,
                        "market_depth": 0.7,
                    },
                    "data_freshness": 1.0,  # 1 минута назад
                }

            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * (backoff_factor**attempt))
                else:
                    raise last_exception from last_exception

        raise last_exception from None

    def _validate_market_meta_data(
        self, market_data: dict[str, Any], symbol: str
    ) -> DataQualityMetrics:
        """Валидация рыночных метаданных"""
        issues = []
        recommendations = []

        # Проверка полноты данных
        completeness = self._calculate_meta_completeness(market_data)
        if completeness < 0.9:
            issues.append(f"Low metadata completeness: {completeness:.1%}")
            recommendations.append("Check market meta data source")

        # Проверка актуальности данных
        timeliness = self._calculate_meta_timeliness(market_data)
        if timeliness < 0.8:
            issues.append(f"Stale market metadata: {timeliness:.1%}")
            recommendations.append("Update market meta data")

        # Проверка согласованности
        consistency = self._calculate_meta_consistency(market_data)
        if consistency < 0.9:
            issues.append(f"Low metadata consistency: {consistency:.1%}")
            recommendations.append("Validate market meta logic")

        # Проверка точности (заглушка)
        accuracy = 1.0

        # Расчет общего score
        overall_score = (completeness + accuracy + timeliness + consistency) / 4.0

        return DataQualityMetrics(
            source=DataSource.MARKET_META,
            symbol=symbol,
            timeframe="N/A",
            completeness=completeness,
            accuracy=accuracy,
            timeliness=timeliness,
            consistency=consistency,
            overall_score=overall_score,
            issues=issues,
            recommendations=recommendations,
            timestamp=datetime.now(),
        )

    def _calculate_meta_completeness(self, data: dict[str, Any]) -> float:
        """Расчет полноты метаданных"""
        required_fields = ["order_validation", "risk_limits", "liquidity_info"]

        present_fields = sum(1 for field in required_fields if data.get(field))
        return present_fields / len(required_fields)

    def _calculate_meta_timeliness(self, data: dict[str, Any]) -> float:
        """Расчет актуальности метаданных"""
        data_freshness = data.get("data_freshness", 0)

        # Данные свежие если получены менее 5 минут назад
        if data_freshness <= 5:
            return 1.0
        if data_freshness <= 15:
            return 0.8
        if data_freshness <= 30:
            return 0.6
        return 0.3

    def _calculate_meta_consistency(self, data: dict[str, Any]) -> float:
        """Расчет согласованности метаданных"""
        consistency_score = 1.0

        # Проверка логической согласованности
        if "order_validation" in data and "risk_limits" in data:
            order_validation = data["order_validation"]
            risk_limits = data["risk_limits"]

            # Проверка: min_order_size < max_order_size
            if order_validation.get("min_order_size", 0) >= order_validation.get(
                "max_order_size", 0
            ):
                consistency_score *= 0.5

            # Проверка: max_position_size > 0
            if risk_limits.get("max_position_size", 0) <= 0:
                consistency_score *= 0.5

        return consistency_score

    def _create_error_result(
        self, message: str, start_time: datetime, errors: list[str]
    ) -> IntegrationResult:
        """Создание результата с ошибкой"""
        duration = (datetime.now() - start_time).total_seconds()

        return IntegrationResult(
            source=DataSource.MARKET_META,
            status=ConnectionStatus.ERROR,
            data=None,
            timestamp=datetime.now(),
            duration_seconds=duration,
            errors=errors,
            warnings=[],
            metadata={"error_message": message},
        )

    async def check_connection_health(self) -> ConnectionStatus:
        """Проверка состояния подключения к market_meta модулю"""
        try:
            # TODO: Реальная проверка подключения
            # from src.market_meta.api import get_market_metadata
            # get_market_metadata("BTC-USDT")

            # Заглушка для тестирования
            await asyncio.sleep(0.01)
            return ConnectionStatus.CONNECTED

        except Exception:
            return ConnectionStatus.ERROR
