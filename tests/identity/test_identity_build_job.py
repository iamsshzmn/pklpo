from __future__ import annotations

from datetime import UTC, datetime

import pytest


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def test_identity_snapshot_derives_trivial_series_for_raw_instruments() -> None:
    from src.identity.application.build_job import derive_identity_snapshot
    from src.identity.domain import IdentityBuildInputs, RawInstrument

    snapshot = derive_identity_snapshot(
        IdentityBuildInputs(
            instruments=[
                RawInstrument(symbol="BTC-USDT-SWAP", venue="OKX", inst_type="SWAP"),
                RawInstrument(symbol="ETH-USDT-SWAP", venue="OKX", inst_type="SWAP"),
            ],
            successions=[],
            gap_classifications=[],
        ),
        as_of=_ts("2026-07-03T00:00:00+00:00"),
    )

    assert {row.series_id for row in snapshot.registry} == {
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
    }
    assert all(row.series_kind == "trivial" for row in snapshot.registry)
    assert all(row.status == "active" for row in snapshot.registry)
    assert {row.source_symbol for row in snapshot.members} == {
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
    }
    assert snapshot.aliases == []
    assert snapshot.gap_ranges == []


def test_identity_snapshot_derives_approved_succession_as_composite_series() -> None:
    from src.identity.application.build_job import derive_identity_snapshot
    from src.identity.domain import (
        ApprovedGapClassification,
        ApprovedSuccession,
        IdentityBuildInputs,
        RawInstrument,
    )

    snapshot = derive_identity_snapshot(
        IdentityBuildInputs(
            instruments=[
                RawInstrument(symbol="TON-USDT-SWAP", venue="OKX", inst_type="SWAP"),
                RawInstrument(symbol="GRAM-USDT-SWAP", venue="OKX", inst_type="SWAP"),
            ],
            successions=[
                ApprovedSuccession(
                    old_symbol="TON-USDT-SWAP",
                    new_symbol="GRAM-USDT-SWAP",
                    venue="OKX",
                    inst_type="SWAP",
                    ratio=1,
                    old_stop_ts=1781054400000,
                    new_start_ts=1781685000000,
                    effective_from=_ts("2026-06-17T10:30:00+00:00"),
                    known_from=_ts("2026-07-01T00:00:00+00:00"),
                    approved_at=_ts("2026-07-02T00:00:00+00:00"),
                )
            ],
            gap_classifications=[
                ApprovedGapClassification(
                    series_id="TON-USDT-SWAP",
                    timeframe="1m",
                    range_start_ts=1781054400000,
                    range_end_ts=1781685000000,
                    gap_type="recoverable_data_gap",
                    recoverability="repairable",
                    reason="GRAM raw starts after TON stop",
                    known_from=_ts("2026-07-01T00:00:00+00:00"),
                    approved_at=_ts("2026-07-02T00:00:00+00:00"),
                )
            ],
        ),
        as_of=_ts("2026-07-03T00:00:00+00:00"),
    )

    assert [(row.series_id, row.series_label, row.series_kind) for row in snapshot.registry] == [
        ("TON-USDT-SWAP", "ton_gram", "composite")
    ]
    assert [(row.series_id, row.source_symbol, row.valid_from, row.valid_to) for row in snapshot.members] == [
        ("TON-USDT-SWAP", "TON-USDT-SWAP", 0, 1781054400000),
        ("TON-USDT-SWAP", "GRAM-USDT-SWAP", 1781685000000, None),
    ]
    assert [(row.old_series_id, row.canonical_series_id) for row in snapshot.aliases] == [
        ("GRAM-USDT-SWAP", "TON-USDT-SWAP")
    ]
    assert [(row.series_id, row.gap_type) for row in snapshot.gap_ranges] == [
        ("TON-USDT-SWAP", "recoverable_data_gap")
    ]


def test_identity_snapshot_hides_succession_before_known_as_of() -> None:
    from src.identity.application.build_job import derive_identity_snapshot
    from src.identity.domain import (
        ApprovedSuccession,
        IdentityBuildInputs,
        RawInstrument,
    )

    snapshot = derive_identity_snapshot(
        IdentityBuildInputs(
            instruments=[
                RawInstrument(symbol="TON-USDT-SWAP", venue="OKX", inst_type="SWAP"),
                RawInstrument(symbol="GRAM-USDT-SWAP", venue="OKX", inst_type="SWAP"),
            ],
            successions=[
                ApprovedSuccession(
                    old_symbol="TON-USDT-SWAP",
                    new_symbol="GRAM-USDT-SWAP",
                    venue="OKX",
                    inst_type="SWAP",
                    ratio=1,
                    old_stop_ts=1781054400000,
                    new_start_ts=1781685000000,
                    effective_from=_ts("2026-06-17T10:30:00+00:00"),
                    known_from=_ts("2026-07-01T00:00:00+00:00"),
                    approved_at=_ts("2026-07-02T00:00:00+00:00"),
                )
            ],
            gap_classifications=[],
        ),
        as_of=_ts("2026-06-30T00:00:00+00:00"),
    )

    assert {row.series_id for row in snapshot.registry} == {
        "TON-USDT-SWAP",
        "GRAM-USDT-SWAP",
    }
    assert all(row.series_kind == "trivial" for row in snapshot.registry)
    assert snapshot.aliases == []


@pytest.mark.asyncio
async def test_identity_build_job_publishes_snapshot_and_enqueues_recalc() -> None:
    from src.identity.application.build_job import IdentityBuildJob
    from src.identity.domain import IdentityBuildInputs, RawInstrument

    class _Repository:
        def __init__(self) -> None:
            self.published = []
            self.enqueued = []

        async def load_inputs(self, as_of):
            return IdentityBuildInputs(
                instruments=[
                    RawInstrument(
                        symbol="BTC-USDT-SWAP", venue="OKX", inst_type="SWAP"
                    )
                ],
                successions=[],
                gap_classifications=[],
            )

        async def publish_snapshot(self, snapshot, context):
            self.published.append((snapshot, context))

        async def enqueue_recalc(self, series_ids, context):
            self.enqueued.append((series_ids, context))

    repository = _Repository()
    result = await IdentityBuildJob(repository).run(
        as_of=_ts("2026-07-03T00:00:00+00:00"),
        run_id="run-1",
        algo_version="test",
        params_hash="hash",
    )

    assert result.series_count == 1
    assert result.member_count == 1
    assert len(repository.published) == 1
    assert repository.enqueued == [(["BTC-USDT-SWAP"], repository.published[0][1])]
