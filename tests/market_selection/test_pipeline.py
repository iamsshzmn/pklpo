"""
Тесты для pipeline orchestration.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.market_selection.application.models import PipelineResult
from src.market_selection.application.pipeline import MarketSelectionPipeline
from src.market_selection.config import MarketSelectionConfig
from src.market_selection.domain.quality_gate import QualityResult, ReasonFlag
from src.market_selection.domain.regime import GlobalRegime, RegimeType
from src.market_selection.domain.universe import UniverseEntry, UniverseStatus


@pytest.fixture
def config():
    return MarketSelectionConfig()


@pytest.fixture
def mock_session():
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
    db = AsyncMock()
    persistence = AsyncMock()
    monitoring = Mock()
    monitoring.record_pipeline_metrics = Mock()
    monitoring.record_error = Mock()
    pl = MarketSelectionPipeline(
        mock_session,
        config,
        db=db,
        persistence=persistence,
        monitoring=monitoring,
    )
    return pl


def _regime(regime_type: RegimeType = RegimeType.TREND_UP, stale: bool = False):
    return GlobalRegime(
        regime=regime_type,
        strength=0.8,
        confidence=0.9,
        stale=stale,
    )


@pytest.mark.asyncio
async def test_pipeline_success(pipeline, mock_session):
    pipeline.db.resolve_ts_eval.return_value = 1000000
    pipeline.db.validate_short_features.return_value = (True, [])
    pipeline.steps.compute_regime = AsyncMock(return_value=_regime())
    pipeline.steps.check_and_fix_stale_regime = AsyncMock(return_value=_regime())
    pipeline.persistence.insert_regime_history = AsyncMock()
    pipeline.steps.compute_quality_gate = AsyncMock(
        side_effect=[
            [
                QualityResult(
                    symbol="BTC-USDT",
                    timeframe="5m",
                    fill_rate=1.0,
                    gap_rate=0.0,
                    data_lag_seconds=60,
                    valid_bars=100,
                    expected_bars=100,
                    eligible=True,
                    quality_score=1.0,
                )
            ],
            [],
            [],
            [],
        ]
    )
    pipeline.steps.compute_pair_metrics = AsyncMock(
        return_value=__import__("pandas").DataFrame(
            {
                "symbol": ["BTC-USDT"],
                "vol_raw": [0.1],
                "trend_q_raw": [0.2],
                "noise_raw": [0.3],
                "stability_raw": [0.4],
                "liq_raw": [0.5],
            }
        )
    )
    pipeline.scoring_engine.calculate_tf_scores = Mock(return_value=[])
    pipeline.scoring_engine.aggregate_mtf_scores = Mock(return_value=[Mock(symbol="BTC-USDT")])
    pipeline.steps.select_universe = AsyncMock(
        return_value=([UniverseEntry(symbol="BTC-USDT", final_score=0.85, rank=1)], [])
    )
    pipeline.universe_manager.check_systemic_outage = Mock(return_value=False)
    pipeline.universe_manager.should_fallback = Mock(return_value=(False, None))
    pipeline.steps.publish_success = AsyncMock(
        return_value=PipelineResult(
            success=True,
            ts_version=1000000,
            ts_eval=1000000,
            universe_size=1,
            status=UniverseStatus.PUBLISHED,
            global_regime=RegimeType.TREND_UP,
        )
    )

    result = await pipeline.run()

    assert result.success is True
    assert result.status == UniverseStatus.PUBLISHED
    assert result.universe_size == 1
    assert mock_session.commit.await_count >= 1


@pytest.mark.asyncio
async def test_pipeline_no_ts_eval(pipeline):
    pipeline.db.resolve_ts_eval.return_value = None

    result = await pipeline.run()

    assert result.success is False
    assert result.error_message == "Could not resolve ts_eval - no data"
    assert result.status == UniverseStatus.FAILED


@pytest.mark.asyncio
async def test_pipeline_missing_features(pipeline):
    pipeline.db.resolve_ts_eval.return_value = 1000000
    pipeline.db.validate_short_features.return_value = (False, ["ema_200"])

    result = await pipeline.run()

    assert result.success is False
    assert "SHORT_FEATURE_MISMATCH" in result.error_message
    assert ReasonFlag.SHORT_FEATURE_MISMATCH in result.reason_flags


@pytest.mark.asyncio
async def test_pipeline_systemic_outage(pipeline):
    pipeline.db.resolve_ts_eval.return_value = 1000000
    pipeline.db.validate_short_features.return_value = (True, [])
    pipeline.steps.compute_regime = AsyncMock(return_value=_regime())
    pipeline.steps.check_and_fix_stale_regime = AsyncMock(return_value=_regime())
    pipeline.persistence.insert_regime_history = AsyncMock()
    pipeline.steps.compute_quality_gate = AsyncMock(side_effect=[[], [], [], []])
    pipeline.steps.handle_fallback = AsyncMock(
        return_value=PipelineResult(
            success=True,
            ts_version=1000000,
            ts_eval=1000000,
            universe_size=5,
            status=UniverseStatus.FALLBACK_PREV,
            global_regime=RegimeType.TREND_UP,
            reason_flags=[ReasonFlag.UNIVERSE_FALLBACK_PREV],
        )
    )

    result = await pipeline.run()

    assert result.success is True
    assert result.status == UniverseStatus.FALLBACK_PREV
    pipeline.steps.handle_fallback.assert_awaited()


@pytest.mark.asyncio
async def test_pipeline_no_final_scores(pipeline):
    pipeline.db.resolve_ts_eval.return_value = 1000000
    pipeline.db.validate_short_features.return_value = (True, [])
    pipeline.steps.compute_regime = AsyncMock(return_value=_regime())
    pipeline.steps.check_and_fix_stale_regime = AsyncMock(return_value=_regime())
    pipeline.persistence.insert_regime_history = AsyncMock()
    pipeline.steps.compute_quality_gate = AsyncMock(side_effect=[[], [], [], []])
    pipeline.universe_manager.check_systemic_outage = Mock(return_value=False)
    pipeline.scoring_engine.aggregate_mtf_scores = Mock(return_value=[])
    pipeline.steps.handle_fallback = AsyncMock(
        return_value=PipelineResult(
            success=True,
            ts_version=1000000,
            ts_eval=1000000,
            universe_size=5,
            status=UniverseStatus.FALLBACK_PREV,
            global_regime=RegimeType.TREND_UP,
        )
    )

    result = await pipeline.run()

    assert result.success is True
    assert result.status == UniverseStatus.FALLBACK_PREV


@pytest.mark.asyncio
async def test_pipeline_small_universe(pipeline):
    pipeline.db.resolve_ts_eval.return_value = 1000000
    pipeline.db.validate_short_features.return_value = (True, [])
    pipeline.steps.compute_regime = AsyncMock(return_value=_regime())
    pipeline.steps.check_and_fix_stale_regime = AsyncMock(return_value=_regime())
    pipeline.persistence.insert_regime_history = AsyncMock()
    pipeline.steps.compute_quality_gate = AsyncMock(side_effect=[[], [], [], []])
    pipeline.universe_manager.check_systemic_outage = Mock(return_value=False)
    pipeline.scoring_engine.aggregate_mtf_scores = Mock(return_value=[Mock(symbol="BTC-USDT")])
    pipeline.steps.select_universe = AsyncMock(return_value=([], []))
    pipeline.universe_manager.should_fallback = Mock(return_value=(True, "SMALL_UNIVERSE"))
    pipeline.steps.handle_fallback = AsyncMock(
        return_value=PipelineResult(
            success=True,
            ts_version=1000000,
            ts_eval=1000000,
            universe_size=5,
            status=UniverseStatus.FALLBACK_PREV,
            global_regime=RegimeType.TREND_UP,
        )
    )

    result = await pipeline.run()

    assert result.success is True
    assert result.status == UniverseStatus.FALLBACK_PREV


@pytest.mark.asyncio
async def test_pipeline_exception_rolls_back(pipeline, mock_session):
    pipeline.db.resolve_ts_eval.side_effect = Exception("DB error")

    result = await pipeline.run()

    assert result.success is False
    assert result.error_message == "DB error"
    assert result.status == UniverseStatus.FAILED
    mock_session.rollback.assert_awaited()


def test_apply_volatile_filter_marks_quality_results(pipeline):
    quality = QualityResult(
        symbol="BTC-USDT",
        timeframe="1H",
        fill_rate=1.0,
        gap_rate=0.0,
        data_lag_seconds=60,
        valid_bars=100,
        expected_bars=100,
        eligible=True,
        quality_score=1.0,
    )
    score = Mock(symbol="BTC-USDT", liq_score=0.1)
    pipeline.scoring_engine.apply_volatile_filter = Mock(return_value=["BTC-USDT"])

    filtered = pipeline._apply_volatile_filter(
        timeframe="1H",
        regime=_regime(RegimeType.VOLATILE),
        quality_by_symbol={"BTC-USDT": quality},
        scores=[score],
    )

    assert filtered == []
    assert quality.eligible is False
    assert ReasonFlag.LOW_LIQ_IN_VOLATILE in quality.reason_flags
