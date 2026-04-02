import asyncio
import logging

from sqlalchemy import text

from src.database import engine
from src.models import Instrument


async def run_migrations():
    async with engine.begin() as conn:
        # Recreate only the instruments table. Using Base.metadata.create_all here
        # bootstraps unrelated ORM tables like indicators_p as plain heap tables.
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                text("DROP TABLE IF EXISTS instruments CASCADE")
            )
        )
        await conn.run_sync(Instrument.__table__.create)
    logging.info("Table instruments recreated with unique instId")


if __name__ == "__main__":
    asyncio.run(run_migrations())
