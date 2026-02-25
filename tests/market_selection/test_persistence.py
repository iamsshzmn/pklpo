"""
Тесты для persistence operations (сохранение данных).
"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.market_selection.domain.quality_gate import QualityResult
from src.market_selection.domain.regime import GlobalRegime, RegimeType
from src.market_selection.domain.scoring import TFScore
from src.market_selection.domain.universe import (
    UniverseEntry,
    UniverseStatus,
    UniverseVersion,
)
from src.market_selection.infrastructure.persistence import (
    LockTimeoutError,
    MarketSelectionPersistence,
)


@pytest.fixture
def mock_session():
    """Фикстура мок-сессии БД."""
    session = AsyncMock()
    return session


@pytest.fixture
def persistence(mock_session):
    """Фикстура MarketSelectionPersistence."""
    return MarketSelectionPersistence(mock_session)


@pytest.fixture
def sample_regime():
    """Фикстура примера режима."""
    return GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
    )


@pytest.fixture
def sample_tf_scores():
    """Фикстура примеров TFScore."""
    return [
        TFScore(
            symbol="BTC-USDT",
            timeframe="1H",
            vol_score=0.8,
            trend_q_score=0.9,
            noise_score=0.7,
            stability_score=0.85,
            liq_score=0.9,
            score_tf_base=0.85,
            score_tf=0.85,
        ),
        TFScore(
            symbol="ETH-USDT",
            timeframe="1H",
            vol_score=0.7,
            trend_q_score=0.8,
            noise_score=0.6,
            stability_score=0.75,
            liq_score=0.8,
            score_tf_base=0.75,
            score_tf=0.75,
        ),
    ]


@pytest.fixture
def sample_quality_results():
    """Фикстура примеров QualityResult."""
    return {
        "BTC-USDT": QualityResult(
            symbol="BTC-USDT",
            timeframe="1H",
            fill_rate=1.0,
            gap_rate=0.0,
            data_lag_seconds=60,
            valid_bars=1000,
            expected_bars=1000,
            eligible=True,
            quality_score=1.0,
        ),
        "ETH-USDT": QualityResult(
            symbol="ETH-USDT",
            timeframe="1H",
            fill_rate=0.98,
            gap_rate=0.01,
            data_lag_seconds=120,
            valid_bars=980,
            expected_bars=1000,
            eligible=True,
            quality_score=0.95,
        ),
    }


@pytest.mark.asyncio
async def test_upsert_scores_tf(
    persistence, mock_session, sample_tf_scores, sample_quality_results, sample_regime
):
    """Тест сохранения оценок по таймфреймам."""
    metrics_raw = {
        "BTC-USDT": {
            "vol_raw": 0.02,
            "trend_q_raw": 0.5,
            "noise_raw": 1.5,
            "stability_raw": 0.8,
            "liq_raw": 1000.0,
        },
        "ETH-USDT": {
            "vol_raw": 0.018,
            "trend_q_raw": 0.45,
            "noise_raw": 1.3,
            "stability_raw": 0.75,
            "liq_raw": 800.0,
        },
    }

    mock_result = Mock()
    mock_result.rowcount = 2
    mock_session.execute = AsyncMock(return_value=mock_result)

    count = await persistence.upsert_scores_tf(
        ts_eval=1000000,
        timeframe="1H",
        scores=sample_tf_scores,
        quality_results=sample_quality_results,
        metrics_raw=metrics_raw,
        regime=sample_regime,
        config_hash="test_hash",
        window_days=30,
    )

    assert count == 2
    # Должно быть вызвано execute для каждого score
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_upsert_scores_tf_empty(persistence, mock_session, sample_regime):
    """Тест сохранения пустого списка оценок."""
    count = await persistence.upsert_scores_tf(
        ts_eval=1000000,
        timeframe="1H",
        scores=[],
        quality_results={},
        metrics_raw={},
        regime=sample_regime,
        config_hash="test_hash",
        window_days=30,
    )

    assert count == 0
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_insert_universe_version(persistence, mock_session):
    """Тест сохранения версии вселенной."""
    version = UniverseVersion(
        ts_version=1000000,
        ts_eval=1000000,
        status=UniverseStatus.PUBLISHED,
        universe_size=30,
        eligible_count=100,
        config_hash="test_hash",
    )

    mock_result = Mock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    await persistence.insert_universe_version(version)

    mock_session.execute.assert_called_once()
    # Проверяем, что был вызван с правильными параметрами
    call_args = mock_session.execute.call_args
    assert call_args is not None


@pytest.mark.asyncio
async def test_insert_universe_entries(persistence, mock_session):
    """Тест сохранения записей вселенной."""
    entries = [
        UniverseEntry(
            symbol="BTC-USDT",
            final_score=0.9,
            rank=1,
            score_4h=0.85,
            score_1h=0.88,
        ),
        UniverseEntry(
            symbol="ETH-USDT",
            final_score=0.8,
            rank=2,
            score_4h=0.78,
            score_1h=0.82,
        ),
    ]

    mock_result = Mock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    count = await persistence.insert_universe_entries(
        ts_version=1000000,
        entries=entries,
        config_hash="test_hash",
    )

    assert count == 2
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_insert_universe_entries_empty(persistence, mock_session):
    """Тест сохранения пустого списка записей."""
    count = await persistence.insert_universe_entries(
        ts_version=1000000,
        entries=[],
        config_hash="test_hash",
    )

    assert count == 0
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_update_version_status(persistence, mock_session):
    """Тест обновления статуса версии."""
    mock_result = Mock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    await persistence.update_version_status(
        ts_version=1000000,
        status="published",
        notes="Test notes",
    )

    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_copy_previous_universe(persistence, mock_session):
    """Тест копирования предыдущей вселенной."""
    mock_result = Mock()
    mock_result.mappings.return_value.one.return_value = {
        "source_count": 30,
        "source_duplicates": 0,
        "inserted_count": 30,
        "skipped_conflicts": 0,
    }
    mock_session.execute = AsyncMock(return_value=mock_result)

    count = await persistence.copy_previous_universe(
        new_ts_version=1000001,
        source_ts_version=1000000,
        config_hash="test_hash",
    )

    assert count == 30
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_copy_previous_universe_with_metrics(persistence, mock_session):
    """Тест детерминированных метрик fallback-copy."""
    metrics_row = {
        "source_count": 30,
        "source_duplicates": 0,
        "inserted_count": 30,
        "skipped_conflicts": 0,
    }
    mock_result = Mock()
    mock_result.mappings.return_value.one.return_value = metrics_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    metrics = await persistence.copy_previous_universe_with_metrics(
        new_ts_version=1000001,
        source_ts_version=1000000,
        config_hash="test_hash",
    )

    assert metrics == metrics_row
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_copy_previous_universe_returns_inserted_count_from_metrics(
    persistence, mock_session
):
    """Текущий контракт copy_previous_universe -> int сохраняется."""
    mock_result = Mock()
    mock_result.mappings.return_value.one.return_value = {
        "source_count": 40,
        "source_duplicates": 2,
        "inserted_count": 35,
        "skipped_conflicts": 3,
    }
    mock_session.execute = AsyncMock(return_value=mock_result)

    inserted = await persistence.copy_previous_universe(
        new_ts_version=1000001,
        source_ts_version=1000000,
        config_hash="test_hash",
    )

    assert inserted == 35


@pytest.mark.asyncio
async def test_acquire_write_lock_for_ts_version(persistence, mock_session):
    """Тест acquire advisory lock с локальным lock_timeout."""
    mock_session.execute = AsyncMock()

    wait_seconds = await persistence.acquire_write_lock_for_ts_version(
        ts_version=1000000,
        lock_timeout_ms=5000,
    )

    assert wait_seconds >= 0
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_acquire_write_lock_for_ts_version_timeout(persistence, mock_session):
    """Тест преобразования lock timeout в LockTimeoutError."""

    async def _execute_side_effect(query, params=None):
        query_str = str(query)
        if "pg_advisory_xact_lock" in query_str:
            raise RuntimeError("canceling statement due to lock timeout")
        return Mock()

    mock_session.execute = AsyncMock(side_effect=_execute_side_effect)

    with pytest.raises(LockTimeoutError):
        await persistence.acquire_write_lock_for_ts_version(
            ts_version=1000000,
            lock_timeout_ms=5000,
        )


@pytest.mark.asyncio
async def test_acquire_write_lock_for_ts_version_out_of_int8_range(
    persistence, mock_session
):
    """Тест валидации ts_version в диапазоне signed BIGINT."""
    with pytest.raises(ValueError):
        await persistence.acquire_write_lock_for_ts_version(
            ts_version=2**63,
            lock_timeout_ms=5000,
        )
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_insert_regime_history(persistence, mock_session, sample_regime):
    """Тест сохранения истории режима."""
    mock_result = Mock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    await persistence.insert_regime_history(
        ts_eval=1000000,
        regime=sample_regime,
        config_hash="test_hash",
    )

    mock_session.execute.assert_called_once()
    # Проверяем, что данные режима переданы корректно
    call_args = mock_session.execute.call_args
    assert call_args is not None
    params = call_args[0][1]  # Второй аргумент - параметры
    assert params["ts_eval"] == 1000000
    assert params["global_regime"] == "TREND_UP"
    assert params["is_stale"] is False


@pytest.mark.asyncio
async def test_cleanup_old_data(persistence, mock_session):
    """Тест очистки старых данных."""
    # Мок для удаления scores
    scores_result = Mock()
    scores_result.rowcount = 100

    # Мок для удаления universe
    universe_result = Mock()
    universe_result.rowcount = 50

    # Мок для удаления versions
    version_result = Mock()

    async def mock_execute(query, params=None):
        query_str = str(query)
        if "market_scores_tf" in query_str:
            return scores_result
        if (
            "market_universe" in query_str
            and "DELETE FROM market_universe" in query_str
        ):
            return universe_result
        return version_result

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    scores_deleted, universe_deleted = await persistence.cleanup_old_data(
        scores_retention_days=180,
        universe_retention_days=90,
    )

    assert scores_deleted == 100
    assert universe_deleted == 50
    # Должно быть 3 вызова: scores, universe entries, universe versions
    assert mock_session.execute.call_count == 3
