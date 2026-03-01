#!/bin/bash
# Continuous Learning - Session Evaluator
# Runs on Stop hook to extract reusable patterns from Claude Code sessions
#
# Why Stop hook instead of UserPromptSubmit:
# - Stop runs once at session end (lightweight)
# - UserPromptSubmit runs every message (heavy, adds latency)
#
# Hook config (in ~/.claude/settings.json):
# {
#   "hooks": {
#     "Stop": [{
#       "matcher": "*",
#       "hooks": [{
#         "type": "command",
#         "command": "~/.claude/skills/continuous-learning/evaluate-session.sh"
#       }]
#     }]
#   }
# }
#
# Patterns to detect: error_resolution, debugging_techniques, workarounds, project_specific
# Patterns to ignore: simple_typos, one_time_fixes, external_api_issues
# Extracted skills saved to: ~/.claude/skills/learned/

set -euo pipefail

# Security: Fail on undefined variables, pipe failures, and errors

# Security: Check that script is not running as root
if [ "$(id -u)" -eq 0 ]; then
  echo "[ContinuousLearning] SECURITY: Script should not run as root" >&2
  exit 1
fi

# Security: Verify required commands are available
for cmd in jq grep; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "[ContinuousLearning] ERROR: Required command '$cmd' is not installed" >&2
    exit 1
  fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_BASE_DIR="${SCRIPT_DIR%/*}"
SECURITY_SCRIPT="${SKILLS_BASE_DIR}/_common/security.sh"

# Load common security functions
if [ -f "$SECURITY_SCRIPT" ] && [ -r "$SECURITY_SCRIPT" ]; then
  # shellcheck source=/dev/null
  source "$SECURITY_SCRIPT"
  # Initialize audit logging
  init_audit_log "ContinuousLearning" || {
    echo "[ContinuousLearning] WARN: Failed to initialize audit log" >&2
  }
  # Verify SKILL.md integrity
  verify_skill_checksums "$SKILLS_BASE_DIR" || {
    audit_log "SECURITY" "SKILL.md integrity check failed"
    # Don't exit on checksum failure, but log it
  }
else
  echo "[ContinuousLearning] WARN: Security module not found: $SECURITY_SCRIPT" >&2
fi
CONFIG_FILE="$SCRIPT_DIR/config.json"
LEARNED_SKILLS_PATH="${HOME}/.claude/skills/learned"
MIN_SESSION_LENGTH=10

