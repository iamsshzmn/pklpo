"""
Утилиты для работы с async сессиями базы данных
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Контекстный менеджер для работы с базой данных.

    Использование:
        async with get_db_session() as session:
            result = await session.execute(query)
            # commit происходит автоматически при выходе из контекста

    Note: Commit happens automatically on successful completion.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        # Explicit commit with proper await to avoid greenlet issues
        await session.commit()
    except sqlalchemy.exc.SQLAlchemyError as e:
        logger.error(f"SQLAlchemyError: {e}")
        await session.rollback()  # Add explicit rollback
        raise
    except sqlalchemy.exc.IntegrityError as e:
        logger.error(f"IntegrityError: {e}")
        await session.rollback()  # Add explicit rollback
        raise
    except sqlalchemy.exc.OperationalError as e:
        logger.error(f"OperationalError: {e}")
        await session.rollback()  # Add explicit rollback
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await session.rollback()  # Add explicit rollback
        raise
    finally:
        await session.close()  # Ensure session is closed properly


async def execute_with_session(func, *args, **kwargs):
    """
    Выполняет функцию с автоматическим управлением сессией.

    Args:
        func: Асинхронная функция, принимающая session как первый аргумент
        *args: Дополнительные аргументы для функции
        **kwargs: Дополнительные именованные аргументы для функции

    Returns:
        Результат выполнения функции
    """
    async with get_db_session() as session:
        return await func(session, *args, **kwargs)


class DatabaseManager:
    """Менеджер для работы с базой данных с retry логикой"""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def execute_with_retry(self, func, *args, **kwargs):
        """
        Выполняет функцию с повторными попытками при ошибках.

        Args:
            func: Асинхронная функция для выполнения
            *args: Аргументы функции
            **kwargs: Именованные аргументы функции

        Returns:
            Результат выполнения функции
        """
        import asyncio

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except sqlalchemy.exc.SQLAlchemyError as e:
                logger.error(f"SQLAlchemyError: {e}")
                last_exception = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
            except sqlalchemy.exc.IntegrityError as e:
                logger.error(f"IntegrityError: {e}")
                last_exception = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
            except sqlalchemy.exc.OperationalError as e:
                logger.error(f"OperationalError: {e}")
                last_exception = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                last_exception = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

        logger.error(f"Все попытки не удались. Последняя ошибка: {last_exception}")
        raise last_exception
