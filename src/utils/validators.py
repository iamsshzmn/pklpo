"""
Утилиты для валидации входных данных
"""

import re
from typing import Any

from pydantic import BaseModel, validator


class SymbolValidator:
    """Валидатор для торговых символов"""

    # Паттерн для валидных символов (например, BTC-USDT, ETH-USDT)
    SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]+-[A-Z0-9]+$")

    @classmethod
    def validate_symbol(cls, symbol: str) -> bool:
        """
        Проверяет валидность торгового символа

        Args:
            symbol: Символ для проверки

        Returns:
            bool: True если символ валиден
        """
        if not isinstance(symbol, str):
            return False

        if not symbol.strip():
            return False

        return bool(cls.SYMBOL_PATTERN.match(symbol.strip().upper()))

    @classmethod
    def normalize_symbol(cls, symbol: str) -> str:
        """
        Нормализует символ (приводит к верхнему регистру)

        Args:
            symbol: Символ для нормализации

        Returns:
            str: Нормализованный символ
        """
        return symbol.strip().upper()


class TimeframeValidator:
    """Валидатор для таймфреймов"""

    VALID_TIMEFRAMES = {
        "1m",
        "5m",
        "15m",
        "30m",  # Минуты
        "1H",
        "4H",
        "6H",
        "12H",  # Часы
        "1D",
        "1Dutc",  # Дни
        "1W",
        "1Wutc",  # Недели
        "1M",
        "1Mutc",  # Месяцы
    }

    @classmethod
    def validate_timeframe(cls, timeframe: str) -> bool:
        """
        Проверяет валидность таймфрейма

        Args:
            timeframe: Таймфрейм для проверки

        Returns:
            bool: True если таймфрейм валиден
        """
        if not isinstance(timeframe, str):
            return False

        return timeframe.strip() in cls.VALID_TIMEFRAMES

    @classmethod
    def get_valid_timeframes(cls) -> list[str]:
        """
        Возвращает список валидных таймфреймов

        Returns:
            List[str]: Список валидных таймфреймов
        """
        return sorted(cls.VALID_TIMEFRAMES)


class PriceValidator:
    """Валидатор для цен"""

    @classmethod
    def validate_price(cls, price: int | float) -> bool:
        """
        Проверяет валидность цены

        Args:
            price: Цена для проверки

        Returns:
            bool: True если цена валидна
        """
        if not isinstance(price, int | float):
            return False

        return price > 0

    @classmethod
    def validate_volume(cls, volume: int | float) -> bool:
        """
        Проверяет валидность объема

        Args:
            volume: Объем для проверки

        Returns:
            bool: True если объем валиден
        """
        if not isinstance(volume, int | float):
            return False

        return volume >= 0


class TimestampValidator:
    """Валидатор для временных меток"""

    @classmethod
    def validate_timestamp(cls, timestamp: int | float) -> bool:
        """
        Проверяет валидность временной метки

        Args:
            timestamp: Временная метка в миллисекундах

        Returns:
            bool: True если временная метка валидна
        """
        if not isinstance(timestamp, int | float):
            return False

        # Проверяем, что timestamp в разумных пределах (2000-2100 годы)
        min_timestamp = 946684800000  # 2000-01-01
        max_timestamp = 4102444800000  # 2100-01-01

        return min_timestamp <= timestamp <= max_timestamp


class SignalValidator:
    """Валидатор для сигналов"""

    VALID_SIGNALS = {-1, 0, 1}  # SELL, HOLD, BUY

    @classmethod
    def validate_signal(cls, signal: int) -> bool:
        """
        Проверяет валидность сигнала

        Args:
            signal: Сигнал для проверки

        Returns:
            bool: True если сигнал валиден
        """
        return signal in cls.VALID_SIGNALS

    @classmethod
    def signal_to_string(cls, signal: int) -> str:
        """
        Преобразует числовой сигнал в строку

        Args:
            signal: Числовой сигнал

        Returns:
            str: Строковое представление сигнала
        """
        signal_map = {-1: "SELL", 0: "HOLD", 1: "BUY"}
        return signal_map.get(signal, "UNKNOWN")


