"""
End-to-end quality pipeline: checks -> store -> alerts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ..infrastructure.quality_repository import QualityMetricsRepository
from ..observability.prometheus import push_quality_metrics
from .quality_alerts import dispatch_quality_alerts
from .quality_checks import run_all_checks

if TYPE_CHECKING:
    from ..domain.quality import QualityReport


class QualityPoolPort(Protocol):
    def acquire(self): ...


async def run_quality_pipeline(
    pool: QualityPoolPort,
    *,
    send_alerts: bool = True,
    alert_cooldown_minutes: int = 30,
) -> tuple[QualityReport, dict[str, int]]:
    """
    Run all quality checks, persist metrics, and optionally dispatch alerts.
    """
    report = await run_all_checks(pool)
    repo = QualityMetricsRepository(pool)
    await repo.save_results(report.results)

    push_quality_metrics(report)

    alert_stats = {"checked": 0, "sent": 0, "suppressed": 0}
    if send_alerts:
        alert_stats = dispatch_quality_alerts(
            report,
            cooldown_minutes=alert_cooldown_minutes,
        )

    return report, alert_stats
