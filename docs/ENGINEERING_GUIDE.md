# ENGINEERING GUIDE — PKLPO

> **Source of truth** for architecture, engineering principles, and active development tasks.
> Read this before writing code. Update it when decisions change.

---

## Table of Contents

1. [Project Purpose](#1-project-purpose)
2. [Architectural Principles](#2-architectural-principles)
3. [Development Methodology](#3-development-methodology)
4. [Programming Paradigms](#4-programming-paradigms)
5. [SOLID Principles](#5-solid-principles)
6. [Component Principles](#6-component-principles)
7. [Dependency Principles](#7-dependency-principles)
8. [Module Architecture](#8-module-architecture)
9. [Modularity Rules](#9-modularity-rules)
10. [Architectural Patterns](#10-architectural-patterns)
11. [Event Sourcing](#11-event-sourcing)
12. [Technical Engineering Rules](#12-technical-engineering-rules)
13. [Current Tasks](#13-current-tasks)
14. [Future Tasks](#14-future-tasks)
15. [Quality Criteria](#15-quality-criteria)

---

## 1. Project Purpose

### Problem Statement

Financial markets produce continuous streams of price and volume data. Extracting actionable analytical signals from this data requires: reliable ingestion, consistent feature engineering, statistically sound signal generation, and disciplined risk control. Building all of this in an ad-hoc manner leads to look-ahead bias, untestable code, and fragile production pipelines.

PKLPO is a **quantitative crypto market analysis platform** that solves this by providing a clean, reproducible pipeline from raw market data to analytical signals.

### Main Pipeline

```
market_data → features → mtf_context → signals → risk → execution → positions
```

Each stage has a single responsibility and communicates with the next via a typed contract (port). No stage reaches backwards in the pipeline.

### Core Modules

| Module | Responsibility |
|--------|----------------|
| `market_data` | Ingest, validate, and store OHLCV / L2 / OI / funding data |
| `features` | Calculate 500+ technical indicators — pure computation, no side effects |
| `mtf_context` | Determine market regime and consensus across timeframes |
| `signals` | Generate typed Signal objects (entry / stop / take / confidence) |
| `risk` | Position sizing, exposure limits, kill-switch, guards |
| `execution` | Unified execution path for backtest / paper / live |
| `positions` | Event-sourced position state, PnL, lifecycle |
| `backtest` | Walk-forward / OOS / CPCV evaluation, research artifacts |
| `platform` | Config, migrations, orchestration, observability |

---

## 2. Architectural Principles

> **Theoretical foundation:** See [`ARCHITECTURE_GUIDE.md`](./ARCHITECTURE_GUIDE.md) for the complete set of Clean Architecture principles, SOLID, component cohesion/coupling rules, key patterns, and anti-patterns. This section defines **how those principles apply to PKLPO specifically**.

### Clean Architecture (Robert C. Martin)

The system is organized in concentric layers. Inner layers know nothing about outer layers. Outer layers depend on inner layers through **interfaces (ports)**, never through concrete implementations.

```
         ┌─────────────────────────────────┐
         │         interfaces / CLI        │  ← outermost: adapters
         │   ┌─────────────────────────┐   │
         │   │      application        │   │  ← use-cases, orchestration
         │   │   ┌─────────────────┐   │   │
         │   │   │     domain      │   │   │  ← entities, rules, no deps
         │   │   └─────────────────┘   │   │
         │   └─────────────────────────┘   │
         │        infrastructure           │  ← DB, APIs, queues
         └─────────────────────────────────┘
```

### Dependency Rule

**Source-code dependencies must point inward only.**

- `interfaces` depends on `application`
- `application` depends on `domain`
- `infrastructure` implements `ports` defined in `domain` / `application`
- `domain` depends on **nothing** in the project

Violations of the Dependency Rule are build-breaking errors, enforced in CI via import-graph checks.

### Layer Definitions

| Layer | Contains | May Import |
|-------|----------|------------|
| `domain` | Entities, value objects, domain services, invariants | stdlib only |
| `application` | Use-cases, orchestration, ports (interfaces) | `domain` |
| `ports` | Abstract interfaces (Repository, Client, Publisher) | `domain` |
| `infrastructure` | DB adapters, API clients, queue consumers | `ports`, `domain` |
| `interfaces` | CLI handlers, Airflow DAGs, REST endpoints | `application` |

---

## 3. Development Methodology

### Test-Driven Development (TDD)

All new code is written test-first. No exceptions for business logic.

**The cycle:**

```
1. RED   — write a failing test that describes the desired behavior
2. GREEN — write the minimum code to make the test pass
3. REFACTOR — clean up without breaking tests
```

**Rules:**
- Never write production code before a failing test exists.
- Each test covers one behavior, not one function.
- Tests in `domain` and `application` layers must not touch the database or network.
- Use fakes / stubs at layer boundaries; only integration tests hit real infrastructure.

**Coverage targets:**
- Total: 85% minimum
- Changed lines: 90% minimum
- `domain` layer: 100%

### Definition of Ready

Before starting any task:
- [ ] Affected bounded context is identified
- [ ] Contracts that change are listed
- [ ] Test plan exists (unit + integration + architecture checks)
- [ ] Migration strategy is defined (no downtime, no broken DAGs)

### Definition of Done

A task is done when:
- [ ] Tests written and passing (`pytest`)
- [ ] Type-checked (`mypy src/`)
- [ ] Linted (`ruff check src/`)
- [ ] Architecture constraints pass (no new forbidden imports)
- [ ] ADR written if an architectural decision was made
- [ ] Docs updated if public API changed

---

## 4. Programming Paradigms

### Structured Programming

- No `goto`, no unstructured control flow.
- Control flow via **sequence**, **selection** (`if`/`match`), and **iteration** (`for`/`while`).
- Functions are small, have a single entry point, and a single return (or clearly structured early returns).
- Max function length: **25 lines**. Max nesting: **2 levels**.

### Object-Oriented Programming

- Classes represent domain concepts, not procedural bags of functions.
- **Depend on abstractions (protocols / ABCs), not concretions.**
- Inversion of control: high-level modules define ports; infrastructure provides adapters.
- Favor composition over inheritance. Inheritance only for true is-a relationships.

### Functional Elements

- Minimize mutable state. Prefer returning new objects over mutating existing ones.
- Pure functions (no side effects) for all calculations in `features` and `domain`.
- Avoid shared mutable state across async tasks — eliminates race conditions.
- Pandas DataFrames inside a function are treated as immutable; use `.copy()` before mutation.

---

## 5. SOLID Principles

### SRP — Single Responsibility Principle

> A module has one, and only one, reason to change.

- `features/core/calculation.py` — only computes indicators; never writes to DB.
- `features/infrastructure/persistence/inserter.py` — only persists; never computes.
- If a class needs two imports from different domains, it probably has two responsibilities.

### OCP — Open/Closed Principle

> Open for extension, closed for modification.

- Adding a new indicator group means creating a new file in `indicator_groups/`, registering it in `registry.py`. No existing code changes.
- Adding a new execution mode (paper → live) means adding an adapter, not editing `ExecutionService`.

### LSP — Liskov Substitution Principle

> Subtypes must be substitutable for their base types.

- All `Repository` implementations must honor the contract of the port.
- `BacktestExecutionAdapter` and `LiveExecutionAdapter` are interchangeable behind `ExecutionServicePort`.
- Tests that pass with a fake adapter must also pass with the real adapter.

### ISP — Interface Segregation Principle

> Clients should not depend on interfaces they do not use.

- `FeatureProviderPort` only exposes `get_features()`. Callers do not see DB handles or connection pools.
- Split wide interfaces into focused protocols. Use `typing.Protocol` with `@runtime_checkable`.

### DIP — Dependency Inversion Principle

> High-level modules should not depend on low-level modules. Both should depend on abstractions.

- `signals` depends on `FeatureProviderPort`, not on `src.features.infrastructure.database`.
- Concrete implementations are wired in `container.py` or Airflow DAG setup — never inside domain / application code.

---

## 6. Component Principles

### REP — Reuse / Release Equivalency Principle

> The granule of reuse is the granule of release.

- Everything released together must be designed to be reused together.
- Don't mix stable domain models with volatile infrastructure code in the same package.

### CCP — Common Closure Principle

> Classes that change together belong together.

- All indicator calculation logic lives in `features/`. When a new indicator standard changes, only `features/` changes.
- Infrastructure persistence code for features lives in `features/infrastructure/`, not in a shared `utils/`.

### CRP — Common Reuse Principle

> Don't force users of a component to depend on things they don't need.

- `features/core` can be imported without pulling in DB drivers.
- `compute_features()` has zero infrastructure dependencies — it is a pure pandas transformation.

---

## 7. Dependency Principles

### ADP — Acyclic Dependencies Principle

> The dependency graph of components must have no cycles.

- CI runs an import-graph check. Any cycle between bounded contexts is a build failure.
- Known controlled exception: `features/__main__.py` uses a lazy import of `cli` — documented, not propagated.
- Fix cycles by extracting a shared abstraction that both sides depend on, not by adding more imports.

### SDP — Stable Dependencies Principle

> Depend in the direction of stability.

- `domain` is the most stable layer — it has no dependencies, so nothing forces it to change.
- `infrastructure` is the least stable — it changes with library versions, DB schemas, API changes.
- Never let `domain` import from `infrastructure`.

### SAP — Stable Abstractions Principle

> The more stable a component, the more abstract it should be.

- `domain` contains only abstract protocols and pure value objects — maximally abstract, maximally stable.
- `infrastructure` contains only concrete implementations — maximally concrete, minimally stable.

---

## 8. Module Architecture

### Target Structure

```
src/
  market_data/
    domain/          # OHLCV entity, freshness rules
    application/     # ingest use-cases, watermark logic
    ports/           # ExchangeClientPort, OHLCVRepositoryPort
    infrastructure/  # OKX client, asyncpg adapters
    interfaces/      # CLI sync commands, Airflow DAG tasks

  features/
    domain/          # FeatureSpec, IndicatorGroup protocols
    application/     # calc.py, save.py, backfill.py use-cases
    ports/           # FeatureProviderPort, FeatureRepositoryPort
    infrastructure/  # DB persistence, upsert, versioning
    interfaces/      # features CLI

  mtf_context/
    domain/          # MarketRegime, ConsensusDecision
    application/     # context builder, trigger engine, consensus
    ports/           # ConsensusProviderPort
    infrastructure/  # DB adapter
    interfaces/      # Airflow DAG tasks

  signals/
    domain/          # Signal, SignalDirection, CostModel
    application/     # signal generation use-case
    ports/           # SignalServicePort
    infrastructure/  # signals DB adapter
    interfaces/      # CLI / API

  risk/
    domain/          # RiskDecision, limits, guards
    application/     # risk evaluation use-case
    ports/           # RiskServicePort, PortfolioStatePort
    infrastructure/  # kill-switch, circuit breaker
    interfaces/      # risk CLI / monitoring

  execution/
    domain/          # OrderIntent, ExecutionEvent, CostModel
    application/     # execution orchestration
    ports/           # ExecutionServicePort
    infrastructure/  # backtest adapter, paper adapter, live adapter
    interfaces/      # execution API

  positions/
    domain/          # Position, PnL, lifecycle events
    application/     # event processor, reporting
    ports/           # PositionStorePort
    infrastructure/  # event store DB adapter
    interfaces/      # positions API / CLI

  backtest/
    domain/          # BacktestRun, WalkForward, CPCV config
    application/     # evaluation orchestration
    ports/           # (reuses ports from other contexts)
    infrastructure/  # artifact storage
    interfaces/      # backtest CLI / reports

  platform/
    config/          # Pydantic Settings, env loading
    migrations/      # DB schema migrations
    orchestration/   # Airflow DAGs, schedulers
    observability/   # logging, metrics (Prometheus), alerting
```

### Module Responsibility Matrix

| Module | Owns | Depends On | Must NOT Import |
|--------|------|------------|-----------------|
| `market_data` | OHLCV ingest + storage | `platform` | any downstream module |
| `features` | Indicator calculation | `market_data` read-model | `signals`, `risk`, `execution` |
| `mtf_context` | Regime + consensus | `features`, `market_data` | `signals`, `risk`, `execution` |
| `signals` | Signal generation | `mtf_context`, `market_data` | `execution`, `positions` |
| `risk` | Sizing + guards | `signals`, `positions` | `market_data` raw ingest |
| `execution` | Order execution | `risk` (order intent only) | `signals` internals, `mtf` internals |
| `positions` | Position state + PnL | `execution` events | upstream pipeline modules |
| `backtest` | Strategy evaluation | all pipeline modules | production infrastructure |
| `platform` | Infra wiring | all modules (infra only) | must not contain business logic |

---

## 9. Modularity Rules

1. **One module = one reason to change.** If two unrelated requirements both touch a module, split it.
2. **One module = one business capability.** Features module calculates indicators. It does not send alerts, manage positions, or configure the DB schema.
3. **No cyclic dependencies between bounded contexts.** Enforced by CI.
4. **Dependencies flow inward.** `infrastructure → ports → application → domain`.
5. **Public API is explicit.** Every module exposes a minimal `__init__.py` or `ports/` interface. Internal implementation is private.
6. **No shared mutable globals.** Configuration is passed as typed `Settings`; no module-level singletons that are mutated at runtime.
7. **Modules max 400 lines.** If a file exceeds 400 lines, split by responsibility.

---

## 10. Architectural Patterns

### Humble Object Pattern

Separate code that is hard to test (I/O, DB, network) from code that is easy to test (logic).

- `compute_features(df)` — pure function, testable with a DataFrame fixture.
- `FeatureCalcService.run(symbol, tf)` — orchestrates I/O; tested via integration tests only.
- Keep I/O boundaries thin ("humble"); keep logic thick and fully unit-tested.

### Strategy Pattern

Encapsulate interchangeable algorithms behind a common interface.

- `ExecutionServicePort` is implemented by `BacktestExecutionAdapter`, `PaperExecutionAdapter`, `LiveExecutionAdapter`.
- `IndicatorGroup` protocol is implemented by each of the 10 indicator group classes.
- The caller is unaware of which strategy is active; it is injected at construction time.

### Facade Pattern

Provide a simplified interface to a complex subsystem.

- `compute_features(df, specs)` is a facade over the 10 indicator groups, dependency resolver, and chunking engine.
- `FeatureService.calculate(symbol, timeframe)` is a facade over watermark lookup, OHLCV fetch, compute, and persist.
- CLI commands are thin facades over application use-cases.

### Repository Pattern

Abstract data access behind a typed interface; callers never write SQL.

- `OHLCVRepositoryPort.get(symbol, tf, from_ts, to_ts) -> pd.DataFrame`
- `FeatureRepositoryPort.upsert(df, symbol, tf) -> None`
- `PositionStorePort.append(events)`, `.get_open_positions()`
- Implementations in `infrastructure/`; ports defined in `ports/` (or `domain/`).

---

## 11. Event Sourcing

### Concept

Instead of storing current state, store the **sequence of events** that produced it. Current state is derived by replaying events.

### Application in PKLPO

`positions` context uses event sourcing:
- `ExecutionEvent` records are appended to an immutable event log.
- Current position state is derived by replaying events for a given `run_id`.
- This enables: full audit trail, point-in-time replay, bug reproduction from production data.

### Principles

- Events are **immutable** — never update or delete an event record.
- Events carry `run_id`, `algo_version`, `params_hash`, `snapshot_id` for full reproducibility.
- Projections (read models) are rebuilt from the event log on demand.

---

## 12. Technical Engineering Rules

### Typing

- Type hints on all function signatures and class attributes.
- `mypy` passes with no errors (strict mode for `domain` and `application` layers).
- Use `typing.Protocol` for ports, not `abc.ABC` with inheritance.
- No `Any` in domain or application layers. `Any` is allowed only in infrastructure adapters for external library compatibility.

### State Management

- No module-level mutable state.
- Configuration via `Settings` objects passed explicitly; no `os.environ` calls inside business logic.
- Thread/async safety: no shared mutable objects across concurrent tasks.

### Logging

- Every pipeline step logs: start, completion, row counts, timing, and any anomalies.
- Use structured logging (key=value pairs), not format strings.
- Log at the `application` boundary; do not litter `domain` with log statements.
- Log levels: `DEBUG` for per-row details, `INFO` for pipeline milestones, `WARNING` for degraded operation, `ERROR` for failures.

### Idempotency

- All DB writes use `INSERT ... ON CONFLICT DO UPDATE` (UPSERT).
- Pipeline steps can be re-run without producing duplicate records or corrupted state.
- Watermark-based incremental updates: always check `MAX(timestamp)` before fetching.

### Reproducibility

- Every calculation run is tagged with `run_id`, `algo_version`, `params_hash`.
- No look-ahead bias: data is read only up to the timestamp of the closed bar.
- Given the same inputs and versions, the system produces identical outputs.

### Safety Conventions

- Destructive operations (migrations, bulk deletes, schema changes) default to **dry-run**.
- Use `--apply` flag to execute actual changes.
- Always print the execution plan before any destructive action.

### Data Quality — Fail-Loud Policy

*(Added: features-prune-v2 V1, 2026-06-08)*

- **Data quality anomalies are terminal, not silent.** Conditions listed below must raise
  an exception or return a hard failure — never silently zero-fill, replace with NaN, or
  continue with degraded data.
- **Terminal conditions** (gate_validator is the enforcement point):
  - `len(df) < GateConfig.min_rows` before DB write
  - `nan_ratio(feature_group) > GateConfig.max_nan_ratio` before DB write
  - `fill_rate < GateConfig.min_fill_rate` before DB write
  - `coverage_pct < 99.5` (check `candle_eligibility`, do not join features)
- **NaN outside bootstrap period** is a bug, not expected output. Log as ERROR.
- **Ambiguous anomalies** (partial data, unknown instrument): log as WARNING and skip
  that instrument — do not write partial rows to `indicators_p`.
- **ORDER BY requirement**: every SQL read from `indicators_p`, `candles_swap_1h`, or
  `features_*` tables that feeds calculation must ORDER BY `(open_time, instrument_id)`
  or equivalent stable key. Reads without ORDER BY must include an explicit comment
  explaining why order is irrelevant (e.g., scalar aggregates).

---

## 13. Current Tasks

### CT-001: Stabilize `features` refactoring (branch: `features_refactoring`)

**Description:** Major refactoring of `src/features/` to align with the target Clean Architecture model. Core layers (`domain`, `application`, `infrastructure`, `indicator_groups`) have been restructured.

**Goal:** Complete the refactoring, ensure all imports resolve, tests pass, and CI is green.

**Expected Result:**
- `mypy src/features/` passes with no errors
- `pytest` passes
- `ruff check src/features/` passes
- No new forbidden cross-context imports
- PR merged to `main`

---

### CT-002: Implement Architecture Fitness Functions in CI

**Description:** The `.github/workflows/ci.yml` does not yet enforce import-graph constraints between bounded contexts.

**Goal:** Add automated checks that fail the build if forbidden dependencies are introduced.

**Expected Result:**
- CI step runs `import-linter` or equivalent
- Forbidden imports from `TARGET_ARCHITECTURE.md §5` are enforced
- Cycle detection between contexts runs on every PR

---

### CT-003: Formalize Port Contracts

**Description:** The 6 core ports defined in `TARGET_ARCHITECTURE.md §6` exist as concepts but are not all implemented as typed `Protocol` classes.

**Goal:** Create `ports/` submodule in each bounded context with typed protocol definitions.

**Expected Result:**
- `FeatureProviderPort`, `ConsensusProviderPort`, `SignalServicePort`, `RiskServicePort`, `ExecutionServicePort`, `PositionStorePort`, `MetricsPort` all exist as `typing.Protocol` classes
- All existing implementations satisfy the protocols (verified by `mypy`)

---

### CT-004: Migrate from Legacy OHLCV Tables

**Description:** Code currently has two OHLCV tables: `ohlcv` (empty, legacy) and `swap_ohlcv_p` (active). The SQLAlchemy `OHLCV` model points to the wrong table, requiring a fragile fallback in `fetch_ohlcv_df`.

**Goal:** Align model with actual table, remove the fallback, document the final DB schema.

**Expected Result:**
- `OHLCV` model maps to `swap_ohlcv_p` directly
- `fetch_ohlcv_df` has no fallback logic
- Legacy table references removed or clearly marked with migration path

---

### CT-005: Remove Circular CLI Dependency

**Description:** `src/features/__main__.py` has a lazy import of `src.cli` — documented but not resolved.

**Goal:** Eliminate the circular dependency by restructuring the entry point.

**Expected Result:**
- `features/__main__.py` does not import from `src.cli`
- Import graph is clean between `features` and `cli`
- CI import-graph check covers this boundary

---

### CT-006: Bootstrap State Reconciliation ✅ DONE 2026-05-15

**Description:** `ops.swap_ohlcv_bootstrap_state` could permanently diverge from `swap_ohlcv_p`. Once `bootstrap_completed=true` was set, the system never re-verified actual row counts — returning hardcoded `coverage=100%, missing=0` from a stale cache.

**Root cause:** Early-exit in `RunBootstrapUseCase.run()` trusted the state table unconditionally. After any row deletion from `swap_ohlcv_p` (cleanup, partition drop), the state remained stuck at `completed`.

**Fixed in `feat/okx-swap-repair-unified`:**
- `use_cases.py`: early-exit now performs live `count_candles` against `swap_ohlcv_p` before returning. If `live_actual < expected_bars`, state is downgraded to `incomplete` and re-fetch starts from `target_end_ts`.
- `interfaces/bootstrap.py`: `init_bootstrap_state` also reconciles `bootstrap_completed=True` pairs with live counts. New `reconcile_bootstrap_state()` for operational use.
- Tests: `test_completed_state_reconciles_when_db_diverges`, `test_completed_state_reconciles_partial_divergence`.

**Invariant established:** `swap_ohlcv_p` is the source of truth. `bootstrap_state` is cache + checkpoint. See `ARCHITECTURE.md §13`.

---

## 14. Future Tasks

### FT-001: Unified Execution Path (Backtest / Paper / Live)

Implement `ExecutionServicePort` with three adapters that share a single `CostModel`. Backtest currently uses different code paths than paper/live. Unify under one interface to eliminate divergence bugs.

---

### FT-002: `mtf_context` Context Extraction

`src/mtf/` contains mixed orchestration and business logic. Extract into a clean `mtf_context` bounded context with `domain/`, `application/`, `ports/`, `infrastructure/` layers per the target architecture.

---

### FT-003: `market_data` Context Formalization

`src/candles/` and `src/market_meta/` should merge into a single `market_data` bounded context. Standardize the OHLCV ingest port and replace ad-hoc DB calls with a typed repository.

---

### FT-004: Observability Platform

Build out `platform/observability/`:
- Structured logging with correlation IDs (`run_id`, `symbol`, `timeframe`)
- Prometheus metrics for pipeline throughput, lag, error rates
- Alerting rules (Slack / PagerDuty) for freshness violations and kill-switch events

---

### FT-005: Walk-Forward Backtesting Engine

Implement the `backtest` context with:
- Walk-forward / OOS split configuration
- CPCV (Combinatorially Purged Cross-Validation)
- DSR (Deflated Sharpe Ratio) calculation
- Artifact storage for reproducible research runs

---

### FT-006: ML Feature Pipeline Integration

Add an ML-ready feature export path:
- Export `FeatureFrame` to parquet with consistent schema versioning
- Label generation (forward returns, volatility regimes)
- Integration point for sklearn / lightgbm pipelines without polluting `features` domain

---

### FT-007: ADR Archive

ADRs live in `Captains_Logbook/done/YYYY/MM/adr/`. Written so far:
- ✅ `ADR-2026-05-03` — last N closed bars architecture
- ✅ `ADR-2026-05-14` — swap_ohlcv_p UTC storage calendar

Retroactive ADRs still TODO:
- Choice of PostgreSQL over ClickHouse for indicators storage
- Pandas-based calculation pipeline vs streaming (Faust / Kafka)
- Watermark-based incremental update strategy

---

### FT-008: Developer Onboarding

- `CONTRIBUTING.md` with step-by-step local setup
- Docker Compose for full local stack (Postgres, Airflow, app)
- Seed data script for development

---

## 15. Quality Criteria

### Architecture Checklist

- [ ] Dependency Rule is satisfied: no inner layer imports an outer layer
- [ ] No cyclic dependencies between bounded contexts (CI enforced)
- [ ] Each module has one, and only one, reason to change
- [ ] Public API of each context is defined in `ports/` as typed Protocols
- [ ] Forbidden cross-context imports from `TARGET_ARCHITECTURE.md §5` are absent

### Code Quality Checklist

- [ ] SOLID principles applied (review against §5)
- [ ] Functions ≤ 25 lines, nesting ≤ 2 levels, modules ≤ 400 lines
- [ ] Type hints on all public functions; `mypy` passes
- [ ] No `Any` in `domain` or `application` layers
- [ ] `ruff check src/` passes with zero errors

### Testing Checklist

- [ ] TDD workflow followed (test written before production code)
- [ ] Unit tests cover `domain` and `application` without hitting DB or network
- [ ] Integration tests exist for infrastructure adapters
- [ ] Architecture tests verify import constraints
- [ ] Coverage ≥ 85% total, ≥ 90% on changed lines

### Safety Checklist

- [ ] No secrets or credentials in source code
- [ ] Destructive operations are dry-run by default
- [ ] All DB writes are idempotent (UPSERT)
- [ ] No look-ahead bias (data read only up to closed bar)
- [ ] All calculations are tagged with `run_id` for reproducibility

### Process Checklist

- [ ] ADR written for every architectural decision
- [ ] CI passes (lint + type-check + tests + architecture checks)
- [ ] Documentation updated when public API changes
- [ ] PR reviewed against this guide before merge

---

*Last updated: 2026-05-15*
*Related documents: `ARCHITECTURE_GUIDE.md` (principles), `TARGET_ARCHITECTURE.md`, `CLAUDE.md`, `ROADMAP.md`, `src/FEATURES_DEPENDENCIES.md`*
