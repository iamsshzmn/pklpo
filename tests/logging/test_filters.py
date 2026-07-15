"""Tests for SensitiveDataFilter in src/logging/filters.py.

Host-runnable: only imports from stdlib and the filters module directly.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_filters() -> ModuleType:
    """Load filters.py directly (avoids pulling logging_config side-effects)."""
    path = _PROJECT_ROOT / "src" / "logging" / "filters.py"
    spec = importlib.util.spec_from_file_location("tests.logging._filters", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── T8.1: URL credential masking ─────────────────────────────────────────────


def test_sensitive_filter_masks_db_url_credentials() -> None:
    """postgresql://user:pass@host — credentials must be masked, host preserved."""
    m = _load_filters()
    f = m.SensitiveDataFilter()
    record = logging.LogRecord(
        "test",
        logging.INFO,
        "",
        0,
        "connecting to postgresql://admin:s3cr3t@db.internal:5432/pklpo",
        (),
        None,
    )
    f.filter(record)
    assert "s3cr3t" not in record.msg, "password still in message after filter"
    assert "admin" not in record.msg, "username still in message after filter"
    assert "db.internal" in record.msg, "host should be preserved"
    assert m.SensitiveDataFilter.MASK in record.msg, "MASK not present in message"


def test_sensitive_filter_masks_redis_url_credentials() -> None:
    """redis://:pass@host — password-only URL form."""
    m = _load_filters()
    f = m.SensitiveDataFilter()
    record = logging.LogRecord(
        "test",
        logging.INFO,
        "",
        0,
        "cache url=redis://:mypassword@cache:6379/0",
        (),
        None,
    )
    f.filter(record)
    assert "mypassword" not in record.msg
    assert "cache" in record.msg  # host preserved


def test_sensitive_filter_masks_url_with_special_chars_in_password() -> None:
    """URL credentials with special characters in the password."""
    m = _load_filters()
    f = m.SensitiveDataFilter()
    msg = "dsn=postgresql://svc_user:P%40ss!word@pg:5432/db"
    record = logging.LogRecord("test", logging.INFO, "", 0, msg, (), None)
    f.filter(record)
    assert "P%40ss" not in record.msg
    assert "pg" in record.msg


def test_sensitive_filter_leaves_url_without_credentials_unchanged() -> None:
    """URL with no credentials must pass through untouched."""
    m = _load_filters()
    f = m.SensitiveDataFilter()
    msg = "fetching https://api.example.com/data"
    record = logging.LogRecord("test", logging.INFO, "", 0, msg, (), None)
    f.filter(record)
    assert record.msg == msg, f"URL without credentials was mutated: {record.msg!r}"


# ── Pre-existing patterns still work ─────────────────────────────────────────


def test_sensitive_filter_masks_password_kwarg() -> None:
    m = _load_filters()
    f = m.SensitiveDataFilter()
    record = logging.LogRecord(
        "test",
        logging.INFO,
        "",
        0,
        "login password=hunter2 ok",
        (),
        None,
    )
    f.filter(record)
    assert "hunter2" not in record.msg


def test_sensitive_filter_masks_api_key() -> None:
    m = _load_filters()
    f = m.SensitiveDataFilter()
    record = logging.LogRecord(
        "test",
        logging.INFO,
        "",
        0,
        "api_key=sk-abc123 used",
        (),
        None,
    )
    f.filter(record)
    assert "sk-abc123" not in record.msg


def test_url_credential_pattern_in_default_patterns() -> None:
    """Ensure the URL-credential pattern is present in DEFAULT_PATTERNS."""
    m = _load_filters()
    patterns = m.SensitiveDataFilter.DEFAULT_PATTERNS
    assert any("://" in p for p in patterns), (
        "No URL-credential pattern found in DEFAULT_PATTERNS"
    )
