from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest


def _make_features_df(n: int = 5) -> pd.DataFrame:
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


class _ObserverContext:
    def __init__(self) -> None:
        self.success_calls: list[dict[str, int]] = []
        self.error_calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        return None

    def record_success(self, *, rows_processed: int, rows_saved: int) -> None:
        self.success_calls.append(
            {"rows_processed": rows_processed, "rows_saved": rows_saved}
        )

    def record_error(self, error) -> None:
        self.error_calls.append(str(error))


class _Observer:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.context = _ObserverContext()

    def observe(self, *, operation, symbol, timeframe, df, log_memory=False):
        self.calls.append(
            {
                "operation": operation,
                "symbol": symbol,
                "timeframe": timeframe,
                "df": df,
                "log_memory": log_memory,
            }
        )
        return self.context


class TestSaveBatchRepositoryInjection:
    @pytest.mark.asyncio
    async def test_save_batch_uses_injected_repository(self):
        from src.features.api import save_batch

        session = AsyncMock()
        repository = MagicMock()
        repository.save_batch_from_df = AsyncMock(return_value=5)
        observer = _Observer()

        result = await save_batch(
            session=session,
            df=_make_features_df(),
            symbol="BTC",
            timeframe="1m",
            repository=repository,
            observer=observer,
        )

        repository.save_batch_from_df.assert_awaited_once()
        session.commit.assert_awaited_once()
        assert result["success"] is True
        assert result["rows_saved"] == 5
        assert result["committed"] is True

    @pytest.mark.asyncio
    async def test_save_batch_can_skip_commit_for_outer_orchestration(self):
        from src.features.api import save_batch

        session = AsyncMock()
        repository = MagicMock()
        repository.save_batch_from_df = AsyncMock(return_value=5)
        observer = _Observer()

        result = await save_batch(
            session=session,
            df=_make_features_df(),
            symbol="BTC",
            timeframe="1m",
            repository=repository,
            observer=observer,
            commit=False,
        )

        repository.save_batch_from_df.assert_awaited_once()
        session.commit.assert_not_awaited()
        session.rollback.assert_not_awaited()
        assert result["success"] is True
        assert result["rows_saved"] == 5
        assert result["committed"] is False

    @pytest.mark.asyncio
    async def test_save_batch_uses_injected_observer(self):
        from src.features.api import save_batch

        session = AsyncMock()
        repository = MagicMock()
        repository.save_batch_from_df = AsyncMock(return_value=5)
        observer = _Observer()

        result = await save_batch(
            session=session,
            df=_make_features_df(),
            symbol="BTC",
            timeframe="1m",
            repository=repository,
            observer=observer,
        )

        assert result["success"] is True
        assert len(observer.calls) == 1
        assert observer.calls[0]["operation"] == "save_batch"
        assert observer.context.success_calls == [
            {"rows_processed": 5, "rows_saved": 5}
        ]
        assert observer.context.error_calls == []

    @pytest.mark.asyncio
    async def test_save_batch_rolls_back_on_repository_error(self):
        from src.features.api import save_batch

        session = AsyncMock()
        repository = MagicMock()
        repository.save_batch_from_df = AsyncMock(side_effect=RuntimeError("boom"))
        observer = _Observer()

        with pytest.raises(RuntimeError, match="boom"):
            await save_batch(
                session=session,
                df=_make_features_df(),
                symbol="BTC",
                timeframe="1m",
                repository=repository,
                observer=observer,
            )

        session.rollback.assert_awaited_once()


