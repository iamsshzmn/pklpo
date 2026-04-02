"""
Validation module for the features module.

This module provides validation functions for OHLCV data, feature specifications,
and calculation parameters to ensure data quality and prevent errors.
"""

from typing import Any

import numpy as np
import pandas as pd

from src.logging import get_logger

from ..domain.models import FeatureSpec, FeatureValidationError, FeatureValidationResult

# Use the canonical registry from specs.py; fall back gracefully if auxiliary registries are absent
try:
    from ..specs import FEATURE_SPECS, PHASE_2_REQUIRED_FEATURES
except Exception:  # pragma: no cover - defensive import for partial environments
    FEATURE_SPECS = {}
    PHASE_2_REQUIRED_FEATURES = []
try:
    from ..registry import (
        AVAILABLE_INDICATORS,
        INDICATOR_CONFIG,
    )
except Exception:  # pragma: no cover
    AVAILABLE_INDICATORS: list[str] = []  # type: ignore[no-redef]
    INDICATOR_CONFIG: dict[str, Any] = {}  # type: ignore[no-redef]

logger = get_logger(__name__)


def validate_specs_registry_consistency() -> bool:
    """specs.py  registry/"""
    specs_keys = set(FEATURE_SPECS.keys()) if FEATURE_SPECS else set()
    registry_keys = set(AVAILABLE_INDICATORS) if AVAILABLE_INDICATORS else set()
    config_keys = set(INDICATOR_CONFIG.keys()) if INDICATOR_CONFIG else set()

    missing_in_registry = specs_keys - registry_keys
    missing_in_config = registry_keys - config_keys
    extra_in_registry = registry_keys - specs_keys

    if missing_in_registry:
        logger.error(f"Indicators in specs but not in registry: {missing_in_registry}")
    if missing_in_config:
        logger.error(f"Indicators in registry but not in config: {missing_in_config}")
    if extra_in_registry:
        logger.warning(f"Indicators in registry but not in specs: {extra_in_registry}")

    return len(missing_in_registry) == 0 and len(missing_in_config) == 0


