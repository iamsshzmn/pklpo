"""
Tests for Airflow Alerting Module (FEAT-002).

This module tests the alerting functionality including Email, Slack,
and combined callbacks for task failures and SLA misses.
"""

import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.features.infrastructure.alerts import (
    AlertContext,
    AlertLevel,
    combined_failure_callback,
    combined_sla_miss_callback,
    email_failure_callback,
    email_sla_miss_callback,
    extract_alert_context,
    format_failure_email,
    format_slack_message,
    send_slack_alert,
    slack_failure_callback,
    slack_sla_miss_callback,
    success_callback,
)


@pytest.fixture()
def mock_airflow_context():
    """Create mock Airflow context."""
    dag = Mock()
    dag.dag_id = "test_dag"

    task = Mock()
    task.task_id = "test_task"

    task_instance = Mock()
    task_instance.try_number = 1
    task_instance.start_date = datetime.now() - timedelta(seconds=30)
    task_instance.end_date = datetime.now()
    task_instance.log_url = "http://localhost:8080/log/test"

    return {
        "dag": dag,
        "task": {"task_id": "test_task"},
        "task_instance": task_instance,
        "execution_date": datetime(2025, 10, 27, 12, 0, 0),
        "run_id": "test_run_123",
        "exception": Exception("Test error message"),
        "reason": None,
    }


@pytest.fixture()
def alert_context():
    """Create test alert context."""
    return AlertContext(
        dag_id="test_dag",
        task_id="test_task",
        execution_date="2025-10-27T12:00:00",
        run_id="test_run_123",
        try_number=1,
        log_url="http://localhost:8080/log/test",
        duration_seconds=30.5,
        error_message="Test error message",
        level=AlertLevel.ERROR,
    )


class TestAlertContext:
    """Test AlertContext dataclass."""

    def test_alert_context_creation(self, alert_context):
        """Test alert context can be created."""
        assert alert_context.dag_id == "test_dag"
        assert alert_context.task_id == "test_task"
        assert alert_context.level == AlertLevel.ERROR

    def test_alert_context_to_dict(self, alert_context):
        """Test conversion to dictionary."""
        data = alert_context.to_dict()

        assert "dag_id" in data
        assert "task_id" in data
        assert "level" in data
        assert data["level"] == "error"
        assert data["duration_seconds"] == 30.5

    def test_alert_context_to_json(self, alert_context):
        """Test conversion to JSON."""
        import json

        json_str = alert_context.to_json()
        parsed = json.loads(json_str)

        assert parsed["dag_id"] == "test_dag"
        assert parsed["error_message"] == "Test error message"


class TestContextExtraction:
    """Test extracting alert context from Airflow context."""

    def test_extract_alert_context(self, mock_airflow_context):
        """Test basic context extraction."""
        alert_ctx = extract_alert_context(mock_airflow_context)

        assert alert_ctx.dag_id == "test_dag"
        assert alert_ctx.task_id == "test_task"
        assert alert_ctx.try_number == 1
        assert alert_ctx.error_message == "Test error message"
        assert alert_ctx.duration_seconds is not None

    def test_extract_alert_context_without_exception(self, mock_airflow_context):
        """Test context extraction without exception."""
        mock_airflow_context["exception"] = None
        mock_airflow_context["reason"] = "Timeout"

        alert_ctx = extract_alert_context(mock_airflow_context)

        assert alert_ctx.error_message == "Timeout"

    def test_extract_alert_context_minimal(self):
        """Test context extraction with minimal data."""
        minimal_context = {
            "dag": None,
            "task": {"task_id": "minimal_task"},
            "execution_date": "unknown",
        }

        alert_ctx = extract_alert_context(minimal_context)

        assert alert_ctx.dag_id == "unknown"
        assert alert_ctx.task_id == "minimal_task"


