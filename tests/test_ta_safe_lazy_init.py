"""Tests for ta_safe lazy initialization of available functions."""

from __future__ import annotations

import pytest

import src.features.ta_safe.backend as backend_module


def _reset_lazy_cache() -> None:
    """Reset the lazy-init cache to allow re-testing initialization."""
    backend_module._AVAILABLE_FUNCTIONS = None


# --- Lazy init contract ---

def test_lazy_init_starts_as_none():
    _reset_lazy_cache()
    assert backend_module._AVAILABLE_FUNCTIONS is None


def test_get_available_functions_initializes():
    _reset_lazy_cache()
    result = backend_module._get_available_functions()
    assert result is not None
    assert isinstance(result, set)


def test_get_available_functions_caches_result():
    _reset_lazy_cache()
    first = backend_module._get_available_functions()
    # Second call must return the same object (no re-init)
    second = backend_module._get_available_functions()
    assert first is second


def test_get_available_functions_no_reinit_on_repeated_calls():
    _reset_lazy_cache()
    call_count = 0
    original_detect = backend_module._detect_available_functions

    def counting_detect():
        nonlocal call_count
        call_count += 1
        return original_detect()

    backend_module._detect_available_functions = counting_detect
    try:
        backend_module._get_available_functions()
        backend_module._get_available_functions()
        backend_module._get_available_functions()
    finally:
        backend_module._detect_available_functions = original_detect
        _reset_lazy_cache()

    assert call_count == 1, "Detection must run exactly once"


# --- detect_available_functions contract ---

def test_detect_returns_subset_of_allow():
    from src.features.ta_safe.constants import ALLOW
    _reset_lazy_cache()
    detected = backend_module._detect_available_functions()
    assert isinstance(detected, set)
    assert detected <= ALLOW


def test_available_functions_are_strings():
    _reset_lazy_cache()
    funcs = backend_module._get_available_functions()
    for name in funcs:
        assert isinstance(name, str), f"Expected str, got {type(name)}: {name!r}"


# --- safe_ta contract ---

def test_safe_ta_raises_for_forbidden_name():
    import pandas as pd

    from src.features.ta_safe.backend import safe_ta
    from src.features.ta_safe.errors import FeatureCalcError

    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0],
            "high": [2.0, 3.0, 4.0],
            "low": [1.0, 2.0, 3.0],
            "close": [2.0, 3.0, 4.0],
            "volume": [100.0, 200.0, 300.0],
        }
    )
    with pytest.raises(FeatureCalcError):
        safe_ta(df, "__not_in_allowlist__")


def test_safe_ta_raises_for_empty_df():
    import pandas as pd

    from src.features.ta_safe.backend import safe_ta
    from src.features.ta_safe.constants import ALLOW
    from src.features.ta_safe.errors import FeatureCalcError

    empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    allowed_name = next(iter(ALLOW))
    with pytest.raises(FeatureCalcError):
        safe_ta(empty_df, allowed_name)
