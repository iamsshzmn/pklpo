"""
SignalValidator - валидация торговых сигналов

Основные функции:
- Валидация рыночных условий
- Проверка лимитов риска
- Контроль качества данных
- Интеграция с market_meta
"""

import logging
from datetime import datetime
from typing import Any

from src.market_meta.api import get_instrument_info
from src.signals.models import Decision, SignalCandidate, SignalConfig, ValidationResult

logger = logging.getLogger(__name__)


class SignalValidator:
    """
    Валидатор торговых сигналов

    Проверяет сигналы на соответствие:
    - Рыночным условиям
    - Лимитам риска
    - Качеству данных
    - Биржевым ограничениям
    """

    def __init__(self, config: SignalConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate_candidate(self, candidate: SignalCandidate) -> ValidationResult:
        """
        Валидация кандидата на торговый сигнал

        Args:
            candidate: Кандидат на валидацию

        Returns:
            ValidationResult с результатами валидации
        """
        violations = []
        warnings = []
        market_conditions = {}
        risk_assessment = {}
        data_quality = {}

        decision = candidate.decision

        try:
            # 1. Валидация базовых параметров
            self._validate_basic_parameters(decision, violations, warnings)

            # 2. Валидация рыночных условий
            self._validate_market_conditions(
                decision, violations, warnings, market_conditions
            )

            # 3. Валидация лимитов риска
            self._validate_risk_limits(decision, violations, warnings, risk_assessment)

            # 4. Валидация качества данных
            self._validate_data_quality(decision, violations, warnings, data_quality)

            # 5. Валидация биржевых ограничений
            self._validate_exchange_limits(decision, violations, warnings)

            # 6. Валидация временных ограничений
            self._validate_temporal_limits(decision, violations, warnings)

            # Определяем общий результат
            is_valid = len(violations) == 0

            result = ValidationResult(
                is_valid=is_valid,
                violations=violations,
                warnings=warnings,
                market_conditions=market_conditions,
                risk_assessment=risk_assessment,
                data_quality=data_quality,
                validated_at=datetime.utcnow(),
            )

            self.logger.info(
                f"Validation result for symbol {decision.symbol_id}: "
                f"valid={is_valid}, violations={len(violations)}, warnings={len(warnings)}"
            )

            return result

        except Exception as e:
            self.logger.error(f"Validation failed for symbol {decision.symbol_id}: {e}")
            return ValidationResult(
                is_valid=False,
                violations=[f"Validation error: {e!s}"],
                warnings=warnings,
                market_conditions=market_conditions,
                risk_assessment=risk_assessment,
                data_quality=data_quality,
                validated_at=datetime.utcnow(),
            )

    def _validate_basic_parameters(
        self, decision: Decision, violations: list[str], warnings: list[str]
    ):
        """Валидация базовых параметров решения"""

        # Проверка confidence
        if decision.confidence < self.config.min_confidence:
            violations.append(
                f"Confidence {decision.confidence:.3f} below minimum {self.config.min_confidence}"
            )

        # Проверка expected_r
        if decision.expected_r < self.config.min_expected_r:
            violations.append(
                f"Expected return {decision.expected_r:.3f} below minimum {self.config.min_expected_r}"
            )

        # Проверка TTL
        if decision.ttl_sec > self.config.max_ttl_sec:
            violations.append(
                f"TTL {decision.ttl_sec} exceeds maximum {self.config.max_ttl_sec}"
            )

        # Проверка цен
        if decision.entry <= 0:
            violations.append(f"Invalid entry price: {decision.entry}")

        if decision.stop <= 0:
            violations.append(f"Invalid stop price: {decision.stop}")

        if decision.take <= 0:
            violations.append(f"Invalid take price: {decision.take}")

        # Проверка логики цен
        if decision.side.value == "long":
            if decision.stop >= decision.entry:
                violations.append("Long position: stop must be < entry")
            if decision.take <= decision.entry:
                violations.append("Long position: take must be > entry")
        elif decision.side.value == "short":
            if decision.stop <= decision.entry:
                violations.append("Short position: stop must be > entry")
            if decision.take >= decision.entry:
                violations.append("Short position: take must be < entry")

    def _validate_market_conditions(
        self,
        decision: Decision,
        violations: list[str],
        warnings: list[str],
        market_conditions: dict[str, Any],
    ):
        """Валидация рыночных условий"""

        try:
            # Получаем метаданные инструмента
            instrument_info = get_instrument_info(
                f"SYMBOL_{decision.symbol_id}"
            )  # TODO: получить реальный символ
            if not instrument_info:
                violations.append(f"No instrument info for symbol {decision.symbol_id}")
                return

            market_conditions["instrument_info"] = instrument_info

            # Проверяем ликвидность
            if "liquidity_usdt" in instrument_info:
                if instrument_info["liquidity_usdt"] < self.config.min_liquidity_usdt:
                    violations.append(
                        f"Insufficient liquidity: {instrument_info['liquidity_usdt']} < {self.config.min_liquidity_usdt}"
                    )
                market_conditions["liquidity_usdt"] = instrument_info["liquidity_usdt"]

            # Проверяем спред
            if "spread_bps" in instrument_info:
                if instrument_info["spread_bps"] > self.config.max_spread_bps:
                    violations.append(
                        f"Spread too high: {instrument_info['spread_bps']} > {self.config.max_spread_bps}"
                    )
                market_conditions["spread_bps"] = instrument_info["spread_bps"]

            # Проверяем объем
            if "volume_24h_usdt" in instrument_info:
                if instrument_info["volume_24h_usdt"] < self.config.min_volume_24h_usdt:
                    violations.append(
                        f"Insufficient volume: {instrument_info['volume_24h_usdt']} < {self.config.min_volume_24h_usdt}"
                    )
                market_conditions["volume_24h_usdt"] = instrument_info[
                    "volume_24h_usdt"
                ]

            # Проверяем тик-размер
            if "tick_size" in instrument_info:
                # Проверяем, что цены соответствуют тик-размеру
                if not self._is_price_valid(
                    decision.entry, instrument_info["tick_size"]
                ):
                    violations.append(
                        f"Entry price {decision.entry} not aligned with tick size {instrument_info['tick_size']}"
                    )

                if not self._is_price_valid(
                    decision.stop, instrument_info["tick_size"]
                ):
                    violations.append(
                        f"Stop price {decision.stop} not aligned with tick size {instrument_info['tick_size']}"
                    )

                if not self._is_price_valid(
                    decision.take, instrument_info["tick_size"]
                ):
                    violations.append(
                        f"Take price {decision.take} not aligned with tick size {instrument_info['tick_size']}"
                    )

                market_conditions["tick_size"] = instrument_info["tick_size"]

            # Проверяем минимальный номинал
            if "min_notional" in instrument_info:
                # Примерный расчет номинала (нужно будет уточнить с учетом размера позиции)
                estimated_notional = decision.entry * 100  # Предполагаем размер позиции
                if estimated_notional < instrument_info["min_notional"]:
                    warnings.append(
                        f"Estimated notional {estimated_notional} below minimum {instrument_info['min_notional']}"
                    )
                market_conditions["min_notional"] = instrument_info["min_notional"]

        except Exception as e:
            violations.append(f"Market conditions validation failed: {e!s}")

    def _validate_risk_limits(
        self,
        decision: Decision,
        violations: list[str],
        warnings: list[str],
        risk_assessment: dict[str, Any],
    ):
        """Валидация лимитов риска"""

        # Рассчитываем риск на сделку
        risk_per_trade = abs(decision.entry - decision.stop) / decision.entry
        risk_assessment["risk_per_trade"] = risk_per_trade

        # Проверяем максимальный риск на сделку (например, 2%)
        max_risk_per_trade = 0.02
        if risk_per_trade > max_risk_per_trade:
            violations.append(
                f"Risk per trade {risk_per_trade:.3f} exceeds maximum {max_risk_per_trade}"
            )

        # Рассчитываем соотношение риск/доходность
        reward = abs(decision.take - decision.entry)
        risk_reward_ratio = reward / abs(decision.entry - decision.stop)
        risk_assessment["risk_reward_ratio"] = risk_reward_ratio

        # Проверяем минимальное соотношение риск/доходность
        min_risk_reward_ratio = 1.5
        if risk_reward_ratio < min_risk_reward_ratio:
            violations.append(
                f"Risk/reward ratio {risk_reward_ratio:.3f} below minimum {min_risk_reward_ratio}"
            )

        # Проверяем максимальное количество одновременных сигналов
        # (это будет проверяться на уровне системы)
        risk_assessment["max_concurrent_signals"] = self.config.max_concurrent_signals

        # Проверяем дневной лимит сигналов
        risk_assessment["max_daily_signals"] = self.config.max_daily_signals

    def _validate_data_quality(
        self,
        decision: Decision,
        violations: list[str],
        warnings: list[str],
        data_quality: dict[str, Any],
    ):
        """Валидация качества данных"""

        # Проверяем возраст данных
        data_age = (datetime.utcnow() - decision.ts.to_pydatetime()).total_seconds()
        data_quality["data_age_sec"] = data_age

        if data_age > self.config.max_data_age_sec:
            violations.append(
                f"Data age {data_age:.0f}s exceeds maximum {self.config.max_data_age_sec}s"
            )

        # Проверяем качество данных (примерная оценка)
        data_quality_score = 1.0

        # Снижаем оценку за старые данные
        if data_age > 60:  # Больше минуты
            data_quality_score *= 0.9

        if data_age > 300:  # Больше 5 минут
            data_quality_score *= 0.8

        data_quality["data_quality_score"] = data_quality_score

        if data_quality_score < self.config.min_data_quality_score:
            violations.append(
                f"Data quality score {data_quality_score:.3f} below minimum {self.config.min_data_quality_score}"
            )

        # Проверяем наличие rationale
        if not decision.rationale or len(decision.rationale) == 0:
            warnings.append("No rationale provided for decision")

        # Проверяем версию алгоритма
        if not decision.algo_version:
            warnings.append("No algorithm version specified")

        # Проверяем хеш параметров
        if not decision.params_hash:
            warnings.append("No parameters hash specified")

    def _validate_exchange_limits(
        self, decision: Decision, violations: list[str], warnings: list[str]
    ):
        """Валидация биржевых ограничений"""

        try:
            # Получаем метаданные инструмента для валидации
            instrument_info = get_instrument_info(
                f"SYMBOL_{decision.symbol_id}"
            )  # TODO: получить реальный символ
            if not instrument_info:
                violations.append(f"No instrument info for symbol {decision.symbol_id}")
                return

            # Создаем валидаторы (пока пропускаем, так как нужны MarketMetadata объекты)
            # market_validator = MarketValidator(market_meta)
            # position_validator = PositionValidator(market_meta)

            # TODO: Реализовать валидацию через MarketValidator когда будут MarketMetadata объекты
            # Пока просто проверяем базовые условия
            if decision.entry <= 0:
                violations.append(f"Invalid entry price: {decision.entry}")

            if decision.stop <= 0:
                violations.append(f"Invalid stop price: {decision.stop}")

            if decision.take <= 0:
                violations.append(f"Invalid take price: {decision.take}")

        except Exception as e:
            violations.append(f"Exchange limits validation failed: {e!s}")

    def _validate_temporal_limits(
        self, decision: Decision, violations: list[str], warnings: list[str]
    ):
        """Валидация временных ограничений"""

        # Проверяем cooldown между сигналами
        # (это будет проверяться на уровне системы)

        # Проверяем время жизни сигнала
        if decision.ttl_sec < 60:  # Минимум 1 минута
            violations.append(f"TTL {decision.ttl_sec}s too short (minimum 60s)")

        if decision.ttl_sec > 7 * 24 * 3600:  # Максимум 7 дней
            violations.append(f"TTL {decision.ttl_sec}s too long (maximum 7 days)")

    def _is_price_valid(self, price: float, tick_size: float) -> bool:
        """Проверка соответствия цены тик-размеру"""
        if tick_size <= 0:
            return True

        return (
            abs(price % tick_size) < 1e-10
        )  # Учитываем погрешности с плавающей точкой
