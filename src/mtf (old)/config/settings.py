#!/usr/bin/env python3
"""
MTF Configuration Management

Централизованное управление конфигурацией для MTF модуля с валидацией,
версионированием и поддержкой окружений.
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class TimeframeType(Enum):
    """Поддерживаемые таймфреймы"""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class HorizonType(Enum):
    """Торговые горизонты"""

    INTRADAY = "intraday"
    SWING = "swing"
    WEEK = "week"


class ConsensusMode(Enum):
    """Режимы консенсуса"""

    INTRADAY = "intraday"
    SWING = "swing"
    WEEK = "week"
    HYBRID = "hybrid"


@dataclass
class TimeframeConfig:
    """Конфигурация таймфрейма"""

    name: str
    minutes: int
    utc_offset: int = 0  # Смещение UTC в минутах
    weight: float = 1.0  # Вес в консенсусе
    min_bars: int = 100  # Минимум баров для анализа
    max_age_hours: int = 24  # Максимальный возраст данных


@dataclass
class IndicatorConfig:
    """Конфигурация индикаторов"""

    # Трендовые индикаторы
    ema_periods: list[int] = field(default_factory=lambda: [21, 50, 200])
    sma_periods: list[int] = field(default_factory=lambda: [20, 50, 200])
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Осцилляторы
    rsi_period: int = 14
    stoch_k: int = 14
    stoch_d: int = 3

    # Волатильность
    atr_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0

    # Объем
    vwap_period: int = 20
    volume_sma_period: int = 20


@dataclass
class ConsensusConfig:
    """Конфигурация консенсуса"""

    mode: ConsensusMode = ConsensusMode.HYBRID
    min_agreement: float = 0.6  # Минимум согласия между TF
    veto_threshold: float = 0.8  # Порог для вето
    disagreement_penalty: float = 0.3  # Штраф за разногласия

    # Веса для разных горизонтов
    intraday_weight: float = 0.4
    swing_weight: float = 0.4
    week_weight: float = 0.2

    # Пороги для режимов
    trend_threshold: float = 0.6
    flat_threshold: float = 0.3
    volatility_threshold: float = 0.7


@dataclass
class RiskConfig:
    """Конфигурация риск-менеджмента"""

    max_position_size: float = 0.02  # 2% от капитала
    max_correlated_positions: int = 3
    daily_loss_limit: float = 0.05  # 5% дневной лимит
    max_leverage: float = 3.0
    min_risk_reward: float = 1.5  # Минимум R:R

    # Стоп-лоссы
    default_stop_atr: float = 2.0
    max_stop_percent: float = 0.05  # 5% максимум
    time_stop_hours: int = 24  # Временной стоп для intraday

    # Take-profit
    default_take_atr: float = 3.0
    trailing_stop: bool = True
    trailing_distance: float = 1.5


@dataclass
class DataQualityConfig:
    """Конфигурация качества данных"""

    max_data_age_minutes: int = 30
    min_valid_rate: float = 0.95  # 95% валидных данных
    max_nan_rate: float = 0.05  # 5% максимум NaN
    lookback_hours: int = 24  # Период для проверки качества

    # Алерты
    alert_latency_threshold: int = 5  # минут
    alert_volume_spike: float = 3.0  # x3 от среднего
    alert_spread_widening: float = 2.0  # x2 от среднего


@dataclass
class ExchangeConfig:
    """Конфигурация биржи"""

    name: str = "OKX"
    api_timeout: int = 30
    rate_limit_per_minute: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0

    # Комиссии
    maker_fee: float = 0.0008  # 0.08%
    taker_fee: float = 0.001  # 0.1%

    # Минимальные размеры
    min_notional: float = 5.0  # USDT
    min_order_size: float = 0.001  # BTC


@dataclass
class MTFConfig:
    """Основная конфигурация MTF"""

    # Версионирование
    version: str = "1.0.0"
    schema_version: str = "v1"

    # Таймфреймы
    timeframes: dict[str, TimeframeConfig] = field(default_factory=dict)

    # Индикаторы
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)

    # Консенсус
    consensus: ConsensusConfig = field(default_factory=ConsensusConfig)

    # Риск-менеджмент
    risk: RiskConfig = field(default_factory=RiskConfig)

    # Качество данных
    data_quality: DataQualityConfig = field(default_factory=DataQualityConfig)

    # Биржа
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)

    # Экспериментальные флаги
    use_accel_v2: bool = False
    enable_lookahead_guard: bool = True
    enable_circuit_breaker: bool = True

    # Логирование
    log_level: str = "INFO"
    enable_metrics: bool = True
    enable_alerts: bool = True


class ConfigManager:
    """Менеджер конфигурации"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        self._validate_config()

    def _get_default_config_path(self) -> str:
        """Получить путь к конфигурации по умолчанию"""
        base_path = Path(__file__).parent.parent.parent.parent
        return str(base_path / "config" / "mtf_config.yaml")

    def _load_config(self) -> MTFConfig:
        """Загрузить конфигурацию из файла или создать по умолчанию"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    config_data = yaml.safe_load(f)
                return self._dict_to_config(config_data)
            except Exception as e:
                logger.warning(f"Ошибка загрузки конфига {self.config_path}: {e}")
                logger.info("Используется конфигурация по умолчанию")

        return self._create_default_config()

    def _create_default_config(self) -> MTFConfig:
        """Создать конфигурацию по умолчанию"""
        config = MTFConfig()

        # Настройка таймфреймов
        config.timeframes = {
            "1m": TimeframeConfig("1m", 1, weight=0.1, min_bars=100),
            "5m": TimeframeConfig("5m", 5, weight=0.15, min_bars=100),
            "15m": TimeframeConfig("15m", 15, weight=0.2, min_bars=100),
            "30m": TimeframeConfig("30m", 30, weight=0.25, min_bars=100),
            "1h": TimeframeConfig("1h", 60, weight=0.3, min_bars=100),
            "4h": TimeframeConfig("4h", 240, weight=0.4, min_bars=100),
            "1d": TimeframeConfig("1d", 1440, weight=0.5, min_bars=100),
            "1w": TimeframeConfig("1w", 10080, weight=0.6, min_bars=50),
        }

        return config

    def _dict_to_config(self, data: dict[str, Any]) -> MTFConfig:
        """Преобразовать словарь в конфигурацию"""
        # Простая реализация - можно расширить
        config = MTFConfig()

        if "version" in data:
            config.version = data["version"]
        if "schema_version" in data:
            config.schema_version = data["schema_version"]

        # Добавить другие поля по мере необходимости

        return config

    def _validate_config(self):
        """Валидация конфигурации"""
        if not self.config.timeframes:
            raise ValueError("Должен быть указан хотя бы один таймфрейм")

        if (
            self.config.consensus.min_agreement <= 0
            or self.config.consensus.min_agreement > 1
        ):
            raise ValueError("min_agreement должен быть в диапазоне (0, 1]")

        if (
            self.config.risk.max_position_size <= 0
            or self.config.risk.max_position_size > 1
        ):
            raise ValueError("max_position_size должен быть в диапазоне (0, 1]")

    def save_config(self, path: str | None = None):
        """Сохранить конфигурацию в файл"""
        save_path = path or self.config_path

        # Создать директорию если не существует
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        config_dict = self._config_to_dict()

        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Конфигурация сохранена в {save_path}")

    def _config_to_dict(self) -> dict[str, Any]:
        """Преобразовать конфигурацию в словарь"""
        return {
            "version": self.config.version,
            "schema_version": self.config.schema_version,
            "consensus": {
                "mode": self.config.consensus.mode.value,
                "min_agreement": self.config.consensus.min_agreement,
                "veto_threshold": self.config.consensus.veto_threshold,
            },
            "risk": {
                "max_position_size": self.config.risk.max_position_size,
                "daily_loss_limit": self.config.risk.daily_loss_limit,
                "max_leverage": self.config.risk.max_leverage,
            },
            "data_quality": {
                "max_data_age_minutes": self.config.data_quality.max_data_age_minutes,
                "min_valid_rate": self.config.data_quality.min_valid_rate,
            },
            "exchange": {
                "name": self.config.exchange.name,
                "maker_fee": self.config.exchange.maker_fee,
                "taker_fee": self.config.exchange.taker_fee,
            },
        }

    def get_timeframe_config(self, timeframe: str) -> TimeframeConfig | None:
        """Получить конфигурацию таймфрейма"""
        return self.config.timeframes.get(timeframe)

    def get_all_timeframes(self) -> list[str]:
        """Получить список всех таймфреймов"""
        return list(self.config.timeframes.keys())

    def get_horizon_timeframes(self, horizon: HorizonType) -> list[str]:
        """Получить таймфреймы для конкретного горизонта"""
        if horizon == HorizonType.INTRADAY:
            return ["1m", "5m", "15m", "30m"]
        if horizon == HorizonType.SWING:
            return ["1h", "4h", "1d"]
        if horizon == HorizonType.WEEK:
            return ["1d", "1w"]
        return self.get_all_timeframes()


# Глобальный экземпляр конфигурации
config_manager = ConfigManager()
mtf_config = config_manager.config
