"""Root logging configuration.

DEPRECATED: This module now delegates to src.logging.
Use `from src.logging import setup_logging, get_logger` directly.
"""

import warnings

from src.logging import get_logger, setup_logging

# Emit deprecation warning
warnings.warn(
    "src.logging_config is deprecated. Use src.logging instead.",
    DeprecationWarning,
    stacklevel=2,
)


__all__ = [
    "get_logger",
    "setup_logging",
]
