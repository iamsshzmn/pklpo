"""Tests for src.candles.interfaces.recovery_controller facade.

Verifies:
- repair precheck (_collect_repair_candidates) is called only when postgres+okx healthy
  and skip_repair_precheck=False
- apply-path (repair_interface.run_swap_repair, bootstrap run) is NEVER called
- decisions are persisted (including skip)
- skip_repair_precheck=True suppresses the repair precheck call
- dependency failure → snapshot has postgres_healthy=False
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.candles.application.recovery_controller import (
    BootstrapCandidateInfo,
    RecoveryConfig,
    RecoveryDecision,
)

# ---------------------------------------------------------------------------
# Shared defaults
# ---------------------------------------------------------------------------

_REPAIR_DAG = "okx_swap_repair_v1"
_BOOTSTRAP_DAG = "okx_swap_ohlcv_bootstrap_v1"

_ACTIVE_STATES_IDLE: dict[str, list[str]] = {
    _REPAIR_DAG: [],
    _BOOTSTRAP_DAG: [],
}


def _skip_decision(**kwargs: Any) -> RecoveryDecision:
    return RecoveryDecision(
        decision_status="skip",
        action_kind="none",
        reason="no_recovery_needed",
        **kwargs,
    )


def _persisted_row(idx: int = 1) -> dict[str, Any]:
    return {"id": idx, "created_at": datetime.now(UTC)}


@pytest.fixture(autouse=True)
def _candles_repository_mock():
    instrument_repo = AsyncMock()
    instrument_repo.get_instrument_states = AsyncMock(return_value={})

    with patch(
        "src.candles.interfaces.recovery_controller.SwapCandlesRepository",
        return_value=instrument_repo,
    ):
        yield


# ---------------------------------------------------------------------------
# Base patches used in every test
# ---------------------------------------------------------------------------


def _base_patches(
    *,
    postgres_ok: bool = True,
    okx_ok: bool = True,
    active_states: dict | None = None,
    bootstrap_candidates: list | None = None,
    repair_candidates: list | None = None,
    cooldown_rows: list | None = None,
    persisted: list | None = None,
    decisions: list | None = None,
    symbols: list[str] | None = None,
) -> list[Any]:
    if active_states is None:
        active_states = _ACTIVE_STATES_IDLE.copy()
    if bootstrap_candidates is None:
        bootstrap_candidates = []
    if repair_candidates is None:
        repair_candidates = []
    if cooldown_rows is None:
        cooldown_rows = []
    if persisted is None:
        persisted = [_persisted_row()]
    if decisions is None:
        decisions = [_skip_decision()]
    if symbols is None:
        symbols = ["BTC-USDT-SWAP"]

    MODULE = "src.candles.interfaces.recovery_controller"
    APP = "src.candles.application.recovery_controller"

    return [
        patch(
            f"{MODULE}._check_dependencies",
            new=AsyncMock(return_value=(postgres_ok, okx_ok)),
        ),
        patch(
            f"{MODULE}._get_active_dagrun_states",
            new=AsyncMock(return_value=active_states),
        ),
        patch(
            f"{MODULE}._collect_bootstrap_candidates",
            new=AsyncMock(return_value=bootstrap_candidates),
        ),
        patch(
            f"{MODULE}._collect_repair_candidates",
            new=AsyncMock(return_value=repair_candidates),
        ),
        patch(
            f"{MODULE}._load_cooldown_rows", new=AsyncMock(return_value=cooldown_rows)
        ),
        patch(f"{MODULE}._persist_decisions", new=AsyncMock(return_value=persisted)),
        patch(f"{MODULE}.load_symbols_from_file", return_value=symbols),
        patch(
            f"{APP}.choose_recovery_actions",
            return_value=decisions,
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_decisions_writes_triggerable_actions_as_candidates() -> None:
    """Eligible actions are candidates until Airflow actually starts a downstream run."""
    import src.candles.interfaces.recovery_controller as rc_facade

    triggered = RecoveryDecision(
        decision_status="triggered",
        action_kind="repair",
        reason="repair_gap_detected",
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        target_dag_id=_REPAIR_DAG,
    )
    repo = AsyncMock()
    repo.insert_decision = AsyncMock(return_value=_persisted_row())

    await rc_facade._persist_decisions(
        repo,
        [triggered],
        controller_dag_id="pipeline_recovery_controller",
        controller_dag_run_id="controller-run",
        logical_date=None,
    )

    params = repo.insert_decision.call_args.kwargs
    assert params["decision_status"] == "candidate"
    assert params["cooldown_until"] is None


@pytest.mark.asyncio
async def test_collect_repair_called_when_healthy() -> None:
    """_collect_repair_candidates is called when postgres+okx healthy and no skip flag."""
    import src.candles.interfaces.recovery_controller as rc_facade

    collect_repair_mock = AsyncMock(return_value=[])

    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(True, True)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=collect_repair_mock,
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=AsyncMock(return_value=[_persisted_row()]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller.load_symbols_from_file",
            return_value=["BTC-USDT-SWAP"],
        ),
        patch(
            "src.candles.application.recovery_controller.choose_recovery_actions",
            return_value=[_skip_decision()],
        ),
    ):
        await rc_facade.collect_and_decide(
            symbols=["BTC-USDT-SWAP"],
            repair_timeframes=["1H"],
        )

    collect_repair_mock.assert_called_once()


@pytest.mark.asyncio
async def test_collect_repair_skipped_when_flag_set() -> None:
    """_collect_repair_candidates is NOT called when skip_repair_precheck=True."""
    collect_repair_mock = AsyncMock(return_value=[])

    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(True, True)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=collect_repair_mock,
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=AsyncMock(return_value=[_persisted_row()]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller.load_symbols_from_file",
            return_value=["BTC-USDT-SWAP"],
        ),
        patch(
            "src.candles.application.recovery_controller.choose_recovery_actions",
            return_value=[_skip_decision()],
        ),
    ):
        import src.candles.interfaces.recovery_controller as rc_facade

        await rc_facade.collect_and_decide(
            symbols=["BTC-USDT-SWAP"],
            skip_repair_precheck=True,
        )

    collect_repair_mock.assert_not_called()


@pytest.mark.asyncio
async def test_collect_repair_skipped_when_postgres_unhealthy() -> None:
    """_collect_repair_candidates must not run when postgres is down."""
    collect_repair_mock = AsyncMock(return_value=[])

    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(False, True)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=collect_repair_mock,
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller.load_symbols_from_file",
            return_value=["BTC-USDT-SWAP"],
        ),
        patch(
            "src.candles.application.recovery_controller.choose_recovery_actions",
            return_value=[_skip_decision()],
        ),
    ):
        import src.candles.interfaces.recovery_controller as rc_facade

        result = await rc_facade.collect_and_decide(symbols=["BTC-USDT-SWAP"])

    collect_repair_mock.assert_not_called()
    assert result["snapshot_summary"]["postgres_healthy"] is False


@pytest.mark.asyncio
async def test_collect_repair_skipped_when_okx_unhealthy() -> None:
    """_collect_repair_candidates must not run when OKX is unreachable."""
    collect_repair_mock = AsyncMock(return_value=[])

    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(True, False)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=collect_repair_mock,
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=AsyncMock(return_value=[_persisted_row()]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller.load_symbols_from_file",
            return_value=["BTC-USDT-SWAP"],
        ),
        patch(
            "src.candles.application.recovery_controller.choose_recovery_actions",
            return_value=[_skip_decision()],
        ),
    ):
        import src.candles.interfaces.recovery_controller as rc_facade

        result = await rc_facade.collect_and_decide(symbols=["BTC-USDT-SWAP"])

    collect_repair_mock.assert_not_called()
    assert result["snapshot_summary"]["okx_healthy"] is False


@pytest.mark.asyncio
async def test_persist_decisions_called_on_healthy_postgres() -> None:
    """_persist_decisions must be called when postgres is healthy."""
    persisted_row = _persisted_row()
    persist_mock = AsyncMock(return_value=[persisted_row])

    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(True, True)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=persist_mock,
        ),
        patch(
            "src.candles.interfaces.recovery_controller.load_symbols_from_file",
            return_value=["BTC-USDT-SWAP"],
        ),
        patch(
            "src.candles.application.recovery_controller.choose_recovery_actions",
            return_value=[_skip_decision()],
        ),
    ):
        import src.candles.interfaces.recovery_controller as rc_facade

        result = await rc_facade.collect_and_decide(symbols=["BTC-USDT-SWAP"])

    persist_mock.assert_called_once()
    assert result["persisted"] == [persisted_row]


@pytest.mark.asyncio
async def test_persist_decisions_skipped_when_postgres_down() -> None:
    """_persist_decisions must NOT be called when postgres is unhealthy."""
    persist_mock = AsyncMock(return_value=[])

    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(False, True)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=persist_mock,
        ),
        patch(
            "src.candles.interfaces.recovery_controller.load_symbols_from_file",
            return_value=["BTC-USDT-SWAP"],
        ),
        patch(
            "src.candles.application.recovery_controller.choose_recovery_actions",
            return_value=[_skip_decision()],
        ),
    ):
        import src.candles.interfaces.recovery_controller as rc_facade

        await rc_facade.collect_and_decide(symbols=["BTC-USDT-SWAP"])

    persist_mock.assert_not_called()


@pytest.mark.asyncio
async def test_result_contains_expected_keys() -> None:
    """collect_and_decide must return decisions, persisted, snapshot_summary."""
    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(True, True)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=AsyncMock(return_value=[_persisted_row()]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller.load_symbols_from_file",
            return_value=["BTC-USDT-SWAP"],
        ),
        patch(
            "src.candles.application.recovery_controller.choose_recovery_actions",
            return_value=[_skip_decision()],
        ),
    ):
        import src.candles.interfaces.recovery_controller as rc_facade

        result = await rc_facade.collect_and_decide(symbols=["BTC-USDT-SWAP"])

    assert "decisions" in result
    assert "persisted" in result
    assert "snapshot_summary" in result
    summary = result["snapshot_summary"]
    assert "postgres_healthy" in summary
    assert "okx_healthy" in summary
    assert "bootstrap_candidates" in summary
    assert "repair_candidates" in summary


@pytest.mark.asyncio
async def test_triggered_decisions_visible_in_result() -> None:
    """Triggered decisions appear in result['decisions']."""
    triggered = RecoveryDecision(
        decision_status="triggered",
        action_kind="repair",
        reason="repair_gap_detected",
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        target_dag_id=_REPAIR_DAG,
    )

    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(True, True)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=AsyncMock(return_value=[_persisted_row()]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller.load_symbols_from_file",
            return_value=["BTC-USDT-SWAP"],
        ),
        patch(
            "src.candles.interfaces.recovery_controller.choose_recovery_actions",
            return_value=[triggered],
        ),
    ):
        import src.candles.interfaces.recovery_controller as rc_facade

        result = await rc_facade.collect_and_decide(symbols=["BTC-USDT-SWAP"])

    assert result["decisions"][0].decision_status == "triggered"
    assert result["decisions"][0].action_kind == "repair"


@pytest.mark.asyncio
async def test_does_not_call_repair_apply_path() -> None:
    """The facade must never call the repair apply-path (run_swap_repair)."""
    run_repair_mock = AsyncMock(return_value={})

    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(True, True)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=AsyncMock(return_value=[_persisted_row()]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller.load_symbols_from_file",
            return_value=["BTC-USDT-SWAP"],
        ),
        patch(
            "src.candles.application.recovery_controller.choose_recovery_actions",
            return_value=[_skip_decision()],
        ),
        # Patch the apply-path — must NOT be called
        patch("src.candles.interfaces.repair.run_swap_repair", new=run_repair_mock),
    ):
        import src.candles.interfaces.recovery_controller as rc_facade

        await rc_facade.collect_and_decide(symbols=["BTC-USDT-SWAP"])

    run_repair_mock.assert_not_called()


@pytest.mark.asyncio
async def test_universe_equals_curated_no_discovery() -> None:
    """Universe is always curated_symbols — no auto-discovery, no extra symbols."""
    import src.candles.interfaces.recovery_controller as rc_facade

    collected_symbols: list[str] = []

    async def _collect_bootstrap(
        symbols: list[str],
        timeframes: list[str],
        lookback_days: int,
    ) -> list[BootstrapCandidateInfo]:
        collected_symbols.extend(symbols)
        return []

    with (
        patch(
            "src.candles.interfaces.recovery_controller._check_dependencies",
            new=AsyncMock(return_value=(True, True)),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._get_active_dagrun_states",
            new=AsyncMock(return_value=_ACTIVE_STATES_IDLE),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_bootstrap_candidates",
            new=AsyncMock(side_effect=_collect_bootstrap),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._collect_repair_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._load_cooldown_rows",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "src.candles.interfaces.recovery_controller._persist_decisions",
            new=AsyncMock(return_value=[_persisted_row()]),
        ),
        patch(
            "src.candles.application.recovery_controller.choose_recovery_actions",
            return_value=[_skip_decision()],
        ),
    ):
        result = await rc_facade.collect_and_decide(
            symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            bootstrap_timeframes=["1H"],
            skip_repair_precheck=True,
        )

    # Only curated symbols were processed — no extras
    assert collected_symbols == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    # summary has only "curated", no "discovered" / "total"
    assert result["snapshot_summary"]["universe"] == {"curated": 2}
    # RecoveryDiscoveryRepository must not exist in the module namespace
    import src.candles.interfaces.recovery_controller as rc_mod

    assert not hasattr(rc_mod, "RecoveryDiscoveryRepository")
