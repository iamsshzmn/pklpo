# ОСНОВНОЙ ФАЙЛ С ОПЦИЯМИ! Полный цикл работы системы с возможностью выбора этапов
# Выполняет выбранные этапы: миграции БД → загрузка инструментов → синхронизация OHLCV → расчёт индикаторов → обновление метаданных → генерация сигналов → анализ комбинаций → риск-менеджмент → расчёт scores
# Используется для гибкой настройки и выборочного обновления данных

import argparse
import asyncio
import logging
import sys
import time
from collections import defaultdict
from datetime import UTC
from pathlib import Path

from sqlalchemy import text

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent))

import contextlib

from src.candles.sync_candles import fetch_and_sync_candles
from src.config.env_validator import validate_environment
from src.db.migrate_add_swap_fields import run_migrations as run_swap_fields_migrations
from src.db.migrate_add_swap_fields_to_instruments import (
    migrate_add_swap_fields_to_instruments,
)
from src.db.migrate_create_mtf_expanded import migrate_create_mtf_expanded
from src.db.migrate_create_ohlcv import run_migrations as run_ohlcv_migrations
from src.db.migrate_create_positions import run_migrations as run_positions_migrations
from src.db.migrate_create_score_results import migrate_create_score_results
from src.db.migrate_fix_score_results_precision import (
    migrate_fix_score_results_precision,
)
from src.fetch_instruments import fetch_and_upsert_instruments, print_instruments_count
from src.fetch_swap_instruments import fetch_and_update_swap_instruments
from src.indicators.calc_combinations import (
    main_parallel as calc_combinations_parallel_main,
)
from src.indicators.calc_indicators import (
    main_parallel as calc_indicators_parallel_main,
)
from src.logging_config import setup_logging
from src.migrate_create_instruments import run_migrations as run_instruments_migrations
from src.mtf.manager import (
    run_mtf_analysis_only,
    run_mtf_etl_only,
    run_mtf_full_cycle,
    validate_mtf_data,
)
from src.positions.calc_positions import calculate_positions_for_all
from src.scoring_engine.processor import process_all_scores
from src.signals.calculator.signal_calculator import SignalCalculator
from src.trade_recommender.batch_recommendations import (
    get_all_score_ids,
    process_score_recommendations_parallel,
)
from src.utils.db_optimizer import get_processing_stats, validate_data_availability
from src.utils.session_utils import get_db_session

setup_logging("app.log")
logger = logging.getLogger(__name__)


class StageTimer:
    """Класс для измерения времени выполнения этапов"""

    def __init__(self):
        self.stages = {}
        self.current_stage = None
        self.start_time = None

    def start_stage(self, stage_name: str):
        """Начинает измерение времени для этапа"""
        if self.current_stage:
            self.end_stage()

        self.current_stage = stage_name
        self.start_time = time.time()
        logger.info(f"⏱️ Начало этапа: {stage_name}")

    def end_stage(self):
        """Завершает измерение времени для текущего этапа"""
        if self.current_stage and self.start_time:
            duration = time.time() - self.start_time
            self.stages[self.current_stage] = duration
            logger.info(f"✅ Этап '{self.current_stage}' завершен за {duration:.2f}с")
            self.current_stage = None
            self.start_time = None

    def get_summary(self) -> dict:
        """Возвращает сводку по всем этапам"""
        self.end_stage()  # Завершаем текущий этап если есть
        total_time = sum(self.stages.values())
        return {
            "stages": self.stages,
            "total_time": total_time,
            "stages_count": len(self.stages),
        }


async def get_symbols_timeframes(session, symbol: str | None = None):
    """
    Получает символы и таймфреймы за один запрос для оптимизации.

    Args:
        session: Сессия БД
        symbol: Конкретный символ (если None, обрабатываются все)

    Returns:
        dict: {symbol: [timeframes]}
    """
    if symbol:
        query = text(
            """
            SELECT DISTINCT symbol, timeframe
            FROM indicators
            WHERE symbol = :symbol
        """
        )
        result = await session.execute(query, {"symbol": symbol})
    else:
        query = text("SELECT DISTINCT symbol, timeframe FROM indicators")
        result = await session.execute(query)

    mapping = defaultdict(list)
    for row in result.fetchall():
        mapping[row[0]].append(row[1])

    return mapping


