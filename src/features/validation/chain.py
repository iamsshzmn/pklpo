"""
ValidationChain - Chain of Responsibility pattern for validators.

Task 12: OCP-compliant validation pipeline.

This module provides a flexible way to compose validators into a chain.
Adding new validators doesn't require modifying existing code.

Usage:
    chain = ValidationChain()
    chain.add(OHLCVValidator())
    chain.add(FeatureSpecsValidator())
    chain.add(TimestampValidator())

    result = chain.validate(df)
    if not result.is_valid:
        print(result.errors)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.logging import get_logger

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validator_name: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def add_error(self, error: str) -> None:
        """Add an error and mark as invalid."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning (doesn't affect validity)."""
        self.warnings.append(warning)

    def merge(self, other: ValidationResult) -> ValidationResult:
        """Merge another result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.details.update(other.details)
        if not other.is_valid:
            self.is_valid = False
        return self


class Validator(ABC):
    """Abstract base class for validators (Chain of Responsibility)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the validator."""
        ...

    @abstractmethod
    def validate(self, df: pd.DataFrame, **kwargs: Any) -> ValidationResult:
        """
        Validate the DataFrame.

        Args:
            df: DataFrame to validate
            **kwargs: Additional validation parameters

        Returns:
            ValidationResult with errors/warnings
        """
        ...

    def should_stop_on_failure(self) -> bool:
        """Whether to stop the chain if this validator fails."""
        return False


class ValidationChain:
    """
    Chain of Responsibility for validators.

    Allows composing multiple validators into a pipeline.
    OCP-compliant: adding validators doesn't modify existing code.

    Example:
        chain = ValidationChain()
        chain.add(OHLCVValidator())
        chain.add(TimestampValidator())
        result = chain.validate(df)
    """

    def __init__(self) -> None:
        self._validators: list[Validator] = []

    def add(self, validator: Validator) -> ValidationChain:
        """Add a validator to the chain (fluent interface)."""
        self._validators.append(validator)
        return self

    def remove(self, validator_name: str) -> ValidationChain:
        """Remove a validator by name."""
        self._validators = [v for v in self._validators if v.name != validator_name]
        return self

    def clear(self) -> ValidationChain:
        """Remove all validators."""
        self._validators.clear()
        return self

    def validate(self, df: pd.DataFrame, **kwargs: Any) -> ValidationResult:
        """
        Run all validators in sequence.

        Args:
            df: DataFrame to validate
            **kwargs: Additional parameters passed to validators

        Returns:
            Combined ValidationResult from all validators
        """
        combined_result = ValidationResult(is_valid=True, validator_name="chain")

        for validator in self._validators:
            try:
                result = validator.validate(df, **kwargs)
                result.validator_name = validator.name
                combined_result.merge(result)

                logger.debug(
                    f"Validator '{validator.name}': valid={result.is_valid}, "
                    f"errors={len(result.errors)}, warnings={len(result.warnings)}"
                )

                # Stop chain if validator requires it and failed
                if not result.is_valid and validator.should_stop_on_failure():
                    logger.warning(
                        f"Validator '{validator.name}' failed and requires stop. "
                        f"Remaining validators skipped."
                    )
                    break

            except Exception as e:
                error_msg = f"Validator '{validator.name}' raised exception: {e}"
                logger.error(error_msg)
                combined_result.add_error(error_msg)

        return combined_result

    def __len__(self) -> int:
        return len(self._validators)

    def __iter__(self):
        return iter(self._validators)


# =============================================================================
# BUILT-IN VALIDATORS
# =============================================================================


class OHLCVValidator(Validator):
    """Validates OHLCV columns presence and data quality."""

    REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}

    @property
    def name(self) -> str:
        return "ohlcv"

    def should_stop_on_failure(self) -> bool:
        return True  # Can't proceed without OHLCV

    def validate(self, df: pd.DataFrame, **kwargs: Any) -> ValidationResult:
        result = ValidationResult()

        if df is None:
            result.add_error("DataFrame is None")
            return result

        if df.empty:
            result.add_error("DataFrame is empty")
            return result

        # Check required columns
        missing = self.REQUIRED_COLUMNS - set(df.columns)
        if missing:
            result.add_error(f"Missing required columns: {missing}")
            return result

        # Check data quality
        for col in self.REQUIRED_COLUMNS:
            null_ratio = df[col].isna().mean()
            if null_ratio > 0.5:
                result.add_error(
                    f"Column '{col}' has >50% null values ({null_ratio:.1%})"
                )
            elif null_ratio > 0.1:
                result.add_warning(
                    f"Column '{col}' has >10% null values ({null_ratio:.1%})"
                )

        result.details["row_count"] = len(df)
        result.details["column_count"] = len(df.columns)

        return result


class MinRowsValidator(Validator):
    """Validates minimum number of rows."""

    def __init__(self, min_rows: int = 20):
        self.min_rows = min_rows

    @property
    def name(self) -> str:
        return "min_rows"

    def should_stop_on_failure(self) -> bool:
        return True  # Can't calculate indicators with too few rows

    def validate(self, df: pd.DataFrame, **kwargs: Any) -> ValidationResult:
        result = ValidationResult()

        if df is None or len(df) < self.min_rows:
            actual = len(df) if df is not None else 0
            result.add_error(f"Insufficient rows: {actual} < {self.min_rows} minimum")

        return result


class TimestampValidator(Validator):
    """Validates timestamp column presence and quality."""

    @property
    def name(self) -> str:
        return "timestamp"

    def validate(self, df: pd.DataFrame, **kwargs: Any) -> ValidationResult:
        result = ValidationResult()

        # Check for timestamp column (ts or timestamp)
        ts_col = None
        for col in ("ts", "timestamp"):
            if col in df.columns:
                ts_col = col
                break

        if ts_col is None:
            result.add_warning("No timestamp column found (ts or timestamp)")
            return result

        # Check for duplicates
        duplicates = df[ts_col].duplicated().sum()
        if duplicates > 0:
            result.add_warning(f"Found {duplicates} duplicate timestamps")

        # Check for monotonic increase
        if not df[ts_col].is_monotonic_increasing:
            result.add_warning("Timestamps are not monotonically increasing")

        result.details["timestamp_column"] = ts_col
        result.details["duplicate_count"] = duplicates

        return result


class NaNRatioValidator(Validator):
    """Validates NaN ratio in indicator columns."""

    def __init__(self, max_nan_ratio: float = 0.3):
        self.max_nan_ratio = max_nan_ratio

    @property
    def name(self) -> str:
        return "nan_ratio"

    def validate(self, df: pd.DataFrame, **kwargs: Any) -> ValidationResult:
        result = ValidationResult()

        # Exclude service columns
        service_cols = {
            "ts",
            "timestamp",
            "symbol",
            "timeframe",
            "calculated_at",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "data_status",
        }
        indicator_cols = [c for c in df.columns if c not in service_cols]

        if not indicator_cols:
            return result

        high_nan_cols = []
        for col in indicator_cols:
            nan_ratio = df[col].isna().mean()
            if nan_ratio > self.max_nan_ratio:
                high_nan_cols.append((col, nan_ratio))

        if high_nan_cols:
            result.add_warning(
                f"{len(high_nan_cols)} columns exceed {self.max_nan_ratio:.0%} NaN threshold"
            )
            result.details["high_nan_columns"] = high_nan_cols[:10]  # First 10

        return result


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_default_chain() -> ValidationChain:
    """Create a validation chain with default validators."""
    return (
        ValidationChain()
        .add(OHLCVValidator())
        .add(MinRowsValidator(min_rows=20))
        .add(TimestampValidator())
    )


def create_strict_chain() -> ValidationChain:
    """Create a validation chain with strict validators."""
    return (
        ValidationChain()
        .add(OHLCVValidator())
        .add(MinRowsValidator(min_rows=50))
        .add(TimestampValidator())
        .add(NaNRatioValidator(max_nan_ratio=0.1))
    )
