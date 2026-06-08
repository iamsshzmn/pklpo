"""
Exception hierarchy for the market_meta module.

Provides specific exceptions for the various error types
encountered in the market_meta module.
"""

from typing import Any


class MarketMetaError(Exception):
    """
    Base exception for the market_meta module.

    All module exceptions must inherit from this class.
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (context: {context_str})"
        return self.message


class MetadataError(MarketMetaError):
    """Base exception for metadata-related errors"""

    pass


class MetadataStaleError(MetadataError):
    """
    Metadata is stale or unavailable.

    Raised when:
    - The metadata cache has expired
    - Metadata could not be refreshed
    - Metadata is corrupted
    """

    def __init__(
        self,
        message: str = "Metadata is stale",
        last_refresh: str | None = None,
        ttl_hours: float | None = None,
    ):
        context: dict[str, Any] = {}
        if last_refresh:
            context["last_refresh"] = last_refresh
        if ttl_hours:
            context["ttl_hours"] = ttl_hours
        super().__init__(message, context)


class MetadataNotFoundError(MetadataError):
    """
    Requested metadata not found.

    Raised when:
    - The instrument does not exist
    - The instrument is not traded
    - The instrument has been removed
    """

    def __init__(self, symbol: str, message: str | None = None):
        if message is None:
            message = f"Metadata for instrument {symbol} not found"
        super().__init__(message, {"symbol": symbol})


class ValidationError(MarketMetaError):
    """
    Data validation error.

    Base exception for all validation errors.
    """

    def __init__(
        self,
        message: str,
        violations: list[str] | None = None,
        warnings: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ):
        merged_context: dict[str, Any] = context.copy() if context else {}
        if violations:
            merged_context["violations"] = violations
        if warnings:
            merged_context["warnings"] = warnings
        super().__init__(message, merged_context)


class OrderValidationError(ValidationError):
    """
    Order validation error.

    Raised when checking order parameters:
    - Invalid price
    - Invalid quantity
    - Limit exceeded
    """

    def __init__(
        self, symbol: str, violations: list[str], warnings: list[str] | None = None
    ):
        count = len(violations)
        plural = "violation" if count == 1 else "violations"
        message = f"Order validation error for {symbol}: {count} {plural}"
        super().__init__(message, violations, warnings, context={"symbol": symbol})
        self.symbol = symbol


class PriceValidationError(ValidationError):
    """
    Price validation error.

    Raised when:
    - Price does not match tick size
    - Price is outside the allowed range
    - Price is zero or negative
    """

    def __init__(self, symbol: str, price: float, reason: str):
        message = f"Invalid price {price} for {symbol}: {reason}"
        super().__init__(
            message,
            context={"symbol": symbol, "price": price, "reason": reason},
        )


class QuantityValidationError(ValidationError):
    """
    Quantity validation error.

    Raised when:
    - Quantity is below the minimum
    - Quantity exceeds the maximum
    - Quantity does not match lot size
    """

    def __init__(self, symbol: str, quantity: float, reason: str):
        message = f"Invalid quantity {quantity} for {symbol}: {reason}"
        super().__init__(
            message,
            context={"symbol": symbol, "quantity": quantity, "reason": reason},
        )


class RiskError(MarketMetaError):
    """Base exception for risk-related errors"""

    pass


class RiskLimitBreach(RiskError):
    """
    Risk limit breached.

    Raised when:
    - Position limit is exceeded
    - Total exposure is exceeded
    - Daily loss limit is exceeded
    """

    def __init__(
        self,
        message: str,
        risk_type: str,
        current_value: float | None = None,
        limit_value: float | None = None,
    ):
        context: dict[str, Any] = {"risk_type": risk_type}
        if current_value is not None:
            context["current_value"] = current_value
        if limit_value is not None:
            context["limit_value"] = limit_value
        super().__init__(message, context)


class PositionLimitBreach(RiskLimitBreach):
    """
    Position limit breached for a specific instrument.
    """

    def __init__(self, symbol: str, quantity: float, max_quantity: float):
        message = f"Position limit breached for {symbol}: {quantity} > {max_quantity}"
        super().__init__(message, "position_limit", quantity, max_quantity)
        self.symbol = symbol


class ExposureLimitBreach(RiskLimitBreach):
    """
    Total account exposure exceeded.
    """

    def __init__(self, current_exposure: float, max_exposure: float):
        message = f"Total exposure exceeded: {current_exposure} > {max_exposure}"
        super().__init__(message, "total_exposure", current_exposure, max_exposure)


class IntegrationError(MarketMetaError):
    """Base exception for errors integrating with external systems"""

    pass


class OKXIntegrationError(IntegrationError):
    """
    OKX API integration error.

    Raised on:
    - Network errors
    - API errors (4xx, 5xx)
    - Rate limit exceeded
    - Invalid API responses
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        endpoint: str | None = None,
        response_data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ):
        merged_context: dict[str, Any] = dict(context) if context else {}
        if status_code is not None:
            merged_context["status_code"] = status_code
        if endpoint:
            merged_context["endpoint"] = endpoint
        if response_data:
            merged_context["response_data"] = response_data
        super().__init__(message, merged_context)


