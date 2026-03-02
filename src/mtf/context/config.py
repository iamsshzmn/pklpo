"""
Конфигурация для Context Builder
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ContextConfig:
    """Конфигурация для построения контекста"""

    def __init__(self, config_data: dict[str, Any] | None = None):
        """Инициализация конфигурации"""
        if config_data is None:
            config_data = {}

        # Пороги для определения режимов
        self.trend_threshold = config_data.get("trend_threshold", 0.3)
        self.flat_threshold = config_data.get("flat_threshold", 0.1)

        # Веса для компонентов score
        self.ema_weight = config_data.get("ema_weight", 0.3)
        self.adx_weight = config_data.get("adx_weight", 0.2)
        self.rsi_weight = config_data.get("rsi_weight", 0.2)
        self.macd_weight = config_data.get("macd_weight", 0.2)
        self.volume_weight = config_data.get("volume_weight", 0.1)

        # Пороги для индикаторов
        self.adx_strong_trend = config_data.get("adx_strong_trend", 25.0)
        self.adx_weak_trend = config_data.get("adx_weak_trend", 15.0)
        self.rsi_oversold = config_data.get("rsi_oversold", 30.0)
        self.rsi_overbought = config_data.get("rsi_overbought", 70.0)

        # Настройки валидации
        self.min_data_points = config_data.get("min_data_points", 20)
        self.max_age_hours = config_data.get("max_age_hours", 24)

        # Настройки агрегации
        self.timeframe_weights = config_data.get(
            "timeframe_weights", {"1Dutc": 1.0, "4H": 0.8, "1H": 0.6, "15m": 0.4}
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
            self.ema_weight
            + self.adx_weight
            + self.rsi_weight
            + self.macd_weight
            + self.volume_weight
        )

        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Sum of weights is {total_weight}, should be 1.0")

        # Проверка порогов
        if self.trend_threshold <= self.flat_threshold:
            raise ValueError("trend_threshold must be greater than flat_threshold")

        if not 0.0 <= self.trend_threshold <= 1.0:
            raise ValueError("trend_threshold must be between 0.0 and 1.0")

        if not 0.0 <= self.flat_threshold <= 1.0:
            raise ValueError("flat_threshold must be between 0.0 and 1.0")

        # Проверка весов компонентов
        for weight_name, weight_value in [
            ("ema_weight", self.ema_weight),
            ("adx_weight", self.adx_weight),
            ("rsi_weight", self.rsi_weight),
            ("macd_weight", self.macd_weight),
            ("volume_weight", self.volume_weight),
        ]:
            if not 0.0 <= weight_value <= 1.0:
                raise ValueError(f"{weight_name} must be between 0.0 and 1.0")

        # Проверка порогов индикаторов
        if self.adx_strong_trend <= self.adx_weak_trend:
            raise ValueError("adx_strong_trend must be greater than adx_weak_trend")

        if not 0.0 <= self.rsi_oversold <= 50.0:
            raise ValueError("rsi_oversold must be between 0.0 and 50.0")

        if not 50.0 <= self.rsi_overbought <= 100.0:
            raise ValueError("rsi_overbought must be between 50.0 and 100.0")

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
    def from_yaml(cls, config_path: str | Path) -> "ContextConfig":
        """Загрузка конфигурации из YAML файла"""
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            if config_data is None:
                config_data = {}

            # Извлечение секции context если есть
            if "context" in config_data:
                config_data = config_data["context"]

            logger.info(f"Loaded context config from {config_path}")
            return cls(config_data)

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file {config_path}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {config_path}: {e}") from e

    def to_yaml(self, config_path: str | Path) -> None:
        """Сохранение конфигурации в YAML файл"""
        config_path = Path(config_path)

        config_data = {
            "context": {
                "trend_threshold": self.trend_threshold,
                "flat_threshold": self.flat_threshold,
                "ema_weight": self.ema_weight,
                "adx_weight": self.adx_weight,
                "rsi_weight": self.rsi_weight,
                "macd_weight": self.macd_weight,
                "volume_weight": self.volume_weight,
                "adx_strong_trend": self.adx_strong_trend,
                "adx_weak_trend": self.adx_weak_trend,
                "rsi_oversold": self.rsi_oversold,
                "rsi_overbought": self.rsi_overbought,
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

            logger.info(f"Saved context config to {config_path}")

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
            "trend_threshold": self.trend_threshold,
            "flat_threshold": self.flat_threshold,
            "ema_weight": self.ema_weight,
            "adx_weight": self.adx_weight,
            "rsi_weight": self.rsi_weight,
            "macd_weight": self.macd_weight,
            "volume_weight": self.volume_weight,
            "adx_strong_trend": self.adx_strong_trend,
            "adx_weak_trend": self.adx_weak_trend,
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought,
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
    def default(cls) -> "ContextConfig":
        """Создание конфигурации по умолчанию"""
        return cls()

    @classmethod
    def for_production(cls) -> "ContextConfig":
        """Создание конфигурации для продакшена"""
        config_data = {
            "trend_threshold": 0.25,
            "flat_threshold": 0.08,
            "ema_weight": 0.35,
            "adx_weight": 0.25,
            "rsi_weight": 0.2,
            "macd_weight": 0.15,
            "volume_weight": 0.05,
            "adx_strong_trend": 30.0,
            "adx_weak_trend": 20.0,
            "rsi_oversold": 25.0,
            "rsi_overbought": 75.0,
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
    def for_development(cls) -> "ContextConfig":
        """Создание конфигурации для разработки"""
        config_data = {
            "trend_threshold": 0.4,
            "flat_threshold": 0.15,
            "ema_weight": 0.3,
            "adx_weight": 0.2,
            "rsi_weight": 0.2,
            "macd_weight": 0.2,
            "volume_weight": 0.1,
            "adx_strong_trend": 20.0,
            "adx_weak_trend": 10.0,
            "rsi_oversold": 35.0,
            "rsi_overbought": 65.0,
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
