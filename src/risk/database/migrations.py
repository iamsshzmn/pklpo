"""
Миграции для модуля Risk
"""

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)


class RiskDatabaseMigrations:
    """Класс для выполнения миграций схемы risk"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.schemas_path = Path(__file__).parent / "schemas.sql"

    async def run_migrations(self) -> None:
        """Выполнить миграции: создать схему и таблицы, если отсутствуют"""
        conn: asyncpg.Connection | None = None
        try:
            conn = await asyncpg.connect(self.database_url)

            sql = self.schemas_path.read_text(encoding="utf-8")
            await conn.execute(sql)

            logger.info("Risk DB migrations completed")
        finally:
            if conn:
                await conn.close()


async def run_risk_migrations(database_url: str) -> None:
    migrator = RiskDatabaseMigrations(database_url)
    await migrator.run_migrations()
