# OKX Swap Repair v1: Plan vs Actual Scope

**Purpose:** capture the supported runtime contract for `okx_swap_repair_v1` as it exists in code and tests today, so plan text does not drift from the real trigger surface.

## Actual v1 scope

- Any valid OKX swap instId (e.g. `BTC-USDT-SWAP`, `ETH-USDT-SWAP`); preflight checks via `instruments` table.
- Supported timeframes: `1m`, `1H`, `4H`, `1D`, `1W`, `1M`.
- Supported modes: `detect-only`, `dry-run`, `apply`.
- Supported strategies: `gap-repair`, `backfill`.
- The DAG is manual only (`schedule=None`) and is intended for bounded repair windows, not open-ended backfills.

## Trigger contract

- `preflight_instrument_check` runs first, checking that the requested symbol exists in the `instruments` table.
- The DAG validates trigger params in `validate_swap_repair_conf_task`.
- `timeframes` is the primary multi-timeframe input; legacy single `timeframe` is still accepted for compatibility.
- The params snapshot test in `tests/db/test_okx_swap_repair_v1_dag.py` locks the trigger contract; `symbol` has `default=None` and no enum restriction.

## Apply semantics

- If `mode=apply` and neither `start` nor `end` is provided, the DAG switches to `auto_apply_window=True`.
- In that path, the run resolves its own window from coverage state.
- `auto_apply_anchor_strategy` controls how the bootstrap window is chosen: `first-coverage`, `listing-date`, or `explicit`.
- `auto_apply_anchor` is only relevant for explicit anchoring.

## Result semantics

- A full successful `apply` result must be `verified=true`, with `remaining_gap_tasks=0`, `remaining_requested_bars=0`, and `verification_method=gap-detection`.
- Partial auto-apply is intentional current policy and is treated as `success-with-warning`, not a failure-state, when the summary truthfully reports `auto_apply_incomplete=true` and still has remaining work.
- Empty windows are only valid when they are genuine no-op results.

## Operator notes

- `apply` becomes `auto_apply_window=True` when both `start` and `end` are omitted.
- In auto-apply mode the DAG derives the repair window from coverage state instead of using a fixed operator-supplied window.
- `auto_apply_incomplete=true` means the run finished with remaining work still outstanding. Treat it as a partial apply, not a full repair.
- Airflow task state stays `success`; the operator signal comes through audit and metrics (`auto_apply_incomplete`, `remaining_gap_tasks`, `remaining_requested_bars`).
- Hard versus soft failure is intentionally not chosen here; the current policy is success with warning.
- The default anchor strategy is `first-coverage`; examples below use the same enums and defaults as the DAG.

## Anchor strategies

- `first-coverage`: start from the first uncovered point when there is existing coverage. This is the default and the safest general preset.
- `listing-date`: bootstrap from listing metadata when there is no coverage yet. Use this when the exchange listing date is the intended floor.
- `explicit`: bootstrap from `auto_apply_anchor`, which must be a UTC ISO-8601 timestamp.

## Operator presets

Use `timeframes` in new triggers. `timeframe` still works for compatibility, but it is legacy.

### Preview: bounded gap repair

```json
{
  "mode": "detect-only",
  "repair_strategy": "gap-repair",
  "timeframes": ["1m", "1H"],
  "start": "2026-04-01T00:00:00Z",
  "end": "2026-04-01T08:00:00Z",
  "padding_bars": 0
}
```

### Preview: rolling dry run

```json
{
  "mode": "dry-run",
  "repair_strategy": "backfill",
  "timeframes": ["4H", "1D"],
  "window_hours": 6,
  "max_range_days": 7
}
```

### Apply: explicit window

```json
{
  "mode": "apply",
  "repair_strategy": "gap-repair",
  "timeframes": ["1m"],
  "start": "2026-04-01T00:00:00Z",
  "end": "2026-04-01T08:00:00Z"
}
```

### Apply: auto-apply from first coverage

