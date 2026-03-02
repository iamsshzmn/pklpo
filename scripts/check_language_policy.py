#!/usr/bin/env python3
"""
Pre-commit language policy:
- Python source files must be English-only (no Cyrillic characters).
- Repository root README.md must contain Russian text (at least one Cyrillic char).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def _check_python_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}: cannot decode as UTF-8 ({exc})"]

    bad_lines: list[int] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if CYRILLIC_RE.search(line):
            bad_lines.append(idx)
            if len(bad_lines) >= 10:
                break

    if bad_lines:
        errors.append(
            f"{path}: Cyrillic text found in Python source at lines {bad_lines}. "
            "Use English for code descriptions/comments/docstrings/log messages."
        )
    return errors


def _check_root_readme(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}: cannot decode as UTF-8 ({exc})"]

    if not CYRILLIC_RE.search(text):
        return [
            f"{path}: no Cyrillic text found. "
            "Repository README.md must be written in Russian."
        ]
    return []


def main(argv: list[str]) -> int:
    errors: list[str] = []
    for raw in argv:
        path = Path(raw)
        posix = path.as_posix()
        name_lower = path.name.lower()

        if name_lower == "readme.md" and path.parent in {Path("."), Path("")}:
            errors.extend(_check_root_readme(path))
            continue

        if path.suffix.lower() == ".py":
            # Skip virtual env and caches if they leak into file list.
            if "/venv/" in f"/{posix}/" or "/__pycache__/" in f"/{posix}/":
                continue
            errors.extend(_check_python_file(path))

    if errors:
        print("Language policy check failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
