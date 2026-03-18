"""
Global Market Regime Detection for Market Selection

Determines overall market state using basket of top-K symbols by volume:
- TREND_UP: Strong upward trend (ADX high, positive slope)
- TREND_DOWN: Strong downward trend (ADX high, negative slope)
- RANGE: Low volatility sideways (ADX low, ATR/close low)
- VOLATILE: High volatility without clear direction
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

from .config import RegimeClassifierConfig

EPS = 1e-12


class RegimeType(str, Enum):
    """Market regime classification."""

    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    VOLATILE = "VOLATILE"


@dataclass
class TFRegime:
    """Regime for a single timeframe."""

    timeframe: str
    regime: RegimeType
    strength: float  # 0-1
    adx_median: float
    atr_close_ratio: float
    ema_slope: float


@dataclass
class GlobalRegime:
    """Aggregated global market regime across timeframes."""

    regime: RegimeType
    strength: float  # 0-1
    confidence: float  # 0-1
    stale: bool = False

    # Per-TF breakdown
    tf_regimes: dict[str, TFRegime] = field(default_factory=dict)

    # Basket info
    basket_symbols: list[str] = field(default_factory=list)
    basket_size: int = 0

    # Aggregated metrics
    basket_adx_median: float = 0.0
    basket_atr_close_median: float = 0.0
    basket_ema_slope_median: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "global_regime": self.regime.value,
            "global_strength": self.strength,
            "regime_confidence": self.confidence,
            "is_stale": self.stale,
            "basket_size": self.basket_size,
            "basket_symbols": self.basket_symbols,
            "basket_adx_median": self.basket_adx_median,
            "basket_atr_close_median": self.basket_atr_close_median,
            "basket_ema_slope_median": self.basket_ema_slope_median,
            "regime_1d": self.tf_regimes.get("1D", TFRegime("1D", RegimeType.RANGE, 0.5, 0, 0, 0)).regime.value,
            "regime_1d_strength": self.tf_regimes.get("1D", TFRegime("1D", RegimeType.RANGE, 0.5, 0, 0, 0)).strength,
            "regime_4h": self.tf_regimes.get("4H", TFRegime("4H", RegimeType.RANGE, 0.5, 0, 0, 0)).regime.value,
            "regime_4h_strength": self.tf_regimes.get("4H", TFRegime("4H", RegimeType.RANGE, 0.5, 0, 0, 0)).strength,
            "regime_1h": self.tf_regimes.get("1H", TFRegime("1H", RegimeType.RANGE, 0.5, 0, 0, 0)).regime.value,
            "regime_1h_strength": self.tf_regimes.get("1H", TFRegime("1H", RegimeType.RANGE, 0.5, 0, 0, 0)).strength,
        }


class RegimeClassifier:
    """
    Classifies global market regime using basket of top-K symbols.

    Process:
    1. Select top-K symbols by median volume
    2. For each symbol, get ADX, ATR/close, EMA slope
    3. Aggregate across basket using weighted median
    4. Classify per-TF regime
    5. Aggregate across TFs with weights
    """

    def __init__(self, config: RegimeClassifierConfig):
        self.config = config

    def select_basket(
        self,
        volume_data: pd.DataFrame,
    ) -> list[str]:
        """
        Select top-K symbols by median volume.

        Args:
            volume_data: DataFrame with columns: symbol, volume_median
                        Sorted by volume_median descending

        Returns:
            List of top-K symbols
        """
        k = self.config.basket_k

        if len(volume_data) <= k:
            return volume_data["symbol"].tolist()

        return volume_data.head(k)["symbol"].tolist()

    def classify_single_tf(
        self,
        timeframe: str,
        adx_median: float,
        atr_close_ratio: float,
        ema_slope: float,
        atr_p80: float,
    ) -> TFRegime:
        """
        Classify regime for a single timeframe.

        Logic:
        1. VOLATILE: ATR/close > 80th percentile
        2. TREND_UP/DOWN: ADX >= 25 and |slope| high
        3. RANGE: ADX < 18
        """
        regime: RegimeType
        strength: float

        # VOLATILE check first (high priority)
        if atr_p80 > 0 and atr_close_ratio > atr_p80:
            regime = RegimeType.VOLATILE
            strength = min(1.0, atr_close_ratio / atr_p80) if atr_p80 > 0 else 0.8

        # TREND check
        elif adx_median >= self.config.adx_trend_threshold:
            if ema_slope > 0:
                regime = RegimeType.TREND_UP
            else:
                regime = RegimeType.TREND_DOWN
            strength = min(1.0, adx_median / 100.0)

        # RANGE check
        elif adx_median < self.config.adx_range_threshold:
            regime = RegimeType.RANGE
            strength = 1.0 - (adx_median / self.config.adx_range_threshold)

        # Default to RANGE with medium strength
        else:
            regime = RegimeType.RANGE
            strength = 0.5

        return TFRegime(
            timeframe=timeframe,
            regime=regime,
            strength=strength,
            adx_median=adx_median,
            atr_close_ratio=atr_close_ratio,
            ema_slope=ema_slope,
        )

    def aggregate_basket_metrics(
        self,
        basket_data: pd.DataFrame,
    ) -> dict[str, float]:
        """
        Aggregate metrics across basket using weighted median.

        Args:
            basket_data: DataFrame with columns:
                - symbol, volume_median (for weights)
                - adx_median, atr_close_ratio, ema_slope

        Returns:
            Dict with aggregated: adx, atr_close, ema_slope
        """
        if len(basket_data) == 0:
            return {"adx": 20.0, "atr_close": 0.01, "ema_slope": 0.0}

        # Weights: log(volume) to reduce outlier impact
        volumes = basket_data["volume_median"].values
        weights = np.log1p(volumes)
        weights = weights / (weights.sum() + EPS)

        # Weighted median approximation using weighted average
        # (True weighted median is complex; this is a good approximation)
        adx = float((basket_data["adx_median"].values * weights).sum())
        atr_close = float((basket_data["atr_close_ratio"].values * weights).sum())
        ema_slope = float((basket_data["ema_slope"].values * weights).sum())

        return {
            "adx": adx,
            "atr_close": atr_close,
            "ema_slope": ema_slope,
        }

    def aggregate_across_tfs(
        self,
        tf_regimes: dict[str, TFRegime],
    ) -> GlobalRegime:
        """
        Aggregate per-TF regimes into global regime.

        Weights: 1D=0.5, 4H=0.3, 1H=0.2

        Logic:
        1. If any TF is VOLATILE with high ATR → VOLATILE
        2. Calculate weighted direction score
        3. Threshold direction_score for TREND_UP/DOWN/RANGE
        """
        weights = self.config.tf_weights

        direction_score = 0.0
        volatile_flag = False
        total_strength = 0.0
        total_weight = 0.0

        for tf, regime in tf_regimes.items():
            w = weights.get(tf, 0.0)
            total_weight += w
            total_strength += w * regime.strength

            if regime.regime == RegimeType.VOLATILE:
                volatile_flag = True
            elif regime.regime == RegimeType.TREND_UP:
                direction_score += w * 1.0
            elif regime.regime == RegimeType.TREND_DOWN:
                direction_score -= w * 1.0
            # RANGE contributes 0

        # Normalize
        if total_weight > 0:
            direction_score /= total_weight
            avg_strength = total_strength / total_weight
        else:
            avg_strength = 0.5

        # Determine final regime
        if volatile_flag:
            final_regime = RegimeType.VOLATILE
            confidence = 0.7
        elif direction_score >= self.config.trend_up_threshold:
            final_regime = RegimeType.TREND_UP
            confidence = min(1.0, abs(direction_score) / 0.5)
        elif direction_score <= self.config.trend_down_threshold:
            final_regime = RegimeType.TREND_DOWN
            confidence = min(1.0, abs(direction_score) / 0.5)
        else:
            final_regime = RegimeType.RANGE
            confidence = 1.0 - abs(direction_score) / 0.35

        return GlobalRegime(
            regime=final_regime,
            strength=avg_strength,
            confidence=max(0.0, min(1.0, confidence)),
            tf_regimes=tf_regimes,
        )

    def compute_global_regime(
        self,
        basket_symbols: list[str],
        tf_data: dict[str, pd.DataFrame],
        atr_percentiles: dict[str, float],
    ) -> GlobalRegime:
        """
        Compute global regime from basket data across TFs.

        Args:
            basket_symbols: List of symbols in basket
            tf_data: Dict[tf -> DataFrame with basket metrics per symbol]
                    Each DF has: symbol, adx_median, atr_close_ratio, ema_slope, volume_median
            atr_percentiles: Dict[tf -> 80th percentile of ATR/close across all symbols]

        Returns:
            GlobalRegime with full breakdown
        """
        tf_regimes: dict[str, TFRegime] = {}

        for tf in self.config.regime_tfs:
            if tf not in tf_data or tf_data[tf].empty:
                # Missing TF - default to neutral RANGE
                tf_regimes[tf] = TFRegime(
                    timeframe=tf,
                    regime=RegimeType.RANGE,
                    strength=0.5,
                    adx_median=20.0,
                    atr_close_ratio=0.01,
                    ema_slope=0.0,
                )
                continue

            df = tf_data[tf]

            # Filter to basket symbols only
            basket_df = df[df["symbol"].isin(basket_symbols)]
            if basket_df.empty:
                basket_df = df.head(10)  # fallback

            # Aggregate metrics
            agg = self.aggregate_basket_metrics(basket_df)
            atr_p80 = atr_percentiles.get(tf, agg["atr_close"] * 2)

            # Classify
            tf_regime = self.classify_single_tf(
                timeframe=tf,
                adx_median=agg["adx"],
                atr_close_ratio=agg["atr_close"],
                ema_slope=agg["ema_slope"],
                atr_p80=atr_p80,
            )
            tf_regimes[tf] = tf_regime

        # Aggregate across TFs
        global_regime = self.aggregate_across_tfs(tf_regimes)

        # Add basket info
        global_regime.basket_symbols = basket_symbols
        global_regime.basket_size = len(basket_symbols)

        # Add aggregated metrics from primary TF (4H)
        if "4H" in tf_data and not tf_data["4H"].empty:
            basket_df = tf_data["4H"][tf_data["4H"]["symbol"].isin(basket_symbols)]
            if not basket_df.empty:
                global_regime.basket_adx_median = float(basket_df["adx_median"].median())
                global_regime.basket_atr_close_median = float(basket_df["atr_close_ratio"].median())
                global_regime.basket_ema_slope_median = float(basket_df["ema_slope"].median())

        return global_regime
