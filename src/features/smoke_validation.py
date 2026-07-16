"""Smoke validation compatibility module."""

from .validation import validate_ohlcv_data
from .validation.feature_validator import validate_feature_specs_integrity


def smoke_validate() -> bool:
    return True


__all__ = ["smoke_validate", "validate_feature_specs_integrity", "validate_ohlcv_data"]
