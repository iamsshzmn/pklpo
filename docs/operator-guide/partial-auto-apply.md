# Partial Auto-Apply: Operator Guide

## What is partial auto-apply?

When `okx_swap_repair_v1` runs in `apply` mode without explicit `start`/`end`
timestamps, it enters **auto-apply mode**: the DAG derives repair work from
coverage state rather than using a fixed operator-supplied window.

The target repair model for the current redesign is **tail-first progressive
fill**:

- the planner starts with the newest unresolved gap for each `symbol x timeframe`
- the selected gap is split into fixed-size chunks
- chunks are processed from newer history toward older history
- each chunk uses its own fetch/write/verify cycle

This is designed to close recent missing data before the run spends time on
deep historical ranges that OKX may no longer serve completely.

Because a single DAG run is still bounded by `max_range_days` (default 7),
`max_requested_bars_per_run` (default 10,000), and `max_gap_tasks_per_run`
(default 50), one run may cover only part of the outstanding work. When this
happens, the run exits with `auto_apply_incomplete=true`.

## What does `auto_apply_incomplete=true` mean?

The run finished successfully but did **not** close all remaining work for the
timeframe. Specifically:

- `remaining_gap_tasks > 0` or `remaining_requested_bars > 0`
- `verified=true` for the chunk scope that was actually written and re-checked
- `auto_apply_incomplete=true` because the full backlog still contains work

This is intentional. The Airflow task state stays `success`. Progress is
tracked through `ops.swap_repair_audit` and Pushgateway metrics.

## Why does it happen?

| Cause | Explanation |
|---|---|
| Long gap history | The instrument has many months of unresolved history and one run is intentionally bounded |
| Tight guardrails | `max_requested_bars_per_run` or `max_gap_tasks_per_run` stops the run after useful progress |
| Blocked historical ranges | Older chunks may return `received=0` because OKX does not serve that history anymore |
| Many timeframes | Each timeframe consumes its own chunk budget and may stop independently |

## How should operators interpret blocked historical ranges?

An empty or blocked historical chunk is a **soft** operational condition, not an
automatic task failure.

- A chunk may be recorded as blocked or empty when `received=0` for the
  attempted range.
- The run should keep the timeframe in a successful partial state as long as no
  API/store exception or terminal guardrail violation occurred.
- Recent gaps may still be repairable even when deep history is not.

Operationally this means:

- treat blocked history as "remaining work still visible but not currently
  fillable"
- expect `auto_apply_incomplete=true` while such ranges remain
- use diagnostics and audit payloads to distinguish exchange-history limits from
  real system failures

## What should the operator do?

**If the run is expected to be partial:** re-trigger the DAG. Each subsequent
run should continue from the newest still-unresolved gap, then stop again on the
configured guardrails or blocked-history conditions.

**To repair to completion automatically:** schedule or manually re-trigger the
DAG repeatedly until `remaining_gap_tasks=0` in the audit log.

```sql
SELECT symbol, timeframe, remaining_gap_tasks, remaining_requested_bars, verified
FROM ops.swap_repair_audit
WHERE auto_apply_incomplete = true
ORDER BY created_at DESC
LIMIT 20;
```

**To increase progress per run** (use with caution): increase the built-in
limits in code. The shipped DAG surface stays trigger-only, so these values are
not operator-supplied runtime params for `okx_swap_repair_v1`.

> **Warning:** Very large limits can extend the runtime of a single repair run.
> Start conservatively and increase incrementally.

## Monitoring partial apply progress

| Signal | Where to check |
|---|---|
| `auto_apply_incomplete=true` | `ops.swap_repair_audit` column |
| `remaining_gap_tasks` | `ops.swap_repair_audit` column |
| `blocked` / `blocked_chunks` | audit payload or downstream telemetry fields |
| `pklpo_swap_repair_rows_written` | Pushgateway metrics |
| `verified=true` | Confirms the attempted chunk scope was re-checked |

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

At that point, the planned repair scope contains no detectable remaining gaps
and all written candles passed post-repair verification.

## Guardrail risk levels

The `plan_swap_repair` preview includes `guardrail_risk` to help size runs
before triggering apply:

| Risk | Meaning | Action |
|---|---|---|
| `ok` | `requested_bars < 50%` of limit | Safe to apply |
| `medium` | `requested_bars` 50-90% of limit | Monitor run time |
| `high` | `requested_bars >= 90%` of limit | Raise guardrail or split window |

Run in `detect-only` mode first to see the risk level before committing to
`apply`.
