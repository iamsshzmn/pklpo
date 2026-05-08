# ADR-2026-05-03: last N closed bars architecture

## Status

Accepted

## Context

Phase 0 of the OKX swap repair work needs the architectural boundary decisions
captured before implementation starts. The planned work introduces a new
last-N-closed-bars guarantee flow that spans candles repair, targeted features
recalculation, and Airflow orchestration.

The current architecture docs also describe the active indicators table as
`indicators`, while the repair/recalc plan targets `indicators_p`. That mismatch
needs to be recorded now so later phases can implement against the intended
write path without silently treating the docs as authoritative. The existing
legacy-table cleanup track is already captured under `CT-004`.

The plan also requires one OKX-specific configuration hook for 1W handling.
That setting must remain part of centralized application settings instead of
being embedded into DAG code or module constants.

## Decision

The following Phase 0 decisions are accepted:

- Introduce an SLO-driven candles-side use case named
  `GuaranteeLastClosedBarsUseCase` to guarantee the last N closed bars.
- Introduce a separate features-side use case under `features/application/`
  for targeted recalculation of affected bars.
- Keep the Airflow DAG thin. Its role is orchestration across bounded contexts,
  not business logic or exchange-specific policy.
- Treat `indicators_p` as the target table for targeted recalculation in this
  initiative. `docs/ARCHITECTURE.md` currently documents `indicators` as active
  and `indicators_p` as legacy; this ADR records that mismatch and links the
  broader table-alignment work to `CT-004`.
- Store the OKX 1W week anchor in `src/config/settings.py` as
  `OKXSettings.week_anchor_ts_ms`, accessed through `get_settings().okx`.
  It must not be hardcoded in DAGs or module-level constants.
- Phase 0 adds the settings hook only. The effective value starts as a
  code-defined placeholder and env or `.env` sources do not supply it. Phase 8
  replaces that placeholder with the real OKX 1W anchor fetched from the API:
  `1777824000000` (`2026-05-03T16:00:00Z`, Monday `00:00` UTC+8).

  **Phase 8 status (2026-05-07):** Verification script created at `scripts/verify_okx_week_anchor.py`.
  Run manually with OKX API credentials to confirm anchor alignment against real 1W candle timestamps.
  Script retained in `scripts/` for future re-verification.
- Keep `RepairResult` unchanged in this track. If the guarantee/recalc flow
  needs a distinct completion contract, it will use a separate outcome model in
  a later phase.

## Consequences

Positive:

- Cross-context responsibilities are defined before business logic lands.
- Configuration access stays centralized and compatible with Clean
  Architecture boundaries.
- Later phases can build the candles guarantee flow, features recalc flow, and
  DAG orchestration independently without reopening the core ownership model.
- The `indicators` versus `indicators_p` discrepancy is explicit instead of
  becoming an implicit source of drift.

Tradeoffs:

- The week anchor remains code-defined on purpose; runtime env overrides stay
  disabled so DAGs cannot drift from the verified exchange rule.
- This ADR documents the current table-target intent but does not resolve the
  broader schema/documentation inconsistency tracked by `CT-004`.
