# Airflow Alerting Guide (FEAT-002)

**Feature:** Airflow Integration - Alerting and Monitoring  
**Version:** 1.0  
**Status:** ✅ Implemented  

---

## 📋 Overview

The Airflow alerting system provides comprehensive monitoring and notification capabilities for the `features_calc` DAG and other critical pipelines. It supports multiple channels (Email, Slack) and various event types (failures, SLA misses, successes).

### Key Benefits

- **🚨 Immediate Failure Notifications**: Get alerted instantly when tasks fail
- **⏰ SLA Monitoring**: Track and alert on tasks exceeding time thresholds
- **📧 Email Integration**: HTML-formatted emails with task details
- **📱 Slack Integration**: Rich formatted messages with direct log links
- **🔄 Retry Management**: Smart retry logic with exponential backoff
- **✅ Optional Success Notifications**: Celebrate successful runs

---

## 🎯 Features

### Alert Types

1. **Task Failure Alerts**
   - Triggered when a task fails after all retries
   - Includes error message, duration, and log links
   - Sent via Email and/or Slack

2. **SLA Miss Alerts**
   - Triggered when a task exceeds its SLA threshold
   - Warning-level alerts (not critical)
   - Helps identify performance degradation

3. **Success Notifications** (Optional)
   - Triggered on successful task completion
   - Only via Slack (to avoid email spam)
   - Useful for critical production DAGs

### Notification Channels

1. **Email**
   - HTML-formatted messages
   - Includes full task context
   - Requires Airflow SMTP configuration

2. **Slack**
   - Rich block-based formatting
   - Direct links to Airflow logs
   - Configurable via webhook URL

---

## 🚀 Quick Start

### 1. Configure Environment Variables

```bash
# Email configuration (for Airflow SMTP)
export AIRFLOW_ALERT_EMAIL="data-team@company.com,devops@company.com"

# Slack configuration
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Optional: Enable success notifications
export SLACK_SUCCESS_NOTIFICATIONS="false"  # default: false
```

### 2. Update Your DAG

The `features_calc` DAG already has alerting enabled. For other DAGs:

```python
from datetime import timedelta
from src.features.infrastructure.alerts import (
    combined_failure_callback,
    combined_sla_miss_callback,
    success_callback
)

default_args = {
    "owner": "your_team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
    "sla": timedelta(hours=1),  # SLA threshold

    # Alerting callbacks
    "on_failure_callback": combined_failure_callback,
    "sla_miss_callback": combined_sla_miss_callback,
    # "on_success_callback": success_callback,  # Optional

    # Email configuration
    "email_on_failure": True,
    "email_on_retry": False,
    "email": ["data-team@company.com"]
}

with DAG(
    dag_id="your_dag",
    default_args=default_args,
    # ... other DAG config
) as dag:
    # ... your tasks
```

### 3. Test Alerts

```bash
# Test Slack integration
python -m src.features.infrastructure.alerts

# Or use pytest
pytest src/features/tests/test_alerts.py -v
```

---

## 📧 Email Alerts

### Configuration

Email alerts require Airflow SMTP configuration:

```ini
# airflow.cfg
[smtp]
smtp_host = smtp.gmail.com
smtp_starttls = True
smtp_ssl = False
smtp_user = your-email@gmail.com
smtp_password = your-app-password
smtp_port = 587
smtp_mail_from = airflow@yourcompany.com
```

Or via environment variables:

```bash
export AIRFLOW__SMTP__SMTP_HOST=smtp.gmail.com
export AIRFLOW__SMTP__SMTP_USER=your-email@gmail.com
export AIRFLOW__SMTP__SMTP_PASSWORD=your-app-password
export AIRFLOW__SMTP__SMTP_PORT=587
export AIRFLOW__SMTP__SMTP_MAIL_FROM=airflow@yourcompany.com
```

### Email Format

Failure emails include:
- **Header**: Visual indicator of failure
- **Task Details**: DAG ID, Task ID, Execution Date, Try Number
- **Duration**: How long the task ran
- **Error Message**: Full stack trace or error description
- **Log Link**: Direct link to Airflow logs

Example:

```
Subject: 🚨 Airflow Task Failed: features_calc.features_run

[HTML formatted email with:]
- Red header banner
- Table with task details
- Error message in highlighted box
- "View Logs" button
```

---

## 📱 Slack Alerts

### Configuration

1. **Create Slack App**
   - Go to https://api.slack.com/apps
   - Create new app
   - Enable "Incoming Webhooks"
   - Add webhook to your channel
   - Copy webhook URL

2. **Set Environment Variable**
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
   ```

3. **Test Integration**
   ```python
   from src.features.infrastructure.alerts import test_slack_alert
   test_slack_alert()
   ```

### Slack Message Format

Slack messages use rich block formatting:

```
🚨 Airflow Task Alert

DAG: features_calc
Task: features_run
Execution Date: 2025-10-27 12:00:00
Try Number: 2

Duration: 125.50s

Error:
```
Exception: Database connection timeout after 30s
```

[View Logs] (button with direct link)
```

### Color Coding

- **Red** (#dc3545): Errors and failures
- **Orange** (#ff9800): Warnings and SLA misses
- **Green** (#36a64f): Info and success messages
- **Dark Red** (#8b0000): Critical alerts

---

## ⏰ SLA Monitoring

### What is SLA?

SLA (Service Level Agreement) defines the maximum acceptable duration for a task. If a task exceeds this threshold, an SLA miss alert is triggered.

### Configuring SLAs

```python
default_args = {
    "sla": timedelta(hours=1),  # Task should complete in 1 hour
    "sla_miss_callback": combined_sla_miss_callback
}
```

Or per-task:

```python
task = PythonOperator(
    task_id="slow_task",
    python_callable=my_function,
    sla=timedelta(minutes=30),  # This task should complete in 30 minutes
)
```

### SLA Best Practices

1. **Set Realistic Thresholds**: Base SLAs on historical data
2. **Monitor Trends**: Track SLA misses over time
3. **Adjust as Needed**: Update SLAs as data volume changes
4. **Different SLAs per Task**: Not all tasks have the same requirements

---

## 🔧 Advanced Configuration

### Custom Callbacks

You can create custom callbacks for specific needs:

```python
from src.features.infrastructure.alerts import extract_alert_context, send_slack_alert

def custom_failure_callback(context):
    """Custom callback with additional logic."""
    alert_ctx = extract_alert_context(context)

    # Add custom logic
    if "OOM" in str(alert_ctx.error_message):
        alert_ctx.level = AlertLevel.CRITICAL
        # Trigger pagerduty, etc.

    # Send standard alert
    send_slack_alert(alert_ctx)
```

### Per-Task Overrides

```python
critical_task = PythonOperator(
    task_id="critical_task",
    python_callable=important_function,
    # Override default callbacks for this task only
    on_failure_callback=custom_critical_failure_callback,
    email=["cto@company.com"],  # Notify senior staff
    sla=timedelta(minutes=10)  # Stricter SLA
)
```

### Conditional Alerting

```python
def conditional_alert_callback(context):
    """Only alert on specific conditions."""
    error = str(context.get('exception', ''))

    # Ignore transient errors
    if "ConnectionResetError" in error:
        print("Transient error, not alerting")
        return

    # Alert on everything else
    combined_failure_callback(context)
```

---

## 📊 Alert Context

Every alert includes structured context:

```python
@dataclass
class AlertContext:
    dag_id: str                      # DAG identifier
    task_id: str                     # Task identifier
    execution_date: str              # When task was scheduled
    run_id: str                      # Unique run identifier
    try_number: int                  # Retry attempt number
    log_url: Optional[str]           # Direct link to logs
    duration_seconds: Optional[float] # Task execution time
    error_message: Optional[str]     # Error description
    level: AlertLevel                # INFO/WARNING/ERROR/CRITICAL
```

Access context in callbacks:

```python
from src.features.infrastructure.alerts import extract_alert_context

def my_callback(context):
    alert_ctx = extract_alert_context(context)
    print(f"Task {alert_ctx.task_id} failed after {alert_ctx.duration_seconds}s")
    print(f"Error: {alert_ctx.error_message}")
```

---

## 🧪 Testing

### Run Unit Tests

```bash
pytest src/features/tests/test_alerts.py -v
```

### Test Slack Integration

```bash
# Set webhook URL
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Run test
python -c "from src.features.infrastructure.alerts import test_slack_alert; test_slack_alert()"
```

### Test Email Integration

```bash
# Requires Airflow SMTP configuration
python -c "from src.features.infrastructure.alerts import test_email_alert; test_email_alert()"
```

### Simulate Failure in Airflow

Trigger a test DAG with intentional failure to verify alerts:

```python
# test_alert_dag.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from src.features.infrastructure.alerts import combined_failure_callback

def fail_intentionally():
    raise Exception("Test failure for alert verification")

with DAG(
    dag_id="test_alerts",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    default_args={
        "on_failure_callback": combined_failure_callback,
        "email_on_failure": True,
        "email": ["test@company.com"]
    }
) as dag:
    test_task = PythonOperator(
        task_id="test_failure",
        python_callable=fail_intentionally
    )
