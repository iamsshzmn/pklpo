# OKX Swap Repair — Semantics Redesign Plan

> **Deliverable target:** this file lives at `history/planning/okx_swap_repair_semantics_redesign_plan_2026-04-21.md` as the working tracker. Agents update statuses in-place. Optionally copy / link from `docs/repair-redesign.md` once stabilized.
>
> **For agentic workers:** each task has a status field. Take one task at a time: flip `todo → in_progress` at start, `in_progress → done` at finish. Never batch-update. Every task ends with a verification step.

---

## Context

Current state (as of branch `feat/okx-swap-repair-unified`, 2026-04-21):
- `src/candles/application/repair/use_cases.py:131-133` hard-fails the DAG with `ValueError("apply exceeded max_fail_ratio")` whenever `(requested - written) / requested` exceeds `max_fail_ratio=0.1`. This conflates three distinct concerns: API quality, persistence quality, and progress over time.
- There is no `received` metric (API rows inside the target window), no explicit outcome class, and no per-iteration progress guard.
- Summary + audit only expose `rows_written`, `remaining_gap_tasks`, `remaining_requested_bars`, `verified`.
- Critical timeframes (1m, 1H) and lenient ones (1W, 1M) are treated identically.

Target state (per `history/planning/okx_swap_repair_semantics_summary_2026-04-21.md`):
- Outcome classes: `success | partial | empty | fail`. `partial` and `empty` are soft signals, not hard failures.
- Hard-stop only on (a) exceptions, (b) repeated no-progress on critical TFs.
- `progress = remaining_missing_before - remaining_missing_after`, computed from LEFT-JOIN grid (not `count(expected) - count(rows)`).
- Audit + metrics expose `requested, received, written, remaining_missing_before, remaining_missing_after, progress, api_fill_ratio, write_success_ratio, outcome`.

Goal of repair shifts from **"close every gap in one run"** to **"make steady forward progress over time under dirty API behavior"**.

### Policy defaults (confirmed 2026-04-21; overridable in DAG preset)
- `no_progress_threshold N = 3` consecutive no-progress iterations on a critical TF → raise.
- `critical_timeframes = {"1m", "1H"}`.
- Counter scope: **per-DAG-run, per-(symbol, timeframe)**, held in memory across tasks inside one use case invocation. Cross-run escalation deferred to dashboards/alerts.
- `api_fill_ratio` bands: warn `< 0.8`, alert `< 0.5` (observability only — not guardrails).
- `empty` without exception → no immediate local retry; idempotent next DAG run handles it.

### PR strategy (confirmed 2026-04-21)
- **PR1** covers этапы 0–4 (domain + use case): on branch `feat/okx-swap-repair-unified`.
- **PR2** covers этапы 5–8 (audit schema + DAG integration): branch `feat/okx-swap-repair-audit`.
- **PR3** covers этапы 9–11 (tests refresh + docs + deprecation cleanup): branch `feat/okx-swap-repair-finalize`.

---

## File-structure decisions (where new code lands)

| Area | File | Responsibility |
|---|---|---|
| Outcome enum + classifier | `src/candles/domain/repair.py` | `RepairOutcome` StrEnum + `classify_repair_outcome()` pure fn |
| No-progress policy | `src/candles/domain/repair.py` | `NoProgressPolicy` frozen dataclass |
| Progress counter utility | `src/candles/application/repair/progress.py` (new) | `NoProgressTracker` class + unit-testable state machine |
| Use case integration | `src/candles/application/repair/use_cases.py` | compute `received`, `missing_before/after`, outcome, thread tracker |
| DTO + summary | `src/candles/application/repair/dto.py`, `summary.py` | new fields on `RepairResult` / `RepairSummary` |
| Port extension (count only) | `src/candles/application/repair/ports.py` | `count_missing_timestamps()` on `CandleCoverageQueryPort` |
| Port impl | `src/candles/infrastructure/repair_repository.py` | implement `count_missing_timestamps()` |
| Audit schema | `src/db/migrations/migrate_extend_ops_swap_repair_audit_semantics.py` (new) | ADD COLUMNs + backfill default |
| Audit writer | `src/candles/infrastructure/repair_audit_repository.py`, `src/candles/interfaces/repair_audit.py` | persist new fields |
| Metrics | `src/candles/observability/prometheus.py` | new gauges + outcome-labeled counter |
| DAG wiring | `ops/airflow/dags/okx_swap_repair_v1.py` | new preset keys; XCom validator update |

---

## High-level этапы

