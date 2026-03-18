#!/usr/bin/env python3
"""
Миграция для создания единой улучшенной таблицы indicators.

Создает универсальную таблицу для всех технических индикаторов
с поддержкой версионирования, качества данных и оптимизации.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_create_unified_indicators_table() -> None:
    """
    Создает единую таблицу indicators для всех технических индикаторов.
    """
    logger.info("📊 Создаем единую таблицу indicators...")

    async with get_db_session() as session:
        try:
            # Создаем основную таблицу indicators
            logger.info("🔄 Создаем основную таблицу indicators...")
            create_table_q = text(
                """
                CREATE TABLE IF NOT EXISTS indicators (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    timestamp BIGINT NOT NULL,

                    -- Основные OHLCV данные
                    open DECIMAL(20,8) NOT NULL,
                    high DECIMAL(20,8) NOT NULL,
                    low DECIMAL(20,8) NOT NULL,
                    close DECIMAL(20,8) NOT NULL,
                    volume DECIMAL(30,8) NOT NULL,

                    -- === TREND INDICATORS ===
                    -- ADX
                    adx_14 DECIMAL(10,4),
                    adx_pos_di DECIMAL(10,4),
                    adx_neg_di DECIMAL(10,4),

                    -- CCI
                    cci_20 DECIMAL(10,4),

                    -- DPO
                    dpo_20 DECIMAL(10,4),

                    -- Ichimoku
                    ichimoku_a DECIMAL(10,4),
                    ichimoku_b DECIMAL(10,4),
                    ichimoku_senkou_a DECIMAL(10,4),
                    ichimoku_senkou_b DECIMAL(10,4),
                    ichimoku_chikou DECIMAL(10,4),

                    -- KST
                    kst DECIMAL(10,4),

                    -- Momentum
                    mom_10 DECIMAL(10,4),

                    -- PPO
                    ppo DECIMAL(10,4),
                    ppo_signal DECIMAL(10,4),
                    ppo_histogram DECIMAL(10,4),

                    -- ROC
                    roc_10 DECIMAL(10,4),

                    -- Stochastic
                    stoch_k DECIMAL(10,4),
                    stoch_d DECIMAL(10,4),

                    -- Williams %R
                    williams_r DECIMAL(10,4),

                    -- Ultimate Oscillator
                    ultimate_osc DECIMAL(10,4),

                    -- === OSCILLATOR INDICATORS ===
                    -- RSI
                    rsi_14 DECIMAL(10,4),

                    -- === VOLATILITY INDICATORS ===
                    -- ATR
                    atr_14 DECIMAL(10,4),

                    -- Bollinger Bands
                    bb_upper DECIMAL(10,4),
                    bb_middle DECIMAL(10,4),
                    bb_lower DECIMAL(10,4),
                    bb_width DECIMAL(10,4),
                    bb_percent DECIMAL(10,4),

                    -- Keltner Channel
                    kc_upper DECIMAL(10,4),
                    kc_middle DECIMAL(10,4),
                    kc_lower DECIMAL(10,4),

                    -- Donchian Channel
                    dc_upper DECIMAL(10,4),
                    dc_middle DECIMAL(10,4),
                    dc_lower DECIMAL(10,4),

                    -- === VOLUME INDICATORS ===
                    -- OBV
                    obv DECIMAL(20,4),

                    -- VWAP
                    vwap DECIMAL(10,4),

                    -- Money Flow Index
                    mfi_14 DECIMAL(10,4),

                    -- === MOVING AVERAGE INDICATORS ===
                    -- Simple Moving Averages
                    sma_20 DECIMAL(10,4),
                    sma_50 DECIMAL(10,4),
                    sma_200 DECIMAL(10,4),

                    -- Exponential Moving Averages
                    ema_12 DECIMAL(10,4),
                    ema_26 DECIMAL(10,4),
                    ema_50 DECIMAL(10,4),
                    ema_200 DECIMAL(10,4),

                    -- Weighted Moving Average
                    wma_20 DECIMAL(10,4),

                    -- Hull Moving Average
                    hma_20 DECIMAL(10,4),

                    -- Kaufman Adaptive Moving Average
                    kama_20 DECIMAL(10,4),

                    -- Triple Exponential Moving Average
                    tema_20 DECIMAL(10,4),

                    -- Double Exponential Moving Average
                    dema_20 DECIMAL(10,4),

                    -- === MACD ===
                    macd DECIMAL(10,4),
                    macd_signal DECIMAL(10,4),
                    macd_histogram DECIMAL(10,4),

                    -- === ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ ===
                    -- Метаданные расчёта
                    run_id VARCHAR(36),
                    params_hash VARCHAR(16),

                    -- Качество данных
                    data_quality_status VARCHAR(20) DEFAULT 'good',
                    nan_count INTEGER DEFAULT 0,
                    valid_rate DECIMAL(5,4) DEFAULT 1.0,

                    -- Версионирование
                    schema_version VARCHAR(10) DEFAULT 'v2',
                    algo_version VARCHAR(20) DEFAULT '2.0.0',

                    -- Временные метки
                    calculated_at TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """
            )
            await session.execute(create_table_q)
            await session.commit()
            logger.info("✅ Основная таблица indicators создана")

            # Создаем индексы для оптимизации
            logger.info("🔄 Создаем индексы...")

            # Основной индекс для быстрого поиска
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timeframe_timestamp
                ON indicators (symbol, timeframe, timestamp DESC);
            """
                )
            )
            await session.commit()

            # Индекс по run_id для группировки результатов
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_indicators_run_id
                ON indicators (run_id);
            """
                )
            )
            await session.commit()

            # Индекс по качеству данных
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_indicators_quality
                ON indicators (data_quality_status);
            """
                )
            )
            await session.commit()

            # Индексы для популярных индикаторов
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_indicators_rsi
                ON indicators (rsi_14) WHERE rsi_14 IS NOT NULL;
            """
                )
            )
            await session.commit()

            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_indicators_macd
                ON indicators (macd) WHERE macd IS NOT NULL;
            """
                )
            )
            await session.commit()

            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_indicators_atr
                ON indicators (atr_14) WHERE atr_14 IS NOT NULL;
            """
                )
            )
            await session.commit()

            # Уникальное ограничение
            await session.execute(
                text(
                    """
                ALTER TABLE indicators ADD CONSTRAINT uq_indicators_unique
                UNIQUE (symbol, timeframe, timestamp);
            """
                )
            )
            await session.commit()

            logger.info("✅ Индексы созданы")

            # Создаем партиции по месяцам для оптимизации
            logger.info("🔄 Создаем партиции...")

            # Создаем родительскую таблицу для партиций
            await session.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS indicators_p (
                    symbol VARCHAR(20) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    timestamp BIGINT NOT NULL,
                    open DECIMAL(20,8) NOT NULL,
                    high DECIMAL(20,8) NOT NULL,
                    low DECIMAL(20,8) NOT NULL,
                    close DECIMAL(20,8) NOT NULL,
                    volume DECIMAL(30,8) NOT NULL,
                    adx_14 DECIMAL(10,4),
                    adx_pos_di DECIMAL(10,4),
                    adx_neg_di DECIMAL(10,4),
                    cci_20 DECIMAL(10,4),
                    dpo_20 DECIMAL(10,4),
                    ichimoku_a DECIMAL(10,4),
                    ichimoku_b DECIMAL(10,4),
                    ichimoku_senkou_a DECIMAL(10,4),
                    ichimoku_senkou_b DECIMAL(10,4),
                    ichimoku_chikou DECIMAL(10,4),
                    kst DECIMAL(10,4),
                    mom_10 DECIMAL(10,4),
                    ppo DECIMAL(10,4),
                    ppo_signal DECIMAL(10,4),
                    ppo_histogram DECIMAL(10,4),
                    roc_10 DECIMAL(10,4),
                    stoch_k DECIMAL(10,4),
                    stoch_d DECIMAL(10,4),
                    williams_r DECIMAL(10,4),
                    ultimate_osc DECIMAL(10,4),
                    rsi_14 DECIMAL(10,4),
                    atr_14 DECIMAL(10,4),
                    bb_upper DECIMAL(10,4),
                    bb_middle DECIMAL(10,4),
                    bb_lower DECIMAL(10,4),
                    bb_width DECIMAL(10,4),
                    bb_percent DECIMAL(10,4),
                    kc_upper DECIMAL(10,4),
                    kc_middle DECIMAL(10,4),
                    kc_lower DECIMAL(10,4),
                    dc_upper DECIMAL(10,4),
                    dc_middle DECIMAL(10,4),
                    dc_lower DECIMAL(10,4),
                    obv DECIMAL(20,4),
                    vwap DECIMAL(10,4),
                    mfi_14 DECIMAL(10,4),
                    sma_20 DECIMAL(10,4),
                    sma_50 DECIMAL(10,4),
                    sma_200 DECIMAL(10,4),
                    ema_12 DECIMAL(10,4),
                    ema_26 DECIMAL(10,4),
                    ema_50 DECIMAL(10,4),
                    ema_200 DECIMAL(10,4),
                    wma_20 DECIMAL(10,4),
                    hma_20 DECIMAL(10,4),
                    kama_20 DECIMAL(10,4),
                    tema_20 DECIMAL(10,4),
                    dema_20 DECIMAL(10,4),
                    macd DECIMAL(10,4),
                    macd_signal DECIMAL(10,4),
                    macd_histogram DECIMAL(10,4),
                    run_id VARCHAR(36),
                    params_hash VARCHAR(16),
                    data_quality_status VARCHAR(20) DEFAULT 'good',
                    nan_count INTEGER DEFAULT 0,
                    valid_rate DECIMAL(5,4) DEFAULT 1.0,
                    schema_version VARCHAR(10) DEFAULT 'v2',
                    algo_version VARCHAR(20) DEFAULT '2.0.0',
                    calculated_at TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                ) PARTITION BY RANGE (timestamp);
            """
                )
            )

            logger.info("✅ Партиции созданы")

            await session.commit()
            logger.info("✅ Миграция indicators завершена успешно!")

        except Exception as e:
            logger.error(f"❌ Ошибка при создании таблицы indicators: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    import asyncio

    asyncio.run(migrate_create_unified_indicators_table())
