# test-runner

Use when:
- You need to choose and run the smallest useful validation after a change.
- A task asks for verification, regression checks, or review safety.

Do not use when:
- No files changed and the task is pure analysis.
- The repo lacks enough context to justify running commands yet.

Instructions:
1. Match the check to the surface area first.
2. Prefer targeted commands:
   - `pytest tests/db/...` for DB maintenance changes when relevant tests exist
   - `pytest -m "not slow and not integration"` for a broader fast pass
   - `ruff check src tests` for style and import issues
   - `python -m src.cli.main --help` plus a touched subcommand help path for CLI edits
3. Use `powershell -File scripts/check_before_commit.ps1` only for broader pre-handoff validation.
4. If a needed command is not confirmed from the current tree, say so instead of inventing one.

Notes:
- `scripts/check_before_commit.ps1` also calls `bandit`; treat that as environment-dependent because `bandit` is not pinned in `pyproject.toml`.
