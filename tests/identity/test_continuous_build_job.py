from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def test_continuous_snapshot_materializes_composite_without_duplicate_timestamps() -> (
    None
):
    from src.identity.application.continuous_build_job import (
        ContinuousBuildContext,
        RawOhlcvBar,
        build_continuous_snapshot,
    )
    from src.identity.domain import (
        IdentitySnapshot,
        SeriesAliasRow,
        SeriesGapRangeRow,
        SeriesMemberRow,
        SeriesRegistryRow,
    )

    known_from = _ts("2026-07-03T00:00:00+00:00")
    snapshot = IdentitySnapshot(
        registry=[
            SeriesRegistryRow(
                series_id="TON-USDT-SWAP",
                series_label="ton_gram",
                asset_id=None,
                series_kind="composite",
                status="active",
                known_from=known_from,
            )
        ],
        members=[
            SeriesMemberRow(
                series_id="TON-USDT-SWAP",
                source_venue="OKX",
                source_symbol="TON-USDT-SWAP",
                valid_from=0,
                valid_to=2000,
                known_from=known_from,
                adjustment_factor=Decimal("1"),
                succession_id="OKX|SWAP|TON-USDT-SWAP|GRAM-USDT-SWAP",
            ),
            SeriesMemberRow(
                series_id="TON-USDT-SWAP",
                source_venue="OKX",
                source_symbol="GRAM-USDT-SWAP",
                valid_from=2000,
                valid_to=None,
                known_from=known_from,
                adjustment_factor=Decimal("1"),
                succession_id="OKX|SWAP|TON-USDT-SWAP|GRAM-USDT-SWAP",
            ),
        ],
        aliases=[
            SeriesAliasRow(
                old_series_id="GRAM-USDT-SWAP",
                canonical_series_id="TON-USDT-SWAP",
                known_from=known_from,
                reason="symbol_succession",
            )
        ],
        gap_ranges=[
            SeriesGapRangeRow(
                series_id="TON-USDT-SWAP",
                timeframe="1m",
                gap_start_ts=1000,
                gap_end_ts=2000,
                gap_type="migration_halt",
                recoverability="not_repairable_by_design",
                reason="event gap",
                known_from=known_from,
            )
        ],
    )
    raw_bars = [
        RawOhlcvBar(
            source_venue="OKX",
            source_symbol="TON-USDT-SWAP",
            timeframe="1m",
            timestamp=0,
            open=Decimal("1"),
            high=Decimal("2"),
            low=Decimal("0.5"),
            close=Decimal("1.5"),
            volume=Decimal("10"),
        ),
        RawOhlcvBar(
            source_venue="OKX",
            source_symbol="TON-USDT-SWAP",
            timeframe="1m",
            timestamp=2000,
            open=Decimal("9"),
            high=Decimal("9"),
            low=Decimal("9"),
            close=Decimal("9"),
            volume=Decimal("9"),
        ),
        RawOhlcvBar(
            source_venue="OKX",
            source_symbol="GRAM-USDT-SWAP",
            timeframe="1m",
            timestamp=2000,
            open=Decimal("1.6"),
            high=Decimal("1.8"),
            low=Decimal("1.4"),
            close=Decimal("1.7"),
            volume=Decimal("12"),
        ),
    ]

    continuous = build_continuous_snapshot(
        snapshot,
        raw_bars,
        context=ContinuousBuildContext(
            run_id="run-1",
            algo_version="test",
            params_hash="hash",
            snapshot_id="snapshot-1",
        ),
    )

    assert [(row.timestamp, row.source_symbol) for row in continuous.rows] == [
        (0, "TON-USDT-SWAP"),
        (2000, "GRAM-USDT-SWAP"),
    ]
    assert (
        len({(row.series_id, row.timeframe, row.timestamp) for row in continuous.rows})
        == 2
    )
    assert all(row.bar_kind == "native" for row in continuous.rows)
    assert all(row.data_status == "complete" for row in continuous.rows)
    assert {row.succession_id for row in continuous.rows} == {
        "OKX|SWAP|TON-USDT-SWAP|GRAM-USDT-SWAP"
    }
    assert [(row.source_symbol, row.segment_order) for row in continuous.segments] == [
        ("TON-USDT-SWAP", 1),
        ("GRAM-USDT-SWAP", 2),
    ]


