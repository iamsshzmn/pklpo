"""
Configuration module for features calculation.

MIGRATED: Теперь использует централизованную конфигурацию из src.config.
Обратная совместимость сохранена - все старые классы и функции работают.

Рекомендуемый новый подход:
    from src.config import get_settings
    settings = get_settings()
    batch_size = settings.features.batch_size
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

from src.config import get_settings


# =============================================================================
# STREAMING CONFIG
# =============================================================================


@dataclass
class StreamingConfig:
    """
    Configuration for streaming feature calculation.

    DEPRECATED: Используйте `get_settings().features` напрямую.

    Этот класс сохранён для обратной совместимости.
    Значения берутся из централизованной конфигурации.
    """

    # Эти значения будут переопределены в __post_init__
    CHUNKSIZE: int = 200_000
    MAX_LOOKBACK: int = 200
    OVERLAP_SIZE: int = 200
    INSERT_CHUNKSIZE: int = 50_000
    ON_CONFLICT_KEYS: list[str] = field(
        default_factory=lambda: ["symbol", "timeframe", "timestamp"]
    )
    FORCE_GC_AFTER_CHUNK: bool = True
    CLEAR_INTERMEDIATE_OBJECTS: bool = True
    PARALLEL_WORKERS: int = 4
    BATCH_TIMEOUT_SECONDS: int = 300
    ENABLE_VOLATILITY_NORMALIZE: bool = True
    LOG_MEMORY_USAGE: bool = True
    LOG_DF_SHAPES: bool = True
    VERBOSE_LOGGING: bool = False

    def __post_init__(self):
        """Загружает значения из централизованной конфигурации."""
        settings = get_settings().features

        self.CHUNKSIZE = settings.chunk_size
        self.MAX_LOOKBACK = settings.max_lookback
        self.OVERLAP_SIZE = settings.overlap_size
        self.INSERT_CHUNKSIZE = settings.insert_chunk_size
        self.PARALLEL_WORKERS = settings.parallel_workers
        self.BATCH_TIMEOUT_SECONDS = settings.batch_timeout
        self.ENABLE_VOLATILITY_NORMALIZE = settings.volatility_normalize
        self.LOG_MEMORY_USAGE = settings.log_memory
        self.VERBOSE_LOGGING = settings.verbose

        # Ensure overlap is at least as large as max lookback
        if self.OVERLAP_SIZE < self.MAX_LOOKBACK:
            self.OVERLAP_SIZE = self.MAX_LOOKBACK


# =============================================================================
# DATABASE CONFIG
# =============================================================================


@dataclass
class DatabaseConfig:
    """
    Configuration for database operations.

    DEPRECATED: Используйте `get_settings().features` и `get_settings().db` напрямую.

    Этот класс сохранён для обратной совместимости.
    """

    CONNECTION_POOL_SIZE: int = 10
    CONNECTION_TIMEOUT: int = 30
    QUERY_TIMEOUT: int = 300
    BATCH_SIZE: int = 50_000
    COMMIT_FREQUENCY: int = 1000
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    RETRY_BACKOFF_FACTOR: float = 2.0
    USE_COPY_FROM: bool = True
    TEMP_TABLE_PREFIX: str = "temp_indicators_"
    LOG_QUERY_TIMES: bool = True
    LOG_BATCH_STATS: bool = True
    LOG_MEMORY_USAGE: bool = False
    CLEAR_INTERMEDIATE_OBJECTS: bool = True
    FORCE_GC_AFTER_CHUNK: bool = False

    def __post_init__(self):
        """Загружает значения из централизованной конфигурации."""
        settings = get_settings()

        self.CONNECTION_POOL_SIZE = settings.db.pool_size
        self.CONNECTION_TIMEOUT = settings.db.pool_timeout
        self.BATCH_SIZE = settings.features.batch_size
        self.LOG_MEMORY_USAGE = settings.features.log_memory


# =============================================================================
# FEATURE CONFIG
# =============================================================================


@dataclass
class FeatureConfig:
    """
    Configuration for feature calculation.

    DEPRECATED: Используйте `get_settings().features` напрямую.

    Этот класс сохранён для обратной совместимости.
    """

    ENABLE_VOLATILITY_NORMALIZE: bool = True
    NORMALIZE_WINDOW: int = 20
    NORMALIZE_METHOD: str = "rolling_std"
    MIN_DATA_POINTS: int = 20
    MAX_FEATURES_PER_CHUNK: int = 1000
    MIN_FILL_RATE: float = 0.5
    VALIDATE_RESULTS: bool = True
    USE_VECTORIZED_OPERATIONS: bool = True
    CACHE_INTERMEDIATE_RESULTS: bool = False

    def __post_init__(self):
        """Загружает значения из централизованной конфигурации."""
        settings = get_settings().features

        self.ENABLE_VOLATILITY_NORMALIZE = settings.volatility_normalize
        self.NORMALIZE_WINDOW = settings.normalize_window
        self.MIN_FILL_RATE = settings.min_fill_rate
        self.VALIDATE_RESULTS = settings.validate_results


# =============================================================================
# FACTORY FUNCTIONS (обратная совместимость)
# =============================================================================


def load_config_from_env() -> dict[str, Any]:
    """
    Load configuration from environment variables.

    DEPRECATED: Используйте `get_settings()` напрямую.

    Returns:
        Dictionary with configuration values from centralized settings.
    """
    settings = get_settings()
    f = settings.features

    return {
        "CHUNKSIZE": f.chunk_size,
        "MAX_LOOKBACK": f.max_lookback,
        "INSERT_CHUNKSIZE": f.insert_chunk_size,
        "BATCH_SIZE": f.batch_size,
        "MAX_RETRIES": 3,  # Hardcoded, not in features settings
        "ENABLE_VOLATILITY_NORMALIZE": f.volatility_normalize,
        "MIN_FILL_RATE": f.min_fill_rate,
        "LOG_MEMORY_USAGE": f.log_memory,
        "VERBOSE_LOGGING": f.verbose,
    }


def create_streaming_config(**overrides) -> StreamingConfig:
    """
    Create streaming configuration with optional overrides.

    DEPRECATED: Используйте `get_settings().features` напрямую.

    Args:
        **overrides: Override specific configuration values

    Returns:
        StreamingConfig instance
    """
    config = StreamingConfig()

    # Apply explicit overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


def create_database_config(**overrides) -> DatabaseConfig:
    """
    Create database configuration with optional overrides.

    DEPRECATED: Используйте `get_settings().db` и `get_settings().features` напрямую.

    Args:
        **overrides: Override specific configuration values

    Returns:
        DatabaseConfig instance
    """
    config = DatabaseConfig()

    # Apply explicit overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


def create_feature_config(**overrides) -> FeatureConfig:
    """
    Create feature configuration with optional overrides.

    DEPRECATED: Используйте `get_settings().features` напрямую.

    Args:
        **overrides: Override specific configuration values

    Returns:
        FeatureConfig instance
    """
    config = FeatureConfig()

    # Apply explicit overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


# =============================================================================
# DEFAULT INSTANCES (обратная совместимость)
# =============================================================================

# Lazy initialization to avoid circular imports
_default_streaming_config: StreamingConfig | None = None
_default_database_config: DatabaseConfig | None = None
_default_feature_config: FeatureConfig | None = None


def _get_default_streaming_config() -> StreamingConfig:
    global _default_streaming_config
    if _default_streaming_config is None:
        _default_streaming_config = StreamingConfig()
    return _default_streaming_config


def _get_default_database_config() -> DatabaseConfig:
    global _default_database_config
    if _default_database_config is None:
        _default_database_config = DatabaseConfig()
    return _default_database_config


def _get_default_feature_config() -> FeatureConfig:
    global _default_feature_config
    if _default_feature_config is None:
        _default_feature_config = FeatureConfig()
    return _default_feature_config


# Properties for lazy access
class _DefaultConfigs:
    """Lazy container for default configurations."""

    @property
    def DEFAULT_STREAMING_CONFIG(self) -> StreamingConfig:
        return _get_default_streaming_config()

    @property
    def DEFAULT_DATABASE_CONFIG(self) -> DatabaseConfig:
        return _get_default_database_config()

    @property
    def DEFAULT_FEATURE_CONFIG(self) -> FeatureConfig:
        return _get_default_feature_config()


_defaults = _DefaultConfigs()

# For backward compatibility - these are now properties
DEFAULT_STREAMING_CONFIG = property(lambda self: _get_default_streaming_config())
DEFAULT_DATABASE_CONFIG = property(lambda self: _get_default_database_config())
DEFAULT_FEATURE_CONFIG = property(lambda self: _get_default_feature_config())


# =============================================================================
# CLI SUPPORT
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Features configuration")
    parser.add_argument("--show", action="store_true", help="Show current configuration")
    parser.add_argument("--env", action="store_true", help="Show environment variables")
    parser.add_argument(
        "--new", action="store_true", help="Show new centralized config approach"
    )

    args = parser.parse_args()

    if args.show:
        streaming = create_streaming_config()
        database = create_database_config()
        feature = create_feature_config()

        print("Streaming Configuration:")
        print(f"  CHUNKSIZE: {streaming.CHUNKSIZE}")
        print(f"  MAX_LOOKBACK: {streaming.MAX_LOOKBACK}")
        print(f"  INSERT_CHUNKSIZE: {streaming.INSERT_CHUNKSIZE}")
        print(f"  OVERLAP_SIZE: {streaming.OVERLAP_SIZE}")

        print("\nDatabase Configuration:")
        print(f"  BATCH_SIZE: {database.BATCH_SIZE}")
        print(f"  MAX_RETRIES: {database.MAX_RETRIES}")
        print(f"  USE_COPY_FROM: {database.USE_COPY_FROM}")

        print("\nFeature Configuration:")
        print(f"  ENABLE_VOLATILITY_NORMALIZE: {feature.ENABLE_VOLATILITY_NORMALIZE}")
        print(f"  MIN_FILL_RATE: {feature.MIN_FILL_RATE}")
        print(f"  VALIDATE_RESULTS: {feature.VALIDATE_RESULTS}")

    if args.env:
        env_config = load_config_from_env()
        print("Environment Configuration (from centralized settings):")
        for key, value in env_config.items():
            print(f"  {key}: {value}")

    if args.new:
        settings = get_settings()
        print("New Centralized Configuration:")
        print(f"\n  from src.config import get_settings")
        print(f"  settings = get_settings()")
        print(f"\n  # Features")
        print(f"  settings.features.chunk_size = {settings.features.chunk_size}")
        print(f"  settings.features.batch_size = {settings.features.batch_size}")
        print(f"  settings.features.min_fill_rate = {settings.features.min_fill_rate}")
        print(f"\n  # Database")
        print(f"  settings.db.pool_size = {settings.db.pool_size}")
        print(f"  settings.db.async_url = {settings.db.host}:***@{settings.db.port}")