```json
{
  "mode": "apply",
  "repair_strategy": "gap-repair",
  "timeframes": ["1m", "1H"],
  "auto_apply_anchor_strategy": "first-coverage",
  "max_gap_tasks_per_run": 50,
  "max_requested_bars_per_run": 10000
}
```

### Apply: auto-apply from listing date

```json
{
  "mode": "apply",
  "repair_strategy": "backfill",
  "timeframes": ["1D"],
  "auto_apply_anchor_strategy": "listing-date",
  "max_range_days": 7
}
```

### Apply: auto-apply from explicit anchor

```json
{
  "mode": "apply",
  "repair_strategy": "gap-repair",
  "timeframes": ["1W"],
  "auto_apply_anchor_strategy": "explicit",
  "auto_apply_anchor": "2026-01-01T00:00:00Z"
}
```

### Apply: ETH-USDT-SWAP from listing date (multi-symbol)

```json
{
  "symbol": "ETH-USDT-SWAP",
  "mode": "apply",
  "repair_strategy": "backfill",
  "timeframes": ["1D", "1H"],
  "auto_apply_anchor_strategy": "listing-date",
  "max_range_days": 7
}
```

### Apply: SOL-USDT-SWAP gap repair (multi-symbol)

```json
{
  "symbol": "SOL-USDT-SWAP",
  "mode": "apply",
  "repair_strategy": "gap-repair",
  "timeframes": ["1m", "1H"],
  "auto_apply_anchor_strategy": "first-coverage",
  "max_gap_tasks_per_run": 50,
  "max_requested_bars_per_run": 10000
}
```

## SQL correctness layer (added 2026-04-19)

The following repository methods have been added to `RepairCandlesRepository` to align with the sql_summary contract:

- `list_missing_timestamps(symbol, tf, start_ts_ms, end_ts_ms, interval_ms)` — uses `generate_series` LEFT JOIN for fixed-interval TFs; domain helpers for 1M.
- `list_corrupted_timestamps(symbol, tf, start_ts_ms, end_ts_ms)` — NULL/≤0/high<low/open|close outside [low,high]; `volume=0` NOT corrupted.
- `is_features_ready(symbol, tf, closed_until_ts_ms, interval_ms)` — last 300 closed + contiguous + non-corrupted; 1M uses Python-side contiguity check.
- `merge_gaps(ts_list, interval_ms)` added to `src/candles/domain/repair.py`.

All existing repository methods (`list_timestamps`, `find_first_gap_start_ts_ms`, `count_candles`) are unchanged — the application layer continues to use them.

## Out of scope for v1

- Symbols not present in the `instruments` table will fail at preflight with `InstrumentNotFoundError`.
- Any timeframe outside the repair-safe set above.
- Unbounded or multi-symbol repair runs.
- Relaxed apply success criteria that accept unverified or remaining-gap apply summaries.
- Watermark updates from this DAG contract.

## Multi-symbol support (shipped in v1.1)

- `BTC-USDT-SWAP` hardcode removed from DAG `Param.default`; `symbol` is now a required field with no enum.
- `preflight_instrument_check` task added using `src.market_meta` module (primary: `instruments` table).
- `guardrail_risk` in preview changed from `bool` to `"ok"/"medium"/"high"` based on `requested_bars / max_requested_bars_per_run` ratio.
- `min_bars_for_window` utility added to `application/repair/planning.py` for auto-guardrail estimation.
- Per-symbol listing-date cache in `RepairCandlesRepository`.

## Plan vs actual

- Broader plan text may describe repair support more generally, and the CLI entrypoint is broader than the DAG trigger contract, but `okx_swap_repair_v1` itself is narrower and should be treated as the source of truth for manual runs.
- When updating the plan, keep `okx_swap_repair_v1` aligned with the enums and validation rules in `ops/airflow/dags/okx_swap_repair_v1.py`, `src/candles/domain/repair.py`, and the DAG tests.
