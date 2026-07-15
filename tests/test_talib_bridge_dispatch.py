"""Tests for TA-Lib bridge dispatch table and error handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.features.ta_safe.adapters import TALIB_DISPATCH
from src.features.ta_safe.bridge import _talib_bridge
from src.features.ta_safe.errors import FeatureCalcError


def _make_df(rows: int = 30) -> pd.DataFrame:
    import numpy as np

    rng = np.random.default_rng(0)
    close = 100.0 + rng.normal(0, 1, rows).cumsum()
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.1, rows),
            "high": close + abs(rng.normal(0, 0.2, rows)),
            "low": close - abs(rng.normal(0, 0.2, rows)),
            "close": close,
            "volume": rng.integers(1000, 5000, rows).astype(float),
        }
    )


# --- Dispatch table contract ---


def test_talib_dispatch_is_dict():
    assert isinstance(TALIB_DISPATCH, dict)


def test_talib_dispatch_not_empty():
    assert len(TALIB_DISPATCH) > 0


def test_talib_dispatch_values_are_callable():
    for name, fn in TALIB_DISPATCH.items():
        assert callable(fn), f"TALIB_DISPATCH[{name!r}] is not callable"


def test_squeeze_not_in_dispatch():
    """TTM Squeeze has no TA-Lib equivalent — must remain custom."""
    assert "squeeze" not in TALIB_DISPATCH
    assert "squeeze_pro" not in TALIB_DISPATCH


# --- Bridge error handling ---


def test_bridge_unknown_name_raises():
    df = _make_df()
    with pytest.raises(FeatureCalcError, match="TA-Lib mapping not found"):
        _talib_bridge(df, "__nonexistent_indicator__")


def test_bridge_import_error_raises_feature_calc_error():
    df = _make_df()
    indicator_name = next(iter(TALIB_DISPATCH))

    def failing_adapter(df, **kwargs):
        raise ImportError("TA-Lib not installed")

    with patch.dict(TALIB_DISPATCH, {indicator_name: failing_adapter}):
        with pytest.raises(FeatureCalcError, match="TA-Lib not available"):
            _talib_bridge(df, indicator_name)


def test_bridge_runtime_error_raises_feature_calc_error():
    df = _make_df()
    indicator_name = next(iter(TALIB_DISPATCH))

    def crashing_adapter(df, **kwargs):
        raise RuntimeError("TA-Lib internal error")

    with patch.dict(TALIB_DISPATCH, {indicator_name: crashing_adapter}):
        with pytest.raises(FeatureCalcError, match="TA-Lib failed"):
            _talib_bridge(df, indicator_name)


def test_bridge_success_returns_dataframe():
    df = _make_df()
    indicator_name = next(iter(TALIB_DISPATCH))

    mock_result = pd.DataFrame({"result_col": [1.0] * len(df)}, index=df.index)
    mock_adapter = MagicMock(return_value=mock_result)

    with patch.dict(TALIB_DISPATCH, {indicator_name: mock_adapter}):
        result = _talib_bridge(df, indicator_name)

    assert isinstance(result, pd.DataFrame)
    mock_adapter.assert_called_once()
