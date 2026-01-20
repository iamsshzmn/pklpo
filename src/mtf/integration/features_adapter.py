"""
Адаптер для Features Module
"""

import asyncio
from datetime import datetime

import pandas as pd

from .config import IntegrationConfig
from .models import (
    ConnectionStatus,
    DataQualityMetrics,
    DataSource,
    FeaturesData,
    IntegrationResult,
)


class FeaturesAdapter:
    """Адаптер для интеграции с features модулем"""

    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.features_settings = config.features_settings
        self.timeout_settings = config.timeout_settings
        self.retry_settings = config.retry_settings
        self.data_quality_settings = config.data_quality_settings

    async def get_features_data(
        self,
        symbol: str,
        timeframe: str,
        ohlcv_data: pd.DataFrame,
        specs: list[str] | None = None,
    ) -> IntegrationResult:
        """
        Получение данных индикаторов из features модуля

        Args:
            symbol: Символ
            timeframe: Таймфрейм
            ohlcv_data: OHLCV данные
            specs: Список спецификаций индикаторов

        Returns:
            IntegrationResult: Результат интеграции
        """
        start_time = datetime.now()

        try:
            # Проверка доступности модуля
            if not self.features_settings.get("enabled", True):
                return self._create_error_result(
                    "Features module disabled",
                    start_time,
                    ["Features module is disabled in configuration"],
                )

            # Подготовка спецификаций
            if specs is None:
                specs = self.features_settings.get("default_specs", [])

            # Получение данных с таймаутом
            timeout = self.timeout_settings.get("features_timeout", 30.0)
            features_data = await asyncio.wait_for(
                self._compute_features_with_retry(ohlcv_data, specs), timeout=timeout
            )

            # Валидация данных
            quality_metrics = self._validate_features_data(
                features_data, symbol, timeframe
            )

            # Создание результата
            duration = (datetime.now() - start_time).total_seconds()

            return IntegrationResult(
                source=DataSource.FEATURES,
                status=ConnectionStatus.CONNECTED,
                data=FeaturesData(
                    symbol=symbol,
                    timeframe=timeframe,
                    features=features_data,
                    timestamp=datetime.now(),
                    source=DataSource.FEATURES,
                    specs_used=specs,
                    quality_score=quality_metrics.overall_score,
                    metadata={
                        "quality_metrics": quality_metrics,
                        "specs_count": len(specs),
                        "data_points": len(features_data),
                    },
                ),
                timestamp=datetime.now(),
                duration_seconds=duration,
                errors=[],
                warnings=quality_metrics.issues,
                metadata={
                    "specs_used": specs,
                    "data_points": len(features_data),
                    "quality_score": quality_metrics.overall_score,
                },
            )

        except TimeoutError:
            return self._create_error_result(
                "Features computation timeout",
                start_time,
                [f"Features computation timed out after {timeout} seconds"],
            )

        except Exception as e:
            return self._create_error_result(
                f"Features computation error: {e!s}", start_time, [str(e)]
            )

    async def _compute_features_with_retry(
        self, ohlcv_data: pd.DataFrame, specs: list[str]
    ) -> pd.DataFrame:
        """Вычисление индикаторов с повторными попытками"""
        max_retries = self.retry_settings.get("max_retries", 3)
        retry_delay = self.retry_settings.get("retry_delay", 1.0)
        backoff_factor = self.retry_settings.get("backoff_factor", 2.0)

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                # TODO: Реальная интеграция с features модулем
                # from src.features.core import compute_features
                # return compute_features(ohlcv_data, specs=specs, volatility_normalize=True)

                # Заглушка для тестирования
                await asyncio.sleep(0.1)  # Имитация работы

                # Создание мок данных
                mock_features = pd.DataFrame(
                    {
                        "ema_21": [50000.0] * len(ohlcv_data),
                        "ema_55": [49500.0] * len(ohlcv_data),
                        "adx_14": [25.0] * len(ohlcv_data),
                        "atr_14": [500.0] * len(ohlcv_data),
                        "sma_50": [49800.0] * len(ohlcv_data),
                        "sma_200": [48000.0] * len(ohlcv_data),
                        "rsi_14": [55.0] * len(ohlcv_data),
                        "macd": [100.0] * len(ohlcv_data),
                        "macd_signal": [80.0] * len(ohlcv_data),
                        "bb_upper": [51000.0] * len(ohlcv_data),
                        "bb_lower": [49000.0] * len(ohlcv_data),
                        "stoch_k": [60.0] * len(ohlcv_data),
                        "stoch_d": [55.0] * len(ohlcv_data),
                        "volume": [1000000.0] * len(ohlcv_data),
                        "obv": [500000.0] * len(ohlcv_data),
                        "cmf": [0.1] * len(ohlcv_data),
                    }
                )

                # Фильтрация по запрошенным спецификациям
                available_specs = [
                    spec for spec in specs if spec in mock_features.columns
                ]
                return (
                    mock_features[available_specs] if available_specs else mock_features
                )

            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * (backoff_factor**attempt))
                else:
                    raise last_exception from last_exception

        raise last_exception from None

    def _validate_features_data(
        self, features_data: pd.DataFrame, symbol: str, timeframe: str
    ) -> DataQualityMetrics:
        """Валидация данных индикаторов"""
        issues = []
        recommendations = []

        # Проверка полноты данных
        completeness = self._calculate_completeness(features_data)
        if completeness < self.data_quality_settings.get("min_completeness", 0.8):
            issues.append(f"Low data completeness: {completeness:.1%}")
            recommendations.append("Check data source and timeframes")

        # Проверка на аномальные значения
        accuracy = self._calculate_accuracy(features_data)
        if accuracy < 0.9:
            issues.append(f"Low data accuracy: {accuracy:.1%}")
            recommendations.append("Review outlier detection thresholds")

        # Проверка своевременности
        timeliness = 1.0  # Заглушка - в реальной реализации проверять возраст данных

        # Проверка согласованности
        consistency = self._calculate_consistency(features_data)
        if consistency < 0.8:
            issues.append(f"Low data consistency: {consistency:.1%}")
            recommendations.append("Check for data conflicts")

        # Расчет общего score
        overall_score = (completeness + accuracy + timeliness + consistency) / 4.0

        return DataQualityMetrics(
            source=DataSource.FEATURES,
            symbol=symbol,
            timeframe=timeframe,
            completeness=completeness,
            accuracy=accuracy,
            timeliness=timeliness,
            consistency=consistency,
            overall_score=overall_score,
            issues=issues,
            recommendations=recommendations,
            timestamp=datetime.now(),
        )

    def _calculate_completeness(self, data: pd.DataFrame) -> float:
        """Расчет полноты данных"""
        if data.empty:
            return 0.0

        total_cells = data.size
        missing_cells = data.isna().sum().sum()

        return 1.0 - (missing_cells / total_cells)

    def _calculate_accuracy(self, data: pd.DataFrame) -> float:
        """Расчет точности данных"""
        if data.empty:
            return 0.0

        # Проверка на аномальные значения (упрощенная)
        outlier_threshold = self.data_quality_settings.get("outlier_threshold", 3.0)
        outliers = 0

        for column in data.columns:
            if data[column].dtype in ["float64", "int64"]:
                mean = data[column].mean()
                std = data[column].std()
                if std > 0:
                    outliers += (
                        (data[column] - mean).abs() > outlier_threshold * std
                    ).sum()

        total_values = data.size
        accuracy = 1.0 - (outliers / total_values)

        return max(0.0, min(1.0, accuracy))

    def _calculate_consistency(self, data: pd.DataFrame) -> float:
        """Расчет согласованности данных"""
        if data.empty or len(data) < 2:
            return 1.0

        # Проверка логической согласованности между индикаторами
        consistency_score = 1.0

        # Пример: проверка согласованности EMA
        if "ema_21" in data.columns and "ema_55" in data.columns:
            # EMA21 должна быть ближе к цене чем EMA55
            ema_diff = (data["ema_21"] - data["ema_55"]).abs()
            if ema_diff.max() > ema_diff.mean() * 5:  # Простая проверка
                consistency_score *= 0.8

        return consistency_score

    def _create_error_result(
        self, message: str, start_time: datetime, errors: list[str]
    ) -> IntegrationResult:
        """Создание результата с ошибкой"""
        duration = (datetime.now() - start_time).total_seconds()

        return IntegrationResult(
            source=DataSource.FEATURES,
            status=ConnectionStatus.ERROR,
            data=None,
            timestamp=datetime.now(),
            duration_seconds=duration,
            errors=errors,
            warnings=[],
            metadata={"error_message": message},
        )

    async def check_connection_health(self) -> ConnectionStatus:
        """Проверка состояния подключения к features модулю"""
        try:
            # TODO: Реальная проверка подключения
            # from src.features.core import compute_features
            # test_data = pd.DataFrame({'close': [100.0]})
            # compute_features(test_data, specs=['close'])

            # Заглушка для тестирования
            await asyncio.sleep(0.01)
            return ConnectionStatus.CONNECTED

        except Exception:
            return ConnectionStatus.ERROR
