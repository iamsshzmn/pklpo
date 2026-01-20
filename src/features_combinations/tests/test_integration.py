"""Интеграционные тесты для features_combinations."""

import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from src.utils.session_utils import get_db_session

from ..application.service import CombinationService
from ..infrastructure import (
    NumericCombinationCalculator,
    PostgresCombinationRepository,
    PostgresIndicatorProvider,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture()
async def _test_data():
    """Подготовка тестовых данных в indicators."""
    if not (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN")):
        pytest.skip("DATABASE_URL is not set")

    async with get_db_session() as session:
        # Проверяем наличие данных
        check_query = text(
            """
            SELECT COUNT(*) FROM indicators
            WHERE symbol = 'BTC-USDT-SWAP' AND timeframe = '1m'
            AND timestamp >= :start_ts
        """
        )

        start_ts = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)
        result = await session.execute(check_query, {"start_ts": start_ts})
        count = result.scalar()

        if count < 10:
            pytest.skip(f"Not enough indicators data: {count} rows (need at least 10)")

        yield


@pytest.mark.integration()
@pytest.mark.usefixtures("_test_data")
async def test_compute_and_save_integration():
    """Интеграционный тест: расчёт и сохранение комбинаций."""
    async with get_db_session() as session:
        provider = PostgresIndicatorProvider(session)
        calculator = NumericCombinationCalculator()
        repository = PostgresCombinationRepository(session)

        service = CombinationService(
            provider=provider,
            calculator=calculator,
            repository=repository,
        )

        # Вычисляем последние 50 комбинаций
        saved = await service.compute_and_save_latest(
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            limit=50,
        )

        assert saved > 0, "Should save at least some combination rows"

        # Проверяем, что данные сохранились
        check_query = text(
            """
            SELECT COUNT(*) FROM combination_features
            WHERE symbol = 'BTC-USDT-SWAP' AND timeframe = '1m'
        """
        )

        result = await session.execute(check_query)
        count = result.scalar()

        assert count > 0, "Should have combination_features rows in DB"

        # Проверяем формат features (только числа)
        features_query = text(
            """
            SELECT features FROM combination_features
            WHERE symbol = 'BTC-USDT-SWAP' AND timeframe = '1m'
            LIMIT 5
        """
        )

        result = await session.execute(features_query)
        rows = result.fetchall()

        for row in rows:
            features = row[0]  # JSONB
            assert isinstance(features, dict), "features should be dict"
            assert all(
                isinstance(v, int | float) for v in features.values()
            ), "All feature values should be numeric"
            assert not any(
                isinstance(v, str) for v in features.values()
            ), "No string values in features"


@pytest.mark.integration()
@pytest.mark.usefixtures("_test_data")
async def test_features_numeric_only():
    """Проверка, что все features числовые."""
    async with get_db_session() as session:
        query = text(
            """
            SELECT features FROM combination_features
            WHERE symbol = 'BTC-USDT-SWAP' AND timeframe = '1m'
            LIMIT 10
        """
        )

        result = await session.execute(query)
        rows = result.fetchall()

        if not rows:
            pytest.skip("No combination_features data to test")

        for row in rows:
            features = row[0]
            if features:
                for key, value in features.items():
                    assert isinstance(
                        value, int | float
                    ), f"Feature '{key}' has non-numeric value: {value} (type: {type(value)})"
                    assert not isinstance(
                        value, str
                    ), f"Feature '{key}' is string: {value}"
