# Partial Auto-Apply: Operator Guide

## What is partial auto-apply?

When `okx_swap_repair_v1` runs in `apply` mode without explicit `start`/`end` timestamps, it enters **auto-apply mode**: the DAG derives the repair window from coverage state rather than using a fixed operator-supplied window.

Because a single DAG run is bounded by `max_requested_bars_per_run` (default 10,000) and `max_gap_tasks_per_run` (default 50), a single run may cover only part of the outstanding gaps. When this happens, the run exits with `auto_apply_incomplete=true`.

## What does `auto_apply_incomplete=true` mean?

The run finished successfully but did **not** close all gaps in the target range. Specifically:

- `remaining_gap_tasks > 0` or `remaining_requested_bars > 0`
- `verified=true` — the data written in this run was verified
- `auto_apply_incomplete=true` — the repair is not fully complete

This is **intentional design**, not a failure. The Airflow task state stays `success`. Progress is tracked through `ops.swap_repair_audit` and Pushgateway metrics.

## Why does it happen?

| Cause | Explanation |
|---|---|
| Long gap history | The instrument has many months of gaps — more than one run can cover |
| Tight guardrails | `max_requested_bars_per_run` is set low relative to the gap depth |
| Many timeframes | Each timeframe uses its own bar budget per run |

## What should the operator do?

**If the run is expected to be partial:** Simply re-trigger the DAG. Each subsequent run will advance the repair window forward by one `max_requested_bars_per_run` chunk.

**To repair to completion automatically:** Schedule or manually re-trigger the DAG repeatedly until `remaining_gap_tasks=0` in the audit log.

```bash
# Check audit for remaining work
SELECT symbol, timeframe, remaining_gap_tasks, remaining_requested_bars, verified
FROM ops.swap_repair_audit
WHERE auto_apply_incomplete = true
ORDER BY created_at DESC
LIMIT 20;
```

**To increase progress per run** (use with caution): Raise the guardrails in the DAG trigger conf:

```json
{
  "mode": "apply",
  "repair_strategy": "gap-repair",
  "timeframes": ["1H"],
  "auto_apply_anchor_strategy": "first-coverage",
  "max_requested_bars_per_run": 50000,
  "max_gap_tasks_per_run": 200,
  "max_range_days": 30
}
```

> **Warning:** Very large `max_requested_bars_per_run` can cause the DAG to run for longer than `execution_timeout`. Start conservatively and increase incrementally.

## Monitoring partial apply progress

| Signal | Where to check |
|---|---|
| `auto_apply_incomplete=true` | `ops.swap_repair_audit` column |
| `remaining_gap_tasks` | `ops.swap_repair_audit` column |
| `pklpo_swap_repair_rows_written` | Pushgateway metrics |
| `verified=true` | Each completed run should always verify |

## When is a repair fully complete?

A repair is complete when a run returns:

```json
{
  "auto_apply_incomplete": false,
  "remaining_gap_tasks": 0,
  "remaining_requested_bars": 0,
  "verified": true,
  "verification_method": "gap-detection"
}
```

At that point, the repair window contains no detectable gaps and all written candles passed post-repair verification.

## Guardrail risk levels

The `plan_swap_repair` preview includes `guardrail_risk` to help size runs before triggering apply:

| Risk | Meaning | Action |
|---|---|---|
| `ok` | `requested_bars < 50%` of limit | Safe to apply |
| `medium` | `requested_bars` 50–90% of limit | Monitor run time |
| `high` | `requested_bars ≥ 90%` of limit | Raise guardrail or split window |

Run in `detect-only` mode first to see the risk level before committing to `apply`.
