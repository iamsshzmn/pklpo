"""
Scoring Engine for Market Selection

Handles:
1. Percentile normalization of raw metrics
2. Regime-based weight adjustment
3. Per-TF score calculation
4. Multi-TF aggregation to final_score
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

    from src.market_selection.config import MarketSelectionConfig

from .quality_gate import ReasonFlag
from .regime import RegimeType

logger = logging.getLogger(__name__)

EPS = 1e-12


@dataclass
class TFScore:
    """Score for a single (symbol, timeframe)."""

    symbol: str
    timeframe: str

    # Normalized scores (0-1)
    vol_score: float
    trend_q_score: float
    noise_score: float
    stability_score: float
    liq_score: float

    # Aggregated
    score_tf_base: float  # weighted sum of metric scores
    score_tf: float  # score_tf_base * quality_score

    # Applied weights (after regime adjustment)
    weights_used: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "vol_score": self.vol_score,
            "trend_q_score": self.trend_q_score,
            "noise_score": self.noise_score,
            "stability_score": self.stability_score,
            "liq_score": self.liq_score,
            "score_tf_base": self.score_tf_base,
            "score_tf": self.score_tf,
        }


@dataclass
class FinalScore:
    """Final aggregated score for a symbol across all TFs."""

    symbol: str
    final_score: float
    rank: int = 0

    # Per-TF scores
    score_4h: float | None = None
    score_1h: float | None = None
    score_15m: float | None = None
    score_5m: float | None = None

    # Best/worst TF
    best_tf: str | None = None
    worst_tf: str | None = None

    # Penalties applied
    penalty_applied: float = 0.0
    reason_flags: list[ReasonFlag] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "symbol": self.symbol,
            "final_score": self.final_score,
            "rank": self.rank,
            "score_4h": self.score_4h,
            "score_1h": self.score_1h,
            "score_15m": self.score_15m,
            "score_5m": self.score_5m,
            "best_tf": self.best_tf,
            "worst_tf": self.worst_tf,
            "penalty_applied": self.penalty_applied,
            "reason_flags": [f.value for f in self.reason_flags],
        }


class ScoringEngine:
    """
    Calculates normalized scores for market selection.

    Process:
    1. Winsorize raw metrics to handle outliers
    2. Percentile rank normalization within each TF
    3. Apply regime-based weight adjustments
    4. Calculate weighted score per TF
    5. Aggregate across TFs for final score
    """

    def __init__(self, config: MarketSelectionConfig):
        self.config = config
        self.scoring_config = config.scoring

    def normalize_metrics(
        self,
        metrics_df: "pd.DataFrame",
        timeframe: str,
    ) -> "pd.DataFrame":
        """
        Normalize raw metrics to 0-1 using percentile rank.

        Args:
            metrics_df: DataFrame with columns:
                symbol, vol_raw, trend_q_raw, noise_raw, stability_raw, liq_raw
            timeframe: For logging purposes

        Returns:
            DataFrame with additional columns:
                vol_score, trend_q_score, noise_score, stability_score, liq_score
        """
        df = metrics_df.copy()
        n_eligible = len(df)

        if n_eligible == 0:
            return df

        # Determine winsorize percentiles
        if n_eligible < self.scoring_config.small_universe_threshold:
            p_low, p_high = self.scoring_config.winsorize_small_universe
        else:
            p_low, p_high = self.scoring_config.winsorize_percentiles

        # Metric columns and their scoring direction
        # For noise: lower is better, so we invert
        metrics = {
            "vol_raw": ("vol_score", False),  # higher vol = higher score
            "trend_q_raw": ("trend_q_score", False),  # higher trend_q = higher score
            "noise_raw": ("noise_score", True),  # lower noise = higher score (invert)
            "stability_raw": ("stability_score", False),  # higher stability = higher score
            "liq_raw": ("liq_score", False),  # higher liq = higher score
        }

        for raw_col, (score_col, invert) in metrics.items():
            if raw_col not in df.columns:
                df[score_col] = 0.0
                continue

            values = df[raw_col].copy()

            # Handle NaN
            valid_mask = values.notna()
            if valid_mask.sum() == 0:
                df[score_col] = 0.0
                continue

            # Winsorize
            valid_values = values[valid_mask]
            low_val = np.percentile(valid_values, p_low)
            high_val = np.percentile(valid_values, p_high)
            values = values.clip(lower=low_val, upper=high_val)

            # Percentile rank normalization
            if n_eligible < self.scoring_config.fallback_zscore_threshold:
                # Fallback to z-score → sigmoid for very small universes
                scores = self._zscore_sigmoid_normalize(values)
            else:
                # Standard percentile rank
                scores = values.rank(pct=True, na_option="bottom")

            # Invert if lower is better
            if invert:
                scores = 1.0 - scores

            df[score_col] = scores.fillna(0.0)

        logger.debug(f"Normalized {n_eligible} symbols for {timeframe}")
        return df

    def _zscore_sigmoid_normalize(self, values: "pd.Series") -> "pd.Series":
        """
        Normalize using z-score → sigmoid.

        Used when universe is too small for percentile rank.
        """
        valid = values.dropna()
        if len(valid) == 0:
            return values.fillna(0.5)

        mean = valid.mean()
        std = valid.std()

        if std < EPS:
            return values.apply(lambda x: 0.5 if np.isnan(x) else 0.5)

        z = (values - mean) / (std + EPS)
        sigmoid = 1.0 / (1.0 + np.exp(-z))
        return sigmoid

    def get_adjusted_weights(
        self,
        regime: RegimeType,
    ) -> dict[str, float]:
        """
        Get metric weights adjusted for current regime.

        Returns normalized weights (sum = 1.0)
        """
        base = self.scoring_config.base_weights.copy()
        deltas = self.scoring_config.regime_deltas.get(regime.value, {})

        # Apply deltas
        adjusted = {}
        for metric, weight in base.items():
            delta = deltas.get(metric, 0.0)
            adjusted[metric] = max(0.0, weight + delta)

        # Normalize to sum = 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}
        else:
            adjusted = base

        return adjusted

    def calculate_tf_scores(
        self,
        normalized_df: "pd.DataFrame",
        timeframe: str,
        regime: RegimeType,
        quality_scores: dict[str, float],
    ) -> list[TFScore]:
        """
        Calculate weighted scores for each symbol in a timeframe.

        Args:
            normalized_df: DataFrame with normalized metric scores
            timeframe: Candle timeframe
            regime: Current global regime
            quality_scores: Dict[symbol -> quality_score from gate]

        Returns:
            List of TFScore objects
        """
        weights = self.get_adjusted_weights(regime)
        results = []

        for _, row in normalized_df.iterrows():
            symbol = row["symbol"]

            # Get individual scores
            vol_score = float(row.get("vol_score", 0.0))
            trend_q_score = float(row.get("trend_q_score", 0.0))
            noise_score = float(row.get("noise_score", 0.0))
            stability_score = float(row.get("stability_score", 0.0))
            liq_score = float(row.get("liq_score", 0.0))

            # Weighted sum
            score_tf_base = (
                weights["vol"] * vol_score
                + weights["trend_q"] * trend_q_score
                + weights["noise"] * noise_score
                + weights["stability"] * stability_score
                + weights["liq"] * liq_score
            )

            # Apply quality score
            quality = quality_scores.get(symbol, 1.0)
            score_tf = score_tf_base * quality

            results.append(
                TFScore(
                    symbol=symbol,
                    timeframe=timeframe,
                    vol_score=vol_score,
                    trend_q_score=trend_q_score,
                    noise_score=noise_score,
                    stability_score=stability_score,
                    liq_score=liq_score,
                    score_tf_base=score_tf_base,
                    score_tf=score_tf,
                    weights_used=weights,
                )
            )

        return results

    def aggregate_mtf_scores(
        self,
        tf_scores: dict[str, dict[str, float]],
        regime: RegimeType,
    ) -> list[FinalScore]:
        """
        Aggregate per-TF scores into final scores.

        Args:
            tf_scores: Dict[tf -> Dict[symbol -> score_tf]]
            regime: For VOLATILE regime special filter

        Returns:
            List of FinalScore objects, sorted by score descending
        """
        tf_weights = self.scoring_config.tf_weights
        missing_penalty = self.scoring_config.missing_senior_penalty
        junior_penalty = self.scoring_config.missing_junior_penalty

        # Collect all symbols
        all_symbols = set()
        for scores in tf_scores.values():
            all_symbols.update(scores.keys())

        results = []

        for symbol in all_symbols:
            score_4h = tf_scores.get("4H", {}).get(symbol)
            score_1h = tf_scores.get("1H", {}).get(symbol)
            score_15m = tf_scores.get("15m", {}).get(symbol)
            score_5m = tf_scores.get("5m", {}).get(symbol)

            reason_flags: list[ReasonFlag] = []
            penalty = 0.0

            # Check for missing senior TFs
            has_4h = score_4h is not None
            has_1h = score_1h is not None

            if not has_4h and not has_1h:
                # Both senior TFs missing - exclude
                reason_flags.append(ReasonFlag.MISSING_SENIOR_TF)
                continue

            # Build weighted score
            weighted_sum = 0.0
            total_weight = 0.0

            if has_4h:
                weighted_sum += tf_weights["4H"] * score_4h
                total_weight += tf_weights["4H"]
            else:
                # 4H missing - apply penalty
                reason_flags.append(ReasonFlag.MISSING_4H_SOFT)
                penalty = 1.0 - missing_penalty["4H"]

            if has_1h:
                weighted_sum += tf_weights["1H"] * score_1h
                total_weight += tf_weights["1H"]
            else:
                # 1H missing - apply penalty
                reason_flags.append(ReasonFlag.MISSING_1H_SOFT)
                if penalty == 0:
                    penalty = 1.0 - missing_penalty["1H"]
                else:
                    penalty = max(penalty, 1.0 - missing_penalty["1H"])

            # Junior TFs
            if score_15m is not None:
                weighted_sum += tf_weights["15m"] * score_15m
                total_weight += tf_weights["15m"]
            else:
                penalty += junior_penalty

            if score_5m is not None:
                weighted_sum += tf_weights["5m"] * score_5m
                total_weight += tf_weights["5m"]
            else:
                penalty += junior_penalty

            # Calculate base score
            if total_weight > 0:
                base_score = weighted_sum / total_weight
            else:
                continue  # No valid TFs

            # Apply penalty multiplier for missing senior TFs
            if ReasonFlag.MISSING_4H_SOFT in reason_flags:
                base_score *= missing_penalty["4H"]
            if ReasonFlag.MISSING_1H_SOFT in reason_flags:
                base_score *= missing_penalty["1H"]

            # Subtract junior penalties
            final_score = max(0.0, base_score - penalty)

            # VOLATILE regime: filter low liquidity
            if regime == RegimeType.VOLATILE:
                liq_threshold = self.scoring_config.volatile_min_liq_score
                # We'd need liq_score here - for now use score_4h as proxy
                # In practice, this check happens before aggregation

            # Find best/worst TF
            tf_score_map = {
                "4H": score_4h,
                "1H": score_1h,
                "15m": score_15m,
                "5m": score_5m,
            }
            valid_tfs = {k: v for k, v in tf_score_map.items() if v is not None}

            best_tf = max(valid_tfs, key=valid_tfs.get) if valid_tfs else None
            worst_tf = min(valid_tfs, key=valid_tfs.get) if valid_tfs else None

            results.append(
                FinalScore(
                    symbol=symbol,
                    final_score=final_score,
                    score_4h=score_4h,
                    score_1h=score_1h,
                    score_15m=score_15m,
                    score_5m=score_5m,
                    best_tf=best_tf,
                    worst_tf=worst_tf,
                    penalty_applied=penalty,
                    reason_flags=reason_flags,
                )
            )

        # Sort by final_score descending and assign ranks
        results.sort(key=lambda x: x.final_score, reverse=True)
        for i, result in enumerate(results):
            result.rank = i + 1

        return results

    def apply_volatile_filter(
        self,
        scores: list[TFScore],
        liq_scores: dict[str, float],
    ) -> list[str]:
        """
        Filter out symbols with low liquidity in VOLATILE regime.

        Returns list of symbols to exclude.
        """
        threshold = self.scoring_config.volatile_min_liq_score
        excluded = []

        for score in scores:
            liq = liq_scores.get(score.symbol, 0.0)
            if liq < threshold:
                excluded.append(score.symbol)

        if excluded:
            logger.info(
                f"VOLATILE filter: excluding {len(excluded)} symbols with liq < {threshold}"
            )

        return excluded
