from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.candles.application.coverage_gate import evaluate_ohlcv_coverage
from src.features.ports.recalc import RecalcOutcome

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd

    from src.core.run_context import RunContext


def _timeframe_to_seconds(timeframe: str) -> int:
    from src.features.domain.timeframe import timeframe_to_seconds

    return timeframe_to_seconds(timeframe)


def _build_fetch_limit(
    start_ts_ms: int,
    end_ts_ms: int,
    tf_seconds: int,
    warmup_bars: int,
) -> int:
    target_span_ms = max(1, end_ts_ms - start_ts_ms)
    step_ms = tf_seconds * 1000
    target_bars = max(1, (target_span_ms + step_ms - 1) // step_ms)
    return int(target_bars + warmup_bars)


def _filter_target_range(
    df: pd.DataFrame,
    *,
    start_ts_ms: int,
    end_ts_ms: int,
) -> pd.DataFrame:
    mask = (df["ts"] * 1000 >= start_ts_ms) & (df["ts"] * 1000 < end_ts_ms)
    return df.loc[mask].copy()


@dataclass(frozen=True)
class RecalcFeaturesInRange:
    fetch_ohlcv_df: Any
    save_features_df: Any
    compute_features_fn: Callable[[pd.DataFrame, list[str]], pd.DataFrame]
    specs: list[str]
    warmup_bars: int = 500

    async def recalc_in_range(
        self,
        *,
        symbol: str,
        tf: str,
        start_ts_ms: int,
        end_ts_ms: int,
        run_context: RunContext,
    ) -> RecalcOutcome:
        tf_seconds = _timeframe_to_seconds(tf)
        source = await self.fetch_ohlcv_df(
            symbol=symbol,
            timeframe=tf,
            since_ts=max(0, start_ts_ms // 1000 - (self.warmup_bars * tf_seconds)),
            until_ts=end_ts_ms,
            limit=_build_fetch_limit(
                start_ts_ms,
                end_ts_ms,
                tf_seconds,
                self.warmup_bars,
            ),
        )
        if source is None or len(source) == 0:
            return self._build_outcome(0, run_context)
        coverage = evaluate_ohlcv_coverage(
            timestamps_ms=[int(ts * 1000) for ts in source["ts"].tolist()],
            timeframe=tf,
            required_bars=self.warmup_bars,
            end_ts_ms=end_ts_ms,
        )
        if not coverage.passed:
            return self._build_outcome(0, run_context)
        calculated = self.compute_features_fn(source.copy(), self.specs)
        target = _filter_target_range(
            calculated,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )
        if len(target) == 0:
            return self._build_outcome(0, run_context)
        rows_written = await self.save_features_df(target, symbol, tf)
        return self._build_outcome(rows_written, run_context)

    async def run(
        self,
        symbol: str,
        tf: str,
        start_ts_ms: int,
        end_ts_ms: int,
        run_context: RunContext,
    ) -> RecalcOutcome:
        return await self.recalc_in_range(
            symbol=symbol,
            tf=tf,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            run_context=run_context,
        )

    def _build_outcome(
        self,
        rows_written: int,
        run_context: RunContext,
    ) -> RecalcOutcome:
        return RecalcOutcome(
            rows_written=rows_written,
            run_id=run_context.run_id,
            algo_version=run_context.algo_version,
            params_hash=run_context.params_hash,
        )