def validate_ohlcv_data(df: pd.DataFrame) -> None:
    """
    Validate OHLCV DataFrame for required columns and data quality.

    Args:
        df: DataFrame to validate

    Raises:
        FeatureValidationError: If validation fails
    """
    if df is None or df.empty:
        raise FeatureValidationError("OHLCV DataFrame is None or empty")

    # Check required columns
    required_columns = ["open", "high", "low", "close", "volume"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise FeatureValidationError(f"Missing required columns: {missing_columns}")

    # Check data types
    numeric_columns = ["open", "high", "low", "close", "volume"]
    for col in numeric_columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise FeatureValidationError(f"Column {col} must be numeric")

    # Check for negative values in price columns
    price_columns = ["open", "high", "low", "close"]
    for col in price_columns:
        if (df[col] < 0).any():
            raise FeatureValidationError(f"Negative values found in {col} column")

    # Check for negative values in volume
    if (df["volume"] < 0).any():
        raise FeatureValidationError("Negative values found in volume column")

    # Check OHLC relationship
    if not _validate_ohlc_relationship(df):
        raise FeatureValidationError(
            "Invalid OHLC relationship: high < low or close outside [low, high]"
        )

    # Check for NaN values
    nan_columns = df.columns[df.isna().any()].tolist()
    if nan_columns:
        logger.warning(f"NaN values found in columns: {nan_columns}")

    # Check for infinite values
    numeric_df = df.select_dtypes(include=[np.number])
    if not numeric_df.empty:
        inf_columns = numeric_df.columns[np.isinf(numeric_df).any()].tolist()
        if inf_columns:
            raise FeatureValidationError(
                f"Infinite values found in columns: {inf_columns}"
            )

    # Enforce monotonic timestamps if present
    if "ts" in df.columns and not df["ts"].is_monotonic_increasing:
        raise FeatureValidationError("Timestamps are not in ascending order")

    logger.debug(f"OHLCV data validation passed for {len(df)} rows")


def _validate_ohlc_relationship(df: pd.DataFrame) -> bool:
    """
    Validate that OHLC values follow proper relationships.

    Args:
        df: OHLCV DataFrame

    Returns:
        True if relationships are valid
    """
    # High should be >= Low
    if (df["high"] < df["low"]).any():
        return False

    # Close should be between Low and High
    if ((df["close"] < df["low"]) | (df["close"] > df["high"])).any():
        return False

    # Open should be between Low and High (optional check)
    if ((df["open"] < df["low"]) | (df["open"] > df["high"])).any():
        logger.warning("Open price outside [low, high] range detected")

    return True


def validate_feature_specs_integrity(specs: list[FeatureSpec]) -> None:
    """
    Validate feature specifications.

    Args:
        specs: List of feature specifications to validate

    Raises:
        FeatureValidationError: If validation fails
    """
    if not specs:
        raise FeatureValidationError("Feature specifications list is empty")

    # Check for duplicate feature names
    feature_names = [spec.name for spec in specs]
    duplicates = [name for name in set(feature_names) if feature_names.count(name) > 1]
    if duplicates:
        raise FeatureValidationError(f"Duplicate feature names: {duplicates}")

    # Validate each specification
    for spec in specs:
        try:
            # This will trigger __post_init__ validation
            FeatureSpec(
                name=spec.name,
                type=spec.type,
                params=spec.params,
                requires=spec.requires,
                description=spec.description,
            )
        except ValueError as e:
            raise FeatureValidationError(
                f"Invalid feature specification {spec.name}: {e!s}"
            ) from e

    logger.debug(
        f"Feature specifications integrity validation passed for {len(specs)} features"
    )


def validate_phase_requirements(
    specs: list[FeatureSpec], required_list: list[str] | None = None
) -> None:
    """
    Validate that a given set of feature specs contains all required features
    for the current phase (defaults to Phase 2 requirements from specs).

    Args:
        specs: List of feature specifications
        required_list: Optional explicit list of required feature names

    Raises:
        FeatureValidationError: If required features are missing
    """
    if specs is None:
        raise FeatureValidationError("Feature specifications list is None")

    available_features = {spec.name for spec in specs}
    required = (
        set(required_list)
        if required_list is not None
        else set(PHASE_2_REQUIRED_FEATURES)
    )

    missing = required - available_features
    if missing:
        raise FeatureValidationError(f"Missing required features: {sorted(missing)}")
    logger.debug("Phase requirements validation passed")


def validate_feature_compatibility(
    df: pd.DataFrame, feature_names: list[str], feature_specs: dict[str, FeatureSpec]
) -> FeatureValidationResult:
    """
    Validate that all required OHLCV columns are present for the requested features.

    Args:
        df: OHLCV DataFrame
        feature_names: List of feature names to validate
        feature_specs: Dictionary of feature specifications

    Returns:
        FeatureValidationResult with validation details
    """
    available_columns = set(df.columns)
    missing_columns: set[str] = set()
    errors: list[str] = []
    warnings: list[str] = []

    for feature_name in feature_names:
        if feature_name not in feature_specs:
            errors.append(f"Unknown feature: {feature_name}")
            continue

        spec = feature_specs[feature_name]
        for required_col in spec.requires:
            if required_col not in available_columns:
                missing_columns.add(required_col)
                errors.append(f"Feature {feature_name} requires column {required_col}")

    # Check if we have enough data for calculation
    if len(df) < 2:
        errors.append("Insufficient data: need at least 2 rows for feature calculation")

    is_valid = len(errors) == 0

    return FeatureValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        missing_columns=list(missing_columns),
    )


