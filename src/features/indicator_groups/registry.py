"""
Group Registry with decorator-based registration.

This module provides a centralized registry for indicator groups with
automatic registration via decorators. This eliminates the need to manually
update __init__.py when adding new groups.

SOLID principles:
- O (OCP): Adding new groups doesn't require modifying existing code
- D (DIP): Groups register themselves via decorator
- L (LSP): All group calculators must return dict[str, pd.Series]

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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd

logger = get_logger(__name__)


@runtime_checkable
class GroupCalculatorProtocol(Protocol):
    """
    Protocol for group calculator functions (LSP compliance).

    All group calculators MUST:
    1. Accept a DataFrame with OHLCV data
    2. Accept a set of indicator names to calculate
    3. Return a dict[str, pd.Series] with calculated indicators

    This ensures Liskov Substitution Principle - any group calculator
    can be used interchangeably without breaking the contract.
    """

    def __call__(
        self,
        df: pd.DataFrame,
        available: set[str],
        **kwargs,
    ) -> dict[str, pd.Series]:
        """
        Calculate indicators for a group.

        Args:
            df: DataFrame with OHLCV data
            available: Set of indicator names to calculate
            **kwargs: Additional parameters

        Returns:
            Dictionary mapping indicator names to pandas Series
        """
        ...


# Type alias for backward compatibility
GroupCalculatorFunc = GroupCalculatorProtocol


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


class GroupCalculatorTypeError(TypeError):
    """Raised when a group calculator doesn't meet the Protocol requirements."""

    pass


