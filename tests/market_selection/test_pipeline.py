"""
Тесты для pipeline (application layer).
"""

from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest

from src.market_selection.application.pipeline import (
    MarketSelectionPipeline,
)
from src.market_selection.config import MarketSelectionConfig
from src.market_selection.domain.quality_gate import QualityResult, ReasonFlag
from src.market_selection.domain.regime import GlobalRegime, RegimeType, TFRegime
from src.market_selection.domain.scoring import FinalScore, TFScore
from src.market_selection.domain.universe import UniverseEntry, UniverseStatus
from src.market_selection.infrastructure.persistence import LockTimeoutError


@pytest.fixture
def config():
    """Фикстура конфигурации."""
    return MarketSelectionConfig()


@pytest.fixture
def mock_session():
    """Фикстура мок-сессии БД."""
    class _AsyncTx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.begin = Mock(return_value=_AsyncTx())
    session.in_transaction = Mock(return_value=False)
    return session


@pytest.fixture
def pipeline(mock_session, config):
    """Фикстура MarketSelectionPipeline."""
    pl = MarketSelectionPipeline(mock_session, config)
    pl.persistence.acquire_write_lock_for_ts_version = AsyncMock(return_value=0.0)
    return pl


def create_mock_result(rows: list):
    """Создать мок результата запроса."""
    result = Mock()
    result.fetchone = Mock(return_value=rows[0] if rows else None)
    result.fetchall = Mock(return_value=rows)
    result.rowcount = len(rows)
    return result


@pytest.mark.asyncio
async def test_pipeline_success(pipeline, mock_session):
    """Тест успешного выполнения пайплайна."""
    ts_eval = 1000000
    ts_version = ts_eval

    # Мок resolve_ts_eval
    pipeline.db.resolve_ts_eval = AsyncMock(return_value=ts_eval)

    # Мок validate_short_features
    pipeline.db.validate_short_features = AsyncMock(return_value=(True, []))

    # Мок compute_regime
    regime = GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
        tf_regimes={
            "1H": TFRegime(
                timeframe="1H",
                regime=RegimeType.TREND_UP,
                strength=0.8,
                adx_median=25.0,
                atr_close_ratio=0.02,
                ema_slope=0.001,
            )
        },
        basket_symbols=["BTC-USDT", "ETH-USDT"],
        basket_size=2,
        basket_adx_median=25.0,
        basket_atr_close_median=0.02,
        basket_ema_slope_median=0.001,
    )
    pipeline._compute_regime = AsyncMock(return_value=regime)
    pipeline._check_and_fix_stale_regime = AsyncMock(return_value=regime)

    # Мок persistence.insert_regime_history
    pipeline.persistence.insert_regime_history = AsyncMock()

    # Мок quality gate для каждого TF
    quality_result = QualityResult(
        symbol="BTC-USDT",
        timeframe="1H",
        eligible=True,
        quality_score=0.95,
        fill_rate=0.98,
        gap_rate=0.01,
        data_lag_seconds=60,
        valid_bars=100,
        expected_bars=100,
        reason_flags=[],
    )
    pipeline._compute_quality_gate = AsyncMock(return_value=[quality_result])

    # Мок pair metrics
    metrics_df = pd.DataFrame(
        {
            "symbol": ["BTC-USDT"],
            "volatility": [0.02],
            "trend_quality": [0.8],
            "noise": [0.1],
            "stability": [0.9],
            "liquidity": [1000000.0],
        }
    )
    pipeline._compute_pair_metrics = AsyncMock(return_value=metrics_df)

    # Мок scoring
    tf_score = TFScore(
        symbol="BTC-USDT",
        timeframe="1H",
        vol_score=0.8,
        trend_q_score=0.9,
        noise_score=0.7,
        stability_score=0.95,
        liq_score=0.9,
        score_tf_base=0.85,
        score_tf=0.85,
    )
    pipeline.scoring_engine.normalize_metrics = Mock(return_value=metrics_df)
    pipeline.scoring_engine.calculate_tf_scores = Mock(return_value=[tf_score])
    pipeline.scoring_engine.apply_volatile_filter = Mock(return_value=[])

    # Мок persistence.upsert_scores_tf
    pipeline.persistence.upsert_scores_tf = AsyncMock()

    # Мок fetch_previous_universe
    pipeline.db.fetch_previous_universe = AsyncMock(return_value=None)

    # Мок fetch_score_history
    pipeline.db.fetch_score_history = AsyncMock(return_value=pd.DataFrame())

    # Мок select_universe
    universe_entry = UniverseEntry(
        symbol="BTC-USDT",
        rank=1,
        final_score=0.85,
        score_1h=0.85,
    )
    pipeline.universe_manager.select_universe = Mock(
        return_value=([universe_entry], [])
    )
    pipeline.universe_manager.should_fallback = Mock(return_value=(False, None))
    pipeline.universe_manager.create_version = Mock(
        return_value=Mock(
            ts_version=ts_version,
            ts_eval=ts_eval,
            status=UniverseStatus.PUBLISHED,
        )
    )

    # Мок persistence для публикации
    pipeline.persistence.insert_universe_version = AsyncMock()
    pipeline.persistence.insert_universe_entries = AsyncMock()
    pipeline.persistence.update_version_status = AsyncMock()

    # Запуск пайплайна
    result = await pipeline.run()

    # Проверки
    assert result.success is True
    assert result.ts_eval == ts_eval
    assert result.ts_version == ts_version
    assert result.universe_size == 1
    assert result.status == UniverseStatus.PUBLISHED
    assert result.global_regime == RegimeType.TREND_UP
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_pipeline_no_ts_eval(pipeline, mock_session):
    """Тест пайплайна без ts_eval."""
    pipeline.db.resolve_ts_eval = AsyncMock(return_value=None)

    result = await pipeline.run()

    assert result.success is False
    assert result.error_message == "Could not resolve ts_eval - no data"
    assert result.status == UniverseStatus.FAILED
    assert result.universe_size == 0