class OKXRateLimitError(OKXIntegrationError):
    """
    OKX API rate limit exceeded.
    """

    def __init__(
        self, retry_after: int | None = None, context: dict[str, Any] | None = None
    ):
        message = "OKX API rate limit exceeded"
        merged_context = dict(context) if context else {}
        if retry_after is not None:
            merged_context["retry_after"] = retry_after
        super().__init__(message, context=merged_context)


class OKXNetworkError(OKXIntegrationError):
    """
    Network error when calling OKX API.
    """

    def __init__(
        self,
        original_error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ):
        message = "Network error when calling OKX API"
        merged_context = dict(context) if context else {}
        if original_error:
            merged_context["original_error"] = str(original_error)
        super().__init__(message, context=merged_context)


class ConfigurationError(MarketMetaError):
    """
    Module configuration error.

    Raised on:
    - Missing required parameters
    - Invalid configuration values
    - Conflicting settings
    """

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        config_value: Any | None = None,
        context: dict[str, Any] | None = None,
    ):
        merged_context: dict[str, Any] = {}
        if config_key is not None:
            merged_context["config_key"] = config_key
        if config_value is not None:
            merged_context["config_value"] = config_value
        if context:
            merged_context.update(context)
        super().__init__(message, merged_context)


class CacheError(MarketMetaError):
    """Base exception for caching errors"""

    pass


class CacheCorruptionError(CacheError):
    """
    Cache corruption error.

    Raised when:
    - Cached data is corrupted
    - Data format is invalid
    - Deserialization fails
    """

    def __init__(self, message: str, cache_key: str | None = None):
        context: dict[str, Any] = {}
        if cache_key:
            context["cache_key"] = cache_key
        super().__init__(message, context)


# Utility functions for working with exceptions


def is_retryable_error(error: Exception) -> bool:
    """
    Checks whether an error is retryable.

    Args:
        error: Exception to check

    Returns:
        True if the error can be retried
    """
    if isinstance(error, OKXNetworkError):
        return True
    if isinstance(error, OKXRateLimitError):
        return True
    return bool(isinstance(error, MetadataStaleError))


def get_error_context(error: MarketMetaError) -> dict[str, Any]:
    """
    Retrieves the error context.

    Args:
        error: market_meta module exception

    Returns:
        Dictionary containing the error context
    """
    return error.context.copy()


def format_error_message(error: MarketMetaError) -> str:
    """
    Formats an error message with context.

    Args:
        error: market_meta module exception

    Returns:
        Formatted error message
    """
    if error.context:
        context_parts = []
        for key, value in error.context.items():
            if isinstance(value, list | dict):
                context_parts.append(f"{key}={type(value).__name__}")
            else:
                context_parts.append(f"{key}={value}")
        return f"{error.message} [{', '.join(context_parts)}]"
    return error.message
