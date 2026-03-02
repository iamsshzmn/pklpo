---
name: verification-loop
description: Comprehensive Python verification pipeline for PKLPO: black → ruff → mypy → pytest → pre-commit. Run before PRs and after significant changes.
category: quality
model: sonnet
tools: [Read, Grep, Glob, Bash]
---

# Verification Loop Skill

A step-by-step quality gate pipeline for Python code in PKLPO.

## When to Use

- After completing a feature or significant code change
- Before creating a PR
- After refactoring
- When quality gates may have drifted

## Verification Phases

### Phase 1: Format Check

```bash
black src/ --check
```

If it reports files to reformat, fix first:
```bash
black src/
```

### Phase 2: Lint (ruff)

```bash
ruff check src/
```

Auto-fix safe issues:
```bash
ruff check src/ --fix
```

For unsafe fixes (unused imports, etc.) — review first:
```bash
ruff check src/ --fix --unsafe-fixes
```

If lint fails, STOP and fix before continuing.

### Phase 3: Type Check (mypy)

```bash
mypy src/
```

Report all type errors. Fix critical ones before continuing. `# type: ignore` only as last resort — document why.

### Phase 4: Test Suite

```bash
# Fast feedback (skip slow tests)
pytest -m "not slow" --cov=src --cov-report=term-missing -q

# Full suite
pytest --cov=src --cov-report=html
```

Coverage thresholds (from pyproject.toml):
- Total: **85%** minimum
- Changed lines: **90%** minimum

Report:
```
Tests:     PASS/FAIL  (X passed, Y failed)
Coverage:  XX%  (threshold: 85%)
```

### Phase 5: Pre-commit Hooks

```bash
pre-commit run --all-files
```

This runs: trailing-whitespace, end-of-file-fixer, mixed-line-ending (LF), check-case-conflict, check-added-large-files.

On Windows, line-ending fixes may require two runs (first run fixes files, second run passes).

### Phase 6: Diff Review

```bash
git diff --stat
git diff HEAD --name-only
```

Review each changed file for:
- Unintended changes
- Missing error handling
- Potential edge cases
- Accidental secrets or credentials in diff

## Output Format

After running all phases, produce a verification report:

```
VERIFICATION REPORT
==================

Format:    [PASS/FAIL]
Lint:      [PASS/FAIL] (X warnings)
Types:     [PASS/FAIL] (X errors)
Tests:     [PASS/FAIL] (X/Y passed, XX% coverage)
Pre-commit:[PASS/FAIL]
Diff:      [X files changed]

Overall:   [READY / NOT READY] for PR

Issues to Fix:
1. ...
2. ...
```

## Continuous Mode

For long sessions, run verification after each major change:

Checkpoints:
- After completing each function or class
- Before moving to the next task
- After touching DB schemas or indicator specs

Run: `/check` (runs ruff + mypy, see `.claude/commands/`)

## Integration with Hooks

This skill complements PostToolUse hooks but provides deeper verification.
Hooks catch issues immediately; this skill provides a comprehensive pre-PR review.

## Quick Reference

```bash
# Full verification sequence
black src/ && ruff check src/ && mypy src/ && pytest -m "not slow" --cov=src && pre-commit run --all-files
```
