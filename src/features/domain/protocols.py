"""
Domain protocols (абстракции) для расчета индикаторов.

Вводим минимальный протокол без изменения текущего поведения
и без обязательной имплементации существующими модулями.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@runtime_checkable
class IndicatorCalculator(Protocol):
    """Абстракция вычислителя одного индикатора.

    Реализации могут опираться на pandas_ta или кастомную логику.
    """

    def calculate(self, df_ohlcv: pd.DataFrame, **params) -> pd.Series: ...


@runtime_checkable
class BatchIndicatorCalculator(Protocol):
    """Абстракция пакетного вычислителя множества индикаторов.

    Совместима с текущим API: принимает df и множество имен индикаторов,
    возвращает dict[name -> Series] или DataFrame.
    """

    def calculate_many(
        self, df_ohlcv: pd.DataFrame, names: set[str], **params
    ) -> dict[str, pd.Series] | pd.DataFrame: ...


@runtime_checkable
class FeatureCalculator(Protocol):
    """
    Высокоуровневый Protocol для расчёта features.

    Это основной интерфейс для подключения к application layer.
    Позволяет подменять реализацию (например, для тестов или GPU-ускорения).

    Совместим с сигнатурой compute_features().
    """

    def calculate(
        self,
        df_ohlcv: pd.DataFrame,
        specs: list[str] | None = None,
        *,
        volatility_normalize: bool = False,
        normalize_window: int = 20,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Рассчитать features для OHLCV данных.

        Args:
            df_ohlcv: DataFrame с колонками open, high, low, close, volume
            specs: Список имён индикаторов (None = все доступные)
            volatility_normalize: Применить волатильностную нормализацию
            normalize_window: Окно для нормализации

        Returns:
            DataFrame с рассчитанными индикаторами
        """
        ...


@runtime_checkable
class OHLCVValidator(Protocol):
    """Protocol для валидации OHLCV данных."""

    def validate(self, df: pd.DataFrame) -> bool:
        """
        Проверить корректность OHLCV данных.

        Args:
            df: DataFrame для валидации

        Returns:
            True если данные корректны

        Raises:
            ValueError: если данные некорректны
        """
        ...


@runtime_checkable
class FeatureNormalizer(Protocol):
    """Protocol для нормализации features."""

    def normalize(
        self,
        df: pd.DataFrame,
        window: int = 20,
    ) -> pd.DataFrame:
        """
        Нормализовать features.

        Args:
            df: DataFrame с индикаторами
            window: Окно для нормализации

        Returns:
            Нормализованный DataFrame
        """
        ...


@runtime_checkable
class TimestampValidator(Protocol):
    """
    Protocol for timestamp validation (DIP compliance).

    Allows injecting custom timestamp validation logic without
    hard-coding dependencies on specific implementations.
    """

    def validate(self, timestamp: int | None, row_index: int | str) -> bool:
        """
        Validate a timestamp value.

        Args:
            timestamp: Timestamp in milliseconds
            row_index: Row index for error messages

        Returns:
            True if timestamp is valid
        """
        ...


@runtime_checkable
class GroupCalculator(Protocol):
    """
    Protocol for indicator group calculators (LSP compliance).

    All group calculators must follow this interface to ensure
    Liskov Substitution Principle compliance.
    """

    def __call__(
        self,
        df: pd.DataFrame,
        available: set[str],
        **kwargs,
    ) -> dict[str, pd.Series]:
        """
        Calculate indicators for a group.

        Args:
            df: DataFrame with OHLCV data
            available: Set of indicator names to calculate
            **kwargs: Additional parameters

        Returns:
            Dictionary mapping indicator names to pandas Series
        """
        ...
