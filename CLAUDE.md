# CLAUDE.md

## Project Overview

**pklpo** — quantitative trading system: OHLCV candle sync from OKX, feature/indicator calculation pipeline, ML scoring, and trade recommendation.

- **Runtime**: Python 3.11 (pinned in `.python-version`)
- **Database**: PostgreSQL 16 (asyncpg)
- **Orchestration**: Apache Airflow (DAGs in `ops/airflow/dags/`)
- **Exchange**: OKX (CCXT adapter)
- **Package config**: `pyproject.toml` (single source of truth for deps)

## Quick Start

```bash
# Windows
powershell -File scripts/bootstrap.ps1
.venv\Scripts\Activate.ps1

# Unix (make available)
make setup
source .venv/bin/activate
```

Copy `.env.example` → `.env` and fill secrets before running.

## Key Commands

```bash
# CLI
python -m src.cli.main --help
python -m src.cli.main swap-sync --symbols BTC-USDT-SWAP --timeframes 1m 5m 15m
python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1m 5m 15m

# Validation (prefer smallest surface)
make lint          # ruff check + format check
make typecheck     # mypy src
make test          # fast tests (not slow, not integration)
make check         # all of the above

# Full (slower)
make test-all      # all tests including integration
```

## Architecture

```
src/
├── candles/          # OHLCV sync from OKX (domain/application/infrastructure/ports)
├── features/         # Indicator calculation pipeline
├── cli/              # Thin CLI adapters (Typer/Click)
├── config/           # Settings, env loading
├── core/             # Shared domain primitives
├── db/               # Migrations, partition management
├── ml/               # ML scoring engine
├── backtest/         # Backtesting framework
├── market_selection/ # Market filtering/ranking
└── utils/            # Shared utilities
ops/airflow/dags/     # Airflow DAG definitions
tests/                # Repo-level tests by subsystem
scripts/              # Dev/ops automation
```

**Dependency rule**: domain → application → infrastructure. Domain MUST NOT import infrastructure or framework code.

## Module Boundaries

- `src/cli/commands/` — thin adapters only, delegate to application layer
- `src/*/domain/` — pure business rules, no I/O
- `src/*/application/` — use cases, orchestration
- `src/*/infrastructure/` — DB, HTTP, filesystem adapters
- `src/*/ports.py` — protocol/interface definitions

## Configuration

- All settings via `.env` + `src/config/settings.py`
- Do NOT scatter `os.getenv()` calls — add new vars to settings module
- `.env.example` is the canonical reference for available config

## Testing

- `tests/smoke/` — import checks, CLI loads
- `tests/unit/` — isolated logic tests
- `tests/integration/` — needs DB or external services
- `tests/ml/`, `tests/backtest/` — domain-specific suites
- Markers: `slow`, `integration`, `unit`, `smoke`, `performance`, `lookahead`
- Coverage target: 85% (enforced in pyproject.toml, relaxed in CI for partial runs)

## Conventions

- Language: code in English, comments/docs may be Russian
- Formatting: ruff format (black-compatible, 88 chars)
- Imports: isort via ruff (first-party: `src`, `features`, `cli`, `core`, `ml`)
- Commits: conventional (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`)
- Pre-commit: lightweight checks only; heavy validation via `make check`

## What NOT to Do

- Do not add new top-level source directories without discussion
- Do not bypass `src/config/settings.py` for env var access
- Do not put business logic in CLI commands or DAG files
- Do not commit `.env`, credentials, or API keys
- Do not modify existing migration files — add new ones
- Do not use paths from `src/main*.py` — those are deprecated
