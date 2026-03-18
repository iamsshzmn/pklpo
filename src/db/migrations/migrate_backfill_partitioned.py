import asyncio
import logging
from datetime import datetime

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def get_table_column_mapping(session, table: str) -> dict:
    """
    Определяет маппинг колонок между старой и новой таблицей.
    Учитывает возможные различия в именах (timestamp/ts, instid/instId).
    """
    q = text(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = :table
        ORDER BY ordinal_position
    """
    )
    res = await session.execute(q, {"table": table})
    columns = [r[0] for r in res.fetchall()]

    # Определяем имя колонки времени
    time_column = None
    if "timestamp" in columns:
        time_column = "timestamp"
    elif "ts" in columns:
        time_column = "ts"

    # Определяем имя колонки ID инструмента (для instruments)
    id_column = None
    if "instid" in columns:
        id_column = "instid"
    elif "instId" in columns:
        id_column = "instId"

    return {"columns": columns, "time_column": time_column, "id_column": id_column}


async def get_data_range(
    session, table: str, time_column: str
) -> tuple[datetime | None, datetime | None]:
    """
    Получает диапазон дат в таблице для определения границ партиций.
    """
    q = text(
        f"""
        SELECT MIN({time_column}), MAX({time_column})
        FROM {table}
        WHERE {time_column} IS NOT NULL
    """
    )
    res = await session.execute(q)
    min_time, max_time = res.fetchone()

    return min_time, max_time


async def backfill_ohlcv_data(batch_size: int = 10000) -> None:
    """
    Переносит данные из ohlcv в ohlcv_p батчами.
    """
    logger.info("🔄 Начинаем перенос данных из ohlcv в ohlcv_p...")

    async with get_db_session() as session:
        # Получаем маппинг колонок
        old_mapping = await get_table_column_mapping(session, "ohlcv")
        new_mapping = await get_table_column_mapping(session, "ohlcv_p")

        logger.info(f"📋 Колонки в ohlcv: {old_mapping['columns']}")
        logger.info(f"📋 Колонки в ohlcv_p: {new_mapping['columns']}")

        if not old_mapping["time_column"]:
            logger.error("❌ Не найдена колонка времени в ohlcv")
            return

        time_col = old_mapping["time_column"]
        logger.info(f"⏰ Используем колонку времени: {time_col}")

        # Получаем диапазон дат
        min_time, max_time = await get_data_range(session, "ohlcv", time_col)
        if not min_time or not max_time:
            logger.warning("⚠️ Нет данных для переноса в ohlcv")
            return

        logger.info(f"📅 Диапазон данных: {min_time} - {max_time}")

        # Создаем маппинг колонок между старой и новой таблицей
        column_mapping = {
            "symbol": "symbol",
            "timeframe": "timeframe",
            "ts": "timestamp",  # Маппинг ts -> timestamp
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }

        # Получаем колонки для SELECT из старой таблицы
        select_columns = list(column_mapping.keys())
        select_columns_str = ", ".join(select_columns)

        # Получаем колонки для INSERT в новую таблицу
        insert_columns = list(column_mapping.values())
        insert_columns_str = ", ".join(insert_columns)

        logger.info(f"🔗 Маппинг колонок: {column_mapping}")
        logger.info(f"📤 SELECT колонки: {select_columns}")
        logger.info(f"📥 INSERT колонки: {insert_columns}")

        # Считаем общее количество записей (только с непустым timestamp)
        count_q = text(f"SELECT COUNT(*) FROM ohlcv WHERE {time_col} IS NOT NULL")
        total_count = await session.execute(count_q)
        total_records = total_count.scalar()

        logger.info(f"📊 Всего записей для переноса: {total_records}")

        if total_records == 0:
            logger.info("✅ Нет данных для переноса")
            return

        # Переносим данные батчами
        offset = 0
        transferred = 0

        while offset < total_records:
            # Получаем батч данных (только с непустым timestamp)
            select_q = text(
                f"""
                SELECT {select_columns_str}
                FROM ohlcv
                WHERE {time_col} IS NOT NULL
                ORDER BY {time_col}
                LIMIT :limit OFFSET :offset
            """
            )

            batch_data = await session.execute(
                select_q, {"limit": batch_size, "offset": offset}
            )

            rows = batch_data.fetchall()
            if not rows:
                break

            # Вставляем батч в новую таблицу
            placeholders = ", ".join([f":{i}" for i in range(len(insert_columns))])
            insert_q = text(
                f"""
                INSERT INTO ohlcv_p ({insert_columns_str})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            )

            for row in rows:
                params = {str(i): value for i, value in enumerate(row)}
                await session.execute(insert_q, params)

            await session.commit()

            transferred += len(rows)
            offset += batch_size

            logger.info(
                f"📦 Перенесено {transferred}/{total_records} записей ({(transferred/total_records)*100:.1f}%)"
            )

        logger.info(f"✅ Перенос ohlcv завершен: {transferred} записей")


