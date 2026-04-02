from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "agent_workspace" / "hooks" / "config.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_prompt() -> str:
    raw = sys.stdin.read().strip()
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(data, dict):
        for key in ("prompt", "text", "message", "input"):
            value = data.get(key)
            if isinstance(value, str):
                return value
    return raw


def main() -> int:
    config = load_config().get("prompt_enrichment", {})
    if not config.get("enabled", False):
        return 0

    prompt = read_prompt().lower()
    if not prompt:
        return 0

    hints: list[str] = []
    for keyword, hint in config.get("keyword_hints", {}).items():
        if keyword.lower() in prompt:
            hints.append(hint)

    if hints:
        print("Repo hints:")
        for hint in hints:
            print(f"- {hint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