def test_continuous_build_job_publishes_snapshot() -> None:
    import asyncio

    from src.identity.application.continuous_build_job import (
        ContinuousBuildJob,
        RawOhlcvBar,
    )
    from src.identity.domain import (
        IdentitySnapshot,
        SeriesMemberRow,
        SeriesRegistryRow,
    )

    known_from = _ts("2026-07-03T00:00:00+00:00")
    identity_snapshot = IdentitySnapshot(
        registry=[
            SeriesRegistryRow(
                series_id="TON-USDT-SWAP",
                series_label="ton_gram",
                asset_id=None,
                series_kind="composite",
                status="active",
                known_from=known_from,
            )
        ],
        members=[
            SeriesMemberRow(
                series_id="TON-USDT-SWAP",
                source_venue="OKX",
                source_symbol="TON-USDT-SWAP",
                valid_from=0,
                valid_to=1000,
                known_from=known_from,
                adjustment_factor=Decimal("1"),
                succession_id="lineage",
            )
        ],
        aliases=[],
        gap_ranges=[],
    )

    class _IdentityRepository:
        async def load_snapshot(self, as_of):
            return identity_snapshot

    class _RawRepository:
        async def load_bars(self, members):
            assert [member.source_symbol for member in members] == ["TON-USDT-SWAP"]
            return [
                RawOhlcvBar(
                    source_venue="OKX",
                    source_symbol="TON-USDT-SWAP",
                    timeframe="1m",
                    timestamp=0,
                    open=Decimal("1"),
                    high=Decimal("1"),
                    low=Decimal("1"),
                    close=Decimal("1"),
                    volume=Decimal("1"),
                )
            ]

    class _Publisher:
        def __init__(self) -> None:
            self.published = []

        async def publish_snapshot(self, snapshot, context, *, gap_count=0):
            self.published.append((snapshot, context, gap_count))

    publisher = _Publisher()

    result = asyncio.run(
        ContinuousBuildJob(
            identity_repository=_IdentityRepository(),
            raw_repository=_RawRepository(),
            publisher=publisher,
        ).run(
            as_of=known_from,
            run_id="continuous-run-1",
            algo_version="test",
            params_hash="hash",
        )
    )

    assert result.row_count == 1
    assert result.segment_count == 1
    assert result.gap_count == 0
    assert publisher.published[0][1].run_id == "continuous-run-1"


def test_continuous_snapshot_includes_bucket_that_intersects_member_start() -> None:
    from src.identity.application.continuous_build_job import (
        ContinuousBuildContext,
        RawOhlcvBar,
        build_continuous_snapshot,
    )
    from src.identity.domain import (
        IdentitySnapshot,
        SeriesMemberRow,
        SeriesRegistryRow,
    )

    known_from = _ts("2026-07-03T00:00:00+00:00")
    snapshot = IdentitySnapshot(
        registry=[
            SeriesRegistryRow(
                series_id="TON-USDT-SWAP",
                series_label="ton_gram",
                asset_id=None,
                series_kind="composite",
                status="active",
                known_from=known_from,
            )
        ],
        members=[
            SeriesMemberRow(
                series_id="TON-USDT-SWAP",
                source_venue="OKX",
                source_symbol="GRAM-USDT-SWAP",
                valid_from=1781692200000,
                valid_to=None,
                known_from=known_from,
                adjustment_factor=Decimal("1"),
                succession_id="lineage",
            )
        ],
        aliases=[],
        gap_ranges=[],
    )

    continuous = build_continuous_snapshot(
        snapshot,
        [
            RawOhlcvBar(
                source_venue="OKX",
                source_symbol="GRAM-USDT-SWAP",
                timeframe="1H",
                timestamp=1781690400000,
                open=Decimal("1"),
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=Decimal("1"),
            )
        ],
        context=ContinuousBuildContext(
            run_id="run-1",
            algo_version="test",
            params_hash="hash",
        ),
    )

    assert [(row.timeframe, row.timestamp) for row in continuous.rows] == [
        ("1H", 1781690400000)
    ]


def _minimal_composite_snapshot(known_from):
    from src.identity.domain import IdentitySnapshot, SeriesMemberRow, SeriesRegistryRow

    return IdentitySnapshot(
        registry=[
            SeriesRegistryRow(
                series_id="TON-USDT-SWAP",
                series_label="ton_gram",
                asset_id=None,
                series_kind="composite",
                status="active",
                known_from=known_from,
            )
        ],
        members=[
            SeriesMemberRow(
                series_id="TON-USDT-SWAP",
                source_venue="OKX",
                source_symbol="TON-USDT-SWAP",
                valid_from=0,
                valid_to=2000,
                known_from=known_from,
                adjustment_factor=Decimal("1"),
                succession_id="lineage",
            ),
            SeriesMemberRow(
                series_id="TON-USDT-SWAP",
                source_venue="OKX",
                source_symbol="GRAM-USDT-SWAP",
                valid_from=2000,
                valid_to=None,
                known_from=known_from,
                adjustment_factor=Decimal("1"),
                succession_id="lineage",
            ),
        ],
        aliases=[],
        gap_ranges=[],
    )


