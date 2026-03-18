"""Reusable step executor for market selection pipeline."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeVar

import pandas as pd

from ..config import MarketSelectionConfig
from ..domain.metrics import PairMetricsCalculator
from ..domain.quality_gate import DataQualityGate, QualityResult, ReasonFlag
from ..domain.regime import GlobalRegime, RegimeClassifier, RegimeType, TFRegime
from ..domain.universe import (
    UniverseEntry,
    UniverseManager,
    UniverseStatus,
    UniverseVersion,
)
from ..ports import MarketSelectionDBPort, MonitoringPort, PersistencePort
from .models import PipelineResult, PipelineRunContext, TimeframeProcessingState

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PipelineStepExecutor:
    """Encapsulates IO-heavy pipeline steps to keep orchestration compact."""

    def __init__(
        self,
        session: AsyncSession,
        config: MarketSelectionConfig,
        db: MarketSelectionDBPort,
        persistence: PersistencePort,
        monitoring: MonitoringPort,
        quality_gate: DataQualityGate,
        metrics_calc: PairMetricsCalculator,
        regime_classifier: RegimeClassifier,
        universe_manager: UniverseManager,
        write_lock_timeout_ms: int,
    ) -> None:
        self.session = session
        self.config = config
        self.db = db
        self.persistence = persistence
        self.monitoring = monitoring
        self.quality_gate = quality_gate
        self.metrics_calc = metrics_calc
        self.regime_classifier = regime_classifier
        self.universe_manager = universe_manager
        self.write_lock_timeout_ms = write_lock_timeout_ms

    async def run_write_stage(
        self,
        ts_version: int,
        callback: Callable[[], Awaitable[T]],
    ) -> T:
        """Execute write-stage in a short transaction with advisory lock."""
        if self.session.in_transaction():
            await self.session.commit()

        async with self.session.begin():
            await self.persistence.acquire_write_lock_for_ts_version(
                ts_version=ts_version,
                lock_timeout_ms=self.write_lock_timeout_ms,
            )
            return await callback()

    async def compute_regime(self, ts_eval: int) -> GlobalRegime:
        """Compute global market regime."""
        basket_tf = self.config.regime.basket_volume_tf
        volume_data = await self.db.fetch_basket_volume_data(
            basket_tf, ts_eval, self.config.regime.basket_volume_window_days
        )
        basket_symbols = self.regime_classifier.select_basket(volume_data)

        tf_data: dict[str, pd.DataFrame] = {}
        atr_percentiles: dict[str, float] = {}
        for tf in self.config.regime_tfs:
            tf_data[tf] = await self.db.fetch_regime_metrics(tf, ts_eval, basket_symbols)
            atr_percentiles[tf] = await self.db.fetch_atr_percentile(
                tf,
                ts_eval,
                self.config.regime.atr_volatile_percentile,
            )

        return self.regime_classifier.compute_global_regime(
            basket_symbols,
            tf_data,
            atr_percentiles,
        )

    async def check_and_fix_stale_regime(
        self,
        regime: GlobalRegime,
        ts_eval: int,
    ) -> GlobalRegime:
        """Reuse last valid regime if senior TF inputs are stale."""
        stale_tfs, _ = await self._find_stale_regime_tfs(ts_eval)
        if not stale_tfs:
            return regime

        last_valid = await self.db.get_last_valid_regime()
        if not last_valid:
            regime.stale = True
            return regime

        return self._rebuild_regime_from_history(last_valid)

    async def compute_quality_gate(
        self,
        timeframe: str,
        ts_eval: int,
    ) -> list[QualityResult]:
        """Compute quality gate for all symbols in a timeframe."""
        quality_df = await self.db.fetch_quality_data(timeframe, ts_eval)
        if quality_df.empty:
            return []

        expected_bars = self.quality_gate.calculate_expected_bars(
            timeframe,
            self.config.windows_days.get(timeframe, 30),
        )

        results = []
        for _, row in quality_df.iterrows():
            data_lag_seconds = int((ts_eval - row["max_ts"]) / 1000) if row["max_ts"] else 999999
            results.append(
                self.quality_gate.evaluate(
                    symbol=row["symbol"],
                    timeframe=timeframe,
                    valid_bars=int(row["valid_bars"]),
                    expected_bars=expected_bars,
                    gaps_count=int(row["gaps_count"]),
                    data_lag_seconds=data_lag_seconds,
                    volume_present=bool(row["has_volume"]),
                    feature_bars=int(row["feature_bars"]),
                )
            )
        return results

    async def compute_pair_metrics(
        self,
        timeframe: str,
        ts_eval: int,
        eligible_symbols: list[str],
    ) -> pd.DataFrame:
        """Compute pair metrics for eligible symbols."""
        data_df = await self.db.fetch_pair_metrics_data(timeframe, ts_eval)
        if data_df.empty:
            return pd.DataFrame()

        filtered_df = data_df[data_df["symbol"].isin(eligible_symbols)]
        if filtered_df.empty:
            return pd.DataFrame()

        expected_bars = self.quality_gate.calculate_expected_bars(
            timeframe,
            self.config.windows_days.get(timeframe, 30),
        )

        results = []
        for symbol, group_df in filtered_df.groupby("symbol"):
            metrics = self.metrics_calc.calculate_all(
                group_df,
                str(symbol),
                timeframe,
                expected_bars,
            )
            results.append(metrics.to_dict())

        return pd.DataFrame(results)

    async def handle_fallback(
        self,
        ts_version: int,
        ts_eval: int,
        regime: GlobalRegime,
        config_hash: str,
        fallback_reason: str,
        eligible_counts: dict[str, int],
        start_time: float,
    ) -> PipelineResult:
        """Copy the previous published universe into a fallback version."""
        source_version = await self.db.get_last_published_version()
        if source_version is None:
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

        version = UniverseVersion(
            ts_version=ts_version,
            ts_eval=ts_eval,
            status=UniverseStatus.FALLBACK_PREV,
            universe_size=0,
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
            nonlocal copy_metrics
            await self.persistence.insert_universe_version(version)
            copy_metrics = await self.persistence.copy_previous_universe_with_metrics(
                ts_version,
                source_version,
                config_hash,
            )
            await self.persistence.update_version_status(
                ts_version,
                UniverseStatus.FALLBACK_PREV.value,
                notes=self._build_fallback_notes(copy_metrics, source_version),
            )

        await self.run_write_stage(ts_version, _fallback_write_stage)
        return PipelineResult(
            success=True,
            ts_version=ts_version,
            ts_eval=ts_eval,
            universe_size=copy_metrics["inserted_count"],
            status=UniverseStatus.FALLBACK_PREV,
            global_regime=regime.regime,
            eligible_counts=eligible_counts,
            execution_time_seconds=time.time() - start_time,
            reason_flags=[ReasonFlag.UNIVERSE_FALLBACK_PREV],
            config_hash=config_hash,
        )

    async def select_universe(
        self,
        final_scores: list,
        regime: GlobalRegime,
    ) -> tuple[list[UniverseEntry], list[ReasonFlag]]:
        """Select top-N universe from final scores and history."""
        previous_universe = await self.db.fetch_previous_universe()
        score_history = await self.db.fetch_score_history(
            [score.symbol for score in final_scores],
            days=30,
        )
        return self.universe_manager.select_universe(
            final_scores=final_scores,
            score_history=score_history,
            previous_universe=previous_universe,
            regime=regime,
            whitelist=set(self.config.universe.whitelist),
            blacklist=set(self.config.universe.blacklist),
        )

    async def publish_success(
        self,
        ctx: PipelineRunContext,
        regime: GlobalRegime,
        state: TimeframeProcessingState,
        universe: list[UniverseEntry],
        global_flags: list[ReasonFlag],
    ) -> PipelineResult:
        """Publish selected universe and record success metrics."""
        execution_time = ctx.elapsed(time.time())
        version = self.universe_manager.create_version(
            ts_version=ctx.ts_version,
            ts_eval=ctx.ts_eval,
            universe=universe,
            eligible_counts=state.eligible_counts,
            regime=regime,
            config_hash=ctx.config_hash,
            execution_time=execution_time,
        )

        async def _publish_write_stage() -> None:
            await self.persistence.insert_universe_version(version)
            await self.persistence.insert_universe_entries(
                ctx.ts_version,
                universe,
                ctx.config_hash,
            )
            await self.persistence.update_version_status(
                ctx.ts_version,
                UniverseStatus.PUBLISHED.value,
            )

        await self.run_write_stage(ctx.ts_version, _publish_write_stage)
        self.monitoring.record_pipeline_metrics(
            ts_version=ctx.ts_version,
            ts_eval=ctx.ts_eval,
            success=True,
            status=UniverseStatus.PUBLISHED.value,
            universe_size=len(universe),
            execution_time_seconds=execution_time,
            global_regime=regime.regime.value,
            regime_strength=regime.strength,
            regime_stale=regime.stale,
            eligible_counts=state.eligible_counts,
            total_symbols=state.total_symbols,
            reason_flags=[flag.value for flag in global_flags],
        )
        return PipelineResult(
            success=True,
            ts_version=ctx.ts_version,
            ts_eval=ctx.ts_eval,
            universe_size=len(universe),
            status=UniverseStatus.PUBLISHED,
            global_regime=regime.regime,
            eligible_counts=state.eligible_counts,
            total_symbols=state.total_symbols,
            execution_time_seconds=execution_time,
            reason_flags=global_flags,
            config_hash=ctx.config_hash,
        )

    async def _find_stale_regime_tfs(self, ts_eval: int) -> tuple[list[str], int]:
        """Return stale regime timeframes and max lag in seconds."""
        stale_tfs: list[str] = []
        max_lag_seconds = 0
        for tf in self.config.regime_tfs:
            lag_seconds = await self.db.check_regime_tf_lag(tf, ts_eval)
            threshold_seconds = self.config.regime.regime_lag_max_minutes.get(tf, 1440) * 60
            if lag_seconds > threshold_seconds:
                stale_tfs.append(tf)
                max_lag_seconds = max(max_lag_seconds, lag_seconds)
        return stale_tfs, max_lag_seconds

    def _rebuild_regime_from_history(self, last_valid: dict) -> GlobalRegime:
        """Reconstruct a stale regime snapshot from persisted history."""
        tf_regimes = {
            tf: TFRegime(
                timeframe=tf,
                regime=self._parse_regime_type(last_valid.get(f"regime_{tf.lower()}")),
                strength=last_valid.get(f"regime_{tf.lower()}_strength", 0.5),
                adx_median=0.0,
                atr_close_ratio=0.0,
                ema_slope=0.0,
            )
            for tf in self.config.regime_tfs
        }
        return GlobalRegime(
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

    def _parse_regime_type(self, value: str | None) -> RegimeType:
        """Parse persisted regime type with RANGE fallback."""
        if value is None:
            return RegimeType.RANGE
        try:
            return RegimeType(value)
        except ValueError:
            return RegimeType.RANGE

    def _build_fallback_notes(
        self,
        copy_metrics: dict[str, int],
        source_version: int,
    ) -> str:
        """Format fallback copy stats for version notes."""
        return (
            f"Copied {copy_metrics['inserted_count']} symbols from {source_version}; "
            f"source={copy_metrics['source_count']} "
            f"skipped={copy_metrics['skipped_conflicts']} "
            f"source_duplicates={copy_metrics['source_duplicates']}"
        )
