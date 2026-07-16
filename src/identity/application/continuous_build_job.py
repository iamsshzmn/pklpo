"""Continuous OHLCV sparse materialization for composite series."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from src.identity.observability import ContinuousBuildObserver

if TYPE_CHECKING:
    from datetime import datetime

    from src.identity.domain import IdentitySnapshot, SeriesMemberRow


@dataclass(frozen=True)
class RawOhlcvBar:
    source_venue: str
    source_symbol: str
    timeframe: str
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class ContinuousBuildContext:
    run_id: str
    algo_version: str
    params_hash: str
    snapshot_id: str | None = None


@dataclass(frozen=True)
class ContinuousOhlcvRow:
    series_id: str
    timeframe: str
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source_venue: str
    source_symbol: str
    source_timestamp: int
    segment_id: str
    succession_id: str | None
    adjustment_factor: Decimal
    bar_kind: str
    data_status: str
    run_id: str
    algo_version: str
    params_hash: str
    snapshot_id: str | None


@dataclass(frozen=True)
class SeriesSegmentRow:
    series_id: str
    timeframe: str
    segment_id: str
    source_venue: str
    source_symbol: str
    segment_start_ts: int
    segment_end_ts: int | None
    segment_order: int
    reset_features_from_here: bool


@dataclass(frozen=True)
class ContinuousSnapshot:
    rows: list[ContinuousOhlcvRow]
    segments: list[SeriesSegmentRow]


@dataclass(frozen=True)
class ContinuousBuildResult:
    run_id: str
    row_count: int
    segment_count: int
    gap_count: int


class ContinuousIdentityRepository(Protocol):
    async def load_snapshot(self, as_of: datetime) -> IdentitySnapshot:
        """Load the PIT identity snapshot to materialize."""


class ContinuousRawRepository(Protocol):
    async def load_bars(self, members: list[SeriesMemberRow]) -> list[RawOhlcvBar]:
        """Load raw OHLCV bars needed by the composite members."""


class ContinuousPublisher(Protocol):
    async def publish_snapshot(
        self,
        snapshot: ContinuousSnapshot,
        context: ContinuousBuildContext,
        *,
        gap_count: int = 0,
    ) -> None:
        """Persist a continuous snapshot atomically."""

    async def record_failure(
        self, context: ContinuousBuildContext, error_type: str, error_hash: str
    ) -> None:
        """Persist failed continuous-build audit metadata (§17.4)."""


class ContinuousBuildJob:
    def __init__(
        self,
        *,
        identity_repository: ContinuousIdentityRepository,
        raw_repository: ContinuousRawRepository,
        publisher: ContinuousPublisher,
        observer: ContinuousBuildObserver | None = None,
    ) -> None:
        self._identity_repository = identity_repository
        self._raw_repository = raw_repository
        self._publisher = publisher
        self._observer = observer or ContinuousBuildObserver()

    async def run(
        self,
        *,
        as_of: datetime,
        run_id: str,
        algo_version: str,
        params_hash: str,
        snapshot_id: str | None = None,
    ) -> ContinuousBuildResult:
        started = self._observer.start(run_id=run_id, as_of=as_of)
        context = ContinuousBuildContext(
            run_id=run_id,
            algo_version=algo_version,
            params_hash=params_hash,
            snapshot_id=snapshot_id,
        )
        try:
            identity_snapshot = await self._identity_repository.load_snapshot(as_of)
            members = [
                member
                for member in identity_snapshot.members
                if any(
                    registry.series_id == member.series_id
                    and registry.series_kind == "composite"
                    for registry in identity_snapshot.registry
                )
            ]
            raw_bars = await self._raw_repository.load_bars(members)
            continuous_snapshot = build_continuous_snapshot(
                identity_snapshot, raw_bars, context=context
            )
            gap_count = len(
                [
                    gap
                    for gap in identity_snapshot.gap_ranges
                    if any(member.series_id == gap.series_id for member in members)
                ]
            )
            await self._publisher.publish_snapshot(
                continuous_snapshot, context, gap_count=gap_count
            )
            result = ContinuousBuildResult(
                run_id=run_id,
                row_count=len(continuous_snapshot.rows),
                segment_count=len(continuous_snapshot.segments),
                gap_count=gap_count,
            )
            self._observer.success(
                run_id=run_id,
                started=started,
                rows_written=result.row_count,
                segment_count=result.segment_count,
                gap_count=result.gap_count,
            )
            return result
        except Exception as exc:
            error_hash = self._observer.failure(run_id=run_id, started=started, exc=exc)
            record_failure = getattr(self._publisher, "record_failure", None)
            if record_failure is not None:
                await record_failure(context, type(exc).__name__, error_hash)
            raise


def build_continuous_snapshot(
    identity_snapshot: IdentitySnapshot,
    raw_bars: list[RawOhlcvBar],
    *,
    context: ContinuousBuildContext,
) -> ContinuousSnapshot:
    composite_series = {
        row.series_id
        for row in identity_snapshot.registry
        if row.series_kind == "composite" and row.status == "active"
    }
    members = [
        member
        for member in identity_snapshot.members
        if member.series_id in composite_series
    ]
    bars_by_source = {
        (bar.source_venue, bar.source_symbol, bar.timeframe, bar.timestamp): bar
        for bar in raw_bars
    }

    rows_by_key: dict[tuple[str, str, int], ContinuousOhlcvRow] = {}
    segments: list[SeriesSegmentRow] = []

    for segment_order, member in enumerate(
        sorted(members, key=lambda item: (item.series_id, item.valid_from)), start=1
    ):
        member_bars = _bars_for_member(member, bars_by_source.values())
        for timeframe in sorted({bar.timeframe for bar in member_bars}):
            segment_id = _segment_id(member.series_id, timeframe, segment_order)
            segment_bars = [bar for bar in member_bars if bar.timeframe == timeframe]
            if segment_bars:
                segments.append(
                    SeriesSegmentRow(
                        series_id=member.series_id,
                        timeframe=timeframe,
                        segment_id=segment_id,
                        source_venue=member.source_venue,
                        source_symbol=member.source_symbol,
                        segment_start_ts=min(bar.timestamp for bar in segment_bars),
                        segment_end_ts=member.valid_to,
                        segment_order=segment_order,
                        reset_features_from_here=True,
                    )
                )
            for bar in segment_bars:
                key = (member.series_id, bar.timeframe, bar.timestamp)
                rows_by_key[key] = _continuous_row(member, bar, segment_id, context)

    return ContinuousSnapshot(
        rows=[
            rows_by_key[key]
            for key in sorted(rows_by_key, key=lambda item: (item[0], item[1], item[2]))
        ],
        segments=segments,
    )


def _bars_for_member(
    member: SeriesMemberRow, bars: list[RawOhlcvBar] | object
) -> list[RawOhlcvBar]:
    return [
        bar
        for bar in bars
        if bar.source_venue == member.source_venue
        and bar.source_symbol == member.source_symbol
        and bar.timestamp + timeframe_duration_ms(bar.timeframe) > member.valid_from
        and (member.valid_to is None or bar.timestamp < member.valid_to)
    ]


def _continuous_row(
    member: SeriesMemberRow,
    bar: RawOhlcvBar,
    segment_id: str,
    context: ContinuousBuildContext,
) -> ContinuousOhlcvRow:
    return ContinuousOhlcvRow(
        series_id=member.series_id,
        timeframe=bar.timeframe,
        timestamp=bar.timestamp,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        source_venue=bar.source_venue,
        source_symbol=bar.source_symbol,
        source_timestamp=bar.timestamp,
        segment_id=segment_id,
        succession_id=member.succession_id,
        adjustment_factor=Decimal(str(member.adjustment_factor)),
        bar_kind="native",
        data_status="complete",
        run_id=context.run_id,
        algo_version=context.algo_version,
        params_hash=context.params_hash,
        snapshot_id=context.snapshot_id,
    )


def _segment_id(series_id: str, timeframe: str, segment_order: int) -> str:
    return f"{series_id}:{timeframe}:{segment_order:04d}"


def timeframe_duration_ms(timeframe: str) -> int:
    durations = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "30m": 1_800_000,
        "1H": 3_600_000,
        "4H": 14_400_000,
        "12H": 43_200_000,
        "1D": 86_400_000,
        "1W": 604_800_000,
        "1M": 2_678_400_000,
    }
    try:
        return durations[timeframe]
    except KeyError as exc:
        raise ValueError(f"unsupported timeframe: {timeframe}") from exc
