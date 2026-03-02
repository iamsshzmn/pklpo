"""
Конфигурация модуля управления рисками (Фаза 5)

Централизованная настройка всех параметров риска
"""

import os
from pathlib import Path
from typing import Any

import yaml

from .models import RiskConfig


class RiskConfigManager:
    """Менеджер конфигурации рисков"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or self._get_default_config_path()
        self._config: RiskConfig | None = None

    def _get_default_config_path(self) -> str:
        """Получение пути к конфигурации по умолчанию"""
        return str(Path(__file__).parent / "config.yaml")

    def load_config(self) -> RiskConfig:
        """Загрузка конфигурации"""
        if self._config is not None:
            return self._config

        # Сначала пробуем загрузить из файла
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    config_data = yaml.safe_load(f)
                self._config = self._create_config_from_dict(config_data)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                self._config = self._create_default_config()
        else:
            # Создаем конфигурацию по умолчанию
            self._config = self._create_default_config()
            # Сохраняем в файл
            self.save_config(self._config)

        # Валидируем конфигурацию
        self._config.validate()

        return self._config

    def _create_config_from_dict(self, data: dict[str, Any]) -> RiskConfig:
        """Создание конфигурации из словаря"""
        return RiskConfig(
            default_risk_per_trade=data.get("default_risk_per_trade", 0.02),
            max_risk_per_trade=data.get("max_risk_per_trade", 0.05),
            daily_loss_limit=data.get("daily_loss_limit", 0.10),
            weekly_loss_limit=data.get("weekly_loss_limit", 0.20),
            max_concurrent_positions=data.get("max_concurrent_positions", 10),
            max_position_size_usdt=data.get("max_position_size_usdt", 10000.0),
            max_leverage=data.get("max_leverage", 20.0),
            cooldown_after_loss_sec=data.get("cooldown_after_loss_sec", 3600),
            cooldown_between_trades_sec=data.get("cooldown_between_trades_sec", 300),
            circuit_breaker_failure_threshold=data.get(
                "circuit_breaker_failure_threshold", 5
            ),
            circuit_breaker_timeout_sec=data.get("circuit_breaker_timeout_sec", 1800),
            circuit_breaker_half_open_max_calls=data.get(
                "circuit_breaker_half_open_max_calls", 3
            ),
            enable_killswitch=data.get("enable_killswitch", True),
            killswitch_auto_activate_on_loss=data.get(
                "killswitch_auto_activate_on_loss", 0.15
            ),
            min_data_quality_score=data.get("min_data_quality_score", 0.8),
            max_data_age_sec=data.get("max_data_age_sec", 300),
            max_latency_ms=data.get("max_latency_ms", 1000),
            min_throughput_per_min=data.get("min_throughput_per_min", 10),
            enable_alerts=data.get("enable_alerts", True),
            alert_channels=data.get("alert_channels", ["slack", "telegram"]),
        )

    def _create_default_config(self) -> RiskConfig:
        """Создание конфигурации по умолчанию"""
        return RiskConfig()

    def save_config(self, config: RiskConfig):
        """Сохранение конфигурации в файл"""
        config_data = {
            "default_risk_per_trade": config.default_risk_per_trade,
            "max_risk_per_trade": config.max_risk_per_trade,
            "daily_loss_limit": config.daily_loss_limit,
            "weekly_loss_limit": config.weekly_loss_limit,
            "max_concurrent_positions": config.max_concurrent_positions,
            "max_position_size_usdt": config.max_position_size_usdt,
            "max_leverage": config.max_leverage,
            "cooldown_after_loss_sec": config.cooldown_after_loss_sec,
            "cooldown_between_trades_sec": config.cooldown_between_trades_sec,
            "circuit_breaker_failure_threshold": config.circuit_breaker_failure_threshold,
            "circuit_breaker_timeout_sec": config.circuit_breaker_timeout_sec,
            "circuit_breaker_half_open_max_calls": config.circuit_breaker_half_open_max_calls,
            "enable_killswitch": config.enable_killswitch,
            "killswitch_auto_activate_on_loss": config.killswitch_auto_activate_on_loss,
            "min_data_quality_score": config.min_data_quality_score,
            "max_data_age_sec": config.max_data_age_sec,
            "max_latency_ms": config.max_latency_ms,
            "min_throughput_per_min": config.min_throughput_per_min,
            "enable_alerts": config.enable_alerts,
            "alert_channels": config.alert_channels,
        }

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            print(f"Warning: Failed to save config to {self.config_path}: {e}")

    def update_config(self, updates: dict[str, Any]) -> RiskConfig:
        """Обновление конфигурации"""
        current_config = self.load_config()

        # Обновляем поля
        for key, value in updates.items():
            if hasattr(current_config, key):
                setattr(current_config, key, value)

        # Валидируем обновленную конфигурацию
        current_config.validate()

        # Сохраняем
        self.save_config(current_config)

        return current_config

    def get_config(self) -> RiskConfig:
        """Получение текущей конфигурации"""
        return self.load_config()


# Глобальный экземпляр менеджера конфигурации
_config_manager: RiskConfigManager | None = None


def get_config_manager() -> RiskConfigManager:
    """Получение глобального менеджера конфигурации"""
    global _config_manager
    if _config_manager is None:
        _config_manager = RiskConfigManager()
    return _config_manager


def get_risk_config() -> RiskConfig:
    """Получение конфигурации рисков"""
    return get_config_manager().get_config()


def update_risk_config(updates: dict[str, Any]) -> RiskConfig:
    """Обновление конфигурации рисков"""
    return get_config_manager().update_config(updates)