class ValidationError(Exception):
    """Исключение для ошибок валидации"""

    def __init__(self, message: str, field: str | None = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(self.message)


class DataValidator:
    """Комплексный валидатор данных"""

    @classmethod
    def validate_ohlcv_data(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Валидирует OHLCV данные

        Args:
            data: Словарь с OHLCV данными

        Returns:
            Dict[str, Any]: Валидированные данные

        Raises:
            ValidationError: Если данные невалидны
        """
        required_fields = [
            "symbol",
            "timeframe",
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Отсутствует обязательное поле: {field}", field)

        # Валидируем символ
        if not SymbolValidator.validate_symbol(data["symbol"]):
            raise ValidationError(
                f"Невалидный символ: {data['symbol']}", "symbol", data["symbol"]
            )

        # Валидируем таймфрейм
        if not TimeframeValidator.validate_timeframe(data["timeframe"]):
            raise ValidationError(
                f"Невалидный таймфрейм: {data['timeframe']}",
                "timeframe",
                data["timeframe"],
            )

        # Валидируем временную метку
        if not TimestampValidator.validate_timestamp(data["ts"]):
            raise ValidationError(
                f"Невалидная временная метка: {data['ts']}", "ts", data["ts"]
            )

        # Валидируем цены
        for price_field in ["open", "high", "low", "close"]:
            if not PriceValidator.validate_price(data[price_field]):
                raise ValidationError(
                    f"Невалидная цена в поле {price_field}: {data[price_field]}",
                    price_field,
                    data[price_field],
                )

        # Валидируем объем
        if not PriceValidator.validate_volume(data["volume"]):
            raise ValidationError(
                f"Невалидный объем: {data['volume']}", "volume", data["volume"]
            )

        # Проверяем логику OHLCV
        if data["high"] < max(data["open"], data["close"]):
            raise ValidationError(
                "High не может быть меньше максимального из open/close",
                "high",
                data["high"],
            )

        if data["low"] > min(data["open"], data["close"]):
            raise ValidationError(
                "Low не может быть больше минимального из open/close",
                "low",
                data["low"],
            )

        return data

    @classmethod
    def validate_signal_data(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Валидирует данные сигнала

        Args:
            data: Словарь с данными сигнала

        Returns:
            Dict[str, Any]: Валидированные данные

        Raises:
            ValidationError: Если данные невалидны
        """
        required_fields = ["symbol", "timeframe", "ts", "signal"]

        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Отсутствует обязательное поле: {field}", field)

        # Валидируем символ
        if not SymbolValidator.validate_symbol(data["symbol"]):
            raise ValidationError(
                f"Невалидный символ: {data['symbol']}", "symbol", data["symbol"]
            )

        # Валидируем таймфрейм
        if not TimeframeValidator.validate_timeframe(data["timeframe"]):
            raise ValidationError(
                f"Невалидный таймфрейм: {data['timeframe']}",
                "timeframe",
                data["timeframe"],
            )

        # Валидируем временную метку
        if not TimestampValidator.validate_timestamp(data["ts"]):
            raise ValidationError(
                f"Невалидная временная метка: {data['ts']}", "ts", data["ts"]
            )

        # Валидируем сигнал
        if not SignalValidator.validate_signal(data["signal"]):
            raise ValidationError(
                f"Невалидный сигнал: {data['signal']}", "signal", data["signal"]
            )

        return data


# Pydantic модели для валидации
class OHLCVModel(BaseModel):
    """Pydantic модель для OHLCV данных"""

    symbol: str
    timeframe: str
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @validator("symbol")
    def validate_symbol(self, v):
        if not SymbolValidator.validate_symbol(v):
            raise ValueError(f"Невалидный символ: {v}")
        return SymbolValidator.normalize_symbol(v)

    @validator("timeframe")
    def validate_timeframe(self, v):
        if not TimeframeValidator.validate_timeframe(v):
            raise ValueError(f"Невалидный таймфрейм: {v}")
        return v

    @validator("ts")
    def validate_timestamp(self, v):
        if not TimestampValidator.validate_timestamp(v):
            raise ValueError(f"Невалидная временная метка: {v}")
        return v

    @validator("open", "high", "low", "close")
    def validate_prices(self, v):
        if not PriceValidator.validate_price(v):
            raise ValueError(f"Невалидная цена: {v}")
        return v

    @validator("volume")
    def validate_volume(self, v):
        if not PriceValidator.validate_volume(v):
            raise ValueError(f"Невалидный объем: {v}")
        return v


class SignalModel(BaseModel):
    """Pydantic модель для сигналов"""

    symbol: str
    timeframe: str
    ts: int
    signal: int
    reason: str | None = None

    @validator("symbol")
    def validate_symbol(self, v):
        if not SymbolValidator.validate_symbol(v):
            raise ValueError(f"Невалидный символ: {v}")
        return SymbolValidator.normalize_symbol(v)

    @validator("timeframe")
    def validate_timeframe(self, v):
        if not TimeframeValidator.validate_timeframe(v):
            raise ValueError(f"Невалидный таймфрейм: {v}")
        return v

    @validator("ts")
    def validate_timestamp(self, v):
        if not TimestampValidator.validate_timestamp(v):
            raise ValueError(f"Невалидная временная метка: {v}")
        return v

    @validator("signal")
    def validate_signal(self, v):
        if not SignalValidator.validate_signal(v):
            raise ValueError(f"Невалидный сигнал: {v}")
        return v
