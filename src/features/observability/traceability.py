"""
Feature Traceability and Metadata Support

This module provides functionality to track the source and lineage of calculated features,
enabling debugging, auditing, and explainability for LLM pipelines.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class FeatureMetadata:
    """Metadata for a calculated feature."""

    # Core identification
    feature_name: str
    source_group: str  # e.g., 'oscillators', 'ma', 'volatility'

    # Calculation details
    calculation_function: str  # e.g., 'calc_oscillator_indicators'
    calculation_timestamp: datetime = field(default_factory=datetime.utcnow)

    # Quality metrics
    fill_rate: float = 0.0  # Percentage of non-null values
    nan_count: int = 0
    total_count: int = 0

    # Dependencies
    depends_on: list[str] = field(default_factory=list)  # List of required inputs

    # Parameters used
    parameters: dict[str, Any] = field(default_factory=dict)

    # Version tracking
    algorithm_version: str = "2.0.0"
    schema_version: str = "2.0.0"

    # Additional context
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feature_name": self.feature_name,
            "source_group": self.source_group,
            "calculation_function": self.calculation_function,
            "calculation_timestamp": self.calculation_timestamp.isoformat(),
            "fill_rate": self.fill_rate,
            "nan_count": self.nan_count,
            "total_count": self.total_count,
            "depends_on": self.depends_on,
            "parameters": self.parameters,
            "algorithm_version": self.algorithm_version,
            "schema_version": self.schema_version,
            "notes": self.notes,
        }


class FeatureTracer:
    """
    Tracks feature calculation lineage and metadata.

    Usage:
        tracer = FeatureTracer()

        # During calculation
        tracer.track_feature('ema_21', 'ma', 'calc_ma_indicators',
                           depends_on=['close'],
                           parameters={'period': 21})

        # Add quality metrics
        tracer.update_quality('ema_21', series)

        # Get metadata
        metadata = tracer.get_metadata('ema_21')
        lineage = tracer.get_lineage('ema_21')
    """

    def __init__(self):
        self._metadata: dict[str, FeatureMetadata] = {}
        self._enabled = True

    def enable(self):
        """Enable tracing."""
        self._enabled = True

    def disable(self):
        """Disable tracing (for performance)."""
        self._enabled = False

    def track_feature(
        self,
        feature_name: str,
        source_group: str,
        calculation_function: str,
        depends_on: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        notes: str = "",
    ):
        """
        Track a feature calculation.

        Args:
            feature_name: Name of the feature
            source_group: Indicator group (ma, oscillators, etc.)
            calculation_function: Function that calculated it
            depends_on: List of input fields required
            parameters: Calculation parameters
            notes: Additional notes
        """
        if not self._enabled:
            return

        metadata = FeatureMetadata(
            feature_name=feature_name,
            source_group=source_group,
            calculation_function=calculation_function,
            depends_on=depends_on or [],
            parameters=parameters or {},
            notes=notes,
        )

        self._metadata[feature_name] = metadata

    def update_quality(self, feature_name: str, series: pd.Series):
        """
        Update quality metrics for a feature.

        Args:
            feature_name: Name of the feature
            series: Pandas Series with the values
        """
        if not self._enabled or feature_name not in self._metadata:
            return

        metadata = self._metadata[feature_name]
        metadata.total_count = len(series)
        metadata.nan_count = int(series.isna().sum())
        metadata.fill_rate = (
            (metadata.total_count - metadata.nan_count) / metadata.total_count
            if metadata.total_count > 0
            else 0.0
        )

    def get_metadata(self, feature_name: str) -> FeatureMetadata | None:
        """
        Get metadata for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            FeatureMetadata or None if not tracked
        """
        return self._metadata.get(feature_name)

    def get_all_metadata(self) -> dict[str, FeatureMetadata]:
        """Get all tracked metadata."""
        return self._metadata.copy()

    def get_lineage(self, feature_name: str) -> list[str]:
        """
        Get full dependency lineage for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of all dependencies (recursive)
        """
        if feature_name not in self._metadata:
            return []

        metadata = self._metadata[feature_name]
        lineage = metadata.depends_on.copy()

        # Recursively add dependencies of dependencies
        for dep in metadata.depends_on:
            if dep in self._metadata:
                sub_lineage = self.get_lineage(dep)
                for item in sub_lineage:
                    if item not in lineage:
                        lineage.append(item)

        return lineage

    def get_features_by_group(self, group_name: str) -> list[str]:
        """
        Get all features from a specific group.

        Args:
            group_name: Name of the indicator group

        Returns:
            List of feature names
        """
        return [
            name
            for name, meta in self._metadata.items()
            if meta.source_group == group_name
        ]

    def get_quality_report(self) -> dict[str, Any]:
        """
        Generate a quality report for all tracked features.

        Returns:
            Dictionary with quality statistics
        """
        if not self._metadata:
            return {
                "total_features": 0,
                "avg_fill_rate": 0.0,
                "features_by_group": {},
                "low_quality_features": [],
            }

        total_fill_rate = sum(m.fill_rate for m in self._metadata.values())
        avg_fill_rate = total_fill_rate / len(self._metadata)

        # Group by source
        by_group: dict[str, list[str]] = {}
        for meta in self._metadata.values():
            if meta.source_group not in by_group:
                by_group[meta.source_group] = []
            by_group[meta.source_group].append(meta.feature_name)

        # Find low quality features (< 50% fill rate)
        low_quality = [
            (meta.feature_name, meta.fill_rate)
            for meta in self._metadata.values()
            if meta.fill_rate < 0.5
        ]

        return {
            "total_features": len(self._metadata),
            "avg_fill_rate": avg_fill_rate,
            "features_by_group": {k: len(v) for k, v in by_group.items()},
            "low_quality_features": low_quality,
        }

    def export_to_dataframe(self) -> pd.DataFrame:
        """
        Export all metadata to a DataFrame for analysis.

        Returns:
            DataFrame with metadata for all features
        """
        if not self._metadata:
            return pd.DataFrame()

        records = [meta.to_dict() for meta in self._metadata.values()]
        return pd.DataFrame(records)

    def clear(self):
        """Clear all tracked metadata."""
        self._metadata.clear()


# Global tracer instance
_global_tracer = FeatureTracer()


def get_global_tracer() -> FeatureTracer:
    """Get the global feature tracer instance."""
    return _global_tracer


def enable_tracing():
    """Enable global feature tracing."""
    _global_tracer.enable()


def disable_tracing():
    """Disable global feature tracing."""
    _global_tracer.disable()


def track_feature(*args, **kwargs):
    """Convenience function to track a feature using global tracer."""
    _global_tracer.track_feature(*args, **kwargs)


def get_feature_metadata(feature_name: str) -> FeatureMetadata | None:
    """Convenience function to get feature metadata."""
    return _global_tracer.get_metadata(feature_name)
