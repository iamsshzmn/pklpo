from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from src.candles.interfaces.airflow_sync import (
    AirflowSyncRequest,
    run_refresh_okx_meta,
    run_smoke_validate,
    run_swap_sync,
)

if TYPE_CHECKING:
    from pathlib import Path


class _AsyncSessionContext:
    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return None


@pytest.mark.asyncio
async def test_run_refresh_okx_meta_skips_when_cache_is_fresh(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    marker = {"called": False}

    async def _run_catalog_refresh_via_application() -> dict[str, object]:
        marker["called"] = True
        return {"refreshed": True}

    (tmp_path / "instruments_list.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("INSTRUMENTS_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "src.candles.interfaces.airflow_sync.run_catalog_refresh_via_application",
        _run_catalog_refresh_via_application,
    )

    result = await run_refresh_okx_meta(
        AirflowSyncRequest(conf={}, logical_date=datetime(2026, 3, 17, 12, 0))
    )

    assert result == {"refreshed": False, "reason": "cache_fresh"}
    assert marker["called"] is False


@pytest.mark.asyncio
async def test_run_swap_sync_skips_scheduled_run_when_data_is_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _check_data_freshness(session, mode: str):
        assert mode == "fast"
        return True, "data_fresh: 1m lag 30s < 120s"

    monkeypatch.setattr(
        "src.candles.interfaces.airflow_sync.check_data_freshness",
        _check_data_freshness,
    )
    monkeypatch.setattr(
        "src.candles.interfaces.airflow_sync.get_db_session",
        lambda: _AsyncSessionContext(object()),
    )

    result = await run_swap_sync(
        AirflowSyncRequest(
            conf={},
            logical_date=datetime(2026, 3, 17, 12, 5),
            run_type="scheduled",
        )
    )

    assert result["skipped"] is True
    assert result["mode"] == "fast"


@pytest.mark.asyncio
async def test_run_swap_sync_bypasses_freshness_for_manual_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _sync_swap_candles(*, symbols, timeframes, config):
        assert symbols is None
        assert timeframes == ["1m", "5m"]
        assert config["max_concurrent_symbols"] == 10
        assert config["timeout_seconds"] == 30
        return {
            "total_symbols": 2,
            "total_symbols_processed": 2,
            "total_candles_synced": 42,
            "errors_count": 0,
            "duration_seconds": 3.5,
            "candles_per_second": 12.0,
            "endpoint_stats": {"candles": {"rate_limit": 1}},
            "today_fill": {"rows_today": 42},
        }

    monkeypatch.setattr(
        "src.candles.interfaces.airflow_sync.sync_swap_candles",
        _sync_swap_candles,
    )

    result = await run_swap_sync(
        AirflowSyncRequest(
            conf={},
            logical_date=datetime(2026, 3, 17, 12, 5),
            run_type="manual",
        )
    )

    assert result["mode"] == "fast"
    assert result["rows_upserted_total"] == 42
    assert result["total_symbols_processed"] == 2
    assert result["api_429_count"] == 1


@pytest.mark.asyncio
async def test_run_swap_sync_passes_timeout_override_from_conf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _sync_swap_candles(*, symbols, timeframes, config):
        captured["config"] = config
        return {
            "total_symbols": 1,
            "total_symbols_processed": 1,
            "total_candles_synced": 10,
            "errors_count": 0,
            "duration_seconds": 1.0,
            "candles_per_second": 10.0,
            "endpoint_stats": {"candles": {"timeout": 2}},
            "today_fill": {"rows_today": 10},
        }

    monkeypatch.setattr(
        "src.candles.interfaces.airflow_sync.sync_swap_candles",
        _sync_swap_candles,
    )

    result = await run_swap_sync(
        AirflowSyncRequest(
            conf={"timeout_seconds": 45},
            logical_date=datetime(2026, 3, 17, 12, 5),
            run_type="manual",
        )
    )

    assert captured["config"]["timeout_seconds"] == 45
    assert result["api_timeout_count"] == 2


@pytest.mark.asyncio
async def test_run_swap_sync_propagates_adapter_init_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _sync_swap_candles(*, symbols, timeframes, config):
        return {
            "total_symbols": 1,
            "total_symbols_processed": 1,
            "total_candles_synced": 10,
            "errors_count": 0,
            "duration_seconds": 1.0,
            "candles_per_second": 10.0,
            "endpoint_stats": {"candles": {"timeout": 2}},
            "today_fill": {"rows_today": 10},
            "adapter_init": {
                "load_markets_attempts": 3,
                "load_markets_retries": 2,
                "load_markets_duration_ms": 123.4,
                "load_markets_failure_kind": None,
                "load_markets_succeeded": True,
            },
        }

    def _push_swap_sync_metrics(payload):
        captured["payload"] = payload
        return True

    monkeypatch.setattr(
        "src.candles.interfaces.airflow_sync.sync_swap_candles",
        _sync_swap_candles,
    )
    monkeypatch.setattr(
        "src.candles.interfaces.airflow_sync.push_swap_sync_metrics",
        _push_swap_sync_metrics,
    )

    result = await run_swap_sync(
        AirflowSyncRequest(
            conf={"timeout_seconds": 45},
            logical_date=datetime(2026, 3, 17, 12, 5),
            run_type="manual",
        )
    )

    assert result["api_timeout_count"] == 2
    assert captured["payload"]["adapter_init"]["load_markets_attempts"] == 3
    assert captured["payload"]["adapter_init"]["load_markets_retries"] == 2
    assert captured["payload"]["adapter_init"]["load_markets_duration_ms"] == 123.4


@pytest.mark.asyncio
async def test_run_smoke_validate_uses_request_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _run_smoke_validation(session, mode: str, extra_data_enabled: bool):
        captured["mode"] = mode
        captured["extra_data_enabled"] = extra_data_enabled
        return {"total_rows": 10, "rows_today": 5}

    monkeypatch.setattr(
        "src.candles.interfaces.airflow_sync.run_smoke_validation_use_case",
        _run_smoke_validation,
    )
    monkeypatch.setattr(
        "src.candles.interfaces.airflow_sync.get_db_session",
        lambda: _AsyncSessionContext(object()),
    )

    result = await run_smoke_validate(
        AirflowSyncRequest(
            conf={"mode": "ext"},
            logical_date=datetime(2026, 3, 17, 12, 5),
        )
    )

    assert captured == {"mode": "ext", "extra_data_enabled": True}
    assert result == {"total_rows": 10, "rows_today": 5}
