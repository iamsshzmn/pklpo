"""
Скрипт для проверки пустых колонок в таблице indicators.

Использование:
    python scripts/check_empty_columns.py
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_empty_columns():
    """Проверяет пустые колонки в таблице indicators."""
    async with get_db_session() as session:
        try:
            # 1) Список всех колонок и их типов
            logger.info("Получение списка всех колонок...")
            get_columns = text(
                """
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'indicators'
                  AND column_name NOT IN ('symbol', 'timeframe', 'timestamp', 'calculated_at', 'created_at', 'updated_at')
                ORDER BY column_name
            """
            )
            result = await session.execute(get_columns)
            all_columns = result.all()

            logger.info(f"\n📊 Всего колонок (кроме служебных): {len(all_columns)}")
            logger.info("Первые 20 колонок:")
            for col_name, data_type, is_nullable, default in all_columns[:20]:
                logger.info(f"  - {col_name}: {data_type} (nullable: {is_nullable})")

            # 2) Заполненность критических колонок за последние 2 дня
            logger.info("\nПроверка заполненности критических колонок...")
            two_days_ago = int(
                (datetime.utcnow() - timedelta(days=2)).timestamp() * 1000
            )

            check_fill = text(
                """
                SELECT
                    symbol,
                    timeframe,
                    100.0 * SUM((bb_upper IS NOT NULL)::int) / COUNT(*) AS bb_upper_fill,
                    100.0 * SUM((bb_middle IS NOT NULL)::int) / COUNT(*) AS bb_middle_fill,
                    100.0 * SUM((bb_lower IS NOT NULL)::int) / COUNT(*) AS bb_lower_fill,
                    100.0 * SUM((hlc3 IS NOT NULL)::int) / COUNT(*) AS hlc3_fill,
                    100.0 * SUM((hl2 IS NOT NULL)::int) / COUNT(*) AS hl2_fill,
                    100.0 * SUM((ohlc4 IS NOT NULL)::int) / COUNT(*) AS ohlc4_fill,
                    100.0 * SUM((ichimoku_tenkan IS NOT NULL)::int) / COUNT(*) AS ichimoku_tenkan_fill,
                    100.0 * SUM((ichimoku_kijun IS NOT NULL)::int) / COUNT(*) AS ichimoku_kijun_fill,
                    COUNT(*) as total_rows
                FROM indicators
                WHERE timestamp >= :two_days_ago
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
            """
            )
            result = await session.execute(check_fill, {"two_days_ago": two_days_ago})
            fill_rates = result.all()

            if fill_rates:
                logger.info("\n📈 Заполненность критических колонок (последние 2 дня):")
                for row in fill_rates:
                    logger.info(
                        f"  {row[0]} {row[1]}: "
                        f"bb_upper={row[2]:.1f}%, "
                        f"bb_middle={row[3]:.1f}%, "
                        f"bb_lower={row[4]:.1f}%, "
                        f"hlc3={row[5]:.1f}%, "
                        f"hl2={row[6]:.1f}%, "
                        f"ohlc4={row[7]:.1f}%, "
                        f"ichimoku_tenkan={row[8]:.1f}%, "
                        f"ichimoku_kijun={row[9]:.1f}% "
                        f"(всего строк: {row[10]})"
                    )
            else:
                logger.warning("⚠️ Нет данных за последние 2 дня")

            # 3) Поиск полностью пустых колонок
            logger.info("\nПоиск полностью пустых колонок...")
            # Проверяем только критические колонки
            critical_cols = [
                "bb_upper",
                "bb_middle",
                "bb_lower",
                "hlc3",
                "hl2",
                "ohlc4",
                "ichimoku_tenkan",
                "ichimoku_kijun",
                "ichimoku_senkou_a",
                "ichimoku_senkou_b",
                "ichimoku_chikou",
            ]

            empty_cols = []
            for col in critical_cols:
                check_empty = text(
                    f"""
                    SELECT COUNT(*)
                    FROM indicators
                    WHERE timestamp >= :two_days_ago
                      AND {col} IS NOT NULL
                """
                )
                result = await session.execute(
                    check_empty, {"two_days_ago": two_days_ago}
                )
                count = result.scalar() or 0

                if count == 0:
                    empty_cols.append(col)

            if empty_cols:
                logger.warning(f"\n⚠️ Полностью пустые колонки: {', '.join(empty_cols)}")
            else:
                logger.info("\n✅ Все критические колонки имеют данные")

        except Exception as e:
            logger.error(f"❌ Ошибка при проверке: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(check_empty_columns())