@pytest.mark.asyncio
async def test_pipeline_missing_features(pipeline, mock_session):
    """Тест пайплайна с отсутствующими фичами."""
    ts_eval = 1000000
    pipeline.db.resolve_ts_eval = AsyncMock(return_value=ts_eval)
    pipeline.db.validate_short_features = AsyncMock(return_value=(False, ["ema_200"]))

    result = await pipeline.run()

    assert result.success is False
    assert "SHORT_FEATURE_MISMATCH" in result.error_message
    assert ReasonFlag.SHORT_FEATURE_MISMATCH in result.reason_flags
    assert result.status == UniverseStatus.FAILED


@pytest.mark.asyncio
async def test_pipeline_systemic_outage(pipeline, mock_session):
    """Тест пайплайна с системным сбоем."""
    ts_eval = 1000000
    ts_version = ts_eval

    pipeline.db.resolve_ts_eval = AsyncMock(return_value=ts_eval)
    pipeline.db.validate_short_features = AsyncMock(return_value=(True, []))

    regime = GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
        tf_regimes={},
        basket_symbols=[],
        basket_size=0,
        basket_adx_median=0.0,
        basket_atr_close_median=0.0,
        basket_ema_slope_median=0.0,
    )
    pipeline._compute_regime = AsyncMock(return_value=regime)
    pipeline._check_and_fix_stale_regime = AsyncMock(return_value=regime)
    pipeline.persistence.insert_regime_history = AsyncMock()

    # Все TF имеют 0 eligible символов
    pipeline._compute_quality_gate = AsyncMock(return_value=[])

    # Мок fallback
    pipeline.db.get_last_published_version = AsyncMock(return_value=100)
    pipeline.persistence.insert_universe_version = AsyncMock()
    pipeline.persistence.copy_previous_universe_with_metrics = AsyncMock(
        return_value={
            "source_count": 5,
            "source_duplicates": 0,
            "inserted_count": 5,
            "skipped_conflicts": 0,
        }
    )
    pipeline.persistence.update_version_status = AsyncMock()

    result = await pipeline.run()

    assert result.success is True
    assert result.status == UniverseStatus.FALLBACK_PREV
    assert result.universe_size == 5
    assert ReasonFlag.UNIVERSE_FALLBACK_PREV in result.reason_flags
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_pipeline_no_final_scores(pipeline, mock_session):
    """Тест пайплайна без финальных скоров."""
    ts_eval = 1000000
    ts_version = ts_eval

    pipeline.db.resolve_ts_eval = AsyncMock(return_value=ts_eval)
    pipeline.db.validate_short_features = AsyncMock(return_value=(True, []))

    regime = GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
        tf_regimes={},
        basket_symbols=[],
        basket_size=0,
        basket_adx_median=0.0,
        basket_atr_close_median=0.0,
        basket_ema_slope_median=0.0,
    )
    pipeline._compute_regime = AsyncMock(return_value=regime)
    pipeline._check_and_fix_stale_regime = AsyncMock(return_value=regime)
    pipeline.persistence.insert_regime_history = AsyncMock()

    quality_result = QualityResult(
        symbol="BTC-USDT",
        timeframe="1H",
        eligible=True,
        quality_score=0.95,
        fill_rate=0.98,
        gap_rate=0.01,
        data_lag_seconds=60,
        valid_bars=100,
        expected_bars=100,
        reason_flags=[],
    )
    pipeline._compute_quality_gate = AsyncMock(return_value=[quality_result])
    pipeline._compute_pair_metrics = AsyncMock(return_value=pd.DataFrame())
    pipeline.scoring_engine.aggregate_mtf_scores = Mock(return_value=[])

    # Мок fallback
    pipeline.db.get_last_published_version = AsyncMock(return_value=100)
    pipeline.persistence.insert_universe_version = AsyncMock()
    pipeline.persistence.copy_previous_universe_with_metrics = AsyncMock(
        return_value={
            "source_count": 5,
            "source_duplicates": 0,
            "inserted_count": 5,
            "skipped_conflicts": 0,
        }
    )
    pipeline.persistence.update_version_status = AsyncMock()

    result = await pipeline.run()

    assert result.success is True
    assert result.status == UniverseStatus.FALLBACK_PREV
    assert result.universe_size == 5


