"""
Валидаторы рыночных данных и позиций.

Содержит валидаторы для:
- Проверки корректности рыночных данных
- Валидации параметров позиций
- Проверки лимитов и ограничений
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.logging import get_logger

from .metadata import MarginMode, MarketMetadata

logger = get_logger("market_meta.validators")


@dataclass
class ValidationResult:
    """Результат валидации"""

    is_valid: bool
    errors: list[str]
    warnings: list[str]

    def add_error(self, error: str):
        """Добавляет ошибку"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        """Добавляет предупреждение"""
        self.warnings.append(warning)


class MarketValidator:
    """Валидатор рыночных данных"""

    def __init__(self, market_metadata: MarketMetadata):
        self.market_metadata = market_metadata

    def validate_ohlcv_data(
        self, symbol: str, data: list[dict[str, Any]]
    ) -> ValidationResult:
        """Валидирует OHLCV данные"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Проверяем существование инструмента
        instrument = self.market_metadata.get_instrument(symbol)
        if not instrument:
            result.add_error(f"Instrument {symbol} not found in market metadata")
            return result

        if not data:
            result.add_error("Empty OHLCV data")
            return result

        # Проверяем структуру данных
        required_fields = ["ts", "open", "high", "low", "close", "volume"]
        for i, candle in enumerate(data):
            for field in required_fields:
                if field not in candle:
                    result.add_error(f"Missing field '{field}' in candle {i}")

            # Проверяем логику OHLC
            if (
                "open" in candle
                and "high" in candle
                and "low" in candle
                and "close" in candle
            ):
                open_price = float(candle["open"])
                high_price = float(candle["high"])
                low_price = float(candle["low"])
                close_price = float(candle["close"])

                if high_price < low_price:
                    result.add_error(
                        f"High price ({high_price}) < Low price ({low_price}) in candle {i}"
                    )

                if high_price < open_price or high_price < close_price:
                    result.add_error(
                        f"High price ({high_price}) is not highest in candle {i}"
                    )

                if low_price > open_price or low_price > close_price:
                    result.add_error(
                        f"Low price ({low_price}) is not lowest in candle {i}"
                    )

                if volume := candle.get("volume"):
                    if float(volume) < 0:
                        result.add_error(f"Negative volume ({volume}) in candle {i}")

        return result

    def validate_price_data(self, symbol: str, price: float) -> ValidationResult:
        """Валидирует ценовые данные"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        instrument = self.market_metadata.get_instrument(symbol)
        if not instrument:
            result.add_error(f"Instrument {symbol} not found")
            return result

        if price <= 0:
            result.add_error(f"Invalid price: {price} (must be positive)")

        # Проверяем размер тика
        if instrument.tick_size:
            if not instrument.tick_size.validate_price(price):
                result.add_error(
                    f"Price {price} does not match tick size requirements: "
                    f"step={instrument.tick_size.step_size}, "
                    f"min={instrument.tick_size.min_size}, "
                    f"max={instrument.tick_size.max_size}"
                )

        return result

    def validate_volume_data(self, symbol: str, volume: float) -> ValidationResult:
        """Валидирует данные объема"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        instrument = self.market_metadata.get_instrument(symbol)
        if not instrument:
            result.add_error(f"Instrument {symbol} not found")
            return result

        if volume <= 0:
            result.add_error("Volume must be positive")

        if instrument.lot_size:
            if not instrument.lot_size.validate_quantity(volume):
                result.add_error(
                    f"Volume {volume} does not match lot size requirements"
                )

        return result

    def validate_risk(
        self, symbol: str, leverage: float, margin_mode: str
    ) -> ValidationResult:
        """Валидирует параметры риска"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        instrument = self.market_metadata.get_instrument(symbol)
        if not instrument:
            result.add_error(f"Instrument {symbol} not found")
            return result

        # Проверка плеча
        if instrument.max_leverage and leverage > instrument.max_leverage:
            result.add_error(
                f"Leverage {leverage} exceeds maximum {instrument.max_leverage}"
            )

        if leverage <= 0:
            result.add_error("Leverage must be positive")

        if leverage > 100:
            result.add_warning(f"High leverage {leverage}:1 detected")

        # Проверка режима маржи
        if instrument.margin_mode:
            valid_modes = [mode.value for mode in MarginMode]
            if margin_mode not in valid_modes:
                result.add_error(
                    f"Invalid margin mode '{margin_mode}'. Valid: {valid_modes}"
                )

        return result

    def validate_liquidity(
        self, symbol: str, spread_bps: float, vol_usdt: float, book_depth: float
    ) -> ValidationResult:
        """Валидирует параметры ликвидности"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        instrument = self.market_metadata.get_instrument(symbol)
        if not instrument:
            result.add_error(f"Instrument {symbol} not found")
            return result

        if not instrument.liquidity:
            result.add_warning("No liquidity parameters defined for instrument")
            return result

        # Проверка спреда
        spread_pct = spread_bps / 10000  # конвертируем из базисных пунктов в проценты
        if spread_pct > instrument.liquidity.spread_threshold:
            result.add_error(
                f"Spread {spread_pct:.4f}% exceeds threshold {instrument.liquidity.spread_threshold}%"
            )

        # Проверка объема
        if vol_usdt < instrument.liquidity.min_volume_24h:
            result.add_error(
                f"24h volume ${vol_usdt:,.0f} below minimum ${instrument.liquidity.min_volume_24h:,.0f}"
            )

        # Проверка глубины стакана
        if book_depth < 1000:  # минимальная глубина $1000
            result.add_warning(f"Low book depth: ${book_depth:,.0f}")

        return result


