from __future__ import annotations

import importlib
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_tqdm() -> None:
    fake_tqdm = types.ModuleType("tqdm")
    fake_tqdm.tqdm = object()
    sys.modules.setdefault("tqdm", fake_tqdm)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "module_name",
    [
        "src.candles",
        "src.candles.ccxt_okx_adapter",
        "src.candles.domain.policies",
        "src.candles.domain.sync_config",
        "src.candles.instruments_service",
        "src.candles.load_instruments",
        "src.candles.interfaces",
        "src.candles.interfaces.airflow_sync",
        "src.candles.interfaces.swap_sync",
        "src.candles.observability.metrics",
        "src.candles.observability.tracer",
        "src.candles.ports",
        "src.candles.repository",
        "src.candles.update_instruments_list",
    ],
)
def test_candles_module_import_smoke(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module is not None


@pytest.mark.parametrize(
    "module_name",
    [
        "src.candles.candles_cli_service",
        "src.candles.parity_check",
        "src.candles.swap_cli",
        "src.candles.sync_candles",
        "src.candles.sync_policy",
        "src.candles.sync_swap_candles",
    ],
)
def test_removed_legacy_modules_are_not_importable(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
