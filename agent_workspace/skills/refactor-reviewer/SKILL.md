# refactor-reviewer

Use when:
- A change touches multiple modules, reshapes boundaries, or moves logic across layers.
- The task asks for a review of regressions, coupling, or missing validation.

Do not use when:
- The diff is a small isolated bug fix.
- The task is implementation-first and review can wait until after the change.

Instructions:
1. Review behavior first, then style.
2. Check for broken imports, changed public CLI behavior, missing migration or schema sync steps, and tests that no longer match the code path.
3. Compare the refactor against current boundaries already used in the repo instead of idealized architecture.
4. Call out missing validation explicitly.
5. End with concrete follow-up checks, not generic advice.

Focus areas in this repo:
- `src/cli/commands/`
- `src/features/`
- `src/candles/`
- `src/db/migrations/`
- `ops/airflow/dags/`
