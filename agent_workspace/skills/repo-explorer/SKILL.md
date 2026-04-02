# repo-explorer

Use when:
- The task starts with "inspect", "understand", "find the entrypoint", or "map the current repo".
- You need the real command, owning module, test location, or operator path before editing.

Do not use when:
- The task is already scoped to a small file change.
- You already know the owning files and only need to implement or validate.

Instructions:
1. Read the current tree first: `pyproject.toml`, `README.md`, the owning module, and nearby tests or docs.
2. Confirm commands only from current files. Prefer `python -m src.cli.main`, `pytest`, `ruff`, `black`, `mypy`, and `pre-commit` when relevant.
3. Summarize findings as: entrypoints, touched modules, existing checks, and missing conventions.
4. If conventions are missing, propose a small default and mark it with `TODO`.

Optional delegation:
- Use a bounded parallel read for separate areas such as `src/`, `tests/`, and `ops/airflow/` when the task spans multiple subsystems.