class TestEmailFormatting:
    """Test email formatting."""

    def test_format_failure_email(self, alert_context):
        """Test failure email formatting."""
        html = format_failure_email(alert_context)

        assert "test_dag" in html
        assert "test_task" in html
        assert "Test error message" in html
        assert "30.50s" in html
        assert "http://localhost:8080/log/test" in html

    def test_format_failure_email_without_error(self, alert_context):
        """Test email formatting without error message."""
        alert_context.error_message = None

        html = format_failure_email(alert_context)

        assert "test_dag" in html
        assert "test_task" in html
        # Should not crash without error message

    def test_format_failure_email_without_log_url(self, alert_context):
        """Test email formatting without log URL."""
        alert_context.log_url = None

        html = format_failure_email(alert_context)

        assert "test_dag" in html
        # Should not include View Logs link


class TestSlackFormatting:
    """Test Slack message formatting."""

    def test_format_slack_message(self, alert_context):
        """Test Slack message formatting."""
        payload = format_slack_message(alert_context)

        assert "attachments" in payload
        assert len(payload["attachments"]) > 0

        attachment = payload["attachments"][0]
        assert "color" in attachment
        assert "blocks" in attachment

        # Check blocks contain expected data
        blocks = attachment["blocks"]
        assert any("test_dag" in str(block) for block in blocks)
        assert any("test_task" in str(block) for block in blocks)

    def test_format_slack_message_warning_level(self, alert_context):
        """Test Slack formatting with WARNING level."""
        alert_context.level = AlertLevel.WARNING

        payload = format_slack_message(alert_context)
        attachment = payload["attachments"][0]

        # Warning should have different color
        assert attachment["color"] == "#ff9800"

    def test_format_slack_message_with_log_url(self, alert_context):
        """Test Slack formatting includes log button."""
        payload = format_slack_message(alert_context)
        attachment = payload["attachments"][0]
        blocks = attachment["blocks"]

        # Should have actions block with button
        action_blocks = [b for b in blocks if b.get("type") == "actions"]
        assert len(action_blocks) > 0

        button = action_blocks[0]["elements"][0]
        assert button["url"] == "http://localhost:8080/log/test"