async def backfill_indicators_data(batch_size: int = 10000) -> None:
    """
    Переносит данные из indicators в indicators_p батчами.
    """
    logger.info("🔄 Начинаем перенос данных из indicators в indicators_p...")

    async with get_db_session() as session:
        # Получаем маппинг колонок
        old_mapping = await get_table_column_mapping(session, "indicators")
        new_mapping = await get_table_column_mapping(session, "indicators_p")

        logger.info(f"📋 Колонки в indicators: {old_mapping['columns']}")
        logger.info(f"📋 Колонки в indicators_p: {new_mapping['columns']}")

        if not old_mapping["time_column"]:
            logger.error("❌ Не найдена колонка времени в indicators")
            return

        time_col = old_mapping["time_column"]
        logger.info(f"⏰ Используем колонку времени: {time_col}")

        # Получаем диапазон дат
        min_time, max_time = await get_data_range(session, "indicators", time_col)
        if not min_time or not max_time:
            logger.warning("⚠️ Нет данных для переноса в indicators")
            return

        logger.info(f"📅 Диапазон данных: {min_time} - {max_time}")

        # Создаем маппинг колонок между старой и новой таблицей
        column_mapping = {
            "symbol": "symbol",
            "timeframe": "timeframe",
            "ts": "timestamp",  # Маппинг ts -> timestamp
        }

        # Получаем колонки для SELECT из старой таблицы
        select_columns = list(column_mapping.keys())
        select_columns_str = ", ".join(select_columns)

        # Получаем колонки для INSERT в новую таблицу
        insert_columns = list(column_mapping.values())
        insert_columns_str = ", ".join(insert_columns)

        logger.info(f"🔗 Маппинг колонок: {column_mapping}")
        logger.info(f"📤 SELECT колонки: {select_columns}")
        logger.info(f"📥 INSERT колонки: {insert_columns}")

        # Считаем общее количество записей (только с непустым timestamp)
        count_q = text(f"SELECT COUNT(*) FROM indicators WHERE {time_col} IS NOT NULL")
        total_count = await session.execute(count_q)
        total_records = total_count.scalar()

        logger.info(f"📊 Всего записей для переноса: {total_records}")

        if total_records == 0:
            logger.info("✅ Нет данных для переноса")
            return

        # Переносим данные батчами
        offset = 0
        transferred = 0

        while offset < total_records:
            # Получаем батч данных (только с непустым timestamp)
            select_q = text(
                f"""
                SELECT {select_columns_str}
                FROM indicators
                WHERE {time_col} IS NOT NULL
                ORDER BY {time_col}
                LIMIT :limit OFFSET :offset
            """
            )

            batch_data = await session.execute(
                select_q, {"limit": batch_size, "offset": offset}
            )

            rows = batch_data.fetchall()
            if not rows:
                break

            # Вставляем батч в новую таблицу
            placeholders = ", ".join([f":{i}" for i in range(len(insert_columns))])
            insert_q = text(
                f"""
                INSERT INTO indicators_p ({insert_columns_str})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            )

            for row in rows:
                params = {str(i): value for i, value in enumerate(row)}
                await session.execute(insert_q, params)

            await session.commit()

            transferred += len(rows)
            offset += batch_size

            logger.info(
                f"📦 Перенесено {transferred}/{total_records} записей ({(transferred/total_records)*100:.1f}%)"
            )

        logger.info(f"✅ Перенос indicators завершен: {transferred} записей")


async def create_views_for_smooth_transition() -> None:
    """
    Создает VIEW для плавного перехода от старых таблиц к новым.
    """
    logger.info("🔄 Создаем VIEW для плавного перехода...")

    async with get_db_session() as session:
        # Создаем VIEW для ohlcv
        ohlcv_view_q = text(
            """
            CREATE OR REPLACE VIEW ohlcv_view AS
            SELECT * FROM ohlcv_p
            UNION ALL
            SELECT * FROM ohlcv
            WHERE timestamp NOT IN (SELECT timestamp FROM ohlcv_p)
        """
        )

        try:
            await session.execute(ohlcv_view_q)
            logger.info("✅ Создан VIEW ohlcv_view")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось создать ohlcv_view: {e}")

        # Создаем VIEW для indicators
        indicators_view_q = text(
            """
            CREATE OR REPLACE VIEW indicators_view AS
            SELECT * FROM indicators_p
            UNION ALL
            SELECT * FROM indicators
            WHERE timestamp NOT IN (SELECT timestamp FROM indicators_p)
        """
        )

        try:
            await session.execute(indicators_view_q)
            logger.info("✅ Создан VIEW indicators_view")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось создать indicators_view: {e}")

        await session.commit()


async def generate_maintenance_recommendations() -> None:
    """
    Генерирует рекомендации по обслуживанию базы данных.
    """
    logger.info("📋 Рекомендации по обслуживанию базы данных:")
    logger.info("")
    logger.info("1. VACUUM и ANALYZE:")
    logger.info("   VACUUM ANALYZE ohlcv_p;")
    logger.info("   VACUUM ANALYZE indicators_p;")
    logger.info("")
    logger.info("2. Мониторинг партиций:")
    logger.info("   SELECT schemaname, tablename, attname, n_distinct, correlation")
    logger.info("   FROM pg_stats WHERE tablename LIKE '%_p';")
    logger.info("")
    logger.info("3. Проверка размера таблиц:")
    logger.info(
        "   SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))"
    )
    logger.info(
        "   FROM pg_tables WHERE tablename IN ('ohlcv', 'ohlcv_p', 'indicators', 'indicators_p');"
    )
    logger.info("")
    logger.info("4. Удаление старых таблиц (после проверки):")
    logger.info("   DROP TABLE ohlcv; -- только после полной проверки")
    logger.info("   DROP TABLE indicators; -- только после полной проверки")


async def run_backfill_migration() -> None:
    """
    Основная функция для выполнения backfill миграции.
    """
    logger.info("🚀 Начинаем backfill миграцию...")

    try:
        # Переносим данные
        await backfill_ohlcv_data()
        await backfill_indicators_data()

        # Создаем VIEW для плавного перехода
        await create_views_for_smooth_transition()

        # Генерируем рекомендации
        await generate_maintenance_recommendations()

        logger.info("✅ Backfill миграция завершена успешно!")

    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении backfill миграции: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_backfill_migration())
