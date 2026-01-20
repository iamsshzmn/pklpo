#!/usr/bin/env python3
"""
Миграция для создания таблиц торговых рекомендаций
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.database import get_async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_create_trade_recommendations():
    """Создает таблицы для торговых рекомендаций"""

    async for session in get_async_session():
        try:
            # 1. Создаём таблицу trade_recommendations
            create_recommendations_table = text(
                """
                CREATE TABLE IF NOT EXISTS trade_recommendations (
                    id BIGSERIAL PRIMARY KEY,
                    score_id BIGINT NOT NULL,
                    symbol VARCHAR NOT NULL,
                    timeframe VARCHAR NOT NULL,
                    ts BIGINT NOT NULL,

                    -- Результат валидации
                    is_valid BOOLEAN DEFAULT FALSE,
                    validation_reasons TEXT[],

                    -- Направление и цены
                    direction VARCHAR(10) CHECK (direction IN ('LONG', 'SHORT')),
                    entry_price NUMERIC(20, 8),
                    stop_loss_price NUMERIC(20, 8),
                    take_profit_price NUMERIC(20, 8),

                    -- Размеры позиции
                    position_size NUMERIC(20, 8),
                    position_value_usdt NUMERIC(20, 8),
                    risk_amount_usdt NUMERIC(20, 8),

                    -- Плечо и маржа
                    leverage_used NUMERIC(10, 4),
                    margin_required NUMERIC(20, 8),

                    -- Параметры расчёта
                    atr NUMERIC(20, 8),
                    atr_multiplier NUMERIC(10, 4),
                    rr_ratio NUMERIC(10, 4),
                    balance_usdt NUMERIC(20, 8),
                    risk_pct NUMERIC(10, 6),

                    -- Статус
                    status VARCHAR(20) DEFAULT 'pending',
                    dry_run BOOLEAN DEFAULT TRUE,

                    -- Временные метки
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            await session.execute(create_recommendations_table)

            # 2. Создаём индексы
            create_indexes = [
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trade_rec_score_id ON trade_recommendations(score_id)"
                ),
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trade_rec_symbol_timeframe ON trade_recommendations(symbol, timeframe)"
                ),
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trade_rec_ts ON trade_recommendations(ts)"
                ),
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trade_rec_status ON trade_recommendations(status)"
                ),
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trade_rec_created_at ON trade_recommendations(created_at)"
                ),
            ]

            for index_query in create_indexes:
                await session.execute(index_query)

            # 3. Создаём таблицу trade_positions (для исполненных позиций)
            create_positions_table = text(
                """
                CREATE TABLE IF NOT EXISTS trade_positions (
                    id BIGSERIAL PRIMARY KEY,
                    recommendation_id BIGINT REFERENCES trade_recommendations(id),
                    symbol VARCHAR NOT NULL,
                    direction VARCHAR(10) CHECK (direction IN ('LONG', 'SHORT')),

                    -- Цены исполнения
                    entry_price NUMERIC(20, 8),
                    stop_loss_price NUMERIC(20, 8),
                    take_profit_price NUMERIC(20, 8),

                    -- Размеры
                    position_size NUMERIC(20, 8),
                    position_value_usdt NUMERIC(20, 8),
                    risk_amount_usdt NUMERIC(20, 8),

                    -- Плечо
                    leverage_used NUMERIC(10, 4),
                    margin_required NUMERIC(20, 8),

                    -- Статус позиции
                    status VARCHAR(20) DEFAULT 'open', -- open, closed, cancelled
                    pnl_usdt NUMERIC(20, 8), -- прибыль/убыток
                    close_price NUMERIC(20, 8), -- цена закрытия
                    close_reason VARCHAR(50), -- stop_loss, take_profit, manual

                    -- Временные метки
                    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            await session.execute(create_positions_table)

            # 4. Индексы для позиций
            position_indexes = [
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trade_pos_recommendation_id ON trade_positions(recommendation_id)"
                ),
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trade_pos_symbol ON trade_positions(symbol)"
                ),
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trade_pos_status ON trade_positions(status)"
                ),
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trade_pos_opened_at ON trade_positions(opened_at)"
                ),
            ]

            for index_query in position_indexes:
                await session.execute(index_query)

            await session.commit()
            logger.info(
                "✅ Созданы таблицы trade_recommendations и trade_positions с индексами"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка при создании таблиц: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_create_trade_recommendations())