async def validate_system_readiness(symbol=None, timeframe=None, dry_run=True):
    """
    Валидирует готовность системы к работе.

    Args:
        symbol: Символ для проверки
        timeframe: Таймфрейм для проверки
        dry_run: Только проверка без выполнения действий

    Returns:
        dict: Результат валидации
    """
    try:
        logger.info("🔍 Запуск валидации системы...")

        validation_results = {
            "overall_status": "unknown",
            "checks": {},
            "recommendations": [],
            "warnings": [],
            "errors": [],
        }

        async with get_db_session() as session:
            # 1. Проверка подключения к БД
            try:
                result = await session.execute(text("SELECT 1"))
                validation_results["checks"]["database_connection"] = {
                    "status": "✅ OK",
                    "message": "Подключение к базе данных работает",
                }
            except Exception as e:
                validation_results["checks"]["database_connection"] = {
                    "status": "❌ FAILED",
                    "message": f"Ошибка подключения к БД: {e}",
                }
                validation_results["errors"].append("Нет подключения к базе данных")
                return validation_results  # Выходим если нет подключения

            # 2. Проверка наличия таблиц
            required_tables = [
                "instruments",
                "ohlcv",
                "indicators",
                "signals",
                "combination_results",
                "position_calculations",
                "score_results",
                "trade_recommendations",
            ]

            for table in required_tables:
                try:
                    result = await session.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    )
                    count = result.scalar()
                    validation_results["checks"][f"table_{table}"] = {
                        "status": "✅ OK",
                        "message": f"Таблица {table} существует, записей: {count}",
                    }
                except Exception as e:
                    # При ошибке делаем rollback и продолжаем
                    with contextlib.suppress(Exception):
                        await session.rollback()

                    validation_results["checks"][f"table_{table}"] = {
                        "status": "❌ MISSING",
                        "message": f"Таблица {table} отсутствует: {e}",
                    }
                    validation_results["errors"].append(f"Отсутствует таблица {table}")

            # 3. Проверка данных (только если есть таблица indicators)
            if (
                "table_indicators" in validation_results["checks"]
                and validation_results["checks"]["table_indicators"]["status"]
                == "✅ OK"
            ):
                try:
                    data_validation = await validate_data_availability(
                        session, symbol, timeframe
                    )
                    validation_results["checks"]["data_availability"] = {
                        "status": (
                            "✅ OK" if data_validation["is_valid"] else "⚠️ WARNING"
                        ),
                        "message": f"Данные: {data_validation.get('symbols_count', 0)} символов, "
                        f"{data_validation.get('timeframes_count', 0)} таймфреймов, "
                        f"{data_validation.get('total_records', 0)} записей",
                    }

                    if not data_validation["is_valid"]:
                        validation_results["warnings"].extend(
                            data_validation.get("missing_data", [])
                        )

                    if data_validation.get("warnings"):
                        validation_results["warnings"].extend(
                            data_validation["warnings"]
                        )

                    # 4. Статистика обработки
                    if data_validation["is_valid"]:
                        try:
                            stats = await get_processing_stats(session, symbol)
                            validation_results["checks"]["processing_stats"] = {
                                "status": "✅ OK",
                                "message": f"Статистика: {stats.get('total_symbols', 0)} символов, "
                                f"{stats.get('total_timeframes', 0)} таймфреймов, "
                                f"{stats.get('total_records', 0)} записей",
                            }
                        except Exception as e:
                            with contextlib.suppress(Exception):
                                await session.rollback()
                            validation_results["checks"]["processing_stats"] = {
                                "status": "⚠️ WARNING",
                                "message": f"Не удалось получить статистику: {e}",
                            }

                    # 5. Проверка свежести данных
                    if data_validation.get("latest_timestamp"):
                        from datetime import datetime

                        latest_dt = datetime.fromtimestamp(
                            data_validation["latest_timestamp"], tz=UTC
                        )
                        now_dt = datetime.now(UTC)
                        age_hours = (now_dt - latest_dt).total_seconds() / 3600

                        if age_hours < 1:
                            validation_results["checks"]["data_freshness"] = {
                                "status": "✅ OK",
                                "message": f"Данные свежие: {age_hours:.1f} часов назад",
                            }
                        elif age_hours < 24:
                            validation_results["checks"]["data_freshness"] = {
                                "status": "⚠️ WARNING",
                                "message": f"Данные не очень свежие: {age_hours:.1f} часов назад",
                            }
                            validation_results["warnings"].append(
                                f"Данные устарели на {age_hours:.1f} часов"
                            )
                        else:
                            validation_results["checks"]["data_freshness"] = {
                                "status": "❌ STALE",
                                "message": f"Данные сильно устарели: {age_hours:.1f} часов назад",
                            }
                            validation_results["errors"].append(
                                f"Данные сильно устарели: {age_hours:.1f} часов"
                            )
                except Exception as e:
                    with contextlib.suppress(Exception):
                        await session.rollback()
                    validation_results["checks"]["data_availability"] = {
                        "status": "❌ ERROR",
                        "message": f"Ошибка проверки данных: {e}",
                    }
                    validation_results["errors"].append(f"Ошибка проверки данных: {e}")
            else:
                validation_results["checks"]["data_availability"] = {
                    "status": "⚠️ SKIPPED",
                    "message": "Пропущено - нет таблицы indicators",
                }

        # Определяем общий статус
        if validation_results["errors"]:
            validation_results["overall_status"] = "❌ FAILED"
            validation_results["recommendations"].append(
                "Исправьте критические ошибки перед запуском"
            )
        elif validation_results["warnings"]:
            validation_results["overall_status"] = "⚠️ WARNING"
            validation_results["recommendations"].append(
                "Проверьте предупреждения перед запуском"
            )
        else:
            validation_results["overall_status"] = "✅ READY"
            validation_results["recommendations"].append("Система готова к работе")

        # Выводим результаты
        logger.info(f"📊 Общий статус: {validation_results['overall_status']}")
        logger.info("📋 Результаты проверок:")

        for check_name, check_result in validation_results["checks"].items():
            logger.info(
                f"  {check_result['status']} {check_name}: {check_result['message']}"
            )

        if validation_results["warnings"]:
            logger.warning("⚠️ Предупреждения:")
            for warning in validation_results["warnings"]:
                logger.warning(f"  - {warning}")

        if validation_results["errors"]:
            logger.error("❌ Ошибки:")
            for error in validation_results["errors"]:
                logger.error(f"  - {error}")

        if validation_results["recommendations"]:
            logger.info("💡 Рекомендации:")
            for rec in validation_results["recommendations"]:
                logger.info(f"  - {rec}")

        if dry_run:
            logger.info("🔍 Валидация завершена (dry-run режим)")
        else:
            logger.info("✅ Валидация завершена")

        return validation_results

    except Exception as e:
        logger.error(f"❌ Ошибка при валидации системы: {e}", exc_info=True)
        return {
            "overall_status": "❌ ERROR",
            "error": str(e),
            "checks": {},
            "recommendations": ["Проверьте логи для диагностики"],
            "warnings": [],
            "errors": [f"Ошибка валидации: {e}"],
        }


