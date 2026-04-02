"""
Infrastructure: database helpers extracted from calc_indicators.py.

  -   .
"""

from __future__ import annotations

from ..storage_contract import IndicatorStorageContract

# ============================================================================
#
# ============================================================================

#
INDICATOR_COLUMNS = {
    "symbol",
    "timeframe",
    "timestamp",
    "calculated_at",
    "ema_12",
    "ema_21",
    "ema_26",
    "ema_50",
    "ema_200",
    "sma_20",
    "sma_34",
    "sma_50",
    "sma_200",
    "rsi_14",
    "atr_14",
    "adx_14",
    "adx_pos_di",
    "adx_neg_di",
    "macd",
    "macd_signal",
    "macd_histogram",
    "obv",
    "vwap",
}

#
REQUIRED_FIELDS = IndicatorStorageContract.identity_fields_set()

# ============================================================================
#
# ============================================================================

#


# ============================================================================
#  :
# ============================================================================

from .db_operations import ensure_columns_exist, fetch_latest_ts, fetch_ohlcv_df
from .persistence.inserter import insert_indicators
from .persistence.schema_checker import reflect_indicators_table

__all__ = [
    "INDICATOR_COLUMNS",
    "REQUIRED_FIELDS",
    "ensure_columns_exist",
    "fetch_latest_ts",
    "fetch_ohlcv_df",
    "insert_indicators",
    "reflect_indicators_table",
]
