import logging

from src.db.migrate_add_swap_fields import run_migrations as run_swap_fields_migrations
from src.db.migrate_add_swap_fields_to_instruments import (
    migrate_add_swap_fields_to_instruments,
)
from src.db.migrate_create_ohlcv import run_migrations as run_ohlcv_migrations
from src.db.migrate_create_positions import run_migrations as run_positions_migrations
from src.db.migrate_create_score_results import migrate_create_score_results
from src.db.migrate_fix_score_results_precision import (
    migrate_fix_score_results_precision,
)
from src.logging_config import setup_logging
from src.migrate_create_instruments import run_migrations as run_instruments_migrations

logger = logging.getLogger(__name__)


def register(subparsers):
    p = subparsers.add_parser("migrate", help="Выполнить миграции базы данных")
    p.set_defaults(_handler=handle)


async def handle(args):
    setup_logging("app.log")
    logger.info("📋 Запуск миграций базы данных...")
    await run_instruments_migrations()
    await run_ohlcv_migrations()
    await run_swap_fields_migrations()
    await run_positions_migrations()
    await migrate_create_score_results()
    await migrate_fix_score_results_precision()
    await migrate_add_swap_fields_to_instruments()
    logger.info("✅ Все миграции выполнены")
