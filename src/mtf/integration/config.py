"""
Configuration management for MTF Integration module
"""

from pathlib import Path
from typing import Any

import yaml

from .models import IntegrationConfig


class IntegrationConfigManager:
    """Менеджер конфигурации Integration модуля"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self._config: IntegrationConfig | None = None

    def load_config(self, config_path: str | None = None) -> IntegrationConfig:
        """Загрузка конфигурации"""
        if config_path:
            self.config_path = config_path

        if self.config_path and Path(self.config_path).exists():
            try:
                self._config = IntegrationConfig.from_yaml(self.config_path)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                self._config = IntegrationConfig.default()
        else:
            self._config = IntegrationConfig.default()

        return self._config

    def get_config(self) -> IntegrationConfig:
        """Получение текущей конфигурации"""
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def update_config(self, updates: dict[str, Any]) -> None:
        """Обновление конфигурации"""
        if self._config is None:
            self._config = IntegrationConfig.default()

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

        config_data = {"integration": self._config.to_dict()}

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

        if self._config.cache_ttl_seconds <= 0:
            return False

        if self._config.max_timeframes_per_request <= 0:
            return False

        if self._config.min_data_points <= 0:
            return False

        # Проверка OKX конфигурации
        if self._config.okx_enabled:
            if not self._config.okx_api_key:
                return False
            if not self._config.okx_secret_key:
                return False
            if not self._config.okx_passphrase:
                return False

        # Проверка базы данных
        if self._config.database_enabled and not self._config.database_url:
            return False

        # Проверка уведомлений
        return not (
            self._config.notifications_enabled
            and not any(
                [self._config.slack_webhook_url, self._config.email_smtp_server]
            )
        )

    def get_okx_config(self) -> dict[str, Any]:
        """Получение конфигурации OKX API"""
        config = self.get_config()

        return {
            "enabled": config.okx_enabled,
            "api_key": config.okx_api_key,
            "secret_key": config.okx_secret_key,
            "passphrase": config.okx_passphrase,
            "sandbox": config.okx_sandbox,
            "rate_limit": config.okx_rate_limit,
        }

    def get_database_config(self) -> dict[str, Any]:
        """Получение конфигурации базы данных"""
        config = self.get_config()

        return {
            "enabled": config.database_enabled,
            "url": config.database_url,
            "pool_size": config.database_pool_size,
            "timeout": config.database_timeout,
        }

    def get_notification_config(self) -> dict[str, Any]:
        """Получение конфигурации уведомлений"""
        config = self.get_config()

        return {
            "enabled": config.notifications_enabled,
            "slack_webhook_url": config.slack_webhook_url,
            "email_smtp_server": config.email_smtp_server,
            "email_smtp_port": config.email_smtp_port,
            "email_username": config.email_username,
            "email_password": config.email_password,
            "email_from": config.email_from,
            "email_to": config.email_to,
        }

    def get_logging_config(self) -> dict[str, Any]:
        """Получение конфигурации логирования"""
        config = self.get_config()

        return {
            "enable_logging": config.enable_logging,
            "log_level": config.log_level,
            "log_performance": config.log_performance,
        }

    def get_metrics_config(self) -> dict[str, Any]:
        """Получение конфигурации метрик"""
        config = self.get_config()

        return {
            "enable_metrics": config.enable_metrics,
            "metrics_interval_seconds": config.metrics_interval_seconds,
        }
