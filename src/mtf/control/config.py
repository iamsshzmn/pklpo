"""
Configuration management for MTF Control module
"""

from pathlib import Path
from typing import Any

import yaml

from .models import ControlConfig


class ControlConfigManager:
    """Менеджер конфигурации Control модуля"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self._config: ControlConfig | None = None

    def load_config(self, config_path: str | None = None) -> ControlConfig:
        """Загрузка конфигурации"""
        if config_path:
            self.config_path = config_path

        if self.config_path and Path(self.config_path).exists():
            try:
                self._config = ControlConfig.from_yaml(self.config_path)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                self._config = ControlConfig.default()
        else:
            self._config = ControlConfig.default()

        return self._config

    def get_config(self) -> ControlConfig:
        """Получение текущей конфигурации"""
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def update_config(self, updates: dict[str, Any]) -> None:
        """Обновление конфигурации"""
        if self._config is None:
            self._config = ControlConfig.default()

        for key, value in updates.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def save_config(self, config_path: str | None = None) -> None:
        """Сохранение конфигурации в YAML файл"""
        if self._config is None:
            return

        save_path = config_path or self.config_path
        if not save_path:
            return

        config_data = {"control": self._config.to_dict()}

        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)

    def validate_config(self) -> bool:
        """Валидация конфигурации"""
        if self._config is None:
            return False

        # Проверка основных параметров
        if self._config.max_workers <= 0:
            return False

        if self._config.timeout_seconds <= 0:
            return False

        if self._config.retry_attempts < 0:
            return False

        if self._config.monitoring_interval_seconds <= 0:
            return False

        if self._config.health_check_interval_seconds <= 0:
            return False

        if self._config.metrics_collection_interval_seconds <= 0:
            return False

        # Проверка порогов алертов
        if self._config.alert_threshold_errors < 0:
            return False

        if self._config.alert_threshold_response_time <= 0:
            return False

        if self._config.alert_threshold_memory_usage <= 0:
            return False

        if (
            self._config.alert_threshold_cpu_usage <= 0
            or self._config.alert_threshold_cpu_usage > 100
        ):
            return False

        # Проверка ресурсов
        if self._config.max_memory_usage_mb <= 0:
            return False

        if (
            self._config.max_cpu_usage_percent <= 0
            or self._config.max_cpu_usage_percent > 100
        ):
            return False

        if self._config.max_concurrent_requests <= 0:
            return False

        # Проверка восстановления
        if self._config.auto_recovery_attempts < 0:
            return False

        if self._config.auto_recovery_delay_seconds <= 0:
            return False

        # Проверка конфигурации
        return not self._config.config_reload_interval_seconds <= 0

    def get_component_config(self) -> dict[str, Any]:
        """Получение конфигурации компонентов"""
        config = self.get_config()

        return {
            "context_enabled": config.context_enabled,
            "triggers_enabled": config.triggers_enabled,
            "consensus_enabled": config.consensus_enabled,
            "pipeline_enabled": config.pipeline_enabled,
            "integration_enabled": config.integration_enabled,
        }

    def get_monitoring_config(self) -> dict[str, Any]:
        """Получение конфигурации мониторинга"""
        config = self.get_config()

        return {
            "enable_monitoring": config.enable_monitoring,
            "monitoring_interval_seconds": config.monitoring_interval_seconds,
            "health_check_interval_seconds": config.health_check_interval_seconds,
            "metrics_collection_interval_seconds": config.metrics_collection_interval_seconds,
        }

    def get_alert_config(self) -> dict[str, Any]:
        """Получение конфигурации алертов"""
        config = self.get_config()

        return {
            "enable_alerts": config.enable_alerts,
            "alert_threshold_errors": config.alert_threshold_errors,
            "alert_threshold_response_time": config.alert_threshold_response_time,
            "alert_threshold_memory_usage": config.alert_threshold_memory_usage,
            "alert_threshold_cpu_usage": config.alert_threshold_cpu_usage,
        }

    def get_resource_config(self) -> dict[str, Any]:
        """Получение конфигурации ресурсов"""
        config = self.get_config()

        return {
            "max_memory_usage_mb": config.max_memory_usage_mb,
            "max_cpu_usage_percent": config.max_cpu_usage_percent,
            "max_concurrent_requests": config.max_concurrent_requests,
        }

    def get_recovery_config(self) -> dict[str, Any]:
        """Получение конфигурации восстановления"""
        config = self.get_config()

        return {
            "enable_auto_recovery": config.enable_auto_recovery,
            "auto_recovery_attempts": config.auto_recovery_attempts,
            "auto_recovery_delay_seconds": config.auto_recovery_delay_seconds,
        }

    def get_logging_config(self) -> dict[str, Any]:
        """Получение конфигурации логирования"""
        config = self.get_config()

        return {
            "enable_logging": config.enable_logging,
            "log_level": config.log_level,
            "log_performance": config.log_performance,
            "log_retention_days": config.log_retention_days,
        }

    def get_processing_config(self) -> dict[str, Any]:
        """Получение конфигурации обработки"""
        config = self.get_config()

        return {
            "max_workers": config.max_workers,
            "timeout_seconds": config.timeout_seconds,
            "retry_attempts": config.retry_attempts,
            "retry_delay_seconds": config.retry_delay_seconds,
        }

    def reset_to_defaults(self) -> None:
        """Сброс к настройкам по умолчанию"""
        self._config = ControlConfig.default()

    def get_config_summary(self) -> dict[str, Any]:
        """Получение краткого описания конфигурации"""
        config = self.get_config()

        return {
            "version": "1.0.0",
            "components": {
                "context": config.context_enabled,
                "triggers": config.triggers_enabled,
                "consensus": config.consensus_enabled,
                "pipeline": config.pipeline_enabled,
                "integration": config.integration_enabled,
            },
            "monitoring": {
                "enabled": config.enable_monitoring,
                "interval": config.monitoring_interval_seconds,
            },
            "alerts": {
                "enabled": config.enable_alerts,
                "error_threshold": config.alert_threshold_errors,
            },
            "resources": {
                "max_memory_mb": config.max_memory_usage_mb,
                "max_cpu_percent": config.max_cpu_usage_percent,
                "max_workers": config.max_workers,
            },
            "recovery": {
                "auto_recovery": config.enable_auto_recovery,
                "attempts": config.auto_recovery_attempts,
            },
        }
