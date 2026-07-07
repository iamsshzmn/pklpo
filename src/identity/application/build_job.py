"""Identity build derivation and orchestration."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from src.identity.domain import (
    ApprovedGapClassification,
    ApprovedSuccession,
    IdentityBuildContext,
    IdentityBuildInputs,
    IdentityBuildResult,
    IdentitySnapshot,
    SeriesAliasRow,
    SeriesGapRangeRow,
    SeriesMemberRow,
    SeriesRegistryRow,
)
from src.identity.observability import IdentityBuildObserver

if TYPE_CHECKING:
    from datetime import datetime


class IdentityBuildRepository(Protocol):
    async def load_inputs(self, as_of: datetime) -> IdentityBuildInputs:
        """Load raw instruments and approved operational identity inputs."""

    async def publish_snapshot(
        self, snapshot: IdentitySnapshot, context: IdentityBuildContext
    ) -> None:
        """Atomically publish a validated identity snapshot."""

    async def enqueue_recalc(
        self, series_ids: list[str], context: IdentityBuildContext
    ) -> None:
        """Enqueue downstream feature/scoring recalculation for affected series."""

    async def record_failure(
        self, context: IdentityBuildContext, error_type: str, error_hash: str
    ) -> None:
        """Persist failed build audit metadata."""


class IdentityValidationError(ValueError):
    """Raised when an identity snapshot violates build invariants."""


def _is_visible(known_from: datetime, approved_at: datetime, as_of: datetime) -> bool:
    return known_from <= as_of and approved_at <= as_of


def _series_label(old_symbol: str, new_symbol: str) -> str:
    old_base = old_symbol.split("-", 1)[0].lower()
    new_base = new_symbol.split("-", 1)[0].lower()
    return f"{old_base}_{new_base}"


def _succession_lineage_id(succession: ApprovedSuccession) -> str:
    return "|".join(
        (
            succession.venue,
            succession.inst_type,
            succession.old_symbol,
            succession.new_symbol,
        )
    )


def _visible_successions(
    successions: list[ApprovedSuccession], as_of: datetime
) -> list[ApprovedSuccession]:
    return sorted(
        (
            succession
            for succession in successions
            if _is_visible(succession.known_from, succession.approved_at, as_of)
        ),
        key=lambda item: (item.old_symbol, item.new_symbol, item.known_from),
    )


def _visible_gaps(
    gaps: list[ApprovedGapClassification], as_of: datetime
) -> list[ApprovedGapClassification]:
    return sorted(
        (
            gap
            for gap in gaps
            if _is_visible(gap.known_from, gap.approved_at, as_of)
        ),
        key=lambda item: (item.series_id, item.timeframe, item.range_start_ts),
    )


def derive_identity_snapshot(
    inputs: IdentityBuildInputs, *, as_of: datetime
) -> IdentitySnapshot:
    """Derive a PIT-visible identity snapshot from raw and approved ops inputs."""
    visible_successions = _visible_successions(inputs.successions, as_of)
    composite_symbols = {
        succession.old_symbol: succession for succession in visible_successions
    }
    hidden_trivial_symbols = {
        succession.new_symbol for succession in visible_successions
    }
    instrument_by_symbol = {
        instrument.symbol: instrument
        for instrument in sorted(inputs.instruments, key=lambda item: item.symbol)
    }

    registry: list[SeriesRegistryRow] = []
    members: list[SeriesMemberRow] = []
    aliases: list[SeriesAliasRow] = []

    for symbol, instrument in instrument_by_symbol.items():
        if symbol in hidden_trivial_symbols:
            continue

        succession = composite_symbols.get(symbol)
        if succession is None:
            registry.append(
                SeriesRegistryRow(
                    series_id=symbol,
                    series_label=symbol,
                    asset_id=None,
                    series_kind="trivial",
                    status="active",
                    known_from=as_of,
                )
            )
            members.append(
                SeriesMemberRow(
                    series_id=symbol,
                    source_venue=instrument.venue,
                    source_symbol=symbol,
                    valid_from=instrument.list_time or 0,
                    valid_to=None,
                    known_from=as_of,
                    adjustment_factor=Decimal("1"),
                )
            )
            continue

        lineage_id = _succession_lineage_id(succession)
        registry.append(
            SeriesRegistryRow(
                series_id=succession.old_symbol,
                series_label=_series_label(succession.old_symbol, succession.new_symbol),
                asset_id=None,
                series_kind="composite",
                status="active",
                known_from=succession.known_from,
            )
        )
        members.append(
            SeriesMemberRow(
                series_id=succession.old_symbol,
                source_venue=succession.venue,
                source_symbol=succession.old_symbol,
                valid_from=instrument.list_time or 0,
                valid_to=succession.old_stop_ts,
                known_from=succession.known_from,
                adjustment_factor=Decimal("1"),
                succession_id=lineage_id,
            )
        )
        members.append(
            SeriesMemberRow(
                series_id=succession.old_symbol,
                source_venue=succession.venue,
                source_symbol=succession.new_symbol,
                valid_from=succession.new_start_ts or 0,
                valid_to=None,
                known_from=succession.known_from,
                adjustment_factor=Decimal(str(succession.ratio)),
                succession_id=lineage_id,
            )
        )
        aliases.append(
            SeriesAliasRow(
                old_series_id=succession.new_symbol,
                canonical_series_id=succession.old_symbol,
                known_from=succession.known_from,
                reason="symbol_succession",
            )
        )

    visible_gaps = _visible_gaps(inputs.gap_classifications, as_of)
    gap_ranges = [
        SeriesGapRangeRow(
            series_id=gap.series_id,
            timeframe=gap.timeframe,
            gap_start_ts=gap.range_start_ts,
            gap_end_ts=gap.range_end_ts,
            gap_type=gap.gap_type,
            recoverability=gap.recoverability,
            reason=gap.reason,
            known_from=gap.known_from,
        )
        for gap in visible_gaps
    ]

    snapshot = IdentitySnapshot(
        registry=registry,
        members=members,
        aliases=aliases,
        gap_ranges=gap_ranges,
    )
    validate_identity_snapshot(snapshot)
    return snapshot


def validate_identity_snapshot(snapshot: IdentitySnapshot) -> None:
    registry_ids = [row.series_id for row in snapshot.registry]
    if len(registry_ids) != len(set(registry_ids)):
        raise IdentityValidationError("duplicate series_registry series_id")

    member_keys = [
        (
            row.series_id,
            row.source_venue,
            row.source_symbol,
            row.valid_from,
            row.known_from,
        )
        for row in snapshot.members
    ]
    if len(member_keys) != len(set(member_keys)):
        raise IdentityValidationError("duplicate series_members key")

    for row in snapshot.members:
        if row.valid_to is not None and row.valid_from >= row.valid_to:
            raise IdentityValidationError("invalid member validity range")
        if row.adjustment_factor <= 0:
            raise IdentityValidationError("invalid member adjustment factor")

    for row in snapshot.gap_ranges:
        if row.gap_start_ts >= row.gap_end_ts:
            raise IdentityValidationError("invalid gap range")


class IdentityBuildJob:
    def __init__(
        self,
        repository: IdentityBuildRepository,
        observer: IdentityBuildObserver | None = None,
    ) -> None:
        self._repository = repository
        self._observer = observer or IdentityBuildObserver()

    async def run(
        self,
        *,
        as_of: datetime,
        run_id: str,
        algo_version: str,
        params_hash: str,
    ) -> IdentityBuildResult:
        context = IdentityBuildContext(
            run_id=run_id,
            algo_version=algo_version,
            params_hash=params_hash,
            as_of=as_of,
        )
        started = self._observer.start(run_id=run_id, as_of=as_of)
        try:
            inputs = await self._repository.load_inputs(as_of)
            snapshot = derive_identity_snapshot(inputs, as_of=as_of)
            await self._repository.publish_snapshot(snapshot, context)
            await self._repository.enqueue_recalc(snapshot.series_ids, context)
            result = IdentityBuildResult(
                run_id=run_id,
                series_count=len(snapshot.registry),
                member_count=len(snapshot.members),
                alias_count=len(snapshot.aliases),
                gap_count=len(snapshot.gap_ranges),
            )
            self._observer.success(
                run_id=run_id,
                started=started,
                rows_read=(
                    len(inputs.instruments)
                    + len(inputs.successions)
                    + len(inputs.gap_classifications)
                ),
                rows_written=result.series_count,
                gap_count=result.gap_count,
            )
            return result
        except Exception as exc:
            error_hash = self._observer.failure(
                run_id=run_id, started=started, exc=exc
            )
            record_failure = getattr(self._repository, "record_failure", None)
            if record_failure is not None:
                await record_failure(context, type(exc).__name__, error_hash)
            raise
