"""
Конфигурация для Consensus модуля
"""

from pathlib import Path

import yaml

from .models import ConsensusConfig


class ConsensusConfigManager:
    """Менеджер конфигурации консенсуса"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self._config: ConsensusConfig | None = None

    def load_config(self, config_path: str | None = None) -> ConsensusConfig:
        """Загрузка конфигурации из файла"""
        if config_path:
            self.config_path = config_path

        if self.config_path and Path(self.config_path).exists():
            return self._load_from_file(self.config_path)
        return self._get_default_config()

    def _load_from_file(self, config_path: str) -> ConsensusConfig:
        """Загрузка конфигурации из YAML файла"""
        try:
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            return ConsensusConfig(
                context_weight=config_data.get("context_weight", 0.4),
                triggers_weight=config_data.get("triggers_weight", 0.6),
                strong_bullish_threshold=config_data.get(
                    "strong_bullish_threshold", 0.7
                ),
                bullish_threshold=config_data.get("bullish_threshold", 0.3),
                bearish_threshold=config_data.get("bearish_threshold", -0.3),
                strong_bearish_threshold=config_data.get(
                    "strong_bearish_threshold", -0.7
                ),
                very_high_confidence=config_data.get("very_high_confidence", 0.9),
                high_confidence=config_data.get("high_confidence", 0.7),
                medium_confidence=config_data.get("medium_confidence", 0.5),
                low_confidence=config_data.get("low_confidence", 0.3),
                conflict_threshold=config_data.get("conflict_threshold", 0.2),
                min_confidence_for_consensus=config_data.get(
                    "min_confidence_for_consensus", 0.4
                ),
                timeframe_weights=config_data.get(
                    "timeframe_weights",
                    {"15m": 1.0, "5m": 0.8, "1m": 0.6, "1H": 1.2, "4H": 1.5, "1D": 2.0},
                ),
                min_data_points=config_data.get("min_data_points", 5),
                max_age_hours=config_data.get("max_age_hours", 24),
                enable_timeframe_aggregation=config_data.get(
                    "enable_timeframe_aggregation", True
                ),
                enable_confidence_boost=config_data.get(
                    "enable_confidence_boost", True
                ),
                confidence_boost_factor=config_data.get("confidence_boost_factor", 1.2),
                enable_logging=config_data.get("enable_logging", True),
                log_level=config_data.get("log_level", "INFO"),
                cache_enabled=config_data.get("cache_enabled", False),
                cache_ttl_seconds=config_data.get("cache_ttl_seconds", 300),
                max_workers=config_data.get("max_workers", 4),
                timeout_seconds=config_data.get("timeout_seconds", 30.0),
            )
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> ConsensusConfig:
        """Получение конфигурации по умолчанию"""
        return ConsensusConfig()

    def save_config(
        self, config: ConsensusConfig, config_path: str | None = None
    ) -> bool:
        """Сохранение конфигурации в файл"""
        if config_path:
            self.config_path = config_path

        if not self.config_path:
            return False

        try:
            config_data = {
                "context_weight": config.context_weight,
                "triggers_weight": config.triggers_weight,
                "strong_bullish_threshold": config.strong_bullish_threshold,
                "bullish_threshold": config.bullish_threshold,
                "bearish_threshold": config.bearish_threshold,
                "strong_bearish_threshold": config.strong_bearish_threshold,
                "very_high_confidence": config.very_high_confidence,
                "high_confidence": config.high_confidence,
                "medium_confidence": config.medium_confidence,
                "low_confidence": config.low_confidence,
                "conflict_threshold": config.conflict_threshold,
                "min_confidence_for_consensus": config.min_confidence_for_consensus,
                "timeframe_weights": config.timeframe_weights,
                "min_data_points": config.min_data_points,
                "max_age_hours": config.max_age_hours,
                "enable_timeframe_aggregation": config.enable_timeframe_aggregation,
                "enable_confidence_boost": config.enable_confidence_boost,
                "confidence_boost_factor": config.confidence_boost_factor,
                "enable_logging": config.enable_logging,
                "log_level": config.log_level,
                "cache_enabled": config.cache_enabled,
                "cache_ttl_seconds": config.cache_ttl_seconds,
                "max_workers": config.max_workers,
                "timeout_seconds": config.timeout_seconds,
            }

            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

            return True
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")
            return False

    def get_config(self) -> ConsensusConfig:
        """Получение текущей конфигурации"""
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def update_config(self, **kwargs) -> ConsensusConfig:
        """Обновление конфигурации"""
        current_config = self.get_config()

        # Создаем новый объект конфигурации с обновленными значениями
        config_dict = {
            "context_weight": current_config.context_weight,
            "triggers_weight": current_config.triggers_weight,
            "strong_bullish_threshold": current_config.strong_bullish_threshold,
            "bullish_threshold": current_config.bullish_threshold,
            "bearish_threshold": current_config.bearish_threshold,
            "strong_bearish_threshold": current_config.strong_bearish_threshold,
            "very_high_confidence": current_config.very_high_confidence,
            "high_confidence": current_config.high_confidence,
            "medium_confidence": current_config.medium_confidence,
            "low_confidence": current_config.low_confidence,
            "conflict_threshold": current_config.conflict_threshold,
            "min_confidence_for_consensus": current_config.min_confidence_for_consensus,
            "timeframe_weights": current_config.timeframe_weights,
            "min_data_points": current_config.min_data_points,
            "max_age_hours": current_config.max_age_hours,
            "enable_timeframe_aggregation": current_config.enable_timeframe_aggregation,
            "enable_confidence_boost": current_config.enable_confidence_boost,
            "confidence_boost_factor": current_config.confidence_boost_factor,
            "enable_logging": current_config.enable_logging,
            "log_level": current_config.log_level,
            "cache_enabled": current_config.cache_enabled,
            "cache_ttl_seconds": current_config.cache_ttl_seconds,
            "max_workers": current_config.max_workers,
            "timeout_seconds": current_config.timeout_seconds,
        }

        # Обновляем переданные параметры
        config_dict.update(kwargs)

        # Создаем новую конфигурацию
        self._config = ConsensusConfig(**config_dict)
        return self._config


# Глобальный менеджер конфигурации
_config_manager = ConsensusConfigManager()


def get_consensus_config(config_path: str | None = None) -> ConsensusConfig:
    """Получение конфигурации консенсуса"""
    if config_path:
        return _config_manager.load_config(config_path)
    return _config_manager.get_config()


def update_consensus_config(**kwargs) -> ConsensusConfig:
    """Обновление конфигурации консенсуса"""
    return _config_manager.update_config(**kwargs)


def save_consensus_config(config: ConsensusConfig, config_path: str) -> bool:
    """Сохранение конфигурации консенсуса"""
    return _config_manager.save_config(config, config_path)