```

---

## 🐛 Troubleshooting

### Problem: No Slack alerts received

**Solutions:**
1. Check webhook URL is set: `echo $SLACK_WEBHOOK_URL`
2. Verify webhook is valid (test with curl):
   ```bash
   curl -X POST $SLACK_WEBHOOK_URL \
     -H 'Content-Type: application/json' \
     -d '{"text":"Test message"}'
   ```
3. Check Airflow logs for errors
4. Verify network connectivity from Airflow workers

### Problem: No email alerts received

**Solutions:**
1. Check SMTP configuration in `airflow.cfg`
2. Test SMTP connection:
   ```python
   from airflow.utils.email import send_email
   send_email(to=["test@company.com"], subject="Test", html_content="Test")
   ```
3. Check spam folder
4. Verify `email_on_failure=True` in DAG config
5. Check Airflow logs for SMTP errors

### Problem: Too many alert notifications

**Solutions:**
1. Set `email_on_retry=False` to avoid retry spam
2. Increase `retries` and `retry_delay` to reduce failure rate
3. Disable success notifications: `SLACK_SUCCESS_NOTIFICATIONS=false`
4. Implement conditional alerting for transient errors

### Problem: SLA alerts not triggering

**Solutions:**
1. Verify `sla` is set in `default_args` or task
2. Check `sla_miss_callback` is configured
3. Ensure task actually exceeds SLA (check duration)
4. Verify Airflow scheduler is running

---

## 📚 API Reference

### Callback Functions

```python
def email_failure_callback(context: Dict[str, Any]) -> None
    """Send email alert on task failure."""

def email_sla_miss_callback(context: Dict[str, Any]) -> None
    """Send email alert on SLA miss."""

def slack_failure_callback(context: Dict[str, Any]) -> None
    """Send Slack alert on task failure."""

def slack_sla_miss_callback(context: Dict[str, Any]) -> None
    """Send Slack alert on SLA miss."""

def combined_failure_callback(context: Dict[str, Any]) -> None
    """Send alerts to both Email and Slack on failure."""

def combined_sla_miss_callback(context: Dict[str, Any]) -> None
    """Send alerts to both channels on SLA miss."""

def success_callback(context: Dict[str, Any]) -> None
    """Optional success notification (Slack only)."""
```

### Utility Functions

```python
def extract_alert_context(context: Dict[str, Any]) -> AlertContext
    """Extract structured alert context from Airflow context."""

def format_failure_email(alert_ctx: AlertContext) -> str
    """Format HTML email content for failure."""

def format_slack_message(alert_ctx: AlertContext) -> Dict[str, Any]
    """Format Slack message payload with blocks."""

def send_slack_alert(alert_ctx: AlertContext, webhook_url: Optional[str] = None) -> bool
    """Send alert to Slack via webhook."""
```

---

## 🎯 Best Practices

### 1. Use Combined Callbacks

```python
# ✅ GOOD: Combined callback for redundancy
"on_failure_callback": combined_failure_callback

# ❌ BAD: Only one channel (single point of failure)
"on_failure_callback": slack_failure_callback
```

### 2. Set Appropriate Retries

```python
# ✅ GOOD: Retry transient failures
"retries": 2,
"retry_delay": timedelta(minutes=5)

# ❌ BAD: No retries (alert on every transient error)
"retries": 0
```

### 3. Disable Retry Emails

```python
# ✅ GOOD: Only alert on final failure
"email_on_failure": True,
"email_on_retry": False

# ❌ BAD: Spam on every retry
"email_on_retry": True
```

### 4. Set Realistic SLAs

```python
# ✅ GOOD: Based on historical data (p95 + buffer)
"sla": timedelta(hours=1)

# ❌ BAD: Too aggressive (constant false alarms)
"sla": timedelta(minutes=5)
```

### 5. Use Tags for Filtering

```python
# ✅ GOOD: Tag critical DAGs for monitoring
tags=["critical", "production", "monitored"]

# Helps filter in Airflow UI and metrics
```

---

## 📖 Related Documentation

- [RECOMMENDATIONS_AUDIT.md](./RECOMMENDATIONS_AUDIT.md) - Architecture audit
- [IMPLEMENTATION_ROADMAP.md](./IMPLEMENTATION_ROADMAP.md) - Implementation plan
- [VERSIONING_GUIDE.md](./VERSIONING_GUIDE.md) - ML reproducibility
- [Airflow Documentation](https://airflow.apache.org/docs/)

---

**Version:** 1.0  
**Last Updated:** 2025-10-27  
**Status:** ✅ Production Ready