async def update_instruments_from_api():
    """
    Обновляет данные инструментов с API OKX.
    Загружает актуальные данные о комиссиях, финансировании и других параметрах.
    """
    try:
        logger.info("🔄 Запуск обновления данных инструментов с API...")

        # Обновляем данные инструментов с API
        await fetch_and_update_swap_instruments()

        logger.info("✅ Обновление данных инструментов завершено успешно!")

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении инструментов: {e}", exc_info=True)
        raise


def create_parser():
    """Создает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Полный цикл работы торговой системы с возможностью выбора этапов: миграции БД → инструменты → OHLCV → индикаторы → метаданные → сигналы → комбинации → риск-менеджмент → scores"
    )

    parser.add_argument(
        "--validate",
        "-v",
        action="store_true",
        help="Валидировать готовность системы к работе",
    )

    parser.add_argument(
        "--migrations", "-m", action="store_true", help="Выполнить миграции базы данных"
    )

    parser.add_argument(
        "--instruments",
        "-i",
        action="store_true",
        help="Загрузить инструменты с OKX API",
    )

    parser.add_argument(
        "--update-instruments",
        "-ui",
        action="store_true",
        help="Обновить метаданные инструментов (комиссии, финансирование)",
    )

    parser.add_argument(
        "--candles", "-c", action="store_true", help="Синхронизировать OHLCV данные"
    )

    # Взаимоисключающие группы для индикаторов
    indicators_group = parser.add_mutually_exclusive_group()
    indicators_group.add_argument(
        "--indicators",
        "-ind",
        action="store_true",
        help="Рассчитать технические индикаторы (параллельная версия)",
    )

    # Взаимоисключающие группы для сигналов
    signals_group = parser.add_mutually_exclusive_group()
    signals_group.add_argument(
        "--signals",
        "-s",
        action="store_true",
        help="Сгенерировать торговые сигналы",
    )
    signals_group.add_argument(
        "--signals-parallel",
        "-sp",
        action="store_true",
        help="Сгенерировать торговые сигналы (альтернативный флаг)",
    )

    # Взаимоисключающие группы для комбинаций
    combinations_group = parser.add_mutually_exclusive_group()
    combinations_group.add_argument(
        "--combinations",
        "-comb",
        action="store_true",
        help="Проанализировать комбинации индикаторов",
    )

    # Взаимоисключающие группы для позиций
    positions_group = parser.add_mutually_exclusive_group()
    positions_group.add_argument(
        "--positions",
        "-p",
        action="store_true",
        help="Рассчитать размер позиций и риск-менеджмент",
    )

    parser.add_argument(
        "--scoring",
        "-sc",
        action="store_true",
        help="Рассчитать итоговые scores на основе индикаторов и комбинаций",
    )

    parser.add_argument(
        "--recommendations",
        "-rec",
        action="store_true",
        help="Сгенерировать торговые рекомендации на основе scores",
    )

    # MTF модуль
    parser.add_argument(
        "--mtf",
        action="store_true",
        help="Запустить полный цикл MTF (Multi-Timeframe): ETL → анализ решений",
    )

    parser.add_argument(
        "--mtf-etl",
        action="store_true",
        help="Запустить только ETL процесс MTF (context → triggers → consensus)",
    )

    parser.add_argument(
        "--mtf-analysis",
        action="store_true",
        help="Запустить только анализ MTF результатов",
    )

    parser.add_argument(
        "--mtf-validate",
        action="store_true",
        help="Валидировать данные MTF системы",
    )

    parser.add_argument(
        "--mtf-cleanup",
        action="store_true",
        help="Очистить старые MTF данные (старше 24 часов)",
    )

    parser.add_argument(
        "--mtf-cleanup-hours",
        type=int,
        default=24,
        help="Возраст данных в часах для очистки MTF (по умолчанию 24)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Режим тестирования без сохранения в БД",
    )

    parser.add_argument(
        "--verbose",
        "-V",
        action="store_true",
        help="Подробный вывод (DEBUG уровень логирования)",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Тихий режим (только ошибки)",
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        help="Максимальное количество параллельных воркеров (переопределяет настройки)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        help="Размер батча для обработки (переопределяет настройки)",
    )

    parser.add_argument(
        "--all", "-a", action="store_true", help="Выполнить все этапы (по умолчанию)"
    )

    parser.add_argument(
        "--timeframe",
        "-t",
        type=str,
        default="all",
        help="Таймфрейм для сигналов (по умолчанию: all - все доступные)",
    )

    parser.add_argument(
        "--symbol",
        "-sym",
        type=str,
        help="Конкретный символ для обработки (если не указан, обрабатываются все)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Ограничить количество обрабатываемых записей (для рекомендаций)",
    )

    return parser


async def calculate_detailed_signals(timeframe="1m", symbol=None):
    """
    Рассчитывает детализированные сигналы для символов.

    Args:
        timeframe: Таймфрейм для сигналов (если None, обрабатываются все доступные)
        symbol: Конкретный символ (если None, обрабатываются все)
    """
    try:
        logger.info("🚀 Запуск расчёта сигналов...")

        # Создаем движок сигналов и калькулятор
        from src.signals.engine.signal_engine import SignalEngine

        engine = SignalEngine()
        calculator = SignalCalculator(engine)
        logger.info("✅ Калькулятор сигналов создан успешно")

        async with get_db_session() as session:
            # Получаем символы и таймфреймы за один запрос
            symbols_timeframes = await get_symbols_timeframes(session, symbol)

            if not symbols_timeframes:
                logger.warning("⚠️ Нет данных для расчёта сигналов")
                return

            logger.info(
                f"📊 Найдено {len(symbols_timeframes)} символов для расчёта сигналов"
            )

            # Фильтруем по конкретному таймфрейму если указан
            if timeframe and timeframe != "all":
                for sym in list(symbols_timeframes.keys()):
                    symbols_timeframes[sym] = [timeframe]

            # Используем параллельную версию для всех символов
            result = await calculator.calculate_signals_for_all_parallel(
                timeframe=timeframe, symbol=symbol, recalculate=True
            )

            if result.get("status") == "completed":
                logger.info(f"🎉 Всего создано {result.get('signals', 0)} сигналов")
                logger.info(
                    f"✅ Обработано {result.get('processed', 0)} пар symbol-timeframe"
                )
                logger.info(f"❌ Ошибок: {result.get('errors', 0)}")
            else:
                logger.warning(
                    f"⚠️ Расчёт сигналов завершился со статусом: {result.get('status')}"
                )

    except asyncio.CancelledError as e:
        logger.error(f"❌ Операция отменена: {e}")
        raise
    except TimeoutError as e:
        logger.error(f"❌ Таймаут операции: {e}")
        raise
    except ConnectionError as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при расчете сигналов: {e}", exc_info=True)
        raise


async def calculate_scoring(symbol=None):
    """
    Рассчитывает итоговые scores на основе индикаторов и комбинаций.

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)
    """
    try:
        logger.info("🎯 Запуск расчёта итоговых scores...")

        # Запускаем автоматический процессор Scoring Engine
        result = await process_all_scores()

        if result.get("status") == "completed":
            logger.info(
                f"✅ Scoring Engine: обработано {result.get('processed', 0)} записей"
            )
            logger.info(f"   Ошибок: {result.get('errors', 0)}")
            logger.info(f"   Время: {result.get('duration', 0):.1f}с")
        elif result.get("status") == "no_data":
            logger.info("ℹ️ Нет новых данных для расчёта scores")
        else:
            logger.warning(
                f"⚠️ Scoring Engine завершился со статусом: {result.get('status')}"
            )

    except asyncio.CancelledError as e:
        logger.error(f"❌ Операция отменена: {e}")
        raise
    except TimeoutError as e:
        logger.error(f"❌ Таймаут операции: {e}")
        raise
    except ConnectionError as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при расчёте scores: {e}", exc_info=True)
        raise


async def calculate_recommendations(symbol=None, limit=None):
    """
    Генерирует торговые рекомендации на основе scores.

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)
        limit: Ограничение количества обрабатываемых записей
    """
    try:
        logger.info("🎯 Запуск генерации торговых рекомендаций...")

        async with get_db_session() as session:
            # Получаем все score_ids
            all_score_ids = await get_all_score_ids(session)

            if not all_score_ids:
                logger.warning("⚠️ Нет score_results для генерации рекомендаций")
                return

            # Применяем ограничения
            score_ids = all_score_ids
            if limit:
                score_ids = score_ids[:limit]
                logger.info(
                    f"📊 Ограничение: обработаем {len(score_ids)} записей из {len(all_score_ids)}"
                )

            logger.info(f"📊 Найдено {len(score_ids)} score_results для обработки")

            # Обрабатываем рекомендации (параллельная версия)
            results = await process_score_recommendations_parallel(
                score_ids, dry_run=False
            )

            # Выводим итоговую статистику
            logger.info("📊 ИТОГОВАЯ СТАТИСТИКА РЕКОМЕНДАЦИЙ:")
            logger.info(f"📋 Всего записей: {results['total']}")
            logger.info(f"✅ Обработано: {results['processed']}")
            logger.info(f"🎯 Готовых рекомендаций: {results['ready']}")
            logger.info(f"❌ Отклонённых: {results['rejected']}")
            logger.info(f"💥 Ошибок: {results['errors']}")

            if results["ready"] > 0:
                success_rate = results["ready"] / results["processed"] * 100
                logger.info(f"📈 Успешность: {success_rate:.1f}%")

            logger.info("✅ Генерация торговых рекомендаций завершена успешно!")

    except asyncio.CancelledError as e:
        logger.error(f"❌ Операция отменена: {e}")
        raise
    except TimeoutError as e:
        logger.error(f"❌ Таймаут операции: {e}")
        raise
    except ConnectionError as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        raise
    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка при генерации рекомендаций: {e}", exc_info=True
        )
        raise


async def main():
    """
    Основная функция с поддержкой выбора этапов.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Валидация конфигурации
    try:
        logger.info("🔧 Проверка конфигурации системы...")
        settings = validate_environment()
        logger.info("✅ Конфигурация валидна")
        logger.debug(
            f"📊 Настройки: max_workers={settings.max_workers}, batch_size={settings.batch_size}"
        )
    except ValueError as e:
        logger.error(f"❌ Ошибка конфигурации: {e}")
        sys.exit(1)

    # Настройка логирования на основе аргументов
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🔍 Включен подробный режим логирования (DEBUG)")
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
        logger.info("🔇 Включен тихий режим (только ошибки)")

    # Переопределение настроек из аргументов командной строки
    if args.max_workers:
        settings.max_workers = args.max_workers
        logger.info(f"⚡ Переопределено количество воркеров: {args.max_workers}")

    if args.batch_size:
        settings.batch_size = args.batch_size
        logger.info(f"📦 Переопределен размер батча: {args.batch_size}")

    # Проверка режима dry-run
    if args.dry_run:
        logger.warning("🧪 ВКЛЮЧЕН РЕЖИМ DRY-RUN - данные не будут сохранены в БД!")

    # Если не указаны конкретные этапы, выполняем все
    if not any(
        [
            args.validate,
            args.migrations,
            args.instruments,
            args.update_instruments,
            args.candles,
            args.indicators,
            args.signals,
            args.signals_parallel,
            args.combinations,
            args.positions,
            args.scoring,
            args.recommendations,
            args.mtf,
            args.mtf_etl,
            args.mtf_analysis,
            args.mtf_validate,
            args.mtf_cleanup,
        ]
    ):
        args.all = True

    try:
        logger.info("🚀 Запуск работы системы с выбранными этапами...")

        # Инициализируем таймер этапов
        timer = StageTimer()

        # Этап 0: Валидация системы (если запрошена)
        if args.validate:
            timer.start_stage("Валидация системы")
            logger.info("🔍 Этап 0: Валидация готовности системы...")
            validation_result = await validate_system_readiness(
                args.symbol, args.timeframe, dry_run=True
            )

            if validation_result["overall_status"] == "❌ FAILED":
                logger.error(
                    "❌ Система не готова к работе. Исправьте критические ошибки."
                )
                sys.exit(1)
            elif validation_result["overall_status"] == "⚠️ WARNING":
                logger.warning("⚠️ Система готова с предупреждениями. Проверьте логи.")
            else:
                logger.info("✅ Система готова к работе.")
            timer.end_stage()

            # Если только валидация - завершаем
            if not any(
                [
                    args.migrations,
                    args.instruments,
                    args.update_instruments,
                    args.candles,
                    args.indicators,
                    args.signals,
                    args.signals_parallel,
                    args.combinations,
                    args.positions,
                    args.scoring,
                    args.recommendations,
                    args.all,
                    args.mtf,
                    args.mtf_etl,
                    args.mtf_analysis,
                    args.mtf_validate,
                    args.mtf_cleanup,
                ]
            ):
                return

        # Проверяем, если запущена только MTF-задача, пропускаем остальные этапы
        mtf_only = any(
            [
                args.mtf,
                args.mtf_etl,
                args.mtf_analysis,
                args.mtf_validate,
                args.mtf_cleanup,
            ]
        ) and not any(
            [
                args.all,
                args.migrations,
                args.instruments,
                args.update_instruments,
                args.candles,
                args.indicators,
                args.signals,
                args.signals_parallel,
                args.combinations,
                args.positions,
                args.scoring,
                args.recommendations,
            ]
        )

        # Этап 1: Миграции БД
        if not mtf_only and (args.all or args.migrations):
            timer.start_stage("Миграции БД")
            logger.info("📋 Этап 1: Выполнение миграций базы данных...")
            await run_instruments_migrations()
            await run_ohlcv_migrations()
            await run_swap_fields_migrations()
            await run_positions_migrations()
            await migrate_create_score_results()
            await migrate_fix_score_results_precision()
            # Перенесено внутрь блока миграций, чтобы не запускалось при --mtf
            await migrate_add_swap_fields_to_instruments()

            from src.db.migrate_create_trade_recommendations import (
                migrate_create_trade_recommendations,
            )

            await migrate_create_trade_recommendations()
            timer.end_stage()

        # Этап 2: Загрузка инструментов с OKX API
        if not mtf_only and (args.all or args.instruments):
            timer.start_stage("Загрузка инструментов")
            logger.info("📊 Этап 2: Загрузка инструментов с OKX API...")
            await fetch_and_upsert_instruments()
            await print_instruments_count()
            timer.end_stage()

        # Этап 3: Синхронизация OHLCV данных
        if not mtf_only and (args.all or args.candles):
            timer.start_stage("Синхронизация OHLCV")
            logger.info("🕯️ Этап 3: Синхронизация OHLCV данных...")
            await fetch_and_sync_candles(args.symbol)
            timer.end_stage()

        # Этап 4: Обновление метаданных инструментов (комиссии, финансирование)
        if not mtf_only and (args.all or args.update_instruments):
            timer.start_stage("Обновление метаданных")
            logger.info(
                "🔄 Этап 4: Обновление метаданных инструментов (комиссии, финансирование)..."
            )
            await update_instruments_from_api()
            timer.end_stage()

        # Этап 5: Расчёт технических индикаторов (параллельная версия)
        if not mtf_only and (args.all or args.indicators):
            timer.start_stage("Расчёт индикаторов")
            logger.info(
                "⚡ Этап 5: Расчёт технических индикаторов (параллельная версия)..."
            )
            # Автоматически очищаем старые данные перед расчетом (старше 24 часов)
            await calc_indicators_parallel_main(
                args.symbol, cleanup_old=True, cleanup_hours=24
            )
            timer.end_stage()

        # Этап 6: Генерация торговых сигналов
        if not mtf_only and (args.all or args.signals or args.signals_parallel):
            timer.start_stage("Генерация сигналов")
            logger.info(
                "⚡ Этап 6: Генерация торговых сигналов (параллельная версия)..."
            )
            await calculate_detailed_signals(args.timeframe, args.symbol)
            timer.end_stage()

        # Этап 7: Анализ комбинаций индикаторов (параллельная версия)
        if not mtf_only and (args.all or args.combinations):
            timer.start_stage("Анализ комбинаций")
            logger.info(
                "🔗 Этап 7: Анализ комбинаций индикаторов (параллельная версия)..."
            )
            await calc_combinations_parallel_main(args.symbol)
            timer.end_stage()

        # Этап 9: Расчёт размера позиций и риск-менеджмент (параллельная версия)
        if not mtf_only and (args.all or args.positions):
            timer.start_stage("Расчёт позиций")
            logger.info(
                "💰 Этап 9: Расчёт размера позиций и риск-менеджмент (параллельная версия)..."
            )
            result = await calculate_positions_for_all(args.symbol)
            if result.get("status") == "completed":
                logger.info(
                    f"✅ Позиции: обработано {result.get('processed', 0)} инструментов"
                )
                logger.info(f"   Создано позиций: {result.get('positions', 0)}")
                logger.info(f"   Ошибок: {result.get('errors', 0)}")
            timer.end_stage()

        # Этап 10: Расчёт итоговых scores
        if not mtf_only and (args.all or args.scoring):
            timer.start_stage("Расчёт scores")
            logger.info(
                "🎯 Этап 10: Расчёт итоговых scores на основе индикаторов и комбинаций..."
            )
            await calculate_scoring(args.symbol)
            timer.end_stage()

        # Этап 11: Генерация торговых рекомендаций
        if not mtf_only and (args.all or args.recommendations):
            timer.start_stage("Генерация рекомендаций")
            logger.info(
                "🎯 Этап 11: Генерация торговых рекомендаций на основе scores..."
            )
            await calculate_recommendations(args.symbol, args.limit)
            timer.end_stage()

        # Подготовка MTF схемы и таблиц перед запуском любых MTF-задач
        if (
            args.mtf
            or args.mtf_etl
            or args.mtf_analysis
            or args.mtf_validate
            or args.mtf_cleanup
        ):
            logger.info("🧱 Подготовка схемы и таблиц MTF...")
            await migrate_create_mtf_expanded()

            # MTF модуль зависит от таблицы indicators
            if args.mtf or args.mtf_etl:
                logger.info("ℹ️ MTF требует готовых данных в таблице indicators")
                logger.info("   Если таблица пуста, сначала запустите: --indicators")

        # Этап 12: MTF (Multi-Timeframe) модуль
        if args.mtf:
            timer.start_stage("MTF полный цикл")
            logger.info("📊 Этап 12: Запуск полного цикла MTF (Multi-Timeframe)...")
            result = await run_mtf_full_cycle(args.symbol, args.dry_run)
            if result.get("status") == "completed":
                logger.info(
                    f"✅ MTF: найдено {result.get('market_signals', 0)} сигналов, "
                    f"{result.get('swing_opportunities', 0)} swing возможностей, "
                    f"{result.get('intraday_signals', 0)} внутридневных сигналов"
                )
            else:
                logger.error(
                    f"❌ MTF завершился с ошибкой: {result.get('error', 'Unknown error')}"
                )
            timer.end_stage()

        if args.mtf_etl:
            timer.start_stage("MTF ETL")
            logger.info("📊 Этап 12: Запуск MTF ETL процесса...")
            result = await run_mtf_etl_only(args.symbol, args.dry_run)
            if result.get("status") == "completed":
                logger.info("✅ MTF ETL процесс завершен успешно!")
            else:
                logger.error(
                    f"❌ MTF ETL завершился с ошибкой: {result.get('error', 'Unknown error')}"
                )
            timer.end_stage()

        if args.mtf_analysis:
            timer.start_stage("MTF анализ")
            logger.info("🎯 Этап 12: Запуск анализа MTF результатов...")
            result = await run_mtf_analysis_only(args.symbol, args.limit)
            if result.get("status") == "completed":
                logger.info(
                    f"✅ MTF анализ: найдено {result.get('market_signals', 0)} сигналов, "
                    f"{result.get('swing_opportunities', 0)} swing возможностей, "
                    f"{result.get('intraday_signals', 0)} внутридневных сигналов"
                )
            else:
                logger.error(
                    f"❌ MTF анализ завершился с ошибкой: {result.get('error', 'Unknown error')}"
                )
            timer.end_stage()

        if args.mtf_validate:
            timer.start_stage("MTF валидация")
            logger.info("🔍 Этап 12: Валидация MTF данных...")
            result = await validate_mtf_data(args.symbol)
            if result.get("status") == "completed":
                logger.info("✅ Валидация MTF данных завершена!")
            else:
                logger.error(
                    f"❌ Валидация MTF завершилась с ошибкой: {result.get('error', 'Unknown error')}"
                )
            timer.end_stage()

        if args.mtf_cleanup:
            timer.start_stage("MTF очистка")
            logger.info(
                f"🧹 Этап 12: Очистка старых MTF данных (старше {args.mtf_cleanup_hours} часов)..."
            )
            from src.mtf.manager import cleanup_mtf_old_data

            result = await cleanup_mtf_old_data(
                args.mtf_cleanup_hours, args.symbol, args.dry_run
            )
            if result.get("status") == "completed":
                logger.info(
                    f"✅ Очистка MTF данных завершена! Удалено: {result.get('deleted_count', 0)} записей"
                )
            else:
                logger.error(
                    f"❌ Очистка MTF завершилась с ошибкой: {result.get('error', 'Unknown error')}"
                )
            timer.end_stage()

        # Выводим итоговую статистику
        summary = timer.get_summary()
        logger.info("📊 ИТОГОВАЯ СТАТИСТИКА ВЫПОЛНЕНИЯ:")
        logger.info(f"⏱️ Общее время: {summary['total_time']:.2f}с")
        logger.info(f"📋 Количество этапов: {summary['stages_count']}")

        if summary["stages"]:
            logger.info("📈 Время по этапам:")
            for stage, duration in summary["stages"].items():
                percentage = (duration / summary["total_time"]) * 100
                logger.info(f"   {stage}: {duration:.2f}с ({percentage:.1f}%)")

        logger.info("🎉 Работа системы завершена успешно!")

        # Экспорт статистики если запрошено
        if args.verbose:
            await export_execution_stats(summary, args)

    except asyncio.CancelledError as e:
        logger.error(f"CancelledError: {e}", exc_info=True)
        sys.exit(1)
    except TimeoutError as e:
        logger.error(f"TimeoutError: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(2)


async def export_execution_stats(summary: dict, args):
    """
    Экспортирует статистику выполнения в JSON файл

    Args:
        summary: Сводка выполнения от StageTimer
        args: Аргументы командной строки
    """
    try:
        import json
        from datetime import datetime

        stats_data = {
            "timestamp": datetime.now().isoformat(),
            "command_line": " ".join(sys.argv),
            "execution_summary": summary,
            "arguments": {
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "limit": args.limit,
                "dry_run": args.dry_run,
                "verbose": args.verbose,
                "quiet": args.quiet,
                "max_workers": args.max_workers,
                "batch_size": args.batch_size,
            },
            "stages_executed": list(summary.get("stages", {}).keys()),
        }

        # Создаем директорию для логов если её нет
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Генерируем имя файла с временной меткой
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"execution_stats_{timestamp}.json"
        filepath = log_dir / filename

        # Сохраняем статистику
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)

        logger.info(f"📊 Статистика выполнения сохранена в: {filepath}")

    except Exception as e:
        logger.warning(f"⚠️ Не удалось сохранить статистику: {e}")


