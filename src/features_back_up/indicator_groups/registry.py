"""
Group Registry with decorator-based registration.

This module provides a centralized registry for indicator groups with
automatic registration via decorators. This eliminates the need to manually
update __init__.py when adding new groups.

SOLID principles:
- O (OCP): Adding new groups doesn't require modifying existing code
- D (DIP): Groups register themselves via decorator

Usage:
    # In each group file (e.g., ma.py):
    from .registry import GroupRegistry

    @GroupRegistry.register("ma", order=1, dependencies=["overlap"])
    def calc_ma_indicators(df, available):
        ...

    # To get ordered groups:
    from .registry import GroupRegistry
    for group in GroupRegistry.get_ordered():
        result = group.calculator(df, available)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.logging import get_logger

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)


# Type alias for group calculator function
GroupCalculatorFunc = Callable[["pd.DataFrame", set[str]], dict[str, Any]]


@dataclass
class GroupEntry:
    """Entry for a registered indicator group."""

    name: str
    calculator: GroupCalculatorFunc
    order: int
    dependencies: list[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self):
        if not self.description:
            self.description = f"{self.name} indicator group"


class GroupRegistry:
    """
    Centralized registry for indicator groups.

    Provides decorator-based registration and ordered retrieval of groups.

    Example:
        @GroupRegistry.register("ma", order=1, dependencies=["overlap"])
        def calc_ma_indicators(df, available):
            ...

        # Get all groups in order
        for entry in GroupRegistry.get_ordered():
            result = entry.calculator(df, available)
    """

    _groups: dict[str, GroupEntry] = {}
    _initialized: bool = False

    @classmethod
    def register(
        cls,
        name: str,
        order: int,
        dependencies: list[str] | None = None,
        description: str = "",
    ) -> Callable[[GroupCalculatorFunc], GroupCalculatorFunc]:
        """
        Decorator to register an indicator group.

        Args:
            name: Unique name for the group
            order: Execution order (lower = earlier)
            dependencies: List of group names this group depends on
            description: Human-readable description

        Returns:
            Decorator function

        Example:
            @GroupRegistry.register("ma", order=1, dependencies=["overlap"])
            def calc_ma_indicators(df, available):
                ...
        """

        def decorator(func: GroupCalculatorFunc) -> GroupCalculatorFunc:
            entry = GroupEntry(
                name=name,
                calculator=func,
                order=order,
                dependencies=dependencies or [],
                description=description,
            )
            cls._groups[name] = entry
            logger.debug(f"Registered group '{name}' with order={order}")
            return func

        return decorator

    @classmethod
    def get(cls, name: str) -> GroupEntry | None:
        """Get a group entry by name."""
        cls._ensure_initialized()
        return cls._groups.get(name)

    @classmethod
    def get_calculator(cls, name: str) -> GroupCalculatorFunc | None:
        """Get calculator function for a group."""
        entry = cls.get(name)
        return entry.calculator if entry else None

    @classmethod
    def get_ordered(cls) -> list[GroupEntry]:
        """Get all groups sorted by execution order."""
        cls._ensure_initialized()
        return sorted(cls._groups.values(), key=lambda g: g.order)

    @classmethod
    def get_ordered_items(cls) -> list[tuple[str, GroupCalculatorFunc]]:
        """Get ordered list of (name, calculator) tuples for compatibility."""
        return [(entry.name, entry.calculator) for entry in cls.get_ordered()]

    @classmethod
    def get_all_names(cls) -> list[str]:
        """Get all registered group names."""
        cls._ensure_initialized()
        return list(cls._groups.keys())

    @classmethod
    def get_dependencies(cls, name: str) -> list[str]:
        """Get dependencies for a group."""
        entry = cls.get(name)
        return entry.dependencies if entry else []

    @classmethod
    def get_metadata(cls, name: str) -> dict[str, Any]:
        """Get metadata for a group (compatibility with GROUP_METADATA)."""
        entry = cls.get(name)
        if entry is None:
            return {}
        return {
            "name": entry.name,
            "description": entry.description,
            "dependencies": entry.dependencies,
            "order": entry.order,
        }

    @classmethod
    def get_all_metadata(cls) -> dict[str, dict[str, Any]]:
        """Get metadata for all groups."""
        cls._ensure_initialized()
        return {name: cls.get_metadata(name) for name in cls._groups}

    @classmethod
    def clear(cls) -> None:
        """Clear all registered groups (for testing)."""
        cls._groups.clear()
        cls._initialized = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure legacy groups are imported and registered."""
        if cls._initialized:
            return

        # Import legacy groups to trigger registration
        # This provides backward compatibility
        if not cls._groups:
            cls._import_legacy_groups()

        cls._initialized = True

    @classmethod
    def _import_legacy_groups(cls) -> None:
        """Import legacy groups from __init__.py for backward compatibility."""
        try:
            from . import (
                GROUP_CALCULATORS,
                GROUP_METADATA,
            )

            for name, calculator in GROUP_CALCULATORS.items():
                if name not in cls._groups:
                    meta = GROUP_METADATA.get(name, {})
                    entry = GroupEntry(
                        name=name,
                        calculator=calculator,
                        order=meta.get("order", 999),
                        dependencies=meta.get("dependencies", []),
                        description=meta.get("description", ""),
                    )
                    cls._groups[name] = entry

            logger.debug(f"Imported {len(cls._groups)} legacy groups")

        except ImportError as e:
            logger.warning(f"Failed to import legacy groups: {e}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_ordered_groups() -> list[tuple[str, GroupCalculatorFunc]]:
    """
    Get all groups in execution order.

    Compatibility function for existing code.

    Returns:
        List of (group_name, calculator) tuples
    """
    return GroupRegistry.get_ordered_items()


def get_group_calculator(name: str) -> GroupCalculatorFunc | None:
    """Get calculator for a group by name."""
    return GroupRegistry.get_calculator(name)


def get_group_order(name: str) -> int:
    """Get execution order for a group."""
    entry = GroupRegistry.get(name)
    return entry.order if entry else 999
