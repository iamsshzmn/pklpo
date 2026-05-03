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
# CLI (all commands)
python -m src.cli.main --help
python -m src.cli.main swap-sync --symbols BTC-USDT-SWAP --timeframes 1m 5m 15m
python -m src.cli.main swap-repair --symbols BTC-USDT-SWAP --timeframes 1H 4H
python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1m 5m 15m
python -m src.cli.main pipeline           # полный пайплайн обработки
python -m src.cli.main build-bars         # dollar bars из OHLCV
python -m src.cli.main load-instruments   # загрузить инструменты из OKX API
python -m src.cli.main update-list        # обновить список инструментов для синхронизации
python -m src.cli.main cleanup            # управление очисткой данных
python -m src.cli.main market-selection   # фильтрация и ранжирование рынков
python -m src.cli.main label              # triple-barrier labeling (AFML Ch.3)
python -m src.cli.main train              # MetaLabeler (AFML Ch.10)
python -m src.cli.main metrics            # вывод и экспорт quant-метрик бэктеста
python -m src.cli.main indicators-partitions  # обслуживание monthly partitions

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
├── candles/              # OHLCV sync from OKX (domain/application/infrastructure/ports)
│   └── application/repair/  # Gap detection and historical backfill (WIP)
├── features/             # Indicator calculation pipeline
├── features_combinations/ # Registry and models for feature combinations
├── scoring_engine/       # Computes score_raw ∈ [0;1] from indicators, saves to score_results
├── trade_recommender/    # Trade recommendations: entry/sl/tp/position sizing
├── mtf/                  # Multi-timeframe pipeline: context/triggers/consensus
│   ├── context/          # Market regime detection
│   ├── triggers/         # Signal generation with anti-noise filters
│   └── consensus/        # Weighted aggregation with veto logic
├── risk/                 # Risk guards: daily/weekly limits, circuit breaker, SLA
├── signals/              # Signal models, decision maker, promotion workflow
├── positions/            # Position calculation (single + MTF)
├── metrics/              # Quant metrics collection and export
├── settings/             # User-level settings manager (runtime preferences)
├── cli/                  # Thin CLI adapters (Typer/Click)
├── config/               # App config: Pydantic Settings, env loading
├── core/                 # Shared domain primitives
├── db/                   # Migrations, partition management
├── ml/                   # ML scoring engine
├── backtest/             # Backtesting framework
├── market_selection/     # Market filtering/ranking
└── utils/                # Shared utilities
ops/airflow/dags/         # Airflow DAG definitions
tests/                    # Repo-level tests by subsystem
scripts/                  # Dev/ops automation
```

**Dependency rule**: domain → application → infrastructure. Domain MUST NOT import infrastructure or framework code.

## Module Boundaries

- `src/cli/commands/` — thin adapters only, delegate to application layer
- `src/*/domain/` — pure business rules, no I/O
- `src/*/application/` — use cases, orchestration
- `src/*/infrastructure/` — DB, HTTP, filesystem adapters
- `src/*/ports.py` — protocol/interface definitions

## Airflow DAGs

| DAG ID | Schedule | Purpose |
|--------|----------|---------|
| `okx_swap_ohlcv_sync_v2` | `*/5 * * * *` | Live OHLCV ingest for SWAP instruments; modes: `fast` (1m/5m), `slow` (15m–1M), `ext` (with funding_rate/OI), `bootstrap` |
| `okx_swap_repair_v1` | manual | Bounded historical backfill and gap repair for OKX SWAP candles (WIP) |
| `features_calc` | scheduled | Full indicator calculation via `src.cli.main features` |
| `features_calc_short` | scheduled | Incremental calculation of 24 short features only |
| `market_selection` | scheduled | Market filtering based on data quality, pair metrics, global regime |
| `indicators_partition_maintenance` | scheduled | Maintains ready monthly partitions for `indicators_p` |

Full DAG docs: `ops/airflow/dags/README.md`

## Configuration

- **App config**: `src/config/settings.py` — Pydantic Settings, single entry point for all env-backed settings
- **User settings**: `src/settings/` — runtime user preferences manager (not env-backed)
- Do NOT scatter `os.getenv()` calls — add new vars to `src/config/settings.py`
- `.env.example` is the canonical reference for available env vars

## Testing

```
tests/
├── candles/        # candles subsystem (unit + repair + observability)
├── features/       # feature calculation
├── integration/    # needs DB or external services
├── db/             # DAG and migration tests
├── cli/            # CLI command tests
├── ml/             # ML scoring
├── backtest/       # backtesting
├── market_meta/    # market metadata
├── market_selection/
├── smoke/          # import checks, CLI loads
└── unit/           # isolated logic tests
```

- Markers: `slow`, `integration`, `unit`, `smoke`, `performance`, `lookahead`
- Coverage target: 85% (enforced in `pyproject.toml`, relaxed in CI for partial runs)

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