@pytest.mark.asyncio
async def test_pipeline_small_universe(pipeline, mock_session):
    """Тест пайплайна с маленькой вселенной."""
    ts_eval = 1000000
    ts_version = ts_eval

    pipeline.db.resolve_ts_eval = AsyncMock(return_value=ts_eval)
    pipeline.db.validate_short_features = AsyncMock(return_value=(True, []))

    regime = GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
        tf_regimes={},
        basket_symbols=[],
        basket_size=0,
        basket_adx_median=0.0,
        basket_atr_close_median=0.0,
        basket_ema_slope_median=0.0,
    )
    pipeline._compute_regime = AsyncMock(return_value=regime)
    pipeline._check_and_fix_stale_regime = AsyncMock(return_value=regime)
    pipeline.persistence.insert_regime_history = AsyncMock()

    quality_result = QualityResult(
        symbol="BTC-USDT",
        timeframe="1H",
        eligible=True,
        quality_score=0.95,
        fill_rate=0.98,
        gap_rate=0.01,
        data_lag_seconds=60,
        valid_bars=100,
        expected_bars=100,
        reason_flags=[],
    )
    pipeline._compute_quality_gate = AsyncMock(return_value=[quality_result])

    metrics_df = pd.DataFrame(
        {
            "symbol": ["BTC-USDT"],
            "volatility": [0.02],
            "trend_quality": [0.8],
            "noise": [0.1],
            "stability": [0.9],
            "liquidity": [1000000.0],
        }
    )
    pipeline._compute_pair_metrics = AsyncMock(return_value=metrics_df)

    tf_score = TFScore(
        symbol="BTC-USDT",
        timeframe="1H",
        vol_score=0.8,
        trend_q_score=0.9,
        noise_score=0.7,
        stability_score=0.95,
        liq_score=0.9,
        score_tf_base=0.85,
        score_tf=0.85,
    )
    pipeline.scoring_engine.normalize_metrics = Mock(return_value=metrics_df)
    pipeline.scoring_engine.calculate_tf_scores = Mock(return_value=[tf_score])
    pipeline.scoring_engine.apply_volatile_filter = Mock(return_value=[])
    pipeline.persistence.upsert_scores_tf = AsyncMock()

    final_score = FinalScore(
        symbol="BTC-USDT",
        final_score=0.85,
        score_1h=0.85,
        score_4h=None,
    )
    pipeline.scoring_engine.aggregate_mtf_scores = Mock(return_value=[final_score])

    pipeline.db.fetch_previous_universe = AsyncMock(return_value=None)
    pipeline.db.fetch_score_history = AsyncMock(return_value=pd.DataFrame())

    # Вселенная слишком маленькая
    pipeline.universe_manager.select_universe = Mock(return_value=([], []))
    pipeline.universe_manager.should_fallback = Mock(
        return_value=(True, "SMALL_UNIVERSE")
    )

    # Мок fallback
    pipeline.db.get_last_published_version = AsyncMock(return_value=100)
    pipeline.persistence.insert_universe_version = AsyncMock()
    pipeline.persistence.copy_previous_universe_with_metrics = AsyncMock(
        return_value={
            "source_count": 5,
            "source_duplicates": 0,
            "inserted_count": 5,
            "skipped_conflicts": 0,
        }
    )
    pipeline.persistence.update_version_status = AsyncMock()

    result = await pipeline.run()

    assert result.success is True
    assert result.status == UniverseStatus.FALLBACK_PREV
    assert result.universe_size == 5


