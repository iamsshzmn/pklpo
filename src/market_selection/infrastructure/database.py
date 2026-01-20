"""
Database Operations for Market Selection

Read operations:
- Fetch OHLCV and indicator data for metrics calculation
- Fetch previous universe for hysteresis
- Fetch score history for stability

Write operations are in persistence.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.market_selection.config import MarketSelectionConfig

logger = logging.getLogger(__name__)


class MarketSelectionDB:
    """
    Database operations for market selection.

    All timestamps are in milliseconds.
    """

    def __init__(self, session: AsyncSession, config: MarketSelectionConfig):
        self.session = session
        self.config = config

    async def get_max_timestamp(self, timeframe: str) -> int | None:
        """
        Get maximum timestamp across OHLCV and indicators for a TF.

        Returns minimum of the two to ensure data consistency.
        """
        query = text("""
            SELECT LEAST(
                (SELECT MAX(timestamp) FROM swap_ohlcv_p WHERE timeframe = :tf),
                (SELECT MAX(timestamp) FROM indicators WHERE timeframe = :tf)
            ) as max_ts
        """)
        result = await self.session.execute(query, {"tf": timeframe})
        row = result.fetchone()
        return row[0] if row and row[0] else None

    async def resolve_ts_eval(self) -> int | None:
        """
        Resolve ts_eval as minimum of max timestamps across selection TFs.

        This ensures no look-ahead bias.
        """
        max_timestamps = []

        for tf in self.config.selection_tfs:
            max_ts = await self.get_max_timestamp(tf)
            if max_ts:
                max_timestamps.append(max_ts)

        if not max_timestamps:
            logger.error("No data found for any selection timeframe")
            return None

        ts_eval = min(max_timestamps)
        logger.info(f"Resolved ts_eval: {ts_eval}")
        return ts_eval

    async def validate_short_features(self) -> tuple[bool, list[str]]:
        """
        Validate that required short features exist in indicators table.

        Returns (is_valid, missing_features)
        """
        query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
        """)
        result = await self.session.execute(query)
        existing_columns = {row[0] for row in result.fetchall()}

        expected = set(self.config.short_feature_set)
        missing = expected - existing_columns

        max_missing = self.config.max_missing_features
        is_valid = len(missing) <= max_missing

        if missing:
            logger.warning(f"Missing short features: {missing}")

        return is_valid, list(missing)

    async def fetch_quality_data(
        self,
        timeframe: str,
        ts_eval: int,
    ) -> pd.DataFrame:
        """
        Fetch data for quality gate evaluation.

        Returns DataFrame with columns:
            symbol, valid_bars, gaps_count, max_ts, feature_bars, has_volume
        """
        window_days = self.config.windows_days.get(timeframe, 30)
        ts_start = ts_eval - (window_days * 24 * 60 * 60 * 1000)
        tf_bar_ms = self.config.get_tf_bar_ms(timeframe)
        gap_threshold = tf_bar_ms * self.config.quality.gap_threshold_multiplier

        query = text("""
            WITH ohlcv_data AS (
                SELECT
                    symbol,
                    timestamp,
                    volume,
                    LAG(timestamp) OVER (PARTITION BY symbol ORDER BY timestamp) as prev_ts
                FROM swap_ohlcv_p
                WHERE timeframe = :tf
                  AND timestamp BETWEEN :ts_start AND :ts_eval
            ),
            indicators_data AS (
                SELECT
                    symbol,
                    MAX(timestamp) as max_indicator_ts,
                    COUNT(*) FILTER (
                        WHERE atr_14 IS NOT NULL AND adx_14 IS NOT NULL
                    ) as feature_bars
                FROM indicators
                WHERE timeframe = :tf
                  AND timestamp BETWEEN :ts_start AND :ts_eval
                GROUP BY symbol
            ),
            gaps AS (
                SELECT
                    symbol,
                    COUNT(*) as total_bars,
                    COUNT(*) FILTER (
                        WHERE prev_ts IS NOT NULL
                        AND (timestamp - prev_ts) > :gap_threshold
                    ) as gaps_count,
                    MAX(timestamp) as max_ohlcv_ts,
                    SUM(volume) > 0 as has_volume
                FROM ohlcv_data
                GROUP BY symbol
            )
            SELECT
                g.symbol,
                g.total_bars as valid_bars,
                g.gaps_count,
                GREATEST(g.max_ohlcv_ts, COALESCE(i.max_indicator_ts, 0)) as max_ts,
                COALESCE(i.feature_bars, 0) as feature_bars,
                g.has_volume
            FROM gaps g
            LEFT JOIN indicators_data i ON g.symbol = i.symbol
        """)

        result = await self.session.execute(
            query,
            {
                "tf": timeframe,
                "ts_start": ts_start,
                "ts_eval": ts_eval,
                "gap_threshold": gap_threshold,
            },
        )

        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(
            rows,
            columns=["symbol", "valid_bars", "gaps_count", "max_ts", "feature_bars", "has_volume"],
        )

    async def fetch_pair_metrics_data(
        self,
        timeframe: str,
        ts_eval: int,
    ) -> pd.DataFrame:
        """
        Fetch joined OHLCV + indicators data for pair metrics calculation.

        Returns DataFrame with columns:
            symbol, close, volume, atr_14, adx_14, ema, prev_close
        """
        window_days = self.config.windows_days.get(timeframe, 30)
        ts_start = ts_eval - (window_days * 24 * 60 * 60 * 1000)
        ema_col = self.config.regime.ema_slope_source

        query = text(f"""
            WITH ohlcv AS (
                SELECT
                    symbol,
                    timestamp,
                    close,
                    volume,
                    LAG(close) OVER (PARTITION BY symbol ORDER BY timestamp) as prev_close
                FROM swap_ohlcv_p
                WHERE timeframe = :tf
                  AND timestamp BETWEEN :ts_start AND :ts_eval
            ),
            indicators AS (
                SELECT
                    symbol,
                    timestamp,
                    atr_14,
                    adx_14,
                    {ema_col} as ema
                FROM indicators
                WHERE timeframe = :tf
                  AND timestamp BETWEEN :ts_start AND :ts_eval
            )
            SELECT
                o.symbol,
                o.timestamp,
                o.close,
                o.volume,
                o.prev_close,
                i.atr_14,
                i.adx_14,
                i.ema
            FROM ohlcv o
            JOIN indicators i
                ON o.symbol = i.symbol AND o.timestamp = i.timestamp
            WHERE o.close > 0
            ORDER BY o.symbol, o.timestamp
        """)

        result = await self.session.execute(
            query,
            {"tf": timeframe, "ts_start": ts_start, "ts_eval": ts_eval},
        )

        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(
            rows,
            columns=["symbol", "timestamp", "close", "volume", "prev_close", "atr_14", "adx_14", "ema"],
        )

    async def fetch_basket_volume_data(
        self,
        timeframe: str,
        ts_eval: int,
        window_days: int = 30,
    ) -> pd.DataFrame:
        """
        Fetch volume data for basket selection.

        Returns DataFrame with columns: symbol, volume_median
        Sorted by volume_median descending.
        """
        ts_start = ts_eval - (window_days * 24 * 60 * 60 * 1000)
        min_bars = self.config.quality.warmup_min_bars // 2  # More relaxed for basket

        query = text("""
            SELECT
                symbol,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY volume) as volume_median
            FROM swap_ohlcv_p
            WHERE timeframe = :tf
              AND timestamp BETWEEN :ts_start AND :ts_eval
            GROUP BY symbol
            HAVING COUNT(*) >= :min_bars
            ORDER BY volume_median DESC
        """)

        result = await self.session.execute(
            query,
            {"tf": timeframe, "ts_start": ts_start, "ts_eval": ts_eval, "min_bars": min_bars},
        )

        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows, columns=["symbol", "volume_median"])

    async def fetch_regime_metrics(
        self,
        timeframe: str,
        ts_eval: int,
        basket_symbols: list[str],
    ) -> pd.DataFrame:
        """
        Fetch regime metrics for basket symbols.

        Returns DataFrame with columns:
            symbol, adx_median, atr_close_ratio, ema_slope, volume_median

        Note: ema_slope is calculated in Python using linear regression
        on indices (same method as PairMetricsCalculator) for consistency.
        """
        window_days = self.config.regime_windows_days.get(timeframe, 60)
        ts_start = ts_eval - (window_days * 24 * 60 * 60 * 1000)
        ema_col = self.config.regime.ema_slope_source
        slope_lookback = self.config.regime.slope_lookback_bars

        # Fetch all bars for slope calculation
        query = text(f"""
            WITH ohlcv AS (
                SELECT symbol, timestamp, close, volume
                FROM swap_ohlcv_p
                WHERE timeframe = :tf
                  AND timestamp BETWEEN :ts_start AND :ts_eval
                  AND symbol = ANY(:symbols)
            ),
            indicators AS (
                SELECT symbol, timestamp, adx_14, atr_14, {ema_col} as ema
                FROM indicators
                WHERE timeframe = :tf
                  AND timestamp BETWEEN :ts_start AND :ts_eval
                  AND symbol = ANY(:symbols)
            ),
            joined AS (
                SELECT
                    o.symbol,
                    o.timestamp,
                    o.close,
                    o.volume,
                    i.adx_14,
                    i.atr_14 / NULLIF(o.close, 0) as atr_close_ratio,
                    i.ema
                FROM ohlcv o
                JOIN indicators i ON o.symbol = i.symbol AND o.timestamp = i.timestamp
                WHERE o.close > 0 AND i.ema IS NOT NULL
            )
            SELECT
                symbol,
                timestamp,
                adx_14,
                atr_close_ratio,
                ema,
                close,
                volume
            FROM joined
            ORDER BY symbol, timestamp
        """)

        result = await self.session.execute(
            query,
            {"tf": timeframe, "ts_start": ts_start, "ts_eval": ts_eval, "symbols": basket_symbols},
        )

        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()

        # Convert to DataFrame
        bars_df = pd.DataFrame(
            rows,
            columns=["symbol", "timestamp", "adx_14", "atr_close_ratio", "ema", "close", "volume"],
        )

        # Calculate metrics per symbol
        results = []
        for symbol in bars_df["symbol"].unique():
            symbol_df = bars_df[bars_df["symbol"] == symbol].sort_values("timestamp")

            if len(symbol_df) < 10:
                continue

            # Aggregated metrics
            adx_median = float(symbol_df["adx_14"].median())
            atr_close_median = float(symbol_df["atr_close_ratio"].median())
            volume_median = float(symbol_df["volume"].median())

            # Calculate EMA slope using linear regression on indices
            # (same method as PairMetricsCalculator)
            ema_values = symbol_df["ema"].values
            # Use last N bars
            lookback = min(slope_lookback, len(ema_values))
            window_ema = ema_values[-lookback:]

            if len(window_ema) >= 10:
                x = np.arange(len(window_ema))
                x_mean = x.mean()
                y_mean = window_ema.mean()

                numerator = ((x - x_mean) * (window_ema - y_mean)).sum()
                denominator = ((x - x_mean) ** 2).sum()

                if denominator > 1e-12:
                    ema_slope = float(numerator / denominator)
                else:
                    ema_slope = 0.0
            else:
                ema_slope = 0.0

            results.append({
                "symbol": symbol,
                "adx_median": adx_median,
                "atr_close_ratio": atr_close_median,
                "ema_slope": ema_slope,
                "volume_median": volume_median,
            })

        return pd.DataFrame(results)

    async def fetch_atr_percentile(
        self,
        timeframe: str,
        ts_eval: int,
        percentile: int = 80,
    ) -> float:
        """
        Fetch ATR/close percentile for volatility classification.
        """
        window_days = self.config.regime_windows_days.get(timeframe, 60)
        ts_start = ts_eval - (window_days * 24 * 60 * 60 * 1000)

        query = text(f"""
            SELECT PERCENTILE_CONT(:pct / 100.0) WITHIN GROUP (
                ORDER BY i.atr_14 / NULLIF(o.close, 0)
            ) as atr_pct
            FROM swap_ohlcv_p o
            JOIN indicators i
                ON o.symbol = i.symbol
                AND o.timeframe = i.timeframe
                AND o.timestamp = i.timestamp
            WHERE o.timeframe = :tf
              AND o.timestamp BETWEEN :ts_start AND :ts_eval
              AND o.close > 0
        """)

        result = await self.session.execute(
            query,
            {"tf": timeframe, "ts_start": ts_start, "ts_eval": ts_eval, "pct": percentile},
        )

        row = result.fetchone()
        return float(row[0]) if row and row[0] else 0.02  # default

    async def fetch_previous_universe(self) -> set[str]:
        """
        Fetch symbols from the most recent published universe.
        """
        query = text("""
            SELECT mu.symbol
            FROM market_universe mu
            JOIN market_universe_versions muv ON mu.ts_version = muv.ts_version
            WHERE muv.status = 'published'
            ORDER BY muv.ts_version DESC
            LIMIT 1
        """)

        result = await self.session.execute(query)
        rows = result.fetchall()
        return {row[0] for row in rows}

    async def fetch_score_history(
        self,
        symbols: list[str],
        days: int = 30,
    ) -> dict[str, list[float]]:
        """
        Fetch historical final_scores for stability calculation.

        Returns Dict[symbol -> list of scores, newest first]
        """
        query = text("""
            SELECT symbol, final_score
            FROM market_universe mu
            JOIN market_universe_versions muv ON mu.ts_version = muv.ts_version
            WHERE muv.status = 'published'
              AND symbol = ANY(:symbols)
              AND muv.created_at > NOW() - INTERVAL ':days days'
            ORDER BY muv.ts_version DESC
        """.replace(":days", str(days)))

        result = await self.session.execute(query, {"symbols": symbols})
        rows = result.fetchall()

        history: dict[str, list[float]] = {s: [] for s in symbols}
        for symbol, score in rows:
            if symbol in history:
                history[symbol].append(float(score))

        return history

    async def get_last_published_version(self) -> int | None:
        """Get ts_version of last published universe."""
        query = text("""
            SELECT ts_version
            FROM market_universe_versions
            WHERE status = 'published'
            ORDER BY ts_version DESC
            LIMIT 1
        """)

        result = await self.session.execute(query)
        row = result.fetchone()
        return row[0] if row else None

    async def get_last_valid_regime(self) -> dict | None:
        """
        Get last valid (non-stale) regime from history.

        Returns dict with regime data or None if no history.
        """
        query = text("""
            SELECT
                ts_eval,
                global_regime,
                global_strength,
                regime_confidence,
                regime_1d,
                regime_1d_strength,
                regime_4h,
                regime_4h_strength,
                regime_1h,
                regime_1h_strength,
                basket_size,
                basket_symbols,
                basket_adx_median,
                basket_atr_close_median,
                basket_ema_slope_median
            FROM market_regime_history
            WHERE is_stale = false
            ORDER BY ts_eval DESC
            LIMIT 1
        """)

        result = await self.session.execute(query)
        row = result.fetchone()

        if not row:
            return None

        return {
            "ts_eval": row[0],
            "global_regime": row[1],
            "global_strength": float(row[2]),
            "regime_confidence": float(row[3]),
            "regime_1d": row[4],
            "regime_1d_strength": float(row[5]) if row[5] else None,
            "regime_4h": row[6],
            "regime_4h_strength": float(row[7]) if row[7] else None,
            "regime_1h": row[8],
            "regime_1h_strength": float(row[9]) if row[9] else None,
            "basket_size": row[10],
            "basket_symbols": row[11] if row[11] else [],
            "basket_adx_median": float(row[12]) if row[12] else 0.0,
            "basket_atr_close_median": float(row[13]) if row[13] else 0.0,
            "basket_ema_slope_median": float(row[14]) if row[14] else 0.0,
        }

    async def check_regime_tf_lag(
        self,
        timeframe: str,
        ts_eval: int,
    ) -> int:
        """
        Check data lag for regime TF in seconds.

        Returns lag in seconds, or 0 if no data.
        """
        window_days = self.config.regime_windows_days.get(timeframe, 60)
        ts_start = ts_eval - (window_days * 24 * 60 * 60 * 1000)

        query = text("""
            SELECT MAX(timestamp) as max_ts
            FROM (
                SELECT timestamp FROM swap_ohlcv_p
                WHERE timeframe = :tf AND timestamp BETWEEN :ts_start AND :ts_eval
                UNION ALL
                SELECT timestamp FROM indicators
                WHERE timeframe = :tf AND timestamp BETWEEN :ts_start AND :ts_eval
            ) combined
        """)

        result = await self.session.execute(
            query,
            {"tf": timeframe, "ts_start": ts_start, "ts_eval": ts_eval},
        )

        row = result.fetchone()
        if not row or not row[0]:
            return 999999  # Very high lag if no data

        max_ts = row[0]
        lag_seconds = int((ts_eval - max_ts) / 1000)
        return lag_seconds
