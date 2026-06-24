"""Tests for src.candles.application.recovery_controller (decision service).

Covers all 7 gates and key safety rules:
- Gate 1: dependency_gate
- Gate 2: active_run_gate (bootstrap blocks repair; repair blocks bootstrap)
- Gate 3: bootstrap_precedence (bootstrap before repair)
- Gate 4: repair_gate
- Gate 5: cooldown_gate
- Gate 6: rate_limit_gate
- Gate 7: no_recovery_needed skip
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.candles.application.recovery_controller import (
    BOOTSTRAP_DAG_ID,
    REPAIR_DAG_ID,
    BootstrapCandidateInfo,
    PipelineSnapshot,
    RecoveryConfig,
    RepairCandidateInfo,
    choose_recovery_actions,
)


def _config(
    *,
    max_symbols_per_run: int = 3,
    max_timeframes_per_run: int = 2,
    max_total_pairs_per_run: int = 6,
    cooldown_minutes: int = 240,
) -> RecoveryConfig:
    return RecoveryConfig(
        max_symbols_per_run=max_symbols_per_run,
        max_timeframes_per_run=max_timeframes_per_run,
        max_total_pairs_per_run=max_total_pairs_per_run,
        cooldown_minutes=cooldown_minutes,
    )


def _healthy_snapshot(**overrides: object) -> PipelineSnapshot:
    base: dict[str, object] = {
        "postgres_healthy": True,
        "okx_healthy": True,
        "active_dagrun_states": {REPAIR_DAG_ID: [], BOOTSTRAP_DAG_ID: []},
        "bootstrap_candidates": [],
        "repair_candidates": [],
    }
    base.update(overrides)
    return PipelineSnapshot(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Gate 1: dependency
# ---------------------------------------------------------------------------


def test_skip_when_postgres_unhealthy() -> None:
    snapshot = _healthy_snapshot(postgres_healthy=False)
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    assert len(decisions) == 1
    assert decisions[0].decision_status == "skip"
    assert decisions[0].reason == "dependency_unhealthy"


def test_skip_when_okx_unhealthy() -> None:
    snapshot = _healthy_snapshot(okx_healthy=False)
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    assert len(decisions) == 1
    assert decisions[0].decision_status == "skip"
    assert decisions[0].reason == "dependency_unhealthy"


# ---------------------------------------------------------------------------
# Gate 2: active run
# ---------------------------------------------------------------------------


def test_bootstrap_skips_when_repair_dag_running() -> None:
    snapshot = _healthy_snapshot(
        active_dagrun_states={REPAIR_DAG_ID: ["running"], BOOTSTRAP_DAG_ID: []},
        bootstrap_candidates=[
            BootstrapCandidateInfo(
                symbol="BTC-USDT-SWAP", timeframe="1H", status="incomplete"
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    skip_decisions = [d for d in decisions if d.action_kind == "bootstrap"]
    assert all(d.decision_status == "skip" for d in skip_decisions)
    assert all(d.reason == "conflicting_recovery_active" for d in skip_decisions)


def test_repair_skips_when_bootstrap_dag_running() -> None:
    snapshot = _healthy_snapshot(
        active_dagrun_states={REPAIR_DAG_ID: [], BOOTSTRAP_DAG_ID: ["running"]},
        repair_candidates=[
            RepairCandidateInfo(
                symbol="BTC-USDT-SWAP", timeframe="1H", gap_tasks=5, requested_bars=50
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    skip_decisions = [d for d in decisions if d.action_kind == "repair"]
    assert all(d.decision_status == "skip" for d in skip_decisions)
    assert all(d.reason == "conflicting_recovery_active" for d in skip_decisions)


def test_repair_skips_when_repair_dag_already_running() -> None:
    """Repair should not trigger when the repair DAG itself is already running."""
    snapshot = _healthy_snapshot(
        active_dagrun_states={REPAIR_DAG_ID: ["running"], BOOTSTRAP_DAG_ID: []},
        repair_candidates=[
            RepairCandidateInfo(
                symbol="BTC-USDT-SWAP", timeframe="1H", gap_tasks=5, requested_bars=50
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 0


# ---------------------------------------------------------------------------
# Gate 3: bootstrap precedence over repair
# ---------------------------------------------------------------------------


def test_bootstrap_triggered_before_repair_when_bootstrap_incomplete() -> None:
    """Bootstrap candidates with needful status take precedence over repair candidates."""
    snapshot = _healthy_snapshot(
        bootstrap_candidates=[
            BootstrapCandidateInfo(
                symbol="ETH-USDT-SWAP",
                timeframe="1H",
                status="incomplete",
                missing_bars=100,
            )
        ],
        repair_candidates=[
            RepairCandidateInfo(
                symbol="BTC-USDT-SWAP", timeframe="1H", gap_tasks=5, requested_bars=50
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert any(d.action_kind == "bootstrap" for d in triggered)


def test_bootstrap_triggered_for_missing_state() -> None:
    snapshot = _healthy_snapshot(
        bootstrap_candidates=[
            BootstrapCandidateInfo(
                symbol="SOL-USDT-SWAP", timeframe="1H", status="not_initialized"
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 1
    assert triggered[0].action_kind == "bootstrap"
    assert triggered[0].reason == "bootstrap_state_missing"


def test_bootstrap_triggered_for_failed_state() -> None:
    snapshot = _healthy_snapshot(
        bootstrap_candidates=[
            BootstrapCandidateInfo(
                symbol="XRP-USDT-SWAP", timeframe="4H", status="failed"
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert any(d.action_kind == "bootstrap" for d in triggered)


def test_bootstrap_reconcile_downgraded_triggers_with_correct_reason() -> None:
    snapshot = _healthy_snapshot(
        bootstrap_candidates=[
            BootstrapCandidateInfo(
                symbol="BNB-USDT-SWAP",
                timeframe="1H",
                status="incomplete",
                reconcile_downgraded=True,
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 1
    assert triggered[0].reason == "bootstrap_state_reconciled_incomplete"


# ---------------------------------------------------------------------------
# Gate 4: repair
# ---------------------------------------------------------------------------


def test_repair_triggered_for_gap_candidate() -> None:
    snapshot = _healthy_snapshot(
        repair_candidates=[
            RepairCandidateInfo(
                symbol="BTC-USDT-SWAP", timeframe="1H", gap_tasks=3, requested_bars=30
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 1
    assert triggered[0].action_kind == "repair"
    assert triggered[0].reason == "repair_gap_detected"
    assert triggered[0].target_dag_id == REPAIR_DAG_ID
    assert triggered[0].trigger_conf["symbols"] == ["BTC-USDT-SWAP"]


def test_repair_triggered_for_corrupted_bars() -> None:
    snapshot = _healthy_snapshot(
        repair_candidates=[
            RepairCandidateInfo(
                symbol="ETH-USDT-SWAP",
                timeframe="4H",
                gap_tasks=0,
                requested_bars=0,
                corrupted_bars=5,
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 1
    assert triggered[0].reason == "repair_corrupted_recent_closed_bars"
    assert "controller-last-closed-bars" in triggered[0].trigger_conf.get("trigger", "")


def test_repair_skips_when_guardrail_blocked() -> None:
    snapshot = _healthy_snapshot(
        repair_candidates=[
            RepairCandidateInfo(
                symbol="ADA-USDT-SWAP",
                timeframe="1H",
                gap_tasks=10,
                requested_bars=5000,
                guardrail_risk="blocked",
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 0


# ---------------------------------------------------------------------------
# Gate 5: cooldown
# ---------------------------------------------------------------------------


def _make_cooldown_row(
    *,
    action_kind: str,
    target_dag_id: str,
    symbol: str,
    timeframe: str,
    minutes_ago: int = 10,
) -> dict:
    return {
        "id": 1,
        "created_at": datetime.now(UTC) - timedelta(minutes=minutes_ago),
        "decision_status": "triggered",
        "action_kind": action_kind,
        "target_dag_id": target_dag_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "cooldown_until": None,
    }


def test_cooldown_suppresses_repeated_repair_trigger() -> None:
    cooldown_rows = [
        _make_cooldown_row(
            action_kind="repair",
            target_dag_id=REPAIR_DAG_ID,
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            minutes_ago=30,
        )
    ]
    snapshot = _healthy_snapshot(
        repair_candidates=[
            RepairCandidateInfo(
                symbol="BTC-USDT-SWAP", timeframe="1H", gap_tasks=5, requested_bars=50
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot,
        config=_config(cooldown_minutes=240),
        cooldown_rows=cooldown_rows,
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 0
    cooldown_skips = [
        d
        for d in decisions
        if d.decision_status == "skip" and d.reason == "cooldown_active"
    ]
    assert len(cooldown_skips) == 1


def test_cooldown_suppresses_repeated_bootstrap_trigger() -> None:
    cooldown_rows = [
        _make_cooldown_row(
            action_kind="bootstrap",
            target_dag_id=BOOTSTRAP_DAG_ID,
            symbol="ETH-USDT-SWAP",
            timeframe="4H",
            minutes_ago=60,
        )
    ]
    snapshot = _healthy_snapshot(
        bootstrap_candidates=[
            BootstrapCandidateInfo(
                symbol="ETH-USDT-SWAP", timeframe="4H", status="incomplete"
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot,
        config=_config(cooldown_minutes=240),
        cooldown_rows=cooldown_rows,
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 0


def test_cooldown_does_not_block_after_expiry() -> None:
    """A cooldown row older than cooldown_minutes must NOT suppress the trigger."""
    cooldown_rows = [
        _make_cooldown_row(
            action_kind="repair",
            target_dag_id=REPAIR_DAG_ID,
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            minutes_ago=300,  # older than cooldown_minutes=240
        )
    ]
    snapshot = _healthy_snapshot(
        repair_candidates=[
            RepairCandidateInfo(
                symbol="BTC-USDT-SWAP", timeframe="1H", gap_tasks=5, requested_bars=50
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot,
        config=_config(cooldown_minutes=240),
        cooldown_rows=cooldown_rows,
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 1


# ---------------------------------------------------------------------------
# Gate 6: rate limits
# ---------------------------------------------------------------------------


def test_rate_limit_caps_symbols_per_run() -> None:
    candidates = [
        RepairCandidateInfo(
            symbol=f"COIN{i}-USDT-SWAP", timeframe="1H", gap_tasks=5, requested_bars=50
        )
        for i in range(5)
    ]
    snapshot = _healthy_snapshot(repair_candidates=candidates)
    cfg = _config(
        max_symbols_per_run=2, max_timeframes_per_run=5, max_total_pairs_per_run=10
    )
    decisions = choose_recovery_actions(snapshot=snapshot, config=cfg, cooldown_rows=[])
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    triggered_symbols = {d.symbol for d in triggered}
    assert len(triggered_symbols) <= 2


def test_rate_limit_caps_timeframes_per_run() -> None:
    candidates = [
        RepairCandidateInfo(
            symbol="BTC-USDT-SWAP", timeframe=tf, gap_tasks=5, requested_bars=50
        )
        for tf in ["1H", "4H", "1D"]
    ]
    snapshot = _healthy_snapshot(repair_candidates=candidates)
    cfg = _config(
        max_symbols_per_run=5, max_timeframes_per_run=2, max_total_pairs_per_run=10
    )
    decisions = choose_recovery_actions(snapshot=snapshot, config=cfg, cooldown_rows=[])
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    triggered_tfs = {d.timeframe for d in triggered}
    assert len(triggered_tfs) <= 2


def test_rate_limit_always_returns_skip_decision() -> None:
    """Even when rate-limited, the function must return at least one decision."""
    snapshot = _healthy_snapshot()
    cfg = _config(
        max_symbols_per_run=0, max_timeframes_per_run=0, max_total_pairs_per_run=0
    )
    decisions = choose_recovery_actions(snapshot=snapshot, config=cfg, cooldown_rows=[])
    assert len(decisions) >= 1


# ---------------------------------------------------------------------------
# Gate 7: no recovery needed
# ---------------------------------------------------------------------------


def test_no_recovery_skip_when_no_candidates() -> None:
    snapshot = _healthy_snapshot()
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    assert len(decisions) >= 1
    # Must have at least one global skip
    global_skips = [d for d in decisions if d.reason == "no_recovery_needed"]
    assert len(global_skips) >= 1


def test_always_returns_at_least_one_decision() -> None:
    """choose_recovery_actions must never return an empty list."""
    snapshot = _healthy_snapshot()
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    assert len(decisions) >= 1


# ---------------------------------------------------------------------------
# Triggered decision carries correct trigger_conf
# ---------------------------------------------------------------------------


def test_triggered_bootstrap_decision_carries_trigger_conf() -> None:
    snapshot = _healthy_snapshot(
        bootstrap_candidates=[
            BootstrapCandidateInfo(
                symbol="BTC-USDT-SWAP", timeframe="1H", status="missing"
            )
        ],
    )
    cfg = RecoveryConfig(bootstrap_lookback_days=730, bootstrap_chunk_bars=500)
    decisions = choose_recovery_actions(snapshot=snapshot, config=cfg, cooldown_rows=[])
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 1
    tc = triggered[0].trigger_conf
    assert tc["symbols"] == ["BTC-USDT-SWAP"]
    assert tc["timeframes"] == ["1H"]
    assert tc["lookback_days"] == 730
    assert tc["chunk_bars"] == 500
    assert tc["triggered_by"] == "pipeline_recovery_controller"


def test_triggered_repair_decision_carries_trigger_conf() -> None:
    snapshot = _healthy_snapshot(
        repair_candidates=[
            RepairCandidateInfo(
                symbol="ETH-USDT-SWAP", timeframe="4H", gap_tasks=7, requested_bars=70
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=[]
    )
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    assert len(triggered) == 1
    tc = triggered[0].trigger_conf
    assert tc["symbols"] == ["ETH-USDT-SWAP"]
    assert tc["timeframes"] == ["4H"]
    assert "controller-gap-repair" in tc["trigger"]


def test_skip_decisions_are_recorded_even_when_no_trigger() -> None:
    """All gate-level skips (cooldown, rate_limit, conflict) must be in the returned list."""
    cooldown_rows = [
        _make_cooldown_row(
            action_kind="repair",
            target_dag_id=REPAIR_DAG_ID,
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            minutes_ago=10,
        )
    ]
    snapshot = _healthy_snapshot(
        repair_candidates=[
            RepairCandidateInfo(
                symbol="BTC-USDT-SWAP", timeframe="1H", gap_tasks=3, requested_bars=30
            )
        ],
    )
    decisions = choose_recovery_actions(
        snapshot=snapshot, config=_config(), cooldown_rows=cooldown_rows
    )
    skip_reasons = {d.reason for d in decisions if d.decision_status == "skip"}
    assert "cooldown_active" in skip_reasons
