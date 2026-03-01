"""
Configuration module for features calculation.

DEPRECATED: This module is deprecated. Use src.config.get_settings() directly.

Migration guide:
    # OLD:
    from src.features.config import create_streaming_config
    config = create_streaming_config()
    chunk_size = config.CHUNKSIZE

    # NEW:
    from src.config import get_settings
    settings = get_settings()
    chunk_size = settings.features.chunk_size
"""

from __future__ import annotations

import warnings
from typing import Any

from src.config import FeaturesSettings, get_settings


def _emit_deprecation_warning(func_name: str) -> None:
    """Emit deprecation warning for legacy config functions."""
    warnings.warn(
        f"{func_name}() is deprecated. Use get_settings().features directly. "
        "See src.config for the new configuration approach.",
        DeprecationWarning,
        stacklevel=3,
    )


# =============================================================================
# LEGACY ADAPTER FUNCTIONS (deprecated, for backward compatibility only)
# =============================================================================


def load_config_from_env() -> dict[str, Any]:
    """
    Load configuration from environment variables.

    DEPRECATED: Use get_settings() directly.
    """
    _emit_deprecation_warning("load_config_from_env")
    f = get_settings().features

    return {
        "CHUNKSIZE": f.chunk_size,
        "MAX_LOOKBACK": f.max_lookback,
        "INSERT_CHUNKSIZE": f.insert_chunk_size,
        "BATCH_SIZE": f.batch_size,
        "MAX_RETRIES": f.max_retries,
        "ENABLE_VOLATILITY_NORMALIZE": f.volatility_normalize,
        "MIN_FILL_RATE": f.min_fill_rate,
        "LOG_MEMORY_USAGE": f.log_memory,
        "VERBOSE_LOGGING": f.verbose,
    }


def create_streaming_config(**overrides) -> FeaturesSettings:
    """
    Create streaming configuration with optional overrides.

    DEPRECATED: Use get_settings().features directly.
    For custom settings, create a new FeaturesSettings instance.

    Args:
        **overrides: Override specific configuration values (use lowercase keys)

    Returns:
        FeaturesSettings instance
    """
    _emit_deprecation_warning("create_streaming_config")

    base = get_settings().features

    # Map old UPPERCASE keys to new lowercase keys
    key_mapping = {
        "CHUNKSIZE": "chunk_size",
        "MAX_LOOKBACK": "max_lookback",
        "OVERLAP_SIZE": "overlap_size",
        "INSERT_CHUNKSIZE": "insert_chunk_size",
        "FORCE_GC_AFTER_CHUNK": "force_gc_after_chunk",
        "CLEAR_INTERMEDIATE_OBJECTS": "clear_intermediate_objects",
        "PARALLEL_WORKERS": "parallel_workers",
        "BATCH_TIMEOUT_SECONDS": "batch_timeout",
        "ENABLE_VOLATILITY_NORMALIZE": "volatility_normalize",
        "LOG_MEMORY_USAGE": "log_memory",
        "VERBOSE_LOGGING": "verbose",
    }

    # Normalize overrides
    normalized = {}
    for key, value in overrides.items():
        new_key = key_mapping.get(key, key.lower())
        normalized[new_key] = value

    if normalized:
        # Create new instance with overrides
        return FeaturesSettings(**{**base.model_dump(), **normalized})

    return base


def create_database_config(**overrides) -> FeaturesSettings:
    """
    Create database configuration with optional overrides.

    DEPRECATED: Use get_settings().features and get_settings().db directly.

    Args:
        **overrides: Override specific configuration values

    Returns:
        FeaturesSettings instance
    """
    _emit_deprecation_warning("create_database_config")

    base = get_settings().features

    # Map old UPPERCASE keys to new lowercase keys
    key_mapping = {
        "BATCH_SIZE": "batch_size",
        "MAX_RETRIES": "max_retries",
        "RETRY_DELAY": "retry_delay",
        "RETRY_BACKOFF_FACTOR": "retry_backoff_factor",
        "USE_COPY_FROM": "use_copy_from",
        "TEMP_TABLE_PREFIX": "temp_table_prefix",
        "LOG_MEMORY_USAGE": "log_memory",
        "CLEAR_INTERMEDIATE_OBJECTS": "clear_intermediate_objects",
        "FORCE_GC_AFTER_CHUNK": "force_gc_after_chunk",
    }

    # Normalize overrides
    normalized = {}
    for key, value in overrides.items():
        new_key = key_mapping.get(key, key.lower())
        normalized[new_key] = value

    if normalized:
        return FeaturesSettings(**{**base.model_dump(), **normalized})

    return base


def create_feature_config(**overrides) -> FeaturesSettings:
    """
    Create feature configuration with optional overrides.

    DEPRECATED: Use get_settings().features directly.

    Args:
        **overrides: Override specific configuration values

    Returns:
        FeaturesSettings instance
    """
    _emit_deprecation_warning("create_feature_config")

    base = get_settings().features

    # Map old UPPERCASE keys to new lowercase keys
    key_mapping = {
        "ENABLE_VOLATILITY_NORMALIZE": "volatility_normalize",
        "NORMALIZE_WINDOW": "normalize_window",
        "MIN_FILL_RATE": "min_fill_rate",
        "VALIDATE_RESULTS": "validate_results",
    }

    # Normalize overrides
    normalized = {}
    for key, value in overrides.items():
        new_key = key_mapping.get(key, key.lower())
        normalized[new_key] = value

    if normalized:
        return FeaturesSettings(**{**base.model_dump(), **normalized})

    return base


# =============================================================================
# LEGACY TYPE ALIASES (deprecated)
# =============================================================================

# For backward compatibility - these are now aliases to FeaturesSettings
StreamingConfig = FeaturesSettings
DatabaseConfig = FeaturesSettings
FeatureConfig = FeaturesSettings


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

    settings = get_settings()

    if args.show:
        f = settings.features
        print("Features Configuration (from get_settings().features):")
        print(f"  chunk_size: {f.chunk_size}")
        print(f"  max_lookback: {f.max_lookback}")
        print(f"  overlap_size: {f.overlap_size}")
        print(f"  batch_size: {f.batch_size}")
        print(f"  volatility_normalize: {f.volatility_normalize}")
        print(f"  min_fill_rate: {f.min_fill_rate}")
        print(f"  validate_results: {f.validate_results}")
        print(f"  max_retries: {f.max_retries}")
        print(f"  use_copy_from: {f.use_copy_from}")
        print(f"  log_memory: {f.log_memory}")

    if args.env:
        print("Environment Configuration (centralized):")
        print("  Set environment variables with FEATURES_ prefix:")
        print("  FEATURES_CHUNK_SIZE=200000")
        print("  FEATURES_BATCH_SIZE=50000")
        print("  FEATURES_VOLATILITY_NORMALIZE=true")
        print("  ...")

    if args.new:
        print("New Centralized Configuration:")
        print("\n  from src.config import get_settings")
        print("  settings = get_settings()")
        print("\n  # Features")
        print(f"  settings.features.chunk_size = {settings.features.chunk_size}")
        print(f"  settings.features.batch_size = {settings.features.batch_size}")
        print(f"  settings.features.min_fill_rate = {settings.features.min_fill_rate}")
        print("\n  # Database")
        print(f"  settings.db.pool_size = {settings.db.pool_size}")
        print(f"  settings.db.host = {settings.db.host}")
