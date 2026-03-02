"""
Валидатор обязательных данных для расчёта позиций на SWAP.

Проверяет наличие всех необходимых данных согласно техническому заданию:
- Блок 1: Биржевые метаданные
- Блок 2: Рыночные данные
- Блок 3: Параметры пользователя
- Блок 4: Условия сделки
- Блок 5: Контроль сигналов
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Результат валидации данных"""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    missing_fields: list[str]


class PositionDataValidator:
    """Валидатор данных для расчёта позиций"""

    def __init__(self):
        # Обязательные поля по блокам согласно ТЗ
        self.required_fields = {
            "block_1_exchange_metadata": [
                "symbol",
                "margin_mode",
                "tick_size",
                "lot_size",
                "maker_fee",
                "taker_fee",
                "maintenance_margin_rate",
                "max_leverage",
                "funding_rate",
            ],
            "block_2_market_data": ["spot_ohlcv", "swap_ohlcv", "P_last"],
            "block_3_user_params": [
                "balance_usdt",
                "risk_per_trade_pct",
                "leverage_target",
            ],
            "block_4_trade_conditions": [
                "direction",
                "stop_method",
                "stop_value",
                "tp_levels_pct",
                "order_type_entry",
                "slippage_pct",
            ],
            "block_5_signal_control": [
                "consensus_threshold",
                "timeframe_entry",
                "signal_age_max",
            ],
        }

    def validate_all_blocks(self, data: dict[str, Any]) -> ValidationResult:
        """
        Валидирует все блоки данных согласно ТЗ.

        Args:
            data: Словарь с данными для валидации

        Returns:
            ValidationResult с результатами валидации
        """
        errors = []
        warnings = []
        missing_fields = []

        # Проверяем каждый блок
        for block_name, required_fields in self.required_fields.items():
            block_errors, block_warnings, block_missing = self._validate_block(
                data, block_name, required_fields
            )
            errors.extend(block_errors)
            warnings.extend(block_warnings)
            missing_fields.extend(block_missing)

        # Дополнительные проверки
        additional_errors, additional_warnings = self._validate_additional_rules(data)
        errors.extend(additional_errors)
        warnings.extend(additional_warnings)

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            missing_fields=missing_fields,
        )

    def _validate_block(
        self, data: dict[str, Any], block_name: str, required_fields: list[str]
    ) -> tuple[list[str], list[str], list[str]]:
        """Валидирует конкретный блок данных"""
        errors = []
        warnings = []
        missing_fields = []

        for field in required_fields:
            if field not in data or data[field] is None:
                missing_fields.append(f"{block_name}.{field}")
                errors.append(f"Отсутствует обязательное поле: {field}")
            else:
                # Проверяем тип и значение поля
                field_errors, field_warnings = self._validate_field_value(
                    field, data[field], block_name
                )
                errors.extend(field_errors)
                warnings.extend(field_warnings)

        return errors, warnings, missing_fields

    def _validate_field_value(
        self, field: str, value: Any, block_name: str
    ) -> tuple[list[str], list[str]]:
        """Валидирует значение конкретного поля"""
        errors = []
        warnings = []

        if block_name == "block_1_exchange_metadata":
            errors, warnings = self._validate_exchange_metadata(field, value)
        elif block_name == "block_2_market_data":
            errors, warnings = self._validate_market_data(field, value)
        elif block_name == "block_3_user_params":
            errors, warnings = self._validate_user_params(field, value)
        elif block_name == "block_4_trade_conditions":
            errors, warnings = self._validate_trade_conditions(field, value)
        elif block_name == "block_5_signal_control":
            errors, warnings = self._validate_signal_control(field, value)

        return errors, warnings

    def _validate_exchange_metadata(
        self, field: str, value: Any
    ) -> tuple[list[str], list[str]]:
        """Валидирует биржевые метаданные"""
        errors = []
        warnings = []

        if field == "symbol":
            if not isinstance(value, str):
                errors.append("symbol должен быть строкой")
            elif "-SWAP" not in value:
                errors.append(
                    "symbol должен содержать '-SWAP' (например: SOL-USDT-SWAP)"
                )
            elif len(value) < 8:  # Минимальная длина для валидного символа
                warnings.append("symbol слишком короткий")

        elif field == "margin_mode":
            if value not in ["isolated", "cross"]:
                errors.append("margin_mode должен быть 'isolated' или 'cross'")
            elif value == "cross":
                warnings.append("cross margin требует особого внимания к рискам")

        elif field in [
            "tick_size",
            "lot_size",
            "maker_fee",
            "taker_fee",
            "maintenance_margin_rate",
        ]:
            try:
                decimal_value = Decimal(str(value))
                if decimal_value <= 0:
                    errors.append(f"{field} должен быть положительным числом")
                elif decimal_value > 1:
                    warnings.append(
                        f"{field} больше 1 - проверьте корректность значения"
                    )
            except (ValueError, TypeError):
                errors.append(f"{field} должен быть числом")

        elif field == "max_leverage":
            try:
                int_value = int(value)
                if int_value <= 0:
                    errors.append("max_leverage должен быть положительным числом")
                elif int_value > 1000:
                    errors.append("max_leverage не может превышать 1000")
                elif int_value > 100:
                    warnings.append("max_leverage больше 100 - очень высокое плечо")
            except (ValueError, TypeError):
                errors.append("max_leverage должен быть целым числом")

        return errors, warnings

    def _validate_market_data(
        self, field: str, value: Any
    ) -> tuple[list[str], list[str]]:
        """Валидирует рыночные данные"""
        errors = []
        warnings = []

        if field in ["spot_ohlcv", "swap_ohlcv"]:
            if not isinstance(value, list):
                errors.append(f"{field} должен быть массивом")
            elif len(value) < 200:
                errors.append(
                    f"{field} должен содержать минимум 200 баров (сейчас: {len(value)})"
                )
            else:
                # Проверяем структуру OHLCV
                for i, bar in enumerate(value[:10]):  # Проверяем первые 10 баров
                    if not isinstance(bar, dict):
                        errors.append(f"{field}[{i}]: каждый бар должен быть объектом")
                        break

                    required_ohlcv = ["open", "high", "low", "close", "volume"]
                    for req_field in required_ohlcv:
                        if req_field not in bar:
                            errors.append(f"{field}[{i}]: отсутствует поле {req_field}")
                            break
                        if not isinstance(bar[req_field], int | float | Decimal):
                            errors.append(
                                f"{field}[{i}].{req_field}: должно быть числом"
                            )
                            break

                    # Проверяем логику OHLCV
                    if (
                        "high" in bar
                        and "low" in bar
                        and "open" in bar
                        and "close" in bar
                    ):
                        if bar["high"] < bar["low"]:
                            errors.append(
                                f"{field}[{i}]: high не может быть меньше low"
                            )
                        if bar["high"] < bar["open"] or bar["high"] < bar["close"]:
                            errors.append(
                                f"{field}[{i}]: high должен быть максимальным значением"
                            )
                        if bar["low"] > bar["open"] or bar["low"] > bar["close"]:
                            errors.append(
                                f"{field}[{i}]: low должен быть минимальным значением"
                            )

                if len(value) > 1000:
                    warnings.append(
                        f"{field} содержит много данных ({len(value)} баров) - может замедлить расчёты"
                    )

        elif field == "P_last":
            try:
                decimal_value = Decimal(str(value))
                if decimal_value <= 0:
                    errors.append("P_last должен быть положительным числом")
                elif decimal_value > 1000000:
                    warnings.append("P_last очень высокий - проверьте корректность")
            except (ValueError, TypeError):
                errors.append("P_last должен быть числом")

        return errors, warnings

    def _validate_user_params(
        self, field: str, value: Any
    ) -> tuple[list[str], list[str]]:
        """Валидирует параметры пользователя"""
        errors = []
        warnings = []

        if field == "balance_usdt":
            try:
                decimal_value = Decimal(str(value))
                if decimal_value <= 0:
                    errors.append("balance_usdt должен быть положительным числом")
                elif decimal_value < 10:
                    warnings.append("balance_usdt меньше 10 USDT - низкий баланс")
            except (ValueError, TypeError):
                errors.append("balance_usdt должен быть числом")

        elif field == "risk_per_trade_pct":
            try:
                decimal_value = Decimal(str(value))
                if decimal_value <= 0 or decimal_value > 0.1:  # > 10%
                    errors.append("risk_per_trade_pct должен быть от 0 до 0.1 (10%)")
                elif decimal_value > 0.05:  # > 5%
                    warnings.append("risk_per_trade_pct больше 5% - высокий риск")
            except (ValueError, TypeError):
                errors.append("risk_per_trade_pct должен быть числом")

        elif field == "leverage_target":
            try:
                int_value = int(value)
                if int_value <= 0 or int_value > 100:
                    errors.append("leverage_target должен быть от 1 до 100")
                elif int_value > 20:
                    warnings.append("leverage_target больше 20 - высокое плечо")
            except (ValueError, TypeError):
                errors.append("leverage_target должен быть целым числом")

        return errors, warnings

    def _validate_trade_conditions(
        self, field: str, value: Any
    ) -> tuple[list[str], list[str]]:
        """Валидирует условия сделки"""
        errors = []
        warnings = []

        if field == "direction":
            if value not in ["long", "short"]:
                errors.append("direction должен быть 'long' или 'short'")

        elif field == "stop_method":
            if value not in ["percent", "atr_mult"]:
                errors.append("stop_method должен быть 'percent' или 'atr_mult'")

        elif field == "stop_value":
            try:
                decimal_value = Decimal(str(value))
                if decimal_value <= 0:
                    errors.append("stop_value должен быть положительным числом")
                elif decimal_value > 0.1:  # > 10%
                    warnings.append("stop_value больше 10% - большой стоп")
            except (ValueError, TypeError):
                errors.append("stop_value должен быть числом")

        elif field == "tp_levels_pct":
            if not isinstance(value, list):
                errors.append("tp_levels_pct должен быть массивом")
            else:
                for i, tp_level in enumerate(value):
                    try:
                        decimal_value = Decimal(str(tp_level))
                        if decimal_value <= 0:
                            errors.append(
                                f"tp_levels_pct[{i}] должен быть положительным"
                            )
                    except (ValueError, TypeError):
                        errors.append(f"tp_levels_pct[{i}] должен быть числом")

        elif field == "order_type_entry" and value not in ["market", "limit"]:
            errors.append("order_type_entry должен быть 'market' или 'limit'")

        return errors, warnings

    def _validate_signal_control(
        self, field: str, value: Any
    ) -> tuple[list[str], list[str]]:
        """Валидирует контроль сигналов"""
        errors = []
        warnings = []

        if field == "consensus_threshold":
            try:
                decimal_value = Decimal(str(value))
                if decimal_value < 0:
                    errors.append("consensus_threshold должен быть неотрицательным")
                elif decimal_value > 5:
                    warnings.append("consensus_threshold больше 5 - высокий порог")
            except (ValueError, TypeError):
                errors.append("consensus_threshold должен быть числом")

        elif field == "timeframe_entry":
            valid_timeframes = ["1m", "5m", "15m", "1H", "4H", "1D"]
            if value not in valid_timeframes:
                errors.append(
                    f"timeframe_entry должен быть одним из: {valid_timeframes}"
                )

        elif field == "signal_age_max":
            try:
                int_value = int(value)
                if int_value <= 0 or int_value > 1000:
                    errors.append("signal_age_max должен быть от 1 до 1000")
                elif int_value > 100:
                    warnings.append("signal_age_max больше 100 - старые сигналы")
            except (ValueError, TypeError):
                errors.append("signal_age_max должен быть целым числом")

        return errors, warnings

    def _validate_additional_rules(
        self, data: dict[str, Any]
    ) -> tuple[list[str], list[str]]:
        """Дополнительные проверки логики"""
        errors = []
        warnings = []

        # Проверка соответствия stop_method и stop_value
        if "stop_method" in data and "stop_value" in data:
            if data["stop_method"] == "atr_mult" and "atr14" not in data:
                errors.append("Для stop_method='atr_mult' требуется поле atr14")

        # Проверка соответствия order_type_entry и slippage_pct
        if "order_type_entry" in data and data["order_type_entry"] == "market":
            if "slippage_pct" not in data:
                warnings.append("Для market ордеров рекомендуется указать slippage_pct")

        # Проверка leverage_target vs max_leverage
        if "leverage_target" in data and "max_leverage" in data:
            try:
                target = int(data["leverage_target"])
                max_lev = int(data["max_leverage"])
                if target > max_lev:
                    errors.append(
                        f"leverage_target ({target}) превышает max_leverage ({max_lev})"
                    )
            except (ValueError, TypeError):
                pass

        return errors, warnings
