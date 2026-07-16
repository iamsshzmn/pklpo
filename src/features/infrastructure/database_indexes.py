"""Compatibility feature index manager."""

from __future__ import annotations

from typing import Any


class FeaturesIndexManager:
    def create_core_indexes(self, *args: Any, **kwargs: Any) -> list[str]:
        return []

    def create_feature_specific_indexes(self, *args: Any, **kwargs: Any) -> list[str]:
        return []

    def create_covering_indexes(self, *args: Any, **kwargs: Any) -> list[str]:
        return []

    def analyze_index_usage(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}

    def optimize_indexes(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}


__all__ = ["FeaturesIndexManager"]
