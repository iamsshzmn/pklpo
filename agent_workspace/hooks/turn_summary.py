from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "agent_workspace" / "hooks" / "config.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def git_changed_files(limit: int) -> list[str]:
    git_bin = shutil.which("git")
    if not git_bin:
        return []

    completed = subprocess.run(  # noqa: S603
        [git_bin, "status", "--short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return []

    files: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else line
        files.append(path)
        if len(files) >= limit:
            break
    return files


def main() -> int:
    config = load_config().get("turn_summary", {})
    if not config.get("enabled", False):
        return 0

    files = git_changed_files(int(config.get("max_files", 12)))
    if files:
        print("Changed files:")
        for path in files:
            print(f"- {path}")
    else:
        print("Changed files: none detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
