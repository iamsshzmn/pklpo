#!/bin/bash
# Common Security Functions for Claude Skills
# Provides audit logging and SKILL.md integrity verification

# Security: Initialize audit logging
# Audit log is stored in ~/.claude/skills/audit.log with secure permissions
init_audit_log() {
  local script_name="${1:-unknown}"
  local audit_dir="${HOME}/.claude/skills"
  local audit_file="${audit_dir}/audit.log"

  # Security: Validate audit directory path
  if [[ ! "$audit_dir" == "$HOME"/* ]]; then
    echo "SECURITY: Invalid audit directory path" >&2
    return 1
  fi

  # Create audit directory if it doesn't exist
  if [ ! -d "$audit_dir" ]; then
    mkdir -p "$audit_dir" || {
      echo "SECURITY: Failed to create audit directory" >&2
      return 1
    }
    chmod 700 "$audit_dir" 2>/dev/null || true
  fi

  # Create audit file if it doesn't exist
  if [ ! -f "$audit_file" ]; then
    touch "$audit_file" 2>/dev/null || {
      echo "SECURITY: Failed to create audit file" >&2
      return 1
    }
    chmod 600 "$audit_file" 2>/dev/null || true
  fi

  # Verify audit file permissions
  if [ -f "$audit_file" ]; then
    file_perms=$(stat -c "%a" "$audit_file" 2>/dev/null || stat -f "%OLp" "$audit_file" 2>/dev/null || echo "000")
    if [[ ! "$file_perms" =~ ^[67]00$ ]]; then
      chmod 600 "$audit_file" 2>/dev/null || true
    fi
  fi

  # Export for use in audit_log function
  export AUDIT_FILE="$audit_file"
  export SCRIPT_NAME="$script_name"

  # Log script start
  audit_log "START" "Script started: $script_name (PID: $$, USER: ${USER:-unknown})"
}

# Security: Write audit log entry
# Format: TIMESTAMP | SCRIPT | LEVEL | MESSAGE
audit_log() {
  local level="${1:-INFO}"
  local message="${2:-}"
  local timestamp

  # Generate timestamp (ISO 8601 format)
  if command -v date &> /dev/null; then
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$(date)")
  else
    timestamp="$(date)"
  fi

  # Use AUDIT_FILE if set, otherwise try default location
  local audit_file="${AUDIT_FILE:-${HOME}/.claude/skills/audit.log}"
  local script_name="${SCRIPT_NAME:-unknown}"

  # Security: Validate audit file path
  if [[ ! "$audit_file" == "$HOME"/* ]]; then
    echo "SECURITY: Invalid audit file path" >&2
    return 1
  fi

  # Write log entry (append mode)
  {
    echo "[$timestamp] | $script_name | $level | $message"
  } >> "$audit_file" 2>/dev/null || {
    # Fallback to stderr if audit file write fails
    echo "[$timestamp] | $script_name | $level | $message (audit write failed)" >&2
  }

  # Also output to stderr for immediate visibility of security events
  if [[ "$level" == "SECURITY" ]] || [[ "$level" == "ERROR" ]]; then
    echo "[$script_name] $level: $message" >&2
  fi
}

# Security: Verify SKILL.md file integrity using checksums
# Checksums file: skills/_common/checksums.sha256
verify_skill_checksums() {
  local skills_base_dir="${1:-}"
  local checksums_file="${skills_base_dir}/_common/checksums.sha256"

  # If skills_base_dir not provided, try to detect from script location
  if [ -z "$skills_base_dir" ]; then
    # Try to find skills directory from common locations
    if [ -d "${HOME}/.claude/skills" ]; then
      skills_base_dir="${HOME}/.claude/skills"
    elif [ -d "./skills" ]; then
      skills_base_dir="./skills"
    else
      audit_log "WARN" "Cannot locate skills directory for checksum verification"
      return 0  # Don't fail if we can't find the directory
    fi
  fi

  # Security: Validate skills_base_dir path
  if [[ "$skills_base_dir" == *".."* ]] || [[ "$skills_base_dir" == *"//"* ]]; then
    audit_log "SECURITY" "Path traversal detected in skills_base_dir: $skills_base_dir"
    return 1
  fi

  # Check if checksums file exists
  if [ ! -f "$checksums_file" ]; then
    audit_log "WARN" "Checksums file not found: $checksums_file (first run or not generated yet)"
    return 0  # Don't fail on first run
  fi

  # Security: Validate checksums file is readable
  if [ ! -r "$checksums_file" ]; then
    audit_log "SECURITY" "Checksums file not readable: $checksums_file"
    return 1
  fi

  # Verify checksums file permissions (should be 600)
  if [ -f "$checksums_file" ]; then
    file_perms=$(stat -c "%a" "$checksums_file" 2>/dev/null || stat -f "%OLp" "$checksums_file" 2>/dev/null || echo "000")
    if [[ ! "$file_perms" =~ ^[67]00$ ]]; then
      audit_log "SECURITY" "Checksums file has insecure permissions: $file_perms (expected 600)"
      chmod 600 "$checksums_file" 2>/dev/null || true
    fi
  fi

  # Check if sha256sum is available
  if ! command -v sha256sum &> /dev/null && ! command -v shasum &> /dev/null; then
    audit_log "WARN" "sha256sum/shasum not available, skipping checksum verification"
    return 0  # Don't fail if checksum tool is not available
  fi

  # Determine which checksum command to use
  local checksum_cmd
  if command -v sha256sum &> /dev/null; then
    checksum_cmd="sha256sum"
  else
    checksum_cmd="shasum -a 256"
  fi

  # Verify each SKILL.md file
  local errors=0
  local verified=0

  while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^# ]] && continue

    # Parse checksum file format: CHECKSUM  PATH
    local stored_checksum="${line%% *}"
    local file_path="${line#* }"

    # Remove leading spaces from file_path
    file_path="${file_path#"${file_path%%[![:space:]]*}"}"

    # Skip if line doesn't have expected format
    if [ -z "$stored_checksum" ] || [ -z "$file_path" ]; then
      continue
    fi

    # Construct full path relative to skills_base_dir
    local full_path
    if [[ "$file_path" == /* ]]; then
      full_path="$file_path"
    else
      full_path="${skills_base_dir}/${file_path}"
    fi

    # Security: Validate file path
    if [[ "$full_path" == *".."* ]] || [[ "$full_path" == *"//"* ]]; then
      audit_log "SECURITY" "Path traversal detected in checksum entry: $file_path"
      errors=$((errors + 1))
      continue
    fi

    # Check if file exists
    if [ ! -f "$full_path" ]; then
      audit_log "WARN" "SKILL.md file not found (may have been removed): $file_path"
      continue
    fi

    # Calculate current checksum
    local current_checksum
    if [ "$checksum_cmd" = "sha256sum" ]; then
      current_checksum=$($checksum_cmd "$full_path" 2>/dev/null | cut -d' ' -f1)
    else
      current_checksum=$($checksum_cmd "$full_path" 2>/dev/null | cut -d' ' -f1)
    fi

    # Compare checksums
    if [ "$current_checksum" = "$stored_checksum" ]; then
      verified=$((verified + 1))
    else
      audit_log "SECURITY" "SKILL.md file integrity check FAILED: $file_path (expected: $stored_checksum, got: $current_checksum)"
      errors=$((errors + 1))
    fi
  done < "$checksums_file"

  if [ $errors -eq 0 ]; then
    audit_log "INFO" "SKILL.md integrity verification passed ($verified files verified)"
    return 0
  else
    audit_log "SECURITY" "SKILL.md integrity verification FAILED ($errors errors, $verified verified)"
    return 1
  fi
}

# Security: Generate checksums for all SKILL.md files
# This should be run manually or as part of setup
generate_skill_checksums() {
  local skills_base_dir="${1:-}"
  local checksums_file

  # If skills_base_dir not provided, try to detect from script location
  if [ -z "$skills_base_dir" ]; then
    if [ -d "${HOME}/.claude/skills" ]; then
      skills_base_dir="${HOME}/.claude/skills"
    elif [ -d "./skills" ]; then
      skills_base_dir="./skills"
    else
      echo "ERROR: Cannot locate skills directory" >&2
      return 1
    fi
  fi

  # Security: Validate skills_base_dir path
  if [[ "$skills_base_dir" == *".."* ]] || [[ "$skills_base_dir" == *"//"* ]]; then
    echo "SECURITY: Path traversal detected" >&2
    return 1
  fi

  # Create _common directory if it doesn't exist
  local common_dir="${skills_base_dir}/_common"
  if [ ! -d "$common_dir" ]; then
    mkdir -p "$common_dir" || {
      echo "ERROR: Failed to create _common directory" >&2
      return 1
    }
    chmod 700 "$common_dir" 2>/dev/null || true
  fi

  checksums_file="${common_dir}/checksums.sha256"

  # Check if sha256sum is available
  if ! command -v sha256sum &> /dev/null && ! command -v shasum &> /dev/null; then
    echo "ERROR: sha256sum/shasum not available" >&2
    return 1
  fi

  # Determine which checksum command to use
  local checksum_cmd
  if command -v sha256sum &> /dev/null; then
    checksum_cmd="sha256sum"
  else
    checksum_cmd="shasum -a 256"
  fi

  # Find all SKILL.md files and generate checksums
  local temp_file
  temp_file=$(mktemp "${TMPDIR:-/tmp}/checksums.XXXXXX" 2>/dev/null || echo "/tmp/checksums.$$")

  # Security: Clean up temp file on exit
  trap "rm -f '$temp_file'" EXIT INT TERM

  find "$skills_base_dir" -name "SKILL.md" -type f | while IFS= read -r skill_file; do
    # Security: Validate file path
    if [[ "$skill_file" == *".."* ]] || [[ "$skill_file" == *"//"* ]]; then
      echo "SECURITY: Path traversal detected: $skill_file" >&2
      continue
    fi

    # Calculate checksum
    local checksum
    if [ "$checksum_cmd" = "sha256sum" ]; then
      checksum=$($checksum_cmd "$skill_file" 2>/dev/null | cut -d' ' -f1)
    else
      checksum=$($checksum_cmd "$skill_file" 2>/dev/null | cut -d' ' -f1)
    fi

    # Get relative path from skills_base_dir
    local rel_path="${skill_file#$skills_base_dir/}"

    # Write to temp file
    echo "$checksum  $rel_path" >> "$temp_file"
  done

  # Move temp file to final location with secure permissions
  if [ -f "$temp_file" ] && [ -s "$temp_file" ]; then
    mv "$temp_file" "$checksums_file" || {
      echo "ERROR: Failed to write checksums file" >&2
      rm -f "$temp_file"
      return 1
    }
    chmod 600 "$checksums_file" 2>/dev/null || true
    echo "Generated checksums for SKILL.md files: $checksums_file"
    return 0
  else
    echo "ERROR: No checksums generated" >&2
    rm -f "$temp_file"
    return 1
  fi
}
