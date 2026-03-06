"""
Domain protocols for indicator calculation.

Introduces minimal abstractions without changing current behavior or
requiring immediate implementation updates in existing modules.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
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
class FeatureSaveValidator(Protocol):
    """Protocol for pre-save validation of calculated feature frames."""

    def validate_save_dataframe(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> dict[str, object]:
        """Validate a features DataFrame before persistence."""
        ...


@runtime_checkable
class FeatureSaveObservation(Protocol):
    """Active observation session for save orchestration."""

    def record_success(self, *, rows_processed: int, rows_saved: int) -> None:
        """Record successful completion statistics."""
        ...

    def record_error(self, error: Exception | str) -> None:
        """Record a failed save attempt."""
        ...


@runtime_checkable
class FeatureSaveObserver(Protocol):
    """Protocol for save observability hooks."""

    def observe(
        self,
        *,
        operation: str,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        log_memory: bool = False,
    ) -> AbstractContextManager[FeatureSaveObservation]:
        """Create an observation scope for a save operation."""
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
class IndicatorRepository(Protocol):
    """
    Persistence abstraction for batched indicator storage.

    Separates application logic from concrete database implementation,
    allowing the save pipeline to be tested without real asyncpg access.
    """

    async def save_batch(
        self,
        records: list[dict],
        symbol: str,
        timeframe: str,
    ) -> int:
        """
        Save a batch of indicators.

        Args:
            records: List of dict records with calculated indicators
            symbol: Trading pair
            timeframe: Timeframe

        Returns:
            Number of saved records
        """
        ...

    async def save_batch_from_df(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> int:
        """
        Save a batch from a DataFrame.

        Args:
            df: DataFrame with calculated indicators
            symbol: Trading pair
            timeframe: Timeframe

        Returns:
            Number of saved records
        """
        ...

    async def validate_connection(self) -> dict[str, object]:
        """
        Validate backend availability and table structure.

        Returns:
            Dictionary with connection status and schema details.
        """
        ...

    async def verify_integrity(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict[str, object]:
        """
        Verify integrity of stored data for a symbol/timeframe pair.

        Returns:
            Dictionary with integrity check results.
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