@pytest.mark.asyncio
async def test_pipeline_exception(pipeline, mock_session):
    """Тест пайплайна с исключением."""
    pipeline.db.resolve_ts_eval = AsyncMock(side_effect=Exception("DB error"))

    result = await pipeline.run()

    assert result.success is False
    assert result.error_message == "DB error"
    assert result.status == UniverseStatus.FAILED
    assert mock_session.rollback.called


@pytest.mark.asyncio
async def test_pipeline_stale_regime(pipeline, mock_session):
    """Тест пайплайна с устаревшим режимом."""
    ts_eval = 1000000

    pipeline.db.resolve_ts_eval = AsyncMock(return_value=ts_eval)
    pipeline.db.validate_short_features = AsyncMock(return_value=(True, []))

    # Исходный режим
    regime = GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
        tf_regimes={},
        basket_symbols=[],
        basket_size=0,
        basket_adx_median=0.0,
        basket_atr_close_median=0.0,
        basket_ema_slope_median=0.0,
    )
    pipeline._compute_regime = AsyncMock(return_value=regime)

    # Мок проверки stale regime
    stale_regime = GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=True,  # Помечен как stale
        tf_regimes={},
        basket_symbols=[],
        basket_size=0,
        basket_adx_median=0.0,
        basket_atr_close_median=0.0,
        basket_ema_slope_median=0.0,
    )
    pipeline._check_and_fix_stale_regime = AsyncMock(return_value=stale_regime)
    pipeline.persistence.insert_regime_history = AsyncMock()

    # Остальные моки для успешного завершения
    quality_result = QualityResult(
        symbol="BTC-USDT",
        timeframe="1H",
        eligible=True,
        quality_score=0.95,
        fill_rate=0.98,
        gap_rate=0.01,
        data_lag_seconds=60,
        valid_bars=100,
        expected_bars=100,
        reason_flags=[],
    )
    pipeline._compute_quality_gate = AsyncMock(return_value=[quality_result])

    metrics_df = pd.DataFrame(
        {
            "symbol": ["BTC-USDT"],
            "volatility": [0.02],
            "trend_quality": [0.8],
            "noise": [0.1],
            "stability": [0.9],
            "liquidity": [1000000.0],
        }
    )
    pipeline._compute_pair_metrics = AsyncMock(return_value=metrics_df)

    tf_score = TFScore(
        symbol="BTC-USDT",
        timeframe="1H",
        vol_score=0.8,
        trend_q_score=0.9,
        noise_score=0.7,
        stability_score=0.95,
        liq_score=0.9,
        score_tf_base=0.85,
        score_tf=0.85,
    )
    pipeline.scoring_engine.normalize_metrics = Mock(return_value=metrics_df)
    pipeline.scoring_engine.calculate_tf_scores = Mock(return_value=[tf_score])
    pipeline.scoring_engine.apply_volatile_filter = Mock(return_value=[])
    pipeline.persistence.upsert_scores_tf = AsyncMock()

    final_score = FinalScore(
        symbol="BTC-USDT",
        final_score=0.85,
        score_1h=0.85,
        score_4h=None,
    )
    pipeline.scoring_engine.aggregate_mtf_scores = Mock(return_value=[final_score])

    pipeline.db.fetch_previous_universe = AsyncMock(return_value=None)
    pipeline.db.fetch_score_history = AsyncMock(return_value=pd.DataFrame())

    universe_entry = UniverseEntry(
        symbol="BTC-USDT",
        rank=1,
        final_score=0.85,
        score_1h=0.85,
    )
    pipeline.universe_manager.select_universe = Mock(
        return_value=([universe_entry], [])
    )
    pipeline.universe_manager.should_fallback = Mock(return_value=(False, None))
    pipeline.universe_manager.create_version = Mock(
        return_value=Mock(
            ts_version=ts_eval,
            ts_eval=ts_eval,
            status=UniverseStatus.PUBLISHED,
        )
    )

    pipeline.persistence.insert_universe_version = AsyncMock()
    pipeline.persistence.insert_universe_entries = AsyncMock()
    pipeline.persistence.update_version_status = AsyncMock()

    result = await pipeline.run()

    assert result.success is True
    assert result.global_regime == RegimeType.TREND_UP


