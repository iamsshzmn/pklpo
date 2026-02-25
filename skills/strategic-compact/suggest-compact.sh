#!/bin/bash
# Strategic Compact Suggester
# Runs on PreToolUse or periodically to suggest manual compaction at logical intervals
#
# Why manual over auto-compact:
# - Auto-compact happens at arbitrary points, often mid-task
# - Strategic compacting preserves context through logical phases
# - Compact after exploration, before execution
# - Compact after completing a milestone, before starting next
#
# Hook config (in ~/.claude/settings.json):
# {
#   "hooks": {
#     "PreToolUse": [{
#       "matcher": "Edit|Write",
#       "hooks": [{
#         "type": "command",
#         "command": "~/.claude/skills/strategic-compact/suggest-compact.sh"
#       }]
#     }]
#   }
# }
#
# Criteria for suggesting compact:
# - Session has been running for extended period
# - Large number of tool calls made
# - Transitioning from research/exploration to implementation
# - Plan has been finalized

set -euo pipefail
# Security: Fail on undefined variables, pipe failures, and errors

# Security: Check that script is not running as root
if [ "$(id -u)" -eq 0 ]; then
  echo "[StrategicCompact] SECURITY: Script should not run as root" >&2
  exit 1
fi

# Load common security functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_BASE_DIR="${SCRIPT_DIR%/*}"
SECURITY_SCRIPT="${SKILLS_BASE_DIR}/_common/security.sh"

if [ -f "$SECURITY_SCRIPT" ] && [ -r "$SECURITY_SCRIPT" ]; then
  # shellcheck source=/dev/null
  source "$SECURITY_SCRIPT"
  # Initialize audit logging
  init_audit_log "StrategicCompact" || {
    echo "[StrategicCompact] WARN: Failed to initialize audit log" >&2
  }
  # Verify SKILL.md integrity
  verify_skill_checksums "$SKILLS_BASE_DIR" || {
    audit_log "SECURITY" "SKILL.md integrity check failed"
    # Don't exit on checksum failure, but log it
  }
else
  echo "[StrategicCompact] WARN: Security module not found: $SECURITY_SCRIPT" >&2
fi

# Security: Validate numeric threshold from environment variable
validate_positive_integer() {
  local value="$1"
  local min="${2:-1}"
  local max="${3:-1000000}"

  # Check if it's a valid integer
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    audit_log "SECURITY" "Invalid integer value: $value" 2>/dev/null || echo "[StrategicCompact] SECURITY: Invalid integer value: $value" >&2
    exit 1
  fi

  # Check bounds
  if [ "$value" -lt "$min" ] || [ "$value" -gt "$max" ]; then
    audit_log "SECURITY" "Value out of bounds [$min-$max]: $value" 2>/dev/null || echo "[StrategicCompact] SECURITY: Value out of bounds [$min-$max]: $value" >&2
    exit 1
  fi

  echo "$value"
}

# Security: Validate and sanitize temporary directory path
# Use user-specific temp directory to prevent conflicts
TEMP_BASE="${TMPDIR:-/tmp}"
if [ ! -d "$TEMP_BASE" ] || [ ! -w "$TEMP_BASE" ]; then
  audit_log "SECURITY" "Temporary directory not accessible: $TEMP_BASE" 2>/dev/null || echo "[StrategicCompact] SECURITY: Temporary directory not accessible: $TEMP_BASE" >&2
  exit 1
fi

# Security: Use fixed filename in secure temp directory
# Validate USER variable to prevent injection
if [ -z "${USER:-}" ] || [[ ! "$USER" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  audit_log "SECURITY" "Invalid USER variable" 2>/dev/null || echo "[StrategicCompact] SECURITY: Invalid USER variable" >&2
  exit 1
fi

# Create secure counter file path
COUNTER_FILE="${TEMP_BASE}/claude-tool-count-${USER}"

# Security: Create file if it doesn't exist with restrictive permissions
if [ ! -f "$COUNTER_FILE" ]; then
  touch "$COUNTER_FILE" 2>/dev/null || {
    audit_log "ERROR" "Failed to create counter file: $COUNTER_FILE" 2>/dev/null || echo "[StrategicCompact] ERROR: Failed to create counter file" >&2
    exit 1
  }
  chmod 600 "$COUNTER_FILE" 2>/dev/null || true
  audit_log "INFO" "Created counter file: $COUNTER_FILE" 2>/dev/null || true
fi

# Security: Verify file permissions (should be readable/writable by owner only)
if [ -f "$COUNTER_FILE" ]; then
  file_perms=$(stat -c "%a" "$COUNTER_FILE" 2>/dev/null || stat -f "%OLp" "$COUNTER_FILE" 2>/dev/null || echo "000")
  # Check if permissions are too permissive (not 600 or 700)
  if [[ ! "$file_perms" =~ ^[67]00$ ]]; then
    chmod 600 "$COUNTER_FILE" 2>/dev/null || true
  fi
fi

# Note: Counter file is intentionally preserved between script runs
# to maintain session state. It uses secure permissions (600) and
# is stored in a user-specific temp directory.

# Security: Validate threshold from environment variable
THRESHOLD_RAW=${COMPACT_THRESHOLD:-50}
THRESHOLD=$(validate_positive_integer "$THRESHOLD_RAW" 1 1000000)

# Initialize or increment counter
# Security: Validate count is numeric before arithmetic operations
if [ -f "$COUNTER_FILE" ] && [ -r "$COUNTER_FILE" ]; then
  count_raw=$(cat "$COUNTER_FILE" 2>/dev/null || echo "0")
  if [[ "$count_raw" =~ ^[0-9]+$ ]]; then
    count=$((count_raw + 1))
  else
    count=1
  fi
else
  count=1
fi

# Security: Validate count before writing
if ! [[ "$count" =~ ^[0-9]+$ ]]; then
  audit_log "SECURITY" "Invalid count value: $count" 2>/dev/null || echo "[StrategicCompact] SECURITY: Invalid count value: $count" >&2
  exit 1
fi

# Write count to file with error handling
echo "$count" > "$COUNTER_FILE" || {
  audit_log "ERROR" "Failed to write counter file: $COUNTER_FILE" 2>/dev/null || echo "[StrategicCompact] ERROR: Failed to write counter file" >&2
  exit 1
}

audit_log "INFO" "Tool call count: $count (threshold: $THRESHOLD)" 2>/dev/null || true

# Suggest compact after threshold tool calls
if [ "$count" -eq "$THRESHOLD" ]; then
  audit_log "INFO" "Threshold reached: $THRESHOLD tool calls - consider /compact" 2>/dev/null || true
  echo "[StrategicCompact] $THRESHOLD tool calls reached - consider /compact if transitioning phases" >&2
fi

# Suggest at regular intervals after threshold
# Security: Validate arithmetic operation result
if [ "$count" -gt "$THRESHOLD" ]; then
  remainder=$((count % 25))
  if [ "$remainder" -eq 0 ]; then
    audit_log "INFO" "Checkpoint reached: $count tool calls - good time for /compact" 2>/dev/null || true
    echo "[StrategicCompact] $count tool calls - good checkpoint for /compact if context is stale" >&2
  fi
fi

# Log script completion
audit_log "INFO" "Script completed successfully" 2>/dev/null || true