0. **Documentation bootstrap** — ensure this plan is discoverable from `docs/`.
1. **Domain primitives** — `RepairOutcome`, `classify_repair_outcome()`, `NoProgressPolicy`.
2. **Port extension** — `count_missing_timestamps()` on the coverage query port.
3. **Progress tracker** — isolated state machine for no-progress escalation.
4. **Use case rewrite** — replace `fail_ratio` hard-stop with progress-based guard; compute `received`, outcome, ratios.
5. **DTO + summary extension** — new fields in `RepairResult` and `RepairSummary` (XCom round-trip).
6. **Audit schema migration + writer** — persist new fields to `ops.swap_repair_audit`.
7. **Observability** — Prometheus gauges + outcome counter + structured log fields.
8. **DAG integration** — preset keys, XCom validation, preset docs.
9. **Tests** — unit + integration, rewrite `test_apply_exceeded_max_fail_ratio`.
10. **Docs refresh** — update `okx_swap_repair_v1_plan_vs_actual.md`, DAG README.
11. **Deprecation cleanup** — remove `max_fail_ratio` after prod soak (post-release).

---

## Tasks

Format per task: **id · status · description · files · expected result · verification**

### Этап 0 · Documentation bootstrap

**Цель:** публикация плана в видимом для команды месте.

#### REPAIR-000
- **status:** todo
- **description:** Optional — add `docs/repair-redesign.md` as a pointer to this planning file (one line: link). Skip if the team prefers sourcing plans only from `history/planning/`.
- **files:** `docs/repair-redesign.md` (create, 3–5 lines of pointer content)
- **expected result:** single short markdown file linking to this plan.
- **verification:** `git show HEAD --stat` shows only `docs/repair-redesign.md`; pre-commit hooks on EOL/whitespace pass.

---

### Этап 1 · Domain primitives (PR1)

**Цель:** ввести типобезопасный `RepairOutcome`, функцию классификации и политику критических TF. Чистые изменения без I/O, полностью покрываемые юнит-тестами.

#### REPAIR-101
- **status:** done
- **description:** Add `RepairOutcome(StrEnum)` with values `SUCCESS = "success"`, `PARTIAL = "partial"`, `EMPTY = "empty"`, `FAIL = "fail"`.
- **files:** `src/candles/domain/repair.py` (add near existing enums, before `RepairWindow`)
- **expected result:** enum importable; `RepairOutcome("partial").value == "partial"`.
- **verification:** `python -c "from src.candles.domain.repair import RepairOutcome; print(list(RepairOutcome))"` lists 4 members.
- **commit:** `9156e6c`

#### REPAIR-102
- **status:** done
- **description:** Add pure function `classify_repair_outcome(*, requested: int, received: int, exception: bool) -> RepairOutcome` following the contract: `exception → FAIL`; `received == 0 and requested > 0 → EMPTY`; `0 < received < requested → PARTIAL`; `received >= requested → SUCCESS`; `requested == 0 and not exception → SUCCESS` (noop is success).
- **files:** `src/candles/domain/repair.py` (append below enum)
- **expected result:** function exists with type hints; raises nothing under any int/bool inputs.
- **verification:** new unit test `tests/candles/domain/test_repair_outcome.py` with ≥8 parametrized cases passes: `pytest tests/candles/domain/test_repair_outcome.py -v`.
- **commit:** `447e1dc` (10 parametrized cases green)

#### REPAIR-103
- **status:** done
- **description:** Add `NoProgressPolicy` frozen dataclass with fields `critical_timeframes: frozenset[str] = frozenset({"1m", "1H"})`, `no_progress_threshold: int = 3`; and method `is_critical(timeframe: str) -> bool`.
- **files:** `src/candles/domain/repair.py`
- **expected result:** dataclass immutable; default instance equals a second default instance.
- **verification:** unit test `tests/candles/domain/test_no_progress_policy.py`: default values, `is_critical("1m")` True, `is_critical("1D")` False, `frozen=True` prevents mutation — `pytest tests/candles/domain/test_no_progress_policy.py -v`.
- **commit:** `ca4aa37` (8 cases green)

#### REPAIR-104
- **status:** done
- **description:** Mark `RepairGuardrails.max_fail_ratio` as deprecated in the docstring (do NOT remove — preserve backward compat for one release cycle); keep the field on the dataclass for input, but it will stop being consulted by the use case in REPAIR-401.
- **files:** `src/candles/domain/repair.py:88-117`
- **expected result:** docstring clearly states: "Deprecated in 2026-04. Replaced by `NoProgressPolicy` + `RepairOutcome`. Scheduled for removal after 2026-07."
- **verification:** `grep -A2 "max_fail_ratio" src/candles/domain/repair.py` shows the deprecation note; existing tests still import the field without error.
- **commit:** `1dd861f` (48 domain tests still green)

