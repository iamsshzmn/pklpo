"""
Phase-1 gate tests: duplicate detection + quality alerts wiring.

Covers:
- run_all_checks() includes check_duplicates_1m
- run_quality_pipeline() calls dispatch_quality_alerts when send_alerts=True
- dispatch_quality_alerts fires on CRITICAL severity
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.market_meta_backup.application.quality_checks import run_all_checks
from src.market_meta_backup.application.quality_pipeline import run_quality_pipeline
from src.market_meta_backup.domain.quality import CheckResult, QualityReport, Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(rows_by_query: dict | None = None) -> MagicMock:
    """Build a minimal pool mock whose conn.fetch returns empty lists by default."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.executemany = AsyncMock()

    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    return pool


# ---------------------------------------------------------------------------
# Р‘Р»РѕРє 2: duplicate detection wired into run_all_checks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_all_checks_includes_duplicate_detection():
    """run_all_checks must call check_duplicates_1m and include results."""
    pool = _make_pool()

    with patch(
        "src.candles.application.quality_checks.check_duplicates_1m",
        new_callable=AsyncMock,
    ) as mock_dup:
        mock_dup.return_value = [
            CheckResult(
                check_name="duplicate_rate_1m",
                severity=Severity.OK,
                symbol="BTC-USDT-SWAP",
                timeframe="1m",
                value=0.0,
            )
        ]
        report = await run_all_checks(pool)

    mock_dup.assert_called_once_with(pool)
    check_names = [r.check_name for r in report.results]
    assert "duplicate_rate_1m" in check_names


# ---------------------------------------------------------------------------
# Р‘Р»РѕРє 2: dispatch_quality_alerts fires when send_alerts=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_quality_pipeline_dispatches_alerts_on_violation():
    """run_quality_pipeline must call dispatch when there are WARN/CRITICAL results."""
    pool = _make_pool()
    critical_result = CheckResult(
        check_name="freshness",
        severity=Severity.CRITICAL,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        value=20.0,
    )

    with (
        patch(
            "src.candles.application.quality_pipeline.run_all_checks",
            new_callable=AsyncMock,
        ) as mock_checks,
        patch(
            "src.candles.application.quality_pipeline.QualityMetricsRepository"
        ) as MockRepo,
        patch(
            "src.candles.application.quality_pipeline.dispatch_quality_alerts"
        ) as mock_dispatch,
        patch("src.candles.application.quality_pipeline.push_quality_metrics"),
    ):
        report = QualityReport()
        report.extend([critical_result])
        mock_checks.return_value = report

        repo_instance = AsyncMock()
        repo_instance.save_results = AsyncMock()
        MockRepo.return_value = repo_instance

        mock_dispatch.return_value = {"checked": 1, "sent": 1, "suppressed": 0}

        returned_report, alert_stats = await run_quality_pipeline(
            pool, send_alerts=True
        )

    mock_dispatch.assert_called_once_with(report, cooldown_minutes=30)
    assert alert_stats["sent"] == 1


@pytest.mark.asyncio
async def test_run_quality_pipeline_skips_dispatch_when_send_alerts_false():
    """No alerts should fire when send_alerts=False."""
    pool = _make_pool()

    with (
        patch(
            "src.candles.application.quality_pipeline.run_all_checks",
            new_callable=AsyncMock,
        ) as mock_checks,
        patch(
            "src.candles.application.quality_pipeline.QualityMetricsRepository"
        ) as MockRepo,
        patch(
            "src.candles.application.quality_pipeline.dispatch_quality_alerts"
        ) as mock_dispatch,
        patch("src.candles.application.quality_pipeline.push_quality_metrics"),
    ):
        mock_checks.return_value = QualityReport()
        repo_instance = AsyncMock()
        repo_instance.save_results = AsyncMock()
        MockRepo.return_value = repo_instance

        await run_quality_pipeline(pool, send_alerts=False)

    mock_dispatch.assert_not_called()


# ---------------------------------------------------------------------------
# Prometheus push is called after saving results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_quality_pipeline_calls_prometheus_push():
    """push_quality_metrics must be invoked unconditionally after save."""
    pool = _make_pool()

    with (
        patch(
            "src.candles.application.quality_pipeline.run_all_checks",
            new_callable=AsyncMock,
        ) as mock_checks,
        patch(
            "src.candles.application.quality_pipeline.QualityMetricsRepository"
        ) as MockRepo,
        patch(
            "src.candles.application.quality_pipeline.dispatch_quality_alerts",
            return_value={"checked": 0, "sent": 0, "suppressed": 0},
        ),
        patch(
            "src.candles.application.quality_pipeline.push_quality_metrics"
        ) as mock_push,
    ):
        mock_checks.return_value = QualityReport()
        repo_instance = AsyncMock()
        repo_instance.save_results = AsyncMock()
        MockRepo.return_value = repo_instance

        await run_quality_pipeline(pool, send_alerts=True)

    mock_push.assert_called_once()
