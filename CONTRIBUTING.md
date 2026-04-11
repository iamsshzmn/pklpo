# Contributing

## Scope

This repository is a Python 3.11 codebase with the main entrypoint at `python -m src.cli.main`.
Prefer the current working tree over older docs or historical scaffolding.

## Local Setup

1. Copy `.env.example` to `.env` and fill in local secrets.
2. Run `powershell -File scripts/bootstrap.ps1`.
3. Activate the virtualenv with `.venv\Scripts\Activate.ps1`.
4. Confirm the CLI loads with `python -m src.cli.main --help`.

## Validation

Use the smallest check that matches the surface you changed.

- Python code: `ruff check src tests`
- Formatting: `black --check src tests`
- Typing: `mypy src`
- Fast tests: `pytest -m "not slow and not integration"`
- Broad pre-handoff: `powershell -File scripts/check_before_commit.ps1`

If you change CLI wiring, also run `python -m src.cli.main --help`.
If you change migrations or DB code, run the relevant tests under `tests/db/` when present.

## Configuration And Secrets

- Keep secrets in `.env` only. Do not commit live credentials, tokens, or local connection strings.
- Prefer adding new settings to `src/config/settings.py` instead of scattering `os.getenv()` calls.
- If a script still reads `DATABASE_URL` directly, document that dependency in the script help or docstring.

## Structure

- `src/cli/commands/`: thin CLI adapters only
- `src/*/domain/`: business rules and policies
- `src/*/application/`: use cases and orchestration
- `src/*/infrastructure/`: DB, HTTP, filesystem, third-party adapters
- `ops/airflow/dags/`: orchestration only
- `tests/`: repo-level tests by subsystem

Keep dependencies pointing inward. Domain code should not import infrastructure or Airflow modules.

## Containers

- `scripts/docker-compose.yml` is the local stack for app + Postgres tooling.
- `ops/airflow/docker-compose.airflow.yml` is the Airflow-specific stack.
- Rebuild images when `pyproject.toml` or Dockerfiles change.

## Agent Guidance

- Start with `AGENTS.md`.
- Use the current root CLI and current tests, not historical entrypoints under `src/main*.py`.
- Avoid adding new tooling unless it removes an existing pain point in this tree.