# Security: Validate and sanitize path to prevent path traversal
# Returns normalized absolute path or exits with error
sanitize_path() {
  local input_path="$1"
  local base_dir="${2:-$HOME}"

  # Check for path traversal attempts
  if [[ "$input_path" == *".."* ]] || [[ "$input_path" == *"//"* ]]; then
    audit_log "SECURITY" "Path traversal detected in: $input_path" 2>/dev/null || echo "[ContinuousLearning] SECURITY: Path traversal detected in: $input_path" >&2
    exit 1
  fi

  # Expand ~ to home directory
  local expanded_path="${input_path/#\~/$HOME}"

  # Convert to absolute path
  local abs_path
  if [[ "$expanded_path" == /* ]]; then
    abs_path="$expanded_path"
  else
    # For relative paths, resolve from base_dir
    if [ -d "$base_dir/$expanded_path" ] 2>/dev/null; then
      abs_path="$(cd "$base_dir/$expanded_path" && pwd)"
    elif [ -d "$expanded_path" ] 2>/dev/null; then
      abs_path="$(cd "$expanded_path" && pwd)"
    else
      # Path doesn't exist yet, construct it safely
      abs_path="$base_dir/$expanded_path"
      # Remove any double slashes
      abs_path="${abs_path//\/\//\/}"
    fi
  fi

  # Verify path is within allowed base directory
  # Use realpath if available for better normalization, otherwise use string comparison
  if command -v realpath &> /dev/null; then
    local normalized_base normalized_path
    normalized_base="$(realpath "$base_dir")"
    normalized_path="$(realpath -m "$abs_path")"
    if [[ "$normalized_path" == "$normalized_base"/* ]] || [[ "$normalized_path" == "$normalized_base" ]]; then
      echo "$normalized_path"
    else
      audit_log "SECURITY" "Path outside allowed directory: $input_path" 2>/dev/null || echo "[ContinuousLearning] SECURITY: Path outside allowed directory: $input_path" >&2
      exit 1
    fi
  else
    # Fallback: string comparison (less robust but works)
    if [[ "$abs_path" == "$base_dir"/* ]] || [[ "$abs_path" == "$base_dir" ]]; then
      echo "$abs_path"
    else
      audit_log "SECURITY" "Path outside allowed directory: $input_path" 2>/dev/null || echo "[ContinuousLearning] SECURITY: Path outside allowed directory: $input_path" >&2
      exit 1
    fi
  fi
}

# Security: Validate numeric input with bounds
validate_positive_integer() {
  local value="$1"
  local min="${2:-1}"
  local max="${3:-10000}"

  # Check if it's a valid integer
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    audit_log "SECURITY" "Invalid integer value: $value" 2>/dev/null || echo "[ContinuousLearning] SECURITY: Invalid integer value: $value" >&2
    exit 1
  fi

  # Check bounds
  if [ "$value" -lt "$min" ] || [ "$value" -gt "$max" ]; then
    audit_log "SECURITY" "Value out of bounds [$min-$max]: $value" 2>/dev/null || echo "[ContinuousLearning] SECURITY: Value out of bounds [$min-$max]: $value" >&2
    exit 1
  fi

  echo "$value"
}

# Security: Validate file exists and is readable
validate_file_readable() {
  local file_path="$1"

  if [ ! -f "$file_path" ]; then
    return 1
  fi

  if [ ! -r "$file_path" ]; then
    audit_log "SECURITY" "File not readable: $file_path" 2>/dev/null || echo "[ContinuousLearning] SECURITY: File not readable: $file_path" >&2
    return 1
  fi

  return 0
}

# Load config if exists
if [ -f "$CONFIG_FILE" ]; then
  # Security: Validate config file is readable
  if [ ! -r "$CONFIG_FILE" ]; then
    audit_log "SECURITY" "Config file not readable: $CONFIG_FILE" 2>/dev/null || echo "[ContinuousLearning] SECURITY: Config file not readable: $CONFIG_FILE" >&2
    exit 1
  fi

  # Security: Validate jq is available before using it
  if ! command -v jq &> /dev/null; then
    audit_log "ERROR" "jq is required but not installed" 2>/dev/null || echo "[ContinuousLearning] ERROR: jq is required but not installed" >&2
    exit 1
  fi

  audit_log "INFO" "Loaded config from: $CONFIG_FILE" 2>/dev/null || true

  # Load and validate min_session_length
  local_min_length=$(jq -r '.min_session_length // 10' "$CONFIG_FILE" 2>/dev/null || echo "10")
  MIN_SESSION_LENGTH=$(validate_positive_integer "$local_min_length" 1 10000)

  # Load and sanitize learned_skills_path
  local_skills_path=$(jq -r '.learned_skills_path // "~/.claude/skills/learned/"' "$CONFIG_FILE" 2>/dev/null || echo "~/.claude/skills/learned/")
  LEARNED_SKILLS_PATH=$(sanitize_path "$local_skills_path" "$HOME")
fi

# Security: Ensure learned skills directory is within allowed path
LEARNED_SKILLS_PATH=$(sanitize_path "$LEARNED_SKILLS_PATH" "$HOME")

# Ensure learned skills directory exists with secure permissions
if [ ! -d "$LEARNED_SKILLS_PATH" ]; then
  mkdir -p "$LEARNED_SKILLS_PATH" || {
    audit_log "ERROR" "Failed to create directory: $LEARNED_SKILLS_PATH" 2>/dev/null || echo "[ContinuousLearning] ERROR: Failed to create directory: $LEARNED_SKILLS_PATH" >&2
    exit 1
  }
  # Security: Set restrictive permissions (owner read/write/execute only)
  chmod 700 "$LEARNED_SKILLS_PATH" 2>/dev/null || true
  audit_log "INFO" "Created learned skills directory: $LEARNED_SKILLS_PATH" 2>/dev/null || true
fi

# Get transcript path from environment (set by Claude Code)
transcript_path="${CLAUDE_TRANSCRIPT_PATH:-}"

if [ -z "$transcript_path" ]; then
  exit 0
fi

# Security: Validate and sanitize transcript path
# Only allow paths within user's home or /tmp
if [[ "$transcript_path" == "$HOME"/* ]] || [[ "$transcript_path" == "/tmp"/* ]]; then
  sanitized_transcript_path="$transcript_path"
  audit_log "INFO" "Processing transcript: $transcript_path" 2>/dev/null || true
else
  audit_log "SECURITY" "Transcript path outside allowed locations: $transcript_path" 2>/dev/null || echo "[ContinuousLearning] SECURITY: Transcript path outside allowed locations: $transcript_path" >&2
  exit 1
fi

# Security: Validate file exists and is readable
if ! validate_file_readable "$sanitized_transcript_path"; then
  exit 0
fi

# Count messages in session
# Security: Use safe grep with error handling
message_count=$(grep -c '"type":"user"' "$sanitized_transcript_path" 2>/dev/null || echo "0")

# Validate message_count is a number
if ! [[ "$message_count" =~ ^[0-9]+$ ]]; then
  message_count=0
fi

# Skip short sessions
if [ "$message_count" -lt "$MIN_SESSION_LENGTH" ]; then
  audit_log "INFO" "Session too short ($message_count messages < $MIN_SESSION_LENGTH), skipping" 2>/dev/null || true
  echo "[ContinuousLearning] Session too short ($message_count messages), skipping" >&2
  exit 0
fi

# Signal to Claude that session should be evaluated for extractable patterns
audit_log "INFO" "Session evaluation: $message_count messages, saving to $LEARNED_SKILLS_PATH" 2>/dev/null || true
echo "[ContinuousLearning] Session has $message_count messages - evaluate for extractable patterns" >&2
echo "[ContinuousLearning] Save learned skills to: $LEARNED_SKILLS_PATH" >&2

# Log script completion
audit_log "INFO" "Script completed successfully" 2>/dev/null || true