if __name__ == "__main__":
    asyncio.run(main())


# =============================================================================
# ПОЛНЫЙ ЦИКЛ РАБОТЫ СИСТЕМЫ - ЭТАПЫ В ПОРЯДКЕ ВЫПОЛНЕНИЯ
# =============================================================================

# ЭТАП 0: Валидация системы
# python src/main_with_options.py --validate

# ЭТАП 1: Подготовка базы данных
# python src/main_with_options.py --migrations

# ЭТАП 2: Загрузка инструментов с API
# python src/main_with_options.py --instruments

# ЭТАП 3: Синхронизация OHLCV данных
# python src/main_with_options.py --candles

# ЭТАП 4: Обновление метаданных инструментов (комиссии, финансирование)
# python src/main_with_options.py --update-instruments

# ЭТАП 5: Расчёт технических индикаторов
# python src/main_with_options.py --indicators                    # Основной режим
# python src/main_with_options.py --indicators-parallel           # Основной режим (альтернативный флаг)

# ЭТАП 6: Генерация торговых сигналов
# python src/main_with_options.py --signals                       # Основной режим
# python src/main_with_options.py --signals-parallel              # Основной режим (альтернативный флаг)

# ЭТАП 7: Анализ комбинаций индикаторов (параллельная версия)
# python src/main_with_options.py --combinations                  # Параллельный режим

