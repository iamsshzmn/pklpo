"""
Dependency resolver for feature indicators.

This module provides utilities for resolving indicator dependencies
based on the registry configuration.
"""

from __future__ import annotations

from typing import Any

from src.logging import get_logger

from ..registry import INDICATOR_CONFIG

logger = get_logger(__name__)


def resolve_dependencies(
    requested_indicators: set[str],
    registry: dict[str, dict[str, Any]] | None = None,
) -> set[str]:
    """
    Resolve all dependencies for requested indicators.

    Recursively adds all dependencies from the registry to the set of
    requested indicators.

    Args:
        requested_indicators: Set of initially requested indicator names
        registry: Optional registry dict (defaults to INDICATOR_CONFIG)

    Returns:
        Set of all indicators including dependencies
    """
    if registry is None:
        registry = INDICATOR_CONFIG

    resolved = set(requested_indicators)
    to_process = set(requested_indicators)
    processed = set()

    while to_process:
        current = to_process.pop()
        if current in processed:
            continue
        processed.add(current)

        # Get dependencies from registry
        if current not in registry:
            logger.debug(f"Indicator {current} not in registry, skipping dependencies")
            continue

        deps = registry[current].get("dependencies", [])
        if not deps or not isinstance(deps, list):
            continue

        logger.debug(f"Indicator {current} has dependencies: {deps}")

        # Add dependencies to resolved set
        for dep in deps:
            if isinstance(dep, str) and dep not in resolved:
                resolved.add(dep)
                to_process.add(dep)
                logger.debug(f"Added dependency {dep} for {current}")

    return resolved
