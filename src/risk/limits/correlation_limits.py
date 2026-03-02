"""
Лимиты корреляции

Управление лимитами корреляции:
- Максимальная корреляция между позициями
- Контроль диверсификации портфеля
- Анализ корреляционных рисков
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import numpy as np

from ..config import get_risk_config
from ..models import RiskConfig, RiskViolation
from .models import CorrelationLimitsState

logger = logging.getLogger(__name__)


class CorrelationLimits:
    """
    Управление лимитами корреляции

    Основные функции:
    - Контроль максимальной корреляции между позициями
    - Анализ диверсификации портфеля
    - Предотвращение концентрации рисков
    - Мониторинг корреляционных зависимостей
    """

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or get_risk_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Состояние лимитов корреляции
        self.state = CorrelationLimitsState()

        # Конфигурация лимитов
        self.max_correlation = 0.7  # Максимальная корреляция между позициями
        self.correlation_window_days = 30  # Окно для расчета корреляции
        self.min_correlation_samples = 20  # Минимальное количество образцов для расчета

        # Пороги предупреждений
        self.warning_threshold = 0.6  # 60% корреляции - предупреждение
        self.critical_threshold = 0.8  # 80% корреляции - критическое предупреждение

        # Кэш для быстрого доступа
        self._correlation_cache: dict[str, dict[str, float]] = {}
        self._cache_expiry: dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=1)  # TTL кэша

    def add_correlation(self, symbol1: str, symbol2: str, correlation: float):
        """
        Добавление корреляции между символами

        Args:
            symbol1: Первый символ
            symbol2: Второй символ
            correlation: Значение корреляции (-1 до 1)
        """
        # Валидация корреляции
        if not -1.0 <= correlation <= 1.0:
            self.logger.warning(
                f"Invalid correlation value: {correlation}, must be between -1 and 1"
            )
            return

        # Добавляем в состояние
        self.state.add_correlation(symbol1, symbol2, correlation)

        # Обновляем кэш
        self._update_cache(symbol1, symbol2, correlation)

        self.logger.info(
            f"Added correlation: {symbol1} <-> {symbol2} = {correlation:.3f}"
        )

    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """
        Получение корреляции между символами

        Args:
            symbol1: Первый символ
            symbol2: Второй символ

        Returns:
            Значение корреляции (-1 до 1)
        """
        # Проверяем кэш
        cache_key = f"{symbol1}_{symbol2}"
        if cache_key in self._correlation_cache:
            if datetime.utcnow() < self._cache_expiry.get(cache_key, datetime.min):
                return self._correlation_cache[cache_key]

        # Получаем из состояния
        correlation = self.state.get_correlation(symbol1, symbol2)

        # Обновляем кэш
        self._update_cache(symbol1, symbol2, correlation)

        return correlation

    def _update_cache(self, symbol1: str, symbol2: str, correlation: float):
        """Обновление кэша корреляций"""
        cache_key = f"{symbol1}_{symbol2}"
        self._correlation_cache[cache_key] = correlation
        self._cache_expiry[cache_key] = datetime.utcnow() + self._cache_ttl

    def can_add_position(
        self,
        new_symbol: str,
        existing_symbols: list[str],
        correlation_data: dict[str, float] | None = None,
    ) -> tuple[bool, list[str]]:
        """
        Проверка возможности добавления позиции с учетом корреляции

        Args:
            new_symbol: Новый символ
            existing_symbols: Существующие символы в портфеле
            correlation_data: Данные корреляции (если есть)

        Returns:
            (разрешена_ли_позиция, список_ошибок)
        """
        errors = []

        # Если нет существующих позиций, корреляция не важна
        if not existing_symbols:
            return True, errors

        # Проверяем корреляцию с каждым существующим символом
        for existing_symbol in existing_symbols:
            correlation = self.get_correlation(new_symbol, existing_symbol)

            # Если есть данные корреляции, используем их
            if (
                correlation_data
                and f"{new_symbol}_{existing_symbol}" in correlation_data
            ):
                correlation = correlation_data[f"{new_symbol}_{existing_symbol}"]

            # Проверяем превышение лимита
            if abs(correlation) > self.max_correlation:
                errors.append(
                    f"Correlation limit exceeded: {new_symbol} <-> {existing_symbol} = {correlation:.3f} > {self.max_correlation}"
                )

            # Проверяем критические пороги
            elif abs(correlation) > self.critical_threshold:
                errors.append(
                    f"Critical correlation threshold: {new_symbol} <-> {existing_symbol} = {correlation:.3f} > {self.critical_threshold}"
                )

        return len(errors) == 0, errors

    def calculate_portfolio_correlation(self, symbols: list[str]) -> dict[str, Any]:
        """
        Расчет корреляции портфеля

        Args:
            symbols: Список символов в портфеле

        Returns:
            Словарь с метриками корреляции портфеля
        """
        if len(symbols) < 2:
            return {
                "avg_correlation": 0.0,
                "max_correlation": 0.0,
                "min_correlation": 0.0,
                "correlation_matrix": {},
                "diversification_score": 1.0,
            }

        correlations = []
        correlation_matrix = {}

        # Рассчитываем корреляции между всеми парами
        for i, symbol1 in enumerate(symbols):
            correlation_matrix[symbol1] = {}
            for j, symbol2 in enumerate(symbols):
                if i != j:
                    correlation = self.get_correlation(symbol1, symbol2)
                    correlation_matrix[symbol1][symbol2] = correlation
                    correlations.append(abs(correlation))

        # Статистика
        avg_correlation = np.mean(correlations) if correlations else 0.0
        max_correlation = np.max(correlations) if correlations else 0.0
        min_correlation = np.min(correlations) if correlations else 0.0

        # Скор диверсификации (чем меньше корреляция, тем лучше)
        diversification_score = 1.0 - avg_correlation

        return {
            "avg_correlation": float(avg_correlation),
            "max_correlation": float(max_correlation),
            "min_correlation": float(min_correlation),
            "correlation_matrix": correlation_matrix,
            "diversification_score": float(diversification_score),
            "symbols_count": len(symbols),
        }

    def get_correlation_violations(self, symbols: list[str]) -> list[RiskViolation]:
        """
        Получение нарушений лимитов корреляции

        Args:
            symbols: Список символов в портфеле

        Returns:
            Список нарушений
        """
        violations = []

        # Проверяем корреляцию между всеми парами
        for i, symbol1 in enumerate(symbols):
            for _j, symbol2 in enumerate(symbols[i + 1 :], i + 1):
                correlation = self.get_correlation(symbol1, symbol2)

                if abs(correlation) > self.max_correlation:
                    violation = RiskViolation(
                        limit_id=None,
                        violation_type="correlation_limit_exceeded",
                        violation_value=Decimal(str(abs(correlation))),
                        limit_value=Decimal(str(self.max_correlation)),
                        context={
                            "symbol1": symbol1,
                            "symbol2": symbol2,
                            "correlation": correlation,
                            "timestamp": datetime.utcnow(),
                            "portfolio_symbols": symbols,
                        },
                    )
                    violations.append(violation)
                    self.logger.warning(
                        f"Correlation limit exceeded: {symbol1} <-> {symbol2} = {correlation:.3f}"
                    )

        return violations

    def get_status(self) -> dict[str, Any]:
        """Получение статуса лимитов корреляции"""
        return {
            "max_correlation": self.max_correlation,
            "correlation_window_days": self.correlation_window_days,
            "min_correlation_samples": self.min_correlation_samples,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "cached_correlations": len(self._correlation_cache),
            "total_correlations": len(self.state.symbol_correlations),
        }

    def update_limits(
        self,
        max_correlation: float | None = None,
        correlation_window_days: int | None = None,
        min_correlation_samples: int | None = None,
        warning_threshold: float | None = None,
        critical_threshold: float | None = None,
    ):
        """Обновление лимитов корреляции"""
        if max_correlation is not None:
            self.max_correlation = max_correlation
        if correlation_window_days is not None:
            self.correlation_window_days = correlation_window_days
        if min_correlation_samples is not None:
            self.min_correlation_samples = min_correlation_samples
        if warning_threshold is not None:
            self.warning_threshold = warning_threshold
        if critical_threshold is not None:
            self.critical_threshold = critical_threshold

        self.logger.info(
            f"Updated correlation limits: max_correlation={self.max_correlation}, window_days={self.correlation_window_days}"
        )

    def get_correlation_analysis(self, symbols: list[str]) -> dict[str, Any]:
        """
        Получение анализа корреляции для портфеля

        Args:
            symbols: Список символов в портфеле

        Returns:
            Словарь с анализом корреляции
        """
        if len(symbols) < 2:
            return {
                "analysis": "insufficient_symbols",
                "recommendation": "add_more_symbols_for_diversification",
            }

        # Рассчитываем метрики портфеля
        portfolio_metrics = self.calculate_portfolio_correlation(symbols)

        # Анализ рисков
        risk_analysis = self._analyze_correlation_risks(symbols)

        # Рекомендации
        recommendations = self._generate_recommendations(
            portfolio_metrics, risk_analysis
        )

        return {
            "portfolio_metrics": portfolio_metrics,
            "risk_analysis": risk_analysis,
            "recommendations": recommendations,
            "violations": self.get_correlation_violations(symbols),
        }

    def _analyze_correlation_risks(self, symbols: list[str]) -> dict[str, Any]:
        """Анализ корреляционных рисков"""
        high_correlations = []
        medium_correlations = []
        low_correlations = []

        for i, symbol1 in enumerate(symbols):
            for _j, symbol2 in enumerate(symbols[i + 1 :], i + 1):
                correlation = self.get_correlation(symbol1, symbol2)
                abs_correlation = abs(correlation)

                if abs_correlation > self.critical_threshold:
                    high_correlations.append((symbol1, symbol2, correlation))
                elif abs_correlation > self.warning_threshold:
                    medium_correlations.append((symbol1, symbol2, correlation))
                else:
                    low_correlations.append((symbol1, symbol2, correlation))

        return {
            "high_correlations": high_correlations,
            "medium_correlations": medium_correlations,
            "low_correlations": low_correlations,
            "risk_level": self._calculate_risk_level(
                high_correlations, medium_correlations
            ),
        }

    def _calculate_risk_level(
        self, high_correlations: list, medium_correlations: list
    ) -> str:
        """Расчет уровня риска"""
        if len(high_correlations) > 0:
            return "high"
        if len(medium_correlations) > 2:
            return "medium"
        return "low"

    def _generate_recommendations(
        self, portfolio_metrics: dict[str, Any], risk_analysis: dict[str, Any]
    ) -> list[str]:
        """Генерация рекомендаций по корреляции"""
        recommendations = []

        # Рекомендации на основе метрик портфеля
        if portfolio_metrics["diversification_score"] < 0.5:
            recommendations.append(
                "Portfolio diversification is low, consider adding uncorrelated assets"
            )

        if portfolio_metrics["max_correlation"] > self.critical_threshold:
            recommendations.append(
                "High correlation detected, consider reducing position sizes"
            )

        # Рекомендации на основе анализа рисков
        if risk_analysis["risk_level"] == "high":
            recommendations.append(
                "High correlation risk detected, immediate action required"
            )
        elif risk_analysis["risk_level"] == "medium":
            recommendations.append("Medium correlation risk, monitor closely")

        return recommendations

    def clear_cache(self):
        """Очистка кэша корреляций"""
        self._correlation_cache.clear()
        self._cache_expiry.clear()
        self.logger.info("Cleared correlation cache")

    def get_correlation_summary(self) -> dict[str, Any]:
        """Получение сводки по корреляциям"""
        return {
            "total_correlations": len(self.state.symbol_correlations),
            "cached_correlations": len(self._correlation_cache),
            "max_correlation": self.max_correlation,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "correlation_window_days": self.correlation_window_days,
        }
