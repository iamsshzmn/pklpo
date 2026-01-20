"""
Тестовый скрипт для проверки UPSERT с минимальным набором данных.

Использование:
    python scripts/test_upsert.py --symbols BTC-USDT-SWAP --timeframes 1m --limit 10
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import get_async_session
from src.features.core.calculation import compute_features
from src.features.infrastructure.persistence.inserter import insert_indicators
from src.features.infrastructure.persistence.schema_checker import (
    reflect_indicators_table,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_upsert(
    symbol: str = "BTC-USDT-SWAP",
    timeframe: str = "1m",
    limit: int = 10,
) -> None:
    """
    Тестирует UPSERT с минимальным набором данных.

    Args:
        symbol: Символ для тестирования
        timeframe: Таймфрейм
        limit: Количество баров
    """
    logger.info("=" * 80)
    logger.info("TEST UPSERT - Minimal reproducible case")
    logger.info("=" * 80)
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Timeframe: {timeframe}")
    logger.info(f"Limit: {limit}")

    async for session in get_async_session():
        try:
            # 1. Загружаем OHLCV данные
            logger.info("\n[1] Loading OHLCV data...")
            from sqlalchemy import text

            if limit is not None:
                query = text(
                    """
                    SELECT open, high, low, close, volume, timestamp
                    FROM swap_ohlcv_p
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """
                )
                params = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
            else:
                query = text(
                    """
                    SELECT open, high, low, close, volume, timestamp
                    FROM swap_ohlcv_p
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    ORDER BY timestamp DESC
                """
                )
                params = {"symbol": symbol, "timeframe": timeframe}

            result = await session.execute(query, params)
            rows = result.fetchall()

            if not rows:
                logger.error("No OHLCV data found")
                return

            # Преобразуем в DataFrame
            import pandas as pd

            ohlcv_df = pd.DataFrame(
                [
                    {
                        "open": float(row.open),
                        "high": float(row.high),
                        "low": float(row.low),
                        "close": float(row.close),
                        "volume": float(row.volume),
                        "timestamp": row.timestamp,
                    }
                    for row in reversed(rows)  # Восстанавливаем хронологический порядок
                ]
            )

            if ohlcv_df is None or ohlcv_df.empty:
                logger.error("No OHLCV data found")
                return

            logger.info(f"Loaded {len(ohlcv_df)} bars")
            logger.info(f"Columns: {list(ohlcv_df.columns)}")
            logger.info(f"First bar:\n{ohlcv_df.head(1)}")

            # 2. Вычисляем индикаторы
            logger.info("\n[2] Computing features...")
            features_df = compute_features(ohlcv_df, specs=None)

            if features_df is None or features_df.empty:
                logger.error("No features computed")
                return

            logger.info(f"Computed {len(features_df)} rows with features")
            logger.info(
                f"Feature columns: {len([c for c in features_df.columns if c not in ['symbol', 'timeframe', 'timestamp']])}"
            )
            logger.info(f"First row sample:\n{features_df.head(1)}")

            # 3. Проверяем типы данных перед нормализацией
            logger.info("\n[3] Checking data types before normalization...")
            numeric_cols = [
                c
                for c in features_df.columns
                if c not in ["symbol", "timeframe", "timestamp", "calculated_at"]
            ]

            import numpy as np
            import pandas as pd

            logger.info(f"Checking {len(numeric_cols)} numeric columns...")
            for col in numeric_cols[:10]:  # Первые 10 для примера
                dtype = features_df[col].dtype
                non_null = features_df[col].notna().sum()
                logger.info(f"  {col}: dtype={dtype}, non-null={non_null}")

                # Проверяем строки в числовых колонках
                if features_df[col].dtype == "object":
                    string_count = (
                        features_df[col].map(lambda x: isinstance(x, str)).sum()
                    )
                    if string_count > 0:
                        logger.warning(
                            f"  ⚠️  {col}: {string_count} string values found!"
                        )
                        logger.warning(
                            f"     Sample: {features_df[col][features_df[col].map(lambda x: isinstance(x, str))].head(3).tolist()}"
                        )

                # Проверяем NaN/inf
                if pd.api.types.is_numeric_dtype(features_df[col]):
                    inf_count = np.isinf(features_df[col]).sum()
                    if inf_count > 0:
                        logger.warning(f"  ⚠️  {col}: {inf_count} inf values found!")

            # 4. Отражение таблицы
            logger.info("\n[4] Reflecting indicators table...")
            indicators_table = await reflect_indicators_table(session)
            logger.info(f"Table reflected: {indicators_table.name}")
            logger.info(f"Columns: {len(indicators_table.columns)}")

            # 5. Вставка индикаторов
            logger.info("\n[5] Inserting indicators...")
            saved_count = await insert_indicators(
                session=session,
                ind_df=features_df,
                symbol=symbol,
                timeframe=timeframe,
            )

            logger.info(f"\n✅ SUCCESS: Saved {saved_count} records")

        except Exception as e:
            import traceback

            logger.error("=" * 80)
            logger.error("TEST FAILED")
            logger.error("=" * 80)
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            logger.error("=" * 80)
            raise


def main() -> None:
    """Точка входа."""
    import argparse

    parser = argparse.ArgumentParser(description="Test UPSERT with minimal data")
    parser.add_argument(
        "--symbols", type=str, default="BTC-USDT-SWAP", help="Symbol to test"
    )
    parser.add_argument(
        "--timeframes", type=str, default="1m", help="Timeframe to test"
    )
    parser.add_argument("--limit", type=int, default=10, help="Number of bars")

    args = parser.parse_args()

    asyncio.run(
        test_upsert(
            symbol=args.symbols,
            timeframe=args.timeframes,
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
