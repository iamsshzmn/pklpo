---
name: strategic-compact
description: Suggests manual context compaction at logical intervals to preserve context through task phases rather than arbitrary auto-compaction.
---

# Strategic Compact Skill

> **⚠️ SECURITY WARNING**: This skill uses shell scripts that handle temporary files and environment variables. Always:
> - Review script permissions before execution
> - Validate environment variables (COMPACT_THRESHOLD) are within safe bounds
> - Ensure scripts are not run as root
> - Verify temporary file paths are secure
> - Never execute scripts from untrusted sources

Suggests manual `/compact` at strategic points in your workflow rather than relying on arbitrary auto-compaction.

## Why Strategic Compaction?

Auto-compaction triggers at arbitrary points:
- Often mid-task, losing important context
- No awareness of logical task boundaries
- Can interrupt complex multi-step operations

Strategic compaction at logical boundaries:
- **After exploration, before execution** - Compact research context, keep implementation plan
- **After completing a milestone** - Fresh start for next phase
- **Before major context shifts** - Clear exploration context before different task

## How It Works

The `suggest-compact.sh` script runs on PreToolUse (Edit/Write) and:

1. **Tracks tool calls** - Counts tool invocations in session
2. **Threshold detection** - Suggests at configurable threshold (default: 50 calls)
3. **Periodic reminders** - Reminds every 25 calls after threshold

## Hook Setup

Add to your `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "tool == \"Edit\" || tool == \"Write\"",
      "hooks": [{
        "type": "command",
        "command": "~/.claude/skills/strategic-compact/suggest-compact.sh"
      }]
    }]
  }
}
```

## Configuration

Environment variables:
- `COMPACT_THRESHOLD` - Tool calls before first suggestion (default: 50)
  - **Security**: Must be a positive integer between 1 and 1,000,000
  - **Validation**: Script validates input to prevent injection attacks
  - **Recommendation**: Use values between 25-200 for optimal performance

## Best Practices

1. **Compact after planning** - Once plan is finalized, compact to start fresh
2. **Compact after debugging** - Clear error-resolution context before continuing
3. **Don't compact mid-implementation** - Preserve context for related changes
4. **Read the suggestion** - The hook tells you *when*, you decide *if*

## Security Features

The script implements multiple security measures:

1. **Strict Mode**: Uses `set -euo pipefail` to fail on errors, undefined variables, and pipe failures
2. **Root Check**: Prevents execution as root user to minimize privilege escalation risks
3. **Secure Temp Files**: Uses fixed filename in secure temp directory with restrictive permissions (600)
4. **Input Validation**: Validates all numeric inputs with bounds checking (1-1,000,000)
5. **Path Sanitization**: Validates temporary directory accessibility and USER variable format
6. **Permission Enforcement**: Verifies and enforces file permissions (600) on counter file
7. **Error Handling**: Proper error handling prevents information disclosure
8. **Variable Validation**: Validates USER environment variable to prevent injection attacks

## Related

- [The Longform Guide](https://x.com/affaanmustafa/status/2014040193557471352) - Token optimization section
- Memory persistence hooks - For state that survives compaction
