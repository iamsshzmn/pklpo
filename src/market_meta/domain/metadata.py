"""
Метаданные инструментов и рынка.

Содержит модели для хранения метаданных инструментов:
- Размер тика, лот, номинальная стоимость
- Режимы маржи
- Ставки финансирования
- Параметры ликвидности
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class MarginMode(Enum):
    """Режимы маржи"""

    ISOLATED = "isolated"
    CROSS = "cross"


class InstrumentType(Enum):
    """Типы инструментов"""

    SPOT = "SPOT"
    SWAP = "SWAP"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"


@dataclass
class TickSize:
    """Размер тика для инструмента"""

    min_size: Decimal
    max_size: Decimal
    step_size: Decimal

    def validate_price(self, price: float | Decimal) -> bool:
        """Проверяет, что цена соответствует размеру тика"""
        price_decimal = Decimal(str(price))
        remainder = price_decimal % self.step_size
        return remainder == 0 and self.min_size <= price_decimal <= self.max_size


@dataclass
class LotSize:
    """Размер лота для инструмента"""

    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal

    def validate_quantity(self, quantity: float | Decimal) -> bool:
        """Проверяет, что количество соответствует размеру лота"""
        qty_decimal = Decimal(str(quantity))
        remainder = qty_decimal % self.step_size
        return remainder == 0 and self.min_qty <= qty_decimal <= self.max_qty


@dataclass
class FundingRate:
    """Ставка финансирования для свопов"""

    rate: Decimal
    next_funding_time: datetime
    funding_interval_hours: int = 8

    @property
    def annual_rate(self) -> Decimal:
        """Годовая ставка финансирования"""
        return self.rate * 365 * 24 / self.funding_interval_hours


@dataclass
class LiquidityParams:
    """Параметры ликвидности"""

    min_volume_24h: Decimal
    min_trades_24h: int
    spread_threshold: Decimal  # максимальный спред в %

    def is_liquid(self, volume_24h: Decimal, trades_24h: int, spread: Decimal) -> bool:
        """Проверяет ликвидность инструмента"""
        return (
            volume_24h >= self.min_volume_24h
            and trades_24h >= self.min_trades_24h
            and spread <= self.spread_threshold
        )


@dataclass
class InstrumentMetadata:
    """Метаданные инструмента"""

    # Основная информация
    symbol: str
    inst_id: str
    inst_type: InstrumentType
    base_ccy: str
    quote_ccy: str
    settle_ccy: str | None = None

    # Размеры
    tick_size: TickSize | None = None
    lot_size: LotSize | None = None
    contract_val: Decimal | None = None  # номинальная стоимость контракта

    # Комиссии
    fee_maker: Decimal | None = None  # комиссия мейкера (в %)
    fee_taker: Decimal | None = None  # комиссия тейкера (в %)

    # Плечо и маржа
    max_leverage: int | None = None  # максимальное плечо
    margin_mode: MarginMode | None = None
    position_mode: str | None = None  # LONG_SHORT, NET
    maint_margin_rate: Decimal | None = None  # ставка поддержания маржи
    risk_limit_tier: int | None = None  # уровень лимитов риска

    # Финансирование (для свопов)
    funding_rate: FundingRate | None = None

    # Ликвидность
    liquidity: LiquidityParams | None = None

    # Статус
    state: str = "live"  # live, suspended, expired
    created_time: datetime | None = None
    updated_time: datetime | None = None

    def is_tradable(self) -> bool:
        """Проверяет, можно ли торговать инструментом"""
        return self.state == "live"

    def validate_order(self, price: float, quantity: float) -> bool:
        """Валидирует параметры ордера"""
        if not self.is_tradable():
            return False

        if self.tick_size and not self.tick_size.validate_price(price):
            return False

        if self.lot_size and not self.lot_size.validate_quantity(quantity):
            return False

        return True

    def calculate_notional_value(self, price: float, quantity: float) -> Decimal:
        """Рассчитывает номинальную стоимость позиции"""
        if self.contract_val:
            return Decimal(str(quantity)) * self.contract_val
        return Decimal(str(price)) * Decimal(str(quantity))


@dataclass
class MarketMetadata:
    """Метаданные рынка"""

    exchange: str
    instruments: dict[str, InstrumentMetadata]

    def get_instrument(self, symbol: str) -> InstrumentMetadata | None:
        """Получает метаданные инструмента по символу"""
        return self.instruments.get(symbol)

    def get_tradable_instruments(self) -> list[InstrumentMetadata]:
        """Получает список торгуемых инструментов"""
        return [inst for inst in self.instruments.values() if inst.is_tradable()]

    def get_instruments_by_type(
        self, inst_type: InstrumentType
    ) -> list[InstrumentMetadata]:
        """Получает инструменты по типу"""
        return [
            inst for inst in self.instruments.values() if inst.inst_type == inst_type
        ]

    def get_liquid_instruments(
        self,
        volume_24h: dict[str, Decimal],
        trades_24h: dict[str, int],
        spreads: dict[str, Decimal],
    ) -> list[InstrumentMetadata]:
        """Получает ликвидные инструменты"""
        liquid = []
        for inst in self.instruments.values():
            if not inst.liquidity:
                continue

            vol = volume_24h.get(inst.symbol, Decimal(0))
            trades = trades_24h.get(inst.symbol, 0)
            spread = spreads.get(inst.symbol, Decimal(100))  # 100% если нет данных

            if inst.liquidity.is_liquid(vol, trades, spread):
                liquid.append(inst)

        return liquid
