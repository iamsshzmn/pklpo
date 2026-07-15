"""T4.1 (observability-reliability-track): domain logging layer boundary.

``src/candles/domain`` is pure business logic and MUST NOT import the candles
``infrastructure`` package. Previously ``validators.py`` / ``risk_limits.py``
did ``from ..infrastructure.logging_config import get_logger``, which (via
``infrastructure.__init__`` → ``adapters`` → ``ccxt_okx_adapter``) dragged the
whole exchange-adapter stack and an import-time ``auto_configure()`` into the
domain layer. The fix routes logging through the cross-cutting ``src.logging``.
"""

from __future__ import annotations

import sys

import pytest


def _purge(prefixes: list[str]) -> None:
    for name in list(sys.modules):
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            del sys.modules[name]


def test_risk_limits_loads_without_pulling_infrastructure() -> None:
    """Bulletproof, runtime-only discriminator (no third-party deps needed).

    ``risk_limits`` is imported by ``domain/__init__`` before any module that
    needs optional third-party deps. Under the old code its module-level
    ``from ..infrastructure...`` raised (adapters → ccxt), so the module never
    finished loading. With the fix it loads cleanly and keeps its logger name.
    """
    _purge(["src.candles.domain", "src.candles.infrastructure"])

    # Tolerate unrelated optional deps pulled by *other* domain modules during
    # package __init__ (e.g. pydantic via sync_config); only the layering
    # invariant on risk_limits matters here.
    try:
        import src.candles.domain.risk_limits  # noqa: F401
    except ModuleNotFoundError:
        pass

    module = sys.modules.get("src.candles.domain.risk_limits")
    assert module is not None, (
        "risk_limits must finish importing without pulling candles infrastructure"
    )
    # Behaviour-preserving: old code routed through infrastructure's
    # get_logger("risk_limits") -> src.logging.get_logger("market_meta.risk_limits"),
    # which the project logger namespaces under "pklpo.".
    assert module.logger.name == "pklpo.market_meta.risk_limits"
    assert "src.candles.infrastructure" not in sys.modules
    assert "src.candles.infrastructure.logging_config" not in sys.modules


def test_domain_modules_avoid_infrastructure_and_keep_logger_names() -> None:
    """Full acceptance check; needs the project dependency set (CI)."""
    pytest.importorskip("pydantic")

    _purge(["src.candles.domain", "src.candles.infrastructure"])

    import src.candles.domain.risk_limits as risk_limits
    import src.candles.domain.validators as validators

    assert validators.logger.name == "pklpo.market_meta.validators"
    assert risk_limits.logger.name == "pklpo.market_meta.risk_limits"
    assert "src.candles.infrastructure" not in sys.modules
    assert "src.candles.infrastructure.logging_config" not in sys.modules
    assert not any(m.endswith("candles.observability.prometheus") for m in sys.modules)