class GroupRegistry:
    """
    Centralized registry for indicator groups.

    Provides decorator-based registration and ordered retrieval of groups.
    Uses name mangling for encapsulation (__groups, __initialized).

    Example:
        @GroupRegistry.register("ma", order=1, dependencies=["overlap"])
        def calc_ma_indicators(df, available):
            ...

        # Get all groups in order
        for entry in GroupRegistry.get_ordered():
            result = entry.calculator(df, available)
    """

    # Private class attributes with name mangling for encapsulation
    __groups: dict[str, GroupEntry] = {}
    __initialized: bool = False

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

        Raises:
            GroupCalculatorTypeError: If the function doesn't match Protocol

        Example:
            @GroupRegistry.register("ma", order=1, dependencies=["overlap"])
            def calc_ma_indicators(df, available):
                ...
        """

        def decorator(func: GroupCalculatorFunc) -> GroupCalculatorFunc:
            # Runtime type validation (LSP compliance)
            cls.__validate_calculator(func, name)

            entry = GroupEntry(
                name=name,
                calculator=func,
                order=order,
                dependencies=dependencies or [],
                description=description,
            )
            cls.__groups[name] = entry
            logger.debug(f"Registered group '{name}' with order={order}")
            return func

        return decorator

    @classmethod
    def __validate_calculator(cls, func: GroupCalculatorFunc, name: str) -> None:
        """
        Validate that a calculator function meets the Protocol requirements.

        Args:
            func: Function to validate
            name: Group name for error messages

        Raises:
            GroupCalculatorTypeError: If function doesn't match Protocol
        """
        import inspect

        # Check if callable
        if not callable(func):
            raise GroupCalculatorTypeError(
                f"Group '{name}' calculator must be callable, got {type(func).__name__}"
            )

        # Check function signature
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Must have at least 2 positional params: df, available
        if len(params) < 2:
            raise GroupCalculatorTypeError(
                f"Group '{name}' calculator must accept at least 2 parameters "
                f"(df, available), got {len(params)}: {params}"
            )

        # Check type hints if available
        annotations = getattr(func, "__annotations__", {})
        return_annotation = annotations.get("return")

        if return_annotation is not None:
            # Allow dict[str, pd.Series], dict[str, Any], dict, or no annotation
            return_str = str(return_annotation)
            if "dict" not in return_str.lower() and return_annotation is not dict:
                logger.warning(
                    f"Group '{name}' calculator return type should be dict[str, pd.Series], "
                    f"got {return_annotation}. This may cause LSP violations."
                )

    @classmethod
    def get(cls, name: str) -> GroupEntry | None:
        """Get a group entry by name."""
        cls.__ensure_initialized()
        return cls.__groups.get(name)

    @classmethod
    def get_calculator(cls, name: str) -> GroupCalculatorFunc | None:
        """Get calculator function for a group."""
        entry = cls.get(name)
        return entry.calculator if entry else None

    @classmethod
    def get_ordered(cls) -> list[GroupEntry]:
        """Get all groups sorted by execution order."""
        cls.__ensure_initialized()
        return sorted(cls.__groups.values(), key=lambda g: g.order)

    @classmethod
    def get_ordered_items(cls) -> list[tuple[str, GroupCalculatorFunc]]:
        """Get ordered list of (name, calculator) tuples for compatibility."""
        return [(entry.name, entry.calculator) for entry in cls.get_ordered()]

    @classmethod
    def get_all_names(cls) -> list[str]:
        """Get all registered group names."""
        cls.__ensure_initialized()
        return list(cls.__groups.keys())

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
    def validate_result(
        cls, result: Any, group_name: str, *, strict: bool = False
    ) -> bool:
        """
        Validate that a calculator result conforms to the Protocol.

        This provides runtime LSP verification after calculation.

        Args:
            result: The return value from a group calculator
            group_name: Name of the group (for error messages)
            strict: If True, raise exception on violation; if False, log warning

        Returns:
            True if result is valid, False otherwise

        Raises:
            GroupCalculatorTypeError: If strict=True and result is invalid
        """
        import pandas as pd

        # Must be a dict
        if not isinstance(result, dict):
            msg = (
                f"Group '{group_name}' returned {type(result).__name__}, "
                f"expected dict[str, pd.Series]"
            )
            if strict:
                raise GroupCalculatorTypeError(msg)
            logger.warning(msg)
            return False

        # All values must be pd.Series
        invalid_values = []
        for key, value in result.items():
            if not isinstance(value, pd.Series):
                invalid_values.append((key, type(value).__name__))

        if invalid_values:
            msg = (
                f"Group '{group_name}' returned non-Series values: "
                f"{invalid_values[:5]}{'...' if len(invalid_values) > 5 else ''}"
            )
            if strict:
                raise GroupCalculatorTypeError(msg)
            logger.warning(msg)
            return False

        return True

    @classmethod
    def get_all_metadata(cls) -> dict[str, dict[str, Any]]:
        """Get metadata for all groups."""
        cls.__ensure_initialized()
        return {name: cls.get_metadata(name) for name in cls.__groups}

    @classmethod
    def clear(cls) -> None:
        """Clear all registered groups (for testing)."""
        cls.__groups.clear()
        cls.__initialized = False

    @classmethod
    def __ensure_initialized(cls) -> None:
        """Ensure legacy groups are imported and registered."""
        if cls.__initialized:
            return

        # Import legacy groups to trigger registration
        # This provides backward compatibility
        if not cls.__groups:
            cls.__import_legacy_groups()

        cls.__initialized = True

    @classmethod
    def __import_legacy_groups(cls) -> None:
        """Import legacy groups from __init__.py for backward compatibility."""
        try:
            from . import (
                GROUP_CALCULATORS,
                GROUP_METADATA,
            )

            for name, calculator in GROUP_CALCULATORS.items():
                if name not in cls.__groups:
                    meta = GROUP_METADATA.get(name, {})
                    entry = GroupEntry(
                        name=name,
                        calculator=calculator,
                        order=meta.get("order", 999),
                        dependencies=meta.get("dependencies", []),
                        description=meta.get("description", ""),
                    )
                    cls.__groups[name] = entry

            logger.debug(f"Imported {len(cls.__groups)} legacy groups")

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
