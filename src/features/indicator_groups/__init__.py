"""
Indicator Groups Registry

This module provides a registry of all indicator group calculators.
Groups are executed in the order defined here, which is important for
dependencies between groups.
"""

from __future__ import annotations

from collections.abc import Callable

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

# Type alias for group calculator function
GroupCalculator = Callable[..., dict[str, any]]  # type: ignore

# Registry of indicator groups in execution order
# Order matters: overlap must be first, as other groups may depend on it
GROUP_CALCULATORS: dict[str, GroupCalculator] = {
    "overlap": calc_overlap_indicators,
    "ma": calc_ma_indicators,
    "oscillators": calc_oscillator_indicators,
    "volatility": calc_volatility_indicators,
    "volume": calc_volume_indicators,
    "trend": calc_trend_indicators,
    "squeeze": calc_squeeze_indicators,
    "candles": calc_candles_indicators,
    "statistics": calc_statistics_indicators,
    "performance": calc_performance_indicators,
}

# Group metadata for dependency resolution
GROUP_METADATA: dict[str, dict[str, any]] = {  # type: ignore
    "overlap": {
        "name": "overlap",
        "description": "Basic price transformations (hl2, hlc3, ohlc4, wcp)",
        "dependencies": [],  # No dependencies on other groups
        "order": 0,  # Must be first
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
        "dependencies": ["overlap", "ma"],  # May use overlap and MA
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


def get_group_calculator(group_name: str) -> GroupCalculator | None:
    """
    Get calculator function for a group.

    Args:
        group_name: Name of the group

    Returns:
        Calculator function or None if not found
    """
    return GROUP_CALCULATORS.get(group_name)


def get_group_order(group_name: str) -> int:
    """
    Get execution order for a group.

    Args:
        group_name: Name of the group

    Returns:
        Order number (0 = first, higher = later)
    """
    metadata = GROUP_METADATA.get(group_name, {})
    return metadata.get("order", 999)


def get_ordered_groups() -> list[tuple[str, GroupCalculator]]:
    """
    Get all groups in execution order.

    Returns:
        List of (group_name, calculator) tuples in execution order
    """
    return sorted(
        GROUP_CALCULATORS.items(),
        key=lambda x: get_group_order(x[0]),
    )


__all__ = [
    "GROUP_CALCULATORS",
    "GROUP_METADATA",
    "GroupCalculator",
    "get_group_calculator",
    "get_group_order",
    "get_ordered_groups",
]
