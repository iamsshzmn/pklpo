"""Cross-cutting error-type taxonomy for structured telemetry.

Defines a low-cardinality ``ErrorType`` enum and a ``classify_error_type``
helper that maps an arbitrary exception to one of its values.  Application
and infrastructure layers import from here (or from the facade
``src.pklpo_platform.observability``) instead of hard-coding string literals.

Allowed error-type values (kept in sync with the Grafana Error Events panel
filter ``error_type != "-"``):

  db_error          — asyncpg / SQLAlchemy connection / query failure
  api_error         — remote API transient error (5xx, connection reset…)
  timeout_error     — fetch / connect / read timeout
  rate_limit_error  — OKX HTTP 429 / "Too Many Requests" / code 50011
  validation_error  — input shape, missing columns, domain constraint
  eligibility_error — candle coverage / eligibility gate blocked pipeline
  data_quality_error — NaN flood, invalid rows, data-integrity check
  permission_error  — auth / ACL denial (403, credentials)
  lock_conflict     — distributed lock already held
  unexpected_error  — fallback for unclassified exceptions
"""

from __future__ import annotations

import socket
from enum import StrEnum

try:
    import asyncpg as _asyncpg  # type: ignore[import]
except ImportError:  # pragma: no cover
    _asyncpg = None

try:
    from sqlalchemy import exc as _sa_exc  # type: ignore[import]
except ImportError:  # pragma: no cover
    _sa_exc = None


class ErrorType(StrEnum):
    """Low-cardinality error-type values for structured telemetry fields.

    Inherits from ``str`` so values compare equal to their string literals and
    serialise transparently in JSON / log ``extra`` dicts.  Compatible with
    Python 3.10+ (equivalent to ``StrEnum`` introduced in 3.11).
    """

    DB_ERROR = "db_error"
    API_ERROR = "api_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    VALIDATION_ERROR = "validation_error"
    ELIGIBILITY_ERROR = "eligibility_error"
    DATA_QUALITY_ERROR = "data_quality_error"
    PERMISSION_ERROR = "permission_error"
    LOCK_CONFLICT = "lock_conflict"
    UNEXPECTED_ERROR = "unexpected_error"

    def __str__(self) -> str:  # match StrEnum behaviour on Python 3.10
        return self.value


# ── classification tables ─────────────────────────────────────────────────────

_TIMEOUT_CLASS_NAMES: frozenset[str] = frozenset(
    {
        "TimeoutError",
        "RequestTimeout",
        "ClientTimeoutError",
        "ConnectTimeoutError",
        "ReadTimeout",
        "ServerTimeoutError",
        "TimeoutException",
        "asyncio.TimeoutError",
    }
)

_RATE_LIMIT_CLASS_NAMES: frozenset[str] = frozenset(
    {
        "RateLimitExceeded",
        "DDoSProtection",
        "TooManyRequests",
    }
)

_RATE_LIMIT_MARKERS: tuple[str, ...] = (
    "429",
    "too many requests",
    "50011",
    "rate limit",
    "rate limited",
)

_TIMEOUT_MARKERS: tuple[str, ...] = (
    "timeout",
    "timed out",
    "request timed out",
    "connect timeout",
    "read timeout",
)

_API_TRANSIENT_MARKERS: tuple[str, ...] = (
    "5xx",
    "temporarily",
    "temporary",
    "connection reset",
    "service unavailable",
)

_DB_TRANSIENT_MARKERS: tuple[str, ...] = (
    "connection is closed",
    "connect call failed",
    "name or service not known",
    "temporary failure in name resolution",
    "connection refused",
    "database connection invalidated",
)

_DB_TRANSIENT_ERRNOS: frozenset[int] = frozenset({111, -2, 11001})


# ── public API ────────────────────────────────────────────────────────────────


def classify_error_type(error: BaseException) -> str:
    """Return the ``ErrorType`` string for *error*.

    Walks the full exception chain (``__cause__`` / ``__context__``) so that
    wrapped exceptions are classified correctly.  Returns
    ``ErrorType.UNEXPECTED_ERROR`` when no rule matches.
    """
    for exc in _iter_chain(error):
        name = type(exc).__name__
        msg = str(exc).lower()

        # ── DB outage ────────────────────────────────────────────────────────
        if isinstance(exc, (ConnectionError, ConnectionRefusedError, socket.gaierror)):
            return ErrorType.DB_ERROR
        if _sa_exc is not None and isinstance(
            exc, (_sa_exc.OperationalError, _sa_exc.InterfaceError)
        ):
            return ErrorType.DB_ERROR
        if (
            _sa_exc is not None
            and isinstance(exc, _sa_exc.DBAPIError)
            and getattr(exc, "connection_invalidated", False)
        ):
            return ErrorType.DB_ERROR
        if _asyncpg is not None and isinstance(
            exc,
            (
                _asyncpg.PostgresConnectionError,
                _asyncpg.ConnectionDoesNotExistError,
                _asyncpg.InterfaceError,
            ),
        ):
            return ErrorType.DB_ERROR
        if isinstance(exc, OSError):
            if getattr(exc, "errno", None) in _DB_TRANSIENT_ERRNOS:
                return ErrorType.DB_ERROR
            if any(m in msg for m in _DB_TRANSIENT_MARKERS):
                return ErrorType.DB_ERROR
        if any(m in msg for m in _DB_TRANSIENT_MARKERS):
            return ErrorType.DB_ERROR

        # ── OKX / exchange rate-limit ────────────────────────────────────────
        if name in _RATE_LIMIT_CLASS_NAMES or any(m in msg for m in _RATE_LIMIT_MARKERS):
            return ErrorType.RATE_LIMIT_ERROR

        # ── Timeout ──────────────────────────────────────────────────────────
        if name in _TIMEOUT_CLASS_NAMES or any(m in msg for m in _TIMEOUT_MARKERS):
            return ErrorType.TIMEOUT_ERROR

        # ── Generic transient API error ──────────────────────────────────────
        if any(m in msg for m in _API_TRANSIENT_MARKERS):
            return ErrorType.API_ERROR

    return ErrorType.UNEXPECTED_ERROR


# ── internal helpers ──────────────────────────────────────────────────────────


def _iter_chain(error: BaseException) -> list[BaseException]:
    """Walk the exception chain, guarding against cycles."""
    chain: list[BaseException] = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain
