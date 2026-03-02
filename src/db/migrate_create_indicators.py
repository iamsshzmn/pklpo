import asyncio
import logging

from sqlalchemy import text

from src.database import engine
from src.models import Base


async def run_migrations():
    async with engine.begin() as conn:
        # Удаляем таблицу, если существует (для применения новых ограничений)
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                text("DROP TABLE IF EXISTS indicators CASCADE")
            )
        )
        await conn.run_sync(Base.metadata.create_all)
    logging.info("Таблица indicators пересоздана с составным PRIMARY KEY")


if __name__ == "__main__":
    asyncio.run(run_migrations())
