"""
Group-based calculation with batch persistence.

This module implements the group-based calculation architecture as specified in the plan:
overlap → MA → oscillators → volatility → volume → trend → candles → squeeze → statistics → performance

Each group is calculated on a common DataFrame and immediately persisted as a batch.

REFACTORING NOTE (Phase 1.2):
This module is now a facade that re-exports from the SRP-compliant modules:
- group_calculator.py: GroupFeatureCalculator (calculation only)
- group_persister.py: GroupPersister (persistence only)
- group_metrics.py: GroupMetricsRecorder (metrics only)
- group_orchestrator.py: GroupCalculationOrchestrator (coordination)

The old GroupCalculator class is kept for backward compatibility but delegates
to the new components internally.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

# Re-export from new SRP-compliant modules
from .group_calculator import GroupFeatureCalculator
from .group_metrics import GroupMetricsRecorder
from .group_orchestrator import (
    GroupCalculationConfig,
    GroupCalculationOrchestrator,
    compute_features_grouped,
)
from .group_persister import GroupPersister

if TYPE_CHECKING:
    import pandas as pd

# Public API (backward compatible)
__all__ = [
    # Legacy exports (backward compatible)
    "CALCULATION_ORDER",
    "GroupCalculationConfig",
    "GroupCalculator",
    "compute_features_grouped",
    # New SRP-compliant exports
    "GroupFeatureCalculator",
    "GroupPersister",
    "GroupMetricsRecorder",
    "GroupCalculationOrchestrator",
]

# Standard calculation order for all indicator groups
CALCULATION_ORDER = [
    "overlap",  # Basic price calculations (hlc3, hl2, etc) - no dependencies
    "ma",  # Moving averages - depends on OHLC
    "oscillators",  # RSI, MACD, Stochastic - depends on close, MA
    "volatility",  # ATR, Bollinger Bands - depends on OHLC, MA
    "volume",  # OBV, CMF, VWAP - depends on volume
    "trend",  # ADX, Aroon, Supertrend - depends on OHLC, ATR
    "candles",  # Candlestick patterns - depends on OHLC
    "squeeze",  # Squeeze Momentum - depends on BB, KC
    "statistics",  # Statistical measures - depends on price data
    "performance",  # Performance metrics - depends on close
]


class GroupCalculator:
    """
    Calculator for group-based feature calculation with batch persistence.

    DEPRECATION NOTE:
    This class is deprecated in favor of the new SRP-compliant components:
    - GroupFeatureCalculator: for calculation
    - GroupPersister: for persistence
    - GroupCalculationOrchestrator: for coordination

    This class is kept for backward compatibility and delegates to the new
    components internally.
    """

    def __init__(self, config: GroupCalculationConfig | None = None):
        """
        Initialize the calculator.

        Args:
            config: Configuration for calculation (optional)
        """
        warnings.warn(
            "GroupCalculator is deprecated. Use GroupCalculationOrchestrator instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._orchestrator = GroupCalculationOrchestrator(config)
        self.config = self._orchestrator.config

    def calculate_group(
        self, df: pd.DataFrame, group_name: str, **kwargs
    ) -> pd.DataFrame:
        """
        Calculate features for a specific group.

        Args:
            df: DataFrame with OHLCV data
            group_name: Name of the group to calculate
            **kwargs: Additional parameters

        Returns:
            DataFrame with additional features from the group
        """
        # Use the internal calculator
        result = self._orchestrator._calculator.calculate_group(
            df, group_name, **kwargs
        )
        # Merge results into DataFrame (for backward compatibility)
        for name, series in result.items():
            df[name] = series
        return df

    def persist_batch(self, df: pd.DataFrame, group_name: str, **kwargs) -> bool:
        """
        Persist a batch of calculated features to database.

        Args:
            df: DataFrame with calculated features
            group_name: Name of the group being persisted
            **kwargs: Additional parameters

        Returns:
            True if successful, False otherwise
        """
        return self._orchestrator._persister.persist_batch(df, group_name, **kwargs)

    def calculate_all_groups(self, df_ohlcv: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Calculate all groups in sequence with batch persistence.

        Args:
            df_ohlcv: DataFrame with OHLCV data
            **kwargs: Additional parameters

        Returns:
            DataFrame with all calculated features
        """
        return self._orchestrator.calculate_all_groups(df_ohlcv, **kwargs)
