import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import text

from src.database import get_async_session


async def migrate_create_signals_detailed():
    """Создает таблицу signals_detailed для детализированного хранения сигналов"""

    async for session in get_async_session():
        try:
            print("🔧 Создаем таблицу signals_detailed...")

            # Создаем таблицу signals_detailed
            create_table_query = text(
                """
                CREATE TABLE IF NOT EXISTS signals_detailed (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    ts BIGINT NOT NULL,
                    signal SMALLINT NOT NULL,
                    total_score NUMERIC,

                    -- Текстовые сигналы по правилам
                    sma50_sma200 TEXT,
                    ema21_sma50 TEXT,
                    macd TEXT,
                    rsi14 TEXT,
                    bollinger TEXT,
                    stochastic TEXT,
                    adx14 TEXT,
                    ichimoku TEXT,
                    keltner TEXT,
                    volume_obv_cmf TEXT,

                    -- Числовые scores по правилам
                    sma50_sma200_score NUMERIC,
                    ema21_sma50_score NUMERIC,
                    macd_score NUMERIC,
                    rsi14_score NUMERIC,
                    bollinger_score NUMERIC,
                    stochastic_score NUMERIC,
                    adx14_score NUMERIC,
                    ichimoku_score NUMERIC,
                    keltner_score NUMERIC,
                    volume_obv_cmf_score NUMERIC,

                    created_at TIMESTAMP,

                    PRIMARY KEY (symbol, timeframe, ts)
                )
            """
            )

            await session.execute(create_table_query)

            # Создаем индексы для быстрого поиска
            print("📊 Создаем индексы...")

            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_symbol_timeframe ON signals_detailed(symbol, timeframe)",
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_ts ON signals_detailed(ts)",
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_signal ON signals_detailed(signal)",
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_sma50_sma200 ON signals_detailed(sma50_sma200)",
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_macd ON signals_detailed(macd)",
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_rsi14 ON signals_detailed(rsi14)",
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_bollinger ON signals_detailed(bollinger)",
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_keltner ON signals_detailed(keltner)",
            ]

            for index_query in indexes:
                await session.execute(text(index_query))

            await session.commit()
            print("✅ Таблица signals_detailed создана успешно!")

            # Создаем таблицу справочника кодов
            print("🔧 Создаем таблицу signal_rule_codes...")

            create_codes_table_query = text(
                """
                CREATE TABLE IF NOT EXISTS signal_rule_codes (
                    code SMALLINT PRIMARY KEY,
                    rule_name TEXT NOT NULL,
                    description TEXT
                )
            """
            )

            await session.execute(create_codes_table_query)

            # Заполняем справочник базовыми кодами
            print("📝 Заполняем справочник кодов...")

            rule_codes = [
                # SMA50 vs SMA200
                (-1, "sma50_sma200", "SMA50 < SMA200 (bearish)"),
                (0, "sma50_sma200", "SMA50 = SMA200 (neutral)"),
                (1, "sma50_sma200", "SMA50 > SMA200 (bullish)"),
                # EMA21 vs SMA50
                (-1, "ema21_sma50", "Close < EMA21 < SMA50 (downtrend)"),
                (0, "ema21_sma50", "Neutral EMA21/SMA50"),
                (1, "ema21_sma50", "Close > EMA21 > SMA50 (uptrend)"),
                # MACD
                (-1, "macd", "MACD < Signal (bearish)"),
                (0, "macd", "MACD = Signal (neutral)"),
                (1, "macd", "MACD > Signal (bullish)"),
                # RSI14
                (-1, "rsi14", "RSI14 oversold (<=30)"),
                (0, "rsi14", "RSI14 neutral (30-70)"),
                (1, "rsi14", "RSI14 overbought (>=70)"),
                # Bollinger Bands
                (-1, "bollinger", "Close below BB lower band (oversold)"),
                (0, "bollinger", "Close within BB bands (neutral)"),
                (1, "bollinger", "Close above BB upper band (overbought)"),
                # Stochastic
                (-1, "stochastic", "Stochastic oversold (K<20)"),
                (0, "stochastic", "Stochastic neutral (20-80)"),
                (1, "stochastic", "Stochastic overbought (K>80)"),
                # ADX14
                (-1, "adx14", "ADX14 weak trend (<25)"),
                (0, "adx14", "ADX14 moderate trend (25-50)"),
                (1, "adx14", "ADX14 strong trend (>50)"),
                # Ichimoku
                (-1, "ichimoku", "Close below Kijun (bearish)"),
                (0, "ichimoku", "Close near Kijun (neutral)"),
                (1, "ichimoku", "Close above Kijun (bullish)"),
                # Keltner Channel
                (-1, "keltner", "Close below KC lower band (oversold)"),
                (0, "keltner", "Close within KC bands (neutral)"),
                (1, "keltner", "Close above KC upper band (overbought)"),
                # Volume OBV/CMF
                (-1, "volume_obv_cmf", "Volume indicators bearish"),
                (0, "volume_obv_cmf", "Volume indicators neutral"),
                (1, "volume_obv_cmf", "Volume indicators bullish"),
            ]

            for code, rule_name, description in rule_codes:
                insert_query = text(
                    """
                    INSERT INTO signal_rule_codes (code, rule_name, description)
                    VALUES (:code, :rule_name, :description)
                    ON CONFLICT (code) DO NOTHING
                """
                )
                await session.execute(
                    insert_query,
                    {"code": code, "rule_name": rule_name, "description": description},
                )

            await session.commit()
            print("✅ Справочник кодов заполнен!")

        except Exception as e:
            print(f"❌ Ошибка при миграции: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_create_signals_detailed())
