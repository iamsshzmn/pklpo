from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.candles.domain.repair import (
    LastNClosedBarsOutcome,
    RepairWindow,
    sanitize_repair_candle,
    validate_repair_candles,
)
from src.candles.domain.repair_timeframes import (
    build_last_n_closed_window,
    list_expected_timestamps,
    merge_adjacent_timestamps,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from src.core.run_context import RunContext

    from .ports import (
        CandleCoverageQueryPort,
        HistoricalCandleSourcePort,
        RepairCandleStorePort,
    )


class GuaranteeLastClosedBarsUseCase:
    def __init__(
        self,
        *,
        coverage_query: CandleCoverageQueryPort,
        historical_source: HistoricalCandleSourcePort,
        repair_store: RepairCandleStorePort,
        run_context: RunContext,
        bars: int,
        week_anchor_ts_ms: int,
        calendar: OKXCandleCalendar,
    ) -> None:
        self._coverage_query = coverage_query
        self._historical_source = historical_source
        self._repair_store = repair_store
        self._run_context = run_context
        self._bars = bars
        self._week_anchor_ts_ms = week_anchor_ts_ms
        self._calendar = calendar

    async def run(
        self,
        symbol: str,
        tf: str,
        now_ts_ms: int,
    ) -> LastNClosedBarsOutcome:
        state = await self._detect(symbol=symbol, tf=tf, now_ts_ms=now_ts_ms)
        if not state["unresolved"]:
            return self._build_outcome("ok", [], None, state["corrupted"], 0)
        repaired = await self._apply(symbol=symbol, tf=tf, state=state)
        unresolved = await self._verify(symbol=symbol, tf=tf, state=state)
        status = self._resolve_status(before=state["unresolved"], after=unresolved)
        recalc_range = self._build_recalc_range(
            status=status,
            repaired_timestamps=state["unresolved"][:repaired],
            closed_until=state["closed_until"],
        )
        return self._build_outcome(
            status,
            unresolved,
            recalc_range,
            state["corrupted"],
            repaired,
        )

    async def _detect(self, *, symbol: str, tf: str, now_ts_ms: int) -> dict[str, Any]:
        window_start, closed_until = build_last_n_closed_window(
            now_ts_ms, tf, self._bars, self._week_anchor_ts_ms, calendar=self._calendar
        )
        expected = list_expected_timestamps(
            window_start, closed_until, tf, calendar=self._calendar
        )
        valid = await self._coverage_query.list_existing_valid_timestamps(
            symbol=symbol,
            timeframe=tf,
            start_ts_ms=window_start,
            end_ts_ms=closed_until,
        )
        corrupted = await self._coverage_query.list_corrupted_timestamps(
            symbol=symbol,
            timeframe=tf,
            start_ts_ms=window_start,
            end_ts_ms=closed_until,
        )
        unresolved = self._merge_unresolved(expected, valid, corrupted)
        return {
            "closed_until": closed_until,
            "corrupted": len(corrupted),
            "ranges": merge_adjacent_timestamps(
                unresolved, tf, self._week_anchor_ts_ms, calendar=self._calendar
            ),
            "unresolved": unresolved,
        }

    async def _apply(self, *, symbol: str, tf: str, state: dict[str, Any]) -> int:
        repaired = 0
        for gap_range in state["ranges"]:
            candles = await self._historical_source.fetch_range(
                symbol=symbol,
                timeframe=tf,
                start_ts_ms=gap_range.start_ts_ms,
                end_ts_ms=gap_range.end_ts_ms,
            )
            validated = self._sanitize(
                candles,
                window=RepairWindow(gap_range.start_ts_ms, gap_range.end_ts_ms),
                closed_until=state["closed_until"],
            )
            repaired += await self._repair_store.selective_upsert_candles(
                symbol=symbol,
                timeframe=tf,
                candles=validated,
            )
        return repaired

    async def _verify(
        self, *, symbol: str, tf: str, state: dict[str, Any]
    ) -> list[int]:
        valid = await self._coverage_query.list_existing_valid_timestamps(
            symbol=symbol,
            timeframe=tf,
            start_ts_ms=state["ranges"][0].start_ts_ms,
            end_ts_ms=state["closed_until"],
        )
        corrupted = await self._coverage_query.list_corrupted_timestamps(
            symbol=symbol,
            timeframe=tf,
            start_ts_ms=state["ranges"][0].start_ts_ms,
            end_ts_ms=state["closed_until"],
        )
        expected = list_expected_timestamps(
            state["ranges"][0].start_ts_ms,
            state["closed_until"],
            tf,
            calendar=self._calendar,
        )
        return self._merge_unresolved(expected, valid, corrupted)

    def _sanitize(
        self,
        candles: Sequence[Mapping[str, Any]],
        *,
        window: RepairWindow,
        closed_until: int,
    ) -> list[dict[str, Any]]:
        valid = validate_repair_candles(
            candles=candles,
            task_window=window,
            closed_until_ts_ms=closed_until,
        )
        fetched_at = datetime.now(UTC)
        return [sanitize_repair_candle(row, fetched_at=fetched_at) for row in valid]

    def _merge_unresolved(
        self,
        expected: list[int],
        valid: list[int],
        corrupted: list[int],
    ) -> list[int]:
        return sorted((set(expected) - set(valid)) | set(corrupted))

    def _resolve_status(self, *, before: list[int], after: list[int]) -> str:
        if not after:
            return "ok"
        if len(after) == len(before):
            return "blocked"
        return "partial"

    def _build_recalc_range(
        self,
        *,
        status: str,
        repaired_timestamps: list[int],
        closed_until: int,
    ) -> tuple[int, int] | None:
        if status != "ok" or not repaired_timestamps:
            return None
        return min(repaired_timestamps), closed_until

    def _build_outcome(
        self,
        status: str,
        unresolved: list[int],
        recalc_range: tuple[int, int] | None,
        corrupted_count: int,
        repaired_count: int,
    ) -> LastNClosedBarsOutcome:
        return LastNClosedBarsOutcome(
            status=status,  # type: ignore[arg-type]
            unresolved_timestamps=unresolved,
            affected_recalc_range=recalc_range,
            corrupted_count=corrupted_count,
            repaired_count=repaired_count,
            run_id=self._run_context.run_id,
            algo_version=self._run_context.algo_version,
            params_hash=self._run_context.params_hash,
        )
