"""
MTF Database Migrations

Миграции для создания и обновления таблиц MTF системы.
"""

import asyncio
import os
from pathlib import Path
from typing import Any

import asyncpg

from ..logging_config import get_main_logger

logger = get_main_logger()


class MTFDatabaseMigrations:
    """Класс для управления миграциями MTF базы данных"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.logger = logger
        self.schemas_path = Path(__file__).parent / "schemas.sql"

    async def run_migrations(self) -> bool:
        """Запуск всех миграций"""
        try:
            self.logger.info("Starting MTF database migrations...")

            # Создание таблиц MTF
            await self._create_mtf_tables()

            # Создание индексов
            await self._create_indexes()

            # Создание представлений
            await self._create_views()

            self.logger.info("MTF database migrations completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"MTF database migrations failed: {e}")
            return False

    async def _create_mtf_tables(self):
        """Создание таблиц MTF системы"""
        if not self.schemas_path.exists():
            raise FileNotFoundError(f"Schemas file not found: {self.schemas_path}")

        schemas_sql = self.schemas_path.read_text(encoding="utf-8")

        # Разделяем SQL на отдельные команды
        commands = [cmd.strip() for cmd in schemas_sql.split(";") if cmd.strip()]

        conn = await asyncpg.connect(self.connection_string)
        try:
            for command in commands:
                if command.upper().startswith(
                    (
                        "CREATE TABLE",
                        "CREATE INDEX",
                        "CREATE VIEW",
                        "CREATE OR REPLACE VIEW",
                    )
                ):
                    try:
                        await conn.execute(command)
                        self.logger.debug(f"Executed: {command[:50]}...")
                    except Exception as e:
                        if "already exists" in str(e).lower():
                            self.logger.debug(
                                f"Object already exists: {command[:50]}..."
                            )
                        else:
                            raise
        finally:
            await conn.close()

    async def _create_indexes(self):
        """Создание индексов (уже включено в schemas.sql)"""
        self.logger.debug("Indexes creation handled by schemas.sql")

    async def _create_views(self):
        """Создание представлений (уже включено в schemas.sql)"""
        self.logger.debug("Views creation handled by schemas.sql")

    async def check_tables_exist(self) -> dict[str, bool]:
        """Проверка существования таблиц MTF"""
        tables = [
            "mtf_context",
            "mtf_triggers",
            "mtf_consensus",
            "mtf_pipeline",
            "mtf_integration",
        ]

        results = {}

        conn = await asyncpg.connect(self.connection_string)
        try:
            for table in tables:
                query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = $1
                )
                """
                exists = await conn.fetchval(query, table)
                results[table] = exists
        finally:
            await conn.close()

        return results

    async def get_table_info(self, table_name: str) -> list[dict[str, Any]]:
        """Получение информации о структуре таблицы"""
        query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = $1
        ORDER BY ordinal_position
        """

        conn = await asyncpg.connect(self.connection_string)
        try:
            rows = await conn.fetch(query, table_name)
            return [dict(row) for row in rows]
        finally:
            await conn.close()

    async def get_table_stats(self, table_name: str) -> dict[str, Any]:
        """Получение статистики таблицы"""
        query = f"""
        SELECT
            COUNT(*) as row_count,
            MIN(created_at) as earliest_record,
            MAX(created_at) as latest_record
        FROM {table_name}
        """

        conn = await asyncpg.connect(self.connection_string)
        try:
            try:
                row = await conn.fetchrow(query)
                return dict(row) if row else {}
            except Exception as e:
                self.logger.warning(f"Could not get stats for table {table_name}: {e}")
                return {}
        finally:
            await conn.close()

    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Очистка старых данных"""
        tables = [
            "mtf_context",
            "mtf_triggers",
            "mtf_consensus",
            "mtf_pipeline",
            "mtf_integration",
        ]

        conn = await asyncpg.connect(self.connection_string)
        try:
            for table in tables:
                query = f"""
                DELETE FROM {table}
                WHERE created_at < NOW() - INTERVAL '{days_to_keep} days'
                """

                try:
                    result = await conn.execute(query)
                    self.logger.info(f"Cleaned up old data from {table}: {result}")
                except Exception as e:
                    self.logger.warning(f"Could not cleanup {table}: {e}")
        finally:
            await conn.close()

    async def vacuum_tables(self):
        """Оптимизация таблиц"""
        tables = [
            "mtf_context",
            "mtf_triggers",
            "mtf_consensus",
            "mtf_pipeline",
            "mtf_integration",
        ]

        conn = await asyncpg.connect(self.connection_string)
        try:
            for table in tables:
                try:
                    await conn.execute(f"VACUUM ANALYZE {table}")
                    self.logger.debug(f"Vacuumed table {table}")
                except Exception as e:
                    self.logger.warning(f"Could not vacuum {table}: {e}")
        finally:
            await conn.close()


async def run_mtf_migrations(connection_string: str) -> bool:
    """Утилита для запуска миграций MTF"""
    migrations = MTFDatabaseMigrations(connection_string)
    return await migrations.run_migrations()


if __name__ == "__main__":
    # Для тестирования миграций
    import os

    connection_string = os.getenv(
        "DATABASE_URL", "postgresql://user:password@localhost/pklpo"
    )

    async def test_migrations():
        migrations = MTFDatabaseMigrations(connection_string)

        # Проверяем существование таблиц
        tables_exist = await migrations.check_tables_exist()
        print("Tables exist:", tables_exist)

        # Запускаем миграции
        success = await migrations.run_migrations()
        print("Migrations success:", success)

        # Проверяем снова
        tables_exist_after = await migrations.check_tables_exist()
        print("Tables exist after:", tables_exist_after)

    asyncio.run(test_migrations())
