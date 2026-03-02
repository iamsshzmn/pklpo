from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.candles.instruments_service import (
    refresh_instruments_list,
    resolve_instruments_cache_file,
)


class _RepoStub:
    def __init__(self, symbols: list[str]) -> None:
        self._symbols = symbols

    async def fetch_swap_usdt_symbols(self) -> list[str]:
        return self._symbols

    async def fetch_instrument_counts(self) -> dict[str, int]:
        return {"all": len(self._symbols), "swap": len(self._symbols), "usdt": len(self._symbols)}


class _LoggerStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def info(self, msg, *args):
        self.calls.append(("info", str(msg)))

    def debug(self, msg, *args):
        self.calls.append(("debug", str(msg)))

    def warning(self, msg, *args):
        self.calls.append(("warning", str(msg)))

    def error(self, msg, *args):
        self.calls.append(("error", str(msg)))


def test_resolve_cache_file_falls_back_to_tempdir_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INSTRUMENTS_CACHE_DIR", raising=False)

    path = resolve_instruments_cache_file()

    assert path.name == "instruments_list.json"
    assert path.parent == Path(tempfile.gettempdir())


@pytest.mark.asyncio
async def test_refresh_instruments_list_updates_file(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    instruments_file = cache_dir / "instruments_list.json"
    instruments_file.write_text(
        json.dumps(["BTC-USDT-SWAP", "XRP-USDT-SWAP"]),
        encoding="utf-8",
    )

    repo = _RepoStub(["ETH-USDT-SWAP", "BTC-USDT-SWAP", "SOL-USDT-SWAP"])
    logger = _LoggerStub()

    result = await refresh_instruments_list(
        repository=repo,  # type: ignore[arg-type]
        logger=logger,
        cache_dir=cache_dir,
    )

    assert result == ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
    saved = json.loads(instruments_file.read_text(encoding="utf-8"))
    assert saved == result


@pytest.mark.asyncio
async def test_refresh_instruments_list_noop_when_unchanged(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    instruments_file = cache_dir / "instruments_list.json"
    expected = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
    instruments_file.write_text(json.dumps(expected), encoding="utf-8")

    repo = _RepoStub(["ETH-USDT-SWAP", "SOL-USDT-SWAP", "BTC-USDT-SWAP"])
    logger = _LoggerStub()

    result = await refresh_instruments_list(
        repository=repo,  # type: ignore[arg-type]
        logger=logger,
        cache_dir=cache_dir,
    )

    assert result == expected
    assert json.loads(instruments_file.read_text(encoding="utf-8")) == expected
