# AGENTS.md

## Purpose

This repository uses a shared agent baseline for repeatable engineering work.
Use the current working tree only. Do not recover deleted agent files, old repo scaffolding, or prior branch-specific conventions.

## Project Facts

- Runtime: Python `3.11`
- Package and tool config: `pyproject.toml`
- Main CLI entrypoint: `python -m src.cli.main`
- Source roots used now: `src/`, `tests/`, `ops/airflow/`, `scripts/`, `docs/`
- Live agent workspace: `agent_workspace/`

## Confirmed Commands

Prefer commands that are proven by the current tree:

- `python -m src.cli.main --help`
- `python -m src.cli.main migrate`
- `python -m src.cli.main update-list`
- `python -m src.cli.main swap-sync --symbols BTC-USDT-SWAP --timeframes 1m 5m 15m`
- `python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1m 5m 15m`
- `python -m src.cli.main indicators-partitions`
- `pytest`
- `pytest -m "not slow and not integration"`
- `ruff check src tests`
- `black src tests`
- `mypy src`
- `pre-commit run --all-files`
- `powershell -File scripts/check_before_commit.ps1`

If a command is only mentioned in older prose or requires extra local tools not pinned in `pyproject.toml`, treat it as optional and say so.

## Working Rules

- Start by reading the current files that own the feature, command, or schema being changed.
- Prefer the smallest validation that matches the touched surface before running broad repo checks.
- Keep edits aligned with current module boundaries: CLI in `src/cli/commands/`, domain/application/infrastructure splits where already present, DAG logic in `ops/airflow/dags/`, DB changes in `src/db/migrations/`.
- Preserve existing command names, paths, and trading terminology.
- Treat the worktree as user-owned. Do not revert unrelated changes.
- When conventions are unclear from the current tree, choose a small default and leave a concise `TODO` with the missing input.

## Validation Defaults

- Python code edits: `ruff check ...` plus targeted `pytest ...`
- CLI changes: `python -m src.cli.main --help` and the touched subcommand help or dry-run path when available
- DB or migration changes: relevant `pytest tests/db ...` where present; otherwise document the gap
- Broad pre-handoff check when warranted: `powershell -File scripts/check_before_commit.ps1`

## Skills And Hooks

- Skills live in `agent_workspace/skills/`
- Hook scripts live in `agent_workspace/hooks/`
- Claude Code wiring lives in `.claude/settings.json`
- Human-facing details live in `docs/agent-workspace.md`

Use the matching skill before freeform work when the task fits one of the shared workflows.
