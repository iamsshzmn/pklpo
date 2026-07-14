"""
Утилиты для батчевой обработки данных
"""

import asyncio
import logging
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class BatchProcessor:
    """Класс для батчевой обработки данных"""

    def __init__(self, batch_size: int = 100, max_workers: int = 4):
        """
        Инициализация процессора

        Args:
            batch_size: Размер батча
            max_workers: Максимальное количество воркеров
        """
        self.batch_size = batch_size
        self.max_workers = max_workers

    async def process_batches(
        self,
        items: list[T],
        processor_func: Callable[[list[T]], R],
        save_func: Callable[[list[R]], None] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[R]:
        """
        Обрабатывает элементы батчами

        Args:
            items: Список элементов для обработки
            processor_func: Функция обработки батча
            save_func: Функция сохранения результатов (опционально)
            progress_callback: Функция обратного вызова для прогресса

        Returns:
            List[R]: Результаты обработки
        """
        results = []
        total_items = len(items)

        for i in range(0, total_items, self.batch_size):
            batch = items[i : i + self.batch_size]

            try:
                # Обрабатываем батч
                batch_result = await processor_func(batch)

                if save_func and batch_result:
                    await save_func(batch_result)

                if isinstance(batch_result, list):
                    results.extend(batch_result)
                else:
                    results.append(batch_result)

                # Вызываем callback прогресса
                if progress_callback:
                    progress_callback(
                        min(i + self.batch_size, total_items), total_items
                    )

                logger.debug(
                    f"Обработан батч {i // self.batch_size + 1}: {len(batch)} элементов"
                )

            except Exception as e:
                logger.error(
                    f"Ошибка при обработке батча {i // self.batch_size + 1}: {e}"
                )
                continue

        return results

    async def process_batches_parallel(
        self,
        items: list[T],
        processor_func: Callable[[list[T]], R],
        save_func: Callable[[list[R]], None] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[R]:
        """
        Обрабатывает элементы батчами параллельно

        Args:
            items: Список элементов для обработки
            processor_func: Функция обработки батча
            save_func: Функция сохранения результатов (опционально)
            progress_callback: Функция обратного вызова для прогресса

        Returns:
            List[R]: Результаты обработки
        """
        # Разбиваем на батчи
        batches = [
            items[i : i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]

        # Создаем семафор для ограничения параллельности
        semaphore = asyncio.Semaphore(self.max_workers)

        async def process_batch_with_semaphore(batch: list[T]) -> R:
            async with semaphore:
                return await processor_func(batch)

        # Запускаем все батчи параллельно
        tasks = [process_batch_with_semaphore(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обрабатываем результаты
        results = []
        for i, batch_result in enumerate(batch_results):
            if isinstance(batch_result, Exception):
                logger.error(f"Ошибка в батче {i + 1}: {batch_result}")
                continue

            if save_func and batch_result:
                await save_func(batch_result)

            if isinstance(batch_result, list):
                results.extend(batch_result)
            else:
                results.append(batch_result)

            # Вызываем callback прогресса
            if progress_callback:
                progress_callback(
                    min((i + 1) * self.batch_size, len(items)), len(items)
                )

        return results


class DatabaseBatchProcessor:
    """Специализированный процессор для работы с базой данных"""

    def __init__(self, batch_size: int = 100):
        """
        Инициализация процессора БД

        Args:
            batch_size: Размер батча для операций с БД
        """
        self.batch_size = batch_size

    async def batch_insert(
        self, session, model_class, items: list[dict], on_conflict: str | None = None
    ) -> int:
        """
        Выполняет батчевую вставку в БД

        Args:
            session: Сессия БД
            model_class: Класс модели SQLAlchemy
            items: Список словарей с данными
            on_conflict: Действие при конфликте (опционально)

        Returns:
            int: Количество вставленных записей
        """
        inserted_count = 0

        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]

            try:
                # Создаем объекты модели
                model_objects = [model_class(**item) for item in batch]

                # Добавляем в сессию
                session.add_all(model_objects)

                # Flush для освобождения памяти
                await session.flush()

                inserted_count += len(batch)
                logger.debug(f"Вставлен батч: {len(batch)} записей")

            except Exception as e:
                logger.error(
                    f"Ошибка при вставке батча {i // self.batch_size + 1}: {e}"
                )
                await session.rollback()
                continue

        return inserted_count

    async def batch_update(
        self,
        session,
        model_class,
        items: list[dict],
        update_fields: list[str],
        where_field: str = "id",
    ) -> int:
        """
        Выполняет батчевое обновление в БД

        Args:
            session: Сессия БД
            model_class: Класс модели SQLAlchemy
            items: Список словарей с данными
            update_fields: Поля для обновления
            where_field: Поле для условия WHERE

        Returns:
            int: Количество обновленных записей
        """
        updated_count = 0

        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]

            try:
                for item in batch:
                    # Получаем условие WHERE
                    where_value = item.get(where_field)
                    if not where_value:
                        continue

                    # Строим запрос обновления
                    update_data = {
                        field: item[field] for field in update_fields if field in item
                    }

                    if update_data:
                        await session.execute(
                            session.query(model_class)
                            .filter(getattr(model_class, where_field) == where_value)
                            .update(update_data)
                        )
                        updated_count += 1

                # Flush для освобождения памяти
                await session.flush()
                logger.debug(f"Обновлен батч: {len(batch)} записей")

            except Exception as e:
                logger.error(
                    f"Ошибка при обновлении батча {i // self.batch_size + 1}: {e}"
                )
                await session.rollback()
                continue

        return updated_count


def create_batch_processor(
    batch_size: int = 100, max_workers: int = 4
) -> BatchProcessor:
    """
    Создает экземпляр BatchProcessor

    Args:
        batch_size: Размер батча
        max_workers: Максимальное количество воркеров

    Returns:
        BatchProcessor: Экземпляр процессора
    """
    return BatchProcessor(batch_size, max_workers)


def create_db_batch_processor(batch_size: int = 100) -> DatabaseBatchProcessor:
    """
    Создает экземпляр DatabaseBatchProcessor

    Args:
        batch_size: Размер батча для операций с БД

    Returns:
        DatabaseBatchProcessor: Экземпляр процессора БД
    """
    return DatabaseBatchProcessor(batch_size)
