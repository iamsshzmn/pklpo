"""Compatibility API surface for market metadata now hosted in ``src.candles``."""

from .application.api import (
    MarketMetaAPI,
    calculate_notional_value,
    get_funding_rate,
    get_instrument_info,
    get_liquidity_info,
    get_mark_price,
    get_open_interest,
    refresh_okx_meta,
    refresh_okx_meta_extended,
    validate_order,
)
from .application.metadata import (
    get_market_instrument_info,
    refresh_market_metadata,
    run_metadata_refresh_job,
    validate_instrument_order,
)

__all__ = [
    "MarketMetaAPI",
    "calculate_notional_value",
    "get_funding_rate",
    "get_instrument_info",
    "get_liquidity_info",
    "get_mark_price",
    "get_market_instrument_info",
    "get_open_interest",
    "refresh_market_metadata",
    "refresh_okx_meta",
    "refresh_okx_meta_extended",
    "run_metadata_refresh_job",
    "validate_instrument_order",
    "validate_order",
]
