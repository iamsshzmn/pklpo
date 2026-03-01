import logging
from datetime import datetime

import src.cli.commands.migrate as migrate
import src.cli.commands.swap_sync as swap_sync

logger = logging.getLogger(__name__)


def register(subparsers):
    p = subparsers.add_parser("pipeline", help="Запуск полного пайплайна обработки")
    p.add_argument(
        "--all", action="store_true", help="Запустить все этапы последовательно"
    )
    p.add_argument(
        "--stages",
        nargs="+",
        choices=[
            "migrate",
            "load-instruments",
            "swap-sync",
            "features",
            "signals",
            "scoring",
            "recommendations",
        ],
        help="Конкретные этапы для запуска",
    )
    p.add_argument(
        "--skip",
        nargs="+",
        choices=[
            "migrate",
            "load-instruments",
            "swap-sync",
            "features",
            "signals",
            "scoring",
            "recommendations",
        ],
        help="Этапы для пропуска",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Показать план выполнения без запуска"
    )

    # Аргументы для этапа features
    p.add_argument("--symbols", nargs="+", help="Символы для обработки (для features)")
    p.add_argument(
        "--timeframes",
        nargs="+",
        default=["1m", "5m", "15m", "1H", "4H", "1D"],
        help="Таймфреймы для обработки (для features)",
    )
    p.add_argument(
        "--specs", nargs="+", help="Список индикаторов для расчёта (для features)"
    )
    p.add_argument(
        "--normalize",
        action="store_true",
        help="Включить волатильностную нормировку (для features)",
    )
    p.add_argument(
        "--normalize-window",
        type=int,
        default=20,
        help="Окно для нормировки (для features)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Количество баров для обработки (для features)",
    )

    p.set_defaults(_handler=handle)


async def handle(args):
    if not args.all and not args.stages:
        logger.error("❌ Укажите --all или --stages для запуска пайплайна")
        return

    # Определяем этапы для выполнения
    all_stages = [
        "migrate",
        "load-instruments",
        "swap-sync",
        "features",
        "signals",
        "scoring",
        "recommendations",
    ]

    stages_to_run = all_stages if args.all else args.stages or []

    # Исключаем пропущенные этапы
    if args.skip:
        stages_to_run = [stage for stage in stages_to_run if stage not in args.skip]

    if not stages_to_run:
        logger.warning("⚠️ Нет этапов для выполнения после применения фильтров")
        return

    # Показываем план выполнения
    logger.info("🚀 ПЛАН ВЫПОЛНЕНИЯ ПАЙПЛАЙНА:")
    for i, stage in enumerate(stages_to_run, 1):
        logger.info(f"  {i}. {stage}")

    if args.dry_run:
        logger.info("🔍 Dry-run режим: план показан, выполнение пропущено")
        return

    # Запускаем этапы последовательно
    start_time = datetime.now()
    logger.info(f"⏰ Начало выполнения: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    for i, stage in enumerate(stages_to_run, 1):
        stage_start = datetime.now()
        logger.info(f"\n🔄 ЭТАП {i}/{len(stages_to_run)}: {stage}")
        logger.info(f"⏰ Начало: {stage_start.strftime('%H:%M:%S')}")

        try:
            if stage == "migrate":
                await migrate.handle(args)
                results[stage] = {
                    "status": "success",
                    "duration": (datetime.now() - stage_start).total_seconds(),
                }

            elif stage == "load-instruments":
                from src.candles import load_instruments

                await load_instruments.load_instruments()
                results[stage] = {
                    "status": "success",
                    "duration": (datetime.now() - stage_start).total_seconds(),
                }

            elif stage == "swap-sync":
                # Запускаем синхронизацию (автообновление списка происходит внутри)
                await swap_sync.handle(args)
                results[stage] = {
                    "status": "success",
                    "duration": (datetime.now() - stage_start).total_seconds(),
                }

            elif stage == "features":
                from src.cli.commands import features as features_cmd

                await features_cmd.handle(args)
                results[stage] = {
                    "status": "success",
                    "duration": (datetime.now() - stage_start).total_seconds(),
                }

            elif stage == "signals":
                logger.info("⚠️ Этап signals пока не реализован")
                results[stage] = {"status": "skipped", "duration": 0}

            elif stage == "scoring":
                logger.info("⚠️ Этап scoring пока не реализован")
                results[stage] = {"status": "skipped", "duration": 0}

            elif stage == "recommendations":
                logger.info("⚠️ Этап recommendations пока не реализован")
                results[stage] = {"status": "skipped", "duration": 0}

        except Exception as e:
            logger.error(f"❌ Ошибка в этапе {stage}: {e}")
            results[stage] = {
                "status": "error",
                "error": str(e),
                "duration": (datetime.now() - stage_start).total_seconds(),
            }

            # Спрашиваем пользователя о продолжении
            logger.warning(f"⚠️ Этап {stage} завершился с ошибкой")
            logger.info("Продолжить выполнение следующих этапов? (y/n): ")
            # В реальной реализации здесь можно добавить интерактивный ввод
            # Пока просто продолжаем
            continue

    # Итоговая статистика
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    logger.info("\n📊 ИТОГОВАЯ СТАТИСТИКА ПАЙПЛАЙНА:")
    logger.info(f"⏰ Общее время: {total_duration:.1f} сек")
    logger.info(f"📋 Выполнено этапов: {len(stages_to_run)}")

    success_count = sum(1 for r in results.values() if r["status"] == "success")
    error_count = sum(1 for r in results.values() if r["status"] == "error")
    skipped_count = sum(1 for r in results.values() if r["status"] == "skipped")

    logger.info(f"✅ Успешно: {success_count}")
    logger.info(f"❌ Ошибок: {error_count}")
    logger.info(f"⏭️ Пропущено: {skipped_count}")

    if error_count == 0:
        logger.info("🎉 Пайплайн завершен успешно!")
    else:
        logger.warning(f"⚠️ Пайплайн завершен с {error_count} ошибками")
