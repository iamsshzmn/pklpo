"""
Модели данных для расчёта позиций на SWAP инструментах.

Содержит все необходимые модели согласно техническому заданию:
- PositionCalculation - основная модель расчёта позиции
- SwapMetadata - метаданные SWAP инструмента
- UserSettings - пользовательские настройки
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SwapMetadata(Base):
    """Метаданные SWAP инструмента (блок 1 из ТЗ)"""

    __tablename__ = "swap_metadata"

    # Основные ключи
    symbol = Column(String, primary_key=True)  # SOL-USDT-SWAP

    # Биржевые метаданные
    margin_mode = Column(String, nullable=False)  # isolated / cross
    tick_size = Column(Numeric, nullable=False)  # размер тика
    lot_size = Column(Numeric, nullable=False)  # размер лота
    maker_fee = Column(Numeric, nullable=False)  # комиссия мейкера
    taker_fee = Column(Numeric, nullable=False)  # комиссия тейкера
    maintenance_margin_rate = Column(Numeric, nullable=False)  # MMR
    max_leverage = Column(SmallInteger, nullable=False)  # максимальное плечо
    funding_rate = Column(Numeric, nullable=True)  # последняя ставка финансирования

    # Дополнительные поля из существующей таблицы instruments
    contract_val = Column(Float, nullable=True)  # стоимость контракта
    settle_ccy = Column(String, nullable=True)  # валюта расчётов
    ct_type = Column(String, nullable=True)  # linear / inverse
    minSz = Column(Float, nullable=True)  # минимальный размер
    maxSz = Column(Float, nullable=True)  # максимальный размер
    minNotional = Column(Float, nullable=True)  # минимальная сумма сделки

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSettings(Base):
    """Пользовательские настройки (блок 3 из ТЗ)"""

    __tablename__ = "user_settings"

    # Основные ключи
    user_id = Column(String, primary_key=True)  # ID пользователя

    # Параметры риска
    balance_usdt = Column(Numeric, nullable=False)  # баланс в USDT
    risk_per_trade_pct = Column(Numeric, nullable=False)  # риск на сделку в %
    leverage_target = Column(SmallInteger, nullable=False)  # целевое плечо

    # Дополнительные настройки
    default_stop_method = Column(String, default="percent")  # percent / atr_mult
    default_stop_value = Column(Numeric, nullable=True)  # значение стопа
    default_tp_levels_pct = Column(JSON, nullable=True)  # [0.03, 0.06]
    default_order_type_entry = Column(String, default="market")  # market / limit
    default_slippage_pct = Column(Numeric, nullable=True)  # проскальзывание

    # Настройки сигналов
    consensus_threshold = Column(Numeric, nullable=False)  # порог консенсуса
    timeframe_entry = Column(String, nullable=False)  # таймфрейм входа
    signal_age_max = Column(
        SmallInteger, nullable=False
    )  # максимальный возраст сигнала

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PositionCalculation(Base):
    """Расчёт позиции (результат всех вычислений)"""

    __tablename__ = "position_calculations"

    # Основные ключи
    id = Column(String, primary_key=True)  # UUID расчёта
    symbol = Column(String, nullable=False)  # SOL-USDT-SWAP
    user_id = Column(String, nullable=False)  # ID пользователя
    calculated_at = Column(DateTime, default=datetime.utcnow)

    # Входные данные (JSON для хранения всех параметров)
    input_data = Column(JSON, nullable=False)  # все входные данные

    # Результаты расчётов
    position_size = Column(Numeric, nullable=True)  # размер позиции в контрактах
    position_value_usdt = Column(Numeric, nullable=True)  # стоимость позиции в USDT
    entry_price = Column(Numeric, nullable=True)  # цена входа
    stop_loss_price = Column(Numeric, nullable=True)  # цена стоп-лосса
    take_profit_prices = Column(JSON, nullable=True)  # цены тейк-профитов
    risk_amount_usdt = Column(Numeric, nullable=True)  # сумма риска в USDT
    stop_distance_pct = Column(Numeric, nullable=True)  # расстояние стопа в %

    # Расчёт плеча
    leverage_used = Column(SmallInteger, nullable=True)  # использованное плечо
    margin_required = Column(Numeric, nullable=True)  # требуемая маржа
    liquidation_distance_pct = Column(
        Numeric, nullable=True
    )  # расстояние до ликвидации

    # Статус расчёта
    is_valid = Column(Boolean, default=False)  # валидность расчёта
    validation_errors = Column(JSON, nullable=True)  # ошибки валидации
    warnings = Column(JSON, nullable=True)  # предупреждения

    # Интеграция с сигналами
    signal_consensus = Column(Numeric, nullable=True)  # консенсус сигналов
    signal_age_bars = Column(SmallInteger, nullable=True)  # возраст сигнала в барах
    signal_timeframe = Column(String, nullable=True)  # таймфрейм сигнала

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PositionOrder(Base):
    """Ордера позиции (entry, stop-loss, take-profit)"""

    __tablename__ = "position_orders"

    # Основные ключи
    id = Column(String, primary_key=True)  # UUID ордера
    position_calculation_id = Column(String, nullable=False)  # ссылка на расчёт
    order_type = Column(String, nullable=False)  # entry, stop_loss, take_profit

    # Параметры ордера
    side = Column(String, nullable=False)  # buy / sell
    order_type_exchange = Column(String, nullable=False)  # market / limit
    quantity = Column(Numeric, nullable=False)  # количество
    price = Column(Numeric, nullable=True)  # цена (null для market)

    # Дополнительные параметры
    reduce_only = Column(Boolean, default=False)  # только закрытие
    time_in_force = Column(String, nullable=True)  # GTC, IOC, FOK

    # Статус
    status = Column(String, default="calculated")  # calculated, sent, filled, cancelled
    exchange_order_id = Column(String, nullable=True)  # ID ордера на бирже

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
