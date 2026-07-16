"""
Валидатор пользовательских настроек
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class ValidationError:
    """Ошибка валидации"""

    field: str
    message: str
    value: Any = None


class SettingsValidator:
    """Валидатор настроек пользователя"""

    @staticmethod
    def validate_balance_usdt(value: Any) -> tuple[bool, ValidationError | None]:
        """Валидация баланса в USDT"""
        try:
            balance = Decimal(str(value))
            if balance <= 0:
                return False, ValidationError(
                    "balance_usdt", "Баланс должен быть больше 0", value
                )
            if balance > 1000000:
                return False, ValidationError(
                    "balance_usdt", "Баланс не может быть больше 1,000,000 USDT", value
                )
            return True, None
        except (ValueError, TypeError):
            return False, ValidationError(
                "balance_usdt", "Баланс должен быть числом", value
            )

    @staticmethod
    def validate_risk_per_trade_pct(
        value: Any,
    ) -> tuple[bool, ValidationError | None]:
        """Валидация риска на сделку в процентах"""
        try:
            risk = Decimal(str(value))
            if risk <= 0 or risk > 1:
                return False, ValidationError(
                    "risk_per_trade_pct",
                    "Риск должен быть от 0 до 1 (0% до 100%)",
                    value,
                )
            if risk > Decimal("0.1"):
                return False, ValidationError(
                    "risk_per_trade_pct",
                    "Риск не должен превышать 10% на сделку",
                    value,
                )
            return True, None
        except (ValueError, TypeError):
            return False, ValidationError(
                "risk_per_trade_pct", "Риск должен быть числом", value
            )

    @staticmethod
    def validate_leverage_target(value: Any) -> tuple[bool, ValidationError | None]:
        """Валидация целевого плеча"""
        try:
            leverage = int(value)
            if leverage < 1 or leverage > 100:
                return False, ValidationError(
                    "leverage_target", "Плечо должно быть от 1 до 100", value
                )
            return True, None
        except (ValueError, TypeError):
            return False, ValidationError(
                "leverage_target", "Плечо должно быть целым числом", value
            )

    @staticmethod
    def validate_stop_method(value: Any) -> tuple[bool, ValidationError | None]:
        """Валидация метода стопа"""
        valid_methods = ["percent", "atr_mult", "fixed"]
        if value not in valid_methods:
            return False, ValidationError(
                "default_stop_method",
                f"Метод стопа должен быть одним из: {valid_methods}",
                value,
            )
        return True, None

    @staticmethod
    def validate_stop_value(value: Any) -> tuple[bool, ValidationError | None]:
        """Валидация значения стопа"""
        try:
            stop_value = Decimal(str(value))
            if stop_value <= 0 or stop_value > 1:
                return False, ValidationError(
                    "default_stop_value",
                    "Значение стопа должно быть от 0 до 1 (0% до 100%)",
                    value,
                )
            return True, None
        except (ValueError, TypeError):
            return False, ValidationError(
                "default_stop_value", "Значение стопа должно быть числом", value
            )

    @staticmethod
    def validate_tp_levels_pct(value: Any) -> tuple[bool, ValidationError | None]:
        """Валидация уровней тейк-профита"""
        if not isinstance(value, list):
            return False, ValidationError(
                "default_tp_levels_pct",
                "Уровни тейк-профита должны быть списком",
                value,
            )

        if len(value) == 0:
            return False, ValidationError(
                "default_tp_levels_pct",
                "Должен быть хотя бы один уровень тейк-профита",
                value,
            )

        for i, level in enumerate(value):
            try:
                tp_level = Decimal(str(level))
                if tp_level <= 0 or tp_level > 1:
                    return False, ValidationError(
                        "default_tp_levels_pct",
                        f"Уровень {i + 1} должен быть от 0 до 1 (0% до 100%)",
                        value,
                    )
            except (ValueError, TypeError):
                return False, ValidationError(
                    "default_tp_levels_pct",
                    f"Уровень {i + 1} должен быть числом",
                    value,
                )

        return True, None

    @staticmethod
    def validate_order_type_entry(value: Any) -> tuple[bool, ValidationError | None]:
        """Валидация типа ордера входа"""
        valid_types = ["market", "limit"]
        if value not in valid_types:
            return False, ValidationError(
                "default_order_type_entry",
                f"Тип ордера должен быть одним из: {valid_types}",
                value,
            )
        return True, None

    @staticmethod
    def validate_slippage_pct(value: Any) -> tuple[bool, ValidationError | None]:
        """Валидация проскальзывания"""
        try:
            slippage = Decimal(str(value))
            if slippage < 0 or slippage > 1:
                return False, ValidationError(
                    "default_slippage_pct",
                    "Проскальзывание должно быть от 0 до 1 (0% до 100%)",
                    value,
                )
            return True, None
        except (ValueError, TypeError):
            return False, ValidationError(
                "default_slippage_pct", "Проскальзывание должно быть числом", value
            )

    @staticmethod
    def validate_consensus_threshold(
        value: Any,
    ) -> tuple[bool, ValidationError | None]:
        """Валидация порога консенсуса"""
        try:
            consensus = Decimal(str(value))
            if consensus < 0 or consensus > 1:
                return False, ValidationError(
                    "consensus_threshold",
                    "Порог консенсуса должен быть от 0 до 1 (0% до 100%)",
                    value,
                )
            return True, None
        except (ValueError, TypeError):
            return False, ValidationError(
                "consensus_threshold", "Порог консенсуса должен быть числом", value
            )

    @staticmethod
    def validate_timeframe_entry(value: Any) -> tuple[bool, ValidationError | None]:
        """Валидация таймфрейма входа"""
        valid_timeframes = ["1m", "5m", "15m", "1H", "4H", "1D"]
        if value not in valid_timeframes:
            return False, ValidationError(
                "timeframe_entry",
                f"Таймфрейм должен быть одним из: {valid_timeframes}",
                value,
            )
        return True, None

    @staticmethod
    def validate_signal_age_max(value: Any) -> tuple[bool, ValidationError | None]:
        """Валидация максимального возраста сигнала"""
        try:
            age = int(value)
            if age < 1 or age > 1000:
                return False, ValidationError(
                    "signal_age_max",
                    "Возраст сигнала должен быть от 1 до 1000 баров",
                    value,
                )
            return True, None
        except (ValueError, TypeError):
            return False, ValidationError(
                "signal_age_max", "Возраст сигнала должен быть целым числом", value
            )

    @classmethod
    def validate_settings(cls, settings: dict[str, Any]) -> list[ValidationError]:
        """Валидация всех настроек"""
        errors: list[ValidationError] = []

        # Валидация обязательных полей
        validators = {
            "balance_usdt": cls.validate_balance_usdt,
            "risk_per_trade_pct": cls.validate_risk_per_trade_pct,
            "leverage_target": cls.validate_leverage_target,
            "default_stop_method": cls.validate_stop_method,
            "default_stop_value": cls.validate_stop_value,
            "default_tp_levels_pct": cls.validate_tp_levels_pct,
            "default_order_type_entry": cls.validate_order_type_entry,
            "default_slippage_pct": cls.validate_slippage_pct,
            "consensus_threshold": cls.validate_consensus_threshold,
            "timeframe_entry": cls.validate_timeframe_entry,
            "signal_age_max": cls.validate_signal_age_max,
        }

        for field, validator in validators.items():
            if field in settings:
                is_valid, error = validator(settings[field])
                if not is_valid and error is not None:
                    errors.append(error)

        return errors

    @classmethod
    def validate_settings_for_position_calculation(
        cls, settings: dict[str, Any]
    ) -> list[ValidationError]:
        """Валидация настроек для расчёта позиций"""
        errors = cls.validate_settings(settings)

        # Дополнительные проверки для расчёта позиций
        if "balance_usdt" in settings and "risk_per_trade_pct" in settings:
            try:
                balance = Decimal(str(settings["balance_usdt"]))
                risk_pct = Decimal(str(settings["risk_per_trade_pct"]))
                risk_amount = balance * risk_pct

                if risk_amount < 10:
                    errors.append(
                        ValidationError(
                            "risk_amount",
                            "Сумма риска должна быть не менее 10 USDT",
                            float(risk_amount),
                        )
                    )
            except (ValueError, TypeError):
                pass

        return errors
