#!/usr/bin/env python3
"""
MTF Data Quality Monitoring

Мониторинг качества данных в реальном времени с алертами и метриками.
Проверяет свежесть данных, валидность, отсутствие look-ahead и аномалии.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.mtf.config.settings import DataQualityConfig, mtf_config
from src.mtf.monitoring.alerts import AlertManager


class QualityStatus(Enum):
    """Статусы качества данных"""

    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class DataQualityMetrics:
    """Метрики качества данных"""

    symbol: str
    timeframe: str
    timestamp: datetime
    status: QualityStatus

    # Свежесть данных
    data_age_minutes: float
    last_update: datetime

    # Валидность
    total_rows: int
    valid_rows: int
    nan_count: int
    valid_rate: float
    nan_rate: float

    # Аномалии
    volume_spike: float | None = None
    spread_widening: float | None = None
    price_gap: float | None = None

    # Look-ahead защита
    lookahead_guard: bool = True
    future_data_detected: bool = False

    # Дополнительная информация
    warnings: list[str] = None
    errors: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


class DataQualityMonitor:
    """Монитор качества данных"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config: DataQualityConfig = mtf_config.data_quality
        self.alert_manager = AlertManager()

        # Кеш последних проверок
        self._last_checks: dict[str, DataQualityMetrics] = {}
        self._alert_cooldown: dict[str, datetime] = {}

    async def check_symbol_quality(
        self, symbol: str, timeframe: str | None = None
    ) -> DataQualityMetrics:
        """Проверить качество данных для символа"""
        try:
            async with get_async_session() as session:
                if timeframe:
                    return await self._check_single_timeframe(
                        session, symbol, timeframe
                    )
                return await self._check_all_timeframes(session, symbol)
        except Exception as e:
            self.logger.error(f"Ошибка проверки качества для {symbol}: {e}")
            return self._create_error_metrics(symbol, timeframe, str(e))

    async def _check_single_timeframe(
        self, session: AsyncSession, symbol: str, timeframe: str
    ) -> DataQualityMetrics:
        """Проверить качество для одного таймфрейма"""
        # Получаем последние данные
        query = text(
            """
            SELECT
                timestamp,
                open, high, low, close, volume,
                created_at,
                updated_at
            FROM indicators
            WHERE symbol = :symbol AND timeframe = :timeframe
            ORDER BY timestamp DESC
            LIMIT 100
        """
        )

        result = await session.execute(
            query, {"symbol": symbol, "timeframe": timeframe}
        )
        rows = result.fetchall()

        if not rows:
            return self._create_empty_metrics(symbol, timeframe)

        # Анализируем данные
        df = pd.DataFrame(
            rows,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "created_at",
                "updated_at",
            ],
        )

        # Проверяем свежесть
        latest_ts = df["timestamp"].max()
        data_age = (datetime.utcnow() - latest_ts).total_seconds() / 60

        # Проверяем валидность
        total_rows = len(df)
        valid_rows = df[["open", "high", "low", "close"]].notna().all(axis=1).sum()
        nan_count = df[["open", "high", "low", "close"]].isna().sum().sum()
        valid_rate = valid_rows / total_rows if total_rows > 0 else 0
        nan_rate = nan_count / (total_rows * 4) if total_rows > 0 else 0

        # Проверяем look-ahead
        lookahead_guard = True
        future_data = df[df["timestamp"] > datetime.utcnow()]
        future_data_detected = len(future_data) > 0

        # Проверяем аномалии
        volume_spike = self._check_volume_spike(df)
        spread_widening = self._check_spread_widening(df)
        price_gap = self._check_price_gaps(df)

        # Определяем статус
        status = self._determine_status(
            data_age, valid_rate, nan_rate, future_data_detected
        )

        # Собираем предупреждения
        warnings = []
        errors = []

        if data_age > self.config.max_data_age_minutes:
            warnings.append(f"Данные устарели на {data_age:.1f} минут")

        if valid_rate < self.config.min_valid_rate:
            warnings.append(f"Низкая валидность: {valid_rate:.1%}")

        if nan_rate > self.config.max_nan_rate:
            warnings.append(f"Высокий уровень NaN: {nan_rate:.1%}")

        if future_data_detected:
            errors.append("Обнаружены данные из будущего (look-ahead)")
            lookahead_guard = False

        if volume_spike and volume_spike > self.config.alert_volume_spike:
            warnings.append(f"Спайк объема: {volume_spike:.1f}x")

        if spread_widening and spread_widening > self.config.alert_spread_widening:
            warnings.append(f"Расширение спреда: {spread_widening:.1f}x")

        metrics = DataQualityMetrics(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.utcnow(),
            status=status,
            data_age_minutes=data_age,
            last_update=latest_ts,
            total_rows=total_rows,
            valid_rows=valid_rows,
            nan_count=nan_count,
            valid_rate=valid_rate,
            nan_rate=nan_rate,
            volume_spike=volume_spike,
            spread_widening=spread_widening,
            price_gap=price_gap,
            lookahead_guard=lookahead_guard,
            future_data_detected=future_data_detected,
            warnings=warnings,
            errors=errors,
        )

        # Проверяем алерты
        await self._check_alerts(metrics)

        # Кешируем результат
        cache_key = f"{symbol}_{timeframe}"
        self._last_checks[cache_key] = metrics

        return metrics

    async def _check_all_timeframes(
        self, session: AsyncSession, symbol: str
    ) -> DataQualityMetrics:
        """Проверить качество для всех таймфреймов"""
        timeframes = mtf_config.get_all_timeframes()

        # Проверяем каждый таймфрейм
        tf_metrics = []
        for tf in timeframes:
            metrics = await self._check_single_timeframe(session, symbol, tf)
            tf_metrics.append(metrics)

        # Агрегируем результаты
        return self._aggregate_timeframe_metrics(symbol, tf_metrics)

    def _check_volume_spike(self, df: pd.DataFrame) -> float | None:
        """Проверить спайк объема"""
        if "volume" not in df.columns or df["volume"].isna().all():
            return None

        volume = df["volume"].dropna()
        if len(volume) < 10:
            return None

        # Вычисляем средний объем за последние 20 баров
        recent_avg = volume.tail(20).mean()
        current_volume = volume.iloc[-1]

        if recent_avg > 0:
            return current_volume / recent_avg
        return None

    def _check_spread_widening(self, df: pd.DataFrame) -> float | None:
        """Проверить расширение спреда"""
        if not all(col in df.columns for col in ["high", "low"]):
            return None

        # Вычисляем спред (high - low) / close
        df["spread"] = (df["high"] - df["low"]) / df["close"]
        spread = df["spread"].dropna()

        if len(spread) < 10:
            return None

        recent_avg = spread.tail(20).mean()
        current_spread = spread.iloc[-1]

        if recent_avg > 0:
            return current_spread / recent_avg
        return None

    def _check_price_gaps(self, df: pd.DataFrame) -> float | None:
        """Проверить ценовые гэпы"""
        if not all(col in df.columns for col in ["close", "open"]):
            return None

        # Вычисляем гэп между закрытием и следующим открытием
        df["gap"] = abs(df["close"].shift(1) - df["open"]) / df["close"].shift(1)
        gaps = df["gap"].dropna()

        if len(gaps) < 5:
            return None

        # Возвращаем максимальный гэп за последние 10 баров
        return gaps.tail(10).max()

    def _determine_status(
        self, data_age: float, valid_rate: float, nan_rate: float, future_data: bool
    ) -> QualityStatus:
        """Определить статус качества данных"""
        if future_data:
            return QualityStatus.CRITICAL

        if data_age > self.config.max_data_age_minutes * 2:
            return QualityStatus.CRITICAL

        if valid_rate < self.config.min_valid_rate * 0.8:
            return QualityStatus.CRITICAL

        if data_age > self.config.max_data_age_minutes:
            return QualityStatus.WARNING

        if valid_rate < self.config.min_valid_rate:
            return QualityStatus.WARNING

        if nan_rate > self.config.max_nan_rate:
            return QualityStatus.WARNING

        if valid_rate > 0.98 and data_age < self.config.max_data_age_minutes * 0.5:
            return QualityStatus.EXCELLENT

        return QualityStatus.GOOD

    async def _check_alerts(self, metrics: DataQualityMetrics):
        """Проверить и отправить алерты"""
        cache_key = f"{metrics.symbol}_{metrics.timeframe}"
        last_alert = self._alert_cooldown.get(cache_key)

        # Проверяем cooldown (не спамим алертами)
        if (
            last_alert and (datetime.utcnow() - last_alert).total_seconds() < 300
        ):  # 5 минут
            return

        # Отправляем алерты для критических проблем
        if metrics.status == QualityStatus.CRITICAL:
            await self.alert_manager.send_critical_alert(
                f"Критическое качество данных: {metrics.symbol} {metrics.timeframe}",
                f"Статус: {metrics.status.value}\n"
                f"Возраст данных: {metrics.data_age_minutes:.1f} мин\n"
                f"Валидность: {metrics.valid_rate:.1%}\n"
                f"Ошибки: {', '.join(metrics.errors)}",
            )
            self._alert_cooldown[cache_key] = datetime.utcnow()

        elif metrics.status == QualityStatus.WARNING and metrics.warnings:
            await self.alert_manager.send_warning_alert(
                f"Предупреждение качества данных: {metrics.symbol} {metrics.timeframe}",
                f"Предупреждения: {', '.join(metrics.warnings)}",
            )
            self._alert_cooldown[cache_key] = datetime.utcnow()

    def _create_empty_metrics(self, symbol: str, timeframe: str) -> DataQualityMetrics:
        """Создать метрики для пустых данных"""
        return DataQualityMetrics(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.utcnow(),
            status=QualityStatus.UNKNOWN,
            data_age_minutes=float("inf"),
            last_update=datetime.utcnow(),
            total_rows=0,
            valid_rows=0,
            nan_count=0,
            valid_rate=0.0,
            nan_rate=0.0,
            warnings=["Нет данных"],
            errors=[],
        )

    def _create_error_metrics(
        self, symbol: str, timeframe: str, error: str
    ) -> DataQualityMetrics:
        """Создать метрики для ошибки"""
        return DataQualityMetrics(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.utcnow(),
            status=QualityStatus.UNKNOWN,
            data_age_minutes=float("inf"),
            last_update=datetime.utcnow(),
            total_rows=0,
            valid_rows=0,
            nan_count=0,
            valid_rate=0.0,
            nan_rate=0.0,
            warnings=[],
            errors=[error],
        )

    def _aggregate_timeframe_metrics(
        self, symbol: str, tf_metrics: list[DataQualityMetrics]
    ) -> DataQualityMetrics:
        """Агрегировать метрики по таймфреймам"""
        if not tf_metrics:
            return self._create_empty_metrics(symbol, "all")

        # Берем худший статус
        worst_status = max(tf_metrics, key=lambda m: m.status.value)

        # Агрегируем числовые метрики
        avg_data_age = np.mean([m.data_age_minutes for m in tf_metrics])
        avg_valid_rate = np.mean([m.valid_rate for m in tf_metrics])
        avg_nan_rate = np.mean([m.nan_rate for m in tf_metrics])

        # Объединяем предупреждения и ошибки
        all_warnings = []
        all_errors = []
        for m in tf_metrics:
            all_warnings.extend(m.warnings)
            all_errors.extend(m.errors)

        return DataQualityMetrics(
            symbol=symbol,
            timeframe="all",
            timestamp=datetime.utcnow(),
            status=worst_status.status,
            data_age_minutes=avg_data_age,
            last_update=datetime.utcnow(),
            total_rows=sum(m.total_rows for m in tf_metrics),
            valid_rows=sum(m.valid_rows for m in tf_metrics),
            nan_count=sum(m.nan_count for m in tf_metrics),
            valid_rate=avg_valid_rate,
            nan_rate=avg_nan_rate,
            warnings=list(set(all_warnings)),
            errors=list(set(all_errors)),
        )

    async def get_quality_summary(self) -> dict[str, Any]:
        """Получить сводку качества данных"""
        # Получаем список символов
        async with get_async_session() as session:
            query = text("SELECT DISTINCT symbol FROM indicators LIMIT 50")
            result = await session.execute(query)
            symbols = [row[0] for row in result.fetchall()]

        # Проверяем качество для каждого символа
        summary = {
            "timestamp": datetime.utcnow(),
            "total_symbols": len(symbols),
            "status_counts": {status.value: 0 for status in QualityStatus},
            "symbols_by_status": {status.value: [] for status in QualityStatus},
            "overall_status": QualityStatus.UNKNOWN.value,
        }

        for symbol in symbols:
            metrics = await self.check_symbol_quality(symbol)
            summary["status_counts"][metrics.status.value] += 1
            summary["symbols_by_status"][metrics.status.value].append(symbol)

        # Определяем общий статус
        if summary["status_counts"][QualityStatus.CRITICAL.value] > 0:
            summary["overall_status"] = QualityStatus.CRITICAL.value
        elif summary["status_counts"][QualityStatus.WARNING.value] > 0:
            summary["overall_status"] = QualityStatus.WARNING.value
        elif (
            summary["status_counts"][QualityStatus.EXCELLENT.value] > len(symbols) * 0.8
        ):
            summary["overall_status"] = QualityStatus.EXCELLENT.value
        else:
            summary["overall_status"] = QualityStatus.GOOD.value

        return summary


# Глобальный экземпляр монитора
quality_monitor = DataQualityMonitor()