def test_build_continuous_snapshot_is_idempotent() -> None:
    """DoD §14.14: 'identity build is idempotent'. Running the pure builder
    twice against byte-identical inputs (same identity snapshot, same raw
    bars, same run context) must produce byte-identical output — no hidden
    mutable state, wall-clock read, or nondeterministic ordering. This is
    also what makes the ON CONFLICT ... DO UPDATE upsert shape in
    `INSERT_CONTINUOUS_ROWS_SQL` safe to re-run: replaying the same build
    writes back the same rows, it does not accumulate duplicates or drift."""
    from src.identity.application.continuous_build_job import (
        ContinuousBuildContext,
        RawOhlcvBar,
        build_continuous_snapshot,
    )

    known_from = _ts("2026-07-03T00:00:00+00:00")
    snapshot = _minimal_composite_snapshot(known_from)
    raw_bars = [
        RawOhlcvBar(
            source_venue="OKX",
            source_symbol="TON-USDT-SWAP",
            timeframe="1m",
            timestamp=0,
            open=Decimal("1"),
            high=Decimal("2"),
            low=Decimal("0.5"),
            close=Decimal("1.5"),
            volume=Decimal("10"),
        ),
        RawOhlcvBar(
            source_venue="OKX",
            source_symbol="GRAM-USDT-SWAP",
            timeframe="1m",
            timestamp=2000,
            open=Decimal("1.6"),
            high=Decimal("1.8"),
            low=Decimal("1.4"),
            close=Decimal("1.7"),
            volume=Decimal("12"),
        ),
    ]
    context = ContinuousBuildContext(
        run_id="run-1", algo_version="test", params_hash="hash", snapshot_id="snap-1"
    )

    first = build_continuous_snapshot(snapshot, raw_bars, context=context)
    second = build_continuous_snapshot(snapshot, raw_bars, context=context)

    assert first.rows == second.rows
    assert first.segments == second.segments


def test_build_continuous_snapshot_never_produces_gap_marker_rows() -> None:
    """DoD §14.14: 'no physical gap marker rows appear in
    continuous_ohlcv_p'. `core.continuous_ohlcv_p`'s own `bar_kind` CHECK
    constraint only allows ('native','synthetic') — 'gap_marker' rows are
    output-only, produced solely by `OhlcvFacade.read_ohlcv(...,
    include_gap_markers=True)` at read time (Task 4.2), never written to the
    materialized table. This asserts that property holds for the builder
    that actually writes `continuous_ohlcv_p`, not just the DDL string."""
    from src.identity.application.continuous_build_job import (
        ContinuousBuildContext,
        RawOhlcvBar,
        build_continuous_snapshot,
    )

    known_from = _ts("2026-07-03T00:00:00+00:00")
    snapshot = _minimal_composite_snapshot(known_from)
    raw_bars = [
        RawOhlcvBar(
            source_venue="OKX",
            source_symbol="TON-USDT-SWAP",
            timeframe="1m",
            timestamp=0,
            open=Decimal("1"),
            high=Decimal("1"),
            low=Decimal("1"),
            close=Decimal("1"),
            volume=Decimal("1"),
        ),
        # Deliberately no bar covering the [0, 2000) -> gap window: the
        # builder must simply emit no row there, not a synthetic gap-marker
        # row standing in for the missing bar.
        RawOhlcvBar(
            source_venue="OKX",
            source_symbol="GRAM-USDT-SWAP",
            timeframe="1m",
            timestamp=2000,
            open=Decimal("1"),
            high=Decimal("1"),
            low=Decimal("1"),
            close=Decimal("1"),
            volume=Decimal("1"),
        ),
    ]
    continuous = build_continuous_snapshot(
        snapshot,
        raw_bars,
        context=ContinuousBuildContext(
            run_id="run-1", algo_version="test", params_hash="hash"
        ),
    )

    allowed_bar_kinds = {"native", "synthetic"}
    assert all(row.bar_kind in allowed_bar_kinds for row in continuous.rows)
    assert all(row.bar_kind != "gap_marker" for row in continuous.rows)
    # ContinuousOhlcvRow has no is_gap field at all -- gap-ness is not even
    # representable here, which is the point: it is impossible by
    # construction to persist a gap-marker row in continuous_ohlcv_p.
    assert not hasattr(continuous.rows[0], "is_gap")