---

### Этап 2 · Port extension (PR1)

**Цель:** добавить дешёвый `count_missing_timestamps()` на port, чтобы `remaining_missing_before/after` не зависели от fetch всех timestamps.

#### REPAIR-201
- **status:** done
- **description:** Add `async def count_missing_timestamps(self, *, symbol: str, timeframe: str, start_ts_ms: int, end_ts_ms: int) -> int: ...` to `CandleCoverageQueryPort` Protocol.
- **files:** `src/candles/application/repair/ports.py`
- **expected result:** Protocol method exists; mypy passes for all existing implementors OR they stub it.
- **verification:** `make typecheck` is green. If any concrete class doesn't implement it, add in REPAIR-202.
- **commit:** `2fd41a9` (Protocol change — no new mypy errors vs baseline; 4 pre-existing unrelated errors in planning.py/use_cases.py)

#### REPAIR-202
- **status:** done (codex)
- **description:** Implement `count_missing_timestamps()` on `RepairCandlesRepository` by reusing the existing `generate_series` LEFT JOIN IS NULL SQL in `list_missing_timestamps()` but wrapping with `COUNT(*)`. Preserve the `1M` fallback path (Python loop).
- **files:** `src/candles/infrastructure/repair_repository.py` (near lines 298-365)
- **expected result:** method returns int; on empty window returns 0; on fully-covered window returns 0.
- **verification:** integration test `tests/integration/test_repair_repository_missing_count.py` (new) hits a temp partition with one inserted bar inside a window of 10 expected slots → expects `9`. Run `pytest -m integration tests/integration/test_repair_repository_missing_count.py -v`.
- **commit:** `b59e94a` (`pytest --no-cov -m integration tests/integration/test_repair_repository_missing_count.py -v` green; plain `pytest` path was blocked by repo-wide `--cov-fail-under=85`)

---

### Этап 3 · Progress tracker utility (PR1)

**Цель:** изолировать state machine «no-progress counter» в отдельный модуль, чтобы use case остался тонким и тестируемым.

#### REPAIR-301
- **status:** done (codex)
- **description:** Create `src/candles/application/repair/progress.py` with class `NoProgressTracker` that holds `policy: NoProgressPolicy`, `timeframe: str`, internal `_consecutive: int`. Methods: `record(progress: int) -> None` (increments counter when `progress <= 0`, resets otherwise), `should_escalate() -> bool` (True when critical + counter reaches threshold), `snapshot() -> dict` (for logging/audit). Scope: per-DAG-run, in-memory only — no persistence, no audit-history lookup.
- **files:** `src/candles/application/repair/progress.py` (new)
- **expected result:** deterministic state machine; no I/O; all methods pure on internal state.
- **verification:** unit tests `tests/candles/application/test_no_progress_tracker.py` covering: reset on progress > 0, escalation at N=3 on 1m, no escalation on 1D, snapshot shape. `pytest tests/candles/application/test_no_progress_tracker.py -v` passes.
- **commit:** `b88613b` (`pytest --no-cov tests/candles/application/test_no_progress_tracker.py -v` and `ruff check src/candles/application/repair/progress.py tests/candles/application/test_no_progress_tracker.py` green)
---

### Этап 4 · Use case rewrite (PR1)

**Цель:** заменить `fail_ratio` на outcome-aware + progress-based логику без breaking API на входе.

#### REPAIR-401
- **status:** done (codex)
- **description:** In `_BaseRepairUseCase.run()`:
  1. Before the fetch loop: `remaining_missing_before = await self._coverage_query.count_missing_timestamps(...)` over the full `plan.window`.
  2. Inside the loop: accumulate `total_received` = `len(validated)` BEFORE upsert, and accumulate `total_written` (already done).
  3. After the loop: `remaining_missing_after = await self._coverage_query.count_missing_timestamps(...)` over the same window.
  4. Compute `progress = remaining_missing_before - remaining_missing_after` and `outcome = classify_repair_outcome(requested=plan.requested_bars, received=total_received, exception=False)`.
  5. Compute `api_fill_ratio = total_received / max(plan.requested_bars, 1)`, `write_success_ratio = total_written / max(total_received, 1)`.
  6. **Remove** the lines `fail_ratio = ...` and `raise ValueError("apply exceeded max_fail_ratio")` (lines 131-133).
  7. Feed `progress` into a `NoProgressTracker` instance (scoped to this run); if `tracker.should_escalate()` → `raise ValueError(f"no progress on critical TF {plan.timeframe}: {N} iterations in a row")`.
