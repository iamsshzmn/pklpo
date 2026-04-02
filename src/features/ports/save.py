"""Save-related ports for features application use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    import pandas as pd


@runtime_checkable
class FeatureSaveValidator(Protocol):
    """Protocol for pre-save validation of calculated feature frames."""

    def validate_save_dataframe(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> dict[str, object]: ...


@runtime_checkable
class FeatureSaveObservation(Protocol):
    """Active observation session for save orchestration."""

    def record_success(self, *, rows_processed: int, rows_saved: int) -> None: ...

    def record_error(self, error: Exception | str) -> None: ...


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
    ) -> AbstractContextManager[FeatureSaveObservation]: ...
