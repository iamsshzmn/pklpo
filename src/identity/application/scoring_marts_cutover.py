"""Cutover seam: scoring/market_selection/backtest/recommender/labels ->
series-keyed facade reads (§12.12 п.10-11), scoped to `ton_gram` per the
consumer/writer cutover matrix (`consumer_writer_cutover_matrix_2026-07-02.md`,
phase 5.4 rows: market selection freshness/quality/pair-metrics/regime-lag,
scoring engine close lookup, trade recommender, backtest, CLI train/label).

Task 5.3 already gave feature computation a facade-backed read seam
(`fetch_feature_bars_via_facade`). None of this task's eight remaining
consumers need a different read mechanism — each needs targeted glue on top
of the *same* facade / eligibility / execution-resolver primitives already
built in Tasks 4.2, 4.4, 5.1, 5.2, 5.3, addressing the specific risk called
out in its own matrix row:

- market selection freshness/regime lag (rows 1, 4): a shared, table-wide
  `eval_ts` (`RESOLVE_TS_EVAL_SQL`) must not be trusted for `ton_gram`
  unless `ton_gram`'s own segment is `can_score`-eligible AND has bars
  covering that `eval_ts` — otherwise scoring readiness can pass on raw
  candle presence while the post-gap feature warmup contract (Task 5.2) is
  not actually satisfied.
- market selection quality (row 2): an inter-bar gap must be checked against
  `core.series_gap_ranges` before being treated as a liquidity defect — an
  approved migration halt is not a data quality problem.
- market selection pair metrics / scoring engine close lookup (rows 3, 5):
  both want a single point-in-time OHLCV value keyed by `series_id`, not raw
  `symbol` — built directly on Task 5.3's `FeatureBar` sequence.
- trade recommender (row 6): reuses Task 4.4's `ExecutionResolver` verbatim
  — that resolver already *is* the "historical identity stays the TON
  series_id, current tradeable symbol resolves separately" decoupling this
  row calls for.
- backtest (row 7): a thin facade-backed provider — "rejects legacy ohlcv
  for composite" is not new logic, it falls out of `OhlcvFacade` never
  having a code path to the legacy `ohlcv` table at all.
- CLI train/label (row 8): a forward-looking, segment-aware label function —
  the label mirror of Task 5.1's `returns_no_cross_gap` (which is backward-
  looking) — a label must never be built by peeking across a segment
  boundary into the next segment's first bar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from src.identity.application.feature_cutover import (
    FeatureBar,
    fetch_feature_bars_via_facade,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from src.identity.application.feature_reset_policy import SegmentedBar
    from src.identity.application.ohlcv_facade import OhlcvFacade
    from src.identity.application.segment_eligibility import SegmentEligibilityVerdict
    from src.identity.application.shadow_mode_compare import GapWindow

# --- Market selection: freshness / regime-lag readiness (matrix rows 1, 4) ---


def series_is_ready_for_eval(
    *,
    verdict: SegmentEligibilityVerdict,
    eval_ts: int,
    last_bar_ts: int | None,
) -> bool:
    """Is this series/segment safe to include in a market-selection run whose
    shared `eval_ts` was computed globally (`RESOLVE_TS_EVAL_SQL`, table-wide
    `MIN(raw max, indicator max)`)?

    Fails closed: `can_score=False` (segment warmup not satisfied, partial
    event bucket, disabled/context-only timeframe — see Task 5.2) always
    means "not ready", regardless of how fresh the raw candle looks. A
    series whose own last available bar has not yet caught up to the shared
    `eval_ts` is also "not ready" — evaluating it now would score against a
    stale/incomplete bar for that series even while other series in the same
    run are current.
    """
    if not verdict.can_score:
        return False
    return not (last_bar_ts is None or last_bar_ts < eval_ts)


# --- Market selection: quality gap classification (matrix row 2) ---

GapQualityVerdict = Literal["approved_migration_gap", "unclassified_quality_gap"]


def classify_liquidity_gap(
    *,
    prev_bar_ts: int,
    curr_bar_ts: int,
    known_gaps: Sequence[GapWindow],
) -> GapQualityVerdict:
    """An inter-bar gap `(prev_bar_ts, curr_bar_ts)` observed by a
    quality/liquidity check must be checked against `core.series_gap_ranges`
    before being treated as a data quality defect — an approved migration
    halt is a known, classified event, not evidence of poor liquidity.

    Fails closed: no covering known gap means `unclassified_quality_gap` —
    it still counts against quality. This must never default to "assume
    it's fine", or an unapproved/unclassified real outage would silently
    stop counting against the instrument's quality score.
    """
    for gap in known_gaps:
        if gap.gap_start_ts <= prev_bar_ts and curr_bar_ts <= gap.gap_end_ts:
            return "approved_migration_gap"
    return "unclassified_quality_gap"


# --- Market selection pair metrics / scoring engine close lookup (rows 3, 5) ---


def bar_at(bars: Sequence[FeatureBar], timestamp: int) -> FeatureBar | None:
    """Point-in-time OHLCV lookup over series_id-scoped bars (already
    facade-backed via `fetch_feature_bars_via_facade`), replacing a raw
    `symbol`-keyed close/volume lookup. Returns `None` rather than guessing
    the nearest bar — a caller needing the close/volume at an exact
    timestamp must not silently substitute an adjacent bar."""
    for bar in bars:
        if bar.timestamp == timestamp:
            return bar
    return None


# --- Trade recommender (matrix row 6) ---
#
# No new primitive needed here: `ExecutionResolver.resolve_execution_symbol`
# (Task 4.4, `src.identity.application.execution_resolver`) already is the
# "resolved separately from historical identity" service this row calls for
# — `ExecutionResolution.series_id` is always the canonical series_id,
# `ExecutionResolution.source_symbol` is the current tradeable leg. See
# `tests/identity/test_scoring_marts_cutover.py::
# test_recommender_uses_series_id_history_and_resolver_for_execution_symbol`
# for the integration-shaped proof, and the task report for the proposed
# `recommend.py` diff.


# --- Backtest data provider (matrix row 7) ---


class BacktestSeriesProvider:
    """Facade-backed OHLCV provider for backtest, accepting `series_id` and a
    PIT `as_of` (§12.12 п.10-11, matrix row 7). There is no code path here to
    the legacy `ohlcv` table `src.backtest.evaluate` currently reads —
    "rejects legacy ohlcv for composite" falls out of that by construction,
    not from an extra check bolted on afterward."""

    def __init__(self, facade: OhlcvFacade) -> None:
        self._facade = facade

    async def load_bars(
        self,
        *,
        series_id: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        as_of: datetime | None = None,
    ) -> list[FeatureBar]:
        return await fetch_feature_bars_via_facade(
            self._facade,
            series_id=series_id,
            timeframe=timeframe,
            start_ts=start_ts,
            end_ts=end_ts,
            as_of=as_of,
        )


# --- CLI train/label (matrix row 8) ---


def label_next_bar_direction_no_cross_segment(
    bars: Sequence[SegmentedBar],
) -> list[int | None]:
    """Binary next-bar-direction label (1=up, 0=down/flat) — the forward-
    looking mirror of Task 5.1's `returns_no_cross_gap`. `None` at the last
    bar of a segment: a label must never be built by peeking at the first
    bar of the *next* segment, or the succession/gap boundary would leak
    into training data disguised as an ordinary next-bar move."""
    results: list[int | None] = []
    for i, bar in enumerate(bars):
        if i == len(bars) - 1 or bars[i + 1].segment_id != bar.segment_id:
            results.append(None)
            continue
        results.append(1 if bars[i + 1].value > bar.value else 0)
    return results
