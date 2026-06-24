"""Pipeline Recovery Controller — pure decision service.

Inputs:  PipelineSnapshot  (state collected externally)
         RecoveryConfig    (limits and cooldown settings)
         cooldown_rows     (recent decisions from RecoveryDecisionRepository)

Output:  list[RecoveryDecision]

No Airflow imports. No DB I/O. No OKX calls.
Layer: application (pure orchestration logic, no infrastructure).

Decision order (7 gates):
1. dependency_gate   — Postgres / OKX reachable?
2. active_run_gate   — conflicting DAG running?
3. bootstrap_prec    — bootstrap state missing / incomplete / stuck / failed?
4. repair_gate       — gaps / corrupted closed bars detected?
5. cooldown_gate     — suppress repeat within cooldown window?
6. rate_limit_gate   — cap pairs per run?
7. skip              — no recovery needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / enums
# ---------------------------------------------------------------------------

CONTROLLER_DAG_ID = "pipeline_recovery_controller"
REPAIR_DAG_ID = "okx_swap_repair_v1"
BOOTSTRAP_DAG_ID = "okx_swap_ohlcv_bootstrap_v1"

# Bootstrap states that require remediation (controller should trigger bootstrap)
BOOTSTRAP_NEEDS_ACTION_STATUSES: frozenset[str] = frozenset(
    {"missing", "incomplete", "stuck", "failed", "pending", "not_initialized"}
)

# Bootstrap states where bootstrap is actively running / OK
BOOTSTRAP_ACTIVE_STATUSES: frozenset[str] = frozenset({"running", "in_progress"})

# Airflow DagRun states considered "active" (blocking peer actions)
ACTIVE_DAGRUN_STATES: frozenset[str] = frozenset({"running", "queued"})

# ---------------------------------------------------------------------------
# Reason enum strings
# ---------------------------------------------------------------------------

REASON_DEPENDENCY_UNHEALTHY = "dependency_unhealthy"
REASON_CONFLICTING_RECOVERY_ACTIVE = "conflicting_recovery_active"
REASON_COOLDOWN_ACTIVE = "cooldown_active"
REASON_RATE_LIMIT_NO_CANDIDATES = "rate_limit_no_candidates"
REASON_NO_RECOVERY_NEEDED = "no_recovery_needed"
REASON_BOOTSTRAP_STATE_MISSING = "bootstrap_state_missing"
REASON_BOOTSTRAP_STATE_INCOMPLETE = "bootstrap_state_incomplete"
REASON_BOOTSTRAP_STATE_RECONCILED_INCOMPLETE = "bootstrap_state_reconciled_incomplete"
REASON_REPAIR_GAP_DETECTED = "repair_gap_detected"
REASON_REPAIR_CORRUPTED_RECENT_CLOSED_BARS = "repair_corrupted_recent_closed_bars"
REASON_PRECHECK_GUARDRAIL_RISK = "precheck_guardrail_risk"
REASON_TRIGGER_FAILED = "trigger_failed"
REASON_TRIGGERED = "triggered"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RecoveryConfig:
    """Tunable limits for the recovery controller."""

    max_symbols_per_run: int = 3
    max_timeframes_per_run: int = 2
    max_total_pairs_per_run: int = 6
    cooldown_minutes: int = 240
    bootstrap_lookback_days: int = 730
    bootstrap_chunk_bars: int = 500
    # Subsets of curated symbols/timeframes the controller may act on.
    # Empty = use all candidates from snapshot.
    allowed_symbols: list[str] = field(default_factory=list)
    allowed_repair_timeframes: list[str] = field(default_factory=lambda: ["1H", "4H"])
    allowed_bootstrap_timeframes: list[str] = field(
        default_factory=lambda: ["1H", "4H", "1D", "1W", "1M"]
    )


@dataclass
class BootstrapCandidateInfo:
    """Per-(symbol, timeframe) bootstrap state summary."""

    symbol: str
    timeframe: str
    status: str  # "missing" | "incomplete" | "stuck" | "failed" | "completed" | ...
    missing_bars: int = 0
    coverage_pct: float = 100.0
    bootstrap_completed: bool = False
    # Set when reconcile found live coverage below expected
    reconcile_downgraded: bool = False


@dataclass
class RepairCandidateInfo:
    """Per-(symbol, timeframe) repair precheck summary."""

    symbol: str
    timeframe: str
    gap_tasks: int = 0
    requested_bars: int = 0
    corrupted_bars: int = 0
    guardrail_risk: str = "ok"  # "ok" | "blocked" | "high"


@dataclass
class PipelineSnapshot:
    """Read-only view of pipeline state passed into the decision service."""

    # Dependency health
    postgres_healthy: bool = True
    okx_healthy: bool = True

    # Active DagRun states (dag_id -> list of states)
    active_dagrun_states: dict[str, list[str]] = field(default_factory=dict)

    # Bootstrap candidates (symbol/tf pairs)
    bootstrap_candidates: list[BootstrapCandidateInfo] = field(default_factory=list)

    # Repair candidates (from plan_swap_repair precheck)
    repair_candidates: list[RepairCandidateInfo] = field(default_factory=list)

    # Context for snapshot timestamp
    snapshot_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RecoveryDecision:
    """Result of the decision service for one (symbol, timeframe) or a global skip."""

    decision_status: str  # skip | precheck_failed | triggered | trigger_failed
    action_kind: str  # none | repair | bootstrap
    reason: str
    symbol: str | None = None
    timeframe: str | None = None
    target_dag_id: str | None = None
    trigger_conf: dict[str, Any] = field(default_factory=dict)
    precheck_payload: dict[str, Any] = field(default_factory=dict)
    safety_payload: dict[str, Any] = field(default_factory=dict)
    cooldown_until: datetime | None = None
    priority: int = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_dag_active(snapshot: PipelineSnapshot, dag_id: str) -> bool:
    """Return True if dag_id has any running/queued DagRun in the snapshot."""
    states = snapshot.active_dagrun_states.get(dag_id, [])
    return any(s in ACTIVE_DAGRUN_STATES for s in states)


def _cooldown_active(
    *,
    action_kind: str,
    target_dag_id: str,
    symbol: str,
    timeframe: str,
    cooldown_rows: list[dict[str, Any]],
    cooldown_minutes: int,
) -> bool:
    """Return True if a triggered decision for the key exists within cooldown window."""
    since = datetime.now(UTC) - timedelta(minutes=cooldown_minutes)
    for row in cooldown_rows:
        if (
            row.get("action_kind") == action_kind
            and row.get("target_dag_id") == target_dag_id
            and row.get("symbol") == symbol
            and row.get("timeframe") == timeframe
            and row.get("decision_status") == "triggered"
        ):
            created_at = row.get("created_at")
            if created_at is not None and created_at >= since:
                return True
    return False


def _bootstrap_priority(candidate: BootstrapCandidateInfo) -> tuple[int, float]:
    """Lower tuple = higher priority (for sorting)."""
    # missing/failed/stuck first, then incomplete, then reconcile-downgraded
    if candidate.status in {"missing", "not_initialized"}:
        order = 0
    elif candidate.status in {"failed", "stuck"}:
        order = 1
    elif candidate.status == "incomplete" and candidate.reconcile_downgraded:
        order = 2
    elif candidate.status == "incomplete":
        order = 3
    else:
        order = 9
    # secondary: more missing bars = higher priority
    return (order, -candidate.missing_bars)


def _repair_priority(candidate: RepairCandidateInfo) -> tuple[int, int, int]:
    """Lower tuple = higher priority."""
    # corrupted bars are more urgent than gaps
    corrupted = 1 if candidate.corrupted_bars > 0 else 0
    return (1 - corrupted, -candidate.gap_tasks, -candidate.requested_bars)


def _cooldown_until_ts(config: RecoveryConfig) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=config.cooldown_minutes)


# ---------------------------------------------------------------------------
# Main decision function
# ---------------------------------------------------------------------------


def choose_recovery_actions(
    *,
    snapshot: PipelineSnapshot,
    config: RecoveryConfig,
    cooldown_rows: list[dict[str, Any]],
) -> list[RecoveryDecision]:
    """Apply 7-gate decision logic and return a list of RecoveryDecision objects.

    Always returns at least one decision (a global skip if no action is warranted).
    """
    decisions: list[RecoveryDecision] = []

    # ── Gate 1: dependency ──────────────────────────────────────────────────
    if not snapshot.postgres_healthy or not snapshot.okx_healthy:
        reason = REASON_DEPENDENCY_UNHEALTHY
        logger.warning(
            "recovery_controller skip reason=%s postgres_healthy=%s okx_healthy=%s",
            reason,
            snapshot.postgres_healthy,
            snapshot.okx_healthy,
        )
        return [
            RecoveryDecision(
                decision_status="skip",
                action_kind="none",
                reason=reason,
                safety_payload={
                    "postgres_healthy": snapshot.postgres_healthy,
                    "okx_healthy": snapshot.okx_healthy,
                },
            )
        ]

    # ── Collect bootstrap candidates needing action ──────────────────────────
    actionable_bootstrap = [
        c
        for c in snapshot.bootstrap_candidates
        if c.status in BOOTSTRAP_NEEDS_ACTION_STATUSES
        and (not config.allowed_symbols or c.symbol in config.allowed_symbols)
        and (
            not config.allowed_bootstrap_timeframes
            or c.timeframe in config.allowed_bootstrap_timeframes
        )
    ]
    actionable_bootstrap.sort(key=_bootstrap_priority)

    # ── Collect repair candidates ────────────────────────────────────────────
    actionable_repair = [
        c
        for c in snapshot.repair_candidates
        if (c.gap_tasks > 0 or c.corrupted_bars > 0)
        and (not config.allowed_symbols or c.symbol in config.allowed_symbols)
        and (
            not config.allowed_repair_timeframes
            or c.timeframe in config.allowed_repair_timeframes
        )
        and c.guardrail_risk != "blocked"
    ]
    actionable_repair.sort(key=_repair_priority)

    symbols_used: set[str] = set()
    timeframes_used: set[str] = set()
    total_pairs = 0

    def _rate_limit_reached() -> bool:
        return (
            len(symbols_used) >= config.max_symbols_per_run
            or len(timeframes_used) >= config.max_timeframes_per_run
            or total_pairs >= config.max_total_pairs_per_run
        )

    def _try_add(symbol: str, timeframe: str) -> bool:
        nonlocal total_pairs
        if (
            len(symbols_used) >= config.max_symbols_per_run
            and symbol not in symbols_used
        ):
            return False
        if (
            len(timeframes_used) >= config.max_timeframes_per_run
            and timeframe not in timeframes_used
        ):
            return False
        if total_pairs >= config.max_total_pairs_per_run:
            return False
        symbols_used.add(symbol)
        timeframes_used.add(timeframe)
        total_pairs += 1
        return True

    # ── Gate 3 + 2 + 5 + 6: bootstrap candidates ────────────────────────────
    for candidate in actionable_bootstrap:
        symbol = candidate.symbol
        timeframe = candidate.timeframe

        # Gate 2: active-run conflict (bootstrap blocks repair; repair blocks bootstrap)
        if _is_dag_active(snapshot, REPAIR_DAG_ID):
            decisions.append(
                RecoveryDecision(
                    decision_status="skip",
                    action_kind="bootstrap",
                    reason=REASON_CONFLICTING_RECOVERY_ACTIVE,
                    symbol=symbol,
                    timeframe=timeframe,
                    safety_payload={"conflicting_dag": REPAIR_DAG_ID},
                )
            )
            continue

        if _is_dag_active(snapshot, BOOTSTRAP_DAG_ID):
            decisions.append(
                RecoveryDecision(
                    decision_status="skip",
                    action_kind="bootstrap",
                    reason=REASON_CONFLICTING_RECOVERY_ACTIVE,
                    symbol=symbol,
                    timeframe=timeframe,
                    safety_payload={"conflicting_dag": BOOTSTRAP_DAG_ID},
                )
            )
            continue

        # Gate 5: cooldown
        if _cooldown_active(
            action_kind="bootstrap",
            target_dag_id=BOOTSTRAP_DAG_ID,
            symbol=symbol,
            timeframe=timeframe,
            cooldown_rows=cooldown_rows,
            cooldown_minutes=config.cooldown_minutes,
        ):
            decisions.append(
                RecoveryDecision(
                    decision_status="skip",
                    action_kind="bootstrap",
                    reason=REASON_COOLDOWN_ACTIVE,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )
            continue

        # Gate 6: rate limit
        if not _try_add(symbol, timeframe):
            decisions.append(
                RecoveryDecision(
                    decision_status="skip",
                    action_kind="bootstrap",
                    reason=REASON_RATE_LIMIT_NO_CANDIDATES,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )
            continue

        # Choose reason
        if candidate.status in {"missing", "not_initialized"}:
            reason = REASON_BOOTSTRAP_STATE_MISSING
        elif candidate.reconcile_downgraded:
            reason = REASON_BOOTSTRAP_STATE_RECONCILED_INCOMPLETE
        else:
            reason = REASON_BOOTSTRAP_STATE_INCOMPLETE

        trigger_conf: dict[str, Any] = {
            "triggered_by": CONTROLLER_DAG_ID,
            "reason": reason,
            "symbols": [symbol],
            "timeframes": [timeframe],
            "lookback_days": config.bootstrap_lookback_days,
            "chunk_bars": config.bootstrap_chunk_bars,
            "circuit_break_after": 3,
            "skip_recalc": False,
            "dry_run": False,
        }

        decisions.append(
            RecoveryDecision(
                decision_status="triggered",
                action_kind="bootstrap",
                reason=reason,
                symbol=symbol,
                timeframe=timeframe,
                target_dag_id=BOOTSTRAP_DAG_ID,
                trigger_conf=trigger_conf,
                precheck_payload={
                    "bootstrap_status": candidate.status,
                    "missing_bars": candidate.missing_bars,
                    "coverage_pct": candidate.coverage_pct,
                    "reconcile_downgraded": candidate.reconcile_downgraded,
                },
                cooldown_until=_cooldown_until_ts(config),
                priority=10,
            )
        )

    # ── Gate 4 + 2 + 5 + 6: repair candidates ───────────────────────────────
    for candidate in actionable_repair:
        symbol = candidate.symbol
        timeframe = candidate.timeframe

        # Gate 2: conflict — don't repair while bootstrap is active
        if _is_dag_active(snapshot, BOOTSTRAP_DAG_ID):
            decisions.append(
                RecoveryDecision(
                    decision_status="skip",
                    action_kind="repair",
                    reason=REASON_CONFLICTING_RECOVERY_ACTIVE,
                    symbol=symbol,
                    timeframe=timeframe,
                    safety_payload={"conflicting_dag": BOOTSTRAP_DAG_ID},
                )
            )
            continue

        # Gate 2: don't trigger repair when repair DAG already running
        if _is_dag_active(snapshot, REPAIR_DAG_ID):
            decisions.append(
                RecoveryDecision(
                    decision_status="skip",
                    action_kind="repair",
                    reason=REASON_CONFLICTING_RECOVERY_ACTIVE,
                    symbol=symbol,
                    timeframe=timeframe,
                    safety_payload={"conflicting_dag": REPAIR_DAG_ID},
                )
            )
            continue

        # Guardrail risk
        if candidate.guardrail_risk not in {"ok"}:
            decisions.append(
                RecoveryDecision(
                    decision_status="precheck_failed",
                    action_kind="repair",
                    reason=REASON_PRECHECK_GUARDRAIL_RISK,
                    symbol=symbol,
                    timeframe=timeframe,
                    precheck_payload={
                        "guardrail_risk": candidate.guardrail_risk,
                        "gap_tasks": candidate.gap_tasks,
                        "requested_bars": candidate.requested_bars,
                    },
                )
            )
            continue

        # Gate 5: cooldown
        repair_preset = (
            "controller-last-closed-bars"
            if candidate.corrupted_bars > 0 and candidate.gap_tasks == 0
            else "controller-gap-repair"
        )
        repair_dag_id = REPAIR_DAG_ID
        if _cooldown_active(
            action_kind="repair",
            target_dag_id=repair_dag_id,
            symbol=symbol,
            timeframe=timeframe,
            cooldown_rows=cooldown_rows,
            cooldown_minutes=config.cooldown_minutes,
        ):
            decisions.append(
                RecoveryDecision(
                    decision_status="skip",
                    action_kind="repair",
                    reason=REASON_COOLDOWN_ACTIVE,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )
            continue

        # Gate 6: rate limit
        if not _try_add(symbol, timeframe):
            decisions.append(
                RecoveryDecision(
                    decision_status="skip",
                    action_kind="repair",
                    reason=REASON_RATE_LIMIT_NO_CANDIDATES,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )
            continue

        reason = (
            REASON_REPAIR_CORRUPTED_RECENT_CLOSED_BARS
            if candidate.corrupted_bars > 0
            else REASON_REPAIR_GAP_DETECTED
        )

        trigger_conf = {
            "trigger": repair_preset,
            "symbols": [symbol],
            "timeframes": [timeframe],
            "reason": reason,
            "precheck": {
                "source": CONTROLLER_DAG_ID,
                "gap_tasks": candidate.gap_tasks,
                "requested_bars": candidate.requested_bars,
                "max_guardrail_risk": candidate.guardrail_risk,
            },
        }

        decisions.append(
            RecoveryDecision(
                decision_status="triggered",
                action_kind="repair",
                reason=reason,
                symbol=symbol,
                timeframe=timeframe,
                target_dag_id=repair_dag_id,
                trigger_conf=trigger_conf,
                precheck_payload={
                    "gap_tasks": candidate.gap_tasks,
                    "requested_bars": candidate.requested_bars,
                    "corrupted_bars": candidate.corrupted_bars,
                    "guardrail_risk": candidate.guardrail_risk,
                },
                cooldown_until=_cooldown_until_ts(config),
                priority=5,
            )
        )

    # ── Gate 7: if no triggered decisions, add global skip ────────────────────
    triggered = [d for d in decisions if d.decision_status == "triggered"]
    if not triggered:
        has_non_skip = any(d.decision_status != "skip" for d in decisions)
        if not decisions or not has_non_skip:
            decisions.append(
                RecoveryDecision(
                    decision_status="skip",
                    action_kind="none",
                    reason=REASON_NO_RECOVERY_NEEDED,
                )
            )

    logger.info(
        "recovery_controller decisions=%d triggered=%d",
        len(decisions),
        len(triggered),
    )
    return decisions