- **files:** `src/candles/application/repair/use_cases.py`
- **expected result:** exception cases shrink to real failures (DB/HTTP errors) + escalation on critical-TF no-progress; partial/empty no longer raise.
- **verification:** existing test `tests/candles/application/test_repair_use_cases.py::test_apply_exceeded_max_fail_ratio` will fail — that is expected (rewritten in REPAIR-902). New tests added in REPAIR-402 pass.
- **commit:** `e022693` (codex) + cleanup `e792f37` (removed dead `_ = (...)` lines after REPAIR-403 consumed them). Legacy `test_apply_raises_when_fail_ratio_exceeds_limit` expected-fails as designed; 10 other use-case tests green.

#### REPAIR-402
- **status:** done
- **description:** Add unit tests in `tests/candles/application/test_repair_use_cases.py`: `test_partial_api_fill_does_not_raise`, `test_empty_response_without_exception_does_not_raise`, `test_no_progress_escalation_on_1m_after_N_iterations` (simulate multi-iteration via auto-apply loop in `runner.py` or by calling the tracker directly), `test_success_outcome_fields_present_in_result`.
- **files:** `tests/candles/application/test_repair_use_cases.py`
- **expected result:** 4 new tests green; pre-existing success tests still green.
- **verification:** `pytest tests/candles/application/test_repair_use_cases.py -v` — all green except the soon-to-be-rewritten `test_apply_exceeded_max_fail_ratio`.
- **commit:** `336cfda` (4 new tests green + 7 pre-existing still green; legacy `test_apply_raises_when_fail_ratio_exceeds_limit` expected-fails per REPAIR-401)

#### REPAIR-403
- **status:** done (codex)
- **description:** Update the telemetry event `candles.repair.completed` payload in `use_cases.py:135-146` to include `requested`, `received`, `written`, `remaining_missing_before`, `remaining_missing_after`, `progress`, `api_fill_ratio`, `write_success_ratio`, `outcome`.
- **files:** `src/candles/application/repair/use_cases.py:135-146`
- **expected result:** event payload has all 9 new keys.
- **verification:** unit test `tests/candles/application/test_repair_telemetry.py` asserts the event payload keys — `pytest tests/candles/application/test_repair_telemetry.py -v`.
- **commit:** `97985a9` (codex) — `test_repair_completed_telemetry_includes_semantic_fields` green.

---

### Этап 5 · DTO + summary extension (PR2)

**Цель:** прокинуть новые поля через `RepairResult → RepairSummary → to_dict/from_mapping → XCom`, с обратной совместимостью на чтение старых payload'ов.

#### REPAIR-501
- **status:** done
- **commit:** bd2400a
- **description:** Extend `RepairResult` (in `dto.py`) with fields: `received_bars: int = 0`, `remaining_missing_before: int = 0`, `remaining_missing_after: int = 0`, `progress: int = 0`, `api_fill_ratio: float = 0.0`, `write_success_ratio: float = 0.0`, `outcome: RepairOutcome = RepairOutcome.SUCCESS`.
- **files:** `src/candles/application/repair/dto.py`
- **expected result:** dataclass `frozen=True` preserved; default values keep callers compiling.
- **verification:** `make typecheck` green; existing tests still construct `RepairResult` successfully.

#### REPAIR-502
- **status:** done
- **commit:** 5e5dcc1
- **description:** Extend `RepairSummary` with same fields; update `to_dict()`, `from_mapping()` round-trip, `from_result()`, `merge_repair_summaries()` (last-iteration semantics for `outcome`, sum for `received_bars`, last for `remaining_missing_after`, recompute `progress = remaining_missing_before_first - remaining_missing_after_last`).
- **files:** `src/candles/application/repair/summary.py`
- **expected result:** round-trip `RepairSummary → dict → RepairSummary` preserves all new fields; merge of 2 partial summaries yields `PARTIAL` outcome with correct progress.
- **verification:** expand `tests/candles/application/test_repair_summary.py` (or equivalent) with `test_summary_round_trip_includes_new_fields`, `test_merge_two_partial_summaries`. `pytest tests/candles/application/test_repair_summary.py -v` green.

#### REPAIR-503
- **status:** done
- **commit:** d8948ca
- **description:** `build_noop_repair_summary()` should set `outcome=RepairOutcome.SUCCESS`, `received_bars=0`, `remaining_missing_before=0`, `remaining_missing_after=0`, `progress=0`, ratios = 0.0.
- **files:** `src/candles/application/repair/summary.py:218-245`
- **expected result:** noop stays benign and explicit in audit.
- **verification:** unit test `test_noop_summary_outcome_is_success` passes.

---

### Этап 6 · Audit schema migration + writer (PR2)

