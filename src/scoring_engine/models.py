"""
Модели для Scoring Engine
"""

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Numeric,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ScoreResult(Base):
    """Модель для таблицы score_results"""

    __tablename__ = "score_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    ts = Column(BigInteger, nullable=False)  # timestamp в секундах

    # Основные scores
    score_raw = Column(Numeric(10, 6), nullable=True)  # Сырой score [0;1]
    score_calibrated = Column(
        Numeric(10, 6), nullable=True
    )  # Калиброванный score [0;1]

    # Метрики
    p_win = Column(Numeric(10, 6), nullable=True)  # Вероятность выигрыша
    edge_net = Column(Numeric(12, 6), nullable=True)  # Чистое преимущество
    confidence = Column(Numeric(10, 6), nullable=True)  # Уверенность [0;1]

    # Статус
    is_valid = Column(Boolean, default=True)  # Валидность результата
    reasons = Column(ARRAY(Text), nullable=True)  # Причины отклонения

    # Временные метки
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
