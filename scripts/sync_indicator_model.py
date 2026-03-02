"""
Скрипт для синхронизации модели Indicator с реальной схемой БД.
Генерирует Python-код колонок на основе information_schema.
"""

import asyncio
import os

from sqlalchemy import create_engine, text


async def main():
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://pklpo_user:strongpassword@localhost:5432/pklpo"
    )
    # Переключаем на синхронный драйвер для простоты
    database_url_sync = database_url.replace("+asyncpg", "")

    engine = create_engine(database_url_sync)

    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'indicators' AND table_schema = 'public'
            ORDER BY ordinal_position
        """
            )
        )

        columns = result.fetchall()

        print("# Auto-generated columns for Indicator model")
        print("# Generated from public.indicators schema\n")

        type_mapping = {
            "bigint": "BigInteger",
            "numeric": "Numeric",
            "character varying": "String",
            "smallint": "SmallInteger",
            "timestamp with time zone": "DateTime(timezone=True)",
            "timestamp without time zone": "DateTime",
            "double precision": "Float",
        }

        pk_cols = {"symbol", "timeframe", "timestamp"}

        for col_name, data_type, is_nullable in columns:
            if col_name in pk_cols:
                continue  # PK уже определены

            sql_type = type_mapping.get(data_type, "String")
            nullable = "True" if is_nullable == "YES" else "False"

            print(f"    {col_name} = Column({sql_type}, nullable={nullable})")

    engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