**Цель:** persist новые поля в `ops.swap_repair_audit` с безопасной миграцией (nullable + default).

#### REPAIR-601
- **status:** done
- **commit:** 36ae8e0
- **description:** Create new migration `src/db/migrations/migrate_extend_ops_swap_repair_audit_semantics.py` adding columns: `outcome TEXT NULL`, `received_bars INTEGER NULL`, `remaining_missing_before INTEGER NULL`, `remaining_missing_after INTEGER NULL`, `progress INTEGER NULL`, `api_fill_ratio DOUBLE PRECISION NULL`, `write_success_ratio DOUBLE PRECISION NULL`. Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. No default, no backfill (historical rows stay NULL).
- **files:** `src/db/migrations/migrate_extend_ops_swap_repair_audit_semantics.py` (new)
- **expected result:** idempotent; can run twice without error.
- **verification:** apply via `python -m src.db.cli migrate` on a test DB; `psql -c "\\d ops.swap_repair_audit"` shows new columns nullable.

#### REPAIR-602
- **status:** done
- **commit:** ebf20f5
- **description:** Extend `SwapRepairAuditRepository.insert_records()` columns list + VALUES placeholders to include the 7 new fields. Read from `summary_payload` defensively (fall back to NULL if key missing — protects against old callers).
- **files:** `src/candles/infrastructure/repair_audit_repository.py:18-40`
- **expected result:** inserts new columns when payload has them; tolerates missing keys.
- **verification:** unit test `tests/candles/infrastructure/test_repair_audit_repository_new_fields.py` — insert with and without new fields; assert row contents via a stub connection.

#### REPAIR-603
- **status:** done
- **commit:** a6bb127
- **description:** Update `write_swap_repair_audit()` in `src/candles/interfaces/repair_audit.py` to pluck new fields out of `summary_payload` and attach them to the audit row dict passed to the repository.
- **files:** `src/candles/interfaces/repair_audit.py`
- **expected result:** audit row has 7 new keys when available.
- **verification:** `tests/candles/interfaces/test_repair_audit.py` — expand assertions to cover new keys. `pytest tests/candles/interfaces/test_repair_audit.py -v` green.

---

### Этап 7 · Observability — Prometheus + structured logs (PR2)

**Цель:** отделить сигнал прогресса от сигнала ошибки на уровне метрик.

#### REPAIR-701
- **status:** done
- **commit:** 91c1fb5
- **description:** In `src/candles/observability/prometheus.py:push_swap_repair_metrics`, add gauges: `pklpo_swap_repair_received_bars`, `pklpo_swap_repair_progress`, `pklpo_swap_repair_api_fill_ratio`, `pklpo_swap_repair_write_success_ratio`, `pklpo_swap_repair_remaining_missing_before`, `pklpo_swap_repair_remaining_missing_after`. Add counter-style gauge `pklpo_swap_repair_outcome_total{outcome=...}` incremented by 1 per summary.
- **files:** `src/candles/observability/prometheus.py:332-412`
- **expected result:** `pushgateway` receives new metric lines; old gauges still emitted.
- **verification:** unit test `tests/candles/observability/test_prometheus_swap_repair.py` — build a fake payload with new fields, capture pushed text, assert metric names present.

#### REPAIR-702
- **status:** done
- **commit:** 51bdbf1
- **description:** At the end of `_BaseRepairUseCase.run()`, emit a `logger.info("repair.outcome", extra={...})` with the full new field set. Prefix key names with `repair_` to avoid collision with other log fields.
- **files:** `src/candles/application/repair/use_cases.py`
- **expected result:** one structured log line per repair run, grep-able.
- **verification:** capture logs in `test_repair_use_cases.py` with `caplog`, assert keys present.

---

### Этап 8 · DAG integration (PR2)

**Цель:** поверхность оркестрации должна подхватить новые поля, не сломав existing XCom-контракт.

#### REPAIR-801
- **status:** done
- **commit:** 993f032
- **description:** In `ops/airflow/dags/okx_swap_repair_v1.py:REPAIR_TRIGGER_PRESETS`, replace / augment `"repair-all-swaps"` preset: remove reliance on `max_fail_ratio` (keep the key with value `1.0` for backward compat to signal "disabled"); add `"critical_timeframes": ["1m", "1H"]`, `"no_progress_threshold": 3`.
- **files:** `ops/airflow/dags/okx_swap_repair_v1.py:51-67`
- **expected result:** new preset loads without validation errors.
- **verification:** `pytest tests/db/test_okx_swap_repair_v1_dag.py -v` green; DAG import test `pytest tests/airflow/test_dags_import.py` green.

