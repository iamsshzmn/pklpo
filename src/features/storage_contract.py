"""Canonical storage contract for indicators/features persistence."""

from __future__ import annotations


class IndicatorStorageContract:
    """Single source of truth for indicators storage metadata."""

    table_name = "indicators_p"
    identity_fields = ("symbol", "timeframe", "timestamp")
    service_fields = ("symbol", "timeframe", "timestamp", "calculated_at")
    required_fields = ("symbol", "timeframe", "timestamp", "calculated_at")

    @classmethod
    def identity_fields_set(cls) -> set[str]:
        return set(cls.identity_fields)

    @classmethod
    def service_fields_set(cls) -> set[str]:
        return set(cls.service_fields)

    @classmethod
    def required_fields_set(cls) -> set[str]:
        return set(cls.required_fields)

    @classmethod
    def is_feature_column(cls, column_name: str) -> bool:
        return column_name not in cls.service_fields_set()
