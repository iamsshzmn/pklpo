from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.features.application import features_calc_short_service as service


@dataclass
class _FakeExecuteResult:
    value: Any

    def scalar(self) -> Any:
        return self.value


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[Any, dict[str, Any] | None]] = []

    async def execute(self, stmt: Any, params: dict[str, Any] | None = None) -> _FakeExecuteResult:
        self.executed.append((stmt, params))
        return _FakeExecuteResult(1_710_000_000_000)


class _FakeAsyncSession:
    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.session = _FakeSession()

    async def __aenter__(self) -> _FakeSession:
        return self.session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


@dataclass
class _FakeEngine:
    database_url: str
    disposed: bool = False

    async def dispose(self) -> None:
        self.disposed = True


@dataclass
class _FakeReport:
    totals: dict[str, int]

    def summary(self) -> dict[str, int]:
        return self.totals


class _FakeQualityRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, bool, int]] = []

    async def __call__(
        self,
        pool: Any,
        *,
        send_alerts: bool = True,
        alert_cooldown_minutes: int = 30,
    ) -> tuple[_FakeReport, dict[str, int]]:
        self.calls.append((pool, send_alerts, alert_cooldown_minutes))
        return _FakeReport({"total": 7, "ok": 4, "warn": 2, "critical": 1}), {
            "checked": 7,
            "sent": 1,
            "suppressed": 6,
        }


@pytest.mark.asyncio
async def test_run_features_calc_short_validate_uses_quality_runner_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = _FakeEngine("sqlite:///:memory:")
    fake_runner = _FakeQualityRunner()

    monkeypatch.setattr(service, "create_async_engine", lambda *args, **kwargs: fake_engine)
    monkeypatch.setattr(service, "AsyncSession", _FakeAsyncSession)
    monkeypatch.setattr(service, "_push_prometheus_metrics", lambda **kwargs: True)

    result = await service.run_features_calc_short_validate(
        database_url="sqlite:///:memory:",
        quality_enabled=True,
        quality_send_alerts=False,
        quality_alert_cooldown=12,
        quality_pipeline_runner=fake_runner,
    )

    assert fake_runner.calls == [(fake_engine, False, 12)]
    assert result["quality_total_checks"] == 7
    assert result["quality_ok"] == 4
    assert result["quality_warn"] == 2
    assert result["quality_critical"] == 1
    assert result["alerts_checked"] == 7
    assert result["alerts_sent"] == 1
    assert result["alerts_suppressed"] == 6
    assert result["prometheus_push_succeeded"] is True
    assert set(result["lag_seconds"]) == {"1m", "5m"}