class TestSaveParquetRepositoryInjection:
    @pytest.mark.asyncio
    async def test_save_parquet_uses_injected_repository(self, monkeypatch):
        from src.features.api import save_parquet_to_pg

        df = _make_features_df()
        monkeypatch.setattr(pd, "read_parquet", lambda _: df)

        session = AsyncMock()
        repository = MagicMock()
        repository.save_batch_from_df = AsyncMock(return_value=len(df))
        validator = MagicMock()
        validator.validate_save_dataframe.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "feature_count": 1,
            "row_count": len(df),
        }
        observer = _Observer()

        result = await save_parquet_to_pg(
            session=session,
            parquet_path="features.parquet",
            symbol="BTC",
            timeframe="1m",
            repository=repository,
            validator=validator,
            observer=observer,
        )

        repository.save_batch_from_df.assert_awaited_once()
        session.commit.assert_awaited_once()
        assert result["success"] is True
        assert result["rows_saved"] == len(df)

    @pytest.mark.asyncio
    async def test_save_parquet_rolls_back_on_repository_error(self, monkeypatch):
        from src.features.api import save_parquet_to_pg

        monkeypatch.setattr(pd, "read_parquet", lambda _: _make_features_df())

        session = AsyncMock()
        repository = MagicMock()
        repository.save_batch_from_df = AsyncMock(side_effect=RuntimeError("db fail"))
        validator = MagicMock()
        validator.validate_save_dataframe.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "feature_count": 1,
            "row_count": 5,
        }
        observer = _Observer()

        result = await save_parquet_to_pg(
            session=session,
            parquet_path="features.parquet",
            symbol="BTC",
            timeframe="1m",
            repository=repository,
            validator=validator,
            observer=observer,
        )

        assert result["success"] is False
        assert "db fail" in result["error"]
        session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_parquet_uses_injected_validator(self, monkeypatch):
        from src.features.api import save_parquet_to_pg

        df = _make_features_df()
        monkeypatch.setattr(pd, "read_parquet", lambda _: df)

        session = AsyncMock()
        repository = MagicMock()
        repository.save_batch_from_df = AsyncMock(return_value=len(df))
        validator = MagicMock()
        validator.validate_save_dataframe.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "feature_count": 1,
            "row_count": len(df),
        }

        result = await save_parquet_to_pg(
            session=session,
            parquet_path="features.parquet",
            symbol="BTC",
            timeframe="1m",
            repository=repository,
            validator=validator,
            observer=_Observer(),
        )

        validator.validate_save_dataframe.assert_called_once_with(
            df=df,
            symbol="BTC",
            timeframe="1m",
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_save_parquet_returns_error_on_invalid_validator_result(
        self,
        monkeypatch,
    ):
        from src.features.api import save_parquet_to_pg

        df = _make_features_df()
        monkeypatch.setattr(pd, "read_parquet", lambda _: df)

        session = AsyncMock()
        repository = MagicMock()
        repository.save_batch_from_df = AsyncMock()
        validator = MagicMock()
        validator.validate_save_dataframe.return_value = {
            "valid": False,
            "errors": ["bad payload"],
            "warnings": [],
            "feature_count": 1,
            "row_count": len(df),
        }

        result = await save_parquet_to_pg(
            session=session,
            parquet_path="features.parquet",
            symbol="BTC",
            timeframe="1m",
            repository=repository,
            validator=validator,
            observer=_Observer(),
        )

        repository.save_batch_from_df.assert_not_called()
        session.rollback.assert_awaited_once()
        assert result["success"] is False
        assert "bad payload" in result["error"]

    @pytest.mark.asyncio
    async def test_save_parquet_uses_injected_observer(self, monkeypatch):
        from src.features.api import save_parquet_to_pg

        df = _make_features_df()
        monkeypatch.setattr(pd, "read_parquet", lambda _: df)

        session = AsyncMock()
        repository = MagicMock()
        repository.save_batch_from_df = AsyncMock(return_value=len(df))
        validator = MagicMock()
        validator.validate_save_dataframe.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "feature_count": 1,
            "row_count": len(df),
        }
        observer = _Observer()

        result = await save_parquet_to_pg(
            session=session,
            parquet_path="features.parquet",
            symbol="BTC",
            timeframe="1m",
            repository=repository,
            validator=validator,
            observer=observer,
        )

        assert result["success"] is True
        assert len(observer.calls) == 1
        assert observer.calls[0]["operation"] == "save_parquet_to_pg"
        assert observer.context.success_calls == [
            {"rows_processed": len(df), "rows_saved": len(df)}
        ]


class TestSaveHealthChecksRepositoryInjection:
    @pytest.mark.asyncio
    async def test_validate_database_connection_uses_injected_repository(self):
        from src.features.api import validate_database_connection

        session = AsyncMock()
        repository = MagicMock()
        repository.validate_connection = AsyncMock(
            return_value={"valid": True, "table_exists": True, "columns": []}
        )

        result = await validate_database_connection(
            session=session,
            repository=repository,
        )

        repository.validate_connection.assert_awaited_once_with()
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_verify_database_integrity_uses_injected_repository(self):
        from src.features.api import verify_database_integrity

        session = AsyncMock()
        repository = MagicMock()
        repository.verify_integrity = AsyncMock(
            return_value={"integrity_ok": True, "duplicate_count": 0}
        )

        result = await verify_database_integrity(
            session=session,
            symbol="BTC",
            timeframe="1m",
            repository=repository,
        )

        repository.verify_integrity.assert_awaited_once_with(
            symbol="BTC",
            timeframe="1m",
        )
        assert result["integrity_ok"] is True
