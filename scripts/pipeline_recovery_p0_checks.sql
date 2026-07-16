-- P0 checks for pipeline_recovery_controller live validation.
-- Read-only. Run against the live application database with psql.

\echo '1. Recent controller decisions by status/action'
SELECT
    decision_status,
    action_kind,
    target_dag_id,
    count(*) AS rows,
    max(created_at) AS latest_created_at
FROM ops.pipeline_recovery_decisions
WHERE created_at >= now() - interval '24 hours'
GROUP BY decision_status, action_kind, target_dag_id
ORDER BY latest_created_at DESC;

\echo '2. Triggered rows missing target_run_id'
SELECT
    id,
    created_at,
    controller_dag_run_id,
    action_kind,
    target_dag_id,
    symbol,
    timeframe,
    reason
FROM ops.pipeline_recovery_decisions
WHERE decision_status = 'triggered'
  AND target_run_id IS NULL
  AND created_at >= now() - interval '24 hours'
ORDER BY created_at DESC;

\echo '3. Candidate rows that must not poison cooldown'
SELECT
    id,
    created_at,
    controller_dag_run_id,
    action_kind,
    target_dag_id,
    symbol,
    timeframe,
    reason,
    cooldown_until
FROM ops.pipeline_recovery_decisions
WHERE decision_status = 'candidate'
  AND created_at >= now() - interval '24 hours'
ORDER BY created_at DESC;

\echo '4. Possible cooldown poisoning legacy rows: many triggered in one controller run'
SELECT
    controller_dag_run_id,
    action_kind,
    count(*) AS triggered_rows,
    count(target_run_id) AS rows_with_target_run_id,
    min(created_at) AS first_created_at,
    max(created_at) AS last_created_at,
    array_agg(symbol || '/' || timeframe ORDER BY priority, created_at) AS pairs
FROM ops.pipeline_recovery_decisions
WHERE decision_status = 'triggered'
  AND created_at >= now() - interval '7 days'
GROUP BY controller_dag_run_id, action_kind
HAVING count(*) > 1
ORDER BY last_created_at DESC;

\echo '5. Repeated bootstrap triggers for the same pair inside cooldown window'
SELECT
    symbol,
    timeframe,
    count(*) AS triggered_rows,
    min(created_at) AS first_created_at,
    max(created_at) AS last_created_at,
    array_agg(target_run_id ORDER BY created_at DESC) AS target_run_ids
FROM ops.pipeline_recovery_decisions
WHERE decision_status = 'triggered'
  AND action_kind = 'bootstrap'
  AND created_at >= now() - interval '240 minutes'
GROUP BY symbol, timeframe
HAVING count(*) > 1
ORDER BY triggered_rows DESC, last_created_at DESC;

\echo '6. Stale TEST-USDT-SWAP bootstrap state rows'
SELECT
    symbol,
    timeframe,
    status,
    updated_at,
    last_success_at,
    missing_bars,
    coverage_pct
FROM ops.swap_ohlcv_bootstrap_state
WHERE symbol = 'TEST-USDT-SWAP'
ORDER BY updated_at DESC NULLS LAST;

\echo '7. Recent non-test stale bootstrap rows'
SELECT
    symbol,
    timeframe,
    status,
    updated_at,
    last_success_at,
    missing_bars,
    coverage_pct
FROM ops.swap_ohlcv_bootstrap_state
WHERE symbol <> 'TEST-USDT-SWAP'
  AND (
      updated_at IS NULL
      OR updated_at < now() - interval '24 hours'
      OR status IN ('missing', 'incomplete', 'stuck', 'failed', 'pending', 'not_initialized')
  )
ORDER BY updated_at ASC NULLS FIRST
LIMIT 100;
