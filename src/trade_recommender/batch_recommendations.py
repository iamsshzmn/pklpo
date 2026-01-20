"""
Скрипт для массового пересчёта торговых рекомендаций
Обрабатывает все score_results и создаёт торговые рекомендации
"""

import asyncio
import logging
import multiprocessing
import sys
import time
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

from src.database import get_async_session
from src.scoring_engine.models import ScoreResult
from src.trade_recommender.recommend import recommend_for_score

logger = logging.getLogger(__name__)
# Настраиваем логгер для записи только в файл, а не в консоль
logger.setLevel(logging.DEBUG)
# Удаляем все существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Добавляем только файловый обработчик
file_handler = logging.FileHandler("trade_recommender.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


# Функции для управления логированием
def enable_verbose_logging():
    """Включает подробное логирование в консоль"""
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def disable_verbose_logging():
    """Отключает подробное логирование в консоль"""
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            logger.removeHandler(handler)


# Константы для параллельной обработки
MAX_WORKERS = min(multiprocessing.cpu_count(), 8)  # количество параллельных потоков
CHUNK_SIZE = 10  # размер пакета для параллельной обработки


async def get_all_score_ids(session: AsyncSession) -> list[int]:
    """Получает все ID из score_results"""
    try:
        query = select(ScoreResult.id).order_by(ScoreResult.id)
        result = await session.execute(query)
        score_ids = [row[0] for row in result.fetchall()]
        logger.debug(f"📊 Найдено {len(score_ids)} score_results для обработки")
        return score_ids
    except Exception as e:
        logger.error(f"Ошибка при получении score_ids: {e}")
        return []


async def process_single_recommendation(
    score_id: int, dry_run: bool = False
) -> tuple[bool, str, float]:
    """
    Обрабатывает одну рекомендацию

    Args:
        score_id: ID записи score
        dry_run: Если True - не сохраняет в БД

    Returns:
        Кортеж (успех, статус, время обработки)
    """
    start_time = time.time()

    # Отключаем подробное логирование для консоли во время расчетов
    disable_verbose_logging()

    try:
        # Генерируем рекомендацию
        recommendation = await recommend_for_score(score_id, dry_run=dry_run)
        calculation_time = time.time() - start_time

        # Анализируем результат
        status = recommendation.get("status", "unknown")

        if status == "ready":
            logger.debug(
                f"✅ {score_id}: Рекомендация готова за {calculation_time:.2f}с"
            )
            return True, "ready", calculation_time
        if status == "rejected":
            reason = recommendation.get("message", "Неизвестная причина")
            logger.debug(
                f"❌ {score_id}: Отклонено - {reason} за {calculation_time:.2f}с"
            )
            return False, "rejected", calculation_time
        if status == "error":
            error_msg = recommendation.get("message", "Неизвестная ошибка")
            logger.error(
                f"💥 {score_id}: Ошибка - {error_msg} за {calculation_time:.2f}с"
            )
            return False, "error", calculation_time
        logger.warning(
            f"⚠️ {score_id}: Неизвестный статус - {status} за {calculation_time:.2f}с"
        )
        return False, "unknown", calculation_time

    except Exception as e:
        calculation_time = time.time() - start_time
        logger.error(
            f"💥 {score_id}: Критическая ошибка - {e} за {calculation_time:.2f}с"
        )
        return False, "error", calculation_time


async def process_chunk_parallel(
    chunk: list[int], dry_run: bool = False
) -> list[tuple[bool, str, float]]:
    """
    Обрабатывает чанк рекомендаций параллельно

    Args:
        chunk: Список score_ids для обработки
        dry_run: Если True - не сохраняет в БД

    Returns:
        List[Tuple[bool, str, float]]: Результаты обработки
    """
    # Создаём задачи для параллельной обработки
    tasks = []
    for score_id in chunk:
        task = asyncio.create_task(process_single_recommendation(score_id, dry_run))
        tasks.append(task)

    # Выполняем все задачи параллельно
    chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Обрабатываем результаты
    processed_results = []
    for _i, result in enumerate(chunk_results):
        if isinstance(result, Exception):
            processed_results.append((False, "error", 0.0))
        else:
            processed_results.append(result)

    return processed_results


async def process_score_recommendations_parallel(
    score_ids: list[int], dry_run: bool = False
) -> dict:
    """
    Обрабатывает список score_ids параллельно и создаёт рекомендации

    Args:
        score_ids: Список ID для обработки
        dry_run: Если True - не сохраняет в БД

    Returns:
        Dict: Статистика обработки
    """
    results = {
        "total": len(score_ids),
        "processed": 0,
        "ready": 0,
        "rejected": 0,
        "errors": 0,
        "details": [],
    }

    logger.info(
        f"🚀 Запуск параллельной обработки {len(score_ids)} score_results (dry_run={dry_run})"
    )
    logger.info(f"⚡ Используем {MAX_WORKERS} параллельных потоков")
    # Включаем подробное логирование для основных сообщений
    enable_verbose_logging()

    if not score_ids:
        logger.warning("⚠️ Нет score_ids для обработки")
        return results

    # Разбиваем на чанки для параллельной обработки
    chunks = [
        score_ids[i : i + CHUNK_SIZE] for i in range(0, len(score_ids), CHUNK_SIZE)
    ]
    logger.debug(f"📦 Разбито на {len(chunks)} чанков по {CHUNK_SIZE} записей")

    total_calculation_time = 0.0

    # Параллельная обработка с прогресс баром
    with tqdm(
        total=len(chunks),
        desc="🎯 Параллельная обработка рекомендаций",
        unit="чанк",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        position=0,
        leave=True,
        dynamic_ncols=True,
    ) as pbar:
        for chunk in chunks:
            try:
                # Обрабатываем чанк параллельно
                chunk_results = await process_chunk_parallel(chunk, dry_run)

                # Подсчитываем результаты
                for success, status, calc_time in chunk_results:
                    results["processed"] += 1
                    total_calculation_time += calc_time

                    if status == "ready":
                        results["ready"] += 1
                    elif status == "rejected":
                        results["rejected"] += 1
                    else:
                        results["errors"] += 1

                    # Сохраняем детали
                    results["details"].append(
                        {
                            "score_id": chunk[
                                chunk_results.index((success, status, calc_time))
                            ],
                            "status": status,
                            "success": success,
                        }
                    )

                pbar.update(1)
                pbar.set_postfix(
                    {
                        "Готово": f"{results['ready']}",
                        "Отклонено": f"{results['rejected']}",
                        "Ошибок": f"{results['errors']}",
                    }
                )

            except Exception as e:
                logger.error(f"❌ Ошибка при обработке чанка: {e}")
                results["errors"] += len(chunk)
                pbar.update(1)

    # Итоговая статистика
    logger.info("=" * 60)
    logger.info("📊 ИТОГОВАЯ СТАТИСТИКА РЕКОМЕНДАЦИЙ:")
    logger.info(f"📋 Всего записей: {results['total']}")
    logger.info(f"✅ Обработано: {results['processed']}")
    logger.info(f"🎯 Готовых рекомендаций: {results['ready']}")
    logger.info(f"❌ Отклонённых: {results['rejected']}")
    logger.info(f"💥 Ошибок: {results['errors']}")
    logger.info(f"⏱️ Общее время расчётов: {total_calculation_time:.2f}с")

    if results["ready"] > 0:
        success_rate = results["ready"] / results["processed"] * 100
        avg_time = total_calculation_time / results["processed"]
        logger.info(f"📈 Успешность: {success_rate:.1f}%")
        logger.info(f"⏱️ Среднее время на рекомендацию: {avg_time:.2f}с")

    logger.info("🎉 Генерация рекомендаций завершена успешно!")

    return results


async def process_score_recommendations(
    score_ids: list[int], dry_run: bool = False
) -> dict:
    """Обрабатывает список score_ids и создаёт рекомендации (последовательно)"""
    results = {
        "total": len(score_ids),
        "processed": 0,
        "ready": 0,
        "rejected": 0,
        "errors": 0,
        "details": [],
    }

    logger.info(
        f"Начинаем обработку {len(score_ids)} score_results (dry_run={dry_run})"
    )

    for i, score_id in enumerate(score_ids, 1):
        try:
            logger.info(f"[{i}/{len(score_ids)}] Обработка score_id={score_id}")

            # Генерируем рекомендацию
            recommendation = await recommend_for_score(score_id, dry_run=dry_run)

            # Анализируем результат
            status = recommendation.get("status", "unknown")
            results["processed"] += 1

            if status == "ready":
                results["ready"] += 1
                logger.info(f"✅ score_id={score_id}: Рекомендация готова")
            elif status == "rejected":
                results["rejected"] += 1
                reason = recommendation.get("message", "Неизвестная причина")
                logger.info(f"❌ score_id={score_id}: Отклонено - {reason}")
            elif status == "error":
                results["errors"] += 1
                error_msg = recommendation.get("message", "Неизвестная ошибка")
                logger.error(f"💥 score_id={score_id}: Ошибка - {error_msg}")
            else:
                results["errors"] += 1
                logger.warning(f"⚠️ score_id={score_id}: Неизвестный статус - {status}")

            # Сохраняем детали
            results["details"].append(
                {
                    "score_id": score_id,
                    "status": status,
                    "symbol": recommendation.get("symbol"),
                    "timeframe": recommendation.get("timeframe"),
                    "message": recommendation.get("message"),
                }
            )

            # Небольшая пауза между обработкой
            if i % 10 == 0:
                logger.info(
                    f"Прогресс: {i}/{len(score_ids)} ({i/len(score_ids)*100:.1f}%)"
                )
                await asyncio.sleep(0.1)  # Небольшая пауза каждые 10 записей

        except Exception as e:
            results["errors"] += 1
            logger.error(
                f"💥 Критическая ошибка при обработке score_id={score_id}: {e}"
            )
            results["details"].append(
                {"score_id": score_id, "status": "error", "message": str(e)}
            )

    return results


async def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Массовый пересчёт торговых рекомендаций"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Не сохранять результаты в БД (по умолчанию)",
    )
    parser.add_argument("--save", action="store_true", help="Сохранить результаты в БД")
    parser.add_argument(
        "--limit", type=int, help="Ограничить количество обрабатываемых записей"
    )
    parser.add_argument(
        "--offset", type=int, default=0, help="Начать с указанного смещения"
    )

    args = parser.parse_args()
    dry_run = not args.save

    logger.info("Запуск массового пересчёта рекомендаций")
    logger.info(f"dry_run={dry_run}")
    if args.limit:
        logger.info(f"limit={args.limit}")
    if args.offset:
        logger.info(f"offset={args.offset}")

    try:
        async for session in get_async_session():
            # Получаем все score_ids
            all_score_ids = await get_all_score_ids(session)

            if not all_score_ids:
                logger.warning("Нет score_results для обработки")
                return

            # Применяем ограничения
            score_ids = all_score_ids[args.offset :]
            if args.limit:
                score_ids = score_ids[: args.limit]

            logger.info(f"Будет обработано {len(score_ids)} записей")

            # Обрабатываем рекомендации
            results = await process_score_recommendations_parallel(
                score_ids, dry_run=dry_run
            )

            # Выводим итоговую статистику
            print("\n" + "=" * 60)
            print("📊 ИТОГОВАЯ СТАТИСТИКА")
            print("=" * 60)
            print(f"📋 Всего записей: {results['total']}")
            print(f"✅ Обработано: {results['processed']}")
            print(f"🎯 Готовых рекомендаций: {results['ready']}")
            print(f"❌ Отклонённых: {results['rejected']}")
            print(f"💥 Ошибок: {results['errors']}")

            if results["ready"] > 0:
                success_rate = results["ready"] / results["processed"] * 100
                print(f"📈 Успешность: {success_rate:.1f}%")

            print("=" * 60)

            # Выводим детали по ошибкам
            if results["errors"] > 0:
                print("\n🔍 ДЕТАЛИ ОШИБОК:")
                error_details = [
                    d for d in results["details"] if d["status"] == "error"
                ]
                for detail in error_details[:10]:  # Показываем первые 10 ошибок
                    print(
                        f"  score_id={detail['score_id']}: {detail.get('message', 'Нет сообщения')}"
                    )
                if len(error_details) > 10:
                    print(f"  ... и ещё {len(error_details) - 10} ошибок")

            break

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