#### REPAIR-802
- **status:** done
- **description:** Thread `critical_timeframes` + `no_progress_threshold` from preset through to `RepairCommand` / use-case construction. Update `src/candles/application/repair/runner.py:_open_repair_runtime` and `src/candles/interfaces/repair.py:run_swap_repair` to accept and forward a `NoProgressPolicy`.
- **files:** `src/candles/application/repair/runner.py`, `src/candles/interfaces/repair.py`, `ops/airflow/dags/okx_swap_repair_v1.py`
- **expected result:** DAG can override defaults from preset.
- **verification:** DAG contract test checks that when preset sets `no_progress_threshold=1`, the tracker escalates immediately after one no-progress iteration.
- **commit:** `14b1d30` — `tests/db/test_okx_swap_repair_v1_dag.py::test_swap_repair_task_forwards_no_progress_policy_from_preset` + `test_run_swap_repair_once_forwards_no_progress_policy_from_preset` green; `critical_timeframes`/`no_progress_threshold` forwarded end-to-end from DAG preset → interface → `_open_repair_runtime` → `_build_no_progress_policy()` → `_build_repair_use_case`. (Also fixed `tests/candles/interfaces/test_repair.py` snapshot for REPAIR-501/502 carry-over.)

#### REPAIR-803
- **status:** done
- **description:** Update XCom validator `validate_swap_repair_xcom_payload()` to accept but not require new fields (soft validation: if key present, must be of correct type).
- **files:** `ops/airflow/dags/okx_swap_repair_v1.py` (search for `validate_swap_repair_xcom_payload`)
- **expected result:** backward-compatible read of old payloads; forward-compatible read of new.
- **verification:** unit test `tests/db/test_okx_swap_repair_v1_dag.py::test_xcom_accepts_new_fields` passes.
- **commit:** `e3251c4` — soft validation lives in `ops/airflow/dags/_common/repair.py`. 5 new tests green: accepts payload without new fields; accepts with new fields; rejects invalid outcome; rejects non-numeric `api_fill_ratio`; rejects non-integer `progress`.

#### REPAIR-804
- **status:** done
- **description:** Confirm DAG task retries: tasks should NOT retry on `ValueError("apply blocked by guardrails...")` or `ValueError("no progress on critical TF...")` — treat these as terminal fails. Transport exceptions (TimeoutError, HTTPError) should retry per existing DAG policy.
- **files:** `ops/airflow/dags/okx_swap_repair_v1.py`
- **expected result:** exit codes / `retry_delay` consistent with classification.
- **verification:** manual Airflow UI check on a dev instance: trigger DAG with `no_progress_threshold=1`, expect single failure, no retry loop.
- **commit:** _pending_ — `swap_repair_task` translates terminal `ValueError("apply blocked by guardrails" | "no progress on critical TF" ...)` to `AirflowFailException` (no retry). Other exceptions continue to propagate → global `retries: 2` still applies. 3 new unit tests cover both terminal prefixes + a transport-style `TimeoutError` passing through untranslated. Manual Airflow UI verification remains recommended per plan.

---

### Этап 9 · Tests refresh (PR3)

**Цель:** привести существующий test-suite в соответствие с новой семантикой.

#### REPAIR-901
- **status:** todo
- **description:** Rewrite `tests/candles/application/test_repair_use_cases.py::test_apply_exceeded_max_fail_ratio` → `test_no_progress_escalation_raises_on_critical_tf`. Keep the old test name deleted (not `xfail`) since the behavior is fundamentally changed.
- **files:** `tests/candles/application/test_repair_use_cases.py:378`
- **expected result:** new test asserts that only after N consecutive no-progress iterations on `1m`, `ValueError` is raised; single partial fill does NOT raise.
- **verification:** `pytest tests/candles/application/test_repair_use_cases.py::test_no_progress_escalation_raises_on_critical_tf -v` green.

#### REPAIR-902
- **status:** todo
- **description:** Add integration test `tests/integration/test_swap_repair_semantics.py` that exercises the full pipeline with a fake API returning: (a) full window → `success`, (b) half window → `partial`, no exception, (c) empty → `empty`, no exception, (d) 3 consecutive empty on 1m → exception.
- **files:** `tests/integration/test_swap_repair_semantics.py` (new)
- **expected result:** all four scenarios pass.
- **verification:** `pytest -m integration tests/integration/test_swap_repair_semantics.py -v`.

#### REPAIR-903
- **status:** todo
- **description:** Extend `tests/candles/interfaces/test_repair_audit.py` with a case asserting the new 7 fields reach the audit payload.
- **files:** `tests/candles/interfaces/test_repair_audit.py`
- **expected result:** test green; snapshot comparison matches.
- **verification:** `pytest tests/candles/interfaces/test_repair_audit.py -v`.

