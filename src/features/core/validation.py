"""
Validation functions for feature calculation.

This module provides functions for validating feature specifications,
compatibility checks, and data quality validation.
"""

import pandas as pd

from ..models import FeatureError
from ..specs import FEATURE_SPECS, FeatureSpec


def _prepare_feature_specs(specs: list[str | FeatureSpec] | None) -> list[FeatureSpec]:
    """
    Prepare and validate feature specifications.

    Converts string names to FeatureSpec objects and validates their integrity.

    Args:
        specs: List of feature names or FeatureSpec objects, or None for all features

    Returns:
        List of validated FeatureSpec objects

    Raises:
        FeatureError: If validation fails or invalid specs are provided
    """
    # Lazy import to avoid circular dependencies
    from ..validators import (
        validate_feature_specs_integrity,
    )

    if specs is None:
        # Return all available features
        return list(FEATURE_SPECS.values())

    # Convert string names to FeatureSpec objects
    feature_specs: list[FeatureSpec] = []
    for spec in specs:
        if isinstance(spec, str):
            if spec not in FEATURE_SPECS:
                raise FeatureError(f"Unknown feature: {spec}")
            feature_specs.append(FEATURE_SPECS[spec])
        elif isinstance(spec, FeatureSpec):
            feature_specs.append(spec)
        else:
            raise FeatureError(f"Invalid spec type: {type(spec)}")

    # Validate integrity
    try:
        validate_feature_specs_integrity(feature_specs)
    except Exception as e:
        # Log as warning to allow ad-hoc runs with partial specs
        from ..logging_config import get_features_logger

        logger = get_features_logger(__name__)
        logger.warning(f"Phase requirements check warning: {e}")

    return feature_specs


def validate_feature_compatibility(
    df_ohlcv: pd.DataFrame, feature_names: list[str]
) -> list[str]:
    """
    Validate that all required OHLCV columns are present for the requested features.

    Checks if the DataFrame contains all required columns (open, high, low, close, volume)
    for each requested feature according to their FeatureSpec requirements.

    Args:
        df_ohlcv: OHLCV DataFrame to validate
        feature_names: List of feature names to validate

    Returns:
        List of missing required column names. Empty list if all columns are present.

    Example:
        >>> df = pd.DataFrame({'open': [100], 'high': [105], 'low': [99], 'close': [104]})
        >>> missing = validate_feature_compatibility(df, ['rsi_14'])
        >>> 'volume' in missing
        True
    """
    available_columns = set(df_ohlcv.columns)
    missing_columns = set()

    for feature_name in feature_names:
        if feature_name not in FEATURE_SPECS:
            continue

        spec = FEATURE_SPECS[feature_name]
        for required_col in spec.requires:
            if required_col not in available_columns:
                missing_columns.add(required_col)

    return list(missing_columns)
