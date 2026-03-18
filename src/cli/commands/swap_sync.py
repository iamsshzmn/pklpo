import json
import logging

from src.candles.interfaces.swap_sync import sync_swap_candles

logger = logging.getLogger(__name__)


def register(subparsers):
    p = subparsers.add_parser("swap-sync", help="Синхронизация swap свечей")
    p.add_argument("--symbols", nargs="+", help="Символы для синхронизации")
    p.add_argument("--timeframes", nargs="+", help="Таймфреймы для синхронизации")
    p.add_argument("--config", help="Путь к JSON конфигу для синхронизации")
    p.set_defaults(_handler=handle)


async def handle(args):
    config = None
    if getattr(args, "config", None):
        try:
            with open(args.config, encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(
                f"⚠️ Не удалось загрузить конфиг {args.config}: {e}. Используем значения по умолчанию"
            )

    logger.info("🚀 Запуск этапа: синхронизация swap свечей")
    symbols = getattr(args, "symbols", None)
    timeframes = getattr(args, "timeframes", None)
    stats = await sync_swap_candles(
        symbols=symbols, timeframes=timeframes, config=config
    )
    logger.info("✅ Этап swap синхронизации завершён")
    logger.info(
        f"📊 Символов: {stats['total_symbols']}, Свечей: {stats['total_candles_synced']:,}, Ошибок: {stats['errors_count']}"
    )

