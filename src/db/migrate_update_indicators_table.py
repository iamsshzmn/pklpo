#!/usr/bin/env python3
"""
Миграция для обновления существующей таблицы indicators.

Обновляет старую таблицу indicators до новой структуры
с поддержкой всех 52 индикаторов и улучшенной архитектурой.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_update_indicators_table() -> None:
    """
    Обновляет существующую таблицу indicators до новой структуры.
    """
    logger.info("📊 Обновляем таблицу indicators...")

    async with get_db_session() as session:
        try:
            # 1. Переименовываем ts в timestamp
            logger.info("🔄 Переименовываем ts в timestamp...")
            await session.execute(
                text(
                    """
                ALTER TABLE indicators RENAME COLUMN ts TO timestamp;
            """
                )
            )
            await session.commit()
            logger.info("✅ Колонка ts переименована в timestamp")

            # 2. Добавляем недостающие колонки для новых индикаторов
            logger.info("🔄 Добавляем новые колонки...")

            # Добавляем колонки для метаданных
            await session.execute(
                text(
                    """
                ALTER TABLE indicators ADD COLUMN IF NOT EXISTS run_id VARCHAR(36);
            """
                )
            )
            await session.execute(
                text(
                    """
                ALTER TABLE indicators ADD COLUMN IF NOT EXISTS params_hash VARCHAR(16);
            """
                )
            )
            await session.execute(
                text(
                    """
                ALTER TABLE indicators ADD COLUMN IF NOT EXISTS data_quality_status VARCHAR(20) DEFAULT 'good';
            """
                )
            )
            await session.execute(
                text(
                    """
                ALTER TABLE indicators ADD COLUMN IF NOT EXISTS nan_count INTEGER DEFAULT 0;
            """
                )
            )
            await session.execute(
                text(
                    """
                ALTER TABLE indicators ADD COLUMN IF NOT EXISTS valid_rate DECIMAL(5,4) DEFAULT 1.0;
            """
                )
            )
            await session.execute(
                text(
                    """
                ALTER TABLE indicators ADD COLUMN IF NOT EXISTS schema_version VARCHAR(10) DEFAULT 'v2';
            """
                )
            )
            await session.execute(
                text(
                    """
                ALTER TABLE indicators ADD COLUMN IF NOT EXISTS algo_version VARCHAR(20) DEFAULT '2.0.0';
            """
                )
            )
            await session.execute(
                text(
                    """
                ALTER TABLE indicators ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
            """
                )
            )

            # Добавляем недостающие индикаторы
            new_indicators = [
                # DPO
                ("dpo_20", "DECIMAL(10,4)"),
                # KST
                ("kst", "DECIMAL(10,4)"),
                # Momentum
                ("mom_10", "DECIMAL(10,4)"),
                # PPO
                ("ppo", "DECIMAL(10,4)"),
                ("ppo_signal", "DECIMAL(10,4)"),
                ("ppo_histogram", "DECIMAL(10,4)"),
                # ROC
                ("roc_10", "DECIMAL(10,4)"),
                # Williams %R
                ("williams_r", "DECIMAL(10,4)"),
                # Ultimate Oscillator
                ("ultimate_osc", "DECIMAL(10,4)"),
                # Bollinger Bands дополнительные
                ("bb_width", "DECIMAL(10,4)"),
                ("bb_percent", "DECIMAL(10,4)"),
                # Donchian Channel
                ("dc_upper", "DECIMAL(10,4)"),
                ("dc_middle", "DECIMAL(10,4)"),
                ("dc_lower", "DECIMAL(10,4)"),
                # Money Flow Index
                ("mfi_14", "DECIMAL(10,4)"),
                # Weighted Moving Average
                ("wma_20", "DECIMAL(10,4)"),
                # Hull Moving Average
                ("hma_20", "DECIMAL(10,4)"),
                # Kaufman Adaptive Moving Average
                ("kama_20", "DECIMAL(10,4)"),
                # Triple Exponential Moving Average
                ("tema_20", "DECIMAL(10,4)"),
                # Double Exponential Moving Average
                ("dema_20", "DECIMAL(10,4)"),
            ]

            for col_name, col_type in new_indicators:
                await session.execute(
                    text(
                        f"""
                    ALTER TABLE indicators ADD COLUMN IF NOT EXISTS {col_name} {col_type};
                """
                    )
                )
                await session.commit()

            logger.info("✅ Новые колонки добавлены")

            # 3. Обновляем существующие колонки для соответствия новой структуре
            logger.info("🔄 Обновляем существующие колонки...")

            # Переименовываем существующие колонки для соответствия новой структуре
            renames = [
                ("rsi14", "rsi_14"),
                ("atr14", "atr_14"),
                ("adx14", "adx_14"),
                ("ichimoku_tenkan", "ichimoku_a"),
                ("ichimoku_kijun", "ichimoku_b"),
            ]

            for old_name, new_name in renames:
                try:
                    await session.execute(
                        text(
                            f"""
                        ALTER TABLE indicators RENAME COLUMN {old_name} TO {new_name};
                    """
                        )
                    )
                    await session.commit()
                except Exception as e:
                    logger.warning(
                        f"Не удалось переименовать {old_name} в {new_name}: {e}"
                    )

            logger.info("✅ Существующие колонки обновлены")

            # 4. Создаем индексы если их нет
            logger.info("🔄 Создаем индексы...")

            indexes = [
                (
                    "idx_indicators_symbol_timeframe_timestamp",
                    "CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timeframe_timestamp ON indicators (symbol, timeframe, timestamp DESC)",
                ),
                (
                    "idx_indicators_run_id",
                    "CREATE INDEX IF NOT EXISTS idx_indicators_run_id ON indicators (run_id)",
                ),
                (
                    "idx_indicators_quality",
                    "CREATE INDEX IF NOT EXISTS idx_indicators_quality ON indicators (data_quality_status)",
                ),
                (
                    "idx_indicators_rsi",
                    "CREATE INDEX IF NOT EXISTS idx_indicators_rsi ON indicators (rsi_14) WHERE rsi_14 IS NOT NULL",
                ),
                (
                    "idx_indicators_macd",
                    "CREATE INDEX IF NOT EXISTS idx_indicators_macd ON indicators (macd) WHERE macd IS NOT NULL",
                ),
                (
                    "idx_indicators_atr",
                    "CREATE INDEX IF NOT EXISTS idx_indicators_atr ON indicators (atr_14) WHERE atr_14 IS NOT NULL",
                ),
            ]

            for index_name, index_sql in indexes:
                try:
                    await session.execute(text(index_sql))
                    await session.commit()
                except Exception as e:
                    logger.warning(f"Не удалось создать индекс {index_name}: {e}")

            logger.info("✅ Индексы созданы")

            # 5. Добавляем уникальное ограничение если его нет
            logger.info("🔄 Добавляем уникальное ограничение...")
            try:
                await session.execute(
                    text(
                        """
                    ALTER TABLE indicators ADD CONSTRAINT IF NOT EXISTS uq_indicators_unique
                    UNIQUE (symbol, timeframe, timestamp);
                """
                    )
                )
                await session.commit()
                logger.info("✅ Уникальное ограничение добавлено")
            except Exception as e:
                logger.warning(f"Не удалось добавить уникальное ограничение: {e}")

            await session.commit()
            logger.info("✅ Миграция обновления indicators завершена успешно!")

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении таблицы indicators: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    import asyncio

    asyncio.run(migrate_update_indicators_table())
