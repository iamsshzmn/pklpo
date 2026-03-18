#!/usr/bin/env python3
"""Миграция: создание таблицы mtf_signals (отдельно от position_calculations).

Структура минимальна и соответствует требованиям модуля MTF:
- id (UUID/VARCHAR PK)
- symbol
- calculated_at (UTC)
- signal_consensus (SMALLINT: -1/0/1)
- signal_timeframe (например, '15m')
- signal_age_bars (SMALLINT)
- input_data (JSONB)
- created_at, updated_at

Индексы по symbol, calculated_at.
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database import get_async_session

logger = logging.getLogger(__name__)


async def migrate_create_mtf_signals():
    async for session in get_async_session():
        try:
            await session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS mtf_signals (
                        id VARCHAR PRIMARY KEY,
                        symbol VARCHAR NOT NULL,
                        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        signal_consensus SMALLINT,
                        signal_timeframe VARCHAR,
                        signal_age_bars SMALLINT DEFAULT 0,
                        input_data JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )

            # Индексы
            await session.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_mtf_signals_symbol
                    ON mtf_signals(symbol);
                    """
                )
            )
            await session.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_mtf_signals_calculated_at
                    ON mtf_signals(calculated_at);
                    """
                )
            )

            await session.commit()
            logger.info("✅ Таблица mtf_signals создана/актуализирована")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка миграции mtf_signals: {e}")
            raise
        break


async def run_migrations():
    await migrate_create_mtf_signals()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_migrations())
