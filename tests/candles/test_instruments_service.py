from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.candles.instruments_service import (
    load_symbols_from_file,
    refresh_instruments_list,
    resolve_instruments_cache_file,
    resolve_repo_instruments_file,
)


class _RepoStub:
    def __init__(self, symbols: list[str]) -> None:
        self._symbols = symbols

    async def list_swap_symbols(self) -> list[str]:
        return self._symbols

    async def get_instrument_counts(self) -> dict[str, int]:
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


def test_resolve_cache_file_uses_runtime_cache_dir_over_repo_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_snapshot = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "candles"
        / "instruments_list.json"
    )
    assert repo_snapshot.exists()

    monkeypatch.setenv("INSTRUMENTS_CACHE_DIR", str(tmp_path))

    path = resolve_instruments_cache_file()

    assert path == tmp_path / "instruments_list.json"
    assert path != repo_snapshot


def test_resolve_repo_instruments_file_points_to_repo_snapshot() -> None:
    repo_snapshot = resolve_repo_instruments_file()

    assert repo_snapshot.name == "instruments_list.json"
    assert repo_snapshot.exists()


def test_load_symbols_from_file_returns_clean_list(tmp_path: Path) -> None:
    instruments_file = tmp_path / "instruments_list.json"
    instruments_file.write_text(
        json.dumps(["BTC-USDT-SWAP", " ", None, "ETH-USDT-SWAP"]),
        encoding="utf-8",
    )

    result = load_symbols_from_file(instruments_file)

    assert result == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]


@pytest.mark.asyncio
async def test_refresh_instruments_list_uses_runtime_cache_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("INSTRUMENTS_CACHE_DIR", str(tmp_path))

    repo = _RepoStub(["ETH-USDT-SWAP", "BTC-USDT-SWAP", "SOL-USDT-SWAP"])
    logger = _LoggerStub()

    result = await refresh_instruments_list(
        repository=repo,  # type: ignore[arg-type]
        logger=logger,
    )

    instruments_file = tmp_path / "instruments_list.json"
    assert instruments_file.exists() is False
    assert result == ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]


@pytest.mark.asyncio
async def test_refresh_instruments_list_reports_changes_without_updating_file(
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
    assert saved == ["BTC-USDT-SWAP", "XRP-USDT-SWAP"]


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
