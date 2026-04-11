"""
Pair Metrics Calculator for Market Selection

Calculates 5 metrics per (symbol, timeframe):
1. Volatility: median(atr_14 / close)
2. Trend Quality: adx_norm * abs(ema_slope_norm)
3. Noise: std(|returns|) / median(|returns|)
4. Stability: dominance * (1 - switch_rate)
5. Liquidity: median(volume) / (cv(volume) + 1)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

# Small constant to prevent division by zero
EPS = 1e-12


@dataclass
class PairMetrics:
    """Raw metric values for a single (symbol, timeframe)."""

    symbol: str
    timeframe: str

    # Raw values
    vol_raw: float | None
    trend_q_raw: float | None
    noise_raw: float | None
    stability_raw: float | None
    liq_raw: float | None

    # Quality gate passed
    valid_bars: int
    expected_bars: int

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "vol_raw": self.vol_raw,
            "trend_q_raw": self.trend_q_raw,
            "noise_raw": self.noise_raw,
            "stability_raw": self.stability_raw,
            "liq_raw": self.liq_raw,
            "valid_bars": self.valid_bars,
            "expected_bars": self.expected_bars,
        }


class PairMetricsCalculator:
    """
    Calculates 5 trading metrics per (symbol, timeframe).

    Designed to work with data from indicators and swap_ohlcv_p tables.
    """

    def __init__(
        self,
        ema_slope_source: str = "ema_21",
        slope_lookback_bars: int = 50,
        adx_trend_threshold: int = 25,
        adx_range_threshold: int = 18,
    ):
        """
        Initialize calculator.

        Args:
            ema_slope_source: EMA column to use for trend slope (ema_21 or ema_55)
            slope_lookback_bars: Number of bars for slope regression
            adx_trend_threshold: ADX threshold for trend classification (default: 25)
            adx_range_threshold: ADX threshold for range classification (default: 18)
        """
        self.ema_slope_source = ema_slope_source
        self.slope_lookback_bars = slope_lookback_bars
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_range_threshold = adx_range_threshold

    def calculate_all(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        expected_bars: int,
    ) -> PairMetrics:
        """
        Calculate all 5 metrics from joined OHLCV + indicators DataFrame.

        Required columns:
            - close, volume (from swap_ohlcv_p)
            - atr_14, adx_14, ema_21/ema_55 (from indicators)

        Args:
            df: DataFrame with OHLCV and indicator data, sorted by timestamp
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            expected_bars: Expected number of bars (for reporting)

        Returns:
            PairMetrics with all 5 raw values
        """
        valid_bars = len(df)

        # (1) Volatility
        vol_raw = self._calc_volatility(df)

        # (2) Trend Quality
        trend_q_raw = self._calc_trend_quality(df)

        # (3) Noise
        noise_raw = self._calc_noise(df)

        # (4) Stability
        stability_raw = self._calc_stability(df)

        # (5) Liquidity
        liq_raw = self._calc_liquidity(df)

        return PairMetrics(
            symbol=symbol,
            timeframe=timeframe,
            vol_raw=vol_raw,
            trend_q_raw=trend_q_raw,
            noise_raw=noise_raw,
            stability_raw=stability_raw,
            liq_raw=liq_raw,
            valid_bars=valid_bars,
            expected_bars=expected_bars,
        )

    def _calc_volatility(self, df: pd.DataFrame) -> float | None:
        """
        Calculate volatility metric.

        Formula: vol = median(atr_14 / close)
        Higher values mean more volatile.
        """
        if "atr_14" not in df.columns or "close" not in df.columns:
            return None

        atr = df["atr_14"].dropna()
        close = df["close"].loc[atr.index]

        if len(atr) == 0 or (close == 0).any():
            return None

        ratio = atr / (close + EPS)
        return float(ratio.median())

    def _calc_trend_quality(self, df: pd.DataFrame) -> float | None:
        """
        Calculate trend quality metric.

        Formula: trend_q = adx_norm * abs(ema_slope_norm)
        Where:
            adx_norm = median(adx_14) / 100
            ema_slope_norm = slope(EMA) / median(close)

        Higher values mean stronger, cleaner trend.
        """
        if "adx_14" not in df.columns:
            return None

        ema_col = self.ema_slope_source
        if ema_col not in df.columns:
            return None

        adx = df["adx_14"].dropna()
        if len(adx) == 0:
            return None

        adx_norm = float(adx.median()) / 100.0

        # Calculate EMA slope via linear regression on last N bars
        ema_slope = self._calc_ema_slope(df, ema_col)
        if ema_slope is None:
            return adx_norm * 0.5  # fallback: just use ADX

        close_median = df["close"].median()
        if close_median <= 0:
            return None

        ema_slope_norm = abs(ema_slope) / (close_median + EPS)

        return adx_norm * ema_slope_norm

    def _calc_ema_slope(self, df: pd.DataFrame, ema_col: str) -> float | None:
        """Calculate EMA slope using linear regression."""
        ema = df[ema_col].dropna()

        if len(ema) < self.slope_lookback_bars:
            # Use what we have if less than lookback
            if len(ema) < 10:
                return None
        else:
            ema = ema.tail(self.slope_lookback_bars)

        # Simple linear regression: slope = Cov(x,y) / Var(x)
        x = np.arange(len(ema))
        y = ema.values

        x_mean = x.mean()
        y_mean = y.mean()

        numerator = ((x - x_mean) * (y - y_mean)).sum()
        denominator = ((x - x_mean) ** 2).sum()

        if denominator < EPS:
            return 0.0

        slope = numerator / denominator
        return float(slope)

    def _calc_noise(self, df: pd.DataFrame) -> float | None:
        """
        Calculate noise metric.

        Formula: noise = std(|r|) / (median(|r|) + eps)
        Where: r = log(close_t / close_{t-1})

        Higher values mean more erratic/noisy price action.
        """
        if "close" not in df.columns or len(df) < 2:
            return None

        close = df["close"].dropna()
        if len(close) < 2:
            return None

        # Log returns
        returns = np.log(close / close.shift(1)).dropna()
        if len(returns) == 0:
            return None

        abs_returns = np.abs(returns)

        std_r = float(abs_returns.std())
        median_r = float(abs_returns.median())

        return std_r / (median_r + EPS)

    def _calc_stability(self, df: pd.DataFrame) -> float | None:
        """
        Calculate stability metric using local regime classification.

        Process:
        1. Classify each bar's local regime (TREND, RANGE, VOLATILE, NEUTRAL)
        2. Calculate switch_rate_7d = regime switches / total bars
        3. Calculate dominance_7d = max share of any regime
        4. stability = clamp(dominance_7d * (1 - switch_rate_7d), 0, 1)

        Local regime rules:
        - TREND: adx_14 >= 25 AND abs(ema_slope) is high
        - RANGE: adx_14 < 18 AND atr/close is low
        - VOLATILE: atr/close > 80th percentile
        - NEUTRAL: otherwise
        """
        required_cols = ["adx_14", "atr_14", "close", self.ema_slope_source]
        if not all(col in df.columns for col in required_cols):
            return None

        # Filter valid rows
        valid_df = df[required_cols].dropna()
        if len(valid_df) < 20:
            return None

        # Calculate ATR/close ratio
        atr_close_ratio = valid_df["atr_14"] / (valid_df["close"] + EPS)

        # Calculate 80th percentile for volatile threshold
        atr_p80 = float(atr_close_ratio.quantile(0.8))

        # Calculate EMA slope for each bar (rolling window)
        ema_col = self.ema_slope_source
        ema_values = valid_df[ema_col].values

        regimes = []
        for i in range(len(valid_df)):
            regimes.append(
                self._classify_bar_regime(
                    valid_df=valid_df,
                    ema_values=ema_values,
                    atr_close_ratio=atr_close_ratio,
                    atr_p80=atr_p80,
                    index=i,
                )
            )

        if len(regimes) < 7:
            return None

        # Calculate switch_rate: how often regime changes
        switches = sum(1 for i in range(1, len(regimes)) if regimes[i] != regimes[i - 1])
        switch_rate = switches / len(regimes)

        # Calculate dominance: share of most common regime
        regime_counts = Counter(regimes)
        max_count = max(regime_counts.values())
        dominance = max_count / len(regimes)

        # Final stability score
        stability = dominance * (1.0 - switch_rate)
        stability = max(0.0, min(1.0, stability))

        return float(stability)

    def _classify_bar_regime(
        self,
        valid_df: pd.DataFrame,
        ema_values: np.ndarray,
        atr_close_ratio: pd.Series,
        atr_p80: float,
        index: int,
    ) -> str:
        """Classify a single bar into a local regime for stability scoring."""
        start_idx = max(0, index - self.slope_lookback_bars + 1)
        window_ema = ema_values[start_idx : index + 1]

        if len(window_ema) < 10:
            return "NEUTRAL"

        ema_slope_norm = self._calc_window_ema_slope_norm(valid_df, window_ema, start_idx, index)
        adx = valid_df["adx_14"].iloc[index]
        atr_close = atr_close_ratio.iloc[index]

        if atr_close > atr_p80:
            return "VOLATILE"
        if adx >= self.adx_trend_threshold and ema_slope_norm > 0.001:
            return "TREND"
        if adx < self.adx_range_threshold and atr_close < atr_p80 * 0.5:
            return "RANGE"
        return "NEUTRAL"

    def _calc_window_ema_slope_norm(
        self,
        valid_df: pd.DataFrame,
        window_ema: np.ndarray,
        start_idx: int,
        end_idx: int,
    ) -> float:
        """Compute normalized EMA slope for a rolling stability window."""
        x = np.arange(len(window_ema))
        x_mean = x.mean()
        y_mean = window_ema.mean()

        numerator = ((x - x_mean) * (window_ema - y_mean)).sum()
        denominator = ((x - x_mean) ** 2).sum()
        ema_slope = 0.0 if denominator < EPS else numerator / denominator

        close_median = valid_df["close"].iloc[start_idx : end_idx + 1].median()
        return abs(ema_slope) / (close_median + EPS)

    def _calc_liquidity(self, df: pd.DataFrame) -> float | None:
        """
        Calculate liquidity metric.

        Formula: liq = median(volume) / (cv(volume) + 1)
        Where: cv = std(volume) / (mean(volume) + eps)

        Higher median and lower CV = better liquidity.
        """
        if "volume" not in df.columns:
            return None

        volume = df["volume"].dropna()
        if len(volume) == 0:
            return None

        vol_median = float(volume.median())
        vol_mean = float(volume.mean())
        vol_std = float(volume.std())

        if vol_mean < EPS:
            return 0.0

        cv = vol_std / (vol_mean + EPS)
        return vol_median / (cv + 1.0)

