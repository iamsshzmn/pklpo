"""
Utils package for features module.

This package re-exports helpers from the sibling `utils.py` module so callers
can keep using `src.features.utils` as a stable import surface.
"""

from .memlog import MemLog, force_cleanup, log_dataframe_info, memory_monitor
from .utils import (
    _first_col_or_series,
    _nan_series,
    _normalize_series_by_volatility,
    assert_frames_close,
    calculate_feature_statistics,
    ensure_no_lookahead,
    minmax_normalize_features,
    safe_ema,
    safe_sma,
    volatility_normalize_features,
    zscore_normalize_features,
)

ta = None

__all__ = [
    "MemLog",
    "_first_col_or_series",
    "_nan_series",
    "_normalize_series_by_volatility",
    "assert_frames_close",
    "calculate_feature_statistics",
    "ensure_no_lookahead",
    "force_cleanup",
    "log_dataframe_info",
    "memory_monitor",
    "minmax_normalize_features",
    "safe_ema",
    "safe_sma",
    "ta",
    "volatility_normalize_features",
    "zscore_normalize_features",
]
