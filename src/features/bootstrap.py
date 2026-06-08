"""Composition root helpers for the features bounded context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd
    from sqlalchemy.ext.asyncio import AsyncSession

    from .ports import (
        FeatureSaveDependenciesFactory,
        FeatureSaveObserver,
        FeatureSaveValidator,
        FeatureStorageGateway,
        IndicatorRepository,
        PartitionManager,
        QualityPipelineRunner,
        SchemaDDLPort,
    )


@dataclass(frozen=True)
class FeatureSaveDependencies:
    """Explicit save dependencies assembled at the composition root."""

    repository: IndicatorRepository
    validator: FeatureSaveValidator
    observer: FeatureSaveObserver


@dataclass(frozen=True)
class FeatureAirflowCallbacks:
    """Public Airflow callback bundle assembled at the composition root."""

    on_failure_callback: object | None
    sla_miss_callback: object | None
    on_success_callback: object | None


class SqlAlchemyFeatureStorageGateway:
    """Infrastructure-backed storage gateway for features use cases."""

    def __init__(self, *, schema_ddl_port: SchemaDDLPort) -> None:
        self._schema_ddl_port = schema_ddl_port

    async def fetch_latest_ts(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str,
    ) -> int | None:
        from .infrastructure.db_operations import fetch_latest_ts

        return await fetch_latest_ts(session, symbol, timeframe)

    async def fetch_ohlcv_df(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str,
        *,
        since_ts: int | None = None,
        until_ts: int | None = None,
        limit: int = 200,
    ) -> pd.DataFrame | None:
        from .infrastructure.db_operations import fetch_ohlcv_df

        return await fetch_ohlcv_df(
            session,
            symbol,
            timeframe,
            since_ts=since_ts,
            until_ts=until_ts,
            limit=limit,
        )

    async def ensure_indicator_columns(
        self,
        session: AsyncSession,
        table: str,
        columns: list[str],
    ) -> None:
        from .infrastructure.db_operations import ensure_columns_exist

        await ensure_columns_exist(
            session,
            table,
            columns,
            schema_ddl_port=self._schema_ddl_port,
        )


@dataclass(frozen=True)
class FeatureApplicationBootstrap:
    """Explicit dependency bundle created at the module boundary."""

    storage_gateway: FeatureStorageGateway
    save_dependencies_factory: FeatureSaveDependenciesFactory
    quality_pipeline_runner: QualityPipelineRunner
    schema_ddl_port: SchemaDDLPort
    partition_manager_factory: Callable[[AsyncSession], PartitionManager]


def create_feature_application_bootstrap(
    *,
    quality_pipeline_runner: QualityPipelineRunner | None = None,
    schema_ddl_port: SchemaDDLPort | None = None,
    partition_manager_factory: Callable[[AsyncSession], PartitionManager] | None = None,
    repository_backend: str = "postgresql",
    repository_targets: tuple[str, ...] | None = None,
) -> FeatureApplicationBootstrap:
    """Assemble default application dependencies at the composition root."""
    from .infrastructure.partition_adapter import create_partition_manager
    from .infrastructure.quality_adapter import create_quality_pipeline_runner
    from .infrastructure.schema_ddl_adapter import SqlAlchemySchemaDDLAdapter

    resolved_schema_ddl_port = schema_ddl_port or SqlAlchemySchemaDDLAdapter()
    resolved_quality_pipeline_runner = (
        quality_pipeline_runner or create_quality_pipeline_runner()
    )
    resolved_partition_manager_factory = (
        partition_manager_factory or create_partition_manager
    )

    return FeatureApplicationBootstrap(
        storage_gateway=SqlAlchemyFeatureStorageGateway(
            schema_ddl_port=resolved_schema_ddl_port,
        ),
        save_dependencies_factory=lambda session: create_feature_save_dependencies(
            session,
            partition_manager_factory=resolved_partition_manager_factory,
            repository_backend=repository_backend,
            repository_targets=repository_targets,
        ),
        quality_pipeline_runner=resolved_quality_pipeline_runner,
        schema_ddl_port=resolved_schema_ddl_port,
        partition_manager_factory=resolved_partition_manager_factory,
    )


def create_feature_save_dependencies(
    session: AsyncSession,
    *,
    partition_manager_factory: Callable[[AsyncSession], PartitionManager] | None = None,
    repository_backend: str = "postgresql",
    repository_targets: tuple[str, ...] | None = None,
) -> FeatureSaveDependencies:
    """Create the default dependency bundle for save use cases."""
    from .application.save_observer import create_feature_save_observer
    from .application.save_validation import create_feature_save_validator
    from .infrastructure.persistence import create_indicator_repository

    return FeatureSaveDependencies(
        repository=create_indicator_repository(
            session,
            partition_manager_factory=partition_manager_factory,
            storage_backend=repository_backend,
            storage_targets=repository_targets,
        ),
        validator=create_feature_save_validator(),
        observer=create_feature_save_observer(),
    )


def create_feature_airflow_callbacks() -> FeatureAirflowCallbacks:
    """Expose Airflow alert callbacks through the public bootstrap boundary."""
    from .infrastructure.alerts import (
        combined_failure_callback,
        combined_sla_miss_callback,
        success_callback,
    )

    return FeatureAirflowCallbacks(
        on_failure_callback=combined_failure_callback,
        sla_miss_callback=combined_sla_miss_callback,
        on_success_callback=success_callback,
    )


def get_current_feature_version():
    """Resolve current feature version information at the composition root."""
    from .infrastructure.versioning import get_current_version

    return get_current_version()
