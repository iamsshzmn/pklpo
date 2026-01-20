import logging

from src.candles.update_instruments_list import update_instruments_list

logger = logging.getLogger(__name__)


def register(subparsers):
    p = subparsers.add_parser(
        "update-list", help="Обновить список инструментов для синхронизации"
    )
    p.add_argument("--force", action="store_true", help="Принудительно обновить список")
    p.set_defaults(_handler=handle)


async def handle(args):
    logger.info("🔄 Запуск обновления списка инструментов")
    await update_instruments_list()
    logger.info("✅ Обновление списка завершено")
