"""
Group Persister (SRP: persistence only).

This module handles persistence of indicator data to the database
without calculation or metrics concerns. It follows the Single
Responsibility Principle by focusing solely on persistence logic.

Part of Phase 1.2 refactoring: Split GroupCalculator into SRP components.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..infrastructure.upsert_optimizer import UpsertConfig, UpsertOptimizer
from ..observability.logging import LogCategory, get_category_logger

if TYPE_CHECKING:
    import pandas as pd


__all__ = ["GroupPersister", "PersisterProtocol"]


@runtime_checkable
class PersisterProtocol(Protocol):
    """Protocol for persistence implementations (DIP compliance)."""

    def persist(
        self,
        df: pd.DataFrame,
        group_name: str,
        table_name: str,
        **kwargs,
    ) -> bool:
        """
        Persist data to storage.

        Args:
            df: DataFrame with calculated features
            group_name: Name of the group being persisted
            table_name: Target table name
            **kwargs: Additional parameters

        Returns:
            True if successful, False otherwise
        """
        ...


class GroupPersister:
    """
    Persister for indicator groups (SRP: persistence only).

    This class is responsible solely for persisting calculated
    features to the database. It does not handle calculation or metrics.

    Uses UpsertOptimizer for efficient database operations.
    """

    def __init__(self, config: UpsertConfig | None = None):
        """
        Initialize the persister.

        Args:
            config: Configuration for UPSERT operations
        """
        self._logger = get_category_logger(LogCategory.DB)
        self._optimizer = UpsertOptimizer(config or UpsertConfig())

    def persist_batch(
        self,
        df: pd.DataFrame,
        group_name: str,
        table_name: str = "indicators",
        **kwargs,
    ) -> bool:
        """
        Persist a batch of calculated features to database.

        Args:
            df: DataFrame with calculated features
            group_name: Name of the group being persisted
            table_name: Target table name
            **kwargs: Additional parameters for persistence

        Returns:
            True if successful, False otherwise
        """
        try:
            success = self._optimizer.upsert_batch(
                df, group_name, table_name=table_name, **kwargs
            )

            if not success:
                self._logger.error(f"Failed to persist batch for group {group_name}")

            return success

        except Exception as e:
            self._logger.error(f"Error persisting batch for group {group_name}: {e}")
            return False

    def persist_groups(
        self,
        group_results: dict[str, pd.DataFrame],
        table_name: str = "indicators",
        **kwargs,
    ) -> dict[str, bool]:
        """
        Persist multiple groups to database.

        Args:
            group_results: Dictionary mapping group names to DataFrames
            table_name: Target table name
            **kwargs: Additional parameters

        Returns:
            Dictionary mapping group names to success status
        """
        results = {}
        for group_name, df in group_results.items():
            results[group_name] = self.persist_batch(
                df, group_name, table_name, **kwargs
            )
        return results
