"""
Feature Calculation Service.

High-level service that implements FeatureCalculator Protocol.
Provides dependency injection and better testability.

SOLID principles:
- S (SRP): Service orchestrates, delegates actual work to components
- D (DIP): Depends on abstractions (Protocols), not concrete implementations
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.logging import get_logger

from ..specs import FEATURE_SPECS, FeatureSpec
from ..ta_safe.constants import get_backend

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd

    from ..domain.protocols import FeatureNormalizer, OHLCVValidator
    from ..ports import FeatureBackendId, FeatureCalculatorBackend

logger = get_logger(__name__)


# =============================================================================
# DEFAULT IMPLEMENTATIONS
# =============================================================================


class DefaultOHLCVValidator:
    """Default OHLCV validator implementation."""

    REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate OHLCV DataFrame."""
        if df is None or df.empty:
            raise ValueError("DataFrame is None or empty")

        missing_cols = self.REQUIRED_COLUMNS - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Check for all-NaN columns
        for col in self.REQUIRED_COLUMNS:
            if df[col].isna().all():
                raise ValueError(f"Column '{col}' contains only NaN values")

        return True


class DefaultFeatureNormalizer:
    """Default feature normalizer implementation."""

    def normalize(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """Apply volatility normalization."""
        from ..utils import volatility_normalize_features

        if volatility_normalize_features is not None and callable(
            volatility_normalize_features
        ):
            return volatility_normalize_features(df, window=window)
        return df


@contextmanager
def _temporary_feature_backend(backend_id: FeatureBackendId) -> Any:
    """Temporarily override the TA backend for a single calculation."""
    if backend_id == "auto":
        yield
        return

    previous_backend = os.environ.get("FEATURES_TA_BACKEND")
    os.environ["FEATURES_TA_BACKEND"] = backend_id
    try:
        yield
    finally:
        if previous_backend is None:
            os.environ.pop("FEATURES_TA_BACKEND", None)
        else:
            os.environ["FEATURES_TA_BACKEND"] = previous_backend


@dataclass(frozen=True)
class DefaultFeatureCalculatorBackend:
    """Default backend wrapper around the core compute function."""

    backend_id: FeatureBackendId = field(default_factory=get_backend)

    def __call__(
        self,
        compute_fn: Callable[..., pd.DataFrame],
        df_ohlcv: pd.DataFrame,
        specs: list[str] | None = None,
        *,
        volatility_normalize: bool = False,
        normalize_window: int = 20,
        **kwargs: Any,
    ) -> pd.DataFrame:
        with _temporary_feature_backend(self.backend_id):
            return compute_fn(
                df_ohlcv,
                specs=specs,
                volatility_normalize=volatility_normalize,
                normalize_window=normalize_window,
                **kwargs,
            )


# =============================================================================
# FEATURE CALCULATION SERVICE
# =============================================================================


@dataclass
class FeatureCalculationService:
    """
    High-level service for feature calculation.

    Implements FeatureCalculator Protocol and provides:
    - Dependency injection for validator and normalizer
    - Clean separation of concerns
    - Better testability through component injection

    Example:
        >>> service = FeatureCalculationService()
        >>> result = service.calculate(df_ohlcv, specs=['rsi_14', 'ema_21'])

        >>> # With custom validator
        >>> service = FeatureCalculationService(validator=MyCustomValidator())
    """

    validator: OHLCVValidator = field(default_factory=DefaultOHLCVValidator)
    normalizer: FeatureNormalizer = field(default_factory=DefaultFeatureNormalizer)
    backend: FeatureCalculatorBackend | None = field(default=None, repr=False)
    backend_id: FeatureBackendId = "auto"
    _compute_fn: Callable[..., pd.DataFrame] | None = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize compute function if not provided."""
        if self._compute_fn is None:
            from ..core.calculation import compute_features

            self._compute_fn = compute_features
        if self.backend is None:
            self.backend = DefaultFeatureCalculatorBackend(self.backend_id)

    def calculate(
        self,
        df_ohlcv: pd.DataFrame,
        specs: list[str] | None = None,
        *,
        volatility_normalize: bool = False,
        normalize_window: int = 20,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Calculate features for OHLCV data.

        Args:
            df_ohlcv: DataFrame with OHLCV columns
            specs: List of indicator names (None = all available)
            volatility_normalize: Apply volatility normalization
            normalize_window: Window for normalization

        Returns:
            DataFrame with calculated indicators
        """
        # 1. Validate input
        self.validator.validate(df_ohlcv)

        # 2. Calculate features through the configured backend wrapper.
        # The backend may temporarily override FEATURES_TA_BACKEND for the call.
        result = self.backend(
            self._compute_fn,
            df_ohlcv,
            specs=specs,
            volatility_normalize=False,  # We'll apply it ourselves
            normalize_window=normalize_window,
            **kwargs,
        )

        # 3. Apply normalization if requested
        if volatility_normalize:
            result = self.normalizer.normalize(result, window=normalize_window)

        return result

    def calculate_batch(
        self,
        df_ohlcv: pd.DataFrame,
        available: set[str],
        *,
        volatility_normalize: bool = False,
    ) -> pd.DataFrame:
        """
        Calculate features for a batch (compatible with calculate_batch interface).

        Args:
            df_ohlcv: DataFrame with OHLCV columns
            available: Set of indicator names to calculate
            volatility_normalize: Apply volatility normalization

        Returns:
            DataFrame with calculated indicators
        """
        return self.calculate(
            df_ohlcv,
            specs=list(available),
            volatility_normalize=volatility_normalize,
        )

    @staticmethod
    def get_available_specs() -> list[str]:
        """Get list of all available indicator names."""
        return list(FEATURE_SPECS.keys())

    @staticmethod
    def get_spec_info(name: str) -> FeatureSpec | None:
        """Get specification for an indicator by name."""
        return FEATURE_SPECS.get(name)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_feature_service(
    validator: OHLCVValidator | None = None,
    normalizer: FeatureNormalizer | None = None,
    *,
    backend: FeatureCalculatorBackend | None = None,
    backend_id: FeatureBackendId = "auto",
) -> FeatureCalculationService:
    """
    Factory function to create FeatureCalculationService.

    Args:
        validator: Custom OHLCV validator (optional)
        normalizer: Custom feature normalizer (optional)
        backend: Custom backend wrapper (optional)
        backend_id: Backend selection for the default wrapper

    Returns:
        Configured FeatureCalculationService instance
    """
    return FeatureCalculationService(
        validator=validator or DefaultOHLCVValidator(),
        normalizer=normalizer or DefaultFeatureNormalizer(),
        backend=backend,
        backend_id=backend_id,
    )