def validate_calculation_params(
    params: dict[str, Any], feature_name: str, feature_spec: FeatureSpec
) -> None:
    """
    Validate calculation parameters for a specific feature.

    Args:
        params: Parameters to validate
        feature_name: Name of the feature
        feature_spec: Feature specification

    Raises:
        FeatureValidationError: If validation fails
    """
    # Check required parameters
    for param_name, param_value in feature_spec.params.items():
        if param_name not in params:
            raise FeatureValidationError(
                f"Missing required parameter {param_name} for feature {feature_name}"
            )

        # Validate parameter types and ranges
        if isinstance(param_value, int | float):
            if not isinstance(params[param_name], int | float):
                raise FeatureValidationError(
                    f"Parameter {param_name} must be numeric for feature {feature_name}"
                )

            # Check for positive values where appropriate
            if param_name in [
                "period",
                "fast_period",
                "slow_period",
                "signal_period",
                "k_period",
                "d_period",
            ]:
                if params[param_name] <= 0:
                    raise FeatureValidationError(
                        f"Parameter {param_name} must be positive for feature {feature_name}"
                    )

    logger.debug(f"Parameter validation passed for feature {feature_name}")


def validate_data_quality(df: pd.DataFrame) -> FeatureValidationResult:
    """
    Perform comprehensive data quality validation.

    Args:
        df: DataFrame to validate

    Returns:
        FeatureValidationResult with quality metrics
    """
    errors = []
    warnings = []

    # Check for missing values
    missing_counts = df.isnull().sum()
    high_missing_columns = missing_counts[missing_counts > len(df) * 0.1].index.tolist()
    if high_missing_columns:
        warnings.append(
            f"High missing values (>10%) in columns: {high_missing_columns}"
        )

    # Check for zero values in volume
    if "volume" in df.columns and (df["volume"] == 0).any():
        warnings.append("Zero volume values detected")

    # Check for price gaps (large price changes)
    if "close" in df.columns:
        price_changes = df["close"].pct_change().abs()
        large_gaps = price_changes[price_changes > 0.1]  # >10% change
        if not large_gaps.empty:
            warnings.append(
                f"Large price gaps detected: {len(large_gaps)} instances >10%"
            )

    # Check for data consistency
    if len(df) > 1:
        # Check for duplicate timestamps
        if "ts" in df.columns:
            duplicate_timestamps = df["ts"].duplicated().sum()
            if duplicate_timestamps > 0:
                errors.append(f"Duplicate timestamps found: {duplicate_timestamps}")

        # Check for non-monotonic timestamps
        if "ts" in df.columns and not df["ts"].is_monotonic_increasing:
            warnings.append("Timestamps are not in ascending order")

    is_valid = len(errors) == 0

    return FeatureValidationResult(
        is_valid=is_valid, errors=errors, warnings=warnings, missing_columns=[]
    )


def validate_lookahead_safety(
    df: pd.DataFrame, feature_names: list[str], feature_specs: dict[str, FeatureSpec]
) -> FeatureValidationResult:
    """
    Validate that feature calculations don't introduce lookahead bias.

    Args:
        df: OHLCV DataFrame
        feature_names: List of feature names to validate
        feature_specs: Dictionary of feature specifications

    Returns:
        FeatureValidationResult with lookahead safety assessment
    """
    errors = []
    warnings = []

    # Check for features that might have lookahead issues
    lookahead_risky_features = [
        "bbands_percent",  # Uses future data for normalization
        "natr_14",  # Normalized ATR might use future data
    ]

    risky_features = [f for f in feature_names if f in lookahead_risky_features]
    if risky_features:
        warnings.append(f"Features with potential lookahead risk: {risky_features}")

    # Check data ordering
    if "ts" in df.columns and len(df) > 1 and not df["ts"].is_monotonic_increasing:
        errors.append("Data not in chronological order - lookahead bias possible")

    is_valid = len(errors) == 0

    return FeatureValidationResult(
        is_valid=is_valid, errors=errors, warnings=warnings, missing_columns=[]
    )