---

### Этап 10 · Docs refresh (PR3)

**Цель:** синхронизировать документацию с новой семантикой.

#### REPAIR-1001
- **status:** todo
- **description:** Update `docs/okx_swap_repair_v1_plan_vs_actual.md` (currently deleted on disk per `git status` — restore or recreate) to reflect the new outcome model, new metric names, and reference this plan.
- **files:** `docs/okx_swap_repair_v1_plan_vs_actual.md`
- **expected result:** doc exists, references the plan in `history/planning/`.
- **verification:** `git status` clean for docs; `grep -l "okx_swap_repair_semantics_redesign_plan" docs/` lists the file.

#### REPAIR-1002
- **status:** todo
- **description:** Update `ops/airflow/dags/README.md` to describe the new preset keys `critical_timeframes`, `no_progress_threshold`; note that `max_fail_ratio` is deprecated.
- **files:** `ops/airflow/dags/README.md`
- **expected result:** README lists every active preset key; deprecated note for `max_fail_ratio`.
- **verification:** reviewer grep + visual inspection.

---

### Этап 11 · Clean-up & hardening (PR3, post-soak)

**Цель:** после 1–2 недель прод-наблюдения убрать deprecated поле. Выполнять ТОЛЬКО после подтверждения стабильности.

#### REPAIR-1101
- **status:** blocked
- **blocked reason:** waiting for 1–2 week prod soak after PR2 release; unblock only after team sign-off.
- **description:** Remove `max_fail_ratio` field from `RepairGuardrails` in `src/candles/domain/repair.py`; remove the key from the DAG preset; remove from any remaining audit payload writers. One commit, breaking change — call it out in commit message.
- **files:** `src/candles/domain/repair.py`, `ops/airflow/dags/okx_swap_repair_v1.py`, any remaining references
- **expected result:** `grep -r max_fail_ratio src/ ops/ tests/` returns nothing.
- **verification:** `grep -r max_fail_ratio src/ ops/ tests/` empty; full `make check` green.

---

## Execution rules для агентов

1. **Brown-field protocol:** before starting any task, `git status` must be clean or contain only this plan's in-progress edits. Do not mix unrelated work.
2. **Atomic task ownership:** one task → one agent session. Flip status `todo → in_progress` in this plan file as the first action.
3. **One task at a time:** never update more than one task's status in the same commit. Exception: a task explicitly marked "depends on N, done together" (none in this plan).
4. **Status discipline:**
   - `todo` — not started.
   - `in_progress` — agent is actively working; must include the agent/session id in a footnote inside the task block if multiple agents run in parallel.
   - `done` — verification step passed; commit hash pasted in the task footnote.
   - `blocked` — something external prevents completion; footnote describes the block. Leave `in_progress` if work is paused but resumable.
5. **Verification is mandatory.** A task is NOT `done` until the exact verification command runs green and is recorded.
6. **Commit discipline:** one task = one (or a small set of closely-related) commits, conventional prefix (`feat:`, `refactor:`, `test:`, `docs:`, `chore:` per project convention).
7. **No architectural drift:** if a task can't be completed as written because a prerequisite is wrong, add a new sibling task (`REPAIR-xyz-bis`), leave the original `blocked`, and flag it in the PR.
8. **Tests-first within tasks:** where the task involves code + test, write the failing test first, then the implementation. Verification always runs the new tests.
9. **Do not touch `max_fail_ratio` removal (REPAIR-1101) before soak period.** Remains `blocked` until team confirms 1–2 weeks of stable prod.
10. **No plan edits beyond status / footnote fields** unless the current agent explicitly owns the "plan revision" side-task.

---

## Definition of Done (для всей фичи)

The redesign is considered complete when ALL of the following hold:

- [ ] `src/candles/domain/repair.py` exposes `RepairOutcome`, `classify_repair_outcome`, `NoProgressPolicy`.
- [ ] `_BaseRepairUseCase.run()` no longer contains the string `max_fail_ratio` or `"apply exceeded max_fail_ratio"`.
- [ ] `grep -r "fail_ratio" src/candles/` returns only deprecation docstrings in `domain/repair.py` (until REPAIR-1101).
- [ ] `RepairSummary.to_dict()` contains keys: `outcome, received_bars, remaining_missing_before, remaining_missing_after, progress, api_fill_ratio, write_success_ratio`.
- [ ] `ops.swap_repair_audit` has the 7 new columns (verified via `psql \d`).
- [ ] Prometheus pushgateway shows `pklpo_swap_repair_progress`, `pklpo_swap_repair_api_fill_ratio`, `pklpo_swap_repair_write_success_ratio`, `pklpo_swap_repair_outcome_total` after one DAG run.
- [ ] On a synthetic partial-API run the DAG task **succeeds** (outcome=partial), not fails.
- [ ] On a 3×-empty run on `1m` the DAG task **fails** with a `no progress on critical TF` exception.
- [ ] `make check` is green on feature branch.
- [ ] `okx_swap_repair_v1_plan_vs_actual.md` restored and updated.

