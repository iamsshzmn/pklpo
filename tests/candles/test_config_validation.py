"""Tests for SyncConfig Pydantic validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.candles.domain.sync_config import SyncConfig


class TestSyncConfigDefaults:
    def test_default_values(self) -> None:
        cfg = SyncConfig()
        assert cfg.max_requests_per_second == 80
        assert cfg.batch_size == 300
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 1.0
        assert cfg.timeout_seconds == 30.0
        assert cfg.max_concurrent_symbols == 3
        assert cfg.extra_data is False
        assert cfg.use_ccxt is True
        assert cfg.dynamic_batch_size is False

    def test_frozen(self) -> None:
        cfg = SyncConfig()
        with pytest.raises(ValidationError):
            cfg.batch_size = 999  # type: ignore[misc]


class TestSyncConfigBounds:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("max_requests_per_second", 0),
            ("max_requests_per_second", 201),
            ("batch_size", 49),
            ("batch_size", 1001),
            ("max_retries", -1),
            ("max_retries", 11),
            ("retry_delay", 0.0),
            ("retry_delay", 31.0),
            ("timeout_seconds", 0.0),
            ("timeout_seconds", 301.0),
            ("max_concurrent_symbols", 0),
            ("max_concurrent_symbols", 51),
        ],
    )
    def test_out_of_bounds_rejected(self, field: str, value: object) -> None:
        with pytest.raises(ValidationError):
            SyncConfig(**{field: value})

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("max_requests_per_second", 1),
            ("max_requests_per_second", 200),
            ("batch_size", 50),
            ("batch_size", 1000),
            ("max_retries", 0),
            ("max_retries", 10),
            ("retry_delay", 0.1),
            ("retry_delay", 30.0),
            ("timeout_seconds", 0.1),
            ("timeout_seconds", 300.0),
            ("max_concurrent_symbols", 1),
            ("max_concurrent_symbols", 50),
        ],
    )
    def test_boundary_values_accepted(self, field: str, value: object) -> None:
        cfg = SyncConfig(**{field: value})
        assert getattr(cfg, field) == value


class TestSyncConfigFromEnv:
    def test_from_env_with_overrides(self) -> None:
        cfg = SyncConfig.from_env(overrides={"batch_size": 500, "extra_data": True})
        assert cfg.batch_size == 500
        assert cfg.extra_data is True

    def test_from_env_reads_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CANDLES_BATCH_SIZE", "100")
        monkeypatch.setenv("CANDLES_MAX_CONCURRENT", "10")
        monkeypatch.setenv("OKX_TIMEOUT_SECONDS", "45")
        cfg = SyncConfig.from_env()
        assert cfg.batch_size == 100
        assert cfg.max_concurrent_symbols == 10
        assert cfg.timeout_seconds == 45

    def test_from_env_invalid_value_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CANDLES_BATCH_SIZE", "not_a_number")
        with pytest.raises(ValidationError):
            SyncConfig.from_env()

    def test_from_env_out_of_bounds_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CANDLES_BATCH_SIZE", "9999")
        with pytest.raises(ValidationError):
            SyncConfig.from_env()


class TestSyncConfigModelDump:
    def test_model_dump_returns_dict(self) -> None:
        cfg = SyncConfig()
        d = cfg.model_dump()
        assert isinstance(d, dict)
        assert d["batch_size"] == 300
        assert d["extra_data"] is False
