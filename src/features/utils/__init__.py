"""
Utils package for features module.

This package provides utility functions for feature calculation.
Functions from the parent utils.py module are re-exported here
for convenience and to avoid import conflicts.
"""

import importlib.util
import logging
from pathlib import Path

from .memlog import MemLog, force_cleanup, log_dataframe_info, memory_monitor

logger = logging.getLogger(__name__)

# Import from parent utils.py module (src/features/utils.py)
# Use importlib.util to load the parent module directly from file
# This avoids conflicts between the utils.py module and utils/ package
try:
    parent_dir = Path(__file__).parent.parent
    utils_py_path = parent_dir / "utils.py"

    if not utils_py_path.exists():
        raise ImportError(f"utils.py not found at {utils_py_path}")

    spec = importlib.util.spec_from_file_location(
        "features_utils_module", utils_py_path
    )
    if not spec or not spec.loader:
        raise ImportError("Failed to create spec for utils.py")

    parent_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent_utils)

    # Re-export functions from parent utils module
    volatility_normalize_features = getattr(
        parent_utils, "volatility_normalize_features", None
    )
    zscore_normalize_features = getattr(parent_utils, "zscore_normalize_features", None)
    minmax_normalize_features = getattr(parent_utils, "minmax_normalize_features", None)
    calculate_feature_statistics = getattr(
        parent_utils, "calculate_feature_statistics", None
    )
    ensure_no_lookahead = getattr(parent_utils, "ensure_no_lookahead", None)
    _normalize_series_by_volatility = getattr(
        parent_utils, "_normalize_series_by_volatility", None
    )
    assert_frames_close = getattr(parent_utils, "assert_frames_close", None)
    ta = getattr(parent_utils, "ta", None)
    safe_sma = getattr(parent_utils, "safe_sma", None)
    safe_ema = getattr(parent_utils, "safe_ema", None)
    _first_col_or_series = getattr(parent_utils, "_first_col_or_series", None)
    _nan_series = getattr(parent_utils, "_nan_series", None)

except (ImportError, AttributeError, ValueError, Exception) as e:
    logger.warning(f"Failed to import from parent utils module: {e}")
    volatility_normalize_features = None
    zscore_normalize_features = None
    minmax_normalize_features = None
    calculate_feature_statistics = None
    ensure_no_lookahead = None
    _normalize_series_by_volatility = None
    assert_frames_close = None
    ta = None
    safe_sma = None
    safe_ema = None
    _first_col_or_series = None
    _nan_series = None

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
