"""
Унифицированные утилиты для retry логики.

Единая точка входа для всех retry операций в проекте.
Интегрируется с централизованной конфигурацией.

Использование:
    from src.utils.retry import retry_async, retry_sync, get_db_retry, get_api_retry

    # С дефолтными настройками из конфигурации
    @get_db_retry()
    async def fetch_data():
        ...

    # С кастомными параметрами
    @retry_async(max_attempts=5, jitter=True)
    async def call_api():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.config.settings import RetrySettings

logger = logging.getLogger(__name__)


class RetryConfig:
    """
    Конфигурация для retry логики.

    Может быть создана напрямую или из централизованных настроек.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: type[Exception] | tuple = Exception,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions

    @classmethod
    def from_settings(
        cls,
        settings: RetrySettings | None = None,
        preset: str = "default",
    ) -> RetryConfig:
        """
        Создаёт конфигурацию из централизованных настроек.

        Args:
            settings: RetrySettings или None (загрузится автоматически)
            preset: "default", "db", или "api"

        Returns:
            RetryConfig с настройками из конфигурации
        """
        if settings is None:
            from src.config.settings import get_settings
            settings = get_settings().retry

        if preset == "db":
            return cls(
                max_attempts=settings.db_max_attempts,
                base_delay=settings.db_base_delay,
                max_delay=settings.db_max_delay,
                exponential_base=settings.exponential_base,
                jitter=settings.jitter,
            )
        if preset == "api":
            return cls(
                max_attempts=settings.api_max_attempts,
                base_delay=settings.api_base_delay,
                max_delay=settings.api_max_delay,
                exponential_base=settings.exponential_base,
                jitter=settings.jitter,
            )
        # default
        return cls(
            max_attempts=settings.max_attempts,
            base_delay=settings.base_delay,
            max_delay=settings.max_delay,
            exponential_base=settings.exponential_base,
            jitter=settings.jitter,
        )


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Вычисляет задержку для следующей попытки

    Args:
        attempt: Номер попытки (начиная с 1)
        config: Конфигурация retry

    Returns:
        float: Задержка в секундах
    """
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))

    # Ограничиваем максимальной задержкой
    delay = min(delay, config.max_delay)

    # Добавляем jitter для предотвращения thundering herd
    if config.jitter:
        delay = delay * (0.5 + random.random() * 0.5)

    return delay


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: type[Exception] | tuple = Exception,
    on_retry: Callable | None = None,
):
    """
    Декоратор для retry логики в асинхронных функциях

    Args:
        max_attempts: Максимальное количество попыток
        base_delay: Базовая задержка в секундах
        max_delay: Максимальная задержка в секундах
        exponential_base: База для экспоненциальной задержки
        jitter: Добавлять ли случайность к задержке
        exceptions: Исключения, которые нужно перехватывать
        on_retry: Функция, вызываемая при повторной попытке

    Returns:
        Декоратор функции
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        exceptions=exceptions,
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except config.exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        logger.error(
                            f"Функция {func.__name__} не удалась после "
                            f"{config.max_attempts} попыток. Последняя ошибка: {e}"
                        )
                        raise

                    delay = calculate_delay(attempt, config)

                    logger.warning(
                        f"Попытка {attempt}/{config.max_attempts} функции "
                        f"{func.__name__} не удалась: {e}. "
                        f"Повтор через {delay:.2f}с"
                    )

                    if on_retry:
                        try:
                            on_retry(attempt, e, delay)
                        except Exception as retry_error:
                            logger.error(f"Ошибка в on_retry: {retry_error}")

                    await asyncio.sleep(delay)

            # Этот код не должен выполняться, но на всякий случай
            raise last_exception

        return wrapper

    return decorator


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: type[Exception] | tuple = Exception,
    on_retry: Callable | None = None,
):
    """
    Декоратор для retry логики в синхронных функциях

    Args:
        max_attempts: Максимальное количество попыток
        base_delay: Базовая задержка в секундах
        max_delay: Максимальная задержка в секундах
        exponential_base: База для экспоненциальной задержки
        jitter: Добавлять ли случайность к задержке
        exceptions: Исключения, которые нужно перехватывать
        on_retry: Функция, вызываемая при повторной попытке

    Returns:
        Декоратор функции
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        exceptions=exceptions,
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except config.exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        logger.error(
                            f"Функция {func.__name__} не удалась после "
                            f"{config.max_attempts} попыток. Последняя ошибка: {e}"
                        )
                        raise

                    delay = calculate_delay(attempt, config)

                    logger.warning(
                        f"Попытка {attempt}/{config.max_attempts} функции "
                        f"{func.__name__} не удалась: {e}. "
                        f"Повтор через {delay:.2f}с"
                    )

                    if on_retry:
                        try:
                            on_retry(attempt, e, delay)
                        except Exception as retry_error:
                            logger.error(f"Ошибка в on_retry: {retry_error}")

                    time.sleep(delay)

            # Этот код не должен выполняться, но на всякий случай
            raise last_exception

        return wrapper

    return decorator


class RetryableOperation:
    """Класс для выполнения операций с retry логикой"""

    def __init__(self, config: RetryConfig):
        self.config = config

    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполняет асинхронную функцию с retry логикой

        Args:
            func: Асинхронная функция для выполнения
            *args: Аргументы функции
            **kwargs: Именованные аргументы функции

        Returns:
            Результат выполнения функции
        """
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except self.config.exceptions as e:
                last_exception = e

                if attempt == self.config.max_attempts:
                    logger.error(
                        f"Операция не удалась после {self.config.max_attempts} попыток. "
                        f"Последняя ошибка: {e}"
                    )
                    raise

                delay = calculate_delay(attempt, self.config)

                logger.warning(
                    f"Попытка {attempt}/{self.config.max_attempts} не удалась: {e}. "
                    f"Повтор через {delay:.2f}с"
                )

                await asyncio.sleep(delay)

        raise last_exception

    def execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполняет синхронную функцию с retry логикой

        Args:
            func: Синхронная функция для выполнения
            *args: Аргументы функции
            **kwargs: Именованные аргументы функции

        Returns:
            Результат выполнения функции
        """
        import time

        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except self.config.exceptions as e:
                last_exception = e

                if attempt == self.config.max_attempts:
                    logger.error(
                        f"Операция не удалась после {self.config.max_attempts} попыток. "
                        f"Последняя ошибка: {e}"
                    )
                    raise

                delay = calculate_delay(attempt, self.config)

                logger.warning(
                    f"Попытка {attempt}/{self.config.max_attempts} не удалась: {e}. "
                    f"Повтор через {delay:.2f}с"
                )

                time.sleep(delay)

        raise last_exception


# =============================================================================
# Factory functions for pre-configured retry decorators
# =============================================================================

def get_db_retry(
    exceptions: type[Exception] | tuple | None = None,
    on_retry: Callable | None = None,
) -> Callable:
    """
    Возвращает декоратор для database операций с настройками из конфигурации.

    Args:
        exceptions: Исключения для перехвата (по умолчанию: DB-related)
        on_retry: Callback при retry

    Returns:
        Декоратор retry_async с DB настройками

    Example:
        @get_db_retry()
        async def insert_data(conn, data):
            await conn.execute("INSERT ...")
    """
    config = RetryConfig.from_settings(preset="db")

    if exceptions is None:
        # Common database exceptions
        db_exceptions: list[type[Exception]] = [
            ConnectionError,
            TimeoutError,
            OSError,
        ]
        try:
            import asyncpg
            db_exceptions.extend([
                asyncpg.PostgresConnectionError,
                asyncpg.CannotConnectNowError,
                asyncpg.ConnectionDoesNotExistError,
                asyncpg.TooManyConnectionsError,
            ])
        except ImportError:
            pass
        exceptions = tuple(db_exceptions)

    return retry_async(
        max_attempts=config.max_attempts,
        base_delay=config.base_delay,
        max_delay=config.max_delay,
        exponential_base=config.exponential_base,
        jitter=config.jitter,
        exceptions=exceptions,
        on_retry=on_retry,
    )


def get_api_retry(
    exceptions: type[Exception] | tuple | None = None,
    on_retry: Callable | None = None,
) -> Callable:
    """
    Возвращает декоратор для API вызовов с настройками из конфигурации.

    Args:
        exceptions: Исключения для перехвата (по умолчанию: HTTP-related)
        on_retry: Callback при retry

    Returns:
        Декоратор retry_async с API настройками

    Example:
        @get_api_retry()
        async def fetch_market_data(symbol):
            async with session.get(url) as response:
                return await response.json()
    """
    config = RetryConfig.from_settings(preset="api")

    if exceptions is None:
        # Common API/HTTP exceptions
        api_exceptions: list[type[Exception]] = [
            ConnectionError,
            TimeoutError,
            OSError,
        ]
        try:
            import aiohttp
            api_exceptions.extend([
                aiohttp.ClientError,
                aiohttp.ServerTimeoutError,
            ])
        except ImportError:
            pass
        try:
            import httpx
            api_exceptions.append(httpx.HTTPError)
        except ImportError:
            pass
        exceptions = tuple(api_exceptions)

    return retry_async(
        max_attempts=config.max_attempts,
        base_delay=config.base_delay,
        max_delay=config.max_delay,
        exponential_base=config.exponential_base,
        jitter=config.jitter,
        exceptions=exceptions,
        on_retry=on_retry,
    )


def get_default_retry(
    exceptions: type[Exception] | tuple = Exception,
    on_retry: Callable | None = None,
) -> Callable:
    """
    Возвращает декоратор с дефолтными настройками из конфигурации.

    Args:
        exceptions: Исключения для перехвата
        on_retry: Callback при retry

    Returns:
        Декоратор retry_async с дефолтными настройками
    """
    config = RetryConfig.from_settings(preset="default")

    return retry_async(
        max_attempts=config.max_attempts,
        base_delay=config.base_delay,
        max_delay=config.max_delay,
        exponential_base=config.exponential_base,
        jitter=config.jitter,
        exceptions=exceptions,
        on_retry=on_retry,
    )


# Aliases for backward compatibility
database_retry = get_db_retry
api_retry = get_api_retry
