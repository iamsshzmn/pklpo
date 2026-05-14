from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _check_file_exists(path: Path) -> str | None:
    if path.exists():
        return None
    return f"missing file: {path.relative_to(ROOT)}"


def _check_json_valid(path: Path) -> str | None:
    if not path.exists():
        return f"missing file: {path.relative_to(ROOT)}"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return f"invalid json: {path.relative_to(ROOT)} ({exc})"
    return None


def _check_claude_settings(path: Path) -> str | None:
    if not path.exists():
        return f"missing file: {path.relative_to(ROOT)}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return f"invalid json: {path.relative_to(ROOT)} ({exc})"

    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return "invalid .claude/settings.json: 'hooks' object is required"

    for stage in ("PostToolUse", "Stop"):
        if stage not in hooks:
            return f"invalid .claude/settings.json: missing hook stage '{stage}'"
    return None


def main() -> int:
    errors: list[str] = []

    required_files = [
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / ".claude" / "settings.json",
        ROOT / "agent_workspace" / "hooks" / "post_tool_validate.py",
        ROOT / "agent_workspace" / "hooks" / "turn_summary.py",
        ROOT / "agent_workspace" / "hooks" / "config.json",
        ROOT / ".vscode" / "extensions.json",
        ROOT / "docs" / "agent-workspace.md",
        ROOT / "docs" / "cursor-baseline.md",
    ]

    for file_path in required_files:
        err = _check_file_exists(file_path)
        if err:
            errors.append(err)

    for json_path in (
        ROOT / ".claude" / "settings.json",
        ROOT / "agent_workspace" / "hooks" / "config.json",
        ROOT / ".vscode" / "extensions.json",
    ):
        err = _check_json_valid(json_path)
        if err:
            errors.append(err)

    err = _check_claude_settings(ROOT / ".claude" / "settings.json")
    if err:
        errors.append(err)

    if errors:
        print("[FAIL] Agent infra validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("[OK] Agent infra validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
