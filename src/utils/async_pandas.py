"""
Утилиты для асинхронной обработки pandas DataFrame
"""

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Глобальный пул потоков для CPU-интенсивных операций
_pandas_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pandas_worker")


class AsyncPandasProcessor:
    """Класс для асинхронной обработки pandas DataFrame"""

    def __init__(self, max_workers: int = 4):
        """
        Инициализация процессора

        Args:
            max_workers: Максимальное количество воркеров для параллельной обработки
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="pandas_worker"
        )

    async def create_dataframe(self, data: list[dict[str, Any]]) -> pd.DataFrame:
        """
        Асинхронно создает DataFrame из списка словарей

        Args:
            data: Список словарей с данными

        Returns:
            pd.DataFrame: Созданный DataFrame
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, pd.DataFrame, data)

    async def dataframe_operation(
        self,
        df: pd.DataFrame,
        operation: Callable[[pd.DataFrame], pd.DataFrame],
        *args,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Выполняет операцию над DataFrame в отдельном потоке

        Args:
            df: DataFrame для обработки
            operation: Функция операции
            *args: Аргументы для операции
            **kwargs: Ключевые аргументы для операции

        Returns:
            pd.DataFrame: Результат операции
        """
        loop = asyncio.get_event_loop()

        def _execute_operation():
            return operation(df, *args, **kwargs)

        return await loop.run_in_executor(self.executor, _execute_operation)

    async def apply_function(
        self, df: pd.DataFrame, func: Callable, axis: int = 0, *args, **kwargs
    ) -> pd.DataFrame:
        """
        Асинхронно применяет функцию к DataFrame

        Args:
            df: DataFrame для обработки
            func: Функция для применения
            axis: Ось применения (0 - строки, 1 - колонки)
            *args: Аргументы для функции
            **kwargs: Ключевые аргументы для функции

        Returns:
            pd.DataFrame: Результат применения функции
        """
        loop = asyncio.get_event_loop()

        def _apply():
            return df.apply(func, axis=axis, *args, **kwargs)

        return await loop.run_in_executor(self.executor, _apply)

    async def groupby_operation(
        self,
        df: pd.DataFrame,
        by: str | list[str],
        operation: Callable,
        *args,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Асинхронно выполняет группировку и операцию

        Args:
            df: DataFrame для обработки
            by: Колонка или список колонок для группировки
            operation: Операция для применения к группам
            *args: Аргументы для операции
            **kwargs: Ключевые аргументы для операции

        Returns:
            pd.DataFrame: Результат группировки
        """
        loop = asyncio.get_event_loop()

        def _groupby():
            return df.groupby(by).apply(operation, *args, **kwargs)

        return await loop.run_in_executor(self.executor, _groupby)

    async def merge_dataframes(
        self, df1: pd.DataFrame, df2: pd.DataFrame, how: str = "inner", *args, **kwargs
    ) -> pd.DataFrame:
        """
        Асинхронно объединяет два DataFrame

        Args:
            df1: Первый DataFrame
            df2: Второй DataFrame
            how: Тип объединения ('inner', 'outer', 'left', 'right')
            *args: Дополнительные аргументы для pd.merge
            **kwargs: Ключевые аргументы для pd.merge

        Returns:
            pd.DataFrame: Объединенный DataFrame
        """
        loop = asyncio.get_event_loop()

        def _merge():
            return pd.merge(df1, df2, how=how, *args, **kwargs)

        return await loop.run_in_executor(self.executor, _merge)

    async def sort_values(
        self,
        df: pd.DataFrame,
        by: str | list[str],
        ascending: bool | list[bool] = True,
        *args,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Асинхронно сортирует DataFrame

        Args:
            df: DataFrame для сортировки
            by: Колонка или список колонок для сортировки
            ascending: Направление сортировки
            *args: Дополнительные аргументы
            **kwargs: Ключевые аргументы

        Returns:
            pd.DataFrame: Отсортированный DataFrame
        """
        loop = asyncio.get_event_loop()

        def _sort():
            return df.sort_values(by=by, ascending=ascending, *args, **kwargs)

        return await loop.run_in_executor(self.executor, _sort)

    async def filter_dataframe(
        self, df: pd.DataFrame, condition: Callable[[pd.DataFrame], pd.Series]
    ) -> pd.DataFrame:
        """
        Асинхронно фильтрует DataFrame

        Args:
            df: DataFrame для фильтрации
            condition: Функция условия фильтрации

        Returns:
            pd.DataFrame: Отфильтрованный DataFrame
        """
        loop = asyncio.get_event_loop()

        def _filter():
            mask = condition(df)
            return df[mask]

        return await loop.run_in_executor(self.executor, _filter)

    async def calculate_indicators(
        self, df: pd.DataFrame, indicator_funcs: dict[str, Callable], *args, **kwargs
    ) -> pd.DataFrame:
        """
        Асинхронно рассчитывает индикаторы

        Args:
            df: DataFrame с OHLCV данными
            indicator_funcs: Словарь функций индикаторов
            *args: Аргументы для функций индикаторов
            **kwargs: Ключевые аргументы для функций индикаторов

        Returns:
            pd.DataFrame: DataFrame с рассчитанными индикаторами
        """
        loop = asyncio.get_event_loop()

        def _calculate():
            result_df = df.copy()
            for name, func in indicator_funcs.items():
                try:
                    result = func(df, *args, **kwargs)
                    if isinstance(result, pd.Series):
                        result_df[name] = result
                    elif isinstance(result, dict):
                        for key, value in result.items():
                            if isinstance(value, pd.Series):
                                result_df[f"{name}_{key}"] = value
                except Exception as e:
                    logger.warning(f"Ошибка при расчете индикатора {name}: {e}")
            return result_df

        return await loop.run_in_executor(self.executor, _calculate)

    async def batch_process_dataframes(
        self,
        dataframes: list[pd.DataFrame],
        operation: Callable[[pd.DataFrame], pd.DataFrame],
        *args,
        **kwargs,
    ) -> list[pd.DataFrame]:
        """
        Пакетная обработка нескольких DataFrame

        Args:
            dataframes: Список DataFrame для обработки
            operation: Операция для применения
            *args: Аргументы для операции
            **kwargs: Ключевые аргументы для операции

        Returns:
            List[pd.DataFrame]: Список обработанных DataFrame
        """
        tasks = []
        for df in dataframes:
            task = self.dataframe_operation(df, operation, *args, **kwargs)
            tasks.append(task)

        return await asyncio.gather(*tasks)

    def __del__(self):
        """Очистка ресурсов"""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)


# Глобальный экземпляр для удобства использования
async_pandas = AsyncPandasProcessor()


# Удобные функции для быстрого использования
async def create_dataframe_async(data: list[dict[str, Any]]) -> pd.DataFrame:
    """Асинхронно создает DataFrame"""
    return await async_pandas.create_dataframe(data)


async def apply_function_async(
    df: pd.DataFrame, func: Callable, axis: int = 0, *args, **kwargs
) -> pd.DataFrame:
    """Асинхронно применяет функцию к DataFrame"""
    return await async_pandas.apply_function(df, func, axis, *args, **kwargs)


async def sort_values_async(
    df: pd.DataFrame,
    by: str | list[str],
    ascending: bool | list[bool] = True,
    *args,
    **kwargs,
) -> pd.DataFrame:
    """Асинхронно сортирует DataFrame"""
    return await async_pandas.sort_values(df, by, ascending, *args, **kwargs)


async def calculate_indicators_async(
    df: pd.DataFrame, indicator_funcs: dict[str, Callable], *args, **kwargs
) -> pd.DataFrame:
    """Асинхронно рассчитывает индикаторы"""
    return await async_pandas.calculate_indicators(df, indicator_funcs, *args, **kwargs)


# Декоратор для автоматического перевода синхронных pandas операций в асинхронные
def async_pandas_operation(func: Callable) -> Callable:
    """
    Декоратор для автоматического выполнения pandas операций в отдельном потоке

    Args:
        func: Функция с pandas операциями

    Returns:
        Callable: Асинхронная версия функции
    """

    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_pandas_executor, func, *args, **kwargs)

    return wrapper


# Примеры использования декоратора
@async_pandas_operation
def calc_rsi_sync(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Синхронный расчет RSI"""
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


@async_pandas_operation
def calc_macd_sync(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, pd.Series]:
    """Синхронный расчет MACD"""
    ema_fast = df["close"].ewm(span=fast).mean()
    ema_slow = df["close"].ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


# Асинхронные версии
async def calc_rsi_async(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Асинхронный расчет RSI"""
    return await calc_rsi_sync(df, period)


async def calc_macd_async(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, pd.Series]:
    """Асинхронный расчет MACD"""
    return await calc_macd_sync(df, fast, slow, signal)
