from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.features.bootstrap import (
    create_feature_application_bootstrap,
    create_feature_save_dependencies,
)
from src.features.infrastructure.persistence.repository import (
    SqlAlchemyIndicatorRepository,
    create_indicator_repository,
)
from src.features.ports.persistence import (
    IndicatorRepository,
    RepositoryStorageProfile,
)


class TestIndicatorRepositoryProtocolContract:
    def test_runtime_protocol_requires_storage_description(self):
        class Repo:
            def describe_storage(self):
                return RepositoryStorageProfile(
                    backend="postgresql",
                    targets=("indicators_p",),
                    table_name="indicators_p",
                )

            async def save_batch(self, records, symbol, timeframe):
                return len(records)

            async def save_batch_from_df(self, df, symbol, timeframe):
                return len(df)

            async def validate_connection(self):
                return {"valid": True}

            async def verify_integrity(self, symbol, timeframe):
                return {"integrity_ok": True}

        assert isinstance(Repo(), IndicatorRepository)

    def test_runtime_protocol_rejects_missing_storage_description(self):
        class IncompleteRepo:
            async def save_batch(self, records, symbol, timeframe):
                return len(records)

            async def save_batch_from_df(self, df, symbol, timeframe):
                return len(df)

            async def validate_connection(self):
                return {"valid": True}

            async def verify_integrity(self, symbol, timeframe):
                return {"integrity_ok": True}

        assert not isinstance(IncompleteRepo(), IndicatorRepository)


class TestSqlAlchemyIndicatorRepositoryContract:
    @pytest.mark.asyncio
    async def test_save_batch_returns_zero_for_empty_input(self):
        repo = SqlAlchemyIndicatorRepository(AsyncMock())
        repo.save_batch_from_df = AsyncMock(return_value=7)

        result = await repo.save_batch([], "BTC-USDT-SWAP", "1m")

        assert result == 0
        repo.save_batch_from_df.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_batch_forwards_to_dataframe_path(self):
        repo = SqlAlchemyIndicatorRepository(AsyncMock())
        repo.save_batch_from_df = AsyncMock(return_value=3)

        result = await repo.save_batch(
            [{"timestamp": 1, "close": 10.0}],
            "BTC-USDT-SWAP",
            "1m",
        )

        assert result == 3
        repo.save_batch_from_df.assert_awaited_once()

    def test_describe_storage_uses_default_postgresql_profile(self):
        repo = SqlAlchemyIndicatorRepository(AsyncMock())

        assert repo.describe_storage() == RepositoryStorageProfile(
            backend="postgresql",
            targets=("indicators_p",),
            table_name="indicators_p",
        )

    def test_factory_supports_backend_and_target_metadata(self):
        repo = create_indicator_repository(
            AsyncMock(),
            storage_backend="clickhouse",
            storage_targets=("indicators_hot", "indicators_cold"),
        )

        assert repo.describe_storage() == RepositoryStorageProfile(
            backend="clickhouse",
            targets=("indicators_hot", "indicators_cold"),
            table_name="indicators_p",
        )


class TestFeatureSaveBootstrapContract:
    def test_create_feature_save_dependencies_passes_repository_metadata(self):
        deps = create_feature_save_dependencies(
            AsyncMock(),
            repository_backend="clickhouse",
            repository_targets=("indicators_hot", "indicators_cold"),
        )

        assert deps.repository.describe_storage() == RepositoryStorageProfile(
            backend="clickhouse",
            targets=("indicators_hot", "indicators_cold"),
            table_name="indicators_p",
        )

    def test_feature_application_bootstrap_closes_over_repository_metadata(self):
        bootstrap = create_feature_application_bootstrap(
            repository_backend="clickhouse",
            repository_targets=("indicators_hot", "indicators_cold"),
        )

        deps = bootstrap.save_dependencies_factory(AsyncMock())

        assert deps.repository.describe_storage() == RepositoryStorageProfile(
            backend="clickhouse",
            targets=("indicators_hot", "indicators_cold"),
            table_name="indicators_p",
        )
