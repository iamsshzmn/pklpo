"""
Модели для торговых рекомендаций
"""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class TradeRecommendation(Base):
    """Модель для таблицы trade_recommendations"""

    __tablename__ = "trade_recommendations"

    # Основные ключи
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    score_id = Column(BigInteger, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    ts = Column(BigInteger, nullable=False)  # timestamp в секундах

    # Результат валидации
    is_valid = Column(Boolean, default=False)
    validation_reasons = Column(ARRAY(Text), nullable=True)

    # Направление и цены
    direction = Column(String(10), nullable=True)
    entry_price = Column(Numeric(20, 8), nullable=True)
    stop_loss_price = Column(Numeric(20, 8), nullable=True)
    take_profit_price = Column(Numeric(20, 8), nullable=True)

    # Размеры позиции
    position_size = Column(Numeric(20, 8), nullable=True)
    position_value_usdt = Column(Numeric(20, 8), nullable=True)
    risk_amount_usdt = Column(Numeric(20, 8), nullable=True)

    # Плечо и маржа
    leverage_used = Column(Numeric(10, 4), nullable=True)
    margin_required = Column(Numeric(20, 8), nullable=True)

    # Параметры расчёта
    atr = Column(Numeric(20, 8), nullable=True)
    atr_multiplier = Column(Numeric(10, 4), nullable=True)
    rr_ratio = Column(Numeric(10, 4), nullable=True)
    balance_usdt = Column(Numeric(20, 8), nullable=True)
    risk_pct = Column(Numeric(10, 6), nullable=True)

    # Статус
    status = Column(String(20), default="pending")  # pending, ready, rejected, error
    dry_run = Column(Boolean, default=True)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    positions = relationship("TradePosition", back_populates="recommendation")

    # Ограничения
    __table_args__ = (
        CheckConstraint("direction IN ('LONG', 'SHORT')", name="check_direction"),
        CheckConstraint(
            "status IN ('pending', 'ready', 'rejected', 'error')", name="check_status"
        ),
    )


class TradePosition(Base):
    """Модель для таблицы trade_positions"""

    __tablename__ = "trade_positions"

    # Основные ключи
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    recommendation_id = Column(
        BigInteger, ForeignKey("trade_recommendations.id"), nullable=True
    )
    symbol = Column(String, nullable=False)
    direction = Column(String(10), nullable=False)

    # Цены исполнения
    entry_price = Column(Numeric(20, 8), nullable=True)
    stop_loss_price = Column(Numeric(20, 8), nullable=True)
    take_profit_price = Column(Numeric(20, 8), nullable=True)

    # Размеры
    position_size = Column(Numeric(20, 8), nullable=True)
    position_value_usdt = Column(Numeric(20, 8), nullable=True)
    risk_amount_usdt = Column(Numeric(20, 8), nullable=True)

    # Плечо
    leverage_used = Column(Numeric(10, 4), nullable=True)
    margin_required = Column(Numeric(20, 8), nullable=True)

    # Статус позиции
    status = Column(String(20), default="open")  # open, closed, cancelled
    pnl_usdt = Column(Numeric(20, 8), nullable=True)  # прибыль/убыток
    close_price = Column(Numeric(20, 8), nullable=True)  # цена закрытия
    close_reason = Column(String(50), nullable=True)  # stop_loss, take_profit, manual

    # Временные метки
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    recommendation = relationship("TradeRecommendation", back_populates="positions")

    # Ограничения
    __table_args__ = (
        CheckConstraint(
            "direction IN ('LONG', 'SHORT')", name="check_position_direction"
        ),
        CheckConstraint(
            "status IN ('open', 'closed', 'cancelled')", name="check_position_status"
        ),
    )