def test_continuous_build_job_emits_success_observability() -> None:
    """§17.4 'continuous build' row: the job must emit the same
    start/success logs+metrics discipline IdentityBuildJob already has —
    this was previously entirely missing (zero observability calls in
    ContinuousBuildJob.run)."""
    import asyncio

    from src.identity.application.continuous_build_job import (
        ContinuousBuildJob,
        RawOhlcvBar,
    )
    from src.identity.observability import ContinuousBuildObserver

    known_from = _ts("2026-07-03T00:00:00+00:00")
    identity_snapshot = _minimal_composite_snapshot(known_from)

    class _IdentityRepository:
        async def load_snapshot(self, as_of):
            return identity_snapshot

    class _RawRepository:
        async def load_bars(self, members):
            return [
                RawOhlcvBar(
                    source_venue="OKX",
                    source_symbol="TON-USDT-SWAP",
                    timeframe="1m",
                    timestamp=0,
                    open=Decimal("1"),
                    high=Decimal("1"),
                    low=Decimal("1"),
                    close=Decimal("1"),
                    volume=Decimal("1"),
                )
            ]

    class _Publisher:
        async def publish_snapshot(self, snapshot, context, *, gap_count=0):
            return None

    observer = ContinuousBuildObserver()

    result = asyncio.run(
        ContinuousBuildJob(
            identity_repository=_IdentityRepository(),
            raw_repository=_RawRepository(),
            publisher=_Publisher(),
            observer=observer,
        ).run(
            as_of=known_from,
            run_id="continuous-run-success",
            algo_version="test",
            params_hash="hash",
        )
    )

    assert result.row_count == 1
    assert [event["stage"] for event in observer.events] == ["start", "finish"]
    assert observer.events[-1]["status"] == "success"
    assert observer.events[-1]["run_id"] == "continuous-run-success"
    assert observer.metrics[-1]["labels"]["status"] == "success"
    assert observer.metrics[-1]["labels"]["component"] == "continuous_build"
    assert observer.metrics[-1]["rows_written"] == 1


def test_continuous_build_job_records_failure_audit_and_observability() -> None:
    """A publisher failure must be logged/metriced (ContinuousBuildObserver)
    AND recorded to ops.continuous_ohlcv_build_audit via record_failure —
    the audit table already has a 'failed' status + error columns
    (migration 530), but nothing wrote to them before this task."""
    import asyncio

    from src.identity.application.continuous_build_job import ContinuousBuildJob

    known_from = _ts("2026-07-03T00:00:00+00:00")
    identity_snapshot = _minimal_composite_snapshot(known_from)

    class _IdentityRepository:
        async def load_snapshot(self, as_of):
            return identity_snapshot

    class _RawRepository:
        async def load_bars(self, members):
            return []

    class _Publisher:
        def __init__(self) -> None:
            self.failures = []

        async def publish_snapshot(self, snapshot, context, *, gap_count=0):
            raise RuntimeError("db connection reset mid-publish")

        async def record_failure(self, context, error_type, error_hash):
            self.failures.append((context, error_type, error_hash))

    from src.identity.observability import ContinuousBuildObserver

    observer = ContinuousBuildObserver()
    publisher = _Publisher()

    with pytest.raises(RuntimeError):
        asyncio.run(
            ContinuousBuildJob(
                identity_repository=_IdentityRepository(),
                raw_repository=_RawRepository(),
                publisher=publisher,
                observer=observer,
            ).run(
                as_of=known_from,
                run_id="continuous-run-failed",
                algo_version="test",
                params_hash="hash",
            )
        )

    assert observer.events[-1]["status"] == "failed"
    assert observer.events[-1]["error_type"] == "RuntimeError"
    assert "db connection reset" not in observer.events[-1]["error_message_hash"]
    assert publisher.failures[0][1] == "RuntimeError"
    assert publisher.failures[0][2] == observer.events[-1]["error_message_hash"]
    # context (run_id/algo_version/params_hash) is always available for
    # failure recording even though the failure happens inside
    # publish_snapshot, after context was built once, up front.
    assert publisher.failures[0][0].run_id == "continuous-run-failed"
