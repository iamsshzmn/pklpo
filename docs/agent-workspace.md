# Agent Workspace

This repository now has a shared Codex and Claude Code baseline rooted in the current working tree.

## Purpose

The baseline is intentionally small and operational:

- `AGENTS.md` holds project-wide working rules
- `agent_workspace/skills/` holds reusable task skills
- `agent_workspace/hooks/` holds deterministic lifecycle hooks
- `.claude/settings.json` wires Claude Code to the shared hooks

`AGENTS.md` is the first file an agent should use. It captures repo facts that are confirmed from the current tree: Python 3.11, `pyproject.toml`, `src/` and `tests/`, the `python -m src.cli.main` entrypoint, and the validation commands already present in the repo.

## Current Skills

The shared skills are instruction-first and short enough to stay reusable:

| Skill | Use it for | Avoid it for |
| --- | --- | --- |
| `repo-explorer` | Discovering entrypoints, ownership, tests, and real commands | Small changes that are already scoped |
| `feature-implementer` | Production changes in current modules or docs | Pure investigation |
| `test-runner` | Selecting the smallest useful repo-backed checks | No-change analysis |
| `bug-investigator` | Reproduction and root-cause isolation | Straightforward feature work |
| `refactor-reviewer` | Regression-focused review of structural changes | Tiny localized edits |
| `release-notes-writer` | Operator-facing summaries of verified changes | Unstable or unverified work |

The manifest is `agent_workspace/skills/manifest.yaml`. Each skill includes:

- `Use when`
- `Do not use when`
- short reusable instructions
- optional delegation notes only when the split is bounded

## Hooks

The shared hook source of truth is `agent_workspace/hooks/config.json`.

| Hook | Script | Purpose |
| --- | --- | --- |
| Prompt safety | `agent_workspace/hooks/check_prompt.py` | Blocks clearly destructive command wording unless the prompt includes confirmation language |
| Prompt enrichment | `agent_workspace/hooks/enrich_prompt.py` | Optional repo-aware hints keyed to current subsystems like migrations, features, candles, and Airflow |
| Post-tool validation | `agent_workspace/hooks/post_tool_validate.py` | Runs `py_compile` and `ruff check` on changed Python files only |
| Turn summary | `agent_workspace/hooks/turn_summary.py` | Prints a short `git status --short` summary at stop time |

Design rules for hooks in this repo:

- deterministic and local-only
- no network access
- no heavy repo-wide checks
- fail-safe by default
- scoped to commands and files that exist in the current tree

## Claude Code Wiring

`.claude/settings.json` wires these hook stages:

- `UserPromptSubmit` for prompt safety and optional enrichment
- `PostToolUse` for lightweight validation after write tools
- `Stop` for a changed-file summary

The enrichment hook is present but disabled in `agent_workspace/hooks/config.json`. Enable it only if the team wants extra repo hints on every prompt.

## Repo-Backed Validation Commands

These are the commands confirmed from the current repository and safe to reference as defaults:

```bash
python -m src.cli.main --help
python -m src.cli.main migrate
python -m src.cli.main indicators-partitions
pytest
pytest -m "not slow and not integration"
ruff check src tests
black src tests
mypy src
pre-commit run --all-files
powershell -File scripts/check_before_commit.ps1
```

Notes:

- `scripts/check_before_commit.ps1` is a broader helper, not a hook.
- That script also calls `bandit`, but `bandit` is not pinned in `pyproject.toml`, so treat it as environment-dependent.

## Extending The System

For a new skill:

1. Add `agent_workspace/skills/<skill-name>/SKILL.md`.
2. Keep it short and reusable.
3. Register the skill in `agent_workspace/skills/manifest.yaml`.
4. Reference only commands and paths that exist now.

For a new hook:

1. Add the script under `agent_workspace/hooks/`.
2. Keep it deterministic and fast.
3. Register its behavior in `agent_workspace/hooks/config.json`.
4. Wire it in `.claude/settings.json` only if automatic execution is safe.

## Assumptions And TODOs

- TODO: confirm whether the team wants prompt enrichment enabled by default; it is currently disabled for minimal noise.
- TODO: confirm whether Claude Code in this repo should validate additional write tools beyond `Write|Edit|MultiEdit`.
- TODO: if CI adds a stable changed-files test command, prefer that over file-local `ruff` checks in the post-tool hook.

## Roadmap

- Add one repo-specific architecture review skill once the `features`, `candles`, and `db` boundaries settle further.
- Add a deterministic changed-files test selector only if it proves reliable in this repo.
- Add Codex-native hook wiring later if the team adopts a stable local mechanism; continue reusing `agent_workspace/hooks/`.