class PositionValidator:
    """Валидатор позиций"""

    def __init__(self, market_metadata: MarketMetadata):
        self.market_metadata = market_metadata

    def validate_position_size(
        self, symbol: str, quantity: float, price: float
    ) -> ValidationResult:
        """Валидирует размер позиции"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        instrument = self.market_metadata.get_instrument(symbol)
        if not instrument:
            result.add_error(f"Instrument {symbol} not found")
            return result

        # Проверяем количество
        if quantity == 0:
            result.add_error("Position quantity cannot be zero")

        # Проверяем номинальную стоимость
        notional_value = instrument.calculate_notional_value(price, abs(quantity))

        # Минимальная номинальная стоимость (например, $10)
        min_notional = Decimal("10")
        if notional_value < min_notional:
            result.add_error(
                f"Position notional value ({notional_value}) is below minimum ({min_notional})"
            )

        # Проверяем размер лота
        if instrument.lot_size:
            if not instrument.lot_size.validate_quantity(abs(quantity)):
                result.add_error(
                    f"Position quantity {quantity} does not match lot size requirements"
                )

        return result

    def validate_position_risk(
        self,
        symbol: str,
        quantity: float,
        price: float,
        account_balance: float,
        max_position_size_pct: float = 0.1,  # 10% от баланса
    ) -> ValidationResult:
        """Валидирует риски позиции"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        instrument = self.market_metadata.get_instrument(symbol)
        if not instrument:
            result.add_error(f"Instrument {symbol} not found")
            return result

        # Рассчитываем номинальную стоимость позиции
        notional_value = instrument.calculate_notional_value(price, abs(quantity))

        # Проверяем размер позиции относительно баланса
        position_pct = float(notional_value) / account_balance
        if position_pct > max_position_size_pct:
            result.add_error(
                f"Position size ({position_pct:.2%}) exceeds maximum allowed ({max_position_size_pct:.2%})"
            )

        # Проверяем маржу (если применимо)
        if instrument.maint_margin_rate:
            required_margin = notional_value * instrument.maint_margin_rate
            if required_margin > account_balance:
                result.add_error(
                    f"Insufficient balance for margin requirement: "
                    f"required={required_margin}, available={account_balance}"
                )

        return result

    def validate_multiple_positions(
        self,
        positions: dict[str, dict[str, float]],
        account_balance: float,
        max_total_exposure_pct: float = 0.5,  # 50% от баланса
    ) -> ValidationResult:
        """Валидирует совокупные позиции"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        total_exposure = Decimal("0")

        for symbol, position_data in positions.items():
            quantity = position_data.get("quantity", 0)
            price = position_data.get("price", 0)

            if quantity == 0 or price == 0:
                continue

            instrument = self.market_metadata.get_instrument(symbol)
            if not instrument:
                result.add_error(f"Instrument {symbol} not found")
                continue

            notional_value = instrument.calculate_notional_value(price, abs(quantity))
            total_exposure += notional_value

        # Проверяем общую экспозицию
        total_exposure_pct = float(total_exposure) / account_balance
        if total_exposure_pct > max_total_exposure_pct:
            result.add_error(
                f"Total exposure ({total_exposure_pct:.2%}) exceeds maximum allowed ({max_total_exposure_pct:.2%})"
            )

        return result
