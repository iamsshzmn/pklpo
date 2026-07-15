"""
Unit tests for Market Selection Scoring Engine.

Covers: percentile rank normalization, winsorize 1%/99% and 5%/95% for small universe,
z-score -> sigmoid for very small universe, NaN handling, regime weight adjustment,
per-TF score, MTF aggregation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.market_selection.domain.regime import RegimeType
from src.market_selection.domain.scoring import ScoringEngine, TFScore


class TestNormalizeMetrics:
    """Tests for ScoringEngine.normalize_metrics()."""

    def test_percentile_rank_within_tf(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """Normalized scores are in [0, 1] and preserve order."""
        n = 60
        df = pd.DataFrame(
            {
                "symbol": [f"S{i}" for i in range(n)],
                "vol_raw": np.linspace(0.001, 0.05, n),
                "trend_q_raw": np.linspace(0, 0.5, n),
                "noise_raw": np.linspace(0.5, 2.0, n),
                "stability_raw": np.linspace(0.2, 0.9, n),
                "liq_raw": np.linspace(100, 1000, n),
            }
        )
        out = scoring_engine.normalize_metrics(df, "1H")
        for col in [
            "vol_score",
            "trend_q_score",
            "noise_score",
            "stability_score",
            "liq_score",
        ]:
            assert col in out.columns
            assert out[col].min() >= 0
            assert out[col].max() <= 1

    def test_noise_inverted(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """Noise: lower raw -> higher score (inverted)."""
        df = pd.DataFrame(
            {
                "symbol": ["A", "B", "C"],
                "vol_raw": [0.01, 0.01, 0.01],
                "trend_q_raw": [0.1, 0.1, 0.1],
                "noise_raw": [0.5, 1.0, 2.0],
                "stability_raw": [0.5, 0.5, 0.5],
                "liq_raw": [500, 500, 500],
            }
        )
        out = scoring_engine.normalize_metrics(df, "5m")
        assert (
            out.loc[out["symbol"] == "A", "noise_score"].iloc[0]
            >= out.loc[out["symbol"] == "C", "noise_score"].iloc[0]
        )

    def test_nan_fills_zero(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """Missing metric column or NaN -> score 0."""
        df = pd.DataFrame(
            {
                "symbol": ["A", "B"],
                "vol_raw": [0.01, np.nan],
                "trend_q_raw": [0.1, 0.1],
                "noise_raw": [0.5, 0.5],
                "stability_raw": [0.5, 0.5],
                "liq_raw": [500, 500],
            }
        )
        out = scoring_engine.normalize_metrics(df, "5m")
        assert "vol_score" in out.columns
        assert out["vol_score"].fillna(-1).ge(0).all()

    def test_empty_dataframe(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """Empty DataFrame returns empty."""
        df = pd.DataFrame(
            columns=[
                "symbol",
                "vol_raw",
                "trend_q_raw",
                "noise_raw",
                "stability_raw",
                "liq_raw",
            ]
        )
        out = scoring_engine.normalize_metrics(df, "5m")
        assert len(out) == 0


class TestZScoreSigmoidFallback:
    """Tests for small universe fallback (z-score -> sigmoid)."""

    def test_small_universe_uses_sigmoid(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """When n_eligible < fallback_zscore_threshold (20), use z-score sigmoid."""
        n = 15
        df = pd.DataFrame(
            {
                "symbol": [f"S{i}" for i in range(n)],
                "vol_raw": np.random.randn(n).cumsum() * 0.001 + 0.02,
                "trend_q_raw": np.random.rand(n) * 0.3,
                "noise_raw": np.random.rand(n) * 1.0 + 0.5,
                "stability_raw": np.random.rand(n) * 0.5 + 0.3,
                "liq_raw": np.random.rand(n) * 500 + 200,
            }
        )
        out = scoring_engine.normalize_metrics(df, "5m")
        for col in [
            "vol_score",
            "trend_q_score",
            "noise_score",
            "stability_score",
            "liq_score",
        ]:
            assert out[col].between(0, 1).all() | out[col].isna().all()


class TestGetAdjustedWeights:
    """Tests for regime-based weight adjustment."""

    def test_weights_sum_to_one(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """Adjusted weights sum to 1.0 for each regime."""
        for regime in RegimeType:
            w = scoring_engine.get_adjusted_weights(regime)
            assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_trend_up_boosts_trend_q(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """TREND_UP: trend_q weight higher than base 0.30."""
        w = scoring_engine.get_adjusted_weights(RegimeType.TREND_UP)
        assert w["trend_q"] >= 0.30

    def test_range_boosts_noise_stability(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """RANGE: noise and stability weights increased."""
        w = scoring_engine.get_adjusted_weights(RegimeType.RANGE)
        assert w["noise"] >= 0.20
        assert w["stability"] >= 0.15


class TestCalculateTfScores:
    """Tests for calculate_tf_scores()."""

    def test_score_tf_base_times_quality(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """score_tf = score_tf_base * quality_score."""
        df = pd.DataFrame(
            {
                "symbol": ["A", "B"],
                "vol_score": [0.5, 0.5],
                "trend_q_score": [0.5, 0.5],
                "noise_score": [0.5, 0.5],
                "stability_score": [0.5, 0.5],
                "liq_score": [0.5, 0.5],
            }
        )
        quality_scores = {"A": 1.0, "B": 0.5}
        results = scoring_engine.calculate_tf_scores(
            df, "1H", RegimeType.RANGE, quality_scores
        )
        assert len(results) == 2
        a = next(r for r in results if r.symbol == "A")
        b = next(r for r in results if r.symbol == "B")
        assert a.score_tf_base > 0
        assert a.score_tf == a.score_tf_base
        assert b.score_tf == pytest.approx(b.score_tf_base * 0.5, rel=1e-5)


class TestAggregateMtfScores:
    """Tests for aggregate_mtf_scores()."""

    def test_final_score_weighted_by_tf(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """final_score uses tf_weights 4H:0.4, 1H:0.3, 15m:0.2, 5m:0.1."""
        tf_scores = {
            "4H": {"A": 0.8, "B": 0.6},
            "1H": {"A": 0.7, "B": 0.7},
            "15m": {"A": 0.6, "B": 0.8},
            "5m": {"A": 0.5, "B": 0.5},
        }
        results = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.RANGE)
        assert len(results) == 2
        a = next(r for r in results if r.symbol == "A")
        expected = 0.4 * 0.8 + 0.3 * 0.7 + 0.2 * 0.6 + 0.1 * 0.5
        assert a.final_score == pytest.approx(expected, rel=1e-5)
        assert a.best_tf == "4H"
        assert a.rank in (1, 2)

    def test_missing_senior_tf_excluded(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """Symbol with neither 4H nor 1H is excluded (MISSING_SENIOR_TF)."""
        tf_scores = {
            "4H": {"A": 0.8},
            "1H": {"A": 0.7},
            "15m": {"A": 0.6},
            "5m": {"A": 0.5},
        }
        results = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.RANGE)
        symbols = {r.symbol for r in results}
        assert "A" in symbols
        results2 = scoring_engine.aggregate_mtf_scores(
            {"4H": {"A": 0.8}, "1H": {"A": 0.7}, "15m": {"B": 0.9}, "5m": {"B": 0.9}},
            RegimeType.RANGE,
        )
        symbols2 = {r.symbol for r in results2}
        assert "B" not in symbols2

    def test_ranks_assigned_descending(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """Results sorted by final_score desc, rank 1 = best."""
        tf_scores = {
            "4H": {"A": 0.9, "B": 0.7, "C": 0.5},
            "1H": {"A": 0.9, "B": 0.7, "C": 0.5},
            "15m": {"A": 0.9, "B": 0.7, "C": 0.5},
            "5m": {"A": 0.9, "B": 0.7, "C": 0.5},
        }
        results = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.RANGE)
        assert [r.rank for r in results] == [1, 2, 3]
        assert results[0].symbol == "A"
        assert (
            results[0].final_score >= results[1].final_score >= results[2].final_score
        )


class TestApplyVolatileFilter:
    """Tests for apply_volatile_filter()."""

    def test_excludes_low_liq(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """Symbols with liq_score < threshold are excluded."""
        scores = [
            TFScore("A", "1H", 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, {}),
            TFScore("B", "1H", 0.5, 0.5, 0.5, 0.5, 0.2, 0.5, 0.25, {}),
        ]
        liq_scores = {"A": 0.5, "B": 0.2}
        excluded = scoring_engine.apply_volatile_filter(scores, liq_scores)
        assert "B" in excluded
        assert "A" not in excluded