# ЭТАП 9: Расчёт позиций и риск-менеджмент (параллельная версия)
# python src/main_with_options.py --positions                    # Параллельный режим

# ЭТАП 10: Расчёт итоговых scores
# python src/main_with_options.py --scoring

# ЭТАП 11: Генерация торговых рекомендаций
# python src/main_with_options.py --recommendations


# =============================================================================
# ПОЛНЫЙ ЦИКЛ (все этапы сразу)
# =============================================================================
# python src/main_with_options.py --all

# =============================================================================
# ОБРАБОТКА КОНКРЕТНОГО СИМВОЛА
# =============================================================================
# python src/main_with_options.py --all --symbol BTC-USDT-SWAP
# python src/main_with_options.py --indicators-parallel --symbol BTC-USDT-SWAP
# python src/main_with_options.py --signals-parallel --symbol BTC-USDT-SWAP

# =============================================================================
# ВАЛИДАЦИЯ С КОНКРЕТНЫМ СИМВОЛОМ
# =============================================================================
# python src/main_with_options.py --validate --symbol BTC-USDT-SWAP --timeframe 1m

# =============================================================================
# MTF (Multi-Timeframe) МОДУЛЬ
# =============================================================================
# python src/main_with_options.py --mtf                           # Полный цикл MTF
# python src/main_with_options.py --mtf-etl                       # Только ETL процесс
# python src/main_with_options.py --mtf-analysis                  # Только анализ результатов
# python src/main_with_options.py --mtf-validate                  # Валидация MTF данных
# python src/main_with_options.py --mtf --symbol ETH-USDT-SWAP    # MTF для конкретного символа
# python src/main_with_options.py --mtf-analysis --limit 50       # Анализ с лимитом сигналов

