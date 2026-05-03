from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from src.config.settings import ObservabilitySettings
from src.market_meta_backup.application.quality_alerts import dispatch_quality_alerts
from src.market_meta_backup.application.quality_checks import check_duplicates_1m
from src.market_meta_backup.application.quality_pipeline import run_quality_pipeline
from src.market_meta_backup.domain.quality import CheckResult, QualityReport, Severity


class _FakePool:
    def __init__(self, rows):
        self._rows = rows

    @asynccontextmanager
    async def acquire(self):
        conn = AsyncMock()
        conn.fetch.return_value = self._rows
        yield conn


def test_observability_settings_defaults(monkeypatch):
    monkeypatch.delenv("OBSERVABILITY_PROMETHEUS_ENABLED", raising=False)
    monkeypatch.delenv("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", raising=False)
    monkeypatch.delenv("OBSERVABILITY_METRICS_PREFIX", raising=False)
    monkeypatch.delenv("OBSERVABILITY_JOB_NAME", raising=False)
    s = ObservabilitySettings()
    assert s.prometheus_enabled is False
    assert s.prometheus_pushgateway_url == ""
    assert s.metrics_prefix == "pklpo"
    assert s.job_name == "features_pipeline"


@pytest.mark.asyncio
async def test_check_duplicates_1m():
    rows = [
        {
            "symbol": "BTC-USDT-SWAP",
            "total_bars": 100,
            "duplicate_rows": 2,
            "duplicate_rate_pct": 2.0,
        }
    ]
    pool = _FakePool(rows)
    results = await check_duplicates_1m(pool, window_minutes=60)
    assert len(results) == 1
    assert results[0].check_name == "duplicate_rate_1m"
    assert results[0].severity in {Severity.WARN, Severity.CRITICAL}


def test_dispatch_quality_alerts_no_violations():
    report = QualityReport(
        results=[
            CheckResult(
                check_name="freshness",
                severity=Severity.OK,
                symbol="BTC-USDT-SWAP",
                timeframe="1m",
                value=1.0,
            )
        ]
    )
    stats = dispatch_quality_alerts(report)
    assert stats["checked"] == 0
    assert stats["sent"] == 0


@pytest.mark.asyncio
async def test_run_quality_pipeline_persists_and_dispatches(monkeypatch):
    report = QualityReport(
        results=[
            CheckResult(
                check_name="duplicate_rate_1m",
                severity=Severity.WARN,
                symbol="BTC-USDT-SWAP",
                timeframe="1m",
                value=1.5,
            )
        ]
    )

    run_all_checks_mock = AsyncMock(return_value=report)
    monkeypatch.setattr(
        "src.candles.application.quality_pipeline.run_all_checks",
        run_all_checks_mock,
    )

    save_results_mock = AsyncMock(return_value=1)

    class _RepoStub:
        def __init__(self, _pool) -> None:
            self.pool = _pool

        async def save_results(self, results):
            return await save_results_mock(results)

    monkeypatch.setattr(
        "src.candles.application.quality_pipeline.QualityMetricsRepository",
        _RepoStub,
    )

    def _dispatch(_report, cooldown_minutes):
        return {"checked": 1, "sent": 1, "suppressed": 0}

    monkeypatch.setattr(
        "src.candles.application.quality_pipeline.dispatch_quality_alerts",
        _dispatch,
    )

    pool = object()
    out_report, alert_stats = await run_quality_pipeline(
        pool,
        send_alerts=True,
        alert_cooldown_minutes=15,
    )

    assert out_report is report
    run_all_checks_mock.assert_awaited_once_with(pool)
    save_results_mock.assert_awaited_once()
    assert alert_stats == {"checked": 1, "sent": 1, "suppressed": 0}
