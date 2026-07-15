"""Tests for the cross-cutting ErrorType taxonomy and classify_error_type helper.

Host-runnable (stdlib only, no project deps needed).

RED/GREEN contract
------------------
Before T6.4 the module did not exist; all tests fail with ImportError / FileNotFoundError.
After T6.4 all assertions pass.
"""

from __future__ import annotations

import importlib.util
import socket
from pathlib import Path
from types import ModuleType

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_error_types() -> ModuleType:
    """Load error_types.py directly, bypassing the facade __init__."""
    module_path = (
        _PROJECT_ROOT / "src" / "pklpo_platform" / "observability" / "error_types.py"
    )
    spec = importlib.util.spec_from_file_location(
        "tests.pklpo_platform._error_types", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_error_type_enum_members_are_strings() -> None:
    m = _load_error_types()
    expected = {
        "db_error",
        "api_error",
        "timeout_error",
        "rate_limit_error",
        "validation_error",
        "eligibility_error",
        "data_quality_error",
        "permission_error",
        "lock_conflict",
        "unexpected_error",
    }
    assert {str(e) for e in m.ErrorType} == expected
    assert m.ErrorType.DB_ERROR == "db_error"
    assert m.ErrorType.RATE_LIMIT_ERROR == "rate_limit_error"
    assert m.ErrorType.UNEXPECTED_ERROR == "unexpected_error"


def test_error_type_exported_from_facade_init() -> None:
    init_src = (
        _PROJECT_ROOT / "src" / "pklpo_platform" / "observability" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "ErrorType" in init_src
    assert "classify_error_type" in init_src


def test_classify_db_error_via_connection_refused() -> None:
    m = _load_error_types()
    assert (
        m.classify_error_type(ConnectionRefusedError("connection refused"))
        == "db_error"
    )


def test_classify_db_error_via_message_marker() -> None:
    m = _load_error_types()
    assert m.classify_error_type(OSError("connection is closed")) == "db_error"


def test_classify_db_error_via_gaierror() -> None:
    m = _load_error_types()
    assert (
        m.classify_error_type(socket.gaierror("name or service not known"))
        == "db_error"
    )


def test_classify_rate_limit_via_429_message() -> None:
    m = _load_error_types()
    assert (
        m.classify_error_type(Exception("HTTP 429 Too Many Requests"))
        == "rate_limit_error"
    )


def test_classify_rate_limit_via_okx_code_50011() -> None:
    m = _load_error_types()
    assert (
        m.classify_error_type(Exception("OKX error code 50011: rate limit"))
        == "rate_limit_error"
    )


def test_classify_timeout_via_message() -> None:
    m = _load_error_types()
    assert (
        m.classify_error_type(TimeoutError("request timed out after 30s"))
        == "timeout_error"
    )


def test_classify_timeout_via_class_name() -> None:
    m = _load_error_types()

    class ReadTimeout(Exception):
        pass

    assert m.classify_error_type(ReadTimeout("read timed out")) == "timeout_error"


def test_classify_api_error_via_5xx_marker() -> None:
    m = _load_error_types()
    assert m.classify_error_type(Exception("received 5xx from upstream")) == "api_error"


def test_classify_unexpected_error_fallback() -> None:
    m = _load_error_types()
    assert m.classify_error_type(ValueError("something unknown")) == "unexpected_error"


def test_classify_walks_exception_chain() -> None:
    m = _load_error_types()
    root = ConnectionRefusedError("db port closed")
    wrapper = RuntimeError("db operation failed")
    wrapper.__cause__ = root
    assert m.classify_error_type(wrapper) == "db_error"


def test_classify_chain_first_match_wins() -> None:
    m = _load_error_types()
    root = ConnectionError("connection refused")
    wrapper = Exception("429 wrapping a db outage")
    wrapper.__context__ = root
    # Wrapper (429) checked first -> rate_limit_error
    assert m.classify_error_type(wrapper) == "rate_limit_error"


def test_sync_use_cases_imports_classify_error_type() -> None:
    src = (
        _PROJECT_ROOT / "src" / "candles" / "application" / "sync" / "use_cases.py"
    ).read_text(encoding="utf-8")
    assert "classify_error_type" in src


def test_repair_use_cases_imports_classify_error_type() -> None:
    src = (
        _PROJECT_ROOT / "src" / "candles" / "application" / "repair" / "use_cases.py"
    ).read_text(encoding="utf-8")
    assert "classify_error_type" in src


def test_bootstrap_use_cases_imports_classify_error_type() -> None:
    src = (
        _PROJECT_ROOT / "src" / "candles" / "application" / "bootstrap" / "use_cases.py"
    ).read_text(encoding="utf-8")
    assert "classify_error_type" in src


def test_no_hardcoded_unexpected_error_string_in_use_cases() -> None:
    files = [
        _PROJECT_ROOT / "src" / "candles" / "application" / "sync" / "use_cases.py",
        _PROJECT_ROOT / "src" / "candles" / "application" / "repair" / "use_cases.py",
        _PROJECT_ROOT
        / "src"
        / "candles"
        / "application"
        / "bootstrap"
        / "use_cases.py",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert 'error_type="unexpected_error"' not in text, (
            f"{path.name} still has hardcoded error_type='unexpected_error'"
        )