@pytest.mark.asyncio
async def test_pipeline_volatile_filter(pipeline, mock_session):
    """Тест пайплайна с фильтром VOLATILE режима."""
    ts_eval = 1000000
    ts_version = ts_eval

    pipeline.db.resolve_ts_eval = AsyncMock(return_value=ts_eval)
    pipeline.db.validate_short_features = AsyncMock(return_value=(True, []))

    # VOLATILE режим
    regime = GlobalRegime(
        regime=RegimeType.VOLATILE,
        strength=0.8,
        confidence=0.9,
        stale=False,
        tf_regimes={},
        basket_symbols=[],
        basket_size=0,
        basket_adx_median=0.0,
        basket_atr_close_median=0.0,
        basket_ema_slope_median=0.0,
    )
    pipeline._compute_regime = AsyncMock(return_value=regime)
    pipeline._check_and_fix_stale_regime = AsyncMock(return_value=regime)
    pipeline.persistence.insert_regime_history = AsyncMock()

    quality_result = QualityResult(
        symbol="BTC-USDT",
        timeframe="1H",
        eligible=True,
        quality_score=0.95,
        fill_rate=0.98,
        gap_rate=0.01,
        data_lag_seconds=60,
        valid_bars=100,
        expected_bars=100,
        reason_flags=[],
    )
    pipeline._compute_quality_gate = AsyncMock(return_value=[quality_result])

    metrics_df = pd.DataFrame(
        {
            "symbol": ["BTC-USDT"],
            "volatility": [0.02],
            "trend_quality": [0.8],
            "noise": [0.1],
            "stability": [0.9],
            "liquidity": [1000000.0],
        }
    )
    pipeline._compute_pair_metrics = AsyncMock(return_value=metrics_df)

    tf_score = TFScore(
        symbol="BTC-USDT",
        timeframe="1H",
        vol_score=0.8,
        trend_q_score=0.9,
        noise_score=0.7,
        stability_score=0.95,
        liq_score=0.9,
        score_tf_base=0.85,
        score_tf=0.85,
    )
    pipeline.scoring_engine.normalize_metrics = Mock(return_value=metrics_df)
    pipeline.scoring_engine.calculate_tf_scores = Mock(return_value=[tf_score])
    # Фильтр исключает символ
    pipeline.scoring_engine.apply_volatile_filter = Mock(return_value=["BTC-USDT"])
    pipeline.persistence.upsert_scores_tf = AsyncMock()

    # После фильтрации нет символов
    pipeline.scoring_engine.aggregate_mtf_scores = Mock(return_value=[])

    # Мок fallback
    pipeline.db.get_last_published_version = AsyncMock(return_value=100)
    pipeline.persistence.insert_universe_version = AsyncMock()
    pipeline.persistence.copy_previous_universe_with_metrics = AsyncMock(
        return_value={
            "source_count": 5,
            "source_duplicates": 0,
            "inserted_count": 5,
            "skipped_conflicts": 0,
        }
    )
    pipeline.persistence.update_version_status = AsyncMock()

    # Сохраняем ссылку на quality_result для проверки после выполнения
    quality_results_list = [quality_result]
    pipeline._compute_quality_gate = AsyncMock(return_value=quality_results_list)

    result = await pipeline.run()

    assert result.success is True
    assert result.status == UniverseStatus.FALLBACK_PREV
    # Проверяем, что символ помечен как не eligible после фильтрации
    assert quality_result.eligible is False
    assert ReasonFlag.LOW_LIQ_IN_VOLATILE in quality_result.reason_flags


