---
name: verification-loop
description: Comprehensive verification system for Claude Code sessions including build, type check, lint, test, security scan, and diff review.
category: quality
model: sonnet
tools: [Read, Grep, Glob, Bash]
---

# Verification Loop Skill

> **⚠️ SECURITY WARNING**: This document contains example commands and code snippets. Always:
> - Validate and sanitize all file paths and directory names before executing commands
> - Never execute commands directly from documentation without review
> - Be cautious with `grep` commands that search for secrets - they may expose sensitive data in output
> - Use read-only access for verification operations when possible
> - Prevent path traversal attacks by validating input paths
> - Ensure proper error handling to avoid information disclosure
> - Review `git diff` output carefully - it may contain sensitive information
> - Never run verification commands as root unless absolutely necessary

A comprehensive verification system for Claude Code sessions.

## When to Use

Invoke this skill:
- After completing a feature or significant code change
- Before creating a PR
- When you want to ensure quality gates pass
- After refactoring

## Verification Phases

### Phase 1: Build Verification

> **⚠️ SECURITY NOTE**: Build commands may execute code. Ensure:
> - You're in the correct project directory
> - Build scripts are trusted and reviewed
> - No malicious code in dependencies

```bash
# Check if project builds
# Validate you're in the correct directory before running
npm run build 2>&1 | tail -20
# OR
pnpm build 2>&1 | tail -20
```

If build fails, STOP and fix before continuing.

### Phase 2: Type Check

> **⚠️ SECURITY NOTE**: Type checkers read source files. Ensure:
> - Paths are validated (no path traversal)
> - You're checking the intended directory
> - Error output doesn't expose sensitive file paths unnecessarily

```bash
# TypeScript projects
# Validate current directory before running
npx tsc --noEmit 2>&1 | head -30

# Python projects
# Ensure '.' refers to the intended directory
pyright . 2>&1 | head -30
```

Report all type errors. Fix critical ones before continuing.

### Phase 3: Lint Check

> **⚠️ SECURITY NOTE**: Linters read source files. Validate:
> - Current working directory is correct
> - Lint configuration is trusted
> - Output doesn't expose sensitive information

```bash
# JavaScript/TypeScript
# Ensure you're in the project root
npm run lint 2>&1 | head -30

# Python
# Validate path before running
ruff check . 2>&1 | head -30
```

### Phase 4: Test Suite

> **⚠️ SECURITY NOTE**: Tests execute code. Ensure:
> - Test files are trusted and reviewed
> - No tests execute destructive operations
> - Test environment is isolated from production
> - Coverage reports don't expose sensitive paths

```bash
# Run tests with coverage
# WARNING: Tests execute code - ensure test files are trusted
npm run test -- --coverage 2>&1 | tail -50

# Check coverage threshold
# Target: 80% minimum
```

Report:
- Total tests: X
- Passed: X
- Failed: X
- Coverage: X%

### Phase 5: Security Scan

> **⚠️ SECURITY NOTE**: The commands below search for potential secrets and may expose sensitive data in output.
> - Review output carefully and avoid logging it
> - Consider using tools like `git-secrets` or `truffleHog` for safer secret detection
> - Never commit output containing actual secrets
> - Use `2>/dev/null` to suppress error messages that might leak path information

```bash
# Check for secrets
# WARNING: These commands may expose secrets in output - review carefully
grep -rn "sk-" --include="*.ts" --include="*.js" . 2>/dev/null | head -10
grep -rn "api_key" --include="*.ts" --include="*.js" . 2>/dev/null | head -10

# Check for console.log
grep -rn "console.log" --include="*.ts" --include="*.tsx" src/ 2>/dev/null | head -10
```

### Phase 6: Diff Review

> **⚠️ SECURITY NOTE**: `git diff` may expose sensitive information including:
> - Secrets that were accidentally committed
> - Internal file paths and structure
> - Configuration details
> - Review diff output carefully before sharing or logging

```bash
# Show what changed
# WARNING: Review output for sensitive information before sharing
git diff --stat
git diff HEAD~1 --name-only
```

Review each changed file for:
- Unintended changes
- Missing error handling
- Potential edge cases
- **Security**: Accidental exposure of secrets or sensitive data

## Output Format

After running all phases, produce a verification report:

```
VERIFICATION REPORT
==================

Build:     [PASS/FAIL]
Types:     [PASS/FAIL] (X errors)
Lint:      [PASS/FAIL] (X warnings)
Tests:     [PASS/FAIL] (X/Y passed, Z% coverage)
Security:  [PASS/FAIL] (X issues)
Diff:      [X files changed]

Overall:   [READY/NOT READY] for PR

Issues to Fix:
1. ...
2. ...
```

## Continuous Mode

For long sessions, run verification every 15 minutes or after major changes:

```markdown
Set a mental checkpoint:
- After completing each function
- After finishing a component
- Before moving to next task

Run: /verify
```

## Integration with Hooks

This skill complements PostToolUse hooks but provides deeper verification.
Hooks catch issues immediately; this skill provides comprehensive review.

## Security Best Practices

When implementing verification commands:

1. **Path Validation**: Always validate file paths and directory names to prevent path traversal attacks
   ```bash
   # Example: Validate path before use
   if [[ "$path" == *".."* ]]; then
     echo "ERROR: Path traversal detected" >&2
     exit 1
   fi
   ```

2. **Output Sanitization**: Be careful with command output that may contain secrets
   - Never log full `grep` output that searches for secrets
   - Use `head` or `tail` to limit output size
   - Review output before sharing or committing

3. **Error Handling**: Suppress error messages that might leak information
   - Use `2>/dev/null` for commands that might expose paths
   - Provide generic error messages to users
   - Log detailed errors only in secure locations

4. **Command Execution**: Validate commands before execution
   - Check current working directory
   - Verify required tools are available
   - Ensure scripts are not run as root unless necessary

5. **Git Operations**: Be cautious with `git diff` and similar commands
   - Review diff output for secrets before sharing
   - Use `--stat` or `--name-only` when full diff isn't needed
   - Never commit output containing actual secrets

6. **Test Execution**: Isolate test environments
   - Ensure tests don't modify production data
   - Use test databases and mock services
   - Verify test files are trusted before execution
