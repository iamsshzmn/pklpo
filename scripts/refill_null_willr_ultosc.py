"""
Скрипт для пересчёта записей с NULL значениями для willr и ultosc.
"""

import asyncio
import logging

import pandas as pd
from sqlalchemy import text

from src.features import compute_features
from src.features.specs import FEATURE_SPECS
from src.utils.session_utils import get_db_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def refill_null_indicators(
    symbol: str, timeframe: str, indicators: list[str]
) -> None:
    """Пересчитать записи с NULL для указанных индикаторов."""
    logger.info(f"🔄 Пересчёт NULL значений для {symbol} {timeframe}: {indicators}")

    async with get_db_session() as session:
        # Находим записи с NULL
        conditions = " OR ".join([f"i.{ind} IS NULL" for ind in indicators])
        query = text(
            f"""
            SELECT DISTINCT i.timestamp
            FROM indicators i
            INNER JOIN swap_ohlcv_p o ON
                i.symbol = o.symbol AND
                i.timeframe = o.timeframe AND
                i.timestamp = o.timestamp
            WHERE i.symbol = :symbol
                AND i.timeframe = :timeframe
                AND ({conditions})
            ORDER BY i.timestamp
        """
        )
        result = await session.execute(
            query, {"symbol": symbol, "timeframe": timeframe}
        )
        null_timestamps = [row[0] for row in result.fetchall()]

        if not null_timestamps:
            logger.info(f"✅ Нет записей с NULL для {indicators}")
            return

        logger.info(f"📊 Найдено {len(null_timestamps)} записей с NULL")

        # Получаем OHLCV данные с окном для расчёта
        max_window = 100
        min_ts = min(null_timestamps) - max_window * 60 * 1000
        max_ts = max(null_timestamps) + 60 * 1000

        ohlcv_query = text(
            """
            SELECT
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                timestamp / 1000 as ts
            FROM swap_ohlcv_p
            WHERE symbol = :symbol
                AND timeframe = :timeframe
                AND timestamp >= :min_ts
                AND timestamp <= :max_ts
            ORDER BY timestamp
        """
        )
        ohlcv_result = await session.execute(
            ohlcv_query,
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "min_ts": min_ts,
                "max_ts": max_ts,
            },
        )
        ohlcv_rows = ohlcv_result.fetchall()

        if not ohlcv_rows:
            logger.warning("⚠️ Нет OHLCV данных для пересчёта")
            return

        # Преобразуем в DataFrame
        df_ohlcv = pd.DataFrame(
            ohlcv_rows,
            columns=["timestamp", "open", "high", "low", "close", "volume", "ts"],
        )
        df_ohlcv["ts"] = df_ohlcv["timestamp"] / 1000

        logger.info(f"📊 Загружено {len(df_ohlcv)} OHLCV записей")

        # Рассчитываем индикаторы
        refill_specs = [
            FEATURE_SPECS[ind] for ind in indicators if ind in FEATURE_SPECS
        ]
        if not refill_specs:
            logger.warning(f"⚠️ Некорректные индикаторы: {indicators}")
            return

        features_df = compute_features(
            df_ohlcv, specs=refill_specs, volatility_normalize=False
        )

        # Обновляем записи
        updated_count = 0
        for ind in indicators:
            if ind not in features_df.columns:
                logger.warning(f"⚠️ Индикатор {ind} не рассчитан")
                continue

            for ts in null_timestamps:
                matching = df_ohlcv[df_ohlcv["timestamp"] == ts]
                if len(matching) == 0:
                    continue

                df_idx = matching.index[0]
                if df_idx >= len(features_df):
                    continue

                value = features_df.iloc[df_idx][ind]
                if pd.isna(value):
                    continue

                update_query = text(
                    f"""
                    UPDATE indicators
                    SET {ind} = :value
                    WHERE symbol = :symbol
                        AND timeframe = :timeframe
                        AND timestamp = :timestamp
                        AND {ind} IS NULL
                """
                )
                await session.execute(
                    update_query,
                    {
                        "value": float(value),
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "timestamp": ts,
                    },
                )
                updated_count += 1

        await session.commit()
        logger.info(f"✅ Обновлено {updated_count} записей")


async def main():
    """Основная функция."""
    await refill_null_indicators("BTC-USDT-SWAP", "1m", ["willr", "ultosc"])


if __name__ == "__main__":
    asyncio.run(main())
