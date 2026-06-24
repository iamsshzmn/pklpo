"""DAG: pipeline_recovery_controller.

Scheduled recovery controller.

Reads pipeline state, records a decision in ops.pipeline_recovery_decisions,
and (in future phases) triggers okx_swap_repair_v1 or okx_swap_ohlcv_bootstrap_v1.

Current mode: DRY (branch always goes to skip_recovery).
Trigger tasks are defined but never execute until dry_mode=False is set below.

Task graph::

    collect_recovery_state
    -> choose_recovery_action
    -> branch_recovery_action
    -> [trigger_repair | trigger_bootstrap | skip_recovery]
    -> record_controller_completion

``record_controller_completion`` uses ``trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS``
so it always writes a completion log entry regardless of which branch ran.

Heavy imports (src.candles.*) live inside task callables to not slow DAG discovery.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from _common import (  # type: ignore[import-not-found]
    get_dag_env as _get_common_dag_env,
    get_or_create_event_loop,
    setup_env as _setup_common_env,
)
from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.utils.trigger_rule import TriggerRule

if TYPE_CHECKING:
    import asyncio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rollout flag — set to False to enable real triggers (Stage 6 only)
# ---------------------------------------------------------------------------
DRY_MODE: bool = False

CONTROLLER_DAG_ID = "pipeline_recovery_controller"
REPAIR_DAG_ID = "okx_swap_repair_v1"
BOOTSTRAP_DAG_ID = "okx_swap_ohlcv_bootstrap_v1"

TASK_COLLECT = "collect_recovery_state"
TASK_CHOOSE = "choose_recovery_action"
TASK_BRANCH = "branch_recovery_action"
TASK_TRIGGER_REPAIR = "trigger_repair"
TASK_TRIGGER_BOOTSTRAP = "trigger_bootstrap"
TASK_SKIP = "skip_recovery"
TASK_RECORD = "record_controller_completion"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_loop() -> asyncio.AbstractEventLoop:
    return cast("asyncio.AbstractEventLoop", get_or_create_event_loop())


def get_dag_env() -> dict[str, str]:
    return cast(
        "dict[str, str]",
        _get_common_dag_env(job_name_default="pipeline_recovery_controller"),
    )


def setup_env(env: dict[str, str]) -> None:
    _setup_common_env(env)


def _build_log_context(context: dict[str, Any]) -> str:
    dag_run = context.get("dag_run")
    dag_run_id = getattr(dag_run, "run_id", "unknown")
    logical_date = context.get("logical_date", "unknown")
    return f"dag_run_id={dag_run_id} logical_date={logical_date}"


# ---------------------------------------------------------------------------
# Task callables
# ---------------------------------------------------------------------------


def task_collect_recovery_state(**context: Any) -> dict[str, Any]:
    """Collect pipeline state snapshot and record decisions (without triggering).

    Returns a summary dict pushed to XCom.
    """
    log_ctx = _build_log_context(context)
    logger.info("collect_recovery_state start %s", log_ctx)

    env = get_dag_env()
    setup_env(env)

    # Heavy imports inside callable — keeps DAG parse fast
    from src.candles.interfaces import recovery_controller as rc_facade

    dag_run = context.get("dag_run")
    dag_run_id = getattr(dag_run, "run_id", None)
    logical_date = context.get("logical_date")

    result = _get_loop().run_until_complete(
        rc_facade.collect_and_decide(
            controller_dag_id=CONTROLLER_DAG_ID,
            controller_dag_run_id=dag_run_id,
            logical_date=logical_date,
        )
    )

    snapshot_summary = result.get("snapshot_summary", {})
    decisions = result.get("decisions", [])
    triggered_decisions = [d for d in decisions if d.decision_status == "triggered"]

    logger.info(
        "collect_recovery_state finish %s snapshot=%s decisions=%d triggered=%d",
        log_ctx,
        snapshot_summary,
        len(decisions),
        len(triggered_decisions),
    )

    # XCom payload — lightweight (no full objects, only primitives)
    return {
        "snapshot_summary": snapshot_summary,
        "decision_count": len(decisions),
        "triggered_count": len(triggered_decisions),
        "triggered_actions": [
            {
                "action_kind": d.action_kind,
                "reason": d.reason,
                "symbol": d.symbol,
                "timeframe": d.timeframe,
                "target_dag_id": d.target_dag_id,
                "trigger_conf": d.trigger_conf,
            }
            for d in triggered_decisions
        ],
    }


def task_choose_recovery_action(**context: Any) -> dict[str, Any]:
    """Pull collect_recovery_state result and choose which action to execute.

    Returns {"branch": "trigger_repair" | "trigger_bootstrap" | "skip_recovery",
             "trigger_conf": {...}, "target_dag_id": "...", ...}
    """
    log_ctx = _build_log_context(context)
    logger.info("choose_recovery_action start %s", log_ctx)

    ti = context["ti"]
    collect_result = ti.xcom_pull(task_ids=TASK_COLLECT, key="return_value") or {}
    triggered = collect_result.get("triggered_actions", [])

    if not triggered:
        logger.info("choose_recovery_action no triggered actions %s → skip", log_ctx)
        return {"branch": "skip_recovery", "trigger_conf": {}, "target_dag_id": None}

    # Choose the first triggered action (highest priority was already ranked in decision-service)
    action = triggered[0]
    kind = action.get("action_kind", "none")

    if kind == "repair":
        branch = TASK_TRIGGER_REPAIR
    elif kind == "bootstrap":
        branch = TASK_TRIGGER_BOOTSTRAP
    else:
        branch = TASK_SKIP

    result = {
        "branch": branch,
        "action_kind": kind,
        "reason": action.get("reason"),
        "symbol": action.get("symbol"),
        "timeframe": action.get("timeframe"),
        "target_dag_id": action.get("target_dag_id"),
        "trigger_conf": action.get("trigger_conf", {}),
    }
    logger.info("choose_recovery_action result %s branch=%s", log_ctx, branch)
    return result


def task_branch_recovery_action(**context: Any) -> str:
    """BranchPythonOperator: returns the task_id to follow.

    In DRY_MODE always returns skip_recovery.
    """
    log_ctx = _build_log_context(context)
    ti = context["ti"]
    chosen = ti.xcom_pull(task_ids=TASK_CHOOSE, key="return_value") or {}
    branch = str(chosen.get("branch", TASK_SKIP))

    if DRY_MODE:
        logger.info(
            "branch_recovery_action DRY_MODE=True → skip_recovery (would have been: %s) %s",
            branch,
            log_ctx,
        )
        return TASK_SKIP

    logger.info("branch_recovery_action → %s %s", branch, log_ctx)
    return branch


def task_trigger_repair(**context: Any) -> dict[str, Any]:
    """Trigger okx_swap_repair_v1 with the controller preset conf.

    Active only after DRY_MODE=False and branch selects trigger_repair.
    """
    log_ctx = _build_log_context(context)
    logger.info("trigger_repair start %s", log_ctx)

    ti = context["ti"]
    chosen = ti.xcom_pull(task_ids=TASK_CHOOSE, key="return_value") or {}
    trigger_conf = chosen.get("trigger_conf", {})
    target_dag_id = chosen.get("target_dag_id", REPAIR_DAG_ID)

    # Heavy import inside callable
    from airflow.operators.trigger_dagrun import TriggerDagRunOperator

    logger.info(
        "trigger_repair triggering dag=%s conf=%s %s",
        target_dag_id,
        trigger_conf,
        log_ctx,
    )

    # Use TriggerDagRunOperator.execute() imperatively
    trigger_op = TriggerDagRunOperator(
        task_id="__trigger_repair_inner",
        trigger_dag_id=target_dag_id,
        conf=trigger_conf,
        wait_for_completion=False,
        reset_dag_run=False,
        dag=context["dag"],
    )
    trigger_op.execute(context)

    return {
        "triggered": True,
        "target_dag_id": target_dag_id,
        "trigger_conf": trigger_conf,
    }


def task_trigger_bootstrap(**context: Any) -> dict[str, Any]:
    """Trigger okx_swap_ohlcv_bootstrap_v1 with the controller preset conf.

    Active only after DRY_MODE=False and branch selects trigger_bootstrap.
    """
    log_ctx = _build_log_context(context)
    logger.info("trigger_bootstrap start %s", log_ctx)

    ti = context["ti"]
    chosen = ti.xcom_pull(task_ids=TASK_CHOOSE, key="return_value") or {}
    trigger_conf = chosen.get("trigger_conf", {})
    target_dag_id = chosen.get("target_dag_id", BOOTSTRAP_DAG_ID)

    from airflow.operators.trigger_dagrun import TriggerDagRunOperator

    logger.info(
        "trigger_bootstrap triggering dag=%s conf=%s %s",
        target_dag_id,
        trigger_conf,
        log_ctx,
    )
    trigger_op = TriggerDagRunOperator(
        task_id="__trigger_bootstrap_inner",
        trigger_dag_id=target_dag_id,
        conf=trigger_conf,
        wait_for_completion=False,
        reset_dag_run=False,
        dag=context["dag"],
    )
    trigger_op.execute(context)

    return {
        "triggered": True,
        "target_dag_id": target_dag_id,
        "trigger_conf": trigger_conf,
    }


def task_skip_recovery(**context: Any) -> dict[str, Any]:
    """No-op skip branch. Logs the skip reason."""
    log_ctx = _build_log_context(context)
    ti = context["ti"]
    collect_result = ti.xcom_pull(task_ids=TASK_COLLECT, key="return_value") or {}

    reason = "dry_mode" if DRY_MODE else "no_action_needed"
    logger.info(
        "skip_recovery reason=%s decision_count=%d %s",
        reason,
        collect_result.get("decision_count", 0),
        log_ctx,
    )
    return {"skipped": True, "reason": reason}


def task_record_controller_completion(**context: Any) -> dict[str, Any]:
    """Final task — always runs (permissive trigger rule).

    Summarises the run outcome for audit/observability.
    """
    log_ctx = _build_log_context(context)
    ti = context["ti"]

    collect_result = ti.xcom_pull(task_ids=TASK_COLLECT, key="return_value") or {}
    choose_result = ti.xcom_pull(task_ids=TASK_CHOOSE, key="return_value") or {}
    skip_result = ti.xcom_pull(task_ids=TASK_SKIP, key="return_value") or {}
    repair_result = ti.xcom_pull(task_ids=TASK_TRIGGER_REPAIR, key="return_value") or {}
    bootstrap_result = (
        ti.xcom_pull(task_ids=TASK_TRIGGER_BOOTSTRAP, key="return_value") or {}
    )

    actually_triggered = repair_result.get("triggered") or bootstrap_result.get(
        "triggered"
    )
    branch_taken = choose_result.get("branch", TASK_SKIP)

    result = {
        "dry_mode": DRY_MODE,
        "branch_taken": branch_taken,
        "actually_triggered": bool(actually_triggered),
        "decision_count": collect_result.get("decision_count", 0),
        "triggered_count": collect_result.get("triggered_count", 0),
        "snapshot_summary": collect_result.get("snapshot_summary", {}),
        "skipped": bool(skip_result.get("skipped")),
    }

    logger.info(
        "record_controller_completion %s dry_mode=%s branch=%s triggered=%s decisions=%d",
        log_ctx,
        DRY_MODE,
        branch_taken,
        actually_triggered,
        result["decision_count"],
    )
    return result


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

default_args = {
    "owner": "pipeline_recovery_controller",
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
    "execution_timeout": timedelta(minutes=20),
}

dag = DAG(
    dag_id=CONTROLLER_DAG_ID,
    start_date=datetime(2025, 1, 1),
    schedule="*/30 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["candles", "recovery", "controller"],
    doc_md=__doc__,
)

collect_recovery_state = PythonOperator(
    task_id=TASK_COLLECT,
    python_callable=task_collect_recovery_state,
    dag=dag,
)

choose_recovery_action = PythonOperator(
    task_id=TASK_CHOOSE,
    python_callable=task_choose_recovery_action,
    dag=dag,
)

branch_recovery_action = BranchPythonOperator(
    task_id=TASK_BRANCH,
    python_callable=task_branch_recovery_action,
    dag=dag,
)

trigger_repair = PythonOperator(
    task_id=TASK_TRIGGER_REPAIR,
    python_callable=task_trigger_repair,
    dag=dag,
)

trigger_bootstrap = PythonOperator(
    task_id=TASK_TRIGGER_BOOTSTRAP,
    python_callable=task_trigger_bootstrap,
    dag=dag,
)

skip_recovery = PythonOperator(
    task_id=TASK_SKIP,
    python_callable=task_skip_recovery,
    dag=dag,
)

record_controller_completion = PythonOperator(
    task_id=TASK_RECORD,
    python_callable=task_record_controller_completion,
    dag=dag,
    trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
)

# ---------------------------------------------------------------------------
# Task graph
# ---------------------------------------------------------------------------
(
    collect_recovery_state
    >> choose_recovery_action
    >> branch_recovery_action
    >> [trigger_repair, trigger_bootstrap, skip_recovery]
)
[trigger_repair, trigger_bootstrap, skip_recovery] >> record_controller_completion
