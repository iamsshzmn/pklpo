from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.features.infrastructure.quality_adapter import SQLAlchemyQualityPipelineRunner
from src.features.ports.quality import QualityReportProtocol


@dataclass
class _FakeReport:
    summary_data: dict[str, int]

    def summary(self) -> dict[str, int]:
        return self.summary_data


@pytest.mark.asyncio
async def test_sqlalchemy_quality_pipeline_runner_returns_report_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeBeginContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    class _FakeEngine:
        def begin(self) -> _FakeBeginContext:
            return _FakeBeginContext()

    fake_engine = _FakeEngine()
    fake_report = _FakeReport({"total": 1, "ok": 1, "warn": 0, "critical": 0})
    captured: dict[str, Any] = {}

    async def _fake_run_quality_pipeline(
        pool: Any,
        *,
        send_alerts: bool = True,
        alert_cooldown_minutes: int = 30,
    ) -> tuple[_FakeReport, dict[str, int]]:
        captured["pool"] = pool
        async with pool.acquire() as connection:
            captured["connection"] = connection
        captured["pool"] = pool
        captured["send_alerts"] = send_alerts
        captured["alert_cooldown_minutes"] = alert_cooldown_minutes
        return fake_report, {"checked": 1, "sent": 0, "suppressed": 1}

    monkeypatch.setattr(
        "src.features.infrastructure.quality_adapter.run_quality_pipeline",
        _fake_run_quality_pipeline,
    )

    report, alert_stats = await SQLAlchemyQualityPipelineRunner()(
        fake_engine,
        send_alerts=False,
        alert_cooldown_minutes=15,
    )

    assert isinstance(report, QualityReportProtocol)
    assert report.summary() == {"total": 1, "ok": 1, "warn": 0, "critical": 0}
    assert alert_stats == {"checked": 1, "sent": 0, "suppressed": 1}
    assert hasattr(captured["pool"], "acquire")
    assert hasattr(captured["connection"], "fetch")
    assert hasattr(captured["connection"], "execute")
    assert hasattr(captured["connection"], "executemany")
    assert captured["send_alerts"] is False
    assert captured["alert_cooldown_minutes"] == 15
