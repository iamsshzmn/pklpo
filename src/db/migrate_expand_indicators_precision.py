"""
Миграция 230: Расширение типов колонок indicators для поддержки больших значений.

Проблема: DECIMAL(10,4) ограничивает значения до ~1e6, что недостаточно для
объёмных метрик (OBV, AD/ADOSC, PVI/NVI, PVT, volume_sma20, pdist и т.п.)
на минутных свечах.

Решение: Расширяем все индикаторные колонки до NUMERIC(38,12) для поддержки
значений до 1e26 с точностью до 12 знаков после запятой.
"""

import logging
from pathlib import Path

import yaml
from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


def _load_indicator_columns() -> list[str]:
    """Загружает список всех индикаторных колонок из YAML-схемы."""
    schema_path = Path("src/features/schema/indicators_schema_complete.yml")

    try:
        with open(schema_path, encoding="utf-8") as f:
            schema = yaml.safe_load(f)

        columns = []

        # Добавляем колонки из всех групп индикаторов
        if "indicators" in schema:
            for group_indicators in schema["indicators"].values():
                if isinstance(group_indicators, list):
                    for indicator in group_indicators:
                        if isinstance(indicator, dict) and "name" in indicator:
                            columns.append(indicator["name"])

        logger.info(f"Загружено {len(columns)} индикаторных колонок из схемы")
        return columns

    except Exception as e:
        logger.error(f"Ошибка загрузки схемы: {e}")
        raise


async def _get_all_partitions(session) -> list[str]:
    """Получает список всех партиций indicators_p."""
    query = text(
        """
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE tablename LIKE 'indicators_p_%'
        ORDER BY tablename;
    """
    )

    result = await session.execute(query)
    partitions = [row.tablename for row in result.fetchall()]
    logger.info(f"Найдено {len(partitions)} партиций indicators_p")
    return partitions


async def _alter_column_type(
    session, table_name: str, column_name: str, new_type: str
) -> None:
    """Изменяет тип колонки в таблице (идемпотентно)."""
    # Проверяем текущий тип колонки
    check_query = text(
        """
        SELECT data_type, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_name = :table_name
          AND column_name = :column_name;
    """
    )

    result = await session.execute(
        check_query, {"table_name": table_name, "column_name": column_name}
    )
    row = result.fetchone()

    if not row:
        logger.warning(
            f"Column {column_name} not found in table {table_name}, skipping"
        )
        return

    current_type = row.data_type
    current_precision = row.numeric_precision
    current_scale = row.numeric_scale

    # Если тип уже NUMERIC с достаточной точностью, пропускаем
    if current_type == "numeric" and current_precision and current_precision >= 38:
        logger.debug(
            f"Колонка {table_name}.{column_name} уже имеет тип "
            f"NUMERIC({current_precision},{current_scale}), пропускаем"
        )
        return

    # Выполняем ALTER COLUMN
    alter_query = text(
        f'ALTER TABLE "{table_name}" '
        f'ALTER COLUMN "{column_name}" TYPE {new_type} USING "{column_name}"::numeric'
    )

    try:
        await session.execute(alter_query)
        logger.debug(f"Обновлён тип {table_name}.{column_name} -> {new_type}")
    except Exception as e:
        logger.error(f"Ошибка обновления {table_name}.{column_name}: {e}")
        raise


async def migrate_expand_indicators_precision() -> None:
    """
    Расширяет типы всех индикаторных колонок до NUMERIC(38,12).

    Обрабатывает:
    - Таблицу indicators (если существует)
    - Все партиции indicators_p_*
    """
    logger.info("🔄 Начинаем миграцию расширения типов колонок indicators...")

    # Загружаем список индикаторных колонок
    indicator_columns = _load_indicator_columns()

    if not indicator_columns:
        logger.warning("Не найдено индикаторных колонок в схеме, пропускаем миграцию")
        return

    new_type = "NUMERIC(38,12)"

    async with get_db_session() as session:
        # 1. Обновляем основную таблицу indicators (если существует)
        logger.info("Проверяем наличие таблицы indicators...")
        check_table = text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'indicators'
            );
        """
        )
        result = await session.execute(check_table)
        has_indicators = result.scalar()

        if has_indicators:
            logger.info(
                f"Обновляем таблицу indicators ({len(indicator_columns)} колонок)..."
            )
            for col in indicator_columns:
                await _alter_column_type(session, "indicators", col, new_type)
            await session.commit()
            logger.info("✅ Таблица indicators обновлена")
        else:
            logger.info("Таблица indicators не найдена, пропускаем")

        # 2. Обновляем родительскую таблицу indicators_p (если существует)
        logger.info("Проверяем наличие таблицы indicators_p...")
        check_table_p = text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'indicators_p'
            );
        """
        )
        result = await session.execute(check_table_p)
        has_indicators_p = result.scalar()

        if has_indicators_p:
            logger.info(
                f"Обновляем родительскую таблицу indicators_p ({len(indicator_columns)} колонок)..."
            )
            for col in indicator_columns:
                await _alter_column_type(session, "indicators_p", col, new_type)
            await session.commit()
            logger.info("✅ Родительская таблица indicators_p обновлена")
        else:
            logger.info("Таблица indicators_p не найдена, пропускаем")

        # 3. Обновляем все партиции indicators_p
        logger.info("Обновляем партиции indicators_p...")
        partitions = await _get_all_partitions(session)

        if not partitions:
            logger.warning("Партиции indicators_p не найдены")
        else:
            for partition in partitions:
                logger.info(f"Обновляем партицию {partition}...")
                for col in indicator_columns:
                    await _alter_column_type(session, partition, col, new_type)
                await session.commit()
                logger.info(f"✅ Партиция {partition} обновлена")

        total_tables = (1 if has_indicators else 0) + (1 if has_indicators_p else 0)
        logger.info(
            f"✅ Миграция завершена: обновлено {len(indicator_columns)} колонок "
            f"в {total_tables} таблице(ах) и {len(partitions)} партициях"
        )
