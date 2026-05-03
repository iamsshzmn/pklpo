from __future__ import annotations

import importlib

import pytest


def test_root_package_does_not_export_removed_sync_shim() -> None:
    import src.candles as candles

    assert not hasattr(candles, "sync_swap_candles")


def test_canonical_sync_entrypoint_is_interfaces_swap_sync() -> None:
    module = importlib.import_module("src.candles.interfaces.swap_sync")
    assert hasattr(module, "sync_swap_candles")


def test_removed_root_sync_shim_is_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("src.candles.sync_swap_candles")
