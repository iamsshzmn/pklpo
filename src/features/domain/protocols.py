"""
Domain protocols for indicator calculation.

Introduces minimal abstractions without changing current behavior or
requiring immediate implementation updates in existing modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@runtime_checkable
class IndicatorAdapter(Protocol):
    """Adapter contract for backend-specific indicator calls."""

    def __call__(self, df: pd.DataFrame, **kwargs: object) -> pd.DataFrame: ...


@runtime_checkable
class IndicatorCalculator(Protocol):
    """Abstraction for calculating a single indicator.

    Implementations may rely on pandas_ta or custom logic.
    """

    def calculate(self, df_ohlcv: pd.DataFrame, **params) -> pd.Series: ...


@runtime_checkable
class BatchIndicatorCalculator(Protocol):
    """Abstraction for batch calculation of multiple indicators.

    Compatible with the current API: accepts a DataFrame and a set of
    indicator names, returns either dict[name -> Series] or a DataFrame.
    """

    def calculate_many(
        self, df_ohlcv: pd.DataFrame, names: set[str], **params
    ) -> dict[str, pd.Series] | pd.DataFrame: ...


@runtime_checkable
class FeatureCalculator(Protocol):
    """
    High-level protocol for feature calculation.

    This is the main interface used by the application layer.
    It allows swapping implementations, for example in tests or for GPU acceleration.

    Compatible with the compute_features() signature.
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
        Calculate features for OHLCV data.

        Args:
            df_ohlcv: DataFrame with open, high, low, close, volume columns
            specs: List of indicator names (None = all available)
            volatility_normalize: Whether to apply volatility normalization
            normalize_window: Normalization window

        Returns:
            DataFrame with calculated indicators
        """
        ...


@runtime_checkable
class OHLCVValidator(Protocol):
    """Protocol for OHLCV data validation."""

    def validate(self, df: pd.DataFrame) -> bool:
        """
        Validate OHLCV data.

        Args:
            df: DataFrame to validate

        Returns:
            True if the data is valid

        Raises:
            ValueError: If the data is invalid
        """
        ...


@runtime_checkable
class FeatureNormalizer(Protocol):
    """Protocol for feature normalization."""

    def normalize(
        self,
        df: pd.DataFrame,
        window: int = 20,
    ) -> pd.DataFrame:
        """
        Normalize features.

        Args:
            df: DataFrame with indicators
            window: Normalization window

        Returns:
            Normalized DataFrame
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
