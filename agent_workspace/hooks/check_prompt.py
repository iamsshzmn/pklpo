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


def read_payload() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"prompt": raw}
    return data if isinstance(data, dict) else {"prompt": raw}


def extract_prompt(payload: dict) -> str:
    for key in ("prompt", "text", "message", "input"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    transcript = payload.get("transcript")
    if isinstance(transcript, list):
        parts = [item.get("text", "") for item in transcript if isinstance(item, dict)]
        return "\n".join(part for part in parts if part)
    return ""


def main() -> int:
    config = load_config().get("prompt_safety", {})
    if not config.get("enabled", False):
        return 0

    prompt = extract_prompt(read_payload()).lower()
    if not prompt:
        return 0

    allow_markers = [item.lower() for item in config.get("allow_if_prompt_contains_any", [])]
    if any(marker in prompt for marker in allow_markers):
        return 0

    for pattern in config.get("block_patterns", []):
        if pattern.lower() in prompt:
            print(
                "Blocked by prompt safety hook: destructive command wording requires explicit user confirmation.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
