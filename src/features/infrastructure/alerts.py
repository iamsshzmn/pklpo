"""
Airflow Alerting Module (FEAT-002).

This module provides callbacks and utilities for monitoring and alerting
in Airflow DAGs. It supports multiple notification channels: Email, Slack,
and custom handlers.

Features:
- Email notifications on failure/success
- Slack webhook integration
- SLA breach alerts
- Custom alert formatting
- Context-aware messages with task details
"""

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertContext:
    """Structured alert context."""

    dag_id: str
    task_id: str
    execution_date: str
    run_id: str
    try_number: int
    log_url: str | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    level: AlertLevel = AlertLevel.ERROR

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["level"] = self.level.value
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# =============================================================================
# OBSERVER PATTERN FOR ALERTS (Task 13)
# =============================================================================

# Severity ordering for routing (higher = more severe)
_LEVEL_ORDER: dict[AlertLevel, int] = {
    AlertLevel.INFO: 0,
    AlertLevel.WARNING: 1,
    AlertLevel.ERROR: 2,
    AlertLevel.CRITICAL: 3,
}


class AlertObserver:
    """
    Abstract base for alert observers.

    Task 13: OCP-compliant alert handling via Observer pattern.
    Subclass this to add new notification channels without modifying existing code.

    Each observer can specify a ``min_level`` — alerts below that level
    are silently skipped by the dispatcher.
    """

    min_level: AlertLevel = AlertLevel.INFO

    def notify(self, alert_ctx: AlertContext) -> bool:
        """
        Handle the alert.

        Args:
            alert_ctx: Alert context

        Returns:
            True if notification was sent successfully
        """
        raise NotImplementedError


