"""
Configuration management for MTF Pipeline module
"""

from pathlib import Path
from typing import Any

import yaml

from .models import PipelineConfig


class PipelineConfigManager:
    """Configuration manager for the Pipeline module."""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self._config: PipelineConfig | None = None

    def load_config(self, config_path: str | None = None) -> PipelineConfig:
        """Load configuration."""
        if config_path:
            self.config_path = config_path

        if self.config_path and Path(self.config_path).exists():
            try:
                self._config = PipelineConfig.from_yaml(self.config_path)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                self._config = PipelineConfig.default()
        else:
            self._config = PipelineConfig.default()

        return self._config

    def get_config(self) -> PipelineConfig:
        """Return the current configuration."""
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def update_config(self, updates: dict[str, Any]) -> None:
        """Update configuration."""
        if self._config is None:
            self._config = PipelineConfig.default()

        for key, value in updates.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def save_config(self, config_path: str | None = None) -> None:
        """Save configuration to a YAML file."""
        if self._config is None:
            return

        save_path = config_path or self.config_path
        if not save_path:
            return

        config_data = {"pipeline": self._config.to_dict()}

        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)

    def validate_config(self) -> bool:
        """Validate configuration."""
        if self._config is None:
            return False

        # Basic parameter checks
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

        return not self._config.min_data_points <= 0

    def get_component_configs(self) -> dict[str, dict[str, Any]]:
        """Get component configurations"""
        config = self.get_config()

        return {
            "context": {
                "enabled": config.context_enabled,
                "timeout_seconds": config.timeout_seconds,
                "retry_attempts": config.retry_attempts,
                "cache_enabled": config.cache_enabled,
                "cache_ttl_seconds": config.cache_ttl_seconds,
                "min_data_points": config.min_data_points,
            },
            "triggers": {
                "enabled": config.triggers_enabled,
                "timeout_seconds": config.timeout_seconds,
                "retry_attempts": config.retry_attempts,
                "cache_enabled": config.cache_enabled,
                "cache_ttl_seconds": config.cache_ttl_seconds,
                "min_data_points": config.min_data_points,
            },
            "consensus": {
                "enabled": config.consensus_enabled,
                "timeout_seconds": config.timeout_seconds,
                "retry_attempts": config.retry_attempts,
                "cache_enabled": config.cache_enabled,
                "cache_ttl_seconds": config.cache_ttl_seconds,
                "min_data_points": config.min_data_points,
            },
        }

    def get_logging_config(self) -> dict[str, Any]:
        """Get logging configuration"""
        config = self.get_config()

        return {
            "enable_logging": config.enable_logging,
            "log_level": config.log_level,
            "log_performance": config.log_performance,
        }

    def get_metrics_config(self) -> dict[str, Any]:
        """Get metrics configuration"""
        config = self.get_config()

        return {
            "enable_metrics": config.enable_metrics,
            "metrics_interval_seconds": config.metrics_interval_seconds,
        }
