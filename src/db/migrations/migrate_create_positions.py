"""
Миграция для создания таблиц позиций на SWAP инструментах.

Создаёт таблицы:
- swap_metadata - метаданные SWAP инструментов
- user_settings - пользовательские настройки
- position_calculations - расчёты позиций
- position_orders - ордера позиций
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database import get_async_session

logger = logging.getLogger(__name__)


async def create_swap_metadata_table():
    """Создаёт таблицу swap_metadata"""
    async for session in get_async_session():
        try:
            # Создаём таблицу swap_metadata
            await session.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS swap_metadata (
                    symbol VARCHAR PRIMARY KEY,
                    margin_mode VARCHAR NOT NULL,
                    tick_size NUMERIC NOT NULL,
                    lot_size NUMERIC NOT NULL,
                    maker_fee NUMERIC NOT NULL,
                    taker_fee NUMERIC NOT NULL,
                    maintenance_margin_rate NUMERIC NOT NULL,
                    max_leverage SMALLINT NOT NULL,
                    funding_rate NUMERIC,
                    contract_val FLOAT,
                    settle_ccy VARCHAR,
                    ct_type VARCHAR,
                    minSz FLOAT,
                    maxSz FLOAT,
                    minNotional FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
                )
            )

            await session.commit()
            logger.info("✅ Таблица swap_metadata создана успешно")

        except Exception as e:
            logger.error(f"❌ Ошибка при создании таблицы swap_metadata: {e}")
            await session.rollback()
            raise


async def create_user_settings_table():
    """Создаёт таблицу user_settings"""
    async for session in get_async_session():
        try:
            # Создаём таблицу user_settings
            await session.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id VARCHAR PRIMARY KEY,
                    balance_usdt NUMERIC NOT NULL,
                    risk_per_trade_pct NUMERIC NOT NULL,
                    leverage_target SMALLINT NOT NULL,
                    default_stop_method VARCHAR DEFAULT 'percent',
                    default_stop_value NUMERIC,
                    default_tp_levels_pct JSON,
                    default_order_type_entry VARCHAR DEFAULT 'market',
                    default_slippage_pct NUMERIC,
                    consensus_threshold NUMERIC NOT NULL,
                    timeframe_entry VARCHAR NOT NULL,
                    signal_age_max SMALLINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
                )
            )

            await session.commit()
            logger.info("✅ Таблица user_settings создана успешно")

        except Exception as e:
            logger.error(f"❌ Ошибка при создании таблицы user_settings: {e}")
            await session.rollback()
            raise


async def create_position_calculations_table():
    """Создаёт таблицу position_calculations"""
    async for session in get_async_session():
        try:
            # Создаём таблицу position_calculations
            await session.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS position_calculations (
                    id VARCHAR PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    input_data JSON NOT NULL,
                    position_size NUMERIC,
                    position_value_usdt NUMERIC,
                    entry_price NUMERIC,
                    stop_loss_price NUMERIC,
                    take_profit_prices JSON,
                    risk_amount_usdt NUMERIC,
                    stop_distance_pct NUMERIC,
                    leverage_used SMALLINT,
                    margin_required NUMERIC,
                    liquidation_distance_pct NUMERIC,
                    is_valid BOOLEAN DEFAULT FALSE,
                    validation_errors JSON,
                    warnings JSON,
                    signal_consensus NUMERIC,
                    signal_age_bars SMALLINT,
                    signal_timeframe VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
                )
            )

            await session.commit()
            logger.info("✅ Таблица position_calculations создана успешно")

        except Exception as e:
            logger.error(f"❌ Ошибка при создании таблицы position_calculations: {e}")
            await session.rollback()
            raise


async def create_position_orders_table():
    """Создаёт таблицу position_orders"""
    async for session in get_async_session():
        try:
            # Создаём таблицу position_orders
            await session.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS position_orders (
                    id VARCHAR PRIMARY KEY,
                    position_calculation_id VARCHAR NOT NULL,
                    order_type VARCHAR NOT NULL,
                    side VARCHAR NOT NULL,
                    order_type_exchange VARCHAR NOT NULL,
                    quantity NUMERIC NOT NULL,
                    price NUMERIC,
                    reduce_only BOOLEAN DEFAULT FALSE,
                    time_in_force VARCHAR,
                    status VARCHAR DEFAULT 'calculated',
                    exchange_order_id VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
                )
            )

            await session.commit()
            logger.info("✅ Таблица position_orders создана успешно")

        except Exception as e:
            logger.error(f"❌ Ошибка при создании таблицы position_orders: {e}")
            await session.rollback()
            raise


async def run_migrations():
    """Выполняет все миграции для позиций"""
    logger.info("🚀 Начинаем создание таблиц для позиций...")

    try:
        await create_swap_metadata_table()
        await create_user_settings_table()
        await create_position_calculations_table()
        await create_position_orders_table()

        logger.info("🎉 Все таблицы для позиций созданы успешно!")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при создании таблиц: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_migrations())