class AlertDispatcher:
    """
    Central dispatcher for alert observers.

    Task 13: Observer pattern for extensible alert channels.

    Usage:
        dispatcher = AlertDispatcher()
        dispatcher.subscribe(EmailAlertObserver())
        dispatcher.subscribe(SlackAlertObserver())

        # Later, when alert occurs:
        dispatcher.notify_all(alert_ctx)
    """

    _instance: "AlertDispatcher | None" = None
    _observers: list[AlertObserver]

    def __init__(self) -> None:
        self._observers = []

    @classmethod
    def get_instance(cls) -> "AlertDispatcher":
        """Singleton access."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, observer: AlertObserver) -> "AlertDispatcher":
        """Add an observer (fluent interface)."""
        if observer not in self._observers:
            self._observers.append(observer)
        return self

    def unsubscribe(self, observer: AlertObserver) -> "AlertDispatcher":
        """Remove an observer."""
        if observer in self._observers:
            self._observers.remove(observer)
        return self

    def clear(self) -> "AlertDispatcher":
        """Remove all observers."""
        self._observers.clear()
        return self

    def notify_all(self, alert_ctx: AlertContext) -> dict[str, bool]:
        """
        Notify observers whose ``min_level`` <= alert level.

        Severity order: INFO < WARNING < ERROR < CRITICAL.
        An observer with ``min_level=WARNING`` skips INFO alerts.

        Args:
            alert_ctx: Alert context

        Returns:
            Dict mapping observer class names to success status
        """
        alert_order = _LEVEL_ORDER.get(alert_ctx.level, 0)
        results: dict[str, bool] = {}
        for observer in self._observers:
            observer_name = observer.__class__.__name__
            if alert_order < _LEVEL_ORDER.get(observer.min_level, 0):
                continue
            try:
                success = observer.notify(alert_ctx)
                results[observer_name] = success
            except Exception as e:
                print(f"Observer {observer_name} failed: {e}")
                results[observer_name] = False
        return results

    def __len__(self) -> int:
        return len(self._observers)


class LogAlertObserver(AlertObserver):
    """Observer that logs alerts to stdout."""

    def notify(self, alert_ctx: AlertContext) -> bool:
        level_icons = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨",
        }
        icon = level_icons.get(alert_ctx.level, "📢")
        print(
            f"{icon} [{alert_ctx.level.value.upper()}] "
            f"{alert_ctx.dag_id}.{alert_ctx.task_id}: {alert_ctx.error_message or 'Alert'}"
        )
        return True


class EmailAlertObserver(AlertObserver):
    """Observer that sends email alerts (CRITICAL only by default)."""

    min_level = AlertLevel.CRITICAL

    def __init__(self, recipients: list[str] | None = None):
        self.recipients = recipients or os.getenv(
            "AIRFLOW_ALERT_EMAIL", "data-team@company.com"
        ).split(",")

    def notify(self, alert_ctx: AlertContext) -> bool:
        try:
            from airflow.utils.email import send_email

            html_content = format_failure_email(alert_ctx)
            subject = f"🚨 Airflow Alert: {alert_ctx.dag_id}.{alert_ctx.task_id}"
            send_email(to=self.recipients, subject=subject, html_content=html_content)
            return True
        except Exception as e:
            print(f"EmailAlertObserver failed: {e}")
            return False


class SlackAlertObserver(AlertObserver):
    """Observer that sends Slack alerts."""

    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")

    def notify(self, alert_ctx: AlertContext) -> bool:
        if not self.webhook_url:
            print("SlackAlertObserver: No webhook URL configured")
            return False
        return send_slack_alert(alert_ctx, self.webhook_url)


class TelegramAlertObserver(AlertObserver):
    """Observer that sends alerts via Telegram Bot API (WARNING+ by default).

    Env vars:
        TELEGRAM_BOT_TOKEN: Bot token from @BotFather
        TELEGRAM_CHAT_ID: Target chat/group ID
    """

    min_level = AlertLevel.WARNING

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

    def notify(self, alert_ctx: AlertContext) -> bool:
        if not self.bot_token or not self.chat_id:
            print("TelegramAlertObserver: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
            return False
        return send_telegram_alert(alert_ctx, self.bot_token, self.chat_id)


# Global dispatcher instance
_alert_dispatcher: AlertDispatcher | None = None


def get_alert_dispatcher() -> AlertDispatcher:
    """Get the global alert dispatcher (lazy initialization).

    Default observers:
    - LogAlertObserver: always (all levels)
    - TelegramAlertObserver: if TELEGRAM_BOT_TOKEN is set (WARNING+)
    - EmailAlertObserver: if AIRFLOW_ALERT_EMAIL is set (CRITICAL only)
    """
    global _alert_dispatcher
    if _alert_dispatcher is None:
        _alert_dispatcher = AlertDispatcher()
        _alert_dispatcher.subscribe(LogAlertObserver())

        if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
            _alert_dispatcher.subscribe(TelegramAlertObserver())

        if os.getenv("AIRFLOW_ALERT_EMAIL"):
            _alert_dispatcher.subscribe(EmailAlertObserver())

    return _alert_dispatcher


def extract_alert_context(context: dict[str, Any]) -> AlertContext:
    """
    Extract alert context from Airflow context.

    Args:
        context: Airflow task instance context

    Returns:
        Structured alert context
    """
    task_instance = context.get("task_instance")
    dag = context.get("dag")

    # Calculate duration if task instance available
    duration_seconds = None
    if task_instance:
        start_date = task_instance.start_date
        end_date = task_instance.end_date or datetime.now()
        if start_date:
            duration_seconds = (end_date - start_date).total_seconds()

    # Extract error message
    error_message = None
    exception = context.get("exception")
    if exception:
        error_message = str(exception)
    elif context.get("reason"):
        error_message = context.get("reason")

    # Get log URL
    log_url = None
    if task_instance:
        try:
            log_url = task_instance.log_url
        except Exception:
            # log_url may not be available in all Airflow versions
            pass

    # Safely extract task_id
    task = context.get("task")
    task_id = task.task_id if task and hasattr(task, "task_id") else "unknown"

    # Safely extract try_number
    try_number = (
        task_instance.try_number
        if task_instance and hasattr(task_instance, "try_number")
        else 0
    )

    return AlertContext(
        dag_id=dag.dag_id if dag else "unknown",
        task_id=task_id,
        execution_date=str(context.get("execution_date", "unknown")),
        run_id=context.get("run_id", "unknown"),
        try_number=try_number,
        log_url=log_url,
        duration_seconds=duration_seconds,
        error_message=error_message,
        level=AlertLevel.ERROR,
    )


# ===============================================================================
# Email Callbacks
# ===============================================================================


def format_failure_email(alert_ctx: AlertContext) -> str:
    """
    Format failure email content.

    Args:
        alert_ctx: Alert context

    Returns:
        HTML email content
    """
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .header {{ background-color: #dc3545; color: white; padding: 10px; }}
            .content {{ padding: 20px; }}
            .info-table {{ border-collapse: collapse; width: 100%; }}
            .info-table td {{ padding: 8px; border: 1px solid #ddd; }}
            .info-table tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .error-box {{ background-color: #fff3cd; border: 1px solid #ffc107; padding: 10px; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>🚨 Airflow Task Failed</h2>
        </div>
        <div class="content">
            <h3>Task Failure Details</h3>
            <table class="info-table">
                <tr>
                    <td><strong>DAG ID</strong></td>
                    <td>{alert_ctx.dag_id}</td>
                </tr>
                <tr>
                    <td><strong>Task ID</strong></td>
                    <td>{alert_ctx.task_id}</td>
                </tr>
                <tr>
                    <td><strong>Execution Date</strong></td>
                    <td>{alert_ctx.execution_date}</td>
                </tr>
                <tr>
                    <td><strong>Run ID</strong></td>
                    <td>{alert_ctx.run_id}</td>
                </tr>
                <tr>
                    <td><strong>Try Number</strong></td>
                    <td>{alert_ctx.try_number}</td>
                </tr>
                <tr>
                    <td><strong>Duration</strong></td>
                    <td>{alert_ctx.duration_seconds:.2f}s</td>
                </tr>
            </table>

            {f'<div class="error-box"><strong>Error Message:</strong><br/><pre>{alert_ctx.error_message}</pre></div>' if alert_ctx.error_message else ''}

            {f'<p><a href="{alert_ctx.log_url}">View Logs</a></p>' if alert_ctx.log_url else ''}

            <p>This is an automated alert from Airflow.</p>
        </div>
    </body>
    </html>
    """


