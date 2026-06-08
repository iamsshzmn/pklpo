"""Public API facade for the features bounded context."""

from __future__ import annotations

from .application.feature_service import (
    DefaultFeatureCalculatorBackend,
    DefaultFeatureNormalizer,
    DefaultOHLCVValidator,
    FeatureCalculationService,
    create_feature_service,
)
from .application.features_calc_short_service import (
    run_features_calc_short,
    run_features_calc_short_validate,
)
from .application.save import (
    save_batch,
    save_parquet_to_pg,
    validate_database_connection,
    verify_database_integrity,
)
from .bootstrap import FeatureApplicationBootstrap, create_feature_application_bootstrap
from .domain.models import FeatureResult
from .ports import FeatureBackendId, FeatureCalculatorBackend
from .specs import FEATURE_SPECS, FeatureSpec
from .storage_contract import IndicatorStorageContract

try:
    from .core import compute_features
except Exception:  # pragma: no cover - optional at import time

    def compute_features(*args, **kwargs):  # type: ignore
        raise ImportError(
            "features.core dependencies are not available. Install runtime deps or import 'features.core' directly."
        )


__all__ = [
    "FEATURE_SPECS",
    "DefaultFeatureCalculatorBackend",
    "DefaultFeatureNormalizer",
    "DefaultOHLCVValidator",
    "FeatureApplicationBootstrap",
    "FeatureBackendId",
    "FeatureCalculationService",
    "FeatureCalculatorBackend",
    "FeatureResult",
    "FeatureSpec",
    "IndicatorStorageContract",
    "compute_features",
    "create_feature_application_bootstrap",
    "create_feature_service",
    "run_features_calc_short",
    "run_features_calc_short_validate",
    "save_batch",
    "save_parquet_to_pg",
    "validate_database_connection",
    "verify_database_integrity",
]
