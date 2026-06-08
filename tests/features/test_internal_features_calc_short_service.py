from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd
import pytest

import src.features.application.features_calc_short_service as service


def _make_features_df(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": range(n),
            "open": [1.0] * n,
            "high": [1.1] * n,
            "low": [0.9] * n,
            "close": [1.0] * n,
            "volume": [100.0] * n,
            "ema_8": [1.0] * n,
        }
    )


class TestFeaturesCalcShortServiceSaveDelegation:
    @pytest.mark.asyncio
    async def test_save_features_batch_delegates_to_application_save(
        self,
        monkeypatch,
    ):
        from src.features.application.features_calc_short_service import (
            save_features_batch,
        )

        save_mock = AsyncMock(
            return_value={"success": True, "rows_saved": 3, "committed": False}
        )
        monkeypatch.setattr(
            "src.features.application.features_calc_short_service.save_batch",
            save_mock,
        )

        session = AsyncMock()
        rows_saved = await save_features_batch(
            session=session,
            df_features=_make_features_df(),
            symbol="BTC",
            timeframe="1m",
            save_dependencies_factory=lambda _session: SimpleNamespace(
                repository=object(),
                observer=object(),
            ),
        )

        save_mock.assert_awaited_once()
        call_kwargs = save_mock.await_args.kwargs
        assert call_kwargs["session"] is session
        assert call_kwargs["symbol"] == "BTC"
        assert call_kwargs["timeframe"] == "1m"
        assert call_kwargs["commit"] is False
        assert rows_saved == 3


class TestFeaturesCalcShortServiceValidate:
    @pytest.mark.asyncio
    async def test_validate_uses_injected_quality_runner(self, monkeypatch):
        class _FakeResult:
            def __init__(self, value):
                self._value = value

            def scalar(self):
                return self._value

        class _FakeSession:
            async def execute(self, _stmt, _params=None):
                return _FakeResult(1_700_000_000_000)

        class _FakeSessionContext:
            def __init__(self, _engine):
                self._session = _FakeSession()

            async def __aenter__(self):
                return self._session

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class _FakeEngine:
            def __init__(self):
                self.disposed = False

            async def dispose(self):
                self.disposed = True

        fake_engine = _FakeEngine()

        monkeypatch.setattr(
            service, "create_async_engine", lambda *_args, **_kwargs: fake_engine
        )
        monkeypatch.setattr(service, "AsyncSession", _FakeSessionContext)

        runner_calls = []

        async def _runner(engine, *, send_alerts=True, alert_cooldown_minutes=30):
            runner_calls.append(
                {
                    "engine": engine,
                    "send_alerts": send_alerts,
                    "alert_cooldown_minutes": alert_cooldown_minutes,
                }
            )

            class _Report:
                def summary(self):
                    return {"total": 4, "warn": 1, "critical": 2, "ok": 1}

            return _Report(), {"checked": 3, "sent": 2, "suppressed": 1}

        result = await service.run_features_calc_short_validate(
            database_url="postgresql+asyncpg://example",
            quality_enabled=True,
            quality_send_alerts=False,
            quality_alert_cooldown=17,
            quality_pipeline_runner=_runner,
        )

        assert runner_calls == [
            {
                "engine": fake_engine,
                "send_alerts": False,
                "alert_cooldown_minutes": 17,
            }
        ]
        assert result["quality_total_checks"] == 4
        assert result["quality_warn"] == 1
        assert result["quality_critical"] == 2
        assert result["quality_ok"] == 1
        assert result["alerts_checked"] == 3
        assert result["alerts_sent"] == 2
        assert result["alerts_suppressed"] == 1