---

## Риски и проверки

### Риски

| Риск | Где проявляется | Смягчение |
|---|---|---|
| Неправильный expected-grid → ложный «прогресс» | `list_missing_timestamps` SQL for non-standard TFs (`1M`, `1W`) | Port wrapper reuses existing `_list_missing_1m` fallback; integration test with edge window around month boundary (REPAIR-202). |
| Partition-routing race → `written=0` при `received>0` | Upsert path in `repair_repository.py` | `write_success_ratio < 1.0 with received > 0` визуально заметен в метриках; alert band при `< 0.95`. |
| XCom size взрыв | `RepairSummary.to_dict()` теперь больше | New fields are scalars (int/float); увеличение payload ~60 байт на сводку — незначительно. |
| Накопленный no-progress counter обнуляется между запусками DAG | `NoProgressTracker` scoped in-memory | Принято сознательно. Для пер-run escalation в будущем можно читать `progress` history из `ops.swap_repair_audit`. |
| Старые записи audit с NULL в новых колонках | Дашборды могут падать на division-by-null | В дашбордах использовать `COALESCE(progress, 0)`, `COALESCE(api_fill_ratio, 0.0)`. Задокументировать в REPAIR-1002. |
| Test flakes при integration тесте (реальная БД) | `tests/integration/test_swap_repair_semantics.py` | Использовать `pytest-asyncio` + transactional test fixture из `tests/conftest.py`. |

### Обязательные контрольные метрики/логи во время выката

1. `pklpo_swap_repair_outcome_total{outcome="fail"}` — должен оставаться при нуле вне известных инцидентов.
2. `pklpo_swap_repair_api_fill_ratio` — p50 не должен упасть ниже 0.8 после релиза (значит API деградировал).
3. `pklpo_swap_repair_progress` — отрицательные значения = индикатор обратного роста `missing`, требует немедленной триажа.
4. Структурный лог `repair.outcome` — должен присутствовать для каждой (symbol, timeframe, run) тройки.
5. Размер таблицы `ops.swap_repair_audit` растёт в ожидаемом темпе (не выросла по внесённым колонкам, т.к. INT/FLOAT nullable).
6. DAG SLA — общее wall-clock время не должно вырасти более чем на 10% (новая SQL для `count_missing_timestamps` — +2 дешёвых запроса на use case).

### Точки ручной SQL-валидации

```sql
-- после REPAIR-601
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'ops' AND table_name = 'swap_repair_audit'
  AND column_name IN ('outcome','received_bars','remaining_missing_before','remaining_missing_after','progress','api_fill_ratio','write_success_ratio');
-- expect 7 rows, all nullable.

-- после первого прод-запуска
SELECT outcome, COUNT(*), AVG(progress), AVG(api_fill_ratio), AVG(write_success_ratio)
FROM ops.swap_repair_audit
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY outcome;
-- sanity check: success+partial >> empty+fail, avg(progress) > 0 for success.
```

---

## Verification — end-to-end test plan

Once REPAIR-000 through REPAIR-903 are `done`, run:

```bash
# 1. Lint + types
make lint
make typecheck

# 2. Full test suite
make test
make test-all    # includes integration

# 3. Migration on dev DB
python -m src.db.cli migrate
psql "$PKLPO_DB_URL" -c "\\d ops.swap_repair_audit"

# 4. Smoke DAG run
python -m src.cli.main swap-repair --symbols BTC-USDT-SWAP --timeframe 1m --window 6h --dry-run
python -m src.cli.main swap-repair --symbols BTC-USDT-SWAP --timeframe 1m --window 6h --apply

# 5. Audit query
psql "$PKLPO_DB_URL" -c "
  SELECT outcome, symbol, timeframe, progress, api_fill_ratio, write_success_ratio
  FROM ops.swap_repair_audit
  ORDER BY created_at DESC LIMIT 10;
"
# expect: new columns populated on new rows; old rows NULL.

# 6. Prometheus check (if pushgateway configured)
curl -s http://$PUSHGATEWAY/metrics | grep -E 'pklpo_swap_repair_(progress|api_fill_ratio|outcome_total)'
```

All six steps must pass before declaring the redesign complete.
