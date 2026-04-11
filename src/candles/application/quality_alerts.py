"""
Alert dispatch for data quality checks.
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import UTC, datetime, timedelta
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from src.alerts.slack_webhook import create_slack_notifier

from ..domain.quality import CheckResult, QualityReport, Severity

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

_ALERT_CACHE: dict[str, datetime] = {}


def _iter_violations(results: Iterable[CheckResult]) -> list[CheckResult]:
    return [r for r in results if r.severity in (Severity.WARN, Severity.CRITICAL)]


def _alert_key(result: CheckResult) -> str:
    return "|".join(
        [
            result.check_name,
            result.symbol or "all",
            result.timeframe or "na",
            str(result.severity),
        ]
    )


def _should_send(key: str, cooldown_minutes: int) -> bool:
    now = datetime.now(UTC)
    prev = _ALERT_CACHE.get(key)
    if prev is not None and (now - prev) < timedelta(minutes=cooldown_minutes):
        return False
    _ALERT_CACHE[key] = now
    return True


def _build_message(result: CheckResult) -> str:
    return (
        f"[DQ {result.severity.value.upper()}] "
        f"{result.check_name} "
        f"symbol={result.symbol or 'all'} "
        f"timeframe={result.timeframe or 'na'} "
        f"value={result.value} "
        f"meta={result.meta}"
    )


def _send_email(subject: str, body: str) -> bool:
    smtp_server = os.getenv("ALERT_EMAIL_SMTP_SERVER", "")
    smtp_port = int(os.getenv("ALERT_EMAIL_SMTP_PORT", "587"))
    smtp_user = os.getenv("ALERT_EMAIL_USERNAME", "")
    smtp_password = os.getenv("ALERT_EMAIL_PASSWORD", "")
    from_email = os.getenv("ALERT_EMAIL_FROM", "")
    to_emails_raw = os.getenv("ALERT_EMAIL_TO", "")

    recipients = [x.strip() for x in to_emails_raw.split(",") if x.strip()]
    if not all([smtp_server, smtp_user, smtp_password, from_email, recipients]):
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, recipients, msg.as_string())
        return True
    except Exception:
        logger.warning("Failed to send DQ email alert", exc_info=True)
        return False


def dispatch_quality_alerts(
    report: QualityReport,
    *,
    cooldown_minutes: int = 30,
) -> dict[str, int]:
    """
    Send warn/critical alerts to configured channels.

    Env controls:
    - SLACK_WEBHOOK_URL for Slack
    - ALERT_EMAIL_* for SMTP email
    """
    violations = _iter_violations(report.results)
    if not violations:
        return {"checked": 0, "sent": 0, "suppressed": 0}

    slack = create_slack_notifier()
    sent = 0
    suppressed = 0

    for result in violations:
        key = _alert_key(result)
        if not _should_send(key, cooldown_minutes):
            suppressed += 1
            continue

        msg = _build_message(result)
        logger.warning(msg)

        slack_ok = bool(slack.send_message(msg)) if slack else False
        email_ok = _send_email(subject=f"DQ {result.severity.value}: {result.check_name}", body=msg)
        if slack_ok or email_ok:
            sent += 1

    return {"checked": len(violations), "sent": sent, "suppressed": suppressed}
