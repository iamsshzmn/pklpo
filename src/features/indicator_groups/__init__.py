"""
Indicator Groups (calculation layer).

This package implements HOW indicators are calculated, using ta_safe.
Each module (ma.py, oscillators.py, etc.) contains a calc_*_indicators() function.

Boundary:
    specs/ -> declares indicator metadata (names, params)
    indicator_groups/ -> implements calculation logic
    ta_safe/ -> provides safe_ta_with_fallback() for TA library calls

Groups are executed in the order defined in registry.py, which is important
for dependencies between groups (e.g., overlap must run before oscillators).

All group calculators follow the GroupCalculatorProtocol:
- Accept (df: pd.DataFrame, available: set[str], **kwargs)
- Return dict[str, pd.Series]

This ensures LSP compliance - any calculator can be used interchangeably.
"""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

from .candles import calc_candles_indicators
from .ma import calc_ma_indicators
from .oscillators import calc_oscillator_indicators
from .overlap import calc_overlap_indicators
from .performance import calc_performance_indicators
from .squeeze import calc_squeeze_indicators
from .statistics import calc_statistics_indicators
from .trend import calc_trend_indicators
from .volatility import calc_volatility_indicators
from .volume import calc_volume_indicators

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd

    from .registry import GroupEntry

# Type alias for group calculator function (LSP compliant)
GroupCalculator = "Callable[[pd.DataFrame, set[str]], dict[str, pd.Series]]"

GROUP_MODULES: tuple[str, ...] = (
    "overlap",
    "ma",
    "oscillators",
    "volatility",
    "volume",
    "trend",
    "squeeze",
    "candles",
    "statistics",
    "performance",
)

# Compatibility surface only. Runtime registration is now fully decorator-driven.
GROUP_CALCULATORS: dict[str, GroupCalculator] = {}

# Group metadata for dependency resolution
GROUP_METADATA: dict[str, dict[str, any]] = {  # type: ignore
    "overlap": {
        "name": "overlap",
        "description": "Basic price transformations (hl2, hlc3, ohlc4, wcp)",
        "dependencies": [],
        "order": 0,
    },
    "ma": {
        "name": "ma",
        "description": "Moving averages (SMA, EMA, WMA, etc.)",
        "dependencies": ["overlap"],  # May use hlc3, hl2
        "order": 1,
    },
    "oscillators": {
        "name": "oscillators",
        "description": "Oscillators (RSI, MACD, Stochastic, etc.)",
        "dependencies": ["overlap", "ma"],
        "order": 2,
    },
    "volatility": {
        "name": "volatility",
        "description": "Volatility indicators (ATR, BB, KC, etc.)",
        "dependencies": ["overlap", "ma"],
        "order": 3,
    },
    "volume": {
        "name": "volume",
        "description": "Volume indicators (OBV, VWAP, etc.)",
        "dependencies": ["overlap"],
        "order": 4,
    },
    "trend": {
        "name": "trend",
        "description": "Trend indicators (ADX, Ichimoku, etc.)",
        "dependencies": ["overlap", "ma"],
        "order": 5,
    },
    "squeeze": {
        "name": "squeeze",
        "description": "TTM Squeeze indicators",
        "dependencies": ["volatility", "trend"],
        "order": 6,
    },
    "candles": {
        "name": "candles",
        "description": "Candlestick patterns",
        "dependencies": ["overlap"],
        "order": 7,
    },
    "statistics": {
        "name": "statistics",
        "description": "Statistical indicators",
        "dependencies": ["overlap", "ma"],
        "order": 8,
    },
    "performance": {
        "name": "performance",
        "description": "Performance indicators",
        "dependencies": ["overlap", "ma", "volatility"],
        "order": 9,
    },
}


def ensure_group_modules_loaded(*, force_reload: bool = False) -> None:
    """Load or reload all group modules so decorator registration is applied."""
    package_name = __name__

    for module_name in GROUP_MODULES:
        qualified_name = f"{package_name}.{module_name}"
        if force_reload and qualified_name in sys.modules:
            importlib.reload(sys.modules[qualified_name])
            continue
        importlib.import_module(qualified_name)


def get_group_calculator(group_name: str) -> GroupCalculator | None:
    """
    Get calculator function for a group.

    Args:
        group_name: Name of the group

    Returns:
        Calculator function or None if not found
    """
    return registry_get_group_calculator(group_name)


def get_group_order(group_name: str) -> int:
    """
    Get execution order for a group.

    Args:
        group_name: Name of the group

    Returns:
        Order number (0 = first, higher = later)
    """
    return registry_get_group_order(group_name)


def get_ordered_groups() -> list[tuple[str, GroupCalculator]]:
    """
    Get all groups in execution order.

    Order is derived from GROUP_METADATA dependencies via topological sort
    (networkx). Falls back to `order` field if networkx is unavailable.

    Returns:
        List of (group_name, calculator) tuples in execution order
    """
    return registry_get_ordered_groups()


# Import from new registry module
from .registry import (
    GroupEntry,
    GroupRegistry,
    build_registry_snapshot,
    get_group_calculator as registry_get_group_calculator,
    get_group_order as registry_get_group_order,
    get_ordered_groups as registry_get_ordered_groups,
)

__all__ = [
    "GROUP_CALCULATORS",
    "GROUP_METADATA",
    "GROUP_MODULES",
    "GroupCalculator",
    "GroupEntry",
    "GroupRegistry",
    "build_registry_snapshot",
    "ensure_group_modules_loaded",
    "get_group_calculator",
    "get_group_order",
    "get_ordered_groups",
]
