# OKX Swap Repair v1: Transition Contract

**Purpose:** preserve a stable documentation target for
`ops/airflow/dags/README.md` while the tail-first repair redesign is being
implemented.

This document is intentionally split into two parts:

- **Current runtime contract**: what the shipped DAG and code enforce today
- **Planned tail-first contract**: what the 2026-04-22 plan is changing next

Until implementation tasks 2-6 are complete, operators should treat the current
code and tests as the source of truth.

## Current runtime contract

The current shipped `okx_swap_repair_v1` contract is defined by:

- `ops/airflow/dags/okx_swap_repair_v1.py`
- `src/candles/domain/repair.py`
- `src/candles/application/repair/summary.py`
- `tests/db/test_okx_swap_repair_v1_dag.py`

Current properties:

- the manual DAG surface is trigger-only via `{"trigger": "repair-all-swaps"}`
- the shipped preset uses `auto_apply_anchor_strategy="listing-date"`
- supported DAG timeframes are `["1H", "4H", "1D", "1W", "1M"]`
- the outcome enum remains backward-compatible: `success`, `partial`, `empty`,
  `fail`
- repeated no-progress on critical timeframes is still a terminal path in the
  shipped implementation

## Planned tail-first contract

The active implementation plan is
`history/planning/okx_swap_repair_tail_first_plan_2026-04-22.md`.

That plan introduces the following target semantics:

- auto-apply should work as **tail-first progressive fill**
- repair should select the newest unresolved gap first
- each gap should be processed in descending fixed-size chunks
- `received=0` on an old chunk should become a soft blocked/empty condition,
  not an automatic DAG failure
- blocked historical ranges should remain observable through summary, audit, and
  telemetry fields
- the existing `RepairOutcome` enum must remain backward-compatible in the
  first iteration; blocked state is represented in separate fields instead

## Compatibility rules for the redesign

The redesign is expected to preserve these contracts:

- `auto_apply_incomplete=true` remains the success-path signal for incomplete
  but non-failing repair work
- `verified=true` continues to describe only the attempted chunk/window scope
  that was actually written and re-checked
- Airflow task failure remains reserved for actual terminal errors such as API,
  store, or explicit guardrail failures
- new blocked-history diagnostics should prefer `summary_payload` / JSONB unless
  a later task explicitly introduces new SQL columns and a migration

## Operator reading order

Use the docs in this order:

1. `ops/airflow/dags/README.md` for the DAG trigger surface and operator entry
   point
2. `docs/operator-guide/partial-auto-apply.md` for the operator-facing meaning
   of partial and blocked repair runs
3. `history/planning/okx_swap_repair_tail_first_plan_2026-04-22.md` for the
   implementation plan and remaining rollout tasks
