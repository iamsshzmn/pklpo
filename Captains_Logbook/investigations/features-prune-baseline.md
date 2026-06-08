# features-prune baseline — Wave 0

**Date:** 2026-06-07  
**Branch:** features-prune  
**Commit:** 0dcd9a842cd50fe7e9972b04bf26a2e6027414e8  
**Tool:** `tools/dead_module_detector.py`

---

## File & line counts

| Scope | Files | Lines |
|-------|------:|------:|
| `src/features/` (all types) | 172 | 34 090 |
| `src/features/` (.py only) | 158 | 28 841 |
| Dead modules (no importers) | 15 | 2 648 |
| Live modules | 122 | — |

*Note: detector excludes `__init__.py` files by default (too many internal-only false positives).*

---

## Dead modules (detector output)

These 15 files have zero incoming imports from any file in `src/`, `tests/`, or `ops/`:

| File | Lines | Notes |
|------|------:|-------|
| `src/features/__main__.py` | 80 | CLI entry — callable via `python -m features`, not imported |
| `src/features/backfill.py` | 7 | Thin shim? Check if superseded |
| `src/features/cli/check_database_setup.py` | 256 | CLI utility, run directly |
| `src/features/cli/main.py` | 558 | CLI entry point |
| `src/features/cli/schema_check.py` | 351 | CLI utility (`schema_check` command) |
| `src/features/domain/indicator_specs.py` | 24 | Check vs `specs/*.py` — likely superseded |
| `src/features/infrastructure/diagnostics.py` | 106 | Diagnostic helper — used? |
| `src/features/infrastructure/indicator_registry.py` | 15 | Likely superseded by `registry/` package |
| `src/features/infrastructure/insert_indicators.py` | 10 | Tiny shim — check usage |
| `src/features/infrastructure/snapshot_manager.py` | 291 | Snapshot infra — used in DAGs? |
| `src/features/metrics.py` | 7 | Top-level shim — check if re-exported |
| `src/features/observability/indicators_logging.py` | 264 | **Wave 2 target** — duplicate logger |
| `src/features/observability/logging.py` | 332 | **Wave 2 target** — duplicate logger |
| `src/features/tests/conftest.py` | 15 | Internal test fixture — fine |
| `src/features/tools/generate_schema.py` | 332 | Dev tool, run directly |

---

## Schema YAMLs (Wave 1 targets, non-.py)

| File | Lines | Status |
|------|------:|-------|
| `schema/indicators_schema_clean.yml` | 980 | **Dead** — 0 importers anywhere (Wave 1 delete) |
| `schema/indicators_schema_complete.yml` | 1049 | Used only by migration `migrate_expand_indicators_precision.py` (frozen input) |
| `schema/indicators_schema.yml` | 1069 | **Live** — source of truth; read by domain + cli |

---

## Wave targets summary

| Wave | Target | Expected reduction |
|------|--------|--------------------|
| Wave 1 | `schema_clean.yml` deleted; `schema_complete.yml` annotated | ~−1 000 lines |
| Wave 2 | Observability consolidation | ~−1 200..1 500 lines |
| Wave 3 | Naming/normalization unification | ~−600..900 lines |
| Wave 4 | Infrastructure upsert + alerts | ~−1 500..2 000 lines |
| Wave 5 | Core group_* + validation | ~−1 500..2 000 lines |
| **Target** | | **~11–13k lines** |

---

## Gate status

- [x] Baseline metric recorded
- [x] Dead-module detector written (`tools/dead_module_detector.py`)
- [ ] Pipeline smoke run (manual — run `python -m src.cli.main features` on 2–3 instruments before Wave 1)

---

## Final baseline — after Waves 1–5

**Date:** 2026-06-07  
**Last commit:** `4dd6829`

| Scope | Baseline (Wave 0) | After Wave 5 | Delta |
|-------|------------------:|-------------:|------:|
| `src/features/` (all types) | 172 files / 34 090 lines | — / 28 603 lines | −5 487 |
| `src/features/` (.py only) | 158 files / 28 841 lines | 147 files / 26 496 lines | −11 files / −2 345 lines |
| Dead modules (no importers) | 15 files / 2 648 lines | 8 files / 1 623 lines | −7 files / −1 025 lines |

### Per-wave commit log

| Wave | Коммит | Изменение |
|------|--------|-----------|
| Wave 1 | `7b045b6` | −980 lines (schema_clean.yml deleted; schema_complete.yml annotated) |
| Wave 2 | `7645c25` | −1 232 lines (observability facade: 4 logging/error files) |
| Wave 3 | `357a997` | −762 lines (deprecated name_mapping.py + its tests) |
| Wave 4 | `0e49680` | −147 lines (upsert_builder facade; alerts.py dead blocks) |
| Wave 5 | `4dd6829` | −574 lines (group_calculation facade; 5 dead infra stubs) |
| **Total** | | **−3 695 lines** |

### Remaining dead modules (8 files / 1 623 lines)

Intentionally kept — all are CLI entry points or dev tools run directly:

| File | Lines | Reason kept |
|------|------:|-------------|
| `__main__.py` | 80 | `python -m features` entry point |
| `backfill.py` | 7 | `sys.modules` alias — tests patch `src.features.backfill.*` |
| `cli/check_database_setup.py` | 256 | CLI utility, run directly |
| `cli/main.py` | 558 | CLI entry point |
| `cli/schema_check.py` | 351 | CLI utility |
| `domain/indicator_specs.py` | 24 | Potentially superseded — capability track |
| `tests/conftest.py` | 15 | Internal test fixture |
| `tools/generate_schema.py` | 332 | Dev tool |

### Key discovery: upsert_optimizer is a simulation stub

`infrastructure/upsert_optimizer.py` (297 lines) calls `_simulate_database_operation()`
which uses `time.sleep()` and never touches the DB. Merging with the real upsert path
would change behavior — deferred to capability-pruning track.

### Forecasts vs actuals

| Wave | Forecast | Actual | Gap reason |
|------|----------|--------|------------|
| Wave 1 | ~−1 000 | −980 | YAML only |
| Wave 2 | ~−1 200..1 500 | −1 232 | On target |
| Wave 3 | ~−600..900 | −762 | On target |
| Wave 4 | ~−1 500..2 000 | −147 | upsert_optimizer is a stub, not real path |
| Wave 5 | ~−1 500..2 000 | −574 | Validators have distinct contracts, no safe merge |
