# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PKLPO is a quantitative trading system for cryptocurrency with 500+ technical indicators. It collects market data and generates analytical signals (no real trade execution). Built on Clean Architecture principles with Python 3.11+.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"      # Development dependencies

# Type checking
mypy src/

# Linting and formatting
ruff check src/              # Lint
ruff check src/ --fix        # Lint with auto-fix
black src/                   # Format

# Run all tests
pytest

# Run single test file
pytest src/features/tests/test_core.py

# Run single test function
pytest src/features/tests/test_core.py::test_function_name

# Run tests by marker
pytest -m "not slow"         # Skip slow tests
pytest -m integration        # Integration tests only

# Run with coverage
pytest --cov=src --cov-report=html

# Pre-commit hooks
pre-commit run --all-files

# CLI commands
python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1m 5m 15m
python -m src.cli.main pipeline --symbols BTC-USDT-SWAP --timeframes 1m
python -m src.cli.main migrate
python -m src.cli.main swap-sync --symbols BTC-USDT-SWAP --timeframes 1m
```

## Architecture

### Layered Structure

```
src/
├── cli/                    # CLI entry points (python -m src.cli.main)
├── features/               # Core indicator calculation module
│   ├── core/              # Main calculation engine (compute_features API)
│   ├── application/       # Business logic (calc.py, save.py, backfill.py)
│   ├── domain/            # Business rules (models.py, strategy.py, protocols.py)
│   ├── infrastructure/    # DB persistence, external APIs
│   ├── specs/             # 10 indicator categories (trend, oscillators, volatility, etc.)
│   └── registry/          # AVAILABLE_INDICATORS list
├── models.py              # SQLAlchemy ORM models (Instrument, OHLCV, Indicator, Signal)
├── database.py            # Async database engine (asyncpg, connection pooling)
├── mtf/                   # Multi-timeframe analysis
├── signals/               # Signal generation
├── positions/             # Position sizing
├── risk/                  # Risk management
└── backtest/              # Backtesting engine
```

### Key Patterns

- **Streaming/Chunking**: Large datasets processed in overlapping chunks (default 200K rows) for memory efficiency
- **UPSERT Idempotency**: All DB writes use `(symbol, timeframe, timestamp)` composite key
- **Group-Based Calculation**: 10 indicator groups calculated sequentially with dependency resolution
- **No Look-Ahead Bias**: Calculations only occur after bar close
- **Async Database**: SQLAlchemy 2.0+ with asyncpg, connection pooling (pool_size=5, max_overflow=10)

### Core API

```python
from src.features.core import compute_features

df_result = compute_features(
    df_ohlcv,
    specs=['rsi_14', 'ema_21', 'macd'],
    volatility_normalize=True,
    normalize_window=20
)
```

## Code Standards

- **Style**: PEP 8, Black (line-length 88), Ruff linter
- **Types**: Type hints required, mypy checking
- **Functions**: Max 25 lines, max nesting 2 levels, modules max 400 lines
- **Docstrings**: Google style
- **Imports**: stdlib -> third-party -> local
- **Coverage**: 85% total minimum, 90% on changed lines

### Safety Conventions

- Destructive file/DB operations default to dry-run mode
- Use `--apply` flag to execute actual changes
- Always print execution plan and backup path before destructive operations

## Database

PostgreSQL with partitioned tables:
- `instruments` - Trading pair metadata
- `ohlcv_p` - Market candle data (partitioned)
- `indicators_p` - Calculated indicators (partitioned, 200+ columns)
- `signals` / `signals_detailed` - Trading signals
- `schema_migrations` - Migration history

Environment variables: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DB_HOST`, `DB_PORT`

## Testing

Pytest markers: `slow`, `integration`, `unit`, `smoke`, `performance`, `asyncio`

Test location: `src/features/tests/` and `tests/`

## Extended Guidelines

Additional rules and patterns are in separate files. Read them when relevant to your task.

### Rules (`rules/`)

| File | When to Read |
|------|--------------|
| `rules/coding-style.md` | Writing/reviewing code (immutability, file organization, error handling) |
| `rules/testing.md` | Writing tests, TDD workflow, coverage requirements |
| `rules/security.md` | Security checks, secret management, before commits |
| `rules/git-workflow.md` | Commits, PRs, branching |
| `rules/patterns.md` | API responses, repository pattern, hooks |
| `rules/performance.md` | Model selection, context management, optimization |
| `rules/hooks.md` | Pre/Post tool hooks, auto-accept settings |
| `rules/agents.md` | Multi-agent orchestration, parallel execution |

### Agents (`agents/`)

Specialized agent prompts. Use Task tool with appropriate agent when:

| Agent | Use Case |
|-------|----------|
| `agents/planner.md` | Complex features, implementation planning |
| `agents/architect.md` | System design, architectural decisions |
| `agents/tdd-guide.md` | Test-driven development, new features |
| `agents/code-reviewer.md` | After writing code, code review |
| `agents/security-reviewer.md` | Security analysis, before commits |
| `agents/build-error-resolver.md` | Build failures, error diagnosis |
| `agents/refactor-cleaner.md` | Dead code cleanup, refactoring |
| `agents/e2e-runner.md` | E2E testing, Playwright |
| `agents/doc-updater.md` | Documentation updates |

### Skills (`skills/`)

Reusable skill definitions:

| Skill | Purpose |
|-------|---------|
| `skills/tdd-workflow/` | TDD process automation |
| `skills/security-review/` | Security audit workflow |
| `skills/coding-standards/` | Code quality enforcement |
| `skills/verification-loop/` | Multi-step verification |
| `skills/strategic-compact/` | Context optimization |
| `skills/continuous-learning/` | Session evaluation |
| `skills/ai-skill-practices/` | AI-world practices for writing/improving skills |
| `skills/backend-patterns/` | Backend best practices |
| `skills/frontend-patterns/` | Frontend best practices |
| `skills/clickhouse-io/` | ClickHouse operations |
| `skills/eval-harness/` | Evaluation framework |

Skills manifest: `skills/manifest.yaml`

## Quick Commands

Custom commands for common operations (see `.claude/commands/` for details):

| Command | Description |
|---------|-------------|
| `/test` | Run pytest tests |
| `/lint` | Run ruff + mypy |
| `/format` | Format with Black |
| `/check` | Full verification (lint + test) |
| `/db` | Database operations |
| `/feature` | Calculate indicators |

## Configuration

Claude Code settings in `.claude/`:

| File | Purpose |
|------|---------|
| `settings.json` | Permissions, hooks, MCP servers |
| `instructions.md` | Session-level instructions |
| `ignore.md` | Files to ignore |
| `commands/` | Custom slash commands |
