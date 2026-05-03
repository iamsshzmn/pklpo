from __future__ import annotations

from pathlib import Path


def test_candles_source_contains_no_legacy_runtime_imports() -> None:
    root = Path("src/candles")
    forbidden = (
        "from src.candles.legacy",
        "import src.candles.legacy",
        "runtime_adapters",
        "sync_runtime",
    )

    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert all(marker not in text for marker in forbidden), path.as_posix()
