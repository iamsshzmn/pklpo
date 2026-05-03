"""Skipped: src.platform_ops was removed. Delete once equivalent tests exist."""
from __future__ import annotations

import pytest

pytest.importorskip("src.platform_ops", reason="src.platform_ops module was removed")

import os
import socket
import time
import uuid

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import src.platform_ops.application.indicators_partition_maintenance as maintenance_app
import src.platform_ops.infrastructure.postgres_indicators_partition_maintenance as adapter_module
from src.platform_ops.application.indicators_partition_maintenance import (
    EnsureIndicatorsPartitionWindow,
    ValidateIndicatorsPartitionHorizon,
)
from src.platform_ops.infrastructure import (
    PostgresIndicatorsPartitionMaintenanceAdapter,
)


def _resolve_test_db_url() -> str | None:
    db_url = os.getenv("INDICATORS_PARTITION_TEST_DATABASE_URL") or os.getenv(
        "DATABASE_URL"
    )
    if not db_url:
        return None
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return db_url


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_partition_adapter_creates_window_idempotently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_url = _resolve_test_db_url()
    if not db_url:
        pytest.skip("INDICATORS_PARTITION_TEST_DATABASE_URL or DATABASE_URL is required")

    table_name = f"indicators_p_test_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    engine = create_async_engine(db_url, future=True)
    session_factory = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    monkeypatch.setattr(maintenance_app, "PARENT_TABLE", table_name)
    monkeypatch.setattr(adapter_module, "PARENT_TABLE", table_name)

    try:
        async with engine.begin():
            pass
    except (OSError, socket.gaierror, SQLAlchemyError) as exc:
        await engine.dispose()
        pytest.skip(f"test database is not reachable: {exc}")

    try:
        async with session_factory() as session:
            adapter = PostgresIndicatorsPartitionMaintenanceAdapter(session)
            ensure_use_case = EnsureIndicatorsPartitionWindow(adapter)

            await adapter.ensure_parent_exists()
            await session.execute(
                text(
                    f"""
                    ALTER TABLE {table_name}
                    ADD CONSTRAINT {table_name}_symbol_tf_ts_uniq
                    UNIQUE (symbol, timeframe, timestamp)
                    """
                )
            )
            await session.commit()

            first_result = await ensure_use_case.execute(
                months_back=0,
                months_ahead=1,
                reference_dt=maintenance_app.datetime(
                    2026, 3, 7, tzinfo=maintenance_app.UTC
                ),
                require_parent_pk=True,
            )
            await session.commit()

            second_result = await ensure_use_case.execute(
                months_back=0,
                months_ahead=1,
                reference_dt=maintenance_app.datetime(
                    2026, 3, 7, tzinfo=maintenance_app.UTC
                ),
                require_parent_pk=True,
            )
            await session.commit()

            validate_use_case = ValidateIndicatorsPartitionHorizon(adapter)
            coverage = await validate_use_case.execute(
                months_ahead=1,
                reference_dt=maintenance_app.datetime(
                    2026, 3, 7, tzinfo=maintenance_app.UTC
                ),
            )

            assert first_result.created_count == 2
            assert second_result.created_count == 0
            assert second_result.existing_count == 2
            assert coverage.actual_months_ahead == 1
            assert coverage.missing_partitions == []

            for partition_name in first_result.created_partitions:
                indexes = await session.execute(
                    text(
                        """
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname = 'public' AND tablename = :table_name
                        ORDER BY indexname
                        """
                    ),
                    {"table_name": partition_name},
                )
                rows = indexes.fetchall()
                assert any(
                    'USING brin ("timestamp")' in row[1] for row in rows
                )
                assert any(
                    'USING btree (symbol, timeframe, "timestamp")' in row[1]
                    or '(symbol, timeframe, "timestamp")' in row[1]
                    for row in rows
                )
    finally:
        async with session_factory() as session:
            await session.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
            await session.commit()
        await engine.dispose()
