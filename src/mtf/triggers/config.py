"""
Конфигурация для Triggers Builder
"""

from pathlib import Path
from typing import Any

import yaml

from ..logging_config import get_triggers_logger

logger = get_triggers_logger()


class TriggersConfig:
    """Конфигурация для построения триггеров"""

    def __init__(self, config_data: dict[str, Any] | None = None):
        """Инициализация конфигурации"""
        if config_data is None:
            config_data = {}

        # Пороги для вероятностей
        self.min_probability_threshold = config_data.get(
            "min_probability_threshold", 0.3
        )
        self.max_probability_threshold = config_data.get(
            "max_probability_threshold", 0.9
        )

        # Веса для компонентов вероятности
        self.momentum_weight = config_data.get("momentum_weight", 0.3)
        self.volume_weight = config_data.get("volume_weight", 0.2)
        self.volatility_weight = config_data.get("volatility_weight", 0.2)
        self.support_resistance_weight = config_data.get(
            "support_resistance_weight", 0.15
        )
        self.pattern_weight = config_data.get("pattern_weight", 0.15)

        # Настройки ускорения
        self.acceleration_threshold = config_data.get("acceleration_threshold", 0.1)
        self.min_acceleration_periods = config_data.get("min_acceleration_periods", 3)

        # Настройки микро-фильтра
        self.micro_filter_threshold = config_data.get("micro_filter_threshold", 0.5)
        self.micro_filter_factors = config_data.get(
            "micro_filter_factors",
            ["volume_confirmation", "momentum_consistency", "volatility_check"],
        )

        # Настройки anti-noise фильтра
        self.noise_filter_threshold = config_data.get("noise_filter_threshold", 0.6)
        self.cluster_confirmation_periods = config_data.get(
            "cluster_confirmation_periods", 5
        )
        self.volume_spike_threshold = config_data.get("volume_spike_threshold", 1.5)

        # Настройки валидации
        self.min_data_points = config_data.get("min_data_points", 20)
        self.max_age_hours = config_data.get("max_age_hours", 24)

        # Настройки агрегации
        self.timeframe_weights = config_data.get(
            "timeframe_weights", {"15m": 1.0, "5m": 0.8, "1m": 0.6}
        )

        # Дополнительные настройки
        self.enable_logging = config_data.get("enable_logging", True)
        self.log_level = config_data.get("log_level", "INFO")
        self.cache_enabled = config_data.get("cache_enabled", True)
        self.cache_ttl_seconds = config_data.get("cache_ttl_seconds", 300)

        # Настройки производительности
        self.max_workers = config_data.get("max_workers", 4)
        self.timeout_seconds = config_data.get("timeout_seconds", 30.0)

        # Валидация конфигурации
        self._validate()

    def _validate(self) -> None:
        """Валидация конфигурации"""
        # Проверка весов
        total_weight = (
            self.momentum_weight
            + self.volume_weight
            + self.volatility_weight
            + self.support_resistance_weight
            + self.pattern_weight
        )

        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Sum of weights is {total_weight}, should be 1.0")

        # Проверка порогов вероятности
        if self.min_probability_threshold >= self.max_probability_threshold:
            raise ValueError(
                "min_probability_threshold must be less than max_probability_threshold"
            )

        if not 0.0 <= self.min_probability_threshold <= 1.0:
            raise ValueError("min_probability_threshold must be between 0.0 and 1.0")

        if not 0.0 <= self.max_probability_threshold <= 1.0:
            raise ValueError("max_probability_threshold must be between 0.0 and 1.0")

        # Проверка весов компонентов
        for weight_name, weight_value in [
            ("momentum_weight", self.momentum_weight),
            ("volume_weight", self.volume_weight),
            ("volatility_weight", self.volatility_weight),
            ("support_resistance_weight", self.support_resistance_weight),
            ("pattern_weight", self.pattern_weight),
        ]:
            if not 0.0 <= weight_value <= 1.0:
                raise ValueError(f"{weight_name} must be between 0.0 and 1.0")

        # Проверка настроек ускорения
        if not 0.0 <= self.acceleration_threshold <= 1.0:
            raise ValueError("acceleration_threshold must be between 0.0 and 1.0")

        if self.min_acceleration_periods < 1:
            raise ValueError("min_acceleration_periods must be at least 1")

        # Проверка настроек фильтров
        if not 0.0 <= self.micro_filter_threshold <= 1.0:
            raise ValueError("micro_filter_threshold must be between 0.0 and 1.0")

        if not 0.0 <= self.noise_filter_threshold <= 1.0:
            raise ValueError("noise_filter_threshold must be between 0.0 and 1.0")

        if self.cluster_confirmation_periods < 1:
            raise ValueError("cluster_confirmation_periods must be at least 1")

        if self.volume_spike_threshold < 1.0:
            raise ValueError("volume_spike_threshold must be at least 1.0")

        # Проверка настроек валидации
        if self.min_data_points < 1:
            raise ValueError("min_data_points must be at least 1")

        if self.max_age_hours < 1:
            raise ValueError("max_age_hours must be at least 1")

        # Проверка весов таймфреймов
        for timeframe, weight in self.timeframe_weights.items():
            if not 0.0 <= weight <= 1.0:
                raise ValueError(
                    f"Weight for timeframe {timeframe} must be between 0.0 and 1.0"
                )

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "TriggersConfig":
        """Загрузка конфигурации из YAML файла"""
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            if config_data is None:
                config_data = {}

            # Извлечение секции triggers если есть
            if "triggers" in config_data:
                config_data = config_data["triggers"]

            logger.info(f"Loaded triggers config from {config_path}")
            return cls(config_data)

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file {config_path}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {config_path}: {e}") from e

    def to_yaml(self, config_path: str | Path) -> None:
        """Сохранение конфигурации в YAML файл"""
        config_path = Path(config_path)

        config_data = {
            "triggers": {
                "min_probability_threshold": self.min_probability_threshold,
                "max_probability_threshold": self.max_probability_threshold,
                "momentum_weight": self.momentum_weight,
                "volume_weight": self.volume_weight,
                "volatility_weight": self.volatility_weight,
                "support_resistance_weight": self.support_resistance_weight,
                "pattern_weight": self.pattern_weight,
                "acceleration_threshold": self.acceleration_threshold,
                "min_acceleration_periods": self.min_acceleration_periods,
                "micro_filter_threshold": self.micro_filter_threshold,
                "micro_filter_factors": self.micro_filter_factors,
                "noise_filter_threshold": self.noise_filter_threshold,
                "cluster_confirmation_periods": self.cluster_confirmation_periods,
                "volume_spike_threshold": self.volume_spike_threshold,
                "min_data_points": self.min_data_points,
                "max_age_hours": self.max_age_hours,
                "timeframe_weights": self.timeframe_weights,
                "enable_logging": self.enable_logging,
                "log_level": self.log_level,
                "cache_enabled": self.cache_enabled,
                "cache_ttl_seconds": self.cache_ttl_seconds,
                "max_workers": self.max_workers,
                "timeout_seconds": self.timeout_seconds,
            }
        }

        try:
            # Создание директории если не существует
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"Saved triggers config to {config_path}")

        except Exception as e:
            raise RuntimeError(f"Failed to save config to {config_path}: {e}") from e

    def get_timeframe_weight(self, timeframe: str) -> float:
        """Получить вес таймфрейма"""
        return self.timeframe_weights.get(timeframe, 0.5)

    def update_config(self, updates: dict[str, Any]) -> None:
        """Обновление конфигурации"""
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning(f"Unknown config parameter: {key}")

        # Валидация после обновления
        self._validate()

    def to_dict(self) -> dict[str, Any]:
        """Преобразование конфигурации в словарь"""
        return {
            "min_probability_threshold": self.min_probability_threshold,
            "max_probability_threshold": self.max_probability_threshold,
            "momentum_weight": self.momentum_weight,
            "volume_weight": self.volume_weight,
            "volatility_weight": self.volatility_weight,
            "support_resistance_weight": self.support_resistance_weight,
            "pattern_weight": self.pattern_weight,
            "acceleration_threshold": self.acceleration_threshold,
            "min_acceleration_periods": self.min_acceleration_periods,
            "micro_filter_threshold": self.micro_filter_threshold,
            "micro_filter_factors": self.micro_filter_factors,
            "noise_filter_threshold": self.noise_filter_threshold,
            "cluster_confirmation_periods": self.cluster_confirmation_periods,
            "volume_spike_threshold": self.volume_spike_threshold,
            "min_data_points": self.min_data_points,
            "max_age_hours": self.max_age_hours,
            "timeframe_weights": self.timeframe_weights,
            "enable_logging": self.enable_logging,
            "log_level": self.log_level,
            "cache_enabled": self.cache_enabled,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "max_workers": self.max_workers,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def default(cls) -> "TriggersConfig":
        """Создание конфигурации по умолчанию"""
        return cls()

    @classmethod
    def for_production(cls) -> "TriggersConfig":
        """Создание конфигурации для продакшена"""
        config_data = {
            "min_probability_threshold": 0.4,
            "max_probability_threshold": 0.85,
            "momentum_weight": 0.35,
            "volume_weight": 0.25,
            "volatility_weight": 0.2,
            "support_resistance_weight": 0.1,
            "pattern_weight": 0.1,
            "acceleration_threshold": 0.15,
            "min_acceleration_periods": 5,
            "micro_filter_threshold": 0.6,
            "micro_filter_factors": [
                "volume_confirmation",
                "momentum_consistency",
                "volatility_check",
                "pattern_confirmation",
            ],
            "noise_filter_threshold": 0.7,
            "cluster_confirmation_periods": 7,
            "volume_spike_threshold": 2.0,
            "min_data_points": 50,
            "max_age_hours": 12,
            "enable_logging": True,
            "log_level": "WARNING",
            "cache_enabled": True,
            "cache_ttl_seconds": 180,
            "max_workers": 8,
            "timeout_seconds": 15.0,
        }
        return cls(config_data)

    @classmethod
    def for_development(cls) -> "TriggersConfig":
        """Создание конфигурации для разработки"""
        config_data = {
            "min_probability_threshold": 0.2,
            "max_probability_threshold": 0.95,
            "momentum_weight": 0.3,
            "volume_weight": 0.2,
            "volatility_weight": 0.2,
            "support_resistance_weight": 0.15,
            "pattern_weight": 0.15,
            "acceleration_threshold": 0.1,
            "min_acceleration_periods": 2,
            "micro_filter_threshold": 0.4,
            "micro_filter_factors": ["volume_confirmation", "momentum_consistency"],
            "noise_filter_threshold": 0.5,
            "cluster_confirmation_periods": 3,
            "volume_spike_threshold": 1.2,
            "min_data_points": 10,
            "max_age_hours": 48,
            "enable_logging": True,
            "log_level": "DEBUG",
            "cache_enabled": False,
            "cache_ttl_seconds": 60,
            "max_workers": 2,
            "timeout_seconds": 60.0,
        }
        return cls(config_data)
