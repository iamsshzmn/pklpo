"""Composition root helpers for the features bounded context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .ports import (
    FeatureSaveDependenciesFactory,
    FeatureSaveObserver,
    FeatureSaveValidator,
    FeatureStorageGateway,
    IndicatorRepository,
)

if TYPE_CHECKING:
    import pandas as pd
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class FeatureSaveDependencies:
    """Explicit save dependencies assembled at the composition root."""

    repository: IndicatorRepository
    validator: FeatureSaveValidator
    observer: FeatureSaveObserver


class SqlAlchemyFeatureStorageGateway:
    """Infrastructure-backed storage gateway for features use cases."""

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
        limit: int = 200,
    ) -> pd.DataFrame | None:
        from .infrastructure.db_operations import fetch_ohlcv_df

        return await fetch_ohlcv_df(
            session,
            symbol,
            timeframe,
            since_ts=since_ts,
            limit=limit,
        )

    async def ensure_indicator_columns(
        self,
        session: AsyncSession,
        table: str,
        columns: list[str],
    ) -> None:
        from .infrastructure.db_operations import ensure_columns_exist

        await ensure_columns_exist(session, table, columns)


@dataclass(frozen=True)
class FeatureApplicationBootstrap:
    """Explicit dependency bundle created at the module boundary."""

    storage_gateway: FeatureStorageGateway
    save_dependencies_factory: FeatureSaveDependenciesFactory


def create_feature_application_bootstrap() -> FeatureApplicationBootstrap:
    """Assemble default application dependencies at the composition root."""
    return FeatureApplicationBootstrap(
        storage_gateway=SqlAlchemyFeatureStorageGateway(),
        save_dependencies_factory=create_feature_save_dependencies,
    )


def create_feature_save_dependencies(
    session: AsyncSession,
) -> FeatureSaveDependencies:
    """Create the default dependency bundle for save use cases."""
    from .application.save_observer import create_feature_save_observer
    from .application.save_validation import create_feature_save_validator
    from .infrastructure.persistence import create_indicator_repository

    return FeatureSaveDependencies(
        repository=create_indicator_repository(session),
        validator=create_feature_save_validator(),
        observer=create_feature_save_observer(),
    )


def get_current_feature_version():
    """Resolve current feature version information at the composition root."""
    from .infrastructure.versioning import get_current_version

    return get_current_version()
