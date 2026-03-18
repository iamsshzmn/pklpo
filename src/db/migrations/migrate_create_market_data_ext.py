#!/usr/bin/env python3
"""
Миграция для создания таблицы market_data_ext.

Создает таблицу для хранения расширенных рыночных данных:
- Open Interest (OI)
- Funding Rates
- L2 Order Book метрики (imbalance, spread)

v1: без партиционирования, без liquidations, без depth_usd.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_create_market_data_ext() -> None:
    """
    Создает таблицу market_data_ext для расширенных рыночных данных.
    """
    logger.info("📊 Создаем таблицу market_data_ext...")

    async with get_db_session() as session:
        try:
            # Создаем основную таблицу
            logger.info("🔄 Создаем таблицу market_data_ext...")
            create_table_q = text(
                """
                CREATE TABLE IF NOT EXISTS market_data_ext (
                    id BIGSERIAL,
                    symbol VARCHAR(50) NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,

                    -- Open Interest
                    open_interest DECIMAL(20, 8),
                    oi_change_24h DECIMAL(20, 8),
                    oi_change_pct_24h DECIMAL(10, 6),

                    -- Funding Rates
                    funding_rate DECIMAL(10, 8),
                    next_funding_time TIMESTAMPTZ,
                    funding_interval_hours INTEGER,

                    -- L2 Order Book Imbalance (v1: только базовые метрики)
                    bid_imbalance DECIMAL(10, 6),  -- bid_volume / (bid_volume + ask_volume)
                    ask_imbalance DECIMAL(10, 6),  -- ask_volume / (bid_volume + ask_volume)
                    spread_bps DECIMAL(10, 2),     -- (ask - bid) / bid * 10000

                    -- Метаданные
                    source VARCHAR(20) NOT NULL DEFAULT 'okx',  -- okx, binance, bybit
                    bar_timestamp TIMESTAMPTZ,  -- Привязка к бару OHLCV
                    timeframe VARCHAR(10),      -- 1m, 5m, 15m, 1H, etc.

                    -- Версионирование
                    run_id VARCHAR(100),
                    algo_version VARCHAR(50),
                    params_hash VARCHAR(64),

                    -- Временные метки
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                    -- Индексы
                    CONSTRAINT pk_market_data_ext PRIMARY KEY (id),
                    -- Бизнес-ключ: один символ, один таймфрейм, один бар = одна запись
                    CONSTRAINT uq_market_data_ext_symbol_timeframe_bar_ts
                        UNIQUE (symbol, timeframe, bar_timestamp)
                );
            """
            )
            await session.execute(create_table_q)
            logger.info("✅ Таблица market_data_ext создана")

            # Индексы для производительности
            logger.info("🔄 Создаем индексы...")

            # Составной индекс для основных запросов
            create_index_1 = text(
                """
                CREATE INDEX IF NOT EXISTS idx_market_data_ext_symbol_timeframe_bar_ts
                ON market_data_ext(symbol, timeframe, bar_timestamp DESC);
            """
            )
            await session.execute(create_index_1)

            # Индекс для поиска по сырому timestamp
            create_index_2 = text(
                """
                CREATE INDEX IF NOT EXISTS idx_market_data_ext_timestamp
                ON market_data_ext(timestamp DESC);
            """
            )
            await session.execute(create_index_2)

            # BRIN индекс для временных запросов
            # WHERE условие добавляем через частичный индекс
            create_index_3 = text(
                """
                CREATE INDEX IF NOT EXISTS idx_market_data_ext_bar_ts_brin
                ON market_data_ext USING BRIN (bar_timestamp)
                WHERE bar_timestamp IS NOT NULL;
            """
            )
            await session.execute(create_index_3)

            logger.info("✅ Индексы созданы")

            await session.commit()
            logger.info("🎉 Таблица market_data_ext создана успешно!")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при создании таблицы market_data_ext: {e}")
            raise