# =============================================================================
# НОВЫЕ ВОЗМОЖНОСТИ (УЛУЧШЕННАЯ ВЕРСИЯ)
# =============================================================================

# РЕЖИМЫ ЛОГИРОВАНИЯ
# python src/main_with_options.py --all --verbose                 # Подробный вывод (DEBUG)
# python src/main_with_options.py --all --quiet                   # Только ошибки

# РЕЖИМ ТЕСТИРОВАНИЯ
# python src/main_with_options.py --all --dry-run                 # Тестирование без сохранения в БД

# НАСТРОЙКА ПРОИЗВОДИТЕЛЬНОСТИ
# python src/main_with_options.py --all --max-workers 8           # 8 параллельных воркеров
# python src/main_with_options.py --all --batch-size 200          # Размер батча 200

# КОМБИНИРОВАННЫЕ РЕЖИМЫ
# python src/main_with_options.py --signals --symbol BTC-USDT-SWAP --verbose --dry-run
# python src/main_with_options.py --indicators --max-workers 16 --batch-size 500 --quiet

# ЭКСПОРТ СТАТИСТИКИ
# python src/main_with_options.py --all --verbose                 # Автоматически сохраняет статистику в logs/
# python src/main_with_options.py --signals --verbose             # Статистика только для сигналов

# =============================================================================
# ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ДЛЯ РАЗНЫХ СЦЕНАРИЕВ
# =============================================================================

# БЫСТРАЯ ПРОВЕРКА СИСТЕМЫ
# python src/main_with_options.py --validate --verbose

# ТЕСТИРОВАНИЕ НОВОЙ ФУНКЦИОНАЛЬНОСТИ
# python src/main_with_options.py --signals --symbol BTC-USDT-SWAP --dry-run --verbose

# ПРОИЗВОДСТВЕННЫЙ ЗАПУСК
# python src/main_with_options.py --all --max-workers 8 --batch-size 200

# ОТЛАДКА ПРОБЛЕМ
# python src/main_with_options.py --indicators --symbol ETH-USDT-SWAP --verbose

# МОНИТОРИНГ ПРОИЗВОДИТЕЛЬНОСТИ
# python src/main_with_options.py --all --verbose --max-workers 16 --batch-size 1000
