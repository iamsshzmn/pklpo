"""
Data models for the features module.

This module defines the data structures used throughout the features module
for type safety and consistency.
"""

from dataclasses import dataclass
from typing import Any, TypeAlias

import pandas as pd


@dataclass
class FeatureSpec:
    """
    Specification for a technical feature.

    Attributes:
        name: Unique name of the feature
        type: Type of feature (trend, oscillator, volatility, volume, ma)
        params: Dictionary of parameters for the feature calculation
        requires: List of required OHLCV columns
        description: Human-readable description of the feature
        dependencies: List of other features this feature depends on (optional)
    """

    name: str
    type: str
    params: dict[str, Any]
    requires: list[str]
    description: str
    dependencies: list[str] | None = None

    def __post_init__(self):
        """Validate the feature specification after initialization."""
        if not self.name:
            raise ValueError("Feature name cannot be empty")

        valid_types = [
            "trend",
            "oscillator",
            "volatility",
            "volume",
            "ma",
            "candles",
            "squeeze",
            "overlap",
            "statistics",
            "performance",
        ]
        if self.type not in valid_types:
            raise ValueError(
                f"Invalid feature type: {self.type}. Must be one of {valid_types}"
            )

        valid_columns = ["open", "high", "low", "close", "volume"]
        for col in self.requires:
            if col not in valid_columns:
                raise ValueError(
                    f"Invalid required column: {col}. Must be one of {valid_columns}"
                )


@dataclass
class FeatureResult:
    """
    Result of feature calculation.

    Attributes:
        feature_name: Name of the calculated feature
        values: Series with calculated values
        metadata: Additional metadata about the calculation
        errors: List of errors that occurred during calculation
    """

    feature_name: str
    values: pd.Series
    metadata: dict[str, Any]
    errors: list[str]

    def __post_init__(self):
        """Validate the feature result after initialization."""
        if not self.feature_name:
            raise ValueError("Feature name cannot be empty")

        if not isinstance(self.values, pd.Series):
            raise ValueError("Values must be a pandas Series")


@dataclass
class FeatureCalculationConfig:
    """
    Configuration for feature calculation.

    Attributes:
        volatility_normalize: Whether to apply volatility normalization
        normalize_window: Window size for volatility calculation
        normalize_method: Method for volatility normalization
        min_periods: Minimum number of periods required for calculation
        fill_method: Method for filling missing values
        error_handling: How to handle calculation errors
    """

    volatility_normalize: bool = True
    normalize_window: int = 20
    normalize_method: str = "rolling_std"
    min_periods: int = 1
    fill_method: str = "forward"
    error_handling: str = "warn"  # "warn", "raise", "ignore"

    def __post_init__(self):
        """Validate the configuration after initialization."""
        if self.normalize_window < 1:
            raise ValueError("Normalize window must be at least 1")

        valid_methods = ["rolling_std", "ewm_std"]
        if self.normalize_method not in valid_methods:
            raise ValueError(f"Invalid normalize method: {self.normalize_method}")

        valid_fill_methods = ["forward", "backward", "interpolate", "zero"]
        if self.fill_method not in valid_fill_methods:
            raise ValueError(f"Invalid fill method: {self.fill_method}")

        valid_error_handling = ["warn", "raise", "ignore"]
        if self.error_handling not in valid_error_handling:
            raise ValueError(f"Invalid error handling: {self.error_handling}")


@dataclass
class FeatureValidationResult:
    """
    Result of feature validation.

    Attributes:
        is_valid: Whether the validation passed
        errors: List of validation errors
        warnings: List of validation warnings
        missing_columns: List of missing required columns
    """

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    missing_columns: list[str]

    def __post_init__(self):
        """Initialize empty lists if not provided."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.missing_columns is None:
            self.missing_columns = []


class FeatureError(Exception):
    """
    Custom exception for feature-related errors.

    This exception is raised when feature calculation or validation fails.
    """

    def __init__(
        self,
        message: str,
        feature_name: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """
        Initialize the FeatureError.

        Args:
            message: Error message
            feature_name: Name of the feature that caused the error
            details: Additional error details
        """
        self.message = message
        self.feature_name = feature_name
        self.details = details or {}

        # Build the full error message
        full_message = message
        if feature_name:
            full_message = f"[{feature_name}] {message}"

        super().__init__(full_message)


class FeatureValidationError(FeatureError):
    """
    Exception raised when feature validation fails.
    """

    pass


class FeatureCalculationError(FeatureError):
    """
    Exception raised when feature calculation fails.
    """

    pass


# Type aliases for better code readability
FeatureName: TypeAlias = str
FeatureNames: TypeAlias = list[FeatureName]
FeatureParams: TypeAlias = dict[str, Any]
FeatureValues: TypeAlias = pd.Series
FeatureDict: TypeAlias = dict[FeatureName, FeatureValues]
OHLCVData: TypeAlias = pd.DataFrame
