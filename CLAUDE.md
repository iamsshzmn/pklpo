# CLAUDE.md

## Project Overview

**pklpo** — quantitative trading system: OHLCV candle sync from OKX, feature/indicator pipeline, ML scoring, trade recommendation.

- **Runtime**: Python 3.11 (`requires-python = "==3.11.*"`, see `.python-version`)
- **Database**: PostgreSQL 16 (asyncpg)
- **Orchestration**: Apache Airflow (`ops/airflow/dags/`)
- **Exchange**: OKX (CCXT)
- **Package config**: `pyproject.toml` (single source of truth for deps)

## Authoritative Docs

Read these before deep work — do not duplicate their content here.

- `docs/ARCHITECTURE.md` — current and target architecture, bounded contexts, layer rules, ADRs
- `docs/ARCHITECTURE_GUIDE.md` — how to apply architecture in practice
- `docs/ENGINEERING_GUIDE.md` — engineering conventions, testing, workflow
- `docs/DATA_FLOW.md` / `docs/DEPENDENCIES.md` — pipeline and module dependencies
- `docs/ROADMAP.md` — current initiatives and priorities
- `ops/airflow/dags/README.md` — full DAG catalogue and schedules
- `AGENTS.md` — shared agent baseline for engineering work
- `.claude/rules/candles.md` — layer rules specific to the `candles/` module

## Quick Start

```bash
# Windows
powershell -File scripts/bootstrap.ps1
.venv\Scripts\Activate.ps1

# Unix
make setup && source .venv/bin/activate
```

Copy `.env.example` → `.env` before running.

## Key Commands

```bash
# CLI entry point
python -m src.cli.main --help

# Validation (prefer smallest surface)
make lint          # ruff check + format
make typecheck     # mypy src
make test          # fast tests (excludes slow, integration)
make check         # all of the above
make test-all      # everything, including integration
```

CLI subcommands (full list via `--help`): `swap-sync`, `swap-repair`, `features`, `pipeline`, `build-bars`, `load-instruments`, `update-list`, `cleanup`, `market-selection`, `label`, `train`, `metrics`, `indicators-partitions`.

## Module Boundaries

Dependency rule: **domain → application → infrastructure**. Domain MUST NOT import infrastructure or framework code. Layer map (applies to every bounded context under `src/`):

- `src/*/domain/` — pure business rules, no I/O
- `src/*/application/` — use cases, orchestration via ports
- `src/*/infrastructure/` — DB, HTTP, filesystem adapters
- `src/*/ports.py` — protocol/interface definitions
- `src/cli/commands/` — thin adapters, delegate to application

Full context map: `docs/ARCHITECTURE.md` §4–§7.

## Configuration

- **App config**: `src/config/settings.py` — Pydantic Settings, single entry point for env-backed settings. Do NOT scatter `os.getenv()`.
- **User settings**: `src/settings/` — runtime preferences (not env-backed)
- `.env.example` is the canonical reference for env vars

## Testing

- Layout mirrors `src/` under `tests/` (`candles/`, `features/`, `cli/`, `db/`, `ml/`, `backtest/`, `market_*/`, `integration/`, `smoke/`, `unit/`)
- Markers: `slow`, `integration`, `unit`, `smoke`, `performance`, `lookahead`
- Coverage target: 85% (enforced in `pyproject.toml`)

## Conventions

- Code in English; comments/docs may be Russian
- Formatting: `ruff format` (black-compatible, 88 chars); imports via ruff isort
- Commits: conventional (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`)
- Pre-commit: lightweight only; heavy validation via `make check`

## What NOT to Do

- Do not add new top-level source directories without discussion (see `docs/ARCHITECTURE.md`)
- Do not bypass `src/config/settings.py` for env access
- Do not put business logic in CLI commands or DAG files
- Do not commit `.env`, credentials, or API keys
- Do not modify existing migration files — add new ones
