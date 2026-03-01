"""
Strategy module for determining max lookback periods.

This module provides functions to determine the maximum lookback period
required for different indicator strategies.
"""

from typing import Any

from src.logging import get_logger

logger = get_logger(__name__)

# Strategy definitions with their max lookback periods
STRATEGY_LOOKBACKS = {
    # Moving Averages
    "sma_5": 5,
    "sma_10": 10,
    "sma_20": 20,
    "sma_50": 50,
    "sma_100": 100,
    "sma_200": 200,
    "ema_8": 8,
    "ema_12": 12,
    "ema_21": 21,
    "ema_26": 26,
    "ema_50": 50,
    "ema_100": 100,
    "ema_200": 200,
    # Oscillators
    "rsi_14": 14,
    "rsi_21": 21,
    "stoch_14": 14,
    "willr_14": 14,
    "cci_20": 20,
    "cmo_14": 14,
    # Volatility
    "atr_14": 14,
    "atr_21": 21,
    "bb_20": 20,
    "bb_50": 50,
    "kc_20": 20,
    "dc_20": 20,
    # Trend
    "adx_14": 14,
    "adx_21": 21,
    "aroon_14": 14,
    "dmi_14": 14,
    "psar": 1,  # Parabolic SAR doesn't need much lookback
    # Volume
    "obv": 1,
    "ad": 1,
    "mfi_14": 14,
    "vwap": 1,
    # MACD
    "macd": 26,  # EMA 26 is the slowest component
    "macd_signal": 26,
    "macd_histogram": 26,
    # Candles (most don't need lookback)
    "cdl_doji": 1,
    "cdl_hammer": 1,
    "cdl_engulfing": 1,
    "cdl_harami": 1,
    "cdl_marubozu": 1,
    "cdl_piercing": 1,
    "cdl_shooting_star": 1,
    "cdl_spinning_top": 1,
    "cdl_three_crows": 1,
    "cdl_three_white_soldiers": 1,
    # Statistics
    "std_20": 20,
    "var_20": 20,
    "skew_20": 20,
    "kurt_20": 20,
    # Performance
    "returns": 1,
    "log_returns": 1,
    "volatility": 20,
    "sharpe_ratio": 20,
    # Overlap
    "hlc3": 1,
    "hl2": 1,
    "ohlc4": 1,
    # Squeeze
    "squeeze": 20,
    "squeeze_direction": 20,
    "squeeze_momentum": 20,
}


def max_lookback(strategy: str) -> int:
    """
    Get the maximum lookback period for a strategy.

    Args:
        strategy: Strategy name

    Returns:
        Maximum lookback period in bars
    """
    return STRATEGY_LOOKBACKS.get(strategy, 1)


def get_strategy_lookbacks(strategies: list[str]) -> dict[str, int]:
    """
    Get lookback periods for multiple strategies.

    Args:
        strategies: List of strategy names

    Returns:
        Dictionary mapping strategy names to lookback periods
    """
    return {strategy: max_lookback(strategy) for strategy in strategies}


def get_max_lookback_for_strategies(strategies: list[str]) -> int:
    """
    Get the maximum lookback period across multiple strategies.

    Args:
        strategies: List of strategy names

    Returns:
        Maximum lookback period across all strategies
    """
    if not strategies:
        return 1

    lookbacks = [max_lookback(strategy) for strategy in strategies]
    return max(lookbacks)


def get_available_strategies() -> list[str]:
    """
    Get list of all available strategies.

    Returns:
        List of strategy names
    """
    return list(STRATEGY_LOOKBACKS.keys())


def get_strategies_by_category() -> dict[str, list[str]]:
    """
    Get strategies grouped by category.

    Returns:
        Dictionary mapping categories to strategy lists
    """
    return {
        "moving_averages": [
            s for s in STRATEGY_LOOKBACKS if s.startswith(("sma_", "ema_"))
        ],
        "oscillators": [
            s
            for s in STRATEGY_LOOKBACKS
            if s.startswith(("rsi_", "stoch_", "willr_", "cci_", "cmo_"))
        ],
        "volatility": [
            s for s in STRATEGY_LOOKBACKS if s.startswith(("atr_", "bb_", "kc_", "dc_"))
        ],
        "trend": [
            s
            for s in STRATEGY_LOOKBACKS
            if s.startswith(("adx_", "aroon_", "dmi_", "psar"))
        ],
        "volume": [
            s for s in STRATEGY_LOOKBACKS if s in ["obv", "ad", "mfi_14", "vwap"]
        ],
        "macd": [s for s in STRATEGY_LOOKBACKS if s.startswith("macd")],
        "candles": [s for s in STRATEGY_LOOKBACKS if s.startswith("cdl_")],
        "statistics": [
            s
            for s in STRATEGY_LOOKBACKS
            if s.startswith(("std_", "var_", "skew_", "kurt_"))
        ],
        "performance": [
            s
            for s in STRATEGY_LOOKBACKS
            if s in ["returns", "log_returns", "volatility", "sharpe_ratio"]
        ],
        "overlap": [
            s for s in STRATEGY_LOOKBACKS if s in ["hlc3", "hl2", "ohlc4", "vwap"]
        ],
        "squeeze": [s for s in STRATEGY_LOOKBACKS if s.startswith("squeeze")],
    }


def validate_strategy(strategy: str) -> bool:
    """
    Validate if a strategy is supported.

    Args:
        strategy: Strategy name to validate

    Returns:
        True if strategy is supported, False otherwise
    """
    return strategy in STRATEGY_LOOKBACKS


def get_strategy_info(strategy: str) -> dict[str, Any]:
    """
    Get detailed information about a strategy.

    Args:
        strategy: Strategy name

    Returns:
        Dictionary with strategy information
    """
    if not validate_strategy(strategy):
        return {"error": f"Unknown strategy: {strategy}"}

    lookback = max_lookback(strategy)

    # Determine category
    category = "unknown"
    for cat, strategies in get_strategies_by_category().items():
        if strategy in strategies:
            category = cat
            break

    return {
        "strategy": strategy,
        "lookback": lookback,
        "category": category,
        "supported": True,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Strategy lookback information")
    parser.add_argument("--strategy", help="Get lookback for specific strategy")
    parser.add_argument(
        "--list", action="store_true", help="List all available strategies"
    )
    parser.add_argument(
        "--categories", action="store_true", help="Show strategies by category"
    )

    args = parser.parse_args()

    if args.strategy:
        info = get_strategy_info(args.strategy)
        print(f"Strategy: {info['strategy']}")
        print(f"Lookback: {info['lookback']}")
        print(f"Category: {info['category']}")
    elif args.list:
        strategies = get_available_strategies()
        print("Available strategies:")
        for strategy in sorted(strategies):
            lookback = max_lookback(strategy)
            print(f"  {strategy}: {lookback}")
    elif args.categories:
        categories = get_strategies_by_category()
        for category, strategies in categories.items():
            print(f"\n{category.upper()}:")
            for strategy in sorted(strategies):
                lookback = max_lookback(strategy)
                print(f"  {strategy}: {lookback}")
    else:
        parser.print_help()