def email_failure_callback(context: dict[str, Any]) -> None:
    """
    Email callback for task failures.

    This callback is automatically invoked by Airflow when a task fails.
    It extracts context and formats an email notification.

    Args:
        context: Airflow context dictionary
    """
    from airflow.utils.email import send_email

    alert_ctx = extract_alert_context(context)

    # Get email configuration
    email_to = os.getenv("AIRFLOW_ALERT_EMAIL", "data-team@company.com").split(",")
    email_subject = f"🚨 Airflow Task Failed: {alert_ctx.dag_id}.{alert_ctx.task_id}"

    # Format email content
    html_content = format_failure_email(alert_ctx)

    # Send email
    try:
        send_email(to=email_to, subject=email_subject, html_content=html_content)
        print(f"✅ Failure email sent to {', '.join(email_to)}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def email_sla_miss_callback(context: dict[str, Any]) -> None:
    """
    Email callback for SLA misses.

    Args:
        context: Airflow context dictionary
    """
    from airflow.utils.email import send_email

    alert_ctx = extract_alert_context(context)
    alert_ctx.level = AlertLevel.WARNING
    alert_ctx.error_message = "Task exceeded SLA threshold"

    # Get email configuration
    email_to = os.getenv("AIRFLOW_ALERT_EMAIL", "data-team@company.com").split(",")
    email_subject = f"⚠️ Airflow SLA Miss: {alert_ctx.dag_id}.{alert_ctx.task_id}"

    # Format email content (reuse failure template)
    html_content = format_failure_email(alert_ctx).replace("Task Failed", "SLA Miss")

    # Send email
    try:
        send_email(to=email_to, subject=email_subject, html_content=html_content)
        print(f"✅ SLA miss email sent to {', '.join(email_to)}")
    except Exception as e:
        print(f"❌ Failed to send SLA email: {e}")


# ===============================================================================
# Slack Callbacks
# ===============================================================================


def format_slack_message(alert_ctx: AlertContext) -> dict[str, Any]:
    """
    Format Slack message with blocks.

    Args:
        alert_ctx: Alert context

    Returns:
        Slack message payload
    """
    # Color based on level
    color_map = {
        AlertLevel.INFO: "#36a64f",
        AlertLevel.WARNING: "#ff9800",
        AlertLevel.ERROR: "#dc3545",
        AlertLevel.CRITICAL: "#8b0000",
    }
    color = color_map.get(alert_ctx.level, "#dc3545")

    # Icon based on level
    icon_map = {
        AlertLevel.INFO: "✅",
        AlertLevel.WARNING: "⚠️",
        AlertLevel.ERROR: "❌",
        AlertLevel.CRITICAL: "🚨",
    }
    icon = icon_map.get(alert_ctx.level, "❌")

    # Build message
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{icon} Airflow Task Alert"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*DAG:*\n`{alert_ctx.dag_id}`"},
                {"type": "mrkdwn", "text": f"*Task:*\n`{alert_ctx.task_id}`"},
                {
                    "type": "mrkdwn",
                    "text": f"*Execution Date:*\n{alert_ctx.execution_date}",
                },
                {"type": "mrkdwn", "text": f"*Try Number:*\n{alert_ctx.try_number}"},
            ],
        },
    ]

    # Add duration if available
    if alert_ctx.duration_seconds is not None:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Duration:* {alert_ctx.duration_seconds:.2f}s",
                },
            }
        )

    # Add error message if available
    if alert_ctx.error_message:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:*\n```{alert_ctx.error_message[:500]}```",
                },
            }
        )

    # Add log link if available
    if alert_ctx.log_url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Logs"},
                        "url": alert_ctx.log_url,
                        "style": "danger",
                    }
                ],
            }
        )

    return {"attachments": [{"color": color, "blocks": blocks}]}


