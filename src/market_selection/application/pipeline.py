"""Market Selection Pipeline orchestration."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from ..domain.metrics import PairMetricsCalculator
from ..domain.quality_gate import DataQualityGate, QualityResult, ReasonFlag
from ..domain.regime import GlobalRegime, RegimeClassifier
from ..domain.scoring import ScoringEngine, TFScore
from ..domain.universe import UniverseManager, UniverseStatus
from ..infrastructure.persistence import LockTimeoutError
from .config_projection import (
    build_quality_gate_config,
    build_regime_classifier_config,
    build_scoring_config,
    build_universe_config,
)
from .models import PipelineResult, PipelineRunContext, TimeframeProcessingState
from .steps import PipelineStepExecutor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..config import MarketSelectionConfig
    from ..ports import MarketSelectionDBPort, MonitoringPort, PersistencePort

logger = logging.getLogger(__name__)


class MarketSelectionPipeline:
    """Main orchestrator for market selection."""

    def __init__(
        self,
        session: AsyncSession,
        config: MarketSelectionConfig,
        db: MarketSelectionDBPort,
        persistence: PersistencePort,
        monitoring: MonitoringPort,
    ):
        self.session = session
        self.config = config
        self.db = db
        self.persistence = persistence
        self.monitoring = monitoring

        self.quality_gate = DataQualityGate(build_quality_gate_config(config))
        self.metrics_calc = PairMetricsCalculator(
            ema_slope_source=config.regime.ema_slope_source,
            slope_lookback_bars=config.regime.slope_lookback_bars,
            adx_trend_threshold=config.regime.adx_trend_threshold,
            adx_range_threshold=config.regime.adx_range_threshold,
        )
        self.regime_classifier = RegimeClassifier(
            build_regime_classifier_config(config)
        )
        self.scoring_engine = ScoringEngine(build_scoring_config(config))
        self.universe_manager = UniverseManager(build_universe_config(config))
        self.write_lock_timeout_ms = 10_000
        self.steps = PipelineStepExecutor(
            session=session,
            config=config,
            db=db,
            persistence=persistence,
            monitoring=monitoring,
            quality_gate=self.quality_gate,
            metrics_calc=self.metrics_calc,
            regime_classifier=self.regime_classifier,
            universe_manager=self.universe_manager,
            write_lock_timeout_ms=self.write_lock_timeout_ms,
        )

    @classmethod
    def from_config(
        cls,
        session: AsyncSession,
        config: MarketSelectionConfig,
    ) -> MarketSelectionPipeline:
        """Construct a pipeline from explicit application config."""
        from ..infrastructure.factory import build_market_selection_pipeline

        return build_market_selection_pipeline(session, config)

    async def run(self) -> PipelineResult:
        """Execute the full market selection pipeline."""
        ctx = PipelineRunContext(
            start_time=time.time(),
            config_hash=self.config.config_hash(),
        )
        logger.info(
            "Starting market selection pipeline (config_hash=%s)", ctx.config_hash
        )

        try:
            early_result = await self._initialize_run(ctx)
            if early_result is not None:
                return early_result

            regime = await self._prepare_regime(ctx)
            state = await self._process_timeframes(ctx, regime)

            fallback_result = await self._fallback_for_systemic_outage(
                ctx, regime, state
            )
            if fallback_result is not None:
                return fallback_result

            final_scores = self.scoring_engine.aggregate_mtf_scores(
                state.tf_scores,
                regime.regime,
            )
            if not final_scores:
                return await self.steps.handle_fallback(
                    ctx.ts_version,
                    ctx.ts_eval,
                    regime,
                    ctx.config_hash,
                    "NO_FINAL_SCORES",
                    state.eligible_counts,
                    ctx.start_time,
                )

            universe, global_flags = await self.steps.select_universe(
                final_scores, regime
            )
            should_fallback, fallback_reason = self.universe_manager.should_fallback(
                len(universe)
            )
            if should_fallback:
                return await self.steps.handle_fallback(
                    ctx.ts_version,
                    ctx.ts_eval,
                    regime,
                    ctx.config_hash,
                    fallback_reason or "SMALL_UNIVERSE",
                    state.eligible_counts,
                    ctx.start_time,
                )

            return await self.steps.publish_success(
                ctx=ctx,
                regime=regime,
                state=state,
                universe=universe,
                global_flags=global_flags,
            )
        except LockTimeoutError as exc:
            return self._handle_lock_timeout(ctx, exc)
        except Exception as exc:
            return await self._handle_unexpected_exception(ctx, exc)

    async def _initialize_run(
        self,
        ctx: PipelineRunContext,
    ) -> PipelineResult | None:
        """Resolve ts_eval and validate short features before processing."""
        ctx.ts_eval = await self.db.resolve_ts_eval()
        if ctx.ts_eval is None:
            return self._build_failure_result(
                ctx,
                error_message="Could not resolve ts_eval - no data",
            )

        ctx.ts_version = ctx.ts_eval
        logger.info("ts_eval=%s ts_version=%s", ctx.ts_eval, ctx.ts_version)

        is_valid, missing_features = await self.db.validate_short_features()
        if not is_valid:
            return self._build_failure_result(
                ctx,
                error_message=f"SHORT_FEATURE_MISMATCH: {missing_features}",
                reason_flags=[ReasonFlag.SHORT_FEATURE_MISMATCH],
            )
        return None

    async def _prepare_regime(self, ctx: PipelineRunContext) -> GlobalRegime:
        """Compute, normalize, and persist global regime."""
        regime = await self.steps.compute_regime(ctx.ts_eval)
        regime = await self.steps.check_and_fix_stale_regime(regime, ctx.ts_eval)
        logger.info(
            "Global regime: %s (strength=%.2f, stale=%s)",
            regime.regime.value,
            regime.strength,
            regime.stale,
        )
        await self.persistence.insert_regime_history(
            ctx.ts_eval, regime, ctx.config_hash
        )
        await self.session.commit()
        return regime

    async def _process_timeframes(
        self,
        ctx: PipelineRunContext,
        regime: GlobalRegime,
    ) -> TimeframeProcessingState:
        """Run quality, metrics, normalization, and persistence across TFs."""
        state = TimeframeProcessingState()
        for timeframe in self.config.selection_tfs:
            await self._process_single_timeframe(timeframe, ctx, regime, state)
        return state

    async def _process_single_timeframe(
        self,
        timeframe: str,
        ctx: PipelineRunContext,
        regime: GlobalRegime,
        state: TimeframeProcessingState,
    ) -> None:
        """Process one selection timeframe end-to-end."""
        logger.info("Processing %s...", timeframe)
        quality_results = await self.steps.compute_quality_gate(timeframe, ctx.ts_eval)
        quality_by_symbol = {result.symbol: result for result in quality_results}
        state.quality_results[timeframe] = quality_by_symbol

        eligible = [result for result in quality_results if result.eligible]
        state.eligible_counts[timeframe] = len(eligible)
        state.total_symbols = max(state.total_symbols, len(quality_results))
        if not eligible:
            logger.warning("No eligible symbols for %s", timeframe)
            return

        metrics_df = await self.steps.compute_pair_metrics(
            timeframe,
            ctx.ts_eval,
            [result.symbol for result in eligible],
        )
        if metrics_df.empty:
            logger.warning("No metrics computed for %s", timeframe)
            return

        state.metrics_raw[timeframe] = metrics_df.set_index("symbol").to_dict("index")
        normalized_df = self.scoring_engine.normalize_metrics(metrics_df, timeframe)
        quality_scores = {result.symbol: result.quality_score for result in eligible}
        scores = self.scoring_engine.calculate_tf_scores(
            normalized_df,
            timeframe,
            regime.regime,
            quality_scores,
        )
        scores = self._apply_volatile_filter(
            timeframe, regime, quality_by_symbol, scores
        )
        state.tf_scores[timeframe] = {score.symbol: score.score_tf for score in scores}

        await self.persistence.upsert_scores_tf(
            ts_eval=ctx.ts_eval,
            timeframe=timeframe,
            scores=scores,
            quality_results=quality_by_symbol,
            metrics_raw=state.metrics_raw.get(timeframe, {}),
            regime=regime,
            config_hash=ctx.config_hash,
            window_days=self.config.windows_days.get(timeframe, 30),
        )
        await self.session.commit()

    def _apply_volatile_filter(
        self,
        timeframe: str,
        regime: GlobalRegime,
        quality_by_symbol: dict[str, QualityResult],
        scores: list[TFScore],
    ) -> list[TFScore]:
        """Remove low-liquidity symbols in VOLATILE regime."""
        if regime.regime.value != "VOLATILE":
            return scores

        liq_scores = {score.symbol: score.liq_score for score in scores}
        excluded = self.scoring_engine.apply_volatile_filter(scores, liq_scores)
        if not excluded:
            return scores

        for symbol in excluded:
            if symbol in quality_by_symbol:
                quality_by_symbol[symbol].eligible = False
                quality_by_symbol[symbol].reason_flags.append(
                    ReasonFlag.LOW_LIQ_IN_VOLATILE
                )
        logger.warning(
            "Excluded %s symbols from %s due to volatile liquidity filter",
            len(excluded),
            timeframe,
        )
        return [score for score in scores if score.symbol not in excluded]

    async def _fallback_for_systemic_outage(
        self,
        ctx: PipelineRunContext,
        regime: GlobalRegime,
        state: TimeframeProcessingState,
    ) -> PipelineResult | None:
        """Fallback when senior timeframe outage is detected."""
        if not self.universe_manager.check_systemic_outage(
            state.eligible_counts,
            state.total_symbols,
        ):
            return None

        return await self.steps.handle_fallback(
            ctx.ts_version,
            ctx.ts_eval,
            regime,
            ctx.config_hash,
            "SYSTEMIC_SENIOR_OUTAGE",
            state.eligible_counts,
            ctx.start_time,
        )

    def _handle_lock_timeout(
        self,
        ctx: PipelineRunContext,
        exc: LockTimeoutError,
    ) -> PipelineResult:
        """Record and return lock-timeout failure."""
        execution_time = ctx.elapsed(time.time())
        self.monitoring.record_error("LOCK_TIMEOUT", str(exc))
        self.monitoring.record_pipeline_metrics(
            ts_version=ctx.ts_version,
            ts_eval=ctx.ts_eval,
            success=False,
            status=UniverseStatus.FAILED.value,
            universe_size=0,
            execution_time_seconds=execution_time,
            error_message=str(exc),
            reason_flags=["LOCK_TIMEOUT"],
        )
        return self._build_failure_result(
            ctx,
            error_message=str(exc),
            execution_time_seconds=execution_time,
        )

    async def _handle_unexpected_exception(
        self,
        ctx: PipelineRunContext,
        exc: Exception,
    ) -> PipelineResult:
        """Rollback and record generic pipeline failure."""
        logger.exception("Pipeline failed: %s", exc)
        await self.session.rollback()
        execution_time = ctx.elapsed(time.time())
        self.monitoring.record_pipeline_metrics(
            ts_version=0,
            ts_eval=0,
            success=False,
            status=UniverseStatus.FAILED.value,
            universe_size=0,
            execution_time_seconds=execution_time,
            error_message=str(exc),
            reason_flags=["EXCEPTION"],
        )
        return self._build_failure_result(
            ctx,
            error_message=str(exc),
            execution_time_seconds=execution_time,
        )

    def _build_failure_result(
        self,
        ctx: PipelineRunContext,
        error_message: str,
        reason_flags: list[ReasonFlag] | None = None,
        execution_time_seconds: float = 0.0,
    ) -> PipelineResult:
        """Build a standard failed pipeline result."""
        return PipelineResult(
            success=False,
            ts_version=ctx.ts_version,
            ts_eval=ctx.ts_eval,
            universe_size=0,
            status=UniverseStatus.FAILED,
            error_message=error_message,
            reason_flags=reason_flags or [],
            execution_time_seconds=execution_time_seconds,
            config_hash=ctx.config_hash,
        )
