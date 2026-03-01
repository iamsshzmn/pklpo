"""
Market Selection Pipeline

Main orchestrator for market selection process:
1. Resolve ts_eval
2. Validate features
3. Compute global regime
4. Compute quality gate per TF
5. Compute pair metrics per TF
6. Normalize and score
7. Aggregate across TFs
8. Select universe
9. Publish version
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

import pandas as pd

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from ..config import MarketSelectionConfig, get_config
from ..domain.metrics import PairMetricsCalculator
from ..domain.quality_gate import DataQualityGate, QualityResult, ReasonFlag
from ..domain.regime import GlobalRegime, RegimeClassifier, RegimeType
from ..domain.scoring import ScoringEngine
from ..domain.universe import (
    UniverseManager,
    UniverseStatus,
    UniverseVersion,
)
from ..infrastructure.database import MarketSelectionDB
from ..infrastructure.monitoring import get_metrics, record_pipeline_metrics
from ..infrastructure.persistence import LockTimeoutError, MarketSelectionPersistence

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass
class PipelineResult:
    """Result of market selection pipeline run."""

    success: bool
    ts_version: int
    ts_eval: int
    universe_size: int
    status: UniverseStatus

    # Regime
    global_regime: RegimeType | None = None

    # Statistics
    eligible_counts: dict[str, int] = field(default_factory=dict)
    total_symbols: int = 0
    execution_time_seconds: float = 0.0

    # Errors
    error_message: str | None = None
    reason_flags: list[ReasonFlag] = field(default_factory=list)

    # Config
    config_hash: str = ""


class MarketSelectionPipeline:
    """
    Main orchestrator for market selection.

    Usage:
        async with AsyncSession() as session:
            pipeline = MarketSelectionPipeline(session)
            result = await pipeline.run()
    """

    def __init__(
        self,
        session: AsyncSession,
        config: MarketSelectionConfig | None = None,
    ):
        self.session = session
        self.config = config or get_config()

        # Initialize components
        self.db = MarketSelectionDB(session, self.config)
        self.persistence = MarketSelectionPersistence(session)
        self.quality_gate = DataQualityGate(self.config)
        self.metrics_calc = PairMetricsCalculator(
            ema_slope_source=self.config.regime.ema_slope_source,
            slope_lookback_bars=self.config.regime.slope_lookback_bars,
            adx_trend_threshold=self.config.regime.adx_trend_threshold,
            adx_range_threshold=self.config.regime.adx_range_threshold,
        )
        self.regime_classifier = RegimeClassifier(self.config)
        self.scoring_engine = ScoringEngine(self.config)
        self.universe_manager = UniverseManager(self.config)
        self.write_lock_timeout_ms = 10_000

    async def run(self) -> PipelineResult:
        """
        Execute the full market selection pipeline.

        Steps:
        1. Resolve ts_eval from data
        2. Validate short features exist
        3. Compute global market regime
        4. For each selection TF:
           - Compute quality gate
           - Compute pair metrics
           - Normalize and score
        5. Aggregate across TFs
        6. Select universe (top-N with stability)
        7. Publish version
        """
        start_time = time.time()
        config_hash = self.config.config_hash()
        ts_eval = 0
        ts_version = 0

        logger.info(f"Starting market selection pipeline (config_hash={config_hash})")

        try:
            # Step 1: Resolve ts_eval
            ts_eval = await self.db.resolve_ts_eval()
            if ts_eval is None:
                return PipelineResult(
                    success=False,
                    ts_version=0,
                    ts_eval=0,
                    universe_size=0,
                    status=UniverseStatus.FAILED,
                    error_message="Could not resolve ts_eval - no data",
                    config_hash=config_hash,
                )

            ts_version = ts_eval  # Use ts_eval as version
            logger.info(f"ts_eval={ts_eval}, ts_version={ts_version}")

            # Step 2: Validate features
            is_valid, missing_features = await self.db.validate_short_features()
            if not is_valid:
                return PipelineResult(
                    success=False,
                    ts_version=ts_version,
                    ts_eval=ts_eval,
                    universe_size=0,
                    status=UniverseStatus.FAILED,
                    error_message=f"SHORT_FEATURE_MISMATCH: {missing_features}",
                    reason_flags=[ReasonFlag.SHORT_FEATURE_MISMATCH],
                    config_hash=config_hash,
                )

            # Step 3: Compute global regime
            regime = await self._compute_regime(ts_eval)

            # Check for stale regime (lag exceeds threshold)
            regime = await self._check_and_fix_stale_regime(regime, ts_eval)

            logger.info(f"Global regime: {regime.regime.value} (strength={regime.strength:.2f}, stale={regime.stale})")

            # Save regime history
            await self.persistence.insert_regime_history(ts_eval, regime, config_hash)
            await self.session.commit()

            # Step 4-6: Process each TF
            tf_scores: dict[str, dict[str, float]] = {}  # tf -> {symbol -> score_tf}
            eligible_counts: dict[str, int] = {}
            all_quality_results: dict[str, dict[str, QualityResult]] = {}  # tf -> {symbol -> result}
            all_metrics_raw: dict[str, dict[str, dict]] = {}  # tf -> {symbol -> raw_metrics}
            total_symbols = 0

            for tf in self.config.selection_tfs:
                logger.info(f"Processing {tf}...")

                # Quality gate
                quality_results = await self._compute_quality_gate(tf, ts_eval)
                all_quality_results[tf] = {r.symbol: r for r in quality_results}

                eligible = [r for r in quality_results if r.eligible]
                eligible_counts[tf] = len(eligible)
                total_symbols = max(total_symbols, len(quality_results))

                if not eligible:
                    logger.warning(f"No eligible symbols for {tf}")
                    continue

                # Pair metrics
                metrics_df = await self._compute_pair_metrics(
                    tf, ts_eval, [r.symbol for r in eligible]
                )

                if metrics_df.empty:
                    logger.warning(f"No metrics computed for {tf}")
                    continue

                all_metrics_raw[tf] = metrics_df.set_index("symbol").to_dict("index")

                # Normalize
                normalized_df = self.scoring_engine.normalize_metrics(metrics_df, tf)

                # Score
                quality_scores = {r.symbol: r.quality_score for r in eligible}
                scores = self.scoring_engine.calculate_tf_scores(
                    normalized_df, tf, regime.regime, quality_scores
                )

                # Apply VOLATILE regime filter: exclude low liquidity
                if regime.regime.value == "VOLATILE":
                    liq_scores = {s.symbol: s.liq_score for s in scores}
                    excluded = self.scoring_engine.apply_volatile_filter(scores, liq_scores)
                    # Remove excluded symbols from scores and mark as ineligible
                    scores = [s for s in scores if s.symbol not in excluded]
                    for symbol in excluded:
                        if symbol in all_quality_results[tf]:
                            all_quality_results[tf][symbol].eligible = False
                            all_quality_results[tf][symbol].reason_flags.append(
                                ReasonFlag.LOW_LIQ_IN_VOLATILE
                            )

                # Store
                tf_scores[tf] = {s.symbol: s.score_tf for s in scores}

                # Persist scores
                await self.persistence.upsert_scores_tf(
                    ts_eval=ts_eval,
                    timeframe=tf,
                    scores=scores,
                    quality_results=all_quality_results[tf],
                    metrics_raw=all_metrics_raw.get(tf, {}),
                    regime=regime,
                    config_hash=config_hash,
                    window_days=self.config.windows_days.get(tf, 30),
                )
                await self.session.commit()

            # Check for systemic outage
            if self.universe_manager.check_systemic_outage(eligible_counts, total_symbols):
                logger.warning("Systemic senior TF outage detected - using fallback")
                return await self._handle_fallback(
                    ts_version, ts_eval, regime, config_hash,
                    "SYSTEMIC_SENIOR_OUTAGE", eligible_counts, start_time
                )

            # Step 7: Aggregate across TFs
            final_scores = self.scoring_engine.aggregate_mtf_scores(tf_scores, regime.regime)

            if not final_scores:
                logger.error("No final scores computed")
                return await self._handle_fallback(
                    ts_version, ts_eval, regime, config_hash,
                    "NO_FINAL_SCORES", eligible_counts, start_time
                )

            # Step 8: Select universe
            previous_universe = await self.db.fetch_previous_universe()
            score_history = await self.db.fetch_score_history(
                [s.symbol for s in final_scores], days=30
            )

            universe, global_flags = self.universe_manager.select_universe(
                final_scores=final_scores,
                score_history=score_history,
                previous_universe=previous_universe,
                regime=regime,
                whitelist=set(self.config.universe.whitelist),
                blacklist=set(self.config.universe.blacklist),
            )

            # Check for fallback
            should_fallback, fallback_reason = self.universe_manager.should_fallback(
                len(universe)
            )

            if should_fallback:
                logger.warning(f"Universe too small: {fallback_reason}")
                return await self._handle_fallback(
                    ts_version, ts_eval, regime, config_hash,
                    fallback_reason or "SMALL_UNIVERSE", eligible_counts, start_time
                )

            # Step 9: Publish
            execution_time = time.time() - start_time

            version = self.universe_manager.create_version(
                ts_version=ts_version,
                ts_eval=ts_eval,
                universe=universe,
                eligible_counts=eligible_counts,
                regime=regime,
                config_hash=config_hash,
                execution_time=execution_time,
            )

            async def _publish_write_stage() -> None:
                await self.persistence.insert_universe_version(version)
                await self.persistence.insert_universe_entries(
                    ts_version, universe, config_hash
                )
                await self.persistence.update_version_status(
                    ts_version, UniverseStatus.PUBLISHED.value
                )

            await self._run_write_stage(ts_version, _publish_write_stage)

            logger.info(
                f"Pipeline completed: {len(universe)} symbols in universe "
                f"({execution_time:.2f}s)"
            )

            # Record monitoring metrics
            record_pipeline_metrics(
                ts_version=ts_version,
                ts_eval=ts_eval,
                success=True,
                status=UniverseStatus.PUBLISHED.value,
                universe_size=len(universe),
                execution_time_seconds=execution_time,
                global_regime=regime.regime.value,
                regime_strength=regime.strength,
                regime_stale=regime.stale,
                eligible_counts=eligible_counts,
                total_symbols=total_symbols,
                reason_flags=[f.value for f in global_flags],
            )

            return PipelineResult(
                success=True,
                ts_version=ts_version,
                ts_eval=ts_eval,
                universe_size=len(universe),
                status=UniverseStatus.PUBLISHED,
                global_regime=regime.regime,
                eligible_counts=eligible_counts,
                total_symbols=total_symbols,
                execution_time_seconds=execution_time,
                reason_flags=global_flags,
                config_hash=config_hash,
            )

        except LockTimeoutError as e:
            execution_time = time.time() - start_time
            get_metrics().record_error("LOCK_TIMEOUT", str(e))

            record_pipeline_metrics(
                ts_version=ts_version,
                ts_eval=ts_eval,
                success=False,
                status=UniverseStatus.FAILED.value,
                universe_size=0,
                execution_time_seconds=execution_time,
                error_message=str(e),
                reason_flags=["LOCK_TIMEOUT"],
            )
            return PipelineResult(
                success=False,
                ts_version=ts_version,
                ts_eval=ts_eval,
                universe_size=0,
                status=UniverseStatus.FAILED,
                error_message=str(e),
                execution_time_seconds=execution_time,
                config_hash=config_hash,
            )
        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            await self.session.rollback()

            execution_time = time.time() - start_time

            # Record failure metrics
            record_pipeline_metrics(
                ts_version=0,
                ts_eval=0,
                success=False,
                status=UniverseStatus.FAILED.value,
                universe_size=0,
                execution_time_seconds=execution_time,
                error_message=str(e),
                reason_flags=["EXCEPTION"],
            )

            return PipelineResult(
                success=False,
                ts_version=ts_version,
                ts_eval=ts_eval,
                universe_size=0,
                status=UniverseStatus.FAILED,
                error_message=str(e),
                execution_time_seconds=execution_time,
                config_hash=config_hash,
            )

    async def _run_write_stage(
        self,
        ts_version: int,
        callback: Callable[[], Awaitable[T]],
    ) -> T:
        """
        Execute write-stage in a short transaction guarded by PostgreSQL advisory lock.
        """
        if self.session.in_transaction():
            # Drop any read-only/autobegin transaction before short write-stage.
            await self.session.commit()

        async with self.session.begin():
            wait_seconds = await self.persistence.acquire_write_lock_for_ts_version(
                ts_version=ts_version,
                lock_timeout_ms=self.write_lock_timeout_ms,
            )
            logger.info(
                "Write-stage lock wait ts_version=%s wait=%.3fs timeout_ms=%s",
                ts_version,
                wait_seconds,
                self.write_lock_timeout_ms,
            )
            return await callback()

    async def _compute_regime(self, ts_eval: int) -> GlobalRegime:
        """Compute global market regime."""
        # Select basket
        basket_tf = self.config.regime.basket_volume_tf
        volume_data = await self.db.fetch_basket_volume_data(
            basket_tf, ts_eval, self.config.regime.basket_volume_window_days
        )

        basket_symbols = self.regime_classifier.select_basket(volume_data)
        logger.info(f"Basket: {len(basket_symbols)} symbols")

        # Fetch metrics for each regime TF
        tf_data: dict[str, pd.DataFrame] = {}
        atr_percentiles: dict[str, float] = {}

        for tf in self.config.regime_tfs:
            df = await self.db.fetch_regime_metrics(tf, ts_eval, basket_symbols)
            tf_data[tf] = df

            atr_p80 = await self.db.fetch_atr_percentile(
                tf, ts_eval, self.config.regime.atr_volatile_percentile
            )
            atr_percentiles[tf] = atr_p80

        # Compute regime
        regime = self.regime_classifier.compute_global_regime(
            basket_symbols, tf_data, atr_percentiles
        )

        return regime

    async def _check_and_fix_stale_regime(
        self,
        regime: GlobalRegime,
        ts_eval: int,
    ) -> GlobalRegime:
        """
        Check if regime TF data is stale and use last valid regime if needed.

        If any regime TF has lag exceeding threshold, fetch last valid regime
        from history and mark as stale.
        """
        lag_thresholds = self.config.regime.regime_lag_max_minutes
        max_lag_seconds = 0
        stale_tfs = []

        # Check lag for each regime TF
        for tf in self.config.regime_tfs:
            lag_seconds = await self.db.check_regime_tf_lag(tf, ts_eval)
            threshold_seconds = lag_thresholds.get(tf, 1440) * 60  # Convert minutes to seconds

            if lag_seconds > threshold_seconds:
                stale_tfs.append(tf)
                max_lag_seconds = max(max_lag_seconds, lag_seconds)

        # If any TF is stale, use last valid regime from history
        if stale_tfs:
            logger.warning(
                f"Regime TF data stale: {stale_tfs} (max lag: {max_lag_seconds}s). "
                "Using last valid regime from history."
            )

            last_valid = await self.db.get_last_valid_regime()
            if last_valid:
                # Reconstruct GlobalRegime from history
                from ..domain.regime import RegimeType, TFRegime

                # Reconstruct TF regimes
                tf_regimes = {}
                for tf in self.config.regime_tfs:
                    regime_key = f"regime_{tf.lower()}"
                    strength_key = f"regime_{tf.lower()}_strength"

                    regime_type_str = last_valid.get(regime_key)
                    regime_strength = last_valid.get(strength_key, 0.5)

                    if regime_type_str:
                        try:
                            regime_type = RegimeType(regime_type_str)
                        except ValueError:
                            regime_type = RegimeType.RANGE
                    else:
                        regime_type = RegimeType.RANGE

                    tf_regimes[tf] = TFRegime(
                        timeframe=tf,
                        regime=regime_type,
                        strength=regime_strength,
                        adx_median=0.0,  # Not stored in history
                        atr_close_ratio=0.0,
                        ema_slope=0.0,
                    )

                # Create GlobalRegime from history
                regime = GlobalRegime(
                    regime=RegimeType(last_valid["global_regime"]),
                    strength=last_valid["global_strength"],
                    confidence=last_valid["regime_confidence"],
                    stale=True,
                    tf_regimes=tf_regimes,
                    basket_symbols=last_valid.get("basket_symbols", []),
                    basket_size=last_valid.get("basket_size", 0),
                    basket_adx_median=last_valid.get("basket_adx_median", 0.0),
                    basket_atr_close_median=last_valid.get("basket_atr_close_median", 0.0),
                    basket_ema_slope_median=last_valid.get("basket_ema_slope_median", 0.0),
                )

                logger.info(
                    f"Using stale regime from ts_eval={last_valid['ts_eval']} "
                    f"(current ts_eval={ts_eval})"
                )
            else:
                # No history available - keep current regime but mark as stale
                logger.warning("No valid regime history found, keeping current regime but marking stale")
                regime.stale = True

        return regime

    async def _compute_quality_gate(
        self, timeframe: str, ts_eval: int
    ) -> list[QualityResult]:
        """Compute quality gate for all symbols in a TF."""
        quality_df = await self.db.fetch_quality_data(timeframe, ts_eval)

        if quality_df.empty:
            return []

        window_days = self.config.windows_days.get(timeframe, 30)
        expected_bars = self.quality_gate.calculate_expected_bars(timeframe, window_days)

        results = []
        for _, row in quality_df.iterrows():
            data_lag_seconds = int((ts_eval - row["max_ts"]) / 1000) if row["max_ts"] else 999999

            result = self.quality_gate.evaluate(
                symbol=row["symbol"],
                timeframe=timeframe,
                valid_bars=int(row["valid_bars"]),
                expected_bars=expected_bars,
                gaps_count=int(row["gaps_count"]),
                data_lag_seconds=data_lag_seconds,
                volume_present=bool(row["has_volume"]),
                feature_bars=int(row["feature_bars"]),
            )
            results.append(result)

        return results

    async def _compute_pair_metrics(
        self, timeframe: str, ts_eval: int, eligible_symbols: list[str]
    ) -> pd.DataFrame:
        """Compute pair metrics for eligible symbols."""
        # Fetch data
        data_df = await self.db.fetch_pair_metrics_data(timeframe, ts_eval)

        if data_df.empty:
            return pd.DataFrame()

        # Filter to eligible
        data_df = data_df[data_df["symbol"].isin(eligible_symbols)]

        if data_df.empty:
            return pd.DataFrame()

        window_days = self.config.windows_days.get(timeframe, 30)
        expected_bars = self.quality_gate.calculate_expected_bars(timeframe, window_days)

        # Calculate metrics per symbol
        results = []
        for symbol, group_df in data_df.groupby("symbol"):
            metrics = self.metrics_calc.calculate_all(
                group_df, str(symbol), timeframe, expected_bars
            )
            results.append(metrics.to_dict())

        return pd.DataFrame(results)

    async def _handle_fallback(
        self,
        ts_version: int,
        ts_eval: int,
        regime: GlobalRegime,
        config_hash: str,
        fallback_reason: str,
        eligible_counts: dict[str, int],
        start_time: float,
    ) -> PipelineResult:
        """Handle fallback to previous universe."""
        source_version = await self.db.get_last_published_version()

        if source_version is None:
            logger.error("No previous universe to fallback to")
            return PipelineResult(
                success=False,
                ts_version=ts_version,
                ts_eval=ts_eval,
                universe_size=0,
                status=UniverseStatus.FAILED,
                error_message="No previous universe for fallback",
                reason_flags=[ReasonFlag.UNIVERSE_FALLBACK_PREV],
                config_hash=config_hash,
            )

        # Create fallback version
        version = UniverseVersion(
            ts_version=ts_version,
            ts_eval=ts_eval,
            status=UniverseStatus.FALLBACK_PREV,
            universe_size=0,  # Will be updated
            eligible_count=sum(eligible_counts.values()),
            config_hash=config_hash,
            source_version=source_version,
            fallback_reason=fallback_reason,
            global_regime=regime.regime.value,
            global_strength=regime.strength,
            execution_time_seconds=time.time() - start_time,
        )
        copy_metrics: dict[str, int] = {}

        async def _fallback_write_stage() -> None:
            await self.persistence.insert_universe_version(version)
            nonlocal copy_metrics
            copy_metrics = await self.persistence.copy_previous_universe_with_metrics(
                ts_version,
                source_version,
                config_hash,
            )
            await self.persistence.update_version_status(
                ts_version, UniverseStatus.FALLBACK_PREV.value,
                notes=(
                    f"Copied {copy_metrics['inserted_count']} symbols from {source_version}; "
                    f"source={copy_metrics['source_count']} "
                    f"skipped={copy_metrics['skipped_conflicts']} "
                    f"source_duplicates={copy_metrics['source_duplicates']}"
                ),
            )

        await self._run_write_stage(ts_version, _fallback_write_stage)
        count = copy_metrics["inserted_count"]

        execution_time = time.time() - start_time

        # Record fallback metrics
        record_pipeline_metrics(
            ts_version=ts_version,
            ts_eval=ts_eval,
            success=True,
            status=UniverseStatus.FALLBACK_PREV.value,
            universe_size=count,
            execution_time_seconds=execution_time,
            global_regime=regime.regime.value,
            regime_strength=regime.strength,
            regime_stale=regime.stale,
            eligible_counts=eligible_counts,
            reason_flags=[fallback_reason],
        )

        return PipelineResult(
            success=True,
            ts_version=ts_version,
            ts_eval=ts_eval,
            universe_size=count,
            status=UniverseStatus.FALLBACK_PREV,
            global_regime=regime.regime,
            eligible_counts=eligible_counts,
            execution_time_seconds=execution_time,
            reason_flags=[ReasonFlag.UNIVERSE_FALLBACK_PREV],
            config_hash=config_hash,
        )
