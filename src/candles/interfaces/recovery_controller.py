"""Airflow-facing facade for the pipeline recovery controller.

Wires together:
- repair_interface.plan_swap_repair  (precheck, read-only)
- bootstrap_interface.build_coverage_report + reconcile_bootstrap_state (read-only)
- RecoveryDecisionRepository  (persist decisions)
- RecoveryConfig from settings
- curated symbol list from instruments_list.json

Does NOT call repair apply-path or bootstrap run directly.

Layer: interfaces (thin adapter; may import application + infrastructure, no DAG code).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.candles.application.recovery_controller import (
    BOOTSTRAP_DAG_ID,
    REPAIR_DAG_ID,
    BootstrapCandidateInfo,
    PipelineSnapshot,
    RecoveryConfig,
    RecoveryDecision,
    RepairCandidateInfo,
    choose_recovery_actions,
)
from src.candles.infrastructure.recovery_decision_repository import (
    RecoveryDecisionRepository,
)
from src.candles.instruments_service import (
    load_symbols_from_file,
    resolve_repo_instruments_file,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default controller config (may be overridden by caller / settings)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = RecoveryConfig(
    max_symbols_per_run=3,
    max_timeframes_per_run=2,
    max_total_pairs_per_run=6,
    cooldown_minutes=240,
    bootstrap_lookback_days=730,
    bootstrap_chunk_bars=500,
    allowed_repair_timeframes=["1H", "4H"],
    allowed_bootstrap_timeframes=["1H", "4H", "1D", "1W", "1M"],
)

_REPAIR_BOOTSTRAP_TIMEFRAMES = ("1H", "4H", "1D", "1W", "1M")


# ---------------------------------------------------------------------------
# Snapshot collection helpers
# ---------------------------------------------------------------------------


async def _collect_bootstrap_candidates(
    symbols: list[str],
    timeframes: list[str],
    lookback_days: int,
) -> list[BootstrapCandidateInfo]:
    """Query bootstrap state for all (symbol, timeframe) pairs."""
    from src.candles.interfaces import bootstrap as bootstrap_interface

    candidates: list[BootstrapCandidateInfo] = []

    # 1. coverage report from state table (fast)
    coverage_rows = await bootstrap_interface.build_coverage_report(
        symbols=symbols,
        timeframes=timeframes,
    )

    # 2. reconcile completed states against live swap_ohlcv_p
    reconcile_rows = await bootstrap_interface.reconcile_bootstrap_state(
        symbols=symbols,
        timeframes=timeframes,
        lookback_days=lookback_days,
    )
    reconcile_downgraded: set[tuple[str, str]] = set()
    for row in reconcile_rows:
        if row.get("action") == "downgraded":
            reconcile_downgraded.add((row["symbol"], row["timeframe"]))

    for row in coverage_rows:
        symbol = row["symbol"]
        timeframe = row["timeframe"]
        status = row.get("status", "not_initialized")
        candidates.append(
            BootstrapCandidateInfo(
                symbol=symbol,
                timeframe=timeframe,
                status=status,
                missing_bars=int(row.get("missing_bars") or 0),
                coverage_pct=float(row.get("coverage_pct") or 0.0),
                bootstrap_completed=bool(row.get("bootstrap_completed", False)),
                reconcile_downgraded=(symbol, timeframe) in reconcile_downgraded,
            )
        )

    return candidates


async def _collect_repair_candidates(
    symbols: list[str],
    timeframes: list[str],
) -> list[RepairCandidateInfo]:
    """Run repair plan_swap_repair precheck (dry-run) for each (symbol, timeframe)."""
    from src.candles.domain.repair import RepairExecutionMode, RepairStrategy
    from src.candles.interfaces import repair as repair_interface

    candidates: list[RepairCandidateInfo] = []
    # 6h window for precheck (same as repair DAG auto_apply_window)
    window_hours = 6

    for symbol in symbols:
        for timeframe in timeframes:
            try:
                preview = await repair_interface.plan_swap_repair(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_ts_ms=None,
                    end_ts_ms=None,
                    mode=RepairExecutionMode.DETECT_ONLY,
                    strategy=RepairStrategy.GAP_REPAIR,
                    auto_apply_window=True,
                    max_gap_tasks_per_run=50,
                    max_requested_bars_per_run=10_000,
                    max_range_days=7,
                    max_fail_ratio=1.0,
                    padding_bars=0,
                    window_hours=window_hours,
                )
                gap_tasks = int(preview.get("gap_tasks", 0))
                requested_bars = int(preview.get("requested_bars", 0))
                guardrail_risk = str(preview.get("guardrail_risk", "ok"))

                if gap_tasks > 0 or requested_bars > 0:
                    candidates.append(
                        RepairCandidateInfo(
                            symbol=symbol,
                            timeframe=timeframe,
                            gap_tasks=gap_tasks,
                            requested_bars=requested_bars,
                            guardrail_risk=guardrail_risk,
                        )
                    )
            except Exception as exc:
                logger.warning(
                    "recovery_controller repair precheck failed symbol=%s timeframe=%s error=%s",
                    symbol,
                    timeframe,
                    exc,
                )

    return candidates


async def _check_dependencies() -> tuple[bool, bool]:
    """Check Postgres and OKX reachability. Returns (postgres_ok, okx_ok)."""
    postgres_ok = True
    okx_ok = True

    # Postgres check: simple lightweight query
    try:
        from sqlalchemy import text

        from src.utils.session_utils import get_db_session

        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("recovery_controller postgres health check failed: %s", exc)
        postgres_ok = False

    # OKX check: public time endpoint via CCXT
    try:
        import ccxt.async_support as ccxt

        exchange = ccxt.okx({"enableRateLimit": True})
        try:
            await exchange.fetch_time()
        finally:
            await exchange.close()
    except Exception as exc:
        logger.warning("recovery_controller okx health check failed: %s", exc)
        okx_ok = False

    return postgres_ok, okx_ok


async def _get_active_dagrun_states(dag_ids: list[str]) -> dict[str, list[str]]:
    """Query Airflow DagRun states for given dag_ids.

    Imports Airflow Session inside the function to avoid DAG discovery cost.
    Returns {dag_id: [state, ...]} or empty on failure (fail closed — caller treats
    unknown as potentially active).
    """
    result: dict[str, list[str]] = {dag_id: [] for dag_id in dag_ids}
    try:
        from airflow.models.dagrun import DagRun
        from airflow.utils.session import provide_session

        @provide_session
        def _query(session: Any = None) -> dict[str, list[str]]:
            rows = (
                session.query(DagRun.dag_id, DagRun.state)
                .filter(DagRun.dag_id.in_(dag_ids))
                .filter(DagRun.state.in_(["running", "queued"]))
                .all()
            )
            out: dict[str, list[str]] = {d: [] for d in dag_ids}
            for dag_id, state in rows:
                out[dag_id].append(state)
            return out

        result = _query()
    except Exception as exc:
        logger.warning(
            "recovery_controller dagrun state query failed dag_ids=%s error=%s",
            dag_ids,
            exc,
            exc_info=True,
        )
        # Fail closed: treat both as potentially active so we skip
        for dag_id in dag_ids:
            result[dag_id] = ["running"]

    return result


# ---------------------------------------------------------------------------
# Cooldown rows query
# ---------------------------------------------------------------------------


async def _load_cooldown_rows(
    repository: RecoveryDecisionRepository,
    candidates_bootstrap: list[BootstrapCandidateInfo],
    candidates_repair: list[RepairCandidateInfo],
    config: RecoveryConfig,
) -> list[dict[str, Any]]:
    """Bulk-load cooldown rows for all candidate (action, symbol, timeframe) keys."""
    rows: list[dict[str, Any]] = []

    for candidate in candidates_bootstrap:
        rows.extend(
            await repository.get_cooldown_rows(
                action_kind="bootstrap",
                target_dag_id=BOOTSTRAP_DAG_ID,
                symbol=candidate.symbol,
                timeframe=candidate.timeframe,
                cooldown_minutes=config.cooldown_minutes,
            )
        )

    for candidate in candidates_repair:
        rows.extend(
            await repository.get_cooldown_rows(
                action_kind="repair",
                target_dag_id=REPAIR_DAG_ID,
                symbol=candidate.symbol,
                timeframe=candidate.timeframe,
                cooldown_minutes=config.cooldown_minutes,
            )
        )

    return rows


# ---------------------------------------------------------------------------
# Persist decisions
# ---------------------------------------------------------------------------


async def _persist_decisions(
    repository: RecoveryDecisionRepository,
    decisions: list[RecoveryDecision],
    *,
    controller_dag_id: str,
    controller_dag_run_id: str | None,
    logical_date: Any,
) -> list[dict[str, Any]]:
    """Write all decisions to the DB and return list of inserted rows."""
    persisted: list[dict[str, Any]] = []
    for decision in decisions:
        row = await repository.insert_decision(
            controller_dag_id=controller_dag_id,
            controller_dag_run_id=controller_dag_run_id,
            logical_date=logical_date,
            decision_status=decision.decision_status,
            action_kind=decision.action_kind,
            target_dag_id=decision.target_dag_id,
            target_run_id=None,
            reason=decision.reason,
            symbol=decision.symbol,
            timeframe=decision.timeframe,
            priority=decision.priority,
            cooldown_until=decision.cooldown_until,
            precheck_payload=decision.precheck_payload,
            trigger_conf=decision.trigger_conf,
            safety_payload=decision.safety_payload,
            error=None,
        )
        persisted.append({**row, "decision": decision})
    return persisted


# ---------------------------------------------------------------------------
# Public facade entry point
# ---------------------------------------------------------------------------


async def collect_and_decide(
    *,
    controller_dag_id: str = "pipeline_recovery_controller",
    controller_dag_run_id: str | None = None,
    logical_date: Any = None,
    config: RecoveryConfig | None = None,
    symbols: list[str] | None = None,
    repair_timeframes: list[str] | None = None,
    bootstrap_timeframes: list[str] | None = None,
    skip_repair_precheck: bool = False,
) -> dict[str, Any]:
    """Collect snapshot, run decision service, persist decisions.

    Returns:
        {
            "decisions": [RecoveryDecision, ...],
            "persisted": [{"id": ..., "created_at": ...}, ...],
            "snapshot_summary": {...},
        }

    This is the Airflow task callable (sync wrapper: ``run_collect_and_decide``).
    Does NOT trigger any DAG runs — dry mode enforced at caller level.
    """
    cfg = config or DEFAULT_CONFIG

    # Load curated symbols if not provided
    if symbols is None:
        symbols = load_symbols_from_file(resolve_repo_instruments_file(), logger=logger)
    if not symbols:
        logger.warning("recovery_controller: curated symbol list is empty")

    repair_tfs = repair_timeframes or cfg.allowed_repair_timeframes
    bootstrap_tfs = bootstrap_timeframes or cfg.allowed_bootstrap_timeframes

    logger.info(
        "recovery_controller collect_and_decide start symbols=%d repair_tfs=%s bootstrap_tfs=%s",
        len(symbols),
        repair_tfs,
        bootstrap_tfs,
    )

    # ── 1. Dependency health ────────────────────────────────────────────────
    postgres_ok, okx_ok = await _check_dependencies()

    # ── 2. Active DagRun states ─────────────────────────────────────────────
    active_states = await _get_active_dagrun_states([REPAIR_DAG_ID, BOOTSTRAP_DAG_ID])

    # ── 3. Bootstrap candidates ─────────────────────────────────────────────
    bootstrap_candidates: list[BootstrapCandidateInfo] = []
    if postgres_ok:
        try:
            bootstrap_candidates = await _collect_bootstrap_candidates(
                symbols=symbols,
                timeframes=bootstrap_tfs,
                lookback_days=cfg.bootstrap_lookback_days,
            )
        except Exception as exc:
            logger.error(
                "recovery_controller bootstrap candidate collection failed: %s", exc
            )

    # ── 4. Repair candidates (precheck) ────────────────────────────────────
    repair_candidates: list[RepairCandidateInfo] = []
    if postgres_ok and okx_ok and not skip_repair_precheck:
        try:
            repair_candidates = await _collect_repair_candidates(
                symbols=symbols,
                timeframes=repair_tfs,
            )
        except Exception as exc:
            logger.error(
                "recovery_controller repair candidate collection failed: %s", exc
            )

    snapshot = PipelineSnapshot(
        postgres_healthy=postgres_ok,
        okx_healthy=okx_ok,
        active_dagrun_states=active_states,
        bootstrap_candidates=bootstrap_candidates,
        repair_candidates=repair_candidates,
    )

    # ── 5. Cooldown rows ────────────────────────────────────────────────────
    repository = RecoveryDecisionRepository()
    cooldown_rows: list[dict[str, Any]] = []
    if postgres_ok:
        cooldown_rows = await _load_cooldown_rows(
            repository, bootstrap_candidates, repair_candidates, cfg
        )

    # ── 6. Decision service ─────────────────────────────────────────────────
    decisions = choose_recovery_actions(
        snapshot=snapshot,
        config=cfg,
        cooldown_rows=cooldown_rows,
    )

    # ── 7. Persist ──────────────────────────────────────────────────────────
    persisted: list[dict[str, Any]] = []
    if postgres_ok:
        persisted = await _persist_decisions(
            repository,
            decisions,
            controller_dag_id=controller_dag_id,
            controller_dag_run_id=controller_dag_run_id,
            logical_date=logical_date,
        )

    triggered = [d for d in decisions if d.decision_status == "triggered"]
    logger.info(
        "recovery_controller collect_and_decide done decisions=%d triggered=%d persisted=%d",
        len(decisions),
        len(triggered),
        len(persisted),
    )

    return {
        "decisions": decisions,
        "persisted": persisted,
        "snapshot_summary": {
            "postgres_healthy": postgres_ok,
            "okx_healthy": okx_ok,
            "bootstrap_candidates": len(bootstrap_candidates),
            "repair_candidates": len(repair_candidates),
            "active_dagruns": {k: v for k, v in active_states.items() if v},
        },
    }


def run_collect_and_decide(**kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper for Airflow PythonOperator task callables."""
    return asyncio.get_event_loop().run_until_complete(collect_and_decide(**kwargs))
