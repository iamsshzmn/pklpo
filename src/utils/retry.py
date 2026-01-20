"""
Утилиты для retry логики
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class RetryConfig:
    """Конфигурация для retry логики"""

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
