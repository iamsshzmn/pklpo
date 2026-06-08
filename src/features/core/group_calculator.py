"""
group_calculator — KEEP (features-prune-v2 A5).

Responsibility: calculate indicator groups from OHLCV data. No persistence, no metrics.
Imported by: group_orchestrator.py only.
Decision: kept separate from group_orchestrator and group_metrics per SRP.
Merging would collapse three distinct concerns (calc / metrics / orchestration)
into one file with no architectural gain.

Group Feature Calculator (SRP: calculation only).

This module handles calculation of indicator groups without persistence
or metrics concerns. It follows the Single Responsibility Principle by
focusing solely on the calculation logic.

Part of Phase 1.2 refactoring: Split GroupCalculator into SRP components.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.logging import (
    LogCategory,
    Verbosity,
    get_category_logger,
    should_log,
)

from ..domain.models import FeatureError
from ..indicator_groups.registry import GroupRegistrySnapshot, build_registry_snapshot

if TYPE_CHECKING:
    import pandas as pd

    from ..indicator_groups.registry import GroupEntry


__all__ = ["GroupFeatureCalculator"]

logger = get_category_logger(LogCategory.CALC)


class GroupFeatureCalculator:
    """
    Calculator for indicator groups (SRP: calculation only).

    This class is responsible solely for calculating features for
    indicator groups. It does not handle persistence or metrics.

    Uses GroupRegistry for OCP-compliant group management.
    """

    def __init__(self, registry: GroupRegistrySnapshot | None = None):
        """Initialize the calculator."""
        self._logger = get_category_logger(LogCategory.CALC)
        self._registry = registry or build_registry_snapshot()
        self._init_registry()

    def _init_registry(self) -> None:
        """Initialize GroupRegistry and log available groups."""
        ordered_groups = self._registry.get_ordered()
        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            group_names = [g.name for g in ordered_groups]
            self._logger.debug(
                f"GroupFeatureCalculator: {len(ordered_groups)} groups: {group_names}"
            )

    def calculate_group(
        self,
        df: pd.DataFrame,
        group_name: str,
        available: set[str] | None = None,
        **kwargs,
    ) -> dict[str, pd.Series]:
        """
        Calculate features for a specific group.

        Args:
            df: DataFrame with OHLCV data
            group_name: Name of the group to calculate
            available: Set of indicator names to calculate (None = all)
            **kwargs: Additional parameters for calculation

        Returns:
            Dictionary mapping indicator names to pandas Series

        Raises:
            FeatureError: If calculation fails
        """
        calculator_fn = self._registry.get_calculator(group_name)
        if calculator_fn is None:
            self._logger.warning(f"Unknown group: {group_name}")
            return {}

        start_time = time.perf_counter()

        try:
            # Use all available columns if not specified
            if available is None:
                available = set()

            # Calculate group features
            result = calculator_fn(df, available, **kwargs)

            # Validate result conforms to Protocol (LSP)
            self._registry.validate_result(result, group_name)

            # Log completion at DEBUG level
            if should_log(LogCategory.DIAG, Verbosity.DEBUG):
                elapsed = time.perf_counter() - start_time
                self._logger.debug(
                    f"{group_name}: {len(result)} features in {elapsed:.2f}s"
                )

            return result

        except Exception as e:
            self._logger.error(f"Error calculating group {group_name}: {e}")
            raise FeatureError(f"Failed to calculate group {group_name}: {e}") from e

    def calculate_groups(
        self,
        df: pd.DataFrame,
        groups: list[str] | None = None,
        available: set[str] | None = None,
        **kwargs,
    ) -> dict[str, dict[str, pd.Series]]:
        """
        Calculate features for multiple groups.

        Args:
            df: DataFrame with OHLCV data
            groups: List of group names to calculate (None = all in order)
            available: Set of indicator names to calculate
            **kwargs: Additional parameters

        Returns:
            Dictionary mapping group names to their results
        """
        if groups is None:
            groups = [entry.name for entry in self._registry.get_ordered()]

        results = {}
        for group_name in groups:
            try:
                results[group_name] = self.calculate_group(
                    df, group_name, available, **kwargs
                )
            except FeatureError as e:
                self._logger.error(f"Group {group_name} failed: {e}")
                results[group_name] = {}

        return results

    def get_ordered_groups(self) -> list[GroupEntry]:
        """Get all groups in execution order."""
        return self._registry.get_ordered()

    def get_group_names(self) -> list[str]:
        """Get names of all registered groups."""
        return [entry.name for entry in self._registry.get_ordered()]
