"""
Market Selection Configuration

Single source of truth for all parameters.
config_hash ensures reproducibility across runs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field


class RegimeConfig(BaseModel):
    """Global market regime detection configuration."""

    # Basket selection
    basket_k: int = Field(
        default=20, ge=5, le=50, description="Top-K symbols for basket"
    )
    basket_volume_tf: Literal["1H", "4H"] = Field(default="4H")
    basket_volume_window_days: int = Field(default=30, ge=7, le=90)

    # TF weights for regime aggregation
    tf_weights: dict[str, float] = Field(
        default={"1D": 0.5, "4H": 0.3, "1H": 0.2},
        description="Weights for multi-TF regime aggregation",
    )

    # Lag thresholds for regime TF (in minutes)
    # If lag exceeds threshold, use last valid regime from history
    regime_lag_max_minutes: dict[str, int] = Field(
        default={
            "1D": 1440,  # 24 hours
            "4H": 720,  # 12 hours
            "1H": 180,  # 3 hours
        },
        description="Max lag in minutes before using stale regime",
    )

    # Classification thresholds
    adx_trend_threshold: int = Field(default=25, ge=15, le=40)
    adx_range_threshold: int = Field(default=18, ge=10, le=25)
    atr_volatile_percentile: int = Field(default=80, ge=60, le=95)

    # EMA slope calculation
    ema_slope_source: Literal["ema_21", "ema_55"] = Field(default="ema_21")
    slope_lookback_bars: int = Field(default=50, ge=20, le=100)

    # Direction score thresholds
    trend_up_threshold: float = Field(default=0.35, ge=0.2, le=0.6)
    trend_down_threshold: float = Field(default=-0.35, ge=-0.6, le=-0.2)


class QualityConfig(BaseModel):
    """Data quality gate configuration."""

    # Per-TF thresholds: fill_min, gap_max, lag_max_minutes
    thresholds: dict[str, dict[str, float]] = Field(
        default={
            "5m": {"fill_min": 0.97, "gap_max": 0.015, "lag_max_min": 15},
            "15m": {"fill_min": 0.98, "gap_max": 0.010, "lag_max_min": 45},
            "1H": {"fill_min": 0.99, "gap_max": 0.005, "lag_max_min": 180},
            "4H": {"fill_min": 0.99, "gap_max": 0.005, "lag_max_min": 720},
        }
    )

    # Warmup requirements
    warmup_min_bars: int = Field(
        default=280,
        ge=100,
        description="min(200, 2 * adx_period * 10) with adx_period=14",
    )

    # Gap detection
    gap_threshold_multiplier: float = Field(
        default=1.5,
        ge=1.1,
        le=3.0,
        description="Gap if delta_t > multiplier * tf_ms",
    )


class ScoringConfig(BaseModel):
    """Scoring engine configuration."""

    # Base weights for 5 metrics (must sum to 1.0)
    base_weights: dict[str, float] = Field(
        default={
            "vol": 0.25,
            "trend_q": 0.30,
            "noise": 0.20,
            "stability": 0.15,
            "liq": 0.10,
        }
    )

    # Regime-based weight adjustments (deltas applied to base_weights)
    regime_deltas: dict[str, dict[str, float]] = Field(
        default={
            "TREND_UP": {
                "trend_q": 0.05,
                "noise": -0.03,
                "stability": -0.02,
                "vol": 0.00,
                "liq": 0.00,
            },
            "TREND_DOWN": {
                "trend_q": 0.05,
                "noise": -0.03,
                "stability": -0.02,
                "vol": 0.00,
                "liq": 0.00,
            },
            "RANGE": {
                "noise": 0.05,
                "stability": 0.03,
                "trend_q": -0.05,
                "vol": -0.03,
                "liq": 0.00,
            },
            "VOLATILE": {
                "liq": 0.05,
                "vol": 0.02,
                "noise": -0.02,
                "trend_q": -0.03,
                "stability": -0.02,
            },
        }
    )

    # MTF aggregation weights
    tf_weights: dict[str, float] = Field(
        default={
            "4H": 0.40,
            "1H": 0.30,
            "15m": 0.20,
            "5m": 0.10,
        }
    )

    # Penalties for missing senior TFs
    missing_senior_penalty: dict[str, float] = Field(
        default={
            "4H": 0.92,  # multiply final_score by this if 4H missing
            "1H": 0.90,  # multiply final_score by this if 1H missing
        }
    )
    missing_junior_penalty: float = Field(
        default=0.03,
        description="Subtract from final_score if 5m or 15m missing",
    )

    # VOLATILE regime special filter
    volatile_min_liq_score: float = Field(
        default=0.30,
        ge=0.1,
        le=0.5,
        description="Min liq_score to be eligible in VOLATILE regime",
    )

    # Normalization
    winsorize_percentiles: tuple[float, float] = Field(default=(1.0, 99.0))
    winsorize_small_universe: tuple[float, float] = Field(default=(5.0, 95.0))
    small_universe_threshold: int = Field(default=50)
    fallback_zscore_threshold: int = Field(default=20)


class UniverseConfig(BaseModel):
    """Universe manager configuration."""

    # Selection size
    top_n: int = Field(default=30, ge=10, le=100)
    buffer: int = Field(default=10, ge=5, le=30)

    # Stability thresholds (for hysteresis)
    score_std_7d_max: float = Field(default=0.12, ge=0.05, le=0.25)
    score_std_30d_max: float = Field(default=0.18, ge=0.10, le=0.30)
    min_history_days: int = Field(default=7, ge=3, le=14)

    # Fallback thresholds
    min_universe_hard: int = Field(default=5, ge=1, description="Below this: hard fail")
    min_universe_soft: int = Field(
        default=10, ge=5, description="Below this: use fallback"
    )

    # Systemic outage detection
    systemic_senior_outage_threshold: float = Field(
        default=0.30,
        ge=0.10,
        le=0.50,
        description="If > 30% pairs missing 1H/4H, trigger fallback",
    )

    # Retention
    scores_retention_days: int = Field(default=180, ge=30)
    universe_retention_days: int = Field(default=90, ge=30)

    # White/Black lists
    whitelist: list[str] = Field(
        default_factory=list,
        description="Symbols to force-include (if eligible and have 1H/4H)",
    )
    blacklist: list[str] = Field(
        default_factory=list,
        description="Symbols to force-exclude from universe",
    )


class MarketSelectionConfig(BaseModel):
    """Main configuration for Market Selection module."""

    # Timeframes
    selection_tfs: list[str] = Field(
        default=["5m", "15m", "1H", "4H"],
        description="TFs participating in pair selection",
    )
    regime_tfs: list[str] = Field(
        default=["1D", "4H", "1H"],
        description="TFs for global regime detection",
    )

    # Lookback windows per TF (for pair metrics)
    windows_days: dict[str, int] = Field(
        default={
            "5m": 30,
            "15m": 45,
            "1H": 90,
            "4H": 120,
        }
    )

    # Regime windows (for global regime)
    regime_windows_days: dict[str, int] = Field(
        default={
            "1D": 180,
            "4H": 120,
            "1H": 60,
        }
    )

    # Sub-configs
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    universe: UniverseConfig = Field(default_factory=UniverseConfig)

    # Feature source validation
    short_feature_set: list[str] = Field(
        default=[
            "ema_21",
            "ema_55",
            "supertrend_direction",
            "adx_14",
            "chop",
            "dc_upper",
            "dc_lower",
            "rsi_14",
            "macd",
            "macd_signal",
            "macd_histogram",
            "ppo",
            "tsi",
            "stoch_k",
            "stoch_d",
            "atr_14",
            "natr_14",
            "kc_upper",
            "kc_lower",
            "obv",
            "cmf",
            "mfi",
            "ha_open",
            "ha_close",
        ],
        description="Expected features from features_calc_short",
    )
    max_missing_features: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Max missing features before SHORT_FEATURE_MISMATCH",
    )

    def config_hash(self) -> str:
        """
        Generate deterministic hash of configuration.

        Used for:
        - Reproducibility: same config → same results
        - Versioning: detect config changes
        - Audit: link results to exact config used
        """
        # Canonical JSON with sorted keys
        canonical = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def get_tf_window_ms(self, tf: str) -> int:
        """Get lookback window in milliseconds for a timeframe."""
        days = self.windows_days.get(tf, 30)
        return days * 24 * 60 * 60 * 1000

    def get_tf_bar_ms(self, tf: str) -> int:
        """Get bar duration in milliseconds for a timeframe."""
        tf_to_ms = {
            "1m": 60_000,
            "5m": 5 * 60_000,
            "15m": 15 * 60_000,
            "30m": 30 * 60_000,
            "1H": 60 * 60_000,
            "4H": 4 * 60 * 60_000,
            "12H": 12 * 60 * 60_000,
            "1D": 24 * 60 * 60_000,
            "1W": 7 * 24 * 60 * 60_000,
            "1M": 30 * 24 * 60 * 60_000,
        }
        return tf_to_ms.get(tf, 60_000)

    def get_quality_thresholds(self, tf: str) -> dict[str, float]:
        """Get quality gate thresholds for a timeframe."""
        return self.quality.thresholds.get(
            tf,
            {"fill_min": 0.95, "gap_max": 0.02, "lag_max_min": 60},
        )