def send_slack_alert(alert_ctx: AlertContext, webhook_url: str | None = None) -> bool:
    """
    Send alert to Slack via webhook.

    Args:
        alert_ctx: Alert context
        webhook_url: Slack webhook URL (or read from env)

    Returns:
        True if successful, False otherwise
    """
    import requests  # type: ignore[import-untyped]

    # Get webhook URL
    if webhook_url is None:
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print("⚠️ No Slack webhook URL configured (SLACK_WEBHOOK_URL)")
        return False

    # Format message
    payload = format_slack_message(alert_ctx)

    # Send to Slack
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        print("✅ Slack alert sent successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to send Slack alert: {e}")
        return False


def slack_failure_callback(context: dict[str, Any]) -> None:
    """
    Slack callback for task failures.

    Args:
        context: Airflow context dictionary
    """
    alert_ctx = extract_alert_context(context)
    send_slack_alert(alert_ctx)


def slack_sla_miss_callback(context: dict[str, Any]) -> None:
    """
    Slack callback for SLA misses.

    Args:
        context: Airflow context dictionary
    """
    alert_ctx = extract_alert_context(context)
    alert_ctx.level = AlertLevel.WARNING
    alert_ctx.error_message = "Task exceeded SLA threshold"
    send_slack_alert(alert_ctx)


# ===============================================================================
# Telegram Callbacks
# ===============================================================================


