from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "agent_workspace" / "hooks" / "config.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_payload() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def to_paths(payload: dict) -> list[Path]:
    seen: list[Path] = []
    candidates: list[str] = []

    for key in ("file_path", "path"):
        value = payload.get(key)
        if isinstance(value, str):
            candidates.append(value)

    for key in ("file_paths", "paths"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, str))

    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("file_path", "path"):
            value = tool_input.get(key)
            if isinstance(value, str):
                candidates.append(value)
        for key in ("file_paths", "paths"):
            value = tool_input.get(key)
            if isinstance(value, list):
                candidates.extend(item for item in value if isinstance(item, str))

    for raw_path in candidates:
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT / path
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.is_file() and resolved.suffix == ".py" and resolved not in seen:
            seen.append(resolved)
    return seen


def run(cmd: list[str]) -> tuple[int, str]:
    completed = subprocess.run(  # noqa: S603
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = completed.stdout.strip() or completed.stderr.strip()
    return completed.returncode, output


def main() -> int:
    config = load_config().get("post_tool_validation", {})
    if not config.get("enabled", False):
        return 0

    files = to_paths(read_payload())
    max_files = int(config.get("max_files", 20))
    files = files[:max_files]
    if not files:
        return 0

    rel_files = [str(path.relative_to(ROOT)) for path in files]

    if config.get("python_compile", False):
        code, output = run([sys.executable, "-m", "py_compile", *rel_files])
        if code != 0:
            print(output, file=sys.stderr)
            return code

    if config.get("ruff_check", False):
        code, output = run(["ruff", "check", "--quiet", *rel_files])
        if code != 0:
            print(output, file=sys.stderr)
            return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