@pytest.mark.asyncio
async def test_pipeline_fallback_no_previous(pipeline, mock_session):
    """Тест пайплайна с fallback, но без предыдущей вселенной."""
    ts_eval = 1000000
    ts_version = ts_eval

    pipeline.db.resolve_ts_eval = AsyncMock(return_value=ts_eval)
    pipeline.db.validate_short_features = AsyncMock(return_value=(True, []))

    regime = GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
        tf_regimes={},
        basket_symbols=[],
        basket_size=0,
        basket_adx_median=0.0,
        basket_atr_close_median=0.0,
        basket_ema_slope_median=0.0,
    )
    pipeline._compute_regime = AsyncMock(return_value=regime)
    pipeline._check_and_fix_stale_regime = AsyncMock(return_value=regime)
    pipeline.persistence.insert_regime_history = AsyncMock()

    pipeline._compute_quality_gate = AsyncMock(return_value=[])

    # Нет предыдущей вселенной
    pipeline.db.get_last_published_version = AsyncMock(return_value=None)

    result = await pipeline.run()

    assert result.success is False
    assert result.error_message == "No previous universe for fallback"
    assert result.status == UniverseStatus.FAILED
    assert ReasonFlag.UNIVERSE_FALLBACK_PREV in result.reason_flags


@pytest.mark.asyncio
async def test_pipeline_lock_timeout_returns_failed_result(pipeline, mock_session):
    """Тест abort ветки при timeout advisory lock."""
    ts_eval = 1000000
    pipeline.db.resolve_ts_eval = AsyncMock(return_value=ts_eval)
    pipeline.db.validate_short_features = AsyncMock(return_value=(True, []))

    regime = GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
        tf_regimes={},
        basket_symbols=[],
        basket_size=0,
        basket_adx_median=0.0,
        basket_atr_close_median=0.0,
        basket_ema_slope_median=0.0,
    )
    pipeline._compute_regime = AsyncMock(return_value=regime)
    pipeline._check_and_fix_stale_regime = AsyncMock(return_value=regime)
    pipeline.persistence.insert_regime_history = AsyncMock()
    pipeline._compute_quality_gate = AsyncMock(return_value=[])
    pipeline.db.get_last_published_version = AsyncMock(return_value=100)
    pipeline.persistence.insert_universe_version = AsyncMock()
    pipeline.persistence.copy_previous_universe_with_metrics = AsyncMock(
        return_value={
            "source_count": 5,
            "source_duplicates": 0,
            "inserted_count": 5,
            "skipped_conflicts": 0,
        }
    )
    pipeline.persistence.update_version_status = AsyncMock()
    pipeline.persistence.acquire_write_lock_for_ts_version = AsyncMock(
        side_effect=LockTimeoutError("lock timeout")
    )

    result = await pipeline.run()

    assert result.success is False
    assert result.status == UniverseStatus.FAILED
    assert result.error_message == "lock timeout"
