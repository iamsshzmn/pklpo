import logging

from sqlalchemy import MetaData, Table, inspect, text

from src.models import INDICATORS_TABLE_NAME


async def ensure_columns(session, table_name: str, columns: list[str]):
    """
    Создаёт недостающие NUMERIC-колонки в `table_name`.
    • работает с AsyncSession
    • безопасен при параллельных стартах (ловит duplicate column)
    """
    # 1. Получаем raw-connection, потому что инспекция требует именно его
    conn = await session.connection()

    def _get_cols(sync_conn):
        insp = inspect(sync_conn)
        return {c["name"] for c in insp.get_columns(table_name)}

    existing = await conn.run_sync(_get_cols)

    # 2. Вычисляем, какие колонки нужно добавить
    todo = [c for c in columns if c not in existing and c not in ("ts",)]

    if not todo:
        return  # всё уже есть

    # 3. ALTER TABLE для каждой новой колонки
    for col in todo:
        ddl = text(f'ALTER TABLE {table_name} ADD COLUMN "{col}" NUMERIC')
        try:
            await session.execute(ddl)
            logging.info("Добавлена колонка %s.%s", table_name, col)
        except Exception as e:
            # если другой процесс успел первым
            if "duplicate column" not in str(e).lower():
                raise

    await session.commit()


def get_indicators_table():
    """
    Возвращает объект целевой таблицы indicators для использования в запросах.

    Returns:
        Table: Объект таблицы indicators
    """
    metadata = MetaData()
    return Table(INDICATORS_TABLE_NAME, metadata, autoload_with=None)
