"""
Domain facade for feature specifications.

Экспортирует спецификации из specs.py как стабильную точку доступа
для доменного слоя и валидаторов.
"""

from __future__ import annotations

from ..specs import (
    FEATURE_GROUPS,
    FEATURE_SPECS,
    get_features_by_type,
    get_required_features,
    validate_feature_specs,
)

__all__ = [
    "FEATURE_SPECS",
    "FEATURE_GROUPS",
    "get_features_by_type",
    "get_required_features",
    "validate_feature_specs",
]
