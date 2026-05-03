# Cursor Baseline

This document is the single source of truth for Cursor/Claude local agent baseline in this repository.

## Scope

- Repository root: `D:/projects/pklpo`
- Runtime: Python `3.11`
- Primary instruction files: `AGENTS.md`, `CLAUDE.md`

## Active Hooks

Hook wiring is defined in `.claude/settings.json`.

Currently enabled:

- `PostToolUse` -> `agent_workspace/hooks/post_tool_validate.py`
- `Stop` -> `agent_workspace/hooks/turn_summary.py`

Hook behavior config:

- `agent_workspace/hooks/config.json`

## Hook Inventory

Existing hook scripts:

- `agent_workspace/hooks/post_tool_validate.py`
- `agent_workspace/hooks/turn_summary.py`

No prompt-stage hook scripts are currently connected.

## Cursor Rules

Project-level Cursor rules:

- `.cursor/rules/architecture-boundaries.md`
- `.cursor/rules/safe-git-operations.md`
- `.cursor/rules/validation-strategy.md`

## Validation Defaults

Use commands confirmed by current repo state:

- `ruff check src tests`
- `pytest -m "not slow and not integration"`
- `python -m src.cli.main --help`
- `mypy src`
- `powershell -File scripts/check_before_commit.ps1`

## Maintenance

When changing hooks, rules, or baseline behavior:

1. Update implementation files first.
2. Sync this document and `docs/agent-workspace.md`.
3. Keep statements aligned with files that actually exist in the tree.