class TestSlackSending:
    """Test Slack message sending."""

    @patch("src.features.infrastructure.alerts.requests.post")
    def test_send_slack_alert_success(self, mock_post, alert_context):
        """Test successful Slack alert sending."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}
        ):
            result = send_slack_alert(alert_context)

        assert result is True
        mock_post.assert_called_once()

    @patch("src.features.infrastructure.alerts.requests.post")
    def test_send_slack_alert_failure(self, mock_post, alert_context):
        """Test failed Slack alert sending."""
        mock_post.side_effect = Exception("Network error")

        with patch.dict(
            os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}
        ):
            result = send_slack_alert(alert_context)

        assert result is False

    def test_send_slack_alert_no_webhook(self, alert_context):
        """Test Slack sending without webhook configured."""
        with patch.dict(os.environ, {}, clear=True):
            result = send_slack_alert(alert_context)

        assert result is False


class TestEmailCallbacks:
    """Test email callback functions."""

    @patch("src.features.infrastructure.alerts.send_email")
    def test_email_failure_callback(self, mock_send_email, mock_airflow_context):
        """Test email failure callback."""
        email_failure_callback(mock_airflow_context)

        mock_send_email.assert_called_once()

        # Check call arguments
        call_args = mock_send_email.call_args
        assert "test_dag" in call_args.kwargs["subject"]
        assert "test_task" in call_args.kwargs["subject"]

    @patch("src.features.infrastructure.alerts.send_email")
    def test_email_sla_miss_callback(self, mock_send_email, mock_airflow_context):
        """Test email SLA miss callback."""
        email_sla_miss_callback(mock_airflow_context)

        mock_send_email.assert_called_once()

        # Check call arguments
        call_args = mock_send_email.call_args
        assert "SLA Miss" in call_args.kwargs["subject"]

    @patch("src.features.infrastructure.alerts.send_email")
    def test_email_callback_with_custom_email(
        self, mock_send_email, mock_airflow_context
    ):
        """Test email callback with custom email address."""
        with patch.dict(
            os.environ, {"AIRFLOW_ALERT_EMAIL": "custom@example.com,other@example.com"}
        ):
            email_failure_callback(mock_airflow_context)

        call_args = mock_send_email.call_args
        assert "custom@example.com" in call_args.kwargs["to"]
        assert "other@example.com" in call_args.kwargs["to"]


class TestSlackCallbacks:
    """Test Slack callback functions."""

    @patch("src.features.infrastructure.alerts.send_slack_alert")
    def test_slack_failure_callback(self, mock_send_slack, mock_airflow_context):
        """Test Slack failure callback."""
        slack_failure_callback(mock_airflow_context)

        mock_send_slack.assert_called_once()

        # Check alert context passed
        alert_ctx = mock_send_slack.call_args[0][0]
        assert alert_ctx.dag_id == "test_dag"
        assert alert_ctx.level == AlertLevel.ERROR

    @patch("src.features.infrastructure.alerts.send_slack_alert")
    def test_slack_sla_miss_callback(self, mock_send_slack, mock_airflow_context):
        """Test Slack SLA miss callback."""
        slack_sla_miss_callback(mock_airflow_context)

        mock_send_slack.assert_called_once()

        # Check alert context passed
        alert_ctx = mock_send_slack.call_args[0][0]
        assert alert_ctx.level == AlertLevel.WARNING


class TestCombinedCallbacks:
    """Test combined callback functions."""

    @patch("src.features.infrastructure.alerts.email_failure_callback")
    @patch("src.features.infrastructure.alerts.slack_failure_callback")
    def test_combined_failure_callback(
        self, mock_slack, mock_email, mock_airflow_context
    ):
        """Test combined failure callback."""
        combined_failure_callback(mock_airflow_context)

        # Both callbacks should be called
        mock_email.assert_called_once()
        mock_slack.assert_called_once()

    @patch("src.features.infrastructure.alerts.email_failure_callback")
    @patch("src.features.infrastructure.alerts.slack_failure_callback")
    def test_combined_failure_callback_resilient(
        self, mock_slack, mock_email, mock_airflow_context
    ):
        """Test combined callback is resilient to individual failures."""
        # Email fails but Slack should still be called
        mock_email.side_effect = Exception("Email failed")

        # Should not raise
        combined_failure_callback(mock_airflow_context)

        # Both should be attempted
        mock_email.assert_called_once()
        mock_slack.assert_called_once()

    @patch("src.features.infrastructure.alerts.email_sla_miss_callback")
    @patch("src.features.infrastructure.alerts.slack_sla_miss_callback")
    def test_combined_sla_miss_callback(
        self, mock_slack, mock_email, mock_airflow_context
    ):
        """Test combined SLA miss callback."""
        combined_sla_miss_callback(mock_airflow_context)

        # Both callbacks should be called
        mock_email.assert_called_once()
        mock_slack.assert_called_once()


class TestSuccessCallback:
    """Test success callback."""

    @patch("src.features.infrastructure.alerts.send_slack_alert")
    def test_success_callback_disabled(self, mock_send_slack, mock_airflow_context):
        """Test success callback when disabled."""
        with patch.dict(os.environ, {"SLACK_SUCCESS_NOTIFICATIONS": "false"}):
            success_callback(mock_airflow_context)

        # Should not send Slack notification
        mock_send_slack.assert_not_called()

    @patch("src.features.infrastructure.alerts.send_slack_alert")
    def test_success_callback_enabled(self, mock_send_slack, mock_airflow_context):
        """Test success callback when enabled."""
        with patch.dict(os.environ, {"SLACK_SUCCESS_NOTIFICATIONS": "true"}):
            success_callback(mock_airflow_context)

        # Should send Slack notification
        mock_send_slack.assert_called_once()

        # Check it's INFO level
        alert_ctx = mock_send_slack.call_args[0][0]
        assert alert_ctx.level == AlertLevel.INFO


class TestAlertLevels:
    """Test alert level enum."""

    def test_alert_levels_exist(self):
        """Test all alert levels are defined."""
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"


@pytest.mark.integration()
class TestAlertsIntegration:
    """Integration tests (require actual Slack webhook)."""

    @pytest.mark.skip(reason="Requires actual Slack webhook")
    def test_real_slack_alert(self, alert_context):
        """Test sending real Slack alert (manual test)."""
        # This test requires actual SLACK_WEBHOOK_URL env var
        result = send_slack_alert(alert_context)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
