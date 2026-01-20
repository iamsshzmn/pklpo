"""
CLI команда для миграций БД модуля Risk
Поддерживает загрузку переменных из .env и сборку DATABASE_URL из POSTGRES_*.
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv

from src.mtf.logging_config import get_main_logger
from src.risk.database.migrations import run_risk_migrations

logger = get_main_logger()


def _load_env_files(env_files: list[str] | None) -> None:
    if env_files:
        for path in env_files:
            load_dotenv(dotenv_path=path, override=False)
    else:
        # Попробуем стандартный .env
        load_dotenv(override=False)


def _build_database_url_from_env() -> str | None:
    # Приоритет: DATABASE_URL; иначе собрать из POSTGRES_*/DB_*
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    user = os.environ.get("POSTGRES_USER") or os.environ.get("DB_USER")
    password = os.environ.get("POSTGRES_PASSWORD") or os.environ.get("DB_PASSWORD")
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB") or os.environ.get("DB_NAME")

    if user and password and dbname:
        return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    return None


def register(subparsers):
    parser = subparsers.add_parser("risk-migrate", help="Миграции БД для risk модуля")
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="URL базы данных (перекрывает env)",
    )
    parser.add_argument(
        "--env-file", action="append", help="Путь к .env (можно несколько флагов)"
    )
    parser.set_defaults(_handler=handle_risk_migrate)


async def handle_risk_migrate(args):
    _load_env_files(args.env_file)
    db_url = args.database_url or _build_database_url_from_env()

    if not db_url:
        logger.error(
            "DATABASE_URL не найден и не удалось собрать из POSTGRES_*/DB_* переменных"
        )
        raise SystemExit(1)

    logger.info("Запуск миграций Risk БД...")
    await run_risk_migrations(db_url)
    logger.info("Миграции Risk БД выполнены")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Risk DB migrations runner")
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="URL базы данных (перекрывает env)",
    )
    parser.add_argument(
        "--env-file", action="append", help="Путь к .env (можно несколько флагов)"
    )
    cli_args = parser.parse_args()

    _load_env_files(cli_args.env_file)
    url = cli_args.database_url or _build_database_url_from_env()
    if not url:
        print(
            "DATABASE_URL не найден и не удалось собрать из POSTGRES_*/DB_* переменных",
            flush=True,
        )
        raise SystemExit(1)
    asyncio.run(run_risk_migrations(url))
