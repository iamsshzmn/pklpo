#!/usr/bin/env python3
"""Миграция: создание расширенной MTF архитектуры.

Создает схему mtf и таблицы для расширенного MTF анализа:
- mtf.context - контекстные скоры по TF (1M,1W,1D,4H,1H,30m)
- mtf.triggers - триггеры (15m/5m) и микро-фильтр (1m)
- mtf.consensus - финальные решения по горизонтам (intraday/swing/week)

Структура соответствует требованиям расширенной MTF логики.
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database import get_async_session

logger = logging.getLogger(__name__)


async def migrate_create_mtf_expanded():
    """Создает расширенную MTF архитектуру"""
    async for session in get_async_session():
        try:
            # 1. Создаем схему mtf
            await session.execute(text("CREATE SCHEMA IF NOT EXISTS mtf"))
            logger.info("✅ Схема mtf создана")

            # 2. Создаем таблицу mtf.context
            await session.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS mtf.context (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,            -- 1M/1W/1D/4H/1H/30m
                    ts TIMESTAMPTZ NOT NULL,            -- метка бара TF
                    score NUMERIC,                      -- trend_TF
                    valid BOOLEAN,                      -- |score| >= τ_TF
                    regime TEXT,                        -- для 1M/1W: trend/range + bull/bear
                    meta JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """
                )
            )

            # Индексы для mtf.context
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS mtf_ctx_ix ON mtf.context(symbol,timeframe,ts DESC)
            """
                )
            )
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS mtf_ctx_symbol_timeframe ON mtf.context(symbol,timeframe)
            """
                )
            )
            logger.info("✅ Таблица mtf.context создана")

            # 3. Создаем таблицу mtf.triggers
            await session.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS mtf.triggers (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,            -- 15m/5m/1m
                    ts TIMESTAMPTZ NOT NULL,
                    p_up NUMERIC,                       -- для 1m допускаем NULL
                    p_down NUMERIC,
                    accel SMALLINT,                     -- -1/0/+1 (для 5m)
                    micro_ok BOOLEAN,                   -- только для 1m
                    features JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """
                )
            )

            # Индексы для mtf.triggers
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS mtf_tr_ix ON mtf.triggers(symbol,timeframe,ts DESC)
            """
                )
            )
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS mtf_tr_symbol_timeframe ON mtf.triggers(symbol,timeframe)
            """
                )
            )
            logger.info("✅ Таблица mtf.triggers создана")

            # 4. Создаем таблицу mtf.consensus
            await session.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS mtf.consensus (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    symbol TEXT NOT NULL,
                    horizon TEXT NOT NULL,              -- intraday/swing/week
                    ts TIMESTAMPTZ NOT NULL,            -- время расчёта (обычно close 15m)
                    side SMALLINT NOT NULL,             -- -1/0/+1
                    score NUMERIC NOT NULL,             -- ранжирующий балл
                    input_data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """
                )
            )

            # Индексы для mtf.consensus
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS mtf_con_ix ON mtf.consensus(symbol,horizon,ts DESC)
            """
                )
            )
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS mtf_con_symbol_horizon ON mtf.consensus(symbol,horizon)
            """
                )
            )
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS mtf_con_side_score ON mtf.consensus(side,score DESC)
            """
                )
            )
            logger.info("✅ Таблица mtf.consensus создана")

            # 5. Создаем представления для удобства
            await session.execute(
                text(
                    """
                CREATE OR REPLACE VIEW mtf.latest_consensus AS
                SELECT DISTINCT ON (symbol, horizon)
                    symbol, horizon, ts, side, score, input_data
                FROM mtf.consensus
                ORDER BY symbol, horizon, ts DESC
            """
                )
            )
            logger.info("✅ Представление mtf.latest_consensus создано")

            await session.execute(
                text(
                    """
                CREATE OR REPLACE VIEW mtf.top_intraday AS
                SELECT * FROM mtf.latest_consensus
                WHERE horizon='intraday' AND side<>0
                ORDER BY score DESC
                LIMIT 50
            """
                )
            )
            logger.info("✅ Представление mtf.top_intraday создано")

            await session.execute(
                text(
                    """
                CREATE OR REPLACE VIEW mtf.top_swing AS
                SELECT * FROM mtf.latest_consensus
                WHERE horizon='swing' AND side<>0
                ORDER BY score DESC
                LIMIT 50
            """
                )
            )
            logger.info("✅ Представление mtf.top_swing создано")

            await session.execute(
                text(
                    """
                CREATE OR REPLACE VIEW mtf.top_week AS
                SELECT * FROM mtf.latest_consensus
                WHERE horizon='week' AND side<>0
                ORDER BY score DESC
                LIMIT 50
            """
                )
            )
            logger.info("✅ Представление mtf.top_week создано")

            await session.commit()
            logger.info("✅ Расширенная MTF архитектура создана успешно")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка миграции MTF: {e}")
            raise


async def main():
    """Основная функция миграции"""
    logger.info("🚀 Запуск миграции расширенной MTF архитектуры...")
    await migrate_create_mtf_expanded()
    logger.info("✅ Миграция завершена успешно")


if __name__ == "__main__":
    asyncio.run(main())
