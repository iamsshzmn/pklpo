from __future__ import annotations

from datetime import UTC, datetime

import pytest


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


@pytest.mark.asyncio
async def test_execution_resolver_reports_tradeable_when_instrument_live() -> None:
    from src.identity.application.execution_resolver import ExecutionResolver

    class _Repository:
        async def resolve_alias(self, series_id, as_of):
            return series_id

        async def find_active_member(self, series_id, as_of):
            return {
                "source_venue": "OKX",
                "source_symbol": "BTC-USDT-SWAP",
                "valid_from": 1_000,
                "valid_to": None,
                "instrument_state": "live",
            }

    resolution = await ExecutionResolver(_Repository()).resolve_execution_symbol(
        "BTC-USDT-SWAP", _ts("2026-07-03T00:00:00+00:00")
    )

    assert resolution.series_id == "BTC-USDT-SWAP"
    assert resolution.venue == "OKX"
    assert resolution.source_symbol == "BTC-USDT-SWAP"
    assert resolution.is_tradeable is True
    assert resolution.instrument_state == "live"
    assert resolution.reason == "member_active_and_instrument_live"


@pytest.mark.asyncio
async def test_execution_resolver_resolves_historical_leg_by_valid_range() -> None:
    """as_of before the TON->GRAM migration must resolve TON, as_of today must
    resolve GRAM — driven by the member's valid_from/valid_to window, never by
    picking "the last source_symbol seen in continuous history"."""
    from src.identity.application.execution_resolver import ExecutionResolver

    migration_ts_ms = 1_781_000_000_000  # arbitrary fixed cutover instant

    class _Repository:
        def __init__(self) -> None:
            self.calls: list[tuple[str, datetime]] = []

        async def resolve_alias(self, series_id, as_of):
            return "TON-USDT-SWAP"

        async def find_active_member(self, series_id, as_of):
            self.calls.append((series_id, as_of))
            as_of_ms = int(as_of.timestamp() * 1000)
            if as_of_ms < migration_ts_ms:
                return {
                    "source_venue": "OKX",
                    "source_symbol": "TON-USDT-SWAP",
                    "valid_from": 0,
                    "valid_to": migration_ts_ms,
                    "instrument_state": "expired",
                }
            return {
                "source_venue": "OKX",
                "source_symbol": "GRAM-USDT-SWAP",
                "valid_from": migration_ts_ms,
                "valid_to": None,
                "instrument_state": "live",
            }

    repository = _Repository()
    resolver = ExecutionResolver(repository)

    before_migration = await resolver.resolve_execution_symbol(
        "GRAM-USDT-SWAP", _ts("2026-06-01T00:00:00+00:00")
    )
    today = await resolver.resolve_execution_symbol(
        "GRAM-USDT-SWAP", _ts("2026-07-03T00:00:00+00:00")
    )

    assert before_migration.series_id == "TON-USDT-SWAP"
    assert before_migration.source_symbol == "TON-USDT-SWAP"
    assert before_migration.is_tradeable is False

    assert today.series_id == "TON-USDT-SWAP"
    assert today.source_symbol == "GRAM-USDT-SWAP"
    assert today.is_tradeable is True

    # Both calls hit the canonical series_id, resolved once via alias.
    assert [call[0] for call in repository.calls] == ["TON-USDT-SWAP", "TON-USDT-SWAP"]


@pytest.mark.asyncio
async def test_execution_resolver_reports_unknown_state_when_instrument_missing() -> (
    None
):
    from src.identity.application.execution_resolver import ExecutionResolver

    class _Repository:
        async def resolve_alias(self, series_id, as_of):
            return series_id

        async def find_active_member(self, series_id, as_of):
            return {
                "source_venue": "OKX",
                "source_symbol": "DELISTED-USDT-SWAP",
                "valid_from": 0,
                "valid_to": None,
                "instrument_state": None,
            }

    resolution = await ExecutionResolver(_Repository()).resolve_execution_symbol(
        "DELISTED-USDT-SWAP", _ts("2026-07-03T00:00:00+00:00")
    )

    assert resolution.is_tradeable is False
    assert resolution.instrument_state is None
    assert resolution.reason == "member_active_instrument_state_unknown"


@pytest.mark.asyncio
async def test_execution_resolver_reports_no_active_member() -> None:
    from src.identity.application.execution_resolver import ExecutionResolver

    class _Repository:
        async def resolve_alias(self, series_id, as_of):
            return series_id

        async def find_active_member(self, series_id, as_of):
            return None

    resolution = await ExecutionResolver(_Repository()).resolve_execution_symbol(
        "NEW-USDT-SWAP", _ts("2026-01-01T00:00:00+00:00")
    )

    assert resolution.series_id == "NEW-USDT-SWAP"
    assert resolution.venue is None
    assert resolution.source_symbol is None
    assert resolution.is_tradeable is False
    assert resolution.valid_from is None
    assert resolution.valid_to is None
    assert resolution.reason == "no_active_member_at_as_of"


@pytest.mark.asyncio
async def test_execution_resolver_reports_not_tradeable_for_suspended_instrument() -> (
    None
):
    from src.identity.application.execution_resolver import ExecutionResolver

    class _Repository:
        async def resolve_alias(self, series_id, as_of):
            return series_id

        async def find_active_member(self, series_id, as_of):
            return {
                "source_venue": "OKX",
                "source_symbol": "TON-USDT-SWAP",
                "valid_from": 0,
                "valid_to": None,
                "instrument_state": "suspended",
            }

    resolution = await ExecutionResolver(_Repository()).resolve_execution_symbol(
        "TON-USDT-SWAP", _ts("2026-07-03T00:00:00+00:00")
    )

    assert resolution.is_tradeable is False
    assert resolution.instrument_state == "suspended"
    assert resolution.reason == "member_active_instrument_not_live"
