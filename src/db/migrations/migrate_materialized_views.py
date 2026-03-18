#!/usr/bin/env python3
"""
Миграция для создания материализованных представлений и агрегаций.
Создает представления для часто используемых запросов и агрегаций.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_materialized_views() -> None:
    """
    Создает материализованные представления и агрегации.
    """
    logger.info("📊 Создаем материализованные представления...")

    async with get_db_session() as session:
        try:
            # 1. Представление для статистики по символам
            logger.info("🔄 Создаем представление статистики по символам...")
            symbol_stats_q = text(
                """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_symbol_stats AS
                SELECT
                    symbol,
                    timeframe,
                    COUNT(*) as total_records,
                    MIN(timestamp) as first_record,
                    MAX(timestamp) as last_record,
                    AVG(volume) as avg_volume,
                    AVG(high - low) as avg_spread,
                    AVG(close - open) as avg_change
                FROM ohlcv_p
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe;
            """
            )
            await session.execute(symbol_stats_q)
            await session.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_symbol_stats_symbol_timeframe
                    ON mv_symbol_stats (symbol, timeframe);
                    """
                )
            )
            logger.info("✅ Представление статистики по символам создано")

            # 2. Представление для последних цен
            logger.info("🔄 Создаем представление последних цен...")
            latest_prices_q = text(
                """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_latest_prices AS
                SELECT DISTINCT ON (symbol, timeframe)
                    symbol,
                    timeframe,
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM ohlcv_p
                ORDER BY symbol, timeframe, timestamp DESC;
            """
            )
            await session.execute(latest_prices_q)
            await session.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_prices_symbol_timeframe
                    ON mv_latest_prices (symbol, timeframe);
                    """
                )
            )
            logger.info("✅ Представление последних цен создано")

            # 3. Представление для агрегации по дням
            logger.info("🔄 Создаем представление дневной агрегации...")
            daily_agg_q = text(
                """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_aggregation AS
                SELECT
                    symbol,
                    DATE(TO_TIMESTAMP(timestamp)) as trade_date,
                    MIN(open) as day_open,
                    MAX(high) as day_high,
                    MIN(low) as day_low,
                    MAX(close) as day_close,
                    SUM(volume) as day_volume,
                    COUNT(*) as day_candles
                FROM ohlcv_p
                WHERE timeframe = '1H'
                GROUP BY symbol, DATE(TO_TIMESTAMP(timestamp))
                ORDER BY symbol, trade_date;
            """
            )
            await session.execute(daily_agg_q)
            await session.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_mv_daily_agg_symbol_date
                    ON mv_daily_aggregation (symbol, trade_date);
                    """
                )
            )
            logger.info("✅ Представление дневной агрегации создано")

            # 4. Представление для волатильности
            logger.info("🔄 Создаем представление волатильности...")
            volatility_q = text(
                """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_volatility AS
                SELECT
                    symbol,
                    timeframe,
                    DATE_TRUNC('day', TO_TIMESTAMP(timestamp)) as day,
                    AVG(ABS(close - open)) as avg_daily_change,
                    STDDEV(close - open) as volatility,
                    MAX(high - low) as max_spread,
                    MIN(high - low) as min_spread
                FROM ohlcv_p
                GROUP BY symbol, timeframe, DATE_TRUNC('day', TO_TIMESTAMP(timestamp))
                ORDER BY symbol, timeframe, day;
            """
            )
            await session.execute(volatility_q)
            await session.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_mv_volatility_symbol_timeframe_day
                    ON mv_volatility (symbol, timeframe, day);
                    """
                )
            )
            logger.info("✅ Представление волатильности создано")

            # 5. Представление для топ активных символов
            logger.info("🔄 Создаем представление топ активных символов...")
            top_symbols_q = text(
                """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_top_symbols AS
                SELECT
                    symbol,
                    COUNT(*) as total_records,
                    SUM(volume) as total_volume,
                    AVG(volume) as avg_volume,
                    MAX(timestamp) as last_activity
                FROM ohlcv_p
                WHERE timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '7 days')::BIGINT
                GROUP BY symbol
                ORDER BY total_volume DESC
                LIMIT 100;
            """
            )
            await session.execute(top_symbols_q)
            await session.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_mv_top_symbols_volume
                    ON mv_top_symbols (total_volume DESC);
                    """
                )
            )
            logger.info("✅ Представление топ символов создано")

            # 6. Представление для метрик качества данных
            logger.info("🔄 Создаем представление метрик качества данных...")
            data_quality_q = text(
                """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_data_quality AS
                SELECT
                    'ohlcv_p' as table_name,
                    COUNT(*) as total_records,
                    COUNT(DISTINCT symbol) as unique_symbols,
                    COUNT(DISTINCT timeframe) as unique_timeframes,
                    MIN(timestamp) as earliest_record,
                    MAX(timestamp) as latest_record,
                    COUNT(CASE WHEN volume < 0 THEN 1 END) as negative_volumes,
                    COUNT(CASE WHEN high < low THEN 1 END) as invalid_spreads,
                    COUNT(CASE WHEN timestamp IS NULL THEN 1 END) as null_timestamps
                FROM ohlcv_p
                UNION ALL
                SELECT
                    'indicators_p' as table_name,
                    COUNT(*) as total_records,
                    COUNT(DISTINCT symbol) as unique_symbols,
                    COUNT(DISTINCT timeframe) as unique_timeframes,
                    MIN(timestamp) as earliest_record,
                    MAX(timestamp) as latest_record,
                    0 as negative_volumes,
                    0 as invalid_spreads,
                    COUNT(CASE WHEN timestamp IS NULL THEN 1 END) as null_timestamps
                FROM indicators_p;
            """
            )
            await session.execute(data_quality_q)
            logger.info("✅ Представление качества данных создано")

            # 7. Создаем функцию для обновления представлений
            logger.info("🔄 Создаем функцию обновления представлений...")
            refresh_function_q = text(
                """
                CREATE OR REPLACE FUNCTION refresh_materialized_views()
                RETURNS void AS $$
                BEGIN
                    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_symbol_stats;
                    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_prices;
                    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_aggregation;
                    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_volatility;
                    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_top_symbols;
                    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_data_quality;
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(refresh_function_q)
            logger.info("✅ Функция обновления представлений создана")

            # 8. Создаем триггер для автоматического обновления
            logger.info("🔄 Создаем триггер для автоматического обновления...")
            trigger_q = text(
                """
                CREATE OR REPLACE FUNCTION trigger_refresh_views()
                RETURNS trigger AS $$
                BEGIN
                    -- Обновляем только критически важные представления
                    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_prices;
                    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_top_symbols;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(trigger_q)
            await session.execute(
                text("DROP TRIGGER IF EXISTS trigger_refresh_views_ohlcv ON ohlcv_p;")
            )
            await session.execute(
                text(
                    """
                    CREATE TRIGGER trigger_refresh_views_ohlcv
                        AFTER INSERT OR UPDATE OR DELETE ON ohlcv_p
                        FOR EACH STATEMENT
                        EXECUTE FUNCTION trigger_refresh_views();
                    """
                )
            )
            logger.info("✅ Триггер для автоматического обновления создан")

            await session.commit()

            logger.info("🎉 Все материализованные представления созданы успешно!")
            logger.info("📊 Созданные представления:")
            logger.info("   • mv_symbol_stats - статистика по символам")
            logger.info("   • mv_latest_prices - последние цены")
            logger.info("   • mv_daily_aggregation - дневная агрегация")
            logger.info("   • mv_volatility - волатильность")
            logger.info("   • mv_top_symbols - топ активных символов")
            logger.info("   • mv_data_quality - метрики качества данных")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при создании представлений: {e}")
            raise
