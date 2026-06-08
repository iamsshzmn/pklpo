from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest

from src.candles.interfaces.eligibility import EligibilityRecord
from src.market_selection.application.models import (
    PipelineRunContext,
    TimeframeProcessingState,
)
from src.market_selection.application.pipeline import MarketSelectionPipeline
from src.market_selection.domain.quality_gate import QualityResult
from src.market_selection.domain.regime import GlobalRegime, RegimeType
from src.market_selection.domain.scoring import TFScore


@dataclass
class _Steps:
    metric_symbols: list[str] | None = None

    async def compute_quality_gate(
        self,
        timeframe: str,
        ts_eval: int,
    ) -> list[QualityResult]:
        return [
            QualityResult(
                symbol="BTC-USDT-SWAP",
                timeframe=timeframe,
                fill_rate=1.0,
                gap_rate=0.0,
                data_lag_seconds=0,
                valid_bars=500,
                expected_bars=500,
                eligible=True,
                quality_score=1.0,
            ),
            QualityResult(
                symbol="ETH-USDT-SWAP",
                timeframe=timeframe,
                fill_rate=1.0,
                gap_rate=0.0,
                data_lag_seconds=0,
                valid_bars=500,
                expected_bars=500,
                eligible=True,
                quality_score=1.0,
            ),
        ]

    async def compute_pair_metrics(
        self,
        timeframe: str,
        ts_eval: int,
        eligible_symbols: list[str],
    ) -> pd.DataFrame:
        self.metric_symbols = eligible_symbols
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "vol": 1.0,
                    "trend_q": 1.0,
                    "noise": 1.0,
                    "stability": 1.0,
                    "liq": 1.0,
                }
                for symbol in eligible_symbols
            ]
        )


class _Scoring:
    @staticmethod
    def normalize_metrics(metrics_df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        return metrics_df

    @staticmethod
    def calculate_tf_scores(
        normalized_df: pd.DataFrame,
        timeframe: str,
        regime: RegimeType,
        quality_scores: dict[str, float],
    ) -> list[TFScore]:
        return [
            TFScore(
                symbol=str(row.symbol),
                timeframe=timeframe,
                vol_score=1.0,
                trend_q_score=1.0,
                noise_score=1.0,
                stability_score=1.0,
                liq_score=1.0,
                score_tf_base=1.0,
                score_tf=quality_scores[str(row.symbol)],
            )
            for row in normalized_df.itertuples()
        ]


class _Persistence:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def upsert_scores_tf(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class _Session:
    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_market_selection_filters_scoring_with_feature_eligibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.candles.interfaces import eligibility as eligibility_interface

    async def _get_state(symbol: str, timeframe: str) -> EligibilityRecord:
        return EligibilityRecord(
            symbol=symbol,
            timeframe=timeframe,
            state="eligible" if symbol == "BTC-USDT-SWAP" else "insufficient_history",
            can_compute_features=symbol == "BTC-USDT-SWAP",
            can_score=symbol == "BTC-USDT-SWAP",
            can_train_ml=symbol == "BTC-USDT-SWAP",
            context_only=False,
            reason_flags=[],
            actual_bars=500,
            required_bars=500,
            coverage_pct=100.0,
            evaluated_at=None,
        )

    monkeypatch.setattr(eligibility_interface, "get_state", _get_state)

    pipeline = object.__new__(MarketSelectionPipeline)
    pipeline.steps = _Steps()
    pipeline.scoring_engine = _Scoring()
    pipeline.persistence = _Persistence()
    pipeline.session = _Session()
    pipeline.config = type("Config", (), {"windows_days": {"1H": 30}})()

    state = TimeframeProcessingState()
    await pipeline._process_single_timeframe(
        "1H",
        PipelineRunContext(start_time=0.0, config_hash="cfg", ts_eval=123),
        GlobalRegime(regime=RegimeType.RANGE, strength=0.5, confidence=1.0),
        state,
    )

    assert pipeline.steps.metric_symbols == ["BTC-USDT-SWAP"]
    assert state.eligible_counts["1H"] == 1
    assert state.quality_results["1H"]["ETH-USDT-SWAP"].eligible is False
    assert state.tf_scores["1H"] == {"BTC-USDT-SWAP": 1.0}


@pytest.mark.asyncio
async def test_market_selection_fail_closes_when_feature_eligibility_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.candles.interfaces import eligibility as eligibility_interface

    async def _get_state(symbol: str, timeframe: str) -> EligibilityRecord | None:
        if symbol == "BTC-USDT-SWAP":
            return EligibilityRecord(
                symbol=symbol,
                timeframe=timeframe,
                state="eligible",
                can_compute_features=True,
                can_score=True,
                can_train_ml=True,
                context_only=False,
                reason_flags=[],
                actual_bars=500,
                required_bars=500,
                coverage_pct=100.0,
                evaluated_at=None,
            )
        return None

    monkeypatch.setattr(eligibility_interface, "get_state", _get_state)

    pipeline = object.__new__(MarketSelectionPipeline)
    pipeline.steps = _Steps()
    pipeline.scoring_engine = _Scoring()
    pipeline.persistence = _Persistence()
    pipeline.session = _Session()
    pipeline.config = type("Config", (), {"windows_days": {"1H": 30}})()

    state = TimeframeProcessingState()
    await pipeline._process_single_timeframe(
        "1H",
        PipelineRunContext(start_time=0.0, config_hash="cfg", ts_eval=123),
        GlobalRegime(regime=RegimeType.RANGE, strength=0.5, confidence=1.0),
        state,
    )

    assert pipeline.steps.metric_symbols == ["BTC-USDT-SWAP"]
    assert state.eligible_counts["1H"] == 1
    assert state.quality_results["1H"]["ETH-USDT-SWAP"].eligible is False
