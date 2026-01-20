"""
Airflow configuration for features module.

This configuration implements the Airflow requirements from the plan:
- Separate tasks per group with depends_on_past=False
- XCom only for counters (not DataFrames)
- Retries only for I/O errors (not validation)
- SLA and alerts for no rows in 24h for active symbols/timeframes
"""

# Airflow Variables for features module
AIRFLOW_VARIABLES = {
    "active_symbols": "BTC-USDT,ETH-USDT,ADA-USDT,SOL-USDT",
    "active_timeframes": "1h,4h,1d",
    "features_batch_size": "5000",
    "features_max_retries": "3",
    "features_sla_hours": "24",
    "features_alert_email": "features-team@company.com",
    "features_slack_channel": "#features-alerts",
}

# DAG configuration
DAG_CONFIG = {
    "features_group_calculation": {
        "schedule_interval": "@hourly",
        "max_active_runs": 1,
        "catchup": False,
        "default_args": {
            "depends_on_past": False,
            "retries": 3,
            "retry_delay": "00:05:00",
            "retry_exponential_backoff": True,
            "max_retry_delay": "00:30:00",
            "sla": "24:00:00",
        },
    }
}

# Task configuration
TASK_CONFIG = {
    "fetch_data": {"retries": 3, "retry_delay": "00:02:00"},  # I/O errors
    "group_calculation": {
        "retries": 3,  # I/O errors
        "retry_delay": "00:03:00",
        "depends_on_past": False,
    },
    "sla_check": {
        "retries": 0,  # No retries for validation
        "trigger_rule": "all_success",
    },
    "alerts": {"retries": 0, "trigger_rule": "one_failed"},  # No retries for alerts
}

# SLA configuration
SLA_CONFIG = {
    "check_interval": "01:00:00",  # Check every hour
    "timeout_hours": 24,  # 24 hour timeout
    "alert_threshold": 0,  # Alert if 0 rows in 24h
    "notification_channels": ["email", "slack"],
}

# Retry configuration
RETRY_CONFIG = {
    "io_errors": {
        "max_retries": 3,
        "retry_delay": "00:05:00",
        "exponential_backoff": True,
        "max_retry_delay": "00:30:00",
    },
    "validation_errors": {
        "max_retries": 0,  # No retries for validation
        "fail_fast": True,
    },
    "alert_errors": {"max_retries": 0, "fail_fast": True},  # No retries for alerts
}

# XCom configuration
XCOM_CONFIG = {
    "max_size_mb": 1,  # Limit XCom size
    "allowed_types": ["dict", "list", "int", "float", "str"],  # Only counters
    "forbidden_types": ["DataFrame", "Series", "ndarray"],  # No DataFrames
    "cleanup_after_use": True,
}

# Monitoring configuration
MONITORING_CONFIG = {
    "metrics": [
        "features.rows_written",
        "fill_rate.overlap",
        "fill_rate.ma",
        "fill_rate.oscillators",
        "fill_rate.volatility",
        "fill_rate.volume",
        "fill_rate.trend",
        "fill_rate.candles",
        "fill_rate.squeeze",
        "fill_rate.statistics",
        "fill_rate.performance",
        "rows_last_24h",
        "upsert_failures",
    ],
    "alerts": {
        "low_fill_rate": 0.5,  # Alert if fill rate < 50%
        "high_failure_rate": 0.1,  # Alert if failure rate > 10%
        "no_data_24h": True,  # Alert if no data in 24h
        "sla_violation": True,  # Alert on SLA violation
    },
}

# Email configuration
EMAIL_CONFIG = {
    "smtp_server": "smtp.company.com",
    "smtp_port": 587,
    "smtp_username": "airflow@company.com",
    "smtp_password": "{{ var.value.smtp_password }}",
    "from_email": "airflow@company.com",
    "to_emails": ["features-team@company.com", "devops@company.com"],
}

# Slack configuration
SLACK_CONFIG = {
    "token": "{{ var.value.slack_token }}",
    "channels": {
        "alerts": "#features-alerts",
        "notifications": "#features-notifications",
        "errors": "#features-errors",
    },
    "webhook_url": "{{ var.value.slack_webhook_url }}",
}

# Database configuration
DATABASE_CONFIG = {
    "connection_id": "features_postgres",
    "batch_size": 5000,
    "max_retries": 3,
    "retry_delay": "00:05:00",
    "upsert_method": "on_conflict_do_update",
    "indexes": ["(symbol, timeframe, timestamp)", "(calculated_at)", "(run_id)"],
}

# Logging configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "handlers": {
        "console": True,
        "file": "/opt/airflow/logs/features.log",
        "email": True,
    },
    "log_rotation": {"max_bytes": 10485760, "backup_count": 5},  # 10MB
}

# Performance configuration
PERFORMANCE_CONFIG = {
    "parallel_tasks": 10,  # Max parallel group calculations
    "memory_limit": "2GB",
    "cpu_limit": "1000m",
    "timeout": "01:00:00",  # 1 hour timeout per task
    "batch_processing": True,
    "chunk_size": 5000,
}

# Security configuration
SECURITY_CONFIG = {
    "encrypt_xcom": True,
    "mask_sensitive_data": True,
    "audit_logging": True,
    "access_control": {
        "read_only_users": ["analyst", "viewer"],
        "admin_users": ["admin", "devops"],
        "operator_users": ["features-team"],
    },
}


# Configuration validation
def validate_config():
    """Validate configuration parameters."""
    required_vars = [
        "active_symbols",
        "active_timeframes",
        "features_batch_size",
        "features_max_retries",
        "features_sla_hours",
    ]

    for var in required_vars:
        if var not in AIRFLOW_VARIABLES:
            raise ValueError(f"Required variable {var} not found in AIRFLOW_VARIABLES")

    # Validate batch size
    batch_size = int(AIRFLOW_VARIABLES["features_batch_size"])
    if not (1000 <= batch_size <= 10000):
        raise ValueError("Batch size must be between 1000 and 10000")

    # Validate retries
    max_retries = int(AIRFLOW_VARIABLES["features_max_retries"])
    if not (0 <= max_retries <= 5):
        raise ValueError("Max retries must be between 0 and 5")

    # Validate SLA hours
    sla_hours = int(AIRFLOW_VARIABLES["features_sla_hours"])
    if not (1 <= sla_hours <= 48):
        raise ValueError("SLA hours must be between 1 and 48")

    return True


# Export configuration
__all__ = [
    "AIRFLOW_VARIABLES",
    "DAG_CONFIG",
    "TASK_CONFIG",
    "SLA_CONFIG",
    "RETRY_CONFIG",
    "XCOM_CONFIG",
    "MONITORING_CONFIG",
    "EMAIL_CONFIG",
    "SLACK_CONFIG",
    "DATABASE_CONFIG",
    "LOGGING_CONFIG",
    "PERFORMANCE_CONFIG",
    "SECURITY_CONFIG",
    "validate_config",
]
