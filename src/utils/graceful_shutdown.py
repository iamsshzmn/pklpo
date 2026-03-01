"""
Утилиты для graceful shutdown приложения
"""

import asyncio
import logging
import signal
from collections.abc import Callable

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Менеджер для graceful shutdown приложения"""

    def __init__(self):
        self.shutdown_handlers: list[Callable] = []
        self.is_shutting_down = False
        self._original_handlers = {}

    def add_shutdown_handler(self, handler: Callable) -> None:
        """
        Добавляет обработчик для выполнения при shutdown

        Args:
            handler: Функция для выполнения при shutdown
        """
        self.shutdown_handlers.append(handler)

    def remove_shutdown_handler(self, handler: Callable) -> None:
        """
        Удаляет обработчик shutdown

        Args:
            handler: Функция для удаления
        """
        if handler in self.shutdown_handlers:
            self.shutdown_handlers.remove(handler)

    async def shutdown(self, signal_name: str | None = None) -> None:
        """
        Выполняет graceful shutdown

        Args:
            signal_name: Имя сигнала, вызвавшего shutdown
        """
        if self.is_shutting_down:
            logger.warning("Shutdown уже выполняется")
            return

        self.is_shutting_down = True

        if signal_name:
            logger.info(f"Получен сигнал {signal_name}, начинаем graceful shutdown")
        else:
            logger.info("Начинаем graceful shutdown")

        # Выполняем все обработчики shutdown
        for handler in self.shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
                logger.debug(f"Обработчик shutdown выполнен: {handler.__name__}")
            except Exception as e:
                logger.error(f"Ошибка в обработчике shutdown {handler.__name__}: {e}")

        logger.info("Graceful shutdown завершен")

    def setup_signal_handlers(self) -> None:
        """Настраивает обработчики сигналов"""
        signals = [signal.SIGINT, signal.SIGTERM]

        for sig in signals:
            self._original_handlers[sig] = signal.signal(sig, self._signal_handler)

    def restore_signal_handlers(self) -> None:
        """Восстанавливает оригинальные обработчики сигналов"""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """Обработчик сигналов"""
        signal_name = signal.Signals(signum).name
        logger.info(f"Получен сигнал {signal_name}")

        # Запускаем shutdown в отдельной задаче
        asyncio.create_task(self.shutdown(signal_name))

    async def run_with_shutdown(self, main_func: Callable, *args, **kwargs):
        """
        Запускает основную функцию с поддержкой graceful shutdown

        Args:
            main_func: Основная функция приложения
            *args: Аргументы для основной функции
            **kwargs: Именованные аргументы для основной функции
        """
        try:
            self.setup_signal_handlers()

            if asyncio.iscoroutinefunction(main_func):
                await main_func(*args, **kwargs)
            else:
                main_func(*args, **kwargs)

        except KeyboardInterrupt:
            logger.info("Получен KeyboardInterrupt")
            await self.shutdown("SIGINT")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            await self.shutdown()
        finally:
            self.restore_signal_handlers()


# Глобальный экземпляр для использования в приложении
shutdown_manager = GracefulShutdown()


def add_shutdown_handler(handler: Callable) -> None:
    """
    Добавляет обработчик shutdown к глобальному менеджеру

    Args:
        handler: Функция для выполнения при shutdown
    """
    shutdown_manager.add_shutdown_handler(handler)


def remove_shutdown_handler(handler: Callable) -> None:
    """
    Удаляет обработчик shutdown из глобального менеджера

    Args:
        handler: Функция для удаления
    """
    shutdown_manager.remove_shutdown_handler(handler)


async def run_with_shutdown(main_func: Callable, *args, **kwargs):
    """
    Запускает основную функцию с поддержкой graceful shutdown

    Args:
        main_func: Основная функция приложения
        *args: Аргументы для основной функции
        **kwargs: Именованные аргументы для основной функции
    """
    await shutdown_manager.run_with_shutdown(main_func, *args, **kwargs)


class ShutdownContext:
    """Контекстный менеджер для graceful shutdown"""

    def __init__(self, handlers: list[Callable] | None = None):
        self.handlers = handlers or []
        self.original_handlers = {}

    async def __aenter__(self):
        """Вход в контекст"""
        # Добавляем обработчики
        for handler in self.handlers:
            add_shutdown_handler(handler)

        # Настраиваем обработчики сигналов
        shutdown_manager.setup_signal_handlers()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста"""
        # Выполняем shutdown если есть исключение
        if exc_type is not None:
            await shutdown_manager.shutdown()

        # Восстанавливаем обработчики сигналов
        shutdown_manager.restore_signal_handlers()

        # Удаляем обработчики
        for handler in self.handlers:
            remove_shutdown_handler(handler)


# Утилиты для работы с задачами
async def cancel_all_tasks():
    """Отменяет все запущенные задачи"""
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]

    if tasks:
        logger.info(f"Отменяем {len(tasks)} задач")

        for task in tasks:
            task.cancel()

        # Ждем завершения всех задач
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Все задачи отменены")


async def wait_for_shutdown(timeout: float = 30.0):
    """
    Ждет завершения shutdown с таймаутом

    Args:
        timeout: Таймаут в секундах
    """
    try:
        await asyncio.wait_for(
            asyncio.gather(
                *[
                    asyncio.create_task(handler())
                    for handler in shutdown_manager.shutdown_handlers
                ]
            ),
            timeout=timeout,
        )
    except TimeoutError:
        logger.warning(f"Shutdown не завершился за {timeout} секунд")


# Декоратор для автоматического добавления shutdown handler
def shutdown_handler(func: Callable) -> Callable:
    """
    Декоратор для автоматического добавления функции как shutdown handler

    Args:
        func: Функция для добавления как shutdown handler

    Returns:
        Callable: Оригинальная функция
    """
    add_shutdown_handler(func)
    return func