def format_telegram_message(alert_ctx: AlertContext) -> str:
    """Format alert as Telegram MarkdownV2 message.

    Args:
        alert_ctx: Alert context

    Returns:
        Message text (HTML parse mode)
    """
    icon_map = {
        AlertLevel.INFO: "\u2705",       # green check
        AlertLevel.WARNING: "\u26a0\ufe0f",  # warning
        AlertLevel.ERROR: "\u274c",       # red cross
        AlertLevel.CRITICAL: "\U0001f6a8",  # siren
    }
    icon = icon_map.get(alert_ctx.level, "\u274c")

    lines = [
        f"{icon} <b>Airflow Alert [{alert_ctx.level.value.upper()}]</b>",
        "",
        f"<b>DAG:</b> <code>{_escape_html(alert_ctx.dag_id)}</code>",
        f"<b>Task:</b> <code>{_escape_html(alert_ctx.task_id)}</code>",
        f"<b>Run:</b> {_escape_html(alert_ctx.run_id)}",
        f"<b>Try:</b> {alert_ctx.try_number}",
    ]

    if alert_ctx.duration_seconds is not None:
        lines.append(f"<b>Duration:</b> {alert_ctx.duration_seconds:.1f}s")

    if alert_ctx.error_message:
        # Truncate long error messages for Telegram (4096 char limit)
        err = alert_ctx.error_message[:800]
        lines.append(f"\n<b>Error:</b>\n<pre>{_escape_html(err)}</pre>")

    if alert_ctx.log_url:
        lines.append(f'\n<a href="{alert_ctx.log_url}">View Logs</a>')

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def send_telegram_alert(
    alert_ctx: AlertContext,
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send alert via Telegram Bot API.

    Args:
        alert_ctx: Alert context
        bot_token: Bot token (or read from TELEGRAM_BOT_TOKEN env)
        chat_id: Chat ID (or read from TELEGRAM_CHAT_ID env)

    Returns:
        True if sent successfully
    """
    import requests

    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat:
        print("No Telegram credentials configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        return False

    text = format_telegram_message(alert_ctx)
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False


def telegram_failure_callback(context: dict[str, Any]) -> None:
    """Telegram callback for task failures."""
    alert_ctx = extract_alert_context(context)
    send_telegram_alert(alert_ctx)


def telegram_sla_miss_callback(context: dict[str, Any]) -> None:
    """Telegram callback for SLA misses."""
    alert_ctx = extract_alert_context(context)
    alert_ctx.level = AlertLevel.WARNING
    alert_ctx.error_message = "Task exceeded SLA threshold"
    send_telegram_alert(alert_ctx)


# ===============================================================================
# Combined Callbacks
# ===============================================================================


def combined_failure_callback(context: dict[str, Any]) -> None:
    """
    Combined callback that sends alerts to both Email and Slack.

    Args:
        context: Airflow context dictionary
    """
    # Extract context once
    alert_ctx = extract_alert_context(context)

    print(f"🚨 Task failure detected: {alert_ctx.dag_id}.{alert_ctx.task_id}")
    print(f"   Alert context: {alert_ctx.to_json()}")

    # Send to both channels
    try:
        email_failure_callback(context)
    except Exception as e:
        print(f"❌ Email notification failed: {e}")

    try:
        slack_failure_callback(context)
    except Exception as e:
        print(f"❌ Slack notification failed: {e}")


def combined_sla_miss_callback(context: dict[str, Any]) -> None:
    """
    Combined callback for SLA misses that sends alerts to both channels.

    Args:
        context: Airflow context dictionary
    """
    # Extract context once
    alert_ctx = extract_alert_context(context)
    alert_ctx.level = AlertLevel.WARNING

    print(f"⚠️ SLA miss detected: {alert_ctx.dag_id}.{alert_ctx.task_id}")
    print(f"   Alert context: {alert_ctx.to_json()}")

    # Send to both channels
    try:
        email_sla_miss_callback(context)
    except Exception as e:
        print(f"❌ Email notification failed: {e}")

    try:
        slack_sla_miss_callback(context)
    except Exception as e:
        print(f"❌ Slack notification failed: {e}")


# ===============================================================================
# Success Callbacks (Optional)
# ===============================================================================


def success_callback(context: dict[str, Any]) -> None:
    """
    Optional success callback for critical DAGs.

    Args:
        context: Airflow context dictionary
    """
    alert_ctx = extract_alert_context(context)
    alert_ctx.level = AlertLevel.INFO
    alert_ctx.error_message = None

    print(f"✅ Task completed successfully: {alert_ctx.dag_id}.{alert_ctx.task_id}")

    # Only send Slack notification for success (not email)
    if os.getenv("SLACK_SUCCESS_NOTIFICATIONS", "false").lower() == "true":
        send_slack_alert(alert_ctx)


# ===============================================================================
# Utility Functions
# ===============================================================================


def test_email_alert() -> None:
    """Test email alerting configuration."""
    test_context = {
        "dag": type("obj", (object,), {"dag_id": "test_dag"}),
        "task": {"task_id": "test_task"},
        "execution_date": datetime.now(),
        "run_id": "test_run",
        "task_instance": type(
            "obj",
            (object,),
            {
                "try_number": 1,
                "start_date": datetime.now() - timedelta(seconds=10),
                "end_date": datetime.now(),
                "log_url": "http://localhost:8080/log",
            },
        )(),
        "exception": Exception("Test error message"),
    }

    print("🧪 Testing email alert...")
    email_failure_callback(test_context)


def test_slack_alert() -> None:
    """Test Slack alerting configuration."""
    test_alert_ctx = AlertContext(
        dag_id="test_dag",
        task_id="test_task",
        execution_date=str(datetime.now()),
        run_id="test_run",
        try_number=1,
        log_url="http://localhost:8080/log",
        duration_seconds=10.5,
        error_message="Test error message",
        level=AlertLevel.ERROR,
    )

    print("🧪 Testing Slack alert...")
    success = send_slack_alert(test_alert_ctx)
    if success:
        print("✅ Slack test successful")
    else:
        print("❌ Slack test failed")


if __name__ == "__main__":
    # Test alerting when run directly
    print("=" * 80)
    print("FEAT-002: Airflow Alerting Module Test")
    print("=" * 80)
    print()

    print("📧 Email Configuration:")
    print(f"   AIRFLOW_ALERT_EMAIL: {os.getenv('AIRFLOW_ALERT_EMAIL', 'NOT SET')}")
    print()

    print("📱 Slack Configuration:")
    print(
        f"   SLACK_WEBHOOK_URL: {'SET' if os.getenv('SLACK_WEBHOOK_URL') else 'NOT SET'}"
    )
    print(
        f"   SLACK_SUCCESS_NOTIFICATIONS: {os.getenv('SLACK_SUCCESS_NOTIFICATIONS', 'false')}"
    )
    print()

    # Uncomment to test
    # test_slack_alert()
    # test_email_alert()
