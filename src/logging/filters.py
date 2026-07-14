"""Log filters for security and data protection.

This module provides filters for sanitizing sensitive data in logs.
"""

from __future__ import annotations

import logging
import re
from typing import Any


class SensitiveDataFilter(logging.Filter):
    """Filter for hiding sensitive data in logs.

    Automatically masks passwords, API keys, tokens, and secrets
    in log messages and arguments.

    Example:
        logger.addFilter(SensitiveDataFilter())
        logger.info("Connecting with api_key=sk-12345")
        # Output: Connecting with ***HIDDEN***
    """

    # Default sensitive patterns
    DEFAULT_PATTERNS = [
        r'password["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
        r'api_key["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
        r'secret["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
        r'token["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
        r'auth["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
        r'credential["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
        # URL-embedded credentials: postgresql://user:pass@host, redis://:pass@host, etc.
        # Lookbehind/lookahead preserve the scheme and host; only user:pass is masked.
        # Username is optional ([^:@\s]*) to handle forms like redis://:pass@host.
        r"(?<=://)[^:@\s]*:[^@\s]+(?=@)",
    ]

    # Default sensitive dict keys
    DEFAULT_SENSITIVE_KEYS = [
        "password",
        "api_key",
        "secret",
        "token",
        "key",
        "auth",
        "credential",
        "private",
    ]

    MASK = "***HIDDEN***"

    def __init__(
        self,
        patterns: list[str] | None = None,
        sensitive_keys: list[str] | None = None,
    ) -> None:
        """Initialize the filter.

        Args:
            patterns: Regex patterns to mask. Uses defaults if None.
            sensitive_keys: Dict keys to mask. Uses defaults if None.
        """
        super().__init__()
        self.sensitive_patterns = patterns or self.DEFAULT_PATTERNS
        self.sensitive_keys = sensitive_keys or self.DEFAULT_SENSITIVE_KEYS

        # Compile patterns for performance
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.sensitive_patterns
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter sensitive data from log message."""
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = self._sanitize_message(record.msg)

        if hasattr(record, "args") and record.args:
            record.args = tuple(self._sanitize_arg(arg) for arg in record.args)

        return True

    def _sanitize_message(self, message: str) -> str:
        """Sanitize message by replacing sensitive patterns."""
        for pattern in self.compiled_patterns:
            message = pattern.sub(self.MASK, message)
        return message

    def _sanitize_arg(self, arg: Any) -> Any:
        """Sanitize a single argument."""
        if isinstance(arg, str):
            return self._sanitize_message(arg)
        if isinstance(arg, dict):
            return self._sanitize_dict(arg)
        if isinstance(arg, list):
            return [self._sanitize_arg(item) for item in arg]
        return arg

    def _sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize dictionary by masking sensitive keys."""
        sanitized: dict[str, Any] = {}

        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_keys):
                sanitized[key] = self.MASK
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_arg(item) for item in value]
            else:
                sanitized[key] = value

        return sanitized


class CategoryFilter(logging.Filter):
    """Filter that only allows specific log categories.

    Example:
        handler.addFilter(CategoryFilter({"calc", "insert"}))
    """

    def __init__(self, allowed_categories: set[str]) -> None:
        """Initialize with allowed categories.

        Args:
            allowed_categories: Set of category names to allow.
        """
        super().__init__()
        self.allowed_categories = {c.lower() for c in allowed_categories}

    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow records with matching category."""
        category = getattr(record, "category", "-").lower()
        if category == "-":
            return True  # Allow records without category
        return category in self.allowed_categories
