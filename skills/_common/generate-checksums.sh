#!/bin/bash
# Generate checksums for all SKILL.md files
# This script should be run after adding or modifying SKILL.md files
# to update the integrity verification database

set -euo pipefail

# Security: Check that script is not running as root
if [ "$(id -u)" -eq 0 ]; then
  echo "SECURITY: Script should not run as root" >&2
  exit 1
fi

# Load security functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_BASE_DIR="${SCRIPT_DIR%/*}"
SECURITY_SCRIPT="$SCRIPT_DIR/security.sh"

if [ ! -f "$SECURITY_SCRIPT" ] || [ ! -r "$SECURITY_SCRIPT" ]; then
  echo "ERROR: Security module not found: $SECURITY_SCRIPT" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$SECURITY_SCRIPT"

# Initialize audit logging
init_audit_log "GenerateChecksums" || {
  echo "WARN: Failed to initialize audit log" >&2
}

# Determine skills directory
SKILLS_DIR="${1:-}"

if [ -z "$SKILLS_DIR" ]; then
  # Try to auto-detect
  if [ -d "${HOME}/.claude/skills" ]; then
    SKILLS_DIR="${HOME}/.claude/skills"
  elif [ -d "$SKILLS_BASE_DIR" ]; then
    SKILLS_DIR="$SKILLS_BASE_DIR"
  else
    echo "ERROR: Cannot locate skills directory" >&2
    echo "Usage: $0 [skills_directory]" >&2
    exit 1
  fi
fi

# Security: Validate skills directory path
if [[ "$SKILLS_DIR" == *".."* ]] || [[ "$SKILLS_DIR" == *"//"* ]]; then
  audit_log "SECURITY" "Path traversal detected: $SKILLS_DIR"
  echo "SECURITY: Invalid skills directory path" >&2
  exit 1
fi

if [ ! -d "$SKILLS_DIR" ]; then
  echo "ERROR: Skills directory not found: $SKILLS_DIR" >&2
  exit 1
fi

audit_log "INFO" "Generating checksums for SKILL.md files in: $SKILLS_DIR"

# Generate checksums
if generate_skill_checksums "$SKILLS_DIR"; then
  audit_log "INFO" "Checksums generated successfully"
  echo "✓ Checksums generated successfully"
  echo "  Location: ${SKILLS_DIR}/_common/checksums.sha256"
  exit 0
else
  audit_log "ERROR" "Failed to generate checksums"
  echo "✗ Failed to generate checksums" >&2
  exit 1
fi
