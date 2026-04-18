"""
DEPRECATED: This module is superseded by ``src.config.settings``.

All functionality has been merged into ``src.config.settings``.
Import from ``src.config`` or ``src.config.settings`` instead:

    # Before (deprecated)
    from src.config.env_validator import get_database_url, check_required_env_vars

    # After (canonical)
    from src.config import get_database_url, check_required_env_vars
    # or
    from src.config.settings import get_database_url, check_required_env_vars

This shim re-exports for backward compatibility and will be removed
in a future release.
"""

import warnings as _warnings

_warnings.warn(
    "src.config.env_validator is deprecated. "
    "Use src.config or src.config.settings instead.",
    DeprecationWarning,
    stacklevel=2,
)

from src.config.settings import check_required_env_vars, get_database_url

__all__ = ["check_required_env_vars", "get_database_url"]
